from django.db import migrations, models


class Migration(migrations.Migration):
    """
    message_type is required in some deployments (NOT NULL). Use IF NOT EXISTS so
    databases that already have the column (added manually) still apply state cleanly.
    """

    dependencies = [
        ("maoni", "0009_maoniworkflowsettings"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE maoni_maonisuggestioncomment
                    ADD COLUMN IF NOT EXISTS message_type varchar(40) NOT NULL DEFAULT 'GENERAL';
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="maonisuggestioncomment",
                    name="message_type",
                    field=models.CharField(
                        choices=[
                            ("GENERAL", "General reply"),
                            ("CLARIFICATION", "Clarification request"),
                            ("WORKFLOW", "Workflow / status note"),
                        ],
                        db_index=True,
                        default="GENERAL",
                        max_length=40,
                    ),
                ),
            ],
        ),
    ]
