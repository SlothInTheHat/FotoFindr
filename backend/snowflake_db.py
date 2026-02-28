"""
Snowflake helpers — writes to the existing FOTOFINDR.PUBLIC.PHOTOS table.

Table schema (already created in Snowflake):
  ID           VARCHAR   — UUID
  FILENAME     VARCHAR   — original device URI (ph://, content://, etc.)
  CREATED_AT   TIMESTAMP — auto-set on insert
  METADATA     VARIANT   — caption, tags, embedding, importance_score, user_id, …
  YOLO_DATA    VARIANT   — YOLO detected objects list
  DEEPFACE_DATA VARIANT  — emotion / face data list

All functions are synchronous (snowflake-connector-python is sync).
Call them via BackgroundTasks or asyncio.to_thread to avoid blocking.
"""

import json

import snowflake.connector

from backend.config import settings


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


def _get_conn() -> snowflake.connector.SnowflakeConnection:
    account = settings.snowflake_account.replace("/", "-")
    return snowflake.connector.connect(
        account=account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        database=settings.snowflake_database,
        schema=settings.snowflake_schema,
        warehouse=settings.snowflake_warehouse,
    )


def init_schema() -> None:
    """Verify Snowflake connectivity on startup. Table already exists."""
    try:
        with _get_conn() as conn:
            conn.cursor().execute("SELECT CURRENT_TIMESTAMP()")
        print("[snowflake] Connected.")
    except Exception as e:
        print(f"[snowflake] Connection check failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------


def insert_photo(photo_id: str, device_uri: str, user_id: str) -> None:
    """
    Insert a new row with the device URI as FILENAME.
    METADATA gets user_id so we can filter later.
    YOLO_DATA and DEEPFACE_DATA are filled in by update_photo_pipeline_result.
    """
    try:
        metadata = json.dumps({"user_id": user_id})
        with _get_conn() as conn:
            conn.cursor().execute(
                """
                INSERT INTO photos (ID, FILENAME, CREATED_AT, METADATA, YOLO_DATA, DEEPFACE_DATA)
                SELECT %s, %s, CURRENT_TIMESTAMP(), PARSE_JSON(%s), PARSE_JSON('[]'), PARSE_JSON('[]')
                """,
                (photo_id, device_uri, metadata),
            )
        print(f"[snowflake] insert_photo ok: {photo_id}")
    except Exception as e:
        print(f"[snowflake] insert_photo failed: {e}")


def upsert_photo(photo_id: str, filename: str, result: dict) -> None:
    """
    UPDATE the row if it exists, INSERT if it doesn't.
    Carries all metadata (user_id, caption, tags, …) plus YOLO and DeepFace data.
    """
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
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE photos SET
                    METADATA      = PARSE_JSON(%s),
                    YOLO_DATA     = PARSE_JSON(%s),
                    DEEPFACE_DATA = PARSE_JSON(%s)
                WHERE ID = %s
                """,
                (metadata, yolo_raw, deepface_raw, photo_id),
            )
            if cur.rowcount == 0:
                # Row didn't exist yet — insert it
                cur.execute(
                    """
                    INSERT INTO photos (ID, FILENAME, CREATED_AT, METADATA, YOLO_DATA, DEEPFACE_DATA)
                    SELECT %s, %s, CURRENT_TIMESTAMP(), PARSE_JSON(%s), PARSE_JSON(%s), PARSE_JSON(%s)
                    """,
                    (photo_id, filename, metadata, yolo_raw, deepface_raw),
                )
        print(f"[snowflake] upsert_photo ok: {photo_id}")
    except Exception as e:
        print(f"[snowflake] upsert_photo failed: {e}")


def update_photo_pipeline_result(photo_id: str, result: dict) -> None:
    """
    After AI pipeline finishes, push:
      METADATA    ← caption, tags, embedding, importance_score, user_id, low_value_flags
      YOLO_DATA   ← detected objects from YOLO
      DEEPFACE_DATA ← emotion / face data
    """
    try:
        # Build METADATA: everything except YOLO and emotion data
        metadata = {
            "user_id":          result.get("user_id", ""),
            "caption":          result.get("caption"),
            "tags":             result.get("tags", []),
            "importance_score": result.get("importance_score", 1.0),
            "low_value_flags":  result.get("low_value_flags", []),
            "person_ids":       result.get("person_ids", []),
            "embedding":        result.get("embedding"),
        }

        # detected_objects is already a JSON string from runner.py
        yolo_raw = result.get("detected_objects", "[]")

        # emotions is already a JSON string from runner.py
        deepface_raw = result.get("emotions", "[]")

        with _get_conn() as conn:
            conn.cursor().execute(
                """
                UPDATE photos SET
                    METADATA      = PARSE_JSON(%s),
                    YOLO_DATA     = PARSE_JSON(%s),
                    DEEPFACE_DATA = PARSE_JSON(%s)
                WHERE ID = %s
                """,
                (json.dumps(metadata), yolo_raw, deepface_raw, photo_id),
            )
    except Exception as e:
        print(f"[snowflake] update_photo failed (non-fatal): {e}")
