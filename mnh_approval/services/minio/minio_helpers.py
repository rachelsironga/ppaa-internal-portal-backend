from datetime import timedelta
from django.conf import settings
from mnh_approval.services.minio.minio_client import client


def get_presigned_url(object_name: str, expires_hours=1) -> str:
    try:
        print(f"Generating presigned URL for {object_name}")
        url = client.presigned_get_object(
            bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
            object_name=object_name,
            expires=timedelta(hours=expires_hours),
        )
        return url
    except Exception as e:
        print(f"Failed to generate presigned URL: {e}")
        return None
