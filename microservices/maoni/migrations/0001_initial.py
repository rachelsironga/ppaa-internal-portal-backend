# Maoni tables live on ``maoni_db`` only. User rows live on ``default``; FKs must not
# reference ``auth_user`` in this database (that table does not exist here).

import uuid

import django.db.models.deletion
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    # Do not depend on ppaa_auth here — those migrations run on ``default`` only.
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="MaoniCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uid", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name_plural": "Maoni categories",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="MaoniSuggestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uid", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("title", models.TextField()),
                ("description", models.TextField(blank=True)),
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
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("SUBMITTED", "Submitted"),
                            ("UNDER_HANDLER_REVIEW", "Under handler review"),
                            ("ESCALATED_TO_REVIEWER", "Escalated to reviewer"),
                            ("RETURNED_TO_HANDLER", "Returned to handler"),
                            ("HANDLER_RESPONDED_TO_REVIEWER", "Handler responded to reviewer"),
                            ("HANDLER_RESPONDED_TO_CONTRIBUTOR", "Handler responded to contributor"),
                            ("CLOSED_APPROVED", "Closed - approved"),
                            ("CLOSED_REJECTED", "Closed - rejected"),
                        ],
                        default="DRAFT",
                        max_length=40,
                    ),
                ),
                ("department_uid", models.CharField(blank=True, max_length=64, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="suggestions",
                        to="maoni.maonicategory",
                    ),
                ),
                (
                    "submitted_by_guid",
                    models.UUIDField(blank=True, db_index=True, null=True),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="MaoniSuggestionComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uid", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("is_hr_reply", models.BooleanField(default=False)),
                (
                    "message_type",
                    models.CharField(
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
                (
                    "thread_scope",
                    models.CharField(
                        choices=[
                            ("CONTRIBUTOR", "Contributor-visible thread"),
                            ("STAFF", "Staff-only (handler & institutional reviewer)"),
                        ],
                        db_index=True,
                        default="CONTRIBUTOR",
                        max_length=20,
                    ),
                ),
                ("comment", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="replies",
                        to="maoni.maonisuggestioncomment",
                    ),
                ),
                (
                    "suggestion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comments",
                        to="maoni.maonisuggestion",
                    ),
                ),
                (
                    "commented_by_guid",
                    models.UUIDField(blank=True, db_index=True, null=True),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="MaoniWorkflowSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "escalation_days",
                    models.PositiveIntegerField(
                        default=3,
                        help_text="Days a suggestion can remain with handler before escalation is due.",
                        validators=[MinValueValidator(1), MaxValueValidator(365)],
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
