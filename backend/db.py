"""
Database helpers.

Metadata  → Snowflake (or Postgres as fallback)
Vectors   → pgvector (Postgres extension)
"""

import uuid
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from backend.config import settings


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_pg_conn():
    return psycopg2.connect(settings.postgres_dsn, cursor_factory=RealDictCursor)


# ---------------------------------------------------------------------------
# Schema bootstrap (run once on startup)
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS photos (
    id              UUID PRIMARY KEY,
    user_id         UUID NOT NULL,
    storage_url     TEXT NOT NULL,
    caption         TEXT,
    tags            TEXT[],
    detected_objects JSONB DEFAULT '[]',
    emotions        JSONB DEFAULT '[]',
    person_ids      UUID[] DEFAULT '{}',
    importance_score FLOAT DEFAULT 1.0,
    low_value_flags TEXT[] DEFAULT '{}',
    embedding       vector(1536),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS people (
    id                  UUID PRIMARY KEY,
    user_id             UUID NOT NULL,
    name                TEXT,
    embedding_centroid  vector(1536),
    photo_count         INT DEFAULT 0,
    cover_photo_url     TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS face_embeddings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id    UUID REFERENCES photos(id) ON DELETE CASCADE,
    person_id   UUID REFERENCES people(id),
    embedding   vector(1536) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS photos_embedding_idx
    ON photos USING ivfflat (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS face_embedding_idx
    ON face_embeddings USING ivfflat (embedding vector_cosine_ops);
"""


def init_db():
    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------

def insert_photo(photo_id: str, user_id: str, storage_url: str) -> None:
    sql = """
        INSERT INTO photos (id, user_id, storage_url)
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """
    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (photo_id, user_id, storage_url))
        conn.commit()


def update_photo_pipeline_result(photo_id: str, result: dict) -> None:
    sql = """
        UPDATE photos SET
            caption          = %(caption)s,
            tags             = %(tags)s,
            detected_objects = %(detected_objects)s::jsonb,
            emotions         = %(emotions)s::jsonb,
            person_ids       = %(person_ids)s,
            importance_score = %(importance_score)s,
            low_value_flags  = %(low_value_flags)s,
            embedding        = %(embedding)s
        WHERE id = %(photo_id)s
    """
    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {**result, "photo_id": photo_id})
        conn.commit()


def search_photos_by_vector(
    embedding: list[float],
    user_id: str,
    filters: Optional[dict] = None,
    limit: int = 20,
) -> list[dict]:
    """Cosine similarity search with optional metadata filters."""
    where_clauses = ["user_id = %(user_id)s"]
    params: dict = {"user_id": user_id, "embedding": embedding, "limit": limit}

    if filters:
        if filters.get("person_name"):
            where_clauses.append(
                "EXISTS (SELECT 1 FROM people p WHERE p.id = ANY(photos.person_ids) AND p.name ILIKE %(person_name)s)"
            )
            params["person_name"] = f"%{filters['person_name']}%"
        if filters.get("emotion"):
            where_clauses.append("emotions @> %(emotion_filter)s::jsonb")
            params["emotion_filter"] = f'[{{"dominant": "{filters["emotion"]}"}}]'
        if filters.get("exclude_low_value"):
            where_clauses.append("importance_score >= 0.4")

    where = " AND ".join(where_clauses)
    sql = f"""
        SELECT *, 1 - (embedding <=> %(embedding)s::vector) AS similarity
        FROM photos
        WHERE {where}
        ORDER BY similarity DESC
        LIMIT %(limit)s
    """
    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


# ---------------------------------------------------------------------------
# People / face profiles
# ---------------------------------------------------------------------------

def get_or_create_person(user_id: str, embedding: list[float], threshold: float = 0.75) -> str:
    """
    Find the closest existing person cluster for this face embedding.
    If similarity is above threshold, return that person's ID.
    Otherwise create a new anonymous person profile.
    """
    sql = """
        SELECT id, 1 - (embedding_centroid <=> %(embedding)s::vector) AS similarity
        FROM people
        WHERE user_id = %(user_id)s AND embedding_centroid IS NOT NULL
        ORDER BY similarity DESC
        LIMIT 1
    """
    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"embedding": embedding, "user_id": user_id})
            row = cur.fetchone()

        if row and row["similarity"] >= threshold:
            person_id = str(row["id"])
            # Update centroid (running average approximation)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE people SET photo_count = photo_count + 1 WHERE id = %s",
                    (person_id,),
                )
            conn.commit()
            return person_id

        # Create new anonymous person
        person_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO people (id, user_id, embedding_centroid, photo_count)
                VALUES (%s, %s, %s, 1)
                """,
                (person_id, user_id, embedding),
            )
        conn.commit()
        return person_id


def name_person(person_id: str, name: str) -> None:
    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE people SET name = %s WHERE id = %s", (name, person_id))
        conn.commit()


def get_people(user_id: str) -> list[dict]:
    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, photo_count, cover_photo_url FROM people WHERE user_id = %s ORDER BY photo_count DESC",
                (user_id,),
            )
            return cur.fetchall()
