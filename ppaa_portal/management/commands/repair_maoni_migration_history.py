"""
Fix InconsistentMigrationHistory on secondary databases, e.g.::

    Migration ppaa_portal.0001_initial is applied before its dependency
    ppaa_auth.0004_remove_user_dob on database 'maoni_db'.

``migrate --database=maoni_db`` still records every migration in the plan in
``django_migrations`` even when ``allow_migrate`` skips all operations for that
app on that DB. That leaves stray rows and breaks ``makemigrations`` (which
checks history on every configured connection).

This command deletes ``django_migrations`` rows whose ``app`` label is not
allowed on that database per ``ppaa_portal.db_router``.

Usage::

    docker compose exec backend python manage.py repair_maoni_migration_history
    docker compose exec backend python manage.py repair_maoni_migration_history --database=performance_dashboard_db
    docker compose exec backend python manage.py repair_maoni_migration_history --dry-run
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections

from ppaa_portal.db_router import (
    MaoniRouter,
    PerformanceDashboardRouter,
    ReportsManagementRouter,
)


def _allowed_apps(alias: str) -> frozenset[str] | None:
    if alias == MaoniRouter.database_name:
        return MaoniRouter.route_app_labels
    if alias == PerformanceDashboardRouter.database_name:
        return PerformanceDashboardRouter.route_app_labels
    if alias == ReportsManagementRouter.database_name:
        return ReportsManagementRouter.route_app_labels
    return None


class Command(BaseCommand):
    help = "Remove stray django_migrations rows on a secondary database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default=MaoniRouter.database_name,
            help=f"Database alias (default: {MaoniRouter.database_name})",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print rows that would be removed; do not delete.",
        )

    def handle(self, *args, **options):
        alias = options["database"]
        dry_run = options["dry_run"]

        if alias not in settings.DATABASES:
            self.stderr.write(self.style.ERROR(f"Unknown DATABASES alias: {alias!r}"))
            return

        allowed = _allowed_apps(alias)
        if allowed is None:
            self.stderr.write(
                self.style.ERROR(
                    f"No built-in allowlist for {alias!r}. Supported: "
                    f"{MaoniRouter.database_name}, {PerformanceDashboardRouter.database_name}, "
                    f"{ReportsManagementRouter.database_name}."
                )
            )
            return

        conn = connections[alias]
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, app, name FROM django_migrations ORDER BY id")
            rows = cursor.fetchall()

        stray = [(rid, app, name) for rid, app, name in rows if app not in allowed]

        if not stray:
            self.stdout.write(self.style.SUCCESS(f"No stray rows on {alias!r}."))
            return

        self.stdout.write(
            self.style.WARNING(
                f"{len(stray)} stray row(s) on {alias!r} (allowed apps: {', '.join(sorted(allowed))}):"
            )
        )
        for rid, app, name in stray:
            self.stdout.write(f"  id={rid}  {app}.{name}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no changes."))
            return

        with conn.cursor() as cursor:
            for rid, app, name in stray:
                cursor.execute(
                    "DELETE FROM django_migrations WHERE id = %s",
                    [rid],
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Removed {len(stray)} row(s) from {alias!r}. "
                "You can run makemigrations / migrate again."
            )
        )
