"""
Run makemigrations (if needed) then migrate default and performance_dashboard DBs.
Use when you see: "Your models have changes that are not yet reflected in a migration".
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run makemigrations then migrate (default + performance_dashboard)."

    def handle(self, *args, **options):
        self.stdout.write("Running makemigrations...")
        call_command("makemigrations", verbosity=1)
        self.stdout.write("Migrating default database...")
        call_command("migrate", database="default", verbosity=1)
        self.stdout.write("Migrating performance_dashboard database...")
        call_command("migrate", database="performance_dashboard", verbosity=1)
        self.stdout.write(self.style.SUCCESS("Done."))
