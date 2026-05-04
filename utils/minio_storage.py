from datetime import datetime, timedelta
from urllib.parse import urlparse

import base64
import io
import uuid
from django.conf import settings
from minio import Minio


class MinioStorage:
    def __init__(self, bucket_name=None):
        endpoint_url = getattr(settings, "AWS_S3_ENDPOINT_URL", "") or ""
        parsed = urlparse(endpoint_url)
        hostname = parsed.hostname or parsed.netloc.split(":")[0]
        port = parsed.port if parsed.port else 9000

        # Normalize common console/wrong local ports to the MinIO API port.
        if port in {9001, 9100, 9101}:
            port = 9000

        endpoint = f"{hostname}:{port}" if hostname else ""
        self.client = Minio(
            endpoint=endpoint,
            access_key=settings.AWS_ACCESS_KEY_ID,
            secret_key=settings.AWS_SECRET_ACCESS_KEY,
            secure=endpoint_url.startswith("https"),
        )
        self.bucket = bucket_name or settings.AWS_STORAGE_BUCKET_NAME
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    @staticmethod
    def _normalize_object_path(file_path):
        if not file_path:
            return ""
        return str(file_path).strip()

    def upload_base64_file(
            self,
            base64_str: str,
            folder: str = "uploads",
            file_name: str = "",
            old_file_path: str = ""
    ) -> str:
        """
        Uploads a base64-encoded file to MinIO and returns the file path.
        Deletes the old file if provided.
        Automatically detects content type and extension.
        """
        try:
            if ';base64,' not in base64_str:
                raise ValueError("Invalid base64 format. Missing ';base64,'")

            header, data = base64_str.split(';base64,')
            content_type = header.split(':')[1]  # e.g., "image/png"
            file_ext = content_type.split('/')[-1]

            file_data = base64.b64decode(data)

            # Generate a new unique file name if not provided
            file_name = f"{folder}/{file_name if file_name else uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file_ext}"

            # Delete an old file if provided
            old_object_path = self._normalize_object_path(old_file_path)
            if old_object_path:
                try:
                    self.client.remove_object(bucket_name=self.bucket, object_name=old_object_path)
                except Exception as delete_error:
                    # Log it if needed, but do not prevent upload
                    print(f"Warning: Could not delete old file: {delete_error}")

            # Upload the new file
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=file_name,
                data=io.BytesIO(file_data),
                length=len(file_data),
                content_type=content_type
            )

            return file_name  # only return the object path, not full URL

        except Exception as e:
            raise Exception(f"Failed to upload file to MinIO: {e}")

    def upload_file(
            self,
            file_obj,
            folder: str = "uploads",
            file_name: str = "",
            old_object_path: str = ""
    ) -> str:
        """Uploads a file-like object to MinIO and returns the object path."""
        try:
            if file_obj is None:
                raise ValueError("No file provided for upload")

            original_name = getattr(file_obj, "name", "") or file_name or uuid.uuid4().hex
            object_name = f"{folder}/{file_name or original_name}"
            content_type = getattr(file_obj, "content_type", None) or "application/octet-stream"

            old_object_path = self._normalize_object_path(old_object_path)
            if old_object_path:
                try:
                    self.client.remove_object(bucket_name=self.bucket, object_name=old_object_path)
                except Exception as delete_error:
                    print(f"Warning: Could not delete old file: {delete_error}")

            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
            file_bytes = file_obj.read()
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)

            self.client.put_object(
                bucket_name=self.bucket,
                object_name=object_name,
                data=io.BytesIO(file_bytes),
                length=len(file_bytes),
                content_type=content_type,
            )
            return object_name
        except Exception as e:
            raise Exception(f"Failed to upload file to MinIO: {e}")

    def get_presigned_url(self, object_path: str, expires_hours=1):
        """Return a presigned download URL for an object path."""
        object_path = self._normalize_object_path(object_path)
        if not object_path:
            return None
        return self.client.presigned_get_object(
            bucket_name=self.bucket,
            object_name=object_path,
            expires=timedelta(hours=expires_hours),
        )

    def get_object_bytes(self, object_path: str) -> bytes:
        """Fetch raw bytes for an object path."""
        object_path = self._normalize_object_path(object_path)
        if not object_path:
            return b""

        response = self.client.get_object(self.bucket, object_path)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def remove_file(self, file_path: str) -> None:
        """Removes a file from MinIO by object path. No-op if path is empty."""
        file_path = self._normalize_object_path(file_path)
        if not file_path:
            return
        try:
            self.client.remove_object(bucket_name=self.bucket, object_name=file_path)
        except Exception as e:
            print(f"Warning: Could not remove MinIO object {file_path}: {e}")
