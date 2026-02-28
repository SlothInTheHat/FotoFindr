import uuid
import sqlite3
import json
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Storage ──────────────────────────────────────────────────────────────────

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

DB_PATH = Path("fotofindr.db")


# ── Database ─────────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS photos (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                storage_url TEXT NOT NULL,
                caption     TEXT DEFAULT '',
                tags        TEXT DEFAULT '[]',
                created_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS people (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                name        TEXT,
                photo_count INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)


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
    file: UploadFile = File(...),
    user_id: str = Form(...),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Only image files accepted.")

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large.")

    photo_id = str(uuid.uuid4())
    ext = Path(file.filename or "photo.jpg").suffix or ".jpg"
    save_path = UPLOAD_DIR / f"{photo_id}{ext}"
    save_path.write_bytes(file_bytes)
    storage_url = f"/uploads/{photo_id}{ext}"

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO photos (id, user_id, storage_url) VALUES (?, ?, ?)",
            (photo_id, user_id, storage_url),
        )

    return {"photo_id": photo_id, "storage_url": storage_url, "message": "Uploaded."}


@app.post("/search/")
def search_photos(req: SearchRequest):
    # No AI yet — return all photos for this user
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, user_id, storage_url, caption, tags, created_at FROM photos "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (req.user_id, req.limit),
        ).fetchall()

    photos = []
    for r in rows:
        photos.append({
            "id": r["id"],
            "user_id": r["user_id"],
            "storage_url": r["storage_url"],
            "caption": r["caption"] or "",
            "tags": json.loads(r["tags"] or "[]"),
            "detected_objects": [],
            "emotions": [],
            "person_ids": [],
            "importance_score": 1.0,
            "low_value_flags": [],
        })

    return {
        "photos": photos,
        "narration_text": f"Showing {len(photos)} photos.",
        "narration": None,
        "total": len(photos),
    }


@app.get("/photos/{user_id}")
def get_recent_photos(user_id: str, limit: int = 10):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, user_id, storage_url, caption, tags, created_at FROM photos "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "user_id": r["user_id"],
            "storage_url": r["storage_url"],
            "caption": r["caption"] or "",
            "tags": json.loads(r["tags"] or "[]"),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.get("/profiles/{user_id}")
def list_profiles(user_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, photo_count FROM people WHERE user_id = ? ORDER BY photo_count DESC",
            (user_id,),
        ).fetchall()
    return [{"id": r["id"], "name": r["name"], "photo_count": r["photo_count"], "cover_photo_url": None} for r in rows]


@app.patch("/profiles/{person_id}/name")
def name_person(person_id: str, body: NameRequest):
    with get_conn() as conn:
        conn.execute("UPDATE people SET name = ? WHERE id = ?", (body.name.strip(), person_id))
    return {"ok": True, "person_id": person_id, "name": body.name.strip()}
