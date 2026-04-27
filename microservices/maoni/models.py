import uuid

from django.conf import settings
from django.db import models


class MaoniCategory(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "maoni"
        ordering = ["name"]
        verbose_name_plural = "Maoni categories"

    def __str__(self):
        return self.name


class MaoniSuggestion(models.Model):
    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        PENDING_REVIEW = "PENDING_REVIEW", "Pending review"
        UNDER_CONSIDERATION = "UNDER_CONSIDERATION", "Under consideration"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        IMPLEMENTED = "IMPLEMENTED", "Implemented"

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    title = models.TextField()
    description = models.TextField(blank=True)
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    status = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    category = models.ForeignKey(
        MaoniCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suggestions",
    )
    department_uid = models.CharField(max_length=64, blank=True, null=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maoni_suggestions",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "maoni"
        ordering = ["-created_at"]

    def __str__(self):
        return (self.title or "")[:80]


class MaoniSuggestionComment(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    suggestion = models.ForeignKey(
        MaoniSuggestion,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    commented_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maoni_comments",
    )
    is_hr_reply = models.BooleanField(default=False)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "maoni"
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment on {self.suggestion_id}"
