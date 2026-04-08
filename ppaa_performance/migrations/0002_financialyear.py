# Financial Year for Setup & Configuration. Format 2025-2026, start_date, end_date.

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ppaa_performance", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FinancialYear",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("uid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True, blank=True, null=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_by_id", models.IntegerField(blank=True, null=True)),
                ("updated_by_id", models.IntegerField(blank=True, null=True)),
                ("deleted_by_id", models.IntegerField(blank=True, null=True)),
                ("name", models.CharField(help_text="Format: YYYY-YYYY e.g. 2025-2026", max_length=9, unique=True)),
                ("start_date", models.DateField(help_text="Financial year start date (e.g. 1 July)")),
                ("end_date", models.DateField(help_text="Financial year end date (e.g. 30 June next year)")),
            ],
            options={
                "db_table": "performance_financial_years",
                "ordering": ["-start_date"],
                "verbose_name": "Financial Year",
            },
        ),
    ]
