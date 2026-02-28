"""
Step 4 — Face detection + embedding generation.
Uses MediaPipe for detection, OpenAI for embeddings.
"""

import io
import numpy as np
from PIL import Image
from openai import AsyncOpenAI
from backend.config import settings
from backend.db import get_or_create_person

client = AsyncOpenAI(api_key=settings.openai_api_key)


def _detect_faces_mediapipe(image_bytes: bytes) -> list[bytes]:
    """
    Returns a list of cropped face image bytes.
    Requires: pip install mediapipe
    """
    try:
        import mediapipe as mp
    except ImportError:
        return []

    mp_face = mp.solutions.face_detection

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_array = np.array(img)
    h, w = img_array.shape[:2]

    face_crops = []
    with mp_face.FaceDetection(model_selection=1, min_detection_confidence=0.5) as detector:
        results = detector.process(img_array)
        if not results.detections:
            return []

        for detection in results.detections:
            bb = detection.location_data.relative_bounding_box
            x1 = max(0, int(bb.xmin * w))
            y1 = max(0, int(bb.ymin * h))
            x2 = min(w, int((bb.xmin + bb.width) * w))
            y2 = min(h, int((bb.ymin + bb.height) * h))

            face_img = img.crop((x1, y1, x2, y2)).resize((224, 224))
            buf = io.BytesIO()
            face_img.save(buf, format="JPEG")
            face_crops.append(buf.getvalue())

    return face_crops


async def _embed_face(face_bytes: bytes) -> list[float]:
    """
    Generate a text embedding from a face description (vision → text → embed).
    In production, swap for a dedicated face embedding model.
    """
    import base64

    b64 = base64.b64encode(face_bytes).decode("utf-8")
    # Describe the face first
    desc_resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the face features in this image in 1-2 sentences for identification purposes."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ],
        max_tokens=100,
    )
    description = desc_resp.choices[0].message.content or ""

    # Embed the description
    embed_resp = await client.embeddings.create(
        model="text-embedding-3-small",
        input=description,
    )
    return embed_resp.data[0].embedding


async def detect_and_cluster_faces(
    image_bytes: bytes, user_id: str
) -> list[str]:
    """
    Detect faces, embed each, cluster into person profiles.
    Returns list of person_ids found in this image.
    """
    face_crops = _detect_faces_mediapipe(image_bytes)
    if not face_crops:
        return []

    person_ids = []
    for face_bytes in face_crops:
        embedding = await _embed_face(face_bytes)
        person_id = get_or_create_person(user_id, embedding)
        person_ids.append(person_id)

    return list(set(person_ids))
