from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    photo_id: UUID
    storage_url: str
    message: str = "Photo received. Processing has started."


# ---------------------------------------------------------------------------
# Photo metadata (stored in DB, returned by search)
# ---------------------------------------------------------------------------

class EmotionScore(BaseModel):
    dominant: str
    scores: dict[str, float]  # e.g. {"happy": 0.87, "neutral": 0.10}


class DetectedObject(BaseModel):
    label: str
    confidence: float


class PhotoMetadata(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    storage_url: str
    caption: Optional[str] = None
    tags: list[str] = []
    detected_objects: list[DetectedObject] = []
    emotions: list[EmotionScore] = []
    person_ids: list[UUID] = []
    importance_score: Optional[float] = None
    low_value_flags: list[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# People / face profiles
# ---------------------------------------------------------------------------

class PersonProfile(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    name: Optional[str] = None  # null until user assigns a name
    photo_count: int = 0
    cover_photo_url: Optional[str] = None


class NamePersonRequest(BaseModel):
    name: str


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    user_id: UUID
    limit: int = 20


class SearchResult(BaseModel):
    photos: list[PhotoMetadata]
    narration: Optional[str] = None   # ElevenLabs audio URL
    narration_text: Optional[str] = None
    total: int


# ---------------------------------------------------------------------------
# Pipeline (internal — used between backend and pipeline workers)
# ---------------------------------------------------------------------------

class PipelineResult(BaseModel):
    photo_id: UUID
    caption: Optional[str] = None
    tags: list[str] = []
    detected_objects: list[DetectedObject] = []
    emotions: list[EmotionScore] = []
    face_cluster_ids: list[UUID] = []
    importance_score: float = 1.0
    low_value_flags: list[str] = []
