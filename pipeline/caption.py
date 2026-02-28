"""
Step 1 — Vision caption + tag extraction.
Uses OpenAI Vision API (or Gemini as fallback).
"""

import base64
import json
from openai import AsyncOpenAI
from backend.config import settings

client = AsyncOpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT = """You are a photo analysis assistant.
Given an image, respond with a JSON object containing:
- "caption": a single descriptive sentence about the photo
- "tags": a list of 5-15 concise keyword tags (objects, people, places, activities, colors, mood)

Respond ONLY with valid JSON. No markdown, no explanation."""


async def get_caption_and_tags(image_bytes: bytes) -> dict:
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    }
                ],
            },
        ],
        max_tokens=300,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"caption": raw, "tags": []}

    return {
        "caption": result.get("caption", ""),
        "tags": result.get("tags", []),
    }
