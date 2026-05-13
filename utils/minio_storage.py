from datetime import timedelta
import io
import mimetypes
import os

from django.conf import settings
from minio import Minio


def _normalize_key(object_path: str) -> str:
    """Strip leading slashes for MinIO object names."""
    if not object_path:
        return ""
    return object_path.lstrip("/")


class MinioStorage:
    """S3-compatible MinIO client used by Report Management (attachments)."""

    def __init__(self):
        endpoint_url = getattr(settings, "AWS_S3_ENDPOINT_URL", None) or ""
        endpoint = endpoint_url.replace("http://", "").replace("https://", "").rstrip("/")
        secure = endpoint_url.startswith("https")
        self.bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
        self._client = None
        if endpoint and getattr(settings, "AWS_ACCESS_KEY_ID", None) and getattr(
            settings, "AWS_SECRET_ACCESS_KEY", None
        ):
            self._client = Minio(
                endpoint=endpoint,
                access_key=settings.AWS_ACCESS_KEY_ID,
                secret_key=settings.AWS_SECRET_ACCESS_KEY,
                secure=secure,
            )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        if not self._client or not self.bucket:
            return
        try:
            if not self._client.bucket_exists(self.bucket):
                self._client.make_bucket(self.bucket)
        except Exception as e:
            print(f"Warning: Could not ensure bucket {self.bucket}: {e}")

    def upload_file(self, file, folder="", file_name=None, old_object_path=None):
        """
        Upload multipart file; return stored object path (with leading / for DB consistency).
        """
        if not self._client or not self.bucket:
            return None

        original_name = getattr(file, "name", "") or "file"
        content_type = (
            getattr(file, "content_type", None)
            or mimetypes.guess_type(original_name)[0]
            or "application/octet-stream"
        )
        ext = os.path.splitext(original_name)[1] or mimetypes.guess_extension(content_type) or ".bin"
        if file_name:
            stored_name = os.path.basename(str(file_name))
        else:
            base = os.path.splitext(original_name)[0]
            stored_name = f"{base}{ext}"
        key = f"{folder.strip('/')}/{stored_name}".lstrip("/")

        if old_object_path:
            try:
                self._client.remove_object(self.bucket, _normalize_key(old_object_path))
            except Exception as e:
                print(f"Warning: Could not remove old object {old_object_path}: {e}")

        body = file.file if hasattr(file, "file") else file
        if hasattr(body, "seek"):
            body.seek(0)
        raw = body.read() if hasattr(body, "read") else body
        stream = io.BytesIO(
            raw if isinstance(raw, (bytes, bytearray)) else bytes(raw)
        )
        length = stream.getbuffer().nbytes
        stream.seek(0)

        self._client.put_object(
            self.bucket,
            key,
            stream,
            length=length,
            content_type=content_type,
        )
        return f"/{key}"

    def get_presigned_url(self, object_path, expires_seconds=3600):
        if not self._client or not self.bucket:
            return None
        key = _normalize_key(object_path)
        if not key:
            return None
        try:
            return self._client.presigned_get_object(
                self.bucket,
                key,
                expires=timedelta(seconds=int(expires_seconds)),
            )
        except Exception as e:
            print(f"Warning: presigned_get_object failed: {e}")
            return None

    def get_object_bytes(self, object_path):
        if not self._client or not self.bucket:
            return None
        key = _normalize_key(object_path)
        if not key:
            return None
        try:
            response = self._client.get_object(self.bucket, key)
            return response.read()
        except Exception as e:
            print(f"Warning: get_object failed for {key}: {e}")
            return None
