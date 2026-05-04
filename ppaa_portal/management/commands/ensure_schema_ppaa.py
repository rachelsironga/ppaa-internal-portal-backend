"""
Apply ppaa_auth then ppaa_portal migrations so repair migrations create any
missing tables (auth, departments, positional levels, user profiles, audit log,
internal portal documents).

Usage:
  python manage.py ensure_schema_ppaa
  python manage.py ensure_schema_ppaa --database default
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run migrations for ppaa_auth and ppaa_portal (ensures required tables exist)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="default",
            help="Nominates a database. Defaults to 'default'.",
        )

    def handle(self, *args, **options):
        db = options["database"]
        self.stdout.write(self.style.NOTICE(f"Migrating ppaa_auth on {db!r} …"))
        call_command("migrate", "ppaa_auth", database=db, interactive=False, verbosity=1)
        self.stdout.write(self.style.NOTICE(f"Migrating ppaa_portal on {db!r} …"))
        call_command("migrate", "ppaa_portal", database=db, interactive=False, verbosity=1)
        self.stdout.write(self.style.SUCCESS("Done."))
