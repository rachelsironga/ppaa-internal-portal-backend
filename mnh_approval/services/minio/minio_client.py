from minio import Minio
from django.conf import settings

client = Minio(
    settings.AWS_S3_ENDPOINT_URL.replace("http://", "").replace("https://", ""),
    access_key=settings.AWS_ACCESS_KEY_ID,
    secret_key=settings.AWS_SECRET_ACCESS_KEY,
    secure=settings.AWS_S3_ENDPOINT_URL.startswith("https://"),
)
