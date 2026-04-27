# Adds auth_user.signature for databases that predated this field on the model.
# Uses IF NOT EXISTS so re-runs / partially migrated DBs do not error.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ppaa_auth", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE auth_user ADD COLUMN IF NOT EXISTS "
                        "signature varchar(512) NOT NULL DEFAULT '';"
                    ),
                    reverse_sql="ALTER TABLE auth_user DROP COLUMN IF EXISTS signature;",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="user",
                    name="signature",
                    field=models.CharField(blank=True, max_length=512),
                ),
            ],
        ),
    ]
