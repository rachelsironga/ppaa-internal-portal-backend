import os
from pathlib import Path
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Delete all migration files (except __init__.py) in all apps."

    def handle(self, *args, **options):
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        migration_files_deleted = 0

        # Loop through all apps
        for app_dir in project_root.iterdir():
            migrations_path = app_dir / "migrations"
            if migrations_path.exists() and migrations_path.is_dir():
                for file in migrations_path.iterdir():
                    if file.name != "__init__.py" and file.suffix == ".py":
                        file.unlink()
                        migration_files_deleted += 1

        self.stdout.write(self.style.SUCCESS(
            f"Deleted {migration_files_deleted} migration files (excluding __init__.py)."
        ))
