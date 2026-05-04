from django.core.management.base import BaseCommand
from django.conf import settings
from ppaa_portal.services.minio.minio_client import client
import io


class Command(BaseCommand):
    help = "Initialize MinIO buckets for the portal"

    def handle(self, *args, **options):
        self.stdout.write("Initializing MinIO buckets...")
        
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        
        try:
            # Check if bucket exists
            if client.bucket_exists(bucket_name):
                self.stdout.write(
                    self.style.WARNING(f"Bucket '{bucket_name}' already exists")
                )
            else:
                # Create bucket
                client.make_bucket(bucket_name)
                self.stdout.write(
                    self.style.SUCCESS(f"Created bucket '{bucket_name}'")
                )
            
            # Create folder structure
            folders = [
                "documents",
                "announcements",
                "events",
                "links",
                "user_photos",
                "performance_documents",  # SPISM: activity documents (per-activity subfolders)
            ]
            
            for folder in folders:
                # Create empty object to represent folder
                try:
                    # Check if folder marker already exists
                    try:
                        client.stat_object(bucket_name, f"{folder}/.keep")
                        self.stdout.write(
                            self.style.WARNING(f"Folder '{folder}/' already exists")
                        )
                    except Exception:
                        # Folder doesn't exist, create it
                        client.put_object(
                            bucket_name=bucket_name,
                            object_name=f"{folder}/.keep",
                            data=io.BytesIO(b""),
                            length=0
                        )
                        self.stdout.write(
                            self.style.SUCCESS(f"Created folder '{folder}/'")
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"Folder '{folder}/' may already exist: {e}")
                    )
            
            self.stdout.write(
                self.style.SUCCESS("MinIO buckets initialized successfully!")
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to initialize buckets: {str(e)}")
            )
            raise



