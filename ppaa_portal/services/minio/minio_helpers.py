from datetime import timedelta
from typing import Optional

import logging
from django.conf import settings
from django.core.files.storage import default_storage
from urllib3.exceptions import MaxRetryError

from ppaa_portal.services.minio.minio_client import client

logger = logging.getLogger(__name__)

# Profile / signature images are cached in Redux; presign must outlive typical sessions.
DEFAULT_PRESIGN_HOURS = 1
PROFILE_MEDIA_PRESIGN_HOURS = getattr(
    settings, "PROFILE_MEDIA_PRESIGN_HOURS", 24 * 7
)


def _s3_wire_key(stored_name: str) -> str:
    """
    Object key as stored on S3/MinIO. django-storages returns a logical name from
    ``save()`` but uploads with ``location`` + ``clean_name``; presign must match.
    """
    from storages.utils import clean_name

    name = str(stored_name).lstrip("/")
    normalize = getattr(default_storage, "_normalize_name", None)
    if callable(normalize):
        return normalize(clean_name(name))
    return clean_name(name)


def get_presigned_url(object_name: str, expires_hours=None) -> Optional[str]:
    if not object_name or not str(object_name).strip():
        return None
    hours = (
        expires_hours
        if expires_hours is not None
        else DEFAULT_PRESIGN_HOURS
    )
    expires_in = max(int(hours * 3600), 1)
    wire_key = _s3_wire_key(object_name)

    # Prefer boto3: same client/signing as ``default_storage`` uploads (django-storages).
    try:
        conn = getattr(default_storage, "connection", None)
        bucket = getattr(default_storage, "bucket_name", None) or settings.AWS_STORAGE_BUCKET_NAME
        if conn is not None and bucket:
            return conn.meta.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": wire_key},
                ExpiresIn=expires_in,
            )
    except Exception:
        pass

    try:
        return client.presigned_get_object(
            bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
            object_name=wire_key,
            expires=timedelta(seconds=expires_in),
        )
    except (ConnectionRefusedError, OSError, MaxRetryError) as e:
        logger.warning("MinIO presign failed: %s", e)
        return None
