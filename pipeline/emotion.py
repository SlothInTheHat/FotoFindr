"""
Step 3 — Emotion detection via Presage API.
Falls back to a caption-based heuristic if Presage is unavailable.
"""

import httpx
import base64
from backend.config import settings
from backend.models import EmotionScore

EMOTION_KEYWORDS = {
    "happy": ["smiling", "laughing", "happy", "joy", "grinning", "cheerful"],
    "sad": ["sad", "crying", "tears", "upset", "unhappy", "somber"],
    "angry": ["angry", "furious", "mad", "frustrated", "rage"],
    "surprised": ["surprised", "shocked", "amazed", "astonished"],
    "neutral": ["neutral", "calm", "expressionless", "serious"],
}


async def detect_emotions(image_bytes: bytes, caption: str = "") -> list[EmotionScore]:
    if settings.presage_api_key:
        return await _presage_detect(image_bytes)
    return _caption_heuristic(caption)


async def _presage_detect(image_bytes: bytes) -> list[EmotionScore]:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            settings.presage_api_url,
            headers={"Authorization": f"Bearer {settings.presage_api_key}"},
            json={"image": b64},
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for face in data.get("faces", []):
        emotions = face.get("emotions", {})
        if not emotions:
            continue
        dominant = max(emotions, key=emotions.get)
        results.append(EmotionScore(dominant=dominant, scores=emotions))
    return results


def _caption_heuristic(caption: str) -> list[EmotionScore]:
    caption_lower = caption.lower()
    for emotion, keywords in EMOTION_KEYWORDS.items():
        if any(kw in caption_lower for kw in keywords):
            return [EmotionScore(dominant=emotion, scores={emotion: 0.75, "neutral": 0.25})]
    return []
