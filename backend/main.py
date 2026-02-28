import sys
import uuid
import traceback
from pathlib import Path
from contextlib import asynccontextmanager

# Allow running from inside backend/ (uvicorn main:app) without PYTHONPATH tricks.
# Adds the project root so that `backend`, `pipeline`, and `search` are all importable.
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from PIL import Image, ExifTags
import io

from backend.db import (
    init_db,
    insert_photo,
    search_photos_by_vector,
    get_all_photos_for_user,
    get_people,
    name_person,
)
from search.query import parse_filters
from pipeline.clip_embed import embed_text_async
from pipeline.runner import run_pipeline

# ── Storage ───────────────────────────────────────────────────────────────────

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ── App ───────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="FotoFindr API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# ── Models ────────────────────────────────────────────────────────────────────


class SearchRequest(BaseModel):
    query: str
    user_id: str
    limit: int = 30


class NameRequest(BaseModel):
    name: str


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload/")
async def upload_photo(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Form(...),
    max_width: int = 1080,  # max width for resizing
    quality: int = 85,  # JPEG quality
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Only image files accepted.")

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large.")

    photo_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{photo_id}.jpg"

    try:
        img = Image.open(io.BytesIO(file_bytes))

        # Fix orientation based on EXIF
        try:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == "Orientation":
                    break
            exif = img._getexif()
            if exif is not None:
                orientation_value = exif.get(orientation)
                if orientation_value == 3:
                    img = img.rotate(180, expand=True)
                elif orientation_value == 6:
                    img = img.rotate(270, expand=True)
                elif orientation_value == 8:
                    img = img.rotate(90, expand=True)
        except Exception:
            # ignore if EXIF not present
            pass

        # Convert to RGB for JPEG compatibility
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Resize while keeping aspect ratio
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # Save compressed JPEG
        img.save(save_path, format="JPEG", quality=quality, optimize=True)

        compressed_bytes = save_path.read_bytes()

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image processing failed: {e}")

    storage_url = f"/uploads/{photo_id}.jpg"

    insert_photo(photo_id, user_id, storage_url)

    # Background AI pipeline
    background_tasks.add_task(
        run_pipeline, photo_id, user_id, storage_url, compressed_bytes
    )

    return {"photo_id": photo_id, "storage_url": storage_url, "message": "Uploaded."}


@app.post("/search/")
async def search_photos(req: SearchRequest):
    filters = parse_filters(req.query)

    # Resolve "me" → most-photographed face cluster for this user
    if filters.pop("wants_me", False):
        people = get_people(req.user_id)
        if people:
            filters["person_id"] = people[0]["id"]

    # Resolve named person → person_id by name match
    person_name = filters.pop("person_name", None)
    if person_name:
        for p in get_people(req.user_id):
            if p.get("name", "").lower() == person_name.lower():
                filters["person_id"] = p["id"]
                break

    try:
        embedding = await embed_text_async(req.query)
        photos = search_photos_by_vector(embedding, req.user_id, filters, limit=req.limit)
    except Exception as e:
        print(f"[search] CLIP error: {e}\n{traceback.format_exc()}")
        try:
            photos = get_all_photos_for_user(req.user_id)[:req.limit]
        except Exception as e2:
            print(f"[search] fallback error: {e2}\n{traceback.format_exc()}")
            photos = []

    return {
        "photos": photos,
        "narration_text": f"Found {len(photos)} photos matching '{req.query}'.",
        "narration": None,
        "total": len(photos),
    }


@app.get("/photos/{user_id}")
def get_recent_photos(user_id: str, limit: int = 10):
    return get_all_photos_for_user(user_id)[:limit]


@app.get("/profiles/{user_id}")
def list_profiles(user_id: str):
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "photo_count": p["photo_count"],
            "cover_photo_url": p.get("cover_photo_url"),
        }
        for p in get_people(user_id)
    ]


@app.patch("/profiles/{person_id}/name")
def name_person_endpoint(person_id: str, body: NameRequest):
    name_person(person_id, body.name.strip())
    return {"ok": True, "person_id": person_id, "name": body.name.strip()}
