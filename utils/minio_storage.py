import base64
import binascii
import io
import mimetypes
import os
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse

from django.conf import settings
from minio import Minio


def _normalize_key(object_path: str) -> str:
    """Strip leading slashes for MinIO object names."""
    if not object_path:
        return ""
    return str(object_path).strip().lstrip("/")


class MinioStorage:
    """
    S3-compatible MinIO client for uploads, presigned URLs, and streaming reads.

    Internal portal, profile photos, RMS, and legacy views use ``upload_base64_file``;
    report attachments may use ``upload_file``. Optional ``bucket_name`` targets a
    non-default bucket (e.g. RMS reports).
    """

    def __init__(self, bucket_name=None):
        endpoint_url = (getattr(settings, "AWS_S3_ENDPOINT_URL", None) or "").strip()
        self.bucket = (bucket_name or getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or "").strip() or None
        self._client = None
        if not endpoint_url:
            return
        parsed = urlparse(endpoint_url)
        hostname = parsed.hostname or ""
        if not hostname and parsed.netloc:
            hostname = parsed.netloc.split(":")[0]
        port = parsed.port if parsed.port else 9000
        if port in {9001, 9100, 9101}:
            port = 9000
        endpoint = f"{hostname}:{port}" if hostname else ""
        secure = (parsed.scheme or "http").lower() == "https"
        access = (getattr(settings, "AWS_ACCESS_KEY_ID", None) or "").strip()
        secret = (getattr(settings, "AWS_SECRET_ACCESS_KEY", None) or "").strip()
        if endpoint and access and secret:
            self._client = Minio(
                endpoint=endpoint,
                access_key=access,
                secret_key=secret,
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

    def upload_base64_file(
        self,
        base64_str: str,
        folder: str = "uploads",
        file_name: str = "",
        old_file_path: str = "",
    ) -> str:
        """
        Decode a ``data:*;base64,...`` URL, upload to MinIO, return object key (no leading slash).
        """
        if not self._client or not self.bucket:
            raise Exception(
                "MinIO is not configured (set AWS_S3_ENDPOINT_URL, AWS_ACCESS_KEY_ID, "
                "AWS_SECRET_ACCESS_KEY, and AWS_STORAGE_BUCKET_NAME or pass bucket_name)."
            )
        if not base64_str or ";base64," not in base64_str:
            raise ValueError("Invalid base64 format. Missing ';base64,'")

        header, data = base64_str.split(";base64,", 1)
        if not header.startswith("data:"):
            raise ValueError("Invalid data URL")

        mime_part = header[5:].split(";")[0].strip().lower()
        if "/" not in mime_part:
            raise ValueError("Invalid data URL: could not parse MIME type")
        content_type = mime_part
        subtype = mime_part.split("/", 1)[1]
        if subtype == "svg+xml":
            file_ext = "svg"
        else:
            file_ext = subtype.split("+", 1)[0].strip()
            if file_ext in ("jpg", "pjpeg"):
                file_ext = "jpeg"

        try:
            file_data = base64.b64decode(data, validate=True)
        except (ValueError, binascii.Error) as e:
            raise ValueError("Invalid file encoding") from e

        folder_clean = folder.strip("/")
        bare = (file_name or "").strip() or uuid.uuid4().hex
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        stored_name = f"{folder_clean}/{bare}_{ts}.{file_ext}"

        old = _normalize_key(old_file_path or "")
        if old:
            try:
                self._client.remove_object(self.bucket, old)
            except Exception as e:
                print(f"Warning: Could not delete old file: {e}")

        stream = io.BytesIO(file_data)
        self._client.put_object(
            self.bucket,
            stored_name,
            stream,
            length=len(file_data),
            content_type=content_type,
        )
        return stored_name

    def remove_file(self, file_path: str) -> None:
        """Remove an object by key; no-op if misconfigured or path empty."""
        if not self._client or not self.bucket:
            return
        key = _normalize_key(file_path or "")
        if not key:
            return
        try:
            self._client.remove_object(self.bucket, key)
        except Exception as e:
            print(f"Warning: Could not remove MinIO object {key}: {e}")

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
        stream = io.BytesIO(raw if isinstance(raw, (bytes, bytearray)) else bytes(raw))
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
            return b""
        key = _normalize_key(object_path)
        if not key:
            return b""
        response = None
        try:
            response = self._client.get_object(self.bucket, key)
            return response.read()
        except Exception as e:
            print(f"Warning: get_object failed for {key}: {e}")
            return b""
        finally:
            if response is not None:
                try:
                    response.close()
                    response.release_conn()
                except Exception:
                    pass
