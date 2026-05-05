"""
Create configured MinIO / S3 buckets if missing.

Primary bucket comes from ``AWS_STORAGE_BUCKET_NAME``.
Optional extra buckets can be provided via:
  - ``SPM_BUCKET_NAME``
  - ``RMS_REPORTS_BUCKET``

Usage (Docker):
  docker compose exec backend python manage.py ensure_s3_media_bucket
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from ppaa_portal.services.minio.minio_client import client


class Command(BaseCommand):
    help = "Create configured MinIO/S3 buckets if they do not exist."

    def handle(self, *args, **options):
        names = []
        for key in ("AWS_STORAGE_BUCKET_NAME", "SPM_BUCKET_NAME", "RMS_REPORTS_BUCKET"):
            value = (getattr(settings, key, None) or "").strip()
            if value and value not in names:
                names.append(value)

        if not names:
            self.stderr.write(self.style.ERROR("AWS_STORAGE_BUCKET_NAME is not set."))
            return
        if not getattr(settings, "AWS_S3_ENDPOINT_URL", None):
            self.stderr.write(self.style.ERROR("AWS_S3_ENDPOINT_URL is not set."))
            return

        created = 0
        for name in names:
            if client.bucket_exists(name):
                self.stdout.write(self.style.NOTICE(f"Bucket {name!r} already exists."))
                continue
            try:
                client.make_bucket(name)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Could not create bucket {name!r}: {e}"))
                raise
            self.stdout.write(self.style.SUCCESS(f"Created bucket {name!r}."))
            created += 1

        if created == 0:
            self.stdout.write(self.style.NOTICE("No new buckets were created."))
