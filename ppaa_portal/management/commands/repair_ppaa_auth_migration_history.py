"""
Repair django_migrations when you see:

  InconsistentMigrationHistory: Migration admin.0001_initial is applied before its
  dependency ppaa_auth.0001_initial on database 'default'.

This happens if the DB was migrated with a different AUTH_USER_MODEL / migration
order, or restored from another environment.

`migrate --fake` cannot fix this: Django runs check_consistent_history before any
migration runs, so the same error blocks fake runs. This command inserts rows
into django_migrations via MigrationRecorder instead.

Use ONLY when your database schema already matches ppaa_auth migrations
(e.g. auth_user and related tables exist and are correct). Otherwise use a fresh
database and run migrate.

After it succeeds, run: python manage.py migrate
"""
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = (
        "Record ppaa_auth migrations as applied in django_migrations (no SQL) to fix "
        "InconsistentMigrationHistory when admin ran before ppaa_auth was recorded."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="default",
            help="Nominates a database to repair. Defaults to the 'default' database.",
        )

    def handle(self, *args, **options):
        alias = options["database"]
        backend_root = Path(__file__).resolve().parent.parent.parent.parent
        migrations_dir = backend_root / "ppaa_auth" / "migrations"
        if not migrations_dir.is_dir():
            self.stderr.write(self.style.ERROR(f"Not found: {migrations_dir}"))
            return

        stems = sorted(p.stem for p in migrations_dir.glob("[0-9]*.py"))
        if not stems:
            self.stderr.write(self.style.ERROR("No numbered migrations in ppaa_auth."))
            return

        self.stdout.write(
            self.style.WARNING(
                "Recording ppaa_auth in django_migrations (no SQL). "
                "Ensure DB schema already matches ppaa_auth."
            )
        )

        connection = connections[alias]
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()

        for stem in stems:
            key = ("ppaa_auth", stem)
            if key in applied:
                self.stdout.write(f"  ppaa_auth.{stem} (already recorded, skip)")
                continue
            recorder.record_applied("ppaa_auth", stem)
            self.stdout.write(self.style.SUCCESS(f"  ppaa_auth.{stem} … recorded"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done ({alias}). Next: python manage.py migrate\n"
                "If migrate still fails, your DB may need a fresh migrate (drop DB in dev)."
            )
        )
