"""
Local SQLite stand-in for snowflake_db — same function signatures, same column names.
Use this to verify pipeline logic without a live Snowflake connection.
Data is written to backend/snowflake_test.db.
"""

import json
import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent / "snowflake_test.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema() -> None:
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                ID            TEXT PRIMARY KEY,
                FILENAME      TEXT,
                CREATED_AT    TEXT DEFAULT (datetime('now')),
                METADATA      TEXT DEFAULT '{}',
                YOLO_DATA     TEXT DEFAULT '[]',
                DEEPFACE_DATA TEXT DEFAULT '[]'
            )
        """)
    print("[local_test_db] Schema ready.")


def insert_photo(photo_id: str, device_uri: str, user_id: str) -> None:
    try:
        metadata = json.dumps({"user_id": user_id})
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO photos (ID, FILENAME, METADATA, YOLO_DATA, DEEPFACE_DATA)
                VALUES (?, ?, ?, '[]', '[]')
                """,
                (photo_id, device_uri, metadata),
            )
        print(f"[local_test_db] insert_photo ok: {photo_id}")
    except Exception as e:
        print(f"[local_test_db] insert_photo failed: {e}")


def upsert_photo(photo_id: str, filename: str, result: dict) -> None:
    try:
        metadata = json.dumps({
            "user_id":          result.get("user_id", ""),
            "caption":          result.get("caption"),
            "tags":             result.get("tags", []),
            "importance_score": result.get("importance_score", 1.0),
            "low_value_flags":  result.get("low_value_flags", []),
            "person_ids":       result.get("person_ids", []),
        })
        yolo_raw     = result.get("detected_objects", "[]")
        deepface_raw = result.get("emotions", "[]")

        with _get_conn() as conn:
            cur = conn.execute(
                """
                UPDATE photos SET METADATA=?, YOLO_DATA=?, DEEPFACE_DATA=?
                WHERE ID=?
                """,
                (metadata, yolo_raw, deepface_raw, photo_id),
            )
            if cur.rowcount == 0:
                conn.execute(
                    """
                    INSERT INTO photos (ID, FILENAME, METADATA, YOLO_DATA, DEEPFACE_DATA)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (photo_id, filename, metadata, yolo_raw, deepface_raw),
                )
        print(f"[local_test_db] upsert_photo ok: {photo_id}")
    except Exception as e:
        print(f"[local_test_db] upsert_photo failed: {e}")


def update_photo_pipeline_result(photo_id: str, result: dict) -> None:
    upsert_photo(photo_id, f"/uploads/{photo_id}.jpg", result)


def clear_photos(user_id: str) -> None:
    """Delete all photos for a user."""
    try:
        with _get_conn() as conn:
            conn.execute(
                "DELETE FROM photos WHERE json_extract(METADATA, '$.user_id') = ?",
                (user_id,),
            )
        print(f"[local_test_db] clear_photos ok for user {user_id}")
    except Exception as e:
        print(f"[local_test_db] clear_photos failed: {e}")


def dump_all() -> list[dict]:
    """Return all rows as dicts — useful for quick inspection."""
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM photos").fetchall()
    return [dict(r) for r in rows]
