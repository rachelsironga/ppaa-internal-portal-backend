import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ppaa_portal", "0004_portaldocumentcategory_is_active"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uid", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("title", models.CharField(max_length=500)),
                ("description", models.TextField(blank=True)),
                (
                    "event_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("MEETING", "Meeting"),
                            ("TRAINING", "Training"),
                            ("WORKSHOP", "Workshop"),
                            ("HOLIDAY", "Holiday"),
                            ("OTHER", "Other"),
                        ],
                        max_length=32,
                    ),
                ),
                ("start_date", models.DateTimeField()),
                ("end_date", models.DateTimeField()),
                ("location", models.CharField(blank=True, max_length=500)),
                ("is_all_day", models.BooleanField(default=False)),
                ("is_public", models.BooleanField(default=False)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="portal_events_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="portal_events_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-start_date"],
            },
        ),
    ]
