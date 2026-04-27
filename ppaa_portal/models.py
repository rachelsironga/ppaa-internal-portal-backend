import uuid

from django.conf import settings
from django.db import DatabaseError, models


class AuditLog(models.Model):
    """Used by ``ppaa_auth`` views (e.g. login) for activity tracking."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64)
    model_name = models.CharField(max_length=128)
    object_id = models.CharField(max_length=255, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(null=True, blank=True)
    ip_address = models.CharField(max_length=64, null=True, blank=True)
    user_agent = models.CharField(max_length=512, null=True, blank=True)
    department = models.ForeignKey(
        "ppaa_auth.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


def record_audit_log(**kwargs):
    """Create an audit row; no-op if the table is missing or another DB error occurs."""
    try:
        AuditLog.objects.create(**kwargs)
    except DatabaseError:
        pass


def portal_client_ip(request):
    """Same as RMS ``_rms_client_ip``: respect ``X-Forwarded-For`` behind proxies."""
    if not request:
        return ""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()[:64]
    return (request.META.get("REMOTE_ADDR") or "")[:64]


def audit_department_for_user(user):
    """
    Resolve department for audit rows — aligned with Report Management (``_rms_report_audit_log``):
    prefer active ``UserProfile.department``, then ``get_position()`` / department_uid.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        from ppaa_auth.models import UserProfile

        profile = (
            UserProfile.objects.filter(
                user=user, is_active=True, is_deleted=False
            )
            .select_related("department")
            .first()
        )
        if profile and profile.department_id:
            return profile.department
    except Exception:
        pass
    try:
        from ppaa_auth.models import Department

        if hasattr(user, "get_position") and callable(user.get_position):
            pos = user.get_position() or {}
            du = pos.get("department_uid")
            if du:
                return Department.objects.filter(uid=du, is_deleted=False).first()
    except Exception:
        pass
    return None


def create_audit_log(request, action, model_name, obj=None, changes=None):
    """
    Write a portal ``AuditLog`` row (same shape as login). Use from API views.

    ``obj`` may be a model instance; ``object_id`` / ``object_repr`` are derived when present.
    """
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return
    ip = portal_client_ip(request) or None
    ua = (request.META.get("HTTP_USER_AGENT") or "")[:500]
    object_id = ""
    object_repr = ""
    if obj is not None:
        object_id = str(getattr(obj, "guid", None) or getattr(obj, "pk", "") or "")
        object_repr = str(obj)[:200]
    dept = audit_department_for_user(user)
    record_audit_log(
        user=user,
        action=str(action)[:64],
        model_name=str(model_name)[:128],
        object_id=object_id[:255],
        object_repr=object_repr[:255],
        changes=changes,
        ip_address=ip,
        user_agent=ua,
        department=dept,
        created_by=user,
        updated_by=user,
    )


class PortalDocumentCategory(models.Model):
    """Categories for internal portal documents (staff-facing library)."""

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_document_categories_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_document_categories_updated",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PortalDocument(models.Model):
    class DocStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        PortalDocumentCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    status = models.CharField(
        max_length=20,
        choices=DocStatus.choices,
        default=DocStatus.DRAFT,
    )
    download_count = models.PositiveIntegerField(default=0)
    is_public = models.BooleanField(default=False)
    tags = models.CharField(max_length=512, blank=True)
    file_key = models.CharField(max_length=1024, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_documents_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_documents_updated",
    )

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


class PortalEvent(models.Model):
    """Staff-facing calendar events (internal portal)."""

    class EventType(models.TextChoices):
        MEETING = "MEETING", "Meeting"
        TRAINING = "TRAINING", "Training"
        WORKSHOP = "WORKSHOP", "Workshop"
        HOLIDAY = "HOLIDAY", "Holiday"
        OTHER = "OTHER", "Other"

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    event_type = models.CharField(
        max_length=32,
        choices=EventType.choices,
        blank=True,
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    location = models.CharField(max_length=500, blank=True)
    is_all_day = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_events_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_events_updated",
    )

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.title


class PortalFAQ(models.Model):
    """Staff-managed FAQs for the internal portal."""

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    question = models.TextField()
    answer = models.TextField()
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_faqs_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_faqs_updated",
    )

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Portal FAQ"
        verbose_name_plural = "Portal FAQs"

    def __str__(self):
        return (self.question or "")[:80]


class PortalAnnouncement(models.Model):
    """Staff announcements (internal portal + dashboard)."""

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    title = models.CharField(max_length=500)
    content = models.TextField()
    priority = models.CharField(
        max_length=16,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    is_pinned = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    file_key = models.CharField(max_length=1024, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_announcements_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_announcements_updated",
    )

    class Meta:
        ordering = ["-is_pinned", "-updated_at"]

    def __str__(self):
        return self.title


class PortalTodo(models.Model):
    """Internal portal task list (staff todos)."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
    )
    priority = models.CharField(
        max_length=16,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    department = models.ForeignKey(
        "ppaa_auth.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_todos",
    )
    start_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_todos_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_todos_updated",
    )

    class Meta:
        ordering = ["due_date", "-updated_at"]

    def __str__(self):
        return self.title


class PortalQuickLink(models.Model):
    """Shortcut tiles on the public portal and staff dashboard (name, target URL, optional logo)."""

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=2048)
    logo_key = models.CharField(max_length=512, blank=True, default="")
    logo_original_filename = models.CharField(max_length=255, blank=True, default="")
    total_clicks = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_quick_links_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_quick_links_updated",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PortalPopupCard(models.Model):
    """Motivational / gratitude content and optional image for the public portal popup."""

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    motivational_quote = models.TextField(blank=True, default="")
    gratitude_message = models.TextField(blank=True, default="")
    es_image_key = models.CharField(max_length=512, blank=True, default="")
    es_image_original_filename = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_popup_cards_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_popup_cards_updated",
    )

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"PopupCard {self.uid}"


class PortalPrFlyer(models.Model):
    """PR posters and flyers (images and/or linked YouTube/Instagram videos) for portal galleries."""

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    title = models.CharField(max_length=255, blank=True, default="")
    caption = models.TextField(blank=True, default="")
    video_url = models.CharField(
        max_length=2048,
        blank=True,
        default="",
        help_text="Optional public YouTube or Instagram post/reel URL (used instead of or with a poster image).",
    )
    image_key = models.CharField(max_length=512, blank=True, default="")
    image_original_filename = models.CharField(max_length=255, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    visible_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If set, hidden from dashboards and public image URL after this time (server clock).",
    )
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_pr_flyers_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_pr_flyers_updated",
    )

    class Meta:
        ordering = ["sort_order", "-updated_at"]

    def __str__(self):
        label = (self.title or "").strip() or str(self.uid)
        return f"PR Flyer {label}"

    @classmethod
    def filter_visible_at(cls, qs):
        """Limit queryset to rows still within their visibility window (if ``visible_until`` is set)."""
        from django.db.models import Q
        from django.utils import timezone

        now = timezone.now()
        return qs.filter(Q(visible_until__isnull=True) | Q(visible_until__gte=now))


class RmsStakeholder(models.Model):
    """External stakeholders for Report Management System (RMS) UI."""

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    organization_type = models.CharField(max_length=32, db_index=True)
    contact_person = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(max_length=2048, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rms_stakeholders_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rms_stakeholders_updated",
    )

    class Meta:
        db_table = "rms_stakeholders"
        ordering = ["name"]

    def __str__(self):
        return self.name


class RmsReportType(models.Model):
    """Report types for RMS (frequency, deadlines, reminders)."""

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, db_index=True)
    frequency = models.CharField(max_length=16, db_index=True)
    description = models.TextField(blank=True)
    submission_deadline_days = models.PositiveSmallIntegerField(default=0)
    before_reminder_days = models.PositiveSmallIntegerField(default=7)
    after_reminder_days = models.PositiveSmallIntegerField(default=0)
    requires_attachment = models.BooleanField(default=True)
    template_file = models.URLField(max_length=2048, blank=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rms_report_types_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rms_report_types_updated",
    )

    class Meta:
        db_table = "rms_report_types"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(is_deleted=False),
                name="unique_rms_report_type_code_active",
            ),
        ]

    def __str__(self):
        return self.name


class RmsReportCategory(models.Model):
    """Report categories for RMS (name, code, color, icon)."""

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, db_index=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=16, default="#3B82F6")
    icon = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rms_report_categories_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rms_report_categories_updated",
    )

    class Meta:
        db_table = "rms_report_categories"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(is_deleted=False),
                name="unique_rms_report_category_code_active",
            ),
        ]

    def __str__(self):
        return self.name


class RmsReport(models.Model):
    """Submitted / draft RMS report instance (create flow from internal portal)."""

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    reference_number = models.CharField(max_length=32, unique=True, db_index=True)
    title = models.CharField(max_length=512)
    report_type = models.ForeignKey(
        RmsReportType,
        on_delete=models.PROTECT,
        related_name="reports",
    )
    category = models.ForeignKey(
        RmsReportCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reports",
    )
    financial_year_uid = models.UUIDField(db_index=True)
    financial_period_uid = models.CharField(max_length=255, blank=True)
    financial_period_uids = models.JSONField(default=list, blank=True)
    scope = models.CharField(max_length=16, default="internal")
    priority = models.CharField(max_length=16, default="medium")
    status = models.CharField(max_length=32, default="draft", db_index=True)
    progress_percentage = models.PositiveSmallIntegerField(default=0)
    deadline_date = models.DateField(null=True, blank=True)
    stakeholder = models.ForeignKey(
        RmsStakeholder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reports",
    )
    other_stakeholder_name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    attachment = models.FileField(
        upload_to="rms_reports/%Y/%m/",
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "ppaa_auth.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rms_reports",
    )
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rms_reports_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rms_reports_updated",
    )
    reminder_before_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when the pre-deadline reminder email was sent (at most once).",
    )
    reminder_after_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when the post-deadline reminder email was sent (at most once).",
    )

    class Meta:
        db_table = "rms_reports"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class RmsReportPeriodState(models.Model):
    """Per implementation period (e.g. Q1–Q4) progress and submission for one report."""

    report = models.ForeignKey(
        RmsReport,
        on_delete=models.CASCADE,
        related_name="period_states",
    )
    period_uid = models.CharField(max_length=255, db_index=True)
    progress_percentage = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=32, default="pending", db_index=True)
    notes = models.TextField(blank=True)
    attachment = models.FileField(
        upload_to="rms_reports/periods/%Y/%m/",
        null=True,
        blank=True,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        db_table = "rms_report_period_states"
        ordering = ["period_uid"]
        constraints = [
            models.UniqueConstraint(
                fields=["report", "period_uid"],
                name="unique_rms_report_period_uid",
            ),
        ]

    def __str__(self):
        return f"{self.report_id}:{self.period_uid}"


class RmsReportProgressEntry(models.Model):
    """History of progress % updates for an RMS report (detail page timeline)."""

    report = models.ForeignKey(
        RmsReport,
        on_delete=models.CASCADE,
        related_name="progress_entries",
    )
    period_uid = models.CharField(max_length=255, blank=True, default="")
    percentage = models.PositiveSmallIntegerField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        db_table = "rms_report_progress_entries"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.report_id} @ {self.percentage}%"
