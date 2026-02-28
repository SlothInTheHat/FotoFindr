"""
Step 1 — Vision caption + tag extraction via Gemini.
If GEMINI_API_KEY is not set, returns empty caption/tags and skips the API call.
"""

import asyncio
import json
from backend.config import settings

PROMPT = """You are a photo analysis assistant.
Given an image, respond with a JSON object containing:
- "caption": a single descriptive sentence about the photo
- "tags": a list of 5-15 concise keyword tags (objects, people, places, activities, colors, mood)

Respond ONLY with valid JSON. No markdown, no explanation."""


def _make_client():
    if not settings.gemini_api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=settings.gemini_api_key)
    except ImportError:
        return None


_client = _make_client()


async def get_caption_and_tags(image_bytes: bytes) -> dict:
    if not _client:
        return {"caption": "", "tags": []}

    from google.genai import types
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

    response = await asyncio.to_thread(
        _client.models.generate_content,
        model="gemini-1.5-flash",
        contents=[PROMPT, image_part],
    )

    raw = response.text or "{}"
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"caption": raw, "tags": []}

    return {
        "caption": result.get("caption", ""),
        "tags": result.get("tags", []),
    }
