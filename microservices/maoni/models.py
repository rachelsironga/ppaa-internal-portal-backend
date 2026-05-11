import uuid

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


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
        UNDER_HANDLER_REVIEW = "UNDER_HANDLER_REVIEW", "Under handler review"
        ESCALATED_TO_REVIEWER = "ESCALATED_TO_REVIEWER", "Escalated to reviewer"
        RETURNED_TO_HANDLER = "RETURNED_TO_HANDLER", "Returned to handler"
        HANDLER_RESPONDED_TO_REVIEWER = (
            "HANDLER_RESPONDED_TO_REVIEWER",
            "Handler responded to reviewer",
        )
        HANDLER_RESPONDED_TO_CONTRIBUTOR = (
            "HANDLER_RESPONDED_TO_CONTRIBUTOR",
            "Handler responded to contributor",
        )
        CLOSED_APPROVED = "CLOSED_APPROVED", "Closed - approved"
        CLOSED_REJECTED = "CLOSED_REJECTED", "Closed - rejected"

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
    # Users live on ``default`` DB; Maoni tables live on ``maoni_db``.
    # Store the user GUID rather than a cross-database FK.
    submitted_by_guid = models.UUIDField(null=True, blank=True, db_index=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    department_received_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When staff first opened the case (Submitted → Under handler review) for this department queue.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "maoni"
        ordering = ["-created_at"]

    def __str__(self):
        return (self.title or "")[:80]


class MaoniSuggestionComment(models.Model):
    """Thread message on a suggestion (contributor or staff)."""

    class MessageType(models.TextChoices):
        GENERAL = "GENERAL", "General reply"
        CLARIFICATION = "CLARIFICATION", "Clarification request"
        WORKFLOW = "WORKFLOW", "Workflow / status note"

    class ThreadScope(models.TextChoices):
        CONTRIBUTOR = "CONTRIBUTOR", "Contributor-visible thread"
        STAFF = "STAFF", "Staff-only (handler & institutional reviewer)"

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
    # Store the commenter GUID rather than a cross-database FK.
    commented_by_guid = models.UUIDField(null=True, blank=True, db_index=True)
    is_hr_reply = models.BooleanField(default=False)
    message_type = models.CharField(
        max_length=40,
        choices=MessageType.choices,
        default=MessageType.GENERAL,
        db_index=True,
    )
    thread_scope = models.CharField(
        max_length=20,
        choices=ThreadScope.choices,
        default=ThreadScope.CONTRIBUTOR,
        db_index=True,
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "maoni"
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment on {self.suggestion_id}"


class MaoniWorkflowSettings(models.Model):
    """
    Singleton-style Maoni workflow settings.
    We keep one active row and read the latest by updated_at.
    """

    escalation_days = models.PositiveIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Days a suggestion can remain with handler before escalation is due.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "maoni"
        ordering = ["-updated_at"]
        verbose_name = "Maoni workflow settings"
        verbose_name_plural = "Maoni workflow settings"

    def __str__(self):
        return f"Escalation: {self.escalation_days} day(s)"
