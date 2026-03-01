import sys
import uuid
import json
import asyncio
import traceback
import numpy as np
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class _NumpyEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)


from pathlib import Path
from contextlib import asynccontextmanager

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

from db import (
    init_db,
    insert_photo,
    update_photo_pipeline_result,
    search_photos_by_vector,
    get_all_photos_for_user,
    get_people,
    name_person,
    clear_user_photos,
    get_pipeline_status,
    get_photo_by_id,
    get_untagged_photos,
)
from gemini_service import find_matching_labels
from narration import router as narration_router
import snowflake_db as sf_db
from pipeline.objects import detect_objects
from backend.pipeline.faces import get_face_emotions

# ── Storage ───────────────────────────────────────────────────────────────────

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
NARRATION_DIR = Path("uploads/narrations")
NARRATION_DIR.mkdir(parents=True, exist_ok=True)

DEMO_USER_ID = "00000000-0000-0000-0000-000000000001"


# ── App ───────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    sf_db.init_schema()
    yield


app = FastAPI(title="FotoFindr API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/uploads/narrations",
    StaticFiles(directory="uploads/narrations"),
    name="narrations",
)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.include_router(narration_router)


# ── AI pipeline ───────────────────────────────────────────────────────────────


async def _run_ai_pipeline(
    photo_id: str, image_path: Path, photo_meta: dict | None = None
) -> None:
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

    if isinstance(yolo_result, Exception) or yolo_result is None:
        print(f"[pipeline] yolo failed for {photo_id}: {yolo_result}")
        yolo_json = "[]"
    else:
        yolo_json = json.dumps(
            [{"label": o.label, "confidence": o.confidence} for o in yolo_result]
        )

    if isinstance(deepface_result, Exception) or (
        isinstance(deepface_result, dict) and "error" in deepface_result
    ):
        print(f"[pipeline] deepface failed for {photo_id}: {deepface_result}")
        deepface_json = "[]"
    else:
        deepface_json = json.dumps(
            deepface_result if isinstance(deepface_result, list) else [deepface_result],
            cls=_NumpyEncoder,
        )

    meta = photo_meta or {}
    result = {
        "detected_objects": yolo_json,
        "emotions": deepface_json,
        "user_id": meta.get("user_id", ""),
        "caption": meta.get("caption"),
        "tags": meta.get("tags", []),
        "importance_score": meta.get("importance_score", 1.0),
        "low_value_flags": meta.get("low_value_flags", []),
        "person_ids": meta.get("person_ids", []),
    }

    try:
        update_photo_pipeline_result(photo_id, result)
    except Exception as e:
        print(f"[pipeline] sqlite update failed for {photo_id}: {e}")

    filename = meta.get("storage_url", f"/uploads/{photo_id}.jpg")
    try:
        await loop.run_in_executor(None, sf_db.upsert_photo, photo_id, filename, result)
    except Exception as e:
        print(f"[pipeline] snowflake upsert failed for {photo_id}: {e}")


# ── Models ────────────────────────────────────────────────────────────────────


class SearchRequest(BaseModel):
    query: str
    user_id: str
    limit: int = 20


class NameRequest(BaseModel):
    name: str


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload/")
async def upload_photo(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    device_uri: str = Form(default=""),
    max_width: int = 1080,
    quality: int = 85,
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Only image files accepted.")

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large.")

    photo_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{photo_id}.jpg"

    try:
        if file.content_type in [
            "image/heic",
            "image/heif",
        ] or file.filename.lower().endswith((".heic", ".heif")):
            heif_file = pillow_heif.read_heif(file_bytes)
            img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data)
        else:
            img = Image.open(io.BytesIO(file_bytes))

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

        if img.mode != "RGB":
            img = img.convert("RGB")

        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        img.save(save_path, format="JPEG", quality=quality, optimize=True)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image processing failed: {e}")

    storage_url = f"/uploads/{photo_id}.jpg"
    insert_photo(photo_id, user_id, storage_url, device_uri)

    return {"photo_id": photo_id, "storage_url": storage_url, "message": "Uploaded."}


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
async def clear_endpoint(user_id: str):
    for f in UPLOAD_DIR.glob("*.jpg"):
        try:
            f.unlink()
        except Exception:
            pass

    try:
        clear_user_photos(user_id)
    except Exception as e:
        print(f"[clear] SQLite clear failed: {e}")

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, sf_db.clear_photos, user_id)
    except Exception as e:
        print(f"[clear] Snowflake clear failed: {e}")

    return {"ok": True, "user_id": user_id}


@app.get("/status/{user_id}")
async def pipeline_status(user_id: str):
    return get_pipeline_status(user_id)


@app.post("/search/")
async def search_photos(req: SearchRequest):
    query = req.query.strip()
    user_id = req.user_id.strip()

    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id, metadata, yolo_data, deepface_data FROM PHOTOS")
        ).fetchall()

    photos = []
    all_objects = set()
    all_emotions = set()

    for row in result:
        # Metadata
        try:
            meta = json.loads(row.metadata)
        except (TypeError, json.JSONDecodeError):
            meta = {}

        # YOLO labels
        try:
            yolo_objs = json.loads(row.yolo_data)
            yolo_labels = [obj["label"] for obj in yolo_objs]
        except (TypeError, json.JSONDecodeError, KeyError):
            yolo_labels = []

        # DeepFace emotions
        try:
            df_objs = json.loads(row.deepface_data)
            dominant_emotions = [
                obj["dominant_emotion"] for obj in df_objs if "dominant_emotion" in obj
            ]
        except (TypeError, json.JSONDecodeError, KeyError):
            dominant_emotions = []

        # Collect all objects and emotions seen so far
        all_objects.update(yolo_labels)
        all_emotions.update(dominant_emotions)

        photos.append(
            {
                "metadata": meta,
                "yolo_labels": yolo_labels,
                "dominant_emotions": dominant_emotions,
                "id": row.id,
            }
        )

    # 2️⃣ Ask Gemini which objects/emotions match query
    matched_labels = find_matches(query, list(all_objects), list(all_emotions))

    # 3️⃣ Filter photos: keep those that have at least one matching label
    filtered_photos = []
    for photo in photos:
        labels_in_photo = set(photo["yolo_labels"] + photo["dominant_emotions"])
        if labels_in_photo & set(matched_labels):
            filtered_photos.append(photo)

    return {
        "ok": True,
        "query": query,
        "matched_labels": matched_labels,
        "photos": filtered_photos,
    }


@app.get("/image_labels/")
def image_labels(image_id: str):
    photo = get_photo_by_id(image_id)
    if not photo:
        raise HTTPException(status_code=404, detail=f"Photo {image_id} not found")

    labels: list[str] = []
    for obj in photo.get("detected_objects") or []:
        if isinstance(obj, dict) and obj.get("label"):
            labels.append(obj["label"])
    for face in photo.get("emotions") or []:
        if isinstance(face, dict) and face.get("dominant_emotion"):
            labels.append(face["dominant_emotion"])

    return {"image_id": image_id, "labels": labels}


@app.get("/untagged/{user_id}")
def untagged_photos(user_id: str):
    """Photos that completed the pipeline but have no detected objects or emotions."""
    return {"photos": get_untagged_photos(user_id)}


@app.post("/search/")
async def search_photos(req: SearchRequest):
    all_photos = get_all_photos_for_user(req.user_id)

    object_labels: set[str] = set()
    emotion_labels: set[str] = set()
    for p in all_photos:
        for obj in p.get("detected_objects") or []:
            if isinstance(obj, dict) and obj.get("label"):
                object_labels.add(obj["label"].lower())
        for face in p.get("emotions") or []:
            if isinstance(face, dict) and face.get("dominant_emotion"):
                emotion_labels.add(face["dominant_emotion"].lower())

    loop = asyncio.get_running_loop()
    matching = await loop.run_in_executor(
        None, find_matching_labels, req.query, list(object_labels), list(emotion_labels)
    )
    matching_set = {m.lower() for m in matching}

    if matching_set:
        photos = [
            p
            for p in all_photos
            if any(
                isinstance(obj, dict) and obj.get("label", "").lower() in matching_set
                for obj in (p.get("detected_objects") or [])
            )
            or any(
                isinstance(face, dict)
                and face.get("dominant_emotion", "").lower() in matching_set
                for face in (p.get("emotions") or [])
            )
        ]
    else:
        photos = all_photos

    return {"photos": photos[: req.limit], "matched_labels": list(matching_set)}


@app.post("/reprocess/{user_id}")
async def reprocess_all(user_id: str, background_tasks: BackgroundTasks):
    photos = get_all_photos_for_user(user_id)
    queued = 0
    for photo in photos:
        image_path = UPLOAD_DIR / f"{photo['id']}.jpg"
        if image_path.exists():
            background_tasks.add_task(_run_ai_pipeline, photo["id"], image_path, photo)
            queued += 1
    print(f"[reprocess] Queued {queued}/{len(photos)} photos for user {user_id}")
    return {"queued": queued, "total": len(photos)}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    messages = []
    for err in exc.errors():
        field = err["loc"][-1]
        messages.append(f"{field}: {err['msg']}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation failed, maybe you have a typo or missing field?",
            "message": ", ".join(messages),
        },
    )
