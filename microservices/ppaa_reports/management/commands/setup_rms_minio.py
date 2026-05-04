"""
Django management command to setup MinIO reports-management bucket and grant permissions.
Run: python manage.py setup_rms_minio

Requires: mc (MinIO Client) installed - brew install minio/stable/mc
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Setup MinIO reports-management bucket and grant app user read/write permissions"

    def normalize_endpoint(self, endpoint):
        """Normalize local MinIO endpoints to the API port."""
        parsed = urlparse(endpoint)
        hostname = parsed.hostname or parsed.netloc.split(":")[0]
        scheme = parsed.scheme or "http"
        port = parsed.port if parsed.port else 9000

        if port in {9001, 9100, 9101}:
            port = 9000

        return f"{scheme}://{hostname}:{port}"

    def run_mc(self, args, env=None):
        """Run mc command, return (success, stdout, stderr)."""
        try:
            result = subprocess.run(
                ["mc"] + args,
                capture_output=True,
                text=True,
                env={**os.environ, **(env or {})},
            )
            return result.returncode == 0, result.stdout, result.stderr
        except FileNotFoundError:
            return False, "", "mc not found. Install: brew install minio/stable/mc"

    def handle(self, *args, **options):
        endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
        access_key = getattr(settings, "AWS_ACCESS_KEY_ID", None)
        secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
        bucket = getattr(settings, "RMS_REPORTS_BUCKET", "reports-management")

        if not endpoint or not access_key or not secret_key:
            self.stderr.write(
                self.style.ERROR(
                    "MinIO not configured. Set AWS_S3_ENDPOINT_URL, AWS_ACCESS_KEY_ID, "
                    "AWS_SECRET_ACCESS_KEY in .env"
                )
            )
            return

        endpoint = self.normalize_endpoint(endpoint)

        # Use root credentials for admin ops (fallback to app creds)
        root_user = os.getenv("MINIO_ROOT_USER", access_key)
        root_pass = os.getenv("MINIO_ROOT_PASSWORD", secret_key)

        host = endpoint.replace("http://", "").replace("https://", "")
        alias = "rmsminio"

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:ListBucket",
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{bucket}",
                        f"arn:aws:s3:::{bucket}/*",
                    ],
                }
            ],
        }

        self.stdout.write(f"Endpoint: {endpoint}")
        self.stdout.write(f"Bucket: {bucket}")
        self.stdout.write(f"User: {access_key}")
        self.stdout.write("")

        # 1. Set alias
        self.stdout.write("1. Setting mc alias...")
        ok, out, err = self.run_mc(
            ["alias", "set", alias, f"http://{host}", root_user, root_pass]
        )
        if not ok:
            self.stderr.write(self.style.ERROR(f"   Failed: {err or out}"))
            return
        self.stdout.write("   OK")

        # 2. Create bucket
        self.stdout.write("2. Creating bucket...")
        ok, out, err = self.run_mc(["mb", "--ignore-existing", f"{alias}/{bucket}"])
        if not ok and "BucketAlreadyOwnedByYou" not in err:
            self.stderr.write(self.style.ERROR(f"   Failed: {err or out}"))
            return
        self.stdout.write("   OK")

        # 3. Create policy
        self.stdout.write("3. Creating IAM policy...")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(policy, f, indent=2)
            policy_path = f.name

        try:
            ok, out, err = self.run_mc(
                ["admin", "policy", "create", alias, "rms-reports-policy", policy_path]
            )
            if not ok and "already exists" not in (err or "").lower():
                self.stdout.write(f"   (policy may exist: {err or out})")
            else:
                self.stdout.write("   OK")
        finally:
            os.unlink(policy_path)

        # 4. Attach policy to user
        self.stdout.write(f"4. Attaching policy to user {access_key}...")
        ok, out, err = self.run_mc(
            ["admin", "policy", "attach", alias, "rms-reports-policy", "--user", access_key]
        )
        if not ok:
            self.stderr.write(self.style.WARNING(f"   {err or out}"))
            self.stdout.write("")
            self.stdout.write(
                "   If the user does not exist, create it first:"
            )
            self.stdout.write(
                f"   mc admin user add {alias} {access_key} <secret_key>"
            )
            self.stdout.write("")
            self.stdout.write(
                "   If patrick.nachenga is the MinIO ROOT user, you may not need"
            )
            self.stdout.write(
                "   this step. Try using MINIO_ROOT_USER/MINIO_ROOT_PASSWORD in .env"
            )
            self.stdout.write(
                "   (the credentials MinIO showed when you started it)."
            )
        else:
            self.stdout.write("   OK")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("✅ Setup complete. Restart Django and try uploading a report.")
        )
