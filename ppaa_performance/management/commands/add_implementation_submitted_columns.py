"""
Add implementation_submitted_at and implementation_submitted_by_id to performance_activities
in the performance_dashboard database. Use this if you get:
  column performance_activities.implementation_submitted_at does not exist

Usage (with virtualenv activated, from project root):
  python manage.py add_implementation_submitted_columns
"""
from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Add implementation_submitted_at and implementation_submitted_by_id columns to performance_activities in performance_dashboard DB."

    def handle(self, *args, **options):
        db_alias = "performance_dashboard"
        try:
            conn = connections[db_alias]
            with conn.cursor() as cursor:
                # Check if column already exists
                cursor.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'performance_activities'
                    AND column_name = 'implementation_submitted_at'
                    """
                )
                if cursor.fetchone():
                    self.stdout.write(
                        self.style.SUCCESS(
                            "Column implementation_submitted_at already exists on performance_activities. Nothing to do."
                        )
                    )
                    return

                # Add columns
                self.stdout.write("Adding implementation_submitted_at...")
                cursor.execute(
                    """
                    ALTER TABLE performance_activities
                    ADD COLUMN implementation_submitted_at TIMESTAMP WITH TIME ZONE NULL
                    """
                )
                self.stdout.write("Adding implementation_submitted_by_id...")
                cursor.execute(
                    """
                    ALTER TABLE performance_activities
                    ADD COLUMN implementation_submitted_by_id INTEGER NULL
                    """
                )

                # Record migration so Django won't try to run 0004 again
                cursor.execute(
                    """
                    SELECT 1 FROM django_migrations
                    WHERE app = 'ppaa_performance' AND name = '0004_activity_implementation_submitted'
                    """
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        """
                        INSERT INTO django_migrations (app, name, applied)
                        VALUES ('ppaa_performance', '0004_activity_implementation_submitted', NOW())
                        """
                    )
            self.stdout.write(
                self.style.SUCCESS(
                    "Columns added successfully. Restart the backend and try opening Activities again."
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Failed: {e}\n"
                    "Make sure the performance_dashboard database exists and is configured in .env "
                    "(PERFORMANCE_DASHBOARD_DB_NAME, POSTGRES_*)."
                )
            )
            raise
