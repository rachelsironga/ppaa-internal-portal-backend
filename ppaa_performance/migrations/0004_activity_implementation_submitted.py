# Generated migration for implementation submission tracking

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ppaa_performance", "0003_activity_planned_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="activity",
            name="implementation_submitted_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="When officer submitted implementation (quarterly data/documents) as complete",
            ),
        ),
        migrations.AddField(
            model_name="activity",
            name="implementation_submitted_by_id",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
