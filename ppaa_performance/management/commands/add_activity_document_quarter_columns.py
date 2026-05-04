"""
Add quarter and financial_year columns to performance_activity_documents in the performance_dashboard database.
Use this if you get: column "quarter" of relation "performance_activity_documents" does not exist

Usage (with virtualenv activated, from project root):
  python manage.py add_activity_document_quarter_columns
"""
from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Add quarter and financial_year columns to performance_activity_documents in performance_dashboard DB."

    def handle(self, *args, **options):
        db_alias = "performance_dashboard"
        try:
            conn = connections[db_alias]
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'performance_activity_documents'
                    AND column_name = 'quarter'
                    """
                )
                if cursor.fetchone():
                    self.stdout.write(
                        self.style.SUCCESS(
                            "Columns quarter and financial_year already exist on performance_activity_documents. Nothing to do."
                        )
                    )
                    self._record_migration_if_needed(cursor)
                    return

                self.stdout.write("Adding quarter (SMALLINT NULL)...")
                cursor.execute(
                    """
                    ALTER TABLE performance_activity_documents
                    ADD COLUMN quarter SMALLINT NULL
                    """
                )
                self.stdout.write("Adding financial_year (VARCHAR(9) NULL)...")
                cursor.execute(
                    """
                    ALTER TABLE performance_activity_documents
                    ADD COLUMN financial_year VARCHAR(9) NULL
                    """
                )

                self._record_migration_if_needed(cursor)

            self.stdout.write(
                self.style.SUCCESS(
                    "Columns quarter and financial_year added. Submit your quarterly report again."
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

    def _record_migration_if_needed(self, cursor):
        cursor.execute(
            """
            SELECT 1 FROM django_migrations
            WHERE app = 'ppaa_performance' AND name = '0008_activitydocument_quarter_financial_year'
            """
        )
        if cursor.fetchone() is None:
            cursor.execute(
                """
                INSERT INTO django_migrations (app, name, applied)
                VALUES ('ppaa_performance', '0008_activitydocument_quarter_financial_year', NOW())
                """
            )
            self.stdout.write("Recorded migration 0008_activitydocument_quarter_financial_year as applied.")
