"""Portal file storage — all reads, writes, and deletes go through MinIO."""

import base64
import binascii
import io
import posixpath
import uuid
from pathlib import Path

from utils.minio_storage import MinioStorage
from utils.storage_env import minio_media_env_configured, require_minio_media_configured


def get_minio_storage() -> MinioStorage:
    require_minio_media_configured()
    return MinioStorage()


def store_uploaded_data_url(
    data_url: str,
    preferred_name: str,
    *,
    storage_subdir: str = "documents",
    max_bytes: int | None = None,
    old_file_path: str | None = None,
) -> tuple[str, str]:
    """Decode a data URL and persist bytes in MinIO. Returns (object_key, display_name)."""
    if not data_url or ";base64," not in data_url:
        return "", ""

    _, b64 = data_url.split(";base64,", 1)
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Invalid file encoding") from None

    limit = 20 * 1024 * 1024 if max_bytes is None else max_bytes
    if len(raw) > limit:
        raise ValueError(f"File too large (max {limit // (1024 * 1024)}MB)")

    display_name = (preferred_name or "document").strip() or "document"

    minio = get_minio_storage()
    old = (old_file_path or "").strip()
    try:
        stored = minio.upload_base64_file(
            data_url,
            folder=f"internal_portal/{storage_subdir}",
            file_name=uuid.uuid4().hex,
            old_file_path=old,
        )
        if not stored:
            raise ValueError("Storage returned no object key after upload")
        probe = minio.get_object_bytes(stored)
        if not probe:
            raise ValueError(
                "Upload failed verification (empty object in MinIO). "
                "Check AWS_STORAGE_BUCKET_NAME, AWS_S3_ENDPOINT_URL, and credentials."
            )
        return stored, display_name
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(str(e)) from e


def read_storage_bytes(storage_key: str) -> bytes | None:
    """Return file bytes from MinIO, or None when the object is missing."""
    key = (storage_key or "").strip()
    if not key or not minio_media_env_configured():
        return None
    try:
        raw = get_minio_storage().get_object_bytes(key)
        return raw or None
    except Exception:
        return None


def open_storage_stream(storage_key: str):
    """Readable binary stream for a MinIO object key, or None."""
    raw = read_storage_bytes(storage_key)
    if raw:
        return io.BytesIO(raw)
    return None


def delete_storage_key(storage_key: str) -> None:
    """Remove an object from MinIO (no-op when key is empty)."""
    key = (storage_key or "").strip()
    if not key or not minio_media_env_configured():
        return
    try:
        get_minio_storage().remove_file(key)
    except Exception:
        pass


def storage_display_name(storage_key: str, original_filename: str, fallback_basename: str) -> str:
    return (
        (original_filename or "").strip()
        or posixpath.basename((storage_key or "").strip())
        or fallback_basename
    )
