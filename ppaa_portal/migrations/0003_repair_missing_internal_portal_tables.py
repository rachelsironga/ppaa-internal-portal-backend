"""
Create ppaa_portal tables that are missing (AuditLog, document library).

Depends on ppaa_auth.0003 so ppaa_auth_department and auth_user exist before
AuditLog foreign keys are created.
"""

from django.db import migrations


def repair_missing_tables(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        existing = set(connection.introspection.table_names(cursor))

    # PortalDocumentCategory before PortalDocument; AuditLog last (FK to Department).
    for model_name in (
        "PortalDocumentCategory",
        "PortalDocument",
        "AuditLog",
    ):
        model = apps.get_model("ppaa_portal", model_name)
        table = model._meta.db_table
        if table in existing:
            continue
        schema_editor.create_model(model)
        existing.add(table)


class Migration(migrations.Migration):

    dependencies = [
        ("ppaa_portal", "0002_portal_documents"),
        ("ppaa_auth", "0003_repair_missing_ppaa_auth_tables"),
    ]

    operations = [
        migrations.RunPython(repair_missing_tables, migrations.RunPython.noop),
    ]
