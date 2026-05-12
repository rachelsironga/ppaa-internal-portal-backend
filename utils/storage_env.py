"""Shared checks for MinIO / S3 media configuration (upload + read paths)."""

from django.conf import settings


def minio_media_env_configured() -> bool:
    """
    True when env is complete for ``MinioStorage`` (native SDK uploads to the media bucket).

    Public logo/image routes should read with the same client when this is true, because
    ``default_storage`` (boto3) can disagree with the MinIO SDK on some deployments.
    """
    if not (getattr(settings, "AWS_S3_ENDPOINT_URL", None) or "").strip():
        return False
    if not (getattr(settings, "AWS_ACCESS_KEY_ID", None) or "").strip():
        return False
    if not (getattr(settings, "AWS_SECRET_ACCESS_KEY", None) or "").strip():
        return False
    if not (getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or "").strip():
        return False
    return True
