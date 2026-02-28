import sys
import uuid
import json
import asyncio
import traceback
import numpy as np


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)
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
import pillow_heif
import io

from backend.db import (
    init_db,
    insert_photo,
    update_photo_pipeline_result,
    search_photos_by_vector,
    get_all_photos_for_user,
    get_people,
    name_person,
)
import backend.snowflake_db as sf_db
from search.query import parse_filters
from pipeline.objects import detect_objects
from backend.pipeline.faces import get_face_emotions

# from pipeline.clip_embed import embed_text_async

# ── Storage ───────────────────────────────────────────────────────────────────

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

DEMO_USER_ID = "00000000-0000-0000-0000-000000000001"


# ── App ───────────────────────────────────────────────────────────────────────


async def _startup_clear() -> None:
    """On server start: clear Snowflake then repopulate from existing uploads."""
    loop = asyncio.get_running_loop()

    # Clear Snowflake
    try:
        await loop.run_in_executor(None, sf_db.clear_photos, DEMO_USER_ID)
        print("[startup] Snowflake cleared for demo user.")
    except Exception as e:
        print(f"[startup] Snowflake clear failed (non-fatal): {e}")

    # Repopulate from every photo already in SQLite + uploads folder
    photos = get_all_photos_for_user(DEMO_USER_ID)
    queued = 0
    for photo in photos:
        image_path = UPLOAD_DIR / f"{photo['id']}.jpg"
        if image_path.exists():
            asyncio.create_task(_run_ai_pipeline(photo["id"], image_path, photo))
            queued += 1
    print(f"[startup] Queued {queued}/{len(photos)} photos for AI pipeline.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    sf_db.init_schema()
    asyncio.create_task(_startup_clear())
    yield


app = FastAPI(title="FotoFindr API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# ── AI pipeline ───────────────────────────────────────────────────────────────


async def _run_ai_pipeline(photo_id: str, image_path: Path, photo_meta: dict | None = None) -> None:
    """Run YOLO + DeepFace on the saved JPEG and persist results to both DBs.

    photo_meta: existing SQLite record (user_id, storage_url, caption, tags, …).
    When provided, all metadata is included in the Snowflake upsert so the row
    is created if it doesn't exist yet.
    """
    try:
        image_bytes = image_path.read_bytes()
    except Exception as e:
        print(f"[pipeline] could not read {image_path}: {e}")
        return

    loop = asyncio.get_running_loop()

    yolo_result, deepface_result = await asyncio.gather(
        detect_objects(image_bytes),
        loop.run_in_executor(None, get_face_emotions, str(image_path.resolve())),
        return_exceptions=True,
    )

    # Serialize YOLO
    if isinstance(yolo_result, Exception) or yolo_result is None:
        print(f"[pipeline] yolo failed for {photo_id}: {yolo_result}")
        yolo_json = "[]"
    else:
        yolo_json = json.dumps([{"label": o.label, "confidence": o.confidence} for o in yolo_result])

    # Serialize DeepFace
    if isinstance(deepface_result, Exception) or (isinstance(deepface_result, dict) and "error" in deepface_result):
        print(f"[pipeline] deepface failed for {photo_id}: {deepface_result}")
        deepface_json = "[]"
    else:
        deepface_json = json.dumps(deepface_result if isinstance(deepface_result, list) else [deepface_result], cls=_NumpyEncoder)

    meta = photo_meta or {}
    result = {
        "detected_objects":  yolo_json,
        "emotions":          deepface_json,
        "user_id":           meta.get("user_id", ""),
        "caption":           meta.get("caption"),
        "tags":              meta.get("tags", []),
        "importance_score":  meta.get("importance_score", 1.0),
        "low_value_flags":   meta.get("low_value_flags", []),
        "person_ids":        meta.get("person_ids", []),
    }

    try:
        update_photo_pipeline_result(photo_id, result)
    except Exception as e:
        print(f"[pipeline] sqlite update failed for {photo_id}: {e}")

    # Upsert to Snowflake — inserts the row if it doesn't exist yet, otherwise updates it.
    filename = meta.get("storage_url", f"/uploads/{photo_id}.jpg")
    try:
        await loop.run_in_executor(None, sf_db.upsert_photo, photo_id, filename, result)  # type: ignore[arg-type]
    except Exception as e:
        print(f"[pipeline] snowflake upsert failed for {photo_id}: {e}")


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


@app.get("/test-snowflake")
def test_snowflake():
    try:
        import snowflake.connector
        from backend.config import settings
        conn = snowflake.connector.connect(
            account=settings.snowflake_account.replace("/", "-"),
            user=settings.snowflake_user,
            password=settings.snowflake_password,
            database=settings.snowflake_database,
            schema=settings.snowflake_schema,
            warehouse=settings.snowflake_warehouse,
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM photos")
        count = cur.fetchone()[0]
        conn.close()
        return {"status": "ok", "rows_in_photos": count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/upload/")
async def upload_photo(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Form(...),
    device_uri: str = Form(default=""),  # original on-device URI (ph://, content://, …)
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
        # Detect HEIC/HEIF and convert
        if file.content_type in [
            "image/heic",
            "image/heif",
        ] or file.filename.lower().endswith((".heic", ".heif")):
            heif_file = pillow_heif.read_heif(file_bytes)
            img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data)
        else:
            img = Image.open(io.BytesIO(file_bytes))

        # Fix orientation based on EXIF
        try:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == "Orientation":
                    break
            exif = img.getexif()
            if exif is not None:
                orientation_value = exif.get(orientation)
                if orientation_value == 3:
                    img = img.rotate(180, expand=True)
                elif orientation_value == 6:
                    img = img.rotate(270, expand=True)
                elif orientation_value == 8:
                    img = img.rotate(90, expand=True)
        except Exception:
            pass

        # Convert to RGB for JPEG
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Resize while keeping aspect ratio
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # Save as JPEG
        img.save(save_path, format="JPEG", quality=quality, optimize=True)
        compressed_bytes = save_path.read_bytes()

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image processing failed: {e}")

    storage_url = f"/uploads/{photo_id}.jpg"
    insert_photo(photo_id, user_id, storage_url)
    background_tasks.add_task(sf_db.insert_photo, photo_id, device_uri or storage_url, user_id)
    background_tasks.add_task(
        _run_ai_pipeline, photo_id, save_path,
        {"user_id": user_id, "storage_url": storage_url},
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
        photos = search_photos_by_vector(
            embedding, req.user_id, filters, limit=req.limit
        )
    except Exception as e:
        print(f"[search] CLIP error: {e}\n{traceback.format_exc()}")
        try:
            photos = get_all_photos_for_user(req.user_id)[: req.limit]
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


@app.post("/clear/{user_id}")
async def clear_user_photos(user_id: str):
    """Delete all Snowflake rows for a user. Called by mobile app before re-uploading."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, sf_db.clear_photos, user_id)
    return {"ok": True, "user_id": user_id}


@app.post("/reprocess/{user_id}")
async def reprocess_all(user_id: str, background_tasks: BackgroundTasks):
    """Re-run YOLO + DeepFace on every stored photo for a user."""
    photos = get_all_photos_for_user(user_id)
    queued = 0
    for photo in photos:
        image_path = UPLOAD_DIR / f"{photo['id']}.jpg"
        if image_path.exists():
            background_tasks.add_task(_run_ai_pipeline, photo["id"], image_path, photo)
            queued += 1
    return {"queued": queued, "total": len(photos)}
