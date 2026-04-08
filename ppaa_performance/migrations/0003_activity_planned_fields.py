# Add planned period and planned value label to Activity.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ppaa_performance", "0002_financialyear"),
    ]

    operations = [
        migrations.AddField(
            model_name="activity",
            name="planned_value_label",
            field=models.CharField(
                blank=True,
                help_text="What the planned value represents, e.g. Assessment, Number of trainings",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="activity",
            name="planned_financial_year",
            field=models.CharField(
                blank=True,
                help_text="Financial year when activity will be conducted, e.g. 2024/2025",
                max_length=9,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="activity",
            name="planned_quarter",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[(1, "Q1"), (2, "Q2"), (3, "Q3"), (4, "Q4")],
                help_text="Quarter when activity will be conducted (Q1–Q4)",
                null=True,
            ),
        ),
    ]
