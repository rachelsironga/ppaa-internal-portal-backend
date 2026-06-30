"""Shared checks for MinIO media configuration (required for all portal file storage)."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

MINIO_ENV_VARS = (
    "AWS_S3_ENDPOINT_URL",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_STORAGE_BUCKET_NAME",
)


def minio_media_env_configured() -> bool:
    """True when env is complete for ``MinioStorage`` (native SDK → media bucket)."""
    for name in MINIO_ENV_VARS:
        if not (getattr(settings, name, None) or "").strip():
            return False
    return True


def missing_minio_env_vars() -> list[str]:
    return [name for name in MINIO_ENV_VARS if not (getattr(settings, name, None) or "").strip()]


def require_minio_media_configured() -> None:
    """Raise when MinIO is not configured — all uploads must use MinIO."""
    missing = missing_minio_env_vars()
    if missing:
        raise ImproperlyConfigured(
            "MinIO is required for file storage. Set in .env: "
            + ", ".join(missing)
            + ". AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY must match MINIO_ROOT_USER / "
            "MINIO_ROOT_PASSWORD in docker-compose.yml."
        )
