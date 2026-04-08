from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ppaa_performance", "0008_activitydocument_quarter_financial_year"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE performance_targets
                      ADD COLUMN IF NOT EXISTS responsible_officer_id INTEGER NULL,
                      ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP WITH TIME ZONE NULL,
                      ADD COLUMN IF NOT EXISTS assigned_by_id INTEGER NULL;
                    """,
                    reverse_sql="""
                    ALTER TABLE performance_targets
                      DROP COLUMN IF EXISTS responsible_officer_id,
                      DROP COLUMN IF EXISTS assigned_at,
                      DROP COLUMN IF EXISTS assigned_by_id;
                    """,
                )
            ],
            state_operations=[
                migrations.AddField(
                    model_name="target",
                    name="responsible_officer_id",
                    field=models.IntegerField(
                        blank=True,
                        null=True,
                        help_text="SPISM Performance Officer (auth_user.id) responsible for this target",
                    ),
                ),
                migrations.AddField(
                    model_name="target",
                    name="assigned_at",
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="target",
                    name="assigned_by_id",
                    field=models.IntegerField(blank=True, null=True),
                ),
            ],
        )
    ]

