import uuid
from pathlib import Path
from uuid import UUID

import boto3
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from config import settings
from db import (
    get_photo_status,
    init_db,
    insert_photo,
    update_photo_status,
)
from infra.modal_worker import process_photo
from models import PhotoStatusResponse, UploadResponse

router = APIRouter()

# Ensure new columns exist even on pre-existing SQLite files.
init_db()


def _build_storage_key(photo_id: str, extension: str) -> str:
    normalized_ext = extension.lower() or ".jpg"
    if not normalized_ext.startswith("."):
        normalized_ext = f".{normalized_ext}"
    prefix = settings.storage_prefix.strip("/")
    if prefix:
        return f"{prefix}/{photo_id}{normalized_ext}"
    return f"{photo_id}{normalized_ext}"


def _save_locally(file_bytes: bytes, storage_key: str) -> str:
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(exist_ok=True)
    file_name = Path(storage_key).name
    path = upload_dir / file_name
    path.write_bytes(file_bytes)
    return f"/uploads/{file_name}"


def _save_to_object_storage(file_bytes: bytes, storage_key: str, content_type: str) -> str:
    required = {
        "storage_bucket": settings.storage_bucket,
        "storage_endpoint_url": settings.storage_endpoint_url,
        "storage_access_key": settings.storage_access_key,
        "storage_secret_key": settings.storage_secret_key,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Storage backend is s3, missing settings: {', '.join(missing)}",
        )

    client = boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url,
        aws_access_key_id=settings.storage_access_key,
        aws_secret_access_key=settings.storage_secret_key,
        region_name=settings.storage_region,
    )
    client.put_object(
        Bucket=settings.storage_bucket,
        Key=storage_key,
        Body=file_bytes,
        ContentType=content_type,
    )

    if settings.storage_public_base_url:
        base = settings.storage_public_base_url.rstrip("/")
        return f"{base}/{storage_key}"

    endpoint = settings.storage_endpoint_url.rstrip("/")
    return f"{endpoint}/{settings.storage_bucket}/{storage_key}"


def _save_file(file_bytes: bytes, storage_key: str, content_type: str) -> str:
    if settings.storage_backend.lower() == "s3":
        return _save_to_object_storage(file_bytes, storage_key, content_type)
    return _save_locally(file_bytes, storage_key)


@router.post("/", response_model=UploadResponse)
async def upload_photo(
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
    ext = Path(file.filename or "photo.jpg").suffix or ".jpg"
    storage_key = _build_storage_key(photo_id, ext)
    storage_url = _save_file(file_bytes, storage_key, file.content_type)

    insert_photo(photo_id, user_id, storage_url, status="uploaded")

    try:
        call = process_photo.spawn(photo_id, user_id, storage_url)
        modal_call_id = getattr(call, "object_id", None)
        update_photo_status(
            photo_id,
            "processing",
            modal_call_id=modal_call_id,
            error_message=None,
        )
    except Exception as exc:
        update_photo_status(photo_id, "failed", error_message=f"modal_spawn_failed: {exc}")
        raise HTTPException(status_code=502, detail="Failed to queue Modal processing job.") from exc

    return UploadResponse(
        photo_id=photo_id,
        storage_url=storage_url,
        status="processing",
        modal_call_id=modal_call_id,
    )


@router.get("/{photo_id}/status", response_model=PhotoStatusResponse)
def photo_status(photo_id: UUID):
    row = get_photo_status(str(photo_id))
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found.")

    return PhotoStatusResponse(
        photo_id=row["id"],
        user_id=row["user_id"],
        status=row["status"],
        modal_call_id=row.get("modal_call_id"),
        error_message=row.get("error_message"),
        status_updated_at=row.get("status_updated_at"),
    )
