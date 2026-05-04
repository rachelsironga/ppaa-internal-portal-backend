"""
Drop all tables in the performance_dashboard database (including django_migrations).
Use when you want to re-run migrations from scratch (e.g. to add performance_financial_years).
Usage:
  python manage.py drop_performance_tables
  python manage.py drop_performance_tables --no-input   # skip confirmation
  python manage.py migrate --database=performance_dashboard
"""
from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Drop all tables in the performance_dashboard database (for a clean re-migrate)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_true",
            help="Do not prompt for confirmation.",
        )

    def handle(self, *args, **options):
        db_alias = "performance_dashboard"
        try:
            conn = connections[db_alias]
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY tablename
                    """
                )
                tables = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Cannot connect to database '{db_alias}': {e}. "
                    "Check .env (PERFORMANCE_DASHBOARD_*, POSTGRES_*) and that the database exists."
                )
            )
            return

        if not tables:
            self.stdout.write(self.style.SUCCESS("No tables in performance_dashboard. Nothing to drop."))
            return

        if not options.get("noinput"):
            self.stdout.write(f"Tables to drop: {', '.join(tables)}")
            confirm = input("Drop all tables in performance_dashboard? [y/N]: ")
            if confirm.lower() != "y":
                self.stdout.write("Aborted.")
                return

        with conn.cursor() as cursor:
            for t in tables:
                # quote_ident for safe identifier (e.g. mixed case)
                cursor.execute(
                    'DROP TABLE IF EXISTS public."%s" CASCADE' % t.replace('"', '""')
                )
                self.stdout.write(f"Dropped: {t}")

        self.stdout.write(
            self.style.SUCCESS(
                "All tables dropped. Run: python manage.py migrate --database=performance_dashboard"
            )
        )
