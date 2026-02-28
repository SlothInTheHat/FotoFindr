import uuid
import boto3
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from botocore.exceptions import BotoCoreError

from backend.config import settings
from backend.db import insert_photo
from backend.models import UploadResponse
from pipeline.runner import run_pipeline

router = APIRouter()


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url,
        aws_access_key_id=settings.storage_access_key,
        aws_secret_access_key=settings.storage_secret_key,
        region_name=settings.storage_region,
    )


def _upload_to_storage(file_bytes: bytes, photo_id: str, content_type: str) -> str:
    key = f"photos/{photo_id}.jpg"
    try:
        _s3_client().put_object(
            Bucket=settings.storage_bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
            ACL="public-read",
        )
    except BotoCoreError as e:
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {e}")
    return f"{settings.storage_endpoint_url}/{settings.storage_bucket}/{key}"


@router.post("/", response_model=UploadResponse)
async def upload_photo(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Form(...),
):
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    file_bytes = await file.read()

    if len(file_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large.")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Only image files are accepted.")

    photo_id = str(uuid.uuid4())
    storage_url = _upload_to_storage(file_bytes, photo_id, file.content_type or "image/jpeg")

    insert_photo(photo_id, user_id, storage_url)

    # Kick off async AI pipeline
    background_tasks.add_task(run_pipeline, photo_id, user_id, storage_url, file_bytes)

    return UploadResponse(photo_id=photo_id, storage_url=storage_url)
