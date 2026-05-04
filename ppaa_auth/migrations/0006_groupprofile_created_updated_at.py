"""
Align auth_group_profile with GroupProfile timestamps.

Some deployments already have NOT NULL created_at/updated_at on auth_group_profile
while Django's model did not — INSERTs then omitted those columns and failed.
This migration adds the columns only when missing; state is always updated.
"""

from django.db import migrations, models


def _table_columns(schema_editor, table):
    with schema_editor.connection.cursor() as cursor:
        desc = schema_editor.connection.introspection.get_table_description(
            cursor, table
        )
    return {c.name.lower() for c in desc}


def forwards(apps, schema_editor):
    table = "auth_group_profile"
    columns = _table_columns(schema_editor, table)
    if "created_at" in columns and "updated_at" in columns:
        return

    vendor = schema_editor.connection.vendor
    qn = schema_editor.connection.ops.quote_name

    with schema_editor.connection.cursor() as cursor:
        if "created_at" not in columns:
            if vendor == "postgresql":
                cursor.execute(
                    f"ALTER TABLE {qn(table)} "
                    f"ADD COLUMN {qn('created_at')} TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                )
                cursor.execute(
                    f"ALTER TABLE {qn(table)} "
                    f"ALTER COLUMN {qn('created_at')} DROP DEFAULT"
                )
            elif vendor == "sqlite":
                cursor.execute(
                    f"ALTER TABLE {qn(table)} "
                    f"ADD COLUMN {qn('created_at')} datetime NOT NULL DEFAULT CURRENT_TIMESTAMP"
                )
            else:
                cursor.execute(
                    f"ALTER TABLE {qn(table)} "
                    f"ADD COLUMN {qn('created_at')} datetime(6) NOT NULL "
                    f"DEFAULT CURRENT_TIMESTAMP(6)"
                )

        columns = _table_columns(schema_editor, table)
        if "updated_at" not in columns:
            if vendor == "postgresql":
                cursor.execute(
                    f"ALTER TABLE {qn(table)} "
                    f"ADD COLUMN {qn('updated_at')} TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                )
                cursor.execute(
                    f"ALTER TABLE {qn(table)} "
                    f"ALTER COLUMN {qn('updated_at')} DROP DEFAULT"
                )
            elif vendor == "sqlite":
                cursor.execute(
                    f"ALTER TABLE {qn(table)} "
                    f"ADD COLUMN {qn('updated_at')} datetime NOT NULL DEFAULT CURRENT_TIMESTAMP"
                )
            else:
                cursor.execute(
                    f"ALTER TABLE {qn(table)} "
                    f"ADD COLUMN {qn('updated_at')} datetime(6) NOT NULL "
                    f"DEFAULT CURRENT_TIMESTAMP(6)"
                )


class Migration(migrations.Migration):

    dependencies = [
        ("ppaa_auth", "0005_group_profile_missing_columns"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(forwards, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="groupprofile",
                    name="created_at",
                    field=models.DateTimeField(auto_now_add=True),
                ),
                migrations.AddField(
                    model_name="groupprofile",
                    name="updated_at",
                    field=models.DateTimeField(auto_now=True),
                ),
            ],
        ),
    ]
