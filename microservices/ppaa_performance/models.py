from django.conf import settings
from django.db import models

from ppaa_auth.models import BaseModel


class SpismFinancialYear(BaseModel):
    """Financial year for SPISM (e.g. 2025/2026) with calendar bounds."""

    name = models.CharField(max_length=32, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        db_table = "spism_financial_years"
        ordering = ["-start_date"]

    def __str__(self):
        return self.name


class SpismObjective(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        RETURNED = "RETURNED", "Returned"

    title = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    weight = models.DecimalField(max_digits=6, decimal_places=2)
    financial_year = models.CharField(max_length=32, db_index=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )

    class Meta:
        db_table = "spism_objectives"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class SpismTarget(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        RETURNED = "RETURNED", "Returned"

    objective = models.ForeignKey(
        SpismObjective,
        on_delete=models.CASCADE,
        related_name="targets",
    )
    title = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    weight = models.DecimalField(max_digits=6, decimal_places=2)
    planned_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    responsible_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spism_targets_responsible",
    )
    kpi_name = models.CharField(max_length=255, blank=True)
    kpi_source_type = models.CharField(max_length=32, default="DERIVED")
    kpi_unit = models.CharField(max_length=32, blank=True)
    kpi_planned_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    kpi_direction = models.CharField(max_length=32, default="INCREASE")
    kpi_calculation_method = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )

    class Meta:
        db_table = "spism_targets"
        ordering = ["-created_at"]


class SpismActivity(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        RETURNED = "RETURNED", "Returned"

    target = models.ForeignKey(
        SpismTarget,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    title = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    weight = models.DecimalField(max_digits=6, decimal_places=2)
    planned_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    planned_value_label = models.CharField(max_length=64, blank=True)
    planned_financial_year = models.CharField(max_length=32, blank=True, db_index=True)
    planned_quarters = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    approval_comment = models.TextField(
        blank=True,
        help_text="Latest planning (ES) return comment when status is RETURNED.",
    )
    implementation_submitted_at = models.DateTimeField(null=True, blank=True)
    implementation_quarters_state = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "spism_activities"
        ordering = ["-created_at"]


class SpismQuarterlyData(BaseModel):
    activity = models.ForeignKey(
        SpismActivity,
        on_delete=models.CASCADE,
        related_name="quarterly_rows",
    )
    quarter = models.PositiveSmallIntegerField()
    financial_year = models.CharField(max_length=32, db_index=True)
    actual_value = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        db_table = "spism_quarterly_data"
        ordering = ["financial_year", "quarter"]
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "quarter", "financial_year"],
                name="uniq_spism_quarterly_activity_q_fy",
            )
        ]


class SpismKpiActual(BaseModel):
    target = models.ForeignKey(
        SpismTarget,
        on_delete=models.CASCADE,
        related_name="kpi_actuals",
    )
    financial_year = models.CharField(max_length=32, db_index=True)
    reporting_period = models.CharField(max_length=128, blank=True)
    actual_value = models.DecimalField(max_digits=18, decimal_places=4)
    computed_kpi_percent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "spism_kpi_actuals"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["target", "financial_year"],
                name="uniq_spism_kpi_target_fy",
            )
        ]


class SpismActivityDocument(BaseModel):
    activity = models.ForeignKey(
        SpismActivity,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    file_key = models.CharField(max_length=512)
    original_filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField(default=0)
    mime_type = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)
    quarter = models.PositiveSmallIntegerField(null=True, blank=True)
    financial_year = models.CharField(max_length=32, blank=True)

    class Meta:
        db_table = "spism_activity_documents"
        ordering = ["-created_at"]


class SpismPerformanceAuditLog(BaseModel):
    entity_type = models.CharField(max_length=64, db_index=True)
    entity_uid = models.UUIDField(db_index=True)
    action = models.CharField(max_length=64)
    comment = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spism_audit_logs",
    )

    class Meta:
        db_table = "spism_performance_audit_logs"
        ordering = ["-created_at"]
