from rest_framework import serializers

from ppaa_performance.models import (
    FinancialYear,
    Objective,
    Target,
    Activity,
    QuarterlyData,
    KPIActual,
    ActivityDocument,
)
from ppaa_performance.serializers import (
    ObjectiveSerializer,
    TargetSerializer,
    TargetListSerializer,
    ActivitySerializer,
    ActivityListSerializer,
    QuarterlyDataSerializer,
    KPIActualSerializer,
    KPIActualWriteSerializer,
    ActivityDocumentSerializer,
    ActivityDocumentWriteSerializer,
)


class FinancialYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialYear
        fields = [
            "uid",
            "name",
            "start_date",
            "end_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["uid", "created_at", "updated_at"]


class ImplementationActivityListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for implementation list and approvals.
    Expects queryset annotated with:
      - quarterly_data_count
      - documents_count
      - pending_implementation_approval_count (locked QD submitted but not approved)
    """

    target_title = serializers.CharField(source="target.title", read_only=True)
    objective_title = serializers.CharField(
        source="target.objective.title", read_only=True
    )
    quarterly_data_count = serializers.IntegerField(read_only=True, default=0)
    documents_count = serializers.IntegerField(read_only=True, default=0)
    pending_implementation_approval_count = serializers.IntegerField(
        read_only=True, default=0
    )
    implementation_approved = serializers.SerializerMethodField()
    implementation_review_status = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = [
            "uid",
            "title",
            "weight",
            "planned_financial_year",
            "planned_quarter",
            "planned_quarters",
            "target_title",
            "objective_title",
            "quarterly_data_count",
            "documents_count",
            "implementation_submitted_at",
            "pending_implementation_approval_count",
            "implementation_approved",
            "implementation_review_status",
        ]

    def get_implementation_approved(self, obj):
        pending = getattr(obj, "pending_implementation_approval_count", 0) or 0
        return bool(obj.implementation_submitted_at) and pending == 0

    def get_implementation_review_status(self, obj):
        pending = getattr(obj, "pending_implementation_approval_count", 0) or 0
        if pending > 0:
            return "PENDING_APPROVAL"
        if obj.implementation_submitted_at:
            return "APPROVED"
        return "NOT_SUBMITTED"


class ImplementationTargetListSerializer(serializers.ModelSerializer):
    """
    Serializer for KPI implementation tab (targets with KPI actuals count).
    Expects queryset annotated with:
      - kpi_actuals_count
    """

    objective_title = serializers.CharField(source="objective.title", read_only=True)
    kpi_actuals_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Target
        fields = [
            "uid",
            "title",
            "weight",
            "objective_title",
            "kpi_name",
            "kpi_unit",
            "kpi_planned_value",
            "kpi_direction",
            "kpi_actuals_count",
        ]


__all__ = [
    "FinancialYearSerializer",
    "ObjectiveSerializer",
    "TargetSerializer",
    "TargetListSerializer",
    "ActivitySerializer",
    "ActivityListSerializer",
    "ImplementationActivityListSerializer",
    "ImplementationTargetListSerializer",
    "QuarterlyDataSerializer",
    "KPIActualSerializer",
    "KPIActualWriteSerializer",
    "ActivityDocumentSerializer",
    "ActivityDocumentWriteSerializer",
]

