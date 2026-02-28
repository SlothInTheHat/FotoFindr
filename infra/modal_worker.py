"""
Optional Modal worker for offloading image processing jobs.
Enables parallel processing and faster batch uploads.

Usage:
  modal deploy infra/modal_worker.py
  modal run infra/modal_worker.py::process_photo --photo_id=... --storage_url=...

Requires: pip install modal
"""

import modal

app = modal.App("fotofindr-pipeline")

image = (
    modal.Image.debian_slim()
    .pip_install(
        "openai",
        "Pillow",
        "numpy",
        "opencv-python-headless",
        "mediapipe",
        "httpx",
        "boto3",
        "psycopg2-binary",
        "pgvector",
        "python-dotenv",
        "scipy",
        "ultralytics"
    )
    .run_commands('python -c "from ultralytics import YOLO; YOLO(\'yolov8n.pt\')"')
)


@app.function(image=image, secrets=[modal.Secret.from_name("fotofindr-secrets")])
async def process_photo(photo_id: str, user_id: str, storage_url: str) -> dict:
    """
    Download the photo from storage, run the full pipeline, write results to DB.
    Called by the FastAPI backend instead of BackgroundTasks when Modal is enabled.
    """
    import httpx
    from backend.db import update_photo_status
    from pipeline.runner import run_pipeline

    try:
        update_photo_status(photo_id, "processing")

    async with httpx.AsyncClient() as client:
        resp = await client.get(storage_url)
        resp.raise_for_status()
        image_bytes = resp.content

        await run_pipeline(
            photo_id,
            user_id,
            storage_url,
            image_bytes,
            suppress_exceptions=False,
        )
        update_photo_status(photo_id, "completed", error_message=None)
        return {"photo_id": photo_id, "status": "completed"}
    except Exception as exc:
        update_photo_status(photo_id, "failed", error_message=str(exc))
        raise


@app.local_entrypoint()
def main(photo_id: str, storage_url: str, user_id: str = "demo-user"):
    result = process_photo.remote(photo_id, user_id, storage_url)
    print(result)
