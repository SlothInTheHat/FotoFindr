"""
Step 2 — Object detection.
Uses OpenAI Vision to extract structured object list.
YOLO can be swapped in for offline/faster inference.
"""

import base64
import json
from openai import AsyncOpenAI
from backend.config import settings
from backend.models import DetectedObject

client = AsyncOpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT = """You are an object detection assistant.
Given an image, return a JSON array of detected objects.
Each item should have:
- "label": the object name (lowercase)
- "confidence": your confidence score between 0.0 and 1.0

Include only significant objects (people, animals, vehicles, furniture, food, etc.).
Respond ONLY with a valid JSON array."""


async def detect_objects(image_bytes: bytes) -> list[DetectedObject]:
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

    raw = response.choices[0].message.content or "[]"
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []

    return [
        DetectedObject(label=item.get("label", ""), confidence=item.get("confidence", 0.0))
        for item in items
        if isinstance(item, dict)
    ]
