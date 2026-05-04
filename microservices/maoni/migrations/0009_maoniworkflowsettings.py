from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("maoni", "0008_relax_all_legacy_closure_columns_not_null"),
    ]

    operations = [
        migrations.CreateModel(
            name="MaoniWorkflowSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "escalation_days",
                    models.PositiveIntegerField(
                        default=3,
                        help_text="Days a suggestion can remain with handler before escalation is due.",
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(365),
                        ],
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Maoni workflow settings",
                "verbose_name_plural": "Maoni workflow settings",
                "ordering": ["-updated_at"],
            },
        ),
    ]

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("maoni", "0008_relax_all_legacy_closure_columns_not_null"),
    ]

    operations = [
        migrations.CreateModel(
            name="MaoniWorkflowSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "escalation_days",
                    models.PositiveIntegerField(
                        default=3,
                        help_text="Days a suggestion can remain with handler before escalation is due.",
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(365),
                        ],
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Maoni workflow settings",
                "verbose_name_plural": "Maoni workflow settings",
                "ordering": ["-updated_at"],
            },
        ),
    ]

