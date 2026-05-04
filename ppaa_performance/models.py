"""
Performance Dashboard models. Stored in performance_dashboard_db (router).
User references stored as IntegerField (user id from default DB auth) so we use
the same auth module as the portal/Maoni without duplicating auth_user in this DB.
"""
from decimal import Decimal
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class SPISMBaseModel(models.Model):
    """Base for SPISM models. User refs as IntegerField to use portal auth (no FK across DBs)."""
    id = models.BigAutoField(primary_key=True)
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by_id = models.IntegerField(null=True, blank=True)
    updated_by_id = models.IntegerField(null=True, blank=True)
    deleted_by_id = models.IntegerField(null=True, blank=True)

    class Meta:
        abstract = True


class FinancialYear(SPISMBaseModel):
    """
    Configured financial year. Format: 2025/2026.
    Objectives can be linked to one or more financial years.
    Date range defines when the year starts and ends (e.g. 1 Jul 2025 - 30 Jun 2026).
    """
    name = models.CharField(
        max_length=9,
        unique=True,
        help_text="Format: YYYY/YYYY e.g. 2025/2026",
    )
    start_date = models.DateField(help_text="Financial year start date (e.g. 1 July)")
    end_date = models.DateField(help_text="Financial year end date (e.g. 30 June next year)")

    class Meta:
        db_table = "performance_financial_years"
        ordering = ["-start_date"]
        verbose_name = "Financial Year"

    def __str__(self):
        return self.name


class Objective(SPISMBaseModel):
    """Institutional objective. Sum of objective weights institution-wide = 100%."""
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("RETURNED", "Returned"),
        ("CLOSED","Closed")
    ]
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, null=True)
    weight = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100"))],
        help_text="Weight % (sum of all objectives = 100)",
    )
    financial_year = models.CharField(max_length=9, help_text="e.g. 2024/2025")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    approval_comment = models.TextField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "performance_objectives"
        ordering = ["financial_year", "title"]
        verbose_name = "Objective"

    def __str__(self):
        return f"{self.title} ({self.financial_year})"


class Target(SPISMBaseModel):
    """Target under an objective. Must have KPI defined."""
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("RETURNED", "Returned"),
    ]
    KPI_DIRECTION_CHOICES = [
        ("INCREASE", "Increase favorable"),
        ("DECREASE", "Decrease favorable"),
    ]
    KPI_SOURCE_TYPE_CHOICES = [
        ("DERIVED", "Activity-Driven KPI"),
        ("DIRECT", "Direct KPI"),
    ]
    KPI_CALCULATION_METHOD_CHOICES = [
        ("CUMULATIVE", "Cumulative"),
        ("AVERAGE", "Average"),
    ]
    objective = models.ForeignKey(
        Objective,
        on_delete=models.CASCADE,
        related_name="targets",
    )
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, null=True)
    weight = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100"))],
        help_text="Weight % (sum per objective = 100)",
    )
    planned_value = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    kpi_name = models.CharField(max_length=255, blank=True)
    kpi_description = models.TextField(blank=True, null=True)
    kpi_source_type = models.CharField(
        max_length=20,
        choices=KPI_SOURCE_TYPE_CHOICES,
        default="DERIVED",
    )
    kpi_unit = models.CharField(max_length=100, blank=True)
    kpi_planned_value = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    kpi_baseline = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    kpi_direction = models.CharField(
        max_length=20,
        choices=KPI_DIRECTION_CHOICES,
        default="INCREASE",
    )
    kpi_calculation_method = models.CharField(
        max_length=20,
        choices=KPI_CALCULATION_METHOD_CHOICES,
        default="CUMULATIVE",
    )
    kpi_reporting_frequency = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    approval_comment = models.TextField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by_id = models.IntegerField(null=True, blank=True)
    # NOTE: Stored as IntegerField (user id in default DB auth_user).
    # We cannot enforce a DB-level FK constraint across databases.
    responsible_officer_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="SPISM Performance Officer (auth_user.id) responsible for this target",
    )
    assigned_at = models.DateTimeField(blank=True, null=True)
    assigned_by_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "performance_targets"
        ordering = ["objective", "title"]
        verbose_name = "Target"

    def __str__(self):
        return f"{self.title}"


class Activity(SPISMBaseModel):
    """Activity under a target. Sum of activity weights per target = 100%."""
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("RETURNED", "Returned"),
    ]
    QUARTER_CHOICES = [(1, "Q1"), (2, "Q2"), (3, "Q3"), (4, "Q4")]
    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, null=True)
    weight = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100"))],
        help_text="Weight % (sum per target = 100)",
    )
    planned_value = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    planned_value_label = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="What the planned value represents, e.g. Assessment, Number of trainings",
    )
    planned_financial_year = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        help_text="Financial year when activity will be conducted (derived from target/objective)",
    )
    planned_quarter = models.PositiveSmallIntegerField(
        choices=QUARTER_CHOICES,
        null=True,
        blank=True,
        help_text="Deprecated: use planned_quarters. Single quarter when activity will be conducted.",
    )
    planned_quarters = models.JSONField(
        default=list,
        blank=True,
        help_text="Quarters when activity will be conducted, e.g. [1,2,3,4] for all quarters",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    approval_comment = models.TextField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by_id = models.IntegerField(null=True, blank=True)
    implementation_submitted_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When officer submitted implementation (quarterly data/documents) as complete",
    )
    implementation_submitted_by_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "performance_activities"
        ordering = ["target", "title"]
        verbose_name = "Activity"

    def __str__(self):
        return f"{self.title}"


class QuarterlyData(SPISMBaseModel):
    """Quarterly actuals for an activity."""
    QUARTER_CHOICES = [(1, "Q1"), (2, "Q2"), (3, "Q3"), (4, "Q4")]
    IMPLEMENTATION_STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
        ("APPROVED", "Approved"),
        ("RETURNED", "Returned"),
    ]
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name="quarterly_data",
    )
    quarter = models.PositiveSmallIntegerField(choices=QUARTER_CHOICES)
    financial_year = models.CharField(max_length=9)
    actual_value = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    computed_ai_percent = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
    )
    # DB column is NOT NULL, but this model previously didn't include it.
    # Adding it prevents Django from inserting NULL during quarter creation.
    implementation_status = models.CharField(
        max_length=20,
        choices=IMPLEMENTATION_STATUS_CHOICES,
        default="DRAFT",
    )
    implementation_submitted_at = models.DateTimeField(blank=True, null=True)
    implementation_submitted_by_id = models.IntegerField(blank=True, null=True)
    implementation_approved_at = models.DateTimeField(blank=True, null=True)
    implementation_approved_by_id = models.IntegerField(blank=True, null=True)
    implementation_approval_comment = models.TextField(blank=True, null=True)
    is_locked = models.BooleanField(default=False)

    class Meta:
        db_table = "performance_quarterly_data"
        ordering = ["activity", "financial_year", "quarter"]
        unique_together = [["activity", "financial_year", "quarter"]]
        verbose_name = "Quarterly Data"

    def __str__(self):
        return f"{self.activity.title} {self.get_quarter_display()} {self.financial_year}"


class KPIActual(SPISMBaseModel):
    """KPI actual value per reporting period for a target."""
    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name="kpi_actuals",
    )
    reporting_period = models.CharField(max_length=50, help_text="e.g. Q1 2024/2025")
    financial_year = models.CharField(max_length=9)
    quarter = models.PositiveSmallIntegerField(null=True, blank=True)
    actual_value = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0"))],
    )
    computed_kpi_percent = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "performance_kpi_actuals"
        ordering = ["target", "financial_year", "quarter"]
        verbose_name = "KPI Actual"

    def __str__(self):
        return f"{self.target.title} - {self.reporting_period}"


class ActivityDocument(SPISMBaseModel):
    """Supporting document for an activity. Can be linked to a specific quarter."""
    QUARTER_CHOICES = [(1, "Q1"), (2, "Q2"), (3, "Q3"), (4, "Q4")]
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    file_path = models.CharField(max_length=500, help_text="Storage path (e.g. MinIO key)")
    description = models.TextField(blank=True, null=True)
    quarter = models.PositiveSmallIntegerField(
        choices=QUARTER_CHOICES,
        null=True,
        blank=True,
        help_text="Quarter this document relates to (e.g. Q1 implementation approval)",
    )
    financial_year = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        help_text="Financial year this document relates to (e.g. 2024/2025)",
    )

    class Meta:
        db_table = "performance_activity_documents"
        ordering = ["-created_at"]
        verbose_name = "Activity Document"

    def __str__(self):
        return f"{self.file_name}"


class PerformanceAuditLog(models.Model):
    """Audit trail for performance entities. user_id references auth_user in default DB."""
    id = models.BigAutoField(primary_key=True)
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    entity_type = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=100)
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100, blank=True, null=True)  # e.g. "Objective", "Target", "Activity"
    object_repr = models.CharField(max_length=300, blank=True, null=True)  # human-readable title
    old_value = models.JSONField(blank=True, null=True)
    new_value = models.JSONField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    user_id = models.IntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "performance_audit_logs"
        ordering = ["-timestamp"]
