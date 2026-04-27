"""
Repair auth_group_profile when the table exists but is missing columns expected
by GroupProfile (e.g. drift after manual DB restore or partial create).
"""

from django.db import migrations


def _table_columns(schema_editor, table):
    with schema_editor.connection.cursor() as cursor:
        desc = schema_editor.connection.introspection.get_table_description(
            cursor, table
        )
    return {c.name.lower() for c in desc}


def forwards(apps, schema_editor):
    table = "auth_group_profile"
    qn = schema_editor.connection.ops.quote_name
    columns = _table_columns(schema_editor, table)
    vendor = schema_editor.connection.vendor

    with schema_editor.connection.cursor() as cursor:
        if "last_updated_at" not in columns:
            if vendor == "postgresql":
                sql = (
                    f"ALTER TABLE {qn(table)} "
                    f"ADD COLUMN {qn('last_updated_at')} TIMESTAMPTZ NULL"
                )
            elif vendor == "mysql":
                sql = (
                    f"ALTER TABLE {qn(table)} "
                    f"ADD COLUMN {qn('last_updated_at')} DATETIME(6) NULL"
                )
            else:
                sql = (
                    f"ALTER TABLE {qn(table)} "
                    f"ADD COLUMN {qn('last_updated_at')} datetime NULL"
                )
            cursor.execute(sql)

        columns = _table_columns(schema_editor, table)
        if "last_updated_by_id" not in columns:
            sql = (
                f"ALTER TABLE {qn(table)} "
                f"ADD COLUMN {qn('last_updated_by_id')} BIGINT NULL"
            )
            cursor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ("ppaa_auth", "0004_remove_department_directory_fk"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
