import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ppaa_portal", "0006_portal_faq"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalAnnouncement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uid", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("title", models.CharField(max_length=500)),
                ("content", models.TextField()),
                (
                    "priority",
                    models.CharField(
                        choices=[
                            ("LOW", "Low"),
                            ("MEDIUM", "Medium"),
                            ("HIGH", "High"),
                            ("URGENT", "Urgent"),
                        ],
                        default="MEDIUM",
                        max_length=16,
                    ),
                ),
                ("is_pinned", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("start_date", models.DateTimeField(blank=True, null=True)),
                ("end_date", models.DateTimeField(blank=True, null=True)),
                ("file_key", models.CharField(blank=True, max_length=1024)),
                ("original_filename", models.CharField(blank=True, max_length=255)),
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
                        related_name="portal_announcements_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="portal_announcements_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-is_pinned", "-updated_at"],
            },
        ),
    ]
