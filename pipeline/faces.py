"""
Step 4 — Face detection + embedding generation.

MediaPipe detects face bounding boxes; CLIP embeds the face crop.
Using CLIP (not a dedicated face model) is good enough for demo clustering
and requires no extra API key.
"""

import asyncio
import io

import numpy as np
from PIL import Image

from backend.db import get_or_create_person
from pipeline.clip_embed import embed_image


def _detect_faces_mediapipe(image_bytes: bytes) -> list[bytes]:
    try:
        import mediapipe as mp
    except ImportError:
        return []

    mp_face = mp.solutions.face_detection
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_array = np.array(img)
    h, w = img_array.shape[:2]

    face_crops: list[bytes] = []
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


async def detect_and_cluster_faces(image_bytes: bytes, user_id: str) -> list[str]:
    face_crops = _detect_faces_mediapipe(image_bytes)
    if not face_crops:
        return []

    person_ids: list[str] = []
    for face_bytes in face_crops:
        embedding = await asyncio.to_thread(embed_image, face_bytes)
        person_id = get_or_create_person(user_id, embedding)
        person_ids.append(person_id)

    return list(set(person_ids))
