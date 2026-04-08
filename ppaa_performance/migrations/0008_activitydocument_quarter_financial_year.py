# Generated manually for ActivityDocument quarter and financial_year

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ppaa_performance", "0007_activity_planned_quarters"),
    ]

    operations = [
        migrations.AddField(
            model_name="activitydocument",
            name="quarter",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[(1, "Q1"), (2, "Q2"), (3, "Q3"), (4, "Q4")],
                help_text="Quarter this document relates to (e.g. Q1 implementation approval)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="activitydocument",
            name="financial_year",
            field=models.CharField(
                blank=True,
                help_text="Financial year this document relates to (e.g. 2024/2025)",
                max_length=9,
                null=True,
            ),
        ),
    ]
