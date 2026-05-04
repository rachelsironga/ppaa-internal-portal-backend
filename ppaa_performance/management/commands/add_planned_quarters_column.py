"""
Add planned_quarters column to performance_activities in the performance_dashboard database.
Use this if you get: column performance_activities.planned_quarters does not exist

Usage (with virtualenv activated, from project root):
  python manage.py add_planned_quarters_column
"""
from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Add planned_quarters column to performance_activities in performance_dashboard DB."

    def handle(self, *args, **options):
        db_alias = "performance_dashboard"
        try:
            conn = connections[db_alias]
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'performance_activities'
                    AND column_name = 'planned_quarters'
                    """
                )
                if cursor.fetchone():
                    self.stdout.write(
                        self.style.SUCCESS(
                            "Column planned_quarters already exists on performance_activities. Nothing to do."
                        )
                    )
                    return

                self.stdout.write("Adding planned_quarters (JSONB, default '[]')...")
                cursor.execute(
                    """
                    ALTER TABLE performance_activities
                    ADD COLUMN planned_quarters JSONB NOT NULL DEFAULT '[]'
                    """
                )

                # Record migration so Django won't try to run 0007 again
                cursor.execute(
                    """
                    SELECT 1 FROM django_migrations
                    WHERE app = 'ppaa_performance' AND name = '0007_activity_planned_quarters'
                    """
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        """
                        INSERT INTO django_migrations (app, name, applied)
                        VALUES ('ppaa_performance', '0007_activity_planned_quarters', NOW())
                        """
                    )
                    self.stdout.write("Recorded migration 0007_activity_planned_quarters as applied.")

            self.stdout.write(
                self.style.SUCCESS(
                    "Column planned_quarters added. Restart the backend and try adding/editing activities again."
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Failed: {e}\n"
                    "Ensure the performance_dashboard database exists and is configured in .env "
                    "(PERFORMANCE_DASHBOARD_DB_NAME, POSTGRES_*)."
                )
            )
            raise
