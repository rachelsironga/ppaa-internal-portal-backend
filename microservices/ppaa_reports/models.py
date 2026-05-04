import uuid
from datetime import date, timedelta
from django.db import models
from django.core.validators import (
    FileExtensionValidator,
    MinLengthValidator,
    RegexValidator,
)
from django.conf import settings
from ppaa_auth.models import Department

# PPAA auth does not expose a separate Directory model; reuse Department.
Directory = Department


class BaseModel(models.Model):
    """Base model with common fields for all RMS models"""
    id = models.BigAutoField(primary_key=True)
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_%(class)s",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_%(class)s",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_%(class)s",
    )

    class Meta:
        abstract = True


class FinancialYear(BaseModel):
    """Financial year for report categorization (e.g., 2025/2026)"""
    name = models.CharField(
        max_length=20,
        unique=True,
        help_text="e.g., 2025/2026",
        validators=[
            RegexValidator(
                regex=r'^\d{4}/\d{4}$',
                message='Financial year must be in format YYYY/YYYY (e.g., 2025/2026)'
            )
        ]
    )
    start_date = models.DateField(help_text="Start date of the financial year")
    end_date = models.DateField(help_text="End date of the financial year")
    is_current = models.BooleanField(
        default=False,
        help_text="Is this the current active financial year"
    )
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "ppaa_reports_financial_year"
        ordering = ["-start_date"]
        verbose_name = "Financial Year"
        verbose_name_plural = "Financial Years"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_current:
            FinancialYear.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)
        # Auto-create periods when financial year is created
        self._create_quarters()
        self._create_biannual_periods()

    def _create_quarters(self):
        """Auto-create quarterly periods for this financial year"""
        from datetime import timedelta
        from calendar import monthrange
        
        if not self.pk:
            return
            
        # Check if quarters already exist
        if self.periods.filter(period_type='quarter').exists():
            return
            
        def add_months(start_date, months):
            """Add months to a date"""
            month = start_date.month - 1 + months
            year = start_date.year + month // 12
            month = month % 12 + 1
            day = min(start_date.day, monthrange(year, month)[1])
            return date(year, month, day)
        
        # Calculate quarter dates
        quarter_months = 3
        start = self.start_date
        
        for q in range(1, 5):
            q_start = add_months(start, (q-1) * quarter_months)
            q_end_base = add_months(start, q * quarter_months)
            q_end = q_end_base - timedelta(days=1)
            
            # Don't create if end date exceeds financial year end
            if q_end > self.end_date:
                q_end = self.end_date
                
            FinancialPeriod.objects.get_or_create(
                financial_year=self,
                period_type='quarter',
                period_number=q,
                defaults={
                    'name': f"Q{q} {self.name}",
                    'start_date': q_start,
                    'end_date': q_end,
                    'created_by': self.created_by,
                    'updated_by': self.updated_by,
                }
            )

    def _create_biannual_periods(self):
        """Auto-create half-year (biannual) periods for this financial year"""
        from datetime import timedelta
        from calendar import monthrange

        if not self.pk:
            return

        if self.periods.filter(period_type='biannual').exists():
            return

        def add_months(start_date, months):
            month = start_date.month - 1 + months
            year = start_date.year + month // 12
            month = month % 12 + 1
            day = min(start_date.day, monthrange(year, month)[1])
            return date(year, month, day)

        start = self.start_date
        half_months = 6
        for h in range(1, 3):
            h_start = add_months(start, (h - 1) * half_months)
            h_end_base = add_months(start, h * half_months)
            h_end = h_end_base - timedelta(days=1)
            if h_end > self.end_date:
                h_end = self.end_date

            FinancialPeriod.objects.get_or_create(
                financial_year=self,
                period_type='biannual',
                period_number=h,
                defaults={
                    'name': f"H{h} {self.name}",
                    'start_date': h_start,
                    'end_date': h_end,
                    'created_by': self.created_by,
                    'updated_by': self.updated_by,
                }
            )


class FinancialPeriod(BaseModel):
    """Periods within a financial year (Quarters, Months, Bi-Annual)"""
    PERIOD_TYPES = [
        ('quarter', 'Quarter'),
        ('month', 'Month'),
        ('biannual', 'Bi-Annual'),
    ]

    financial_year = models.ForeignKey(
        FinancialYear,
        on_delete=models.CASCADE,
        related_name="periods"
    )
    period_type = models.CharField(
        max_length=20,
        choices=PERIOD_TYPES,
        default='quarter'
    )
    period_number = models.PositiveIntegerField(
        help_text="Period number (e.g., 1 for Q1, 1-12 for months)"
    )
    name = models.CharField(
        max_length=50,
        help_text="e.g., Q1 2025/2026, January 2025"
    )
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        db_table = "ppaa_reports_financial_period"
        ordering = ["financial_year", "period_type", "period_number"]
        verbose_name = "Financial Period"
        verbose_name_plural = "Financial Periods"
        unique_together = ['financial_year', 'period_type', 'period_number']

    def __str__(self):
        return self.name

    @property
    def display_name(self):
        """Human readable name"""
        if self.period_type == 'quarter':
            return f"Quarter {self.period_number}"
        elif self.period_type == 'month':
            return f"Month {self.period_number}"
        elif self.period_type == 'biannual':
            return f"Half {self.period_number}"
        return self.name


class Stakeholder(BaseModel):
    """External organizations that receive reports"""
    ORGANIZATION_TYPES = [
        ('government', 'Government Agency'),
        ('regulatory', 'Regulatory Body'),
        ('partner', 'Partner Organization'),
        ('donor', 'Donor/Funding Agency'),
        ('ngo', 'NGO'),
        ('private', 'Private Sector'),
        ('academic', 'Academic Institution'),
        ('other', 'Other'),
    ]

    name = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(2)],
        help_text="Stakeholder organization name"
    )
    organization_type = models.CharField(
        max_length=20,
        choices=ORGANIZATION_TYPES,
        default='other'
    )
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r'^\+?[0-9\s\-()]+$',
                message='Enter a valid phone number'
            )
        ]
    )
    address = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "ppaa_reports_stakeholder"
        ordering = ["name"]
        verbose_name = "Stakeholder"
        verbose_name_plural = "Stakeholders"

    def __str__(self):
        return self.name


class ReportType(BaseModel):
    """Types of reports (e.g., Quarterly, Annual, Monthly)"""
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('biannual', 'Bi-Annual'),
        ('annual', 'Annual'),
        ('adhoc', 'Ad-hoc'),
    ]
    REMINDER_TIMING_CHOICES = [
        ('before', 'Before deadline'),
        ('after', 'After deadline'),
    ]

    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Short code for the report type (e.g., QTR, ANN)"
    )
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='monthly'
    )
    description = models.TextField(blank=True, null=True)
    submission_deadline_days = models.PositiveIntegerField(
        default=0,
        help_text="Number of days after the selected reporting period ends before submission is due"
    )
    before_reminder_days = models.PositiveIntegerField(
        default=7,
        help_text="Send approaching-deadline reminder this many days before the computed deadline"
    )
    after_reminder_days = models.PositiveIntegerField(
        default=0,
        help_text="Send overdue reminder this many days after the computed deadline"
    )
    default_days_before_deadline = models.PositiveIntegerField(
        default=7,
        help_text="Default number of days before deadline to send reminders"
    )
    reminder_timing = models.CharField(
        max_length=10,
        choices=REMINDER_TIMING_CHOICES,
        default='before',
        help_text="Whether reminders are sent before or after the deadline"
    )
    requires_attachment = models.BooleanField(
        default=True,
        help_text="Whether this report type requires file attachment"
    )
    template_file = models.FileField(
        upload_to='report_templates/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx', 'xlsx'])],
        help_text="Template file for this report type"
    )

    class Meta:
        db_table = "ppaa_reports_report_type"
        ordering = ["name"]
        verbose_name = "Report Type"
        verbose_name_plural = "Report Types"

    def __str__(self):
        return f"{self.name} ({self.code})"


class ReportCategory(BaseModel):
    """Categories for organizing reports (e.g., Finance, Operations, HR)"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    color = models.CharField(
        max_length=7,
        default='#3B82F6',
        help_text="Hex color code for UI display"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Icon class name for UI display"
    )

    class Meta:
        db_table = "ppaa_reports_category"
        ordering = ["name"]
        verbose_name = "Report Category"
        verbose_name_plural = "Report Categories"

    def __str__(self):
        return self.name


def report_attachment_path(instance, filename):
    """
    Generate upload path for report attachments.
    Includes report uid so each report fetches its own file (avoids collisions
    when multiple reports in same FY/directory upload files with same name).
    """
    directory_code = instance.directory.code if instance.directory else 'general'
    fy_name = instance.financial_year.name if instance.financial_year else 'general'
    # Use report uid (or pk) to ensure unique path per report
    unique_id = str(instance.uid) if hasattr(instance, 'uid') and instance.uid else (
        str(instance.pk) if instance.pk else uuid.uuid4().hex
    )
    safe_name = f"{unique_id}_{filename}"
    return f"reports/{fy_name}/{directory_code}/{safe_name}"


class Report(BaseModel):
    """Main report model with status and deadline tracking"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    REPORT_SCOPE = [
        ('internal', 'Internal'),
        ('external', 'External'),
    ]

    title = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(5)],
        help_text="Report title"
    )
    reference_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="Auto-generated reference number"
    )
    report_type = models.ForeignKey(
        ReportType,
        on_delete=models.PROTECT,
        related_name="reports"
    )
    category = models.ForeignKey(
        ReportCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports"
    )
    directory = models.ForeignKey(
        Directory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="directory_reports",
        help_text="Directorate this report belongs to"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_reports",
        help_text="Unit/Department within the directorate"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_reports",
        help_text="User assigned to work on this report"
    )
    stakeholder = models.ForeignKey(
        Stakeholder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
        help_text="External stakeholder (for external reports)"
    )
    other_stakeholder_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Custom stakeholder name if not in the list"
    )
    financial_year = models.ForeignKey(
        FinancialYear,
        on_delete=models.PROTECT,
        related_name="reports"
    )
    financial_period = models.ForeignKey(
        'FinancialPeriod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
        help_text="Quarter/Period for quarterly/monthly reports"
    )
    scope = models.CharField(
        max_length=20,
        choices=REPORT_SCOPE,
        default='internal'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    deadline_date = models.DateField(db_index=True)
    submission_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Actual date when report was submitted"
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_reports"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Report description or requirements"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Internal notes about the report"
    )
    attachment = models.FileField(
        upload_to=report_attachment_path,
        max_length=500,
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip']
            )
        ],
        help_text="Report document attachment"
    )
    progress_percentage = models.PositiveIntegerField(
        default=0,
        help_text="Progress percentage (0-100)"
    )
    reminder_sent = models.BooleanField(
        default=False,
        help_text="Whether deadline reminder has been sent"
    )
    reminder_sent_at = models.DateTimeField(blank=True, null=True)
    before_reminder_sent = models.BooleanField(
        default=False,
        help_text="Whether the before-deadline reminder has been sent"
    )
    before_reminder_sent_at = models.DateTimeField(blank=True, null=True)
    after_reminder_sent = models.BooleanField(
        default=False,
        help_text="Whether the overdue reminder has been sent"
    )
    after_reminder_sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "ppaa_reports_report"
        ordering = ["-deadline_date", "-created_at"]
        verbose_name = "Report"
        verbose_name_plural = "Reports"
        indexes = [
            models.Index(fields=['status', 'deadline_date']),
            models.Index(fields=['directory', 'financial_year']),
            models.Index(fields=['stakeholder', 'status']),
        ]

    def __str__(self):
        return f"{self.title} ({self.reference_number})"

    def save(self, *args, **kwargs):
        if not self.reference_number:
            self.reference_number = self._generate_reference_number()
        super().save(*args, **kwargs)

    def _generate_reference_number(self):
        """Generate unique reference number: RPT-YYYY-XXXX"""
        year = date.today().year
        last_report = Report.objects.filter(
            reference_number__startswith=f"RPT-{year}-"
        ).order_by('-reference_number').first()
        
        if last_report and last_report.reference_number:
            try:
                last_num = int(last_report.reference_number.split('-')[-1])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        return f"RPT-{year}-{new_num:04d}"

    @property
    def deadline_state(self):
        """Calculate deadline state dynamically"""
        if self.status == 'submitted':
            return 'completed'
        
        today = date.today()
        days_until_deadline = (self.deadline_date - today).days
        
        if days_until_deadline < 0:
            return 'overdue'
        elif days_until_deadline == 0:
            return 'due_today'
        elif days_until_deadline <= 3:
            return 'due_soon'
        else:
            return 'on_track'

    @property
    def days_until_deadline(self):
        """Calculate days until deadline (negative if overdue)"""
        return (self.deadline_date - date.today()).days

    @property
    def is_overdue(self):
        """Check if report is overdue"""
        return self.deadline_state == 'overdue'

    @property
    def submitted_late(self):
        """Check if the report was submitted after its deadline."""
        if not self.submission_date or not self.deadline_date:
            return False
        return self.submission_date.date() > self.deadline_date

    @property
    def days_overdue_on_submission(self):
        """How many days late the report was at the time of submission."""
        if not self.submitted_late:
            return 0
        return (self.submission_date.date() - self.deadline_date).days

    @property
    def effective_stakeholder_name(self):
        """Get stakeholder name (from relationship or custom field)"""
        if self.stakeholder:
            return self.stakeholder.name
        return self.other_stakeholder_name or "N/A"


class ReportProgress(BaseModel):
    """Track progress updates for reports"""
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="progress_updates"
    )
    percentage = models.PositiveIntegerField(
        help_text="Progress percentage at this point"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Progress update notes"
    )
    
    class Meta:
        db_table = "ppaa_reports_progress"
        ordering = ["-created_at"]
        verbose_name = "Report Progress"
        verbose_name_plural = "Report Progress Updates"

    def __str__(self):
        return f"{self.report.title} - {self.percentage}%"


class ReportComment(BaseModel):
    """Comments and discussions on reports"""
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="comments"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies"
    )
    message = models.TextField(validators=[MinLengthValidator(1)])
    is_system_generated = models.BooleanField(
        default=False,
        help_text="Whether this comment was auto-generated by the system"
    )
    mentions_directory = models.BooleanField(
        default=False,
        help_text="When True, ED/RMS_REPORT_MANAGER is directing this message to the report's directory"
    )

    class Meta:
        db_table = "ppaa_reports_comment"
        ordering = ["created_at"]
        verbose_name = "Report Comment"
        verbose_name_plural = "Report Comments"

    def __str__(self):
        return f"Comment on {self.report.title}"


class ReportCommentRead(models.Model):
    """Tracks when a user last read comments on a report (for unread indicator)"""
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="comment_reads"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="report_comment_reads"
    )
    last_read_at = models.DateTimeField(
        help_text="When the user last viewed this report's comments"
    )

    class Meta:
        db_table = "ppaa_reports_comment_read"
        unique_together = [("report", "user")]
        verbose_name = "Report Comment Read"
        verbose_name_plural = "Report Comment Reads"

    def __str__(self):
        return f"{self.user} read {self.report.title} at {self.last_read_at}"


class ReportAuditTrail(BaseModel):
    """Audit trail for all RMS actions"""
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('status_changed', 'Status Changed'),
        ('submitted', 'Submitted'),
        ('downloaded', 'Downloaded'),
        ('progress_updated', 'Progress Updated'),
        ('comment_added', 'Comment Added'),
        ('attachment_uploaded', 'Attachment Uploaded'),
        ('reminder_sent', 'Reminder Sent'),
        ('reassigned', 'Reassigned'),
        ('deleted', 'Deleted'),
    ]

    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="audit_trail",
        null=True,
        blank=True,
    )
    entity_type = models.CharField(max_length=100, blank=True, null=True)
    entity_uid = models.UUIDField(blank=True, null=True)
    entity_name = models.CharField(max_length=255, blank=True, null=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="report_actions"
    )
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    comments = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "ppaa_reports_audit_trail"
        ordering = ["-created_at"]
        verbose_name = "Report Audit Trail"
        verbose_name_plural = "Report Audit Trails"

    def __str__(self):
        target_name = self.entity_name or getattr(self.report, "title", None) or "RMS Item"
        return f"{self.action} - {target_name}"


class ReportReminder(BaseModel):
    """Scheduled reminders for report deadlines"""
    REMINDER_TYPE = [
        ('deadline', 'Deadline Approaching'),
        ('overdue', 'Overdue Notice'),
        ('follow_up', 'Follow Up'),
        ('custom', 'Custom Reminder'),
    ]

    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="reminders"
    )
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPE)
    scheduled_date = models.DateTimeField()
    sent_at = models.DateTimeField(blank=True, null=True)
    is_sent = models.BooleanField(default=False)
    recipient_uids = models.JSONField(
        default=list,
        help_text="List of user UIDs to receive the reminder"
    )
    subject = models.CharField(max_length=255)
    message = models.TextField()

    class Meta:
        db_table = "ppaa_reports_reminder"
        ordering = ["scheduled_date"]
        verbose_name = "Report Reminder"
        verbose_name_plural = "Report Reminders"

    def __str__(self):
        return f"{self.reminder_type} - {self.report.title}"


class ReportSetting(BaseModel):
    """Global settings for the PPAA Reports module"""
    reference_number_prefix = models.CharField(
        max_length=10,
        default='RPT',
        help_text="Prefix for report reference numbers"
    )
    reference_number_counter = models.PositiveIntegerField(
        default=1,
        help_text="Current counter for reference numbers"
    )
    reset_counter_yearly = models.BooleanField(
        default=True,
        help_text="Reset reference number counter at start of each year"
    )
    default_reminder_days = models.PositiveIntegerField(
        default=3,
        help_text="Default days before deadline to send reminders"
    )
    due_soon_threshold_days = models.PositiveIntegerField(
        default=3,
        help_text="Days before deadline to mark as 'Due Soon'"
    )
    enable_email_notifications = models.BooleanField(default=True)
    enable_system_notifications = models.BooleanField(default=True)
    max_attachment_size_mb = models.PositiveIntegerField(
        default=10,
        help_text="Maximum attachment file size in MB"
    )
    allowed_file_extensions = models.JSONField(
        default=list,
        help_text="List of allowed file extensions"
    )
    organization_name = models.CharField(
        max_length=255,
        default='PPAA',
        help_text="Organization name for reports and notifications"
    )

    class Meta:
        db_table = "ppaa_reports_setting"
        verbose_name = "Report Setting"
        verbose_name_plural = "Report Settings"

    def __str__(self):
        return "PPAA Reports Settings"

    def save(self, *args, **kwargs):
        if not self.allowed_file_extensions:
            self.allowed_file_extensions = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Get or create singleton settings instance"""
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
