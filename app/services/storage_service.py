"""
Storage Service — swappable backend (local disk or S3/Cloudflare R2).
Set STORAGE_BACKEND=local | s3 in .env.
"""

import os
import uuid
import logging
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)


def save_image(image_bytes: bytes, user_id: str, content_type: str = "image/jpeg") -> str:
    """
    Persist an image and return its storage key.
    The key is stored on the GlucoseReading row so it can be retrieved later.
    """
    ext = _ext_from_content_type(content_type)
    key = f"scans/{user_id}/{uuid.uuid4()}{ext}"

    if settings.STORAGE_BACKEND == "s3":
        return _save_s3(image_bytes, key, content_type)
    return _save_local(image_bytes, key)


def get_image_url(key: str, expires_in: int = 3600) -> str:
    """Return a URL/path that can be used to retrieve the image."""
    if settings.STORAGE_BACKEND == "s3":
        return _presigned_url(key, expires_in)
    return f"/static/{key}"


def delete_image(key: str) -> None:
    if settings.STORAGE_BACKEND == "s3":
        _delete_s3(key)
    else:
        _delete_local(key)


# ── Local ─────────────────────────────────────────────────────────────────────

def _save_local(image_bytes: bytes, key: str) -> str:
    dest = Path(settings.LOCAL_UPLOAD_DIR) / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(image_bytes)
    logger.debug("Saved image locally: %s", dest)
    return key


def _delete_local(key: str) -> None:
    path = Path(settings.LOCAL_UPLOAD_DIR) / key
    if path.exists():
        path.unlink()


# ── S3 / Cloudflare R2 ────────────────────────────────────────────────────────

def _get_s3_client():
    import boto3
    kwargs = dict(
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    if settings.R2_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.R2_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


def _save_s3(image_bytes: bytes, key: str, content_type: str) -> str:
    client = _get_s3_client()
    client.put_object(
        Bucket=settings.AWS_S3_BUCKET,
        Key=key,
        Body=image_bytes,
        ContentType=content_type,
    )
    logger.debug("Saved image to S3: %s", key)
    return key


def _presigned_url(key: str, expires_in: int) -> str:
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.AWS_S3_BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )


def _delete_s3(key: str) -> None:
    client = _get_s3_client()
    client.delete_object(Bucket=settings.AWS_S3_BUCKET, Key=key)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ext_from_content_type(ct: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png":  ".png",
        "image/webp": ".webp",
    }.get(ct, ".jpg")
