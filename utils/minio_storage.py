from django.conf import settings
from minio import Minio
import base64, io, uuid
from datetime import datetime


class MinioStorage:
    def __init__(self):
        endpoint = settings.AWS_S3_ENDPOINT_URL.replace("http://", "").replace("https://", "")
        self.client = Minio(
            endpoint=endpoint,
            access_key=settings.AWS_ACCESS_KEY_ID,
            secret_key=settings.AWS_SECRET_ACCESS_KEY,
            secure=settings.AWS_S3_ENDPOINT_URL.startswith("https")
        )
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

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
            if old_file_path:
                try:
                    self.client.remove_object(bucket_name=self.bucket, object_name=old_file_path)
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
