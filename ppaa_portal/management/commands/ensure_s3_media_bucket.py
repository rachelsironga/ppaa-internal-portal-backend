"""
Create the MinIO / S3 media bucket if missing.

Portal uploads (PR flyers, documents, popup images, etc.) use ``default_storage``,
which is configured as S3-compatible storage pointing at MinIO.

Usage (Docker):
  docker compose exec backend python manage.py ensure_s3_media_bucket
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from ppaa_portal.services.minio.minio_client import client


class Command(BaseCommand):
    help = "Create AWS_STORAGE_BUCKET_NAME on MinIO/S3 if it does not exist."

    def handle(self, *args, **options):
        name = (getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or "").strip()
        if not name:
            self.stderr.write(self.style.ERROR("AWS_STORAGE_BUCKET_NAME is not set."))
            return
        if not getattr(settings, "AWS_S3_ENDPOINT_URL", None):
            self.stderr.write(self.style.ERROR("AWS_S3_ENDPOINT_URL is not set."))
            return

        if client.bucket_exists(name):
            self.stdout.write(self.style.NOTICE(f"Bucket {name!r} already exists."))
            return

        try:
            client.make_bucket(name)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Could not create bucket {name!r}: {e}"))
            raise
        self.stdout.write(self.style.SUCCESS(f"Created bucket {name!r}."))
