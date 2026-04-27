"""
Create ppaa_auth tables that are missing from the database.

Use when django_migrations lists ppaa_auth as applied but tables were never
created (e.g. --fake-initial, restored DB, or manual drift). Safe to run if some
tables already exist: only missing tables are created, in dependency order.
"""

from django.db import migrations


def repair_missing_tables(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        existing = set(connection.introspection.table_names(cursor))

    # Same dependency order as 0001_initial.
    for model_name in (
        "User",
        "Currency",
        "Directory",
        "Department",
        "GroupProfile",
        "PositionalLevel",
        "UserProfile",
        "Country",
    ):
        model = apps.get_model("ppaa_auth", model_name)
        table = model._meta.db_table
        if table in existing:
            continue
        schema_editor.create_model(model)
        existing.add(table)


class Migration(migrations.Migration):

    dependencies = [
        ("ppaa_auth", "0002_user_signature"),
    ]

    operations = [
        migrations.RunPython(repair_missing_tables, migrations.RunPython.noop),
    ]
