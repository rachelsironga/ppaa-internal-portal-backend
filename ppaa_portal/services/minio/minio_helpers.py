from datetime import timedelta
import logging

from django.conf import settings
from ppaa_portal.services.minio.minio_client import client
from urllib3.exceptions import MaxRetryError

logger = logging.getLogger(__name__)

# Only log "MinIO unavailable" once per process to avoid console spam
_minio_unavailable_logged = False


def _log_minio_unavailable_once(message_or_exception):
    global _minio_unavailable_logged
    if not _minio_unavailable_logged:
        _minio_unavailable_logged = True
        logger.warning(
            "MinIO is not available (%s). File download URLs will be missing. "
            "Start MinIO (e.g. via Docker) or ignore this if not using file storage.",
            message_or_exception,
        )


def get_presigned_url(object_name: str, expires_hours=1) -> str | None:
    try:
        if not object_name:
            logger.warning("Empty object_name provided to get_presigned_url")
            return None

        url = client.presigned_get_object(
            bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
            object_name=object_name,
            expires=timedelta(hours=expires_hours),
        )
        return url
    except (ConnectionRefusedError, OSError) as e:
        _log_minio_unavailable_once(e)
        return None
    except MaxRetryError as e:
        _log_minio_unavailable_once("connection refused or max retries exceeded")
        return None
    except Exception:
        logger.exception("Failed to generate presigned URL for object '%s'", object_name)
        return None
