"""
Pipeline orchestrator — runs all 5 steps for a single uploaded photo.
Called as a FastAPI BackgroundTask after upload.
"""

import asyncio
import json
from backend.db import update_photo_pipeline_result
from backend.models import PipelineResult
from pipeline.caption import get_caption_and_tags
from pipeline.yolo_objects import detect_objects
from pipeline.emotion import detect_emotions
from pipeline.faces import detect_and_cluster_faces
from pipeline.scoring import score_photo
from search.embed import embed_text


async def run_pipeline(photo_id: str, user_id: str, storage_url: str, image_bytes: bytes) -> None:
    try:
        # Steps 1, 2, 5 can run in parallel (don't depend on each other)
        caption_task = asyncio.create_task(get_caption_and_tags(image_bytes))
        objects_task = asyncio.create_task(detect_objects(image_bytes))

        caption_result, objects = await asyncio.gather(caption_task, objects_task)

        caption = caption_result.get("caption", "")
        tags = caption_result.get("tags", [])

        # Steps 3 and 4 use caption and image_bytes
        emotion_task = asyncio.create_task(detect_emotions(image_bytes, caption))
        faces_task = asyncio.create_task(detect_and_cluster_faces(image_bytes, user_id))

        # Scoring is sync — run in executor to not block event loop
        loop = asyncio.get_event_loop()
        scoring_task = loop.run_in_executor(None, score_photo, image_bytes)

        emotions, person_ids, (importance_score, flags) = await asyncio.gather(
            emotion_task, faces_task, scoring_task
        )

        # Embed caption for vector search
        embedding = await embed_text(f"{caption} {' '.join(tags)}")

        result = PipelineResult(
            photo_id=photo_id,
            caption=caption,
            tags=tags,
            detected_objects=objects,
            emotions=emotions,
            face_cluster_ids=person_ids,
            importance_score=importance_score,
            low_value_flags=flags,
        )

        update_photo_pipeline_result(photo_id, {
            "caption": result.caption,
            "tags": result.tags,
            "detected_objects": json.dumps([o.model_dump() for o in result.detected_objects]),
            "emotions": json.dumps([e.model_dump() for e in result.emotions]),
            "person_ids": [str(pid) for pid in result.face_cluster_ids],
            "importance_score": result.importance_score,
            "low_value_flags": result.low_value_flags,
            "embedding": embedding,
        })

    except Exception as exc:
        # Don't crash the server — log and move on
        print(f"[pipeline] ERROR for photo {photo_id}: {exc}")
