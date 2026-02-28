import uuid
from pathlib import Path
from uuid import UUID

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from config import settings
from db import get_photo_status, insert_photo, update_photo_status
from models import PhotoStatusResponse, UploadResponse

router = APIRouter()


def _http_error(status_code: int, error_code: str, message: str) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={"error_code": error_code, "message": message},
    )


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
        _http_error(
            status_code=500,
            error_code="STORAGE_CONFIG_MISSING",
            message=f"Missing storage settings: {', '.join(missing)}",
        )

    try:
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
    except (BotoCoreError, ClientError) as exc:
        _http_error(
            status_code=502,
            error_code="STORAGE_UPLOAD_FAILED",
            message=f"Failed to upload image to object storage: {exc}",
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
        _http_error(
            status_code=413,
            error_code="FILE_TOO_LARGE",
            message=f"File exceeds {settings.max_upload_size_mb}MB limit.",
        )
    if not file.content_type or not file.content_type.startswith("image/"):
        _http_error(
            status_code=415,
            error_code="UNSUPPORTED_MEDIA_TYPE",
            message="Only image files are accepted.",
        )

    photo_id = str(uuid.uuid4())
    ext = Path(file.filename or "photo.jpg").suffix or ".jpg"
    storage_key = _build_storage_key(photo_id, ext)
    storage_url = _save_file(file_bytes, storage_key, file.content_type)

    try:
        insert_photo(photo_id, user_id, storage_url, status="uploaded")
    except Exception as exc:
        _http_error(
            status_code=500,
            error_code="PHOTO_INSERT_FAILED",
            message=f"Failed to create photo record: {exc}",
        )

    try:
        from infra.modal_worker import process_photo
    except Exception as exc:
        update_photo_status(photo_id, "failed", error_message=f"modal_import_failed: {exc}")
        _http_error(
            status_code=503,
            error_code="MODAL_NOT_AVAILABLE",
            message=f"Modal worker is not available: {exc}",
        )

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
        _http_error(
            status_code=502,
            error_code="MODAL_QUEUE_FAILED",
            message=f"Failed to queue Modal processing job: {exc}",
        )

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
        _http_error(
            status_code=404,
            error_code="PHOTO_NOT_FOUND",
            message="Photo not found.",
        )

    return PhotoStatusResponse(
        photo_id=row["id"],
        user_id=row["user_id"],
        status=row["status"],
        modal_call_id=row.get("modal_call_id"),
        error_message=row.get("error_message"),
        status_updated_at=row.get("status_updated_at"),
    )
