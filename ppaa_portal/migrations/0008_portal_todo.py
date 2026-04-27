import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ppaa_auth", "0005_group_profile_missing_columns"),
        ("ppaa_portal", "0007_portal_announcement"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalTodo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uid", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("title", models.CharField(max_length=500)),
                ("description", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("IN_PROGRESS", "In Progress"),
                            ("COMPLETED", "Completed"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="PENDING",
                        max_length=32,
                    ),
                ),
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
                ("start_date", models.DateTimeField(blank=True, null=True)),
                ("due_date", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
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
                        related_name="portal_todos_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="portal_todos",
                        to="ppaa_auth.department",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="portal_todos_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["due_date", "-updated_at"],
            },
        ),
    ]
