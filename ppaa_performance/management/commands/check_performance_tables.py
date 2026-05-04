"""
Check if SPISM (performance) tables exist in the performance_dashboard database.
If not, print clear instructions to run migrations.
Usage: python manage.py check_performance_tables
"""
from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Check if performance_objectives (and other SPISM tables) exist in performance_dashboard DB."

    def handle(self, *args, **options):
        db_alias = "performance_dashboard"

        try:
            conn = connections[db_alias]
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = %s
                    """,
                    ["performance_objectives"],
                )
                exists = cursor.fetchone() is not None
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Cannot connect to database '{db_alias}': {e}. "
                    "Check .env (PERFORMANCE_DASHBOARD_DB_NAME, POSTGRES_*) and that the database exists."
                )
            )
            return

        if exists:
            self.stdout.write(self.style.SUCCESS("SPISM tables found in performance_dashboard. You can save objectives."))
            return

        self.stdout.write(
            self.style.WARNING(
                "Table 'performance_objectives' does NOT exist in the performance_dashboard database.\n"
                "That is why you get: relation \"performance_objectives\" does not exist.\n\n"
                "Run the following (with your virtualenv activated):\n\n"
                "  python manage.py migrate --database=performance_dashboard\n\n"
                "This creates auth/user and SPISM tables in that database. Then save the objective again."
            )
        )
