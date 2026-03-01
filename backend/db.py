"""
Database helpers — SQLite for metadata, numpy for vector search.
No external services needed.
"""

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

import numpy as np

DB_PATH = Path("fotofindr.db")


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom else 0.0


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS photos (
    id               TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL,
    storage_url      TEXT NOT NULL,
    caption          TEXT,
    tags             TEXT DEFAULT '[]',
    detected_objects TEXT DEFAULT '[]',
    emotions         TEXT DEFAULT '[]',
    person_ids       TEXT DEFAULT '[]',
    importance_score REAL DEFAULT 1.0,
    low_value_flags  TEXT DEFAULT '[]',
    embedding        TEXT DEFAULT NULL,
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS people (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL,
    name                TEXT,
    embedding_centroid  TEXT DEFAULT NULL,
    photo_count         INTEGER DEFAULT 0,
    cover_photo_url     TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);
"""


def init_db() -> None:
    with _get_conn() as conn:
        conn.executescript(SCHEMA_SQL)
        # Migrate: silently add columns that may be absent in older DBs
        for col, defn in [
            ("detected_objects", "TEXT DEFAULT '[]'"),
            ("emotions",         "TEXT DEFAULT '[]'"),
            ("person_ids",       "TEXT DEFAULT '[]'"),
            ("importance_score", "REAL DEFAULT 1.0"),
            ("low_value_flags",  "TEXT DEFAULT '[]'"),
            ("embedding",        "TEXT DEFAULT NULL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE photos ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass  # column already exists


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------


def clear_user_photos(user_id: str) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM photos WHERE user_id = ?", (user_id,))


def insert_photo(photo_id: str, user_id: str, storage_url: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO photos (id, user_id, storage_url) VALUES (?, ?, ?)",
            (photo_id, user_id, storage_url),
        )


def update_photo_pipeline_result(photo_id: str, result: dict) -> None:
    embedding = result.get("embedding")
    embedding_json = json.dumps(embedding) if embedding else None

    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE photos SET
                caption          = ?,
                tags             = ?,
                detected_objects = ?,
                emotions         = ?,
                person_ids       = ?,
                importance_score = ?,
                low_value_flags  = ?,
                embedding        = ?
            WHERE id = ?
            """,
            (
                result.get("caption"),
                json.dumps(result.get("tags", [])),
                result.get("detected_objects", "[]"),
                result.get("emotions", "[]"),
                json.dumps(result.get("person_ids", [])),
                result.get("importance_score", 1.0),
                json.dumps(result.get("low_value_flags", [])),
                embedding_json,
                photo_id,
            ),
        )


def _row_to_dict(row) -> dict:
    d = dict(row)
    for key in ("tags", "detected_objects", "emotions", "person_ids", "low_value_flags"):
        if isinstance(d.get(key), str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                d[key] = []
    d.pop("embedding", None)
    return d


def search_photos_by_vector(
    embedding: list[float],
    user_id: str,
    filters: Optional[dict] = None,
    limit: int = 20,
) -> list[dict]:
    """In-memory cosine similarity search with optional metadata filters."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM photos WHERE user_id = ? AND embedding IS NOT NULL",
            (user_id,),
        ).fetchall()

    scored = []
    for row in rows:
        d = dict(row)
        try:
            row_emb = json.loads(d["embedding"])
        except (json.JSONDecodeError, TypeError):
            continue

        if filters:
            # Filter: "me" / specific person_id must appear in photo's person_ids
            if filters.get("person_id"):
                pids_raw = d.get("person_ids", "[]")
                pids = json.loads(pids_raw) if isinstance(pids_raw, str) else pids_raw
                if filters["person_id"] not in pids:
                    continue

            # Filter: at least one object keyword must match a detected object label.
            # If a photo has no YOLO data yet (empty list), skip the filter and let
            # CLIP similarity handle ranking instead.
            if filters.get("objects"):
                obj_raw = d.get("detected_objects", "[]")
                objs = json.loads(obj_raw) if isinstance(obj_raw, str) else obj_raw
                obj_labels = {o.get("label", "").lower() for o in objs if isinstance(o, dict)}
                if obj_labels and not any(kw in obj_labels for kw in filters["objects"]):
                    continue

            # Filter: emotion
            if filters.get("emotion"):
                emotions_raw = d.get("emotions", "[]")
                emotions = json.loads(emotions_raw) if isinstance(emotions_raw, str) else emotions_raw
                dominant_emotions = [e.get("dominant", "") for e in emotions if isinstance(e, dict)]
                if filters["emotion"].lower() not in [e.lower() for e in dominant_emotions]:
                    continue

            if filters.get("exclude_low_value"):
                score = d.get("importance_score", 1.0) or 1.0
                if score < 0.4:
                    continue

        sim = _cosine_similarity(embedding, row_emb)
        d["similarity"] = sim
        scored.append(d)

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return [_row_to_dict(d) for d in scored[:limit]]


def get_pipeline_status(user_id: str) -> dict:
    with _get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM photos WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        processed = conn.execute(
            "SELECT COUNT(*) FROM photos WHERE user_id = ? AND detected_objects IS NOT NULL",
            (user_id,),
        ).fetchone()[0]
    return {"processed": processed, "total": total}


def get_all_photos_for_user(user_id: str) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM photos WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [_row_to_dict(dict(row)) for row in rows]


# ---------------------------------------------------------------------------
# People / face profiles
# ---------------------------------------------------------------------------


def get_or_create_person(
    user_id: str, embedding: list[float], threshold: float = 0.75
) -> str:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, embedding_centroid FROM people WHERE user_id = ? AND embedding_centroid IS NOT NULL",
            (user_id,),
        ).fetchall()

    best_id = None
    best_sim = 0.0
    for row in rows:
        try:
            centroid = json.loads(row["embedding_centroid"])
        except (json.JSONDecodeError, TypeError):
            continue
        sim = _cosine_similarity(embedding, centroid)
        if sim > best_sim:
            best_sim = sim
            best_id = str(row["id"])

    if best_sim >= threshold and best_id:
        with _get_conn() as conn:
            conn.execute(
                "UPDATE people SET photo_count = photo_count + 1 WHERE id = ?",
                (best_id,),
            )
        return best_id

    person_id = str(uuid.uuid4())
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO people (id, user_id, embedding_centroid, photo_count) VALUES (?, ?, ?, 1)",
            (person_id, user_id, json.dumps(embedding)),
        )
    return person_id


def name_person(person_id: str, name: str) -> None:
    with _get_conn() as conn:
        conn.execute("UPDATE people SET name = ? WHERE id = ?", (name, person_id))


def get_people(user_id: str) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, photo_count, cover_photo_url FROM people WHERE user_id = ? ORDER BY photo_count DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]
