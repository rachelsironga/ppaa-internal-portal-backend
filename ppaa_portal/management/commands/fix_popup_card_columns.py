"""
Add missing gratitude_message (and motivational_quote, es_image_path if missing)
to portal_popup_cards. Run this if you see "column does not exist" errors.
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Add missing columns to portal_popup_cards table"

    def handle(self, *args, **options):
        vendor = connection.vendor
        table = "portal_popup_cards"

        # Columns that might be missing: gratitude_message, motivational_quote, es_image_path
        columns_sql = [
            ("gratitude_message", "TEXT"),
            ("motivational_quote", "TEXT"),
            ("es_image_path", "VARCHAR(500)"),
        ]

        with connection.cursor() as cursor:
            for col_name, col_type in columns_sql:
                try:
                    if vendor == "postgresql":
                        sql = f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{col_name}" {col_type};'
                    elif vendor == "sqlite":
                        sql = f'ALTER TABLE "{table}" ADD COLUMN "{col_name}" {col_type};'
                    else:
                        sql = f"ALTER TABLE `{table}` ADD COLUMN `{col_name}` {col_type} NULL;"
                    cursor.execute(sql)
                    self.stdout.write(self.style.SUCCESS(f"Added column {table}.{col_name}"))
                except Exception as e:
                    err = str(e).lower()
                    if "already exists" in err or "duplicate column" in err or "duplicate column name" in err:
                        self.stdout.write(self.style.WARNING(f"Column {col_name} already exists, skipping"))
                    else:
                        self.stdout.write(self.style.ERROR(f"Column {col_name}: {e}"))

        self.stdout.write(self.style.SUCCESS("Done. Try loading popup cards again."))
