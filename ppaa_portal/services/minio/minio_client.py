from minio import Minio
from django.conf import settings
<<<<<<< HEAD

client = Minio(
    settings.AWS_S3_ENDPOINT_URL.replace("http://", "").replace("https://", ""),
    access_key=settings.AWS_ACCESS_KEY_ID,
    secret_key=settings.AWS_SECRET_ACCESS_KEY,
    secure=settings.AWS_S3_ENDPOINT_URL.startswith("https://"),
=======
from urllib.parse import urlparse

# Properly parse the endpoint URL to extract host and port
endpoint_url = settings.AWS_S3_ENDPOINT_URL
parsed = urlparse(endpoint_url)

# Extract hostname
hostname = parsed.hostname or parsed.netloc.split(':')[0]

# Extract port, default to 9000 (API port) if not specified
# Ensure we use API port (9000), not console port (9001)
port = parsed.port if parsed.port else 9000
if port == 9001:
    port = 9000  # Force API port, not console port

# Format endpoint as "hostname:port"
endpoint = f"{hostname}:{port}"

client = Minio(
    endpoint=endpoint,
    access_key=settings.AWS_ACCESS_KEY_ID,
    secret_key=settings.AWS_SECRET_ACCESS_KEY,
    secure=endpoint_url.startswith("https://"),
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
)
