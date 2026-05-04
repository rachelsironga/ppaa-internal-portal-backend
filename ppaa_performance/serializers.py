from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Objective,
    Target,
    Activity,
    QuarterlyData,
    KPIActual,
    ActivityDocument,
    PerformanceAuditLog,
)


class TargetUidField(serializers.Field):
    """Accept target by uid (string) and return Target instance for Activity create/update."""

    def to_internal_value(self, data):
        if data is None or data == "":
            return None
        uid = str(data).strip()
        target = Target.objects.filter(uid=uid, is_deleted=False).first()
        if not target:
            raise serializers.ValidationError("Target with this uid not found.")
        return target

    def to_representation(self, value):
        if value is None:
            return None
        return str(value.uid) if hasattr(value, "uid") else value


# Slug-related for FK by uid (for write)
class QuarterlyDataSerializer(serializers.ModelSerializer):
    activity = serializers.SlugRelatedField(
        slug_field="uid", queryset=Activity.objects.filter(is_deleted=False)
    )

    class Meta:
        model = QuarterlyData
        fields = [
            "uid",
            "activity",
            "quarter",
            "financial_year",
            "actual_value",
            "computed_ai_percent",
            "implementation_status",
            "implementation_submitted_at",
            "implementation_approved_at",
            "implementation_approval_comment",
            "is_locked",
            "created_at",
        ]
        read_only_fields = [
            "uid", "computed_ai_percent", "implementation_status",
            "implementation_submitted_at", "implementation_approved_at",
            "implementation_approval_comment", "created_at",
        ]


class KPIActualWriteSerializer(serializers.ModelSerializer):
    target = serializers.SlugRelatedField(
        slug_field="uid", queryset=Target.objects.filter(is_deleted=False)
    )

    class Meta:
        model = KPIActual
        fields = [
            "uid",
            "target",
            "reporting_period",
            "financial_year",
            "quarter",
            "actual_value",
            "computed_kpi_percent",
            "created_at",
        ]
        read_only_fields = ["uid", "computed_kpi_percent", "created_at"]


class ActivityDocumentWriteSerializer(serializers.ModelSerializer):
    activity = serializers.SlugRelatedField(
        slug_field="uid", queryset=Activity.objects.filter(is_deleted=False)
    )

    class Meta:
        model = ActivityDocument
        fields = [
            "uid",
            "activity",
            "file_name",
            "file_type",
            "file_size",
            "file_path",
            "description",
            "quarter",
            "financial_year",
            "created_at",
        ]
        read_only_fields = ["uid", "created_at"]


class ObjectiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Objective
        fields = [
            "uid",
            "title",
            "description",
            "weight",
            "financial_year",
            "status",
            "approval_comment",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["uid", "created_at", "updated_at", "approved_at"]


class TargetListSerializer(serializers.ModelSerializer):
    responsible_officer_id = serializers.IntegerField(required=False, allow_null=True)
    responsible_officer_name = serializers.SerializerMethodField()
    responsible_officer_label = serializers.SerializerMethodField()

    class Meta:
        model = Target
        fields = [
            "uid",
            "objective",
            "title",
            "description",
            "weight",
            "planned_value",
            "kpi_name",
            "kpi_source_type",
            "kpi_unit",
            "kpi_planned_value",
            "kpi_direction",
            "kpi_calculation_method",
            "status",
            "responsible_officer_id",
            "responsible_officer_name",
            "responsible_officer_label",
            "created_at",
        ]

    def get_responsible_officer_name(self, obj):
        officer_id = getattr(obj, "responsible_officer_id", None)
        if not officer_id:
            return None
        User = get_user_model()
        try:
            u = User.objects.using("default").filter(id=officer_id, is_deleted=False).first()
        except Exception:
            u = User.objects.filter(id=officer_id).first()
        if not u:
            return None
        full_name = (getattr(u, "get_full_name", lambda: "")() or "").strip()
        if not full_name:
            full_name = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
        return full_name or getattr(u, "username", None) or str(officer_id)

    def get_responsible_officer_label(self, obj):
        """
        Full display label with name + department + designation,
        e.g. "Jane Doe (ICT Department - Head of ICT)".
        """
        officer_id = getattr(obj, "responsible_officer_id", None)
        if not officer_id:
            return None
        User = get_user_model()
        try:
            u = User.objects.using("default").filter(id=officer_id, is_deleted=False).first()
        except Exception:
            u = User.objects.filter(id=officer_id).first()
        if not u:
            return None

        full_name = (getattr(u, "get_full_name", lambda: "")() or "").strip()
        if not full_name:
            full_name = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
        if not full_name:
            full_name = getattr(u, "username", None) or str(officer_id)

        title = getattr(getattr(u, "position", None), "level_name", "") or ""
        dept = getattr(getattr(u, "department", None), "name", "") or ""
        extra = " - ".join([x for x in [dept, title] if x])
        return f"{full_name}{f' ({extra})' if extra else ''}"


class TargetSerializer(serializers.ModelSerializer):
    objective = serializers.SlugRelatedField(
        slug_field="uid",
        queryset=Objective.objects.filter(is_deleted=False),
        required=True,
    )
    objective_uid = serializers.SerializerMethodField()
    objective_title = serializers.SerializerMethodField()
    objective_status = serializers.SerializerMethodField()
    objective_financial_year = serializers.SerializerMethodField()
    responsible_officer_id = serializers.IntegerField(required=False, allow_null=True)
    responsible_officer_name = serializers.SerializerMethodField()
    responsible_officer_profile = serializers.SerializerMethodField()

    class Meta:
        model = Target
        fields = [
            "uid",
            "objective",
            "objective_uid",
            "objective_title",
            "objective_status",
            "objective_financial_year",
            "title",
            "description",
            "weight",
            "planned_value",
            "kpi_name",
            "kpi_description",
            "kpi_unit",
            "kpi_source_type",
            "kpi_planned_value",
            "kpi_baseline",
            "kpi_direction",
            "kpi_calculation_method",
            "kpi_reporting_frequency",
            "status",
            "approval_comment",
            "responsible_officer_id",
            "responsible_officer_name",
            "responsible_officer_profile",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "uid",
            "created_at",
            "updated_at",
            "approved_at",
            "objective_uid",
            "objective_title",
            "objective_status",
            "objective_financial_year",
            "responsible_officer_name",
            "responsible_officer_profile",
        ]

    def get_objective_uid(self, obj):
        return str(obj.objective.uid) if obj.objective_id else None

    def get_objective_title(self, obj):
        return obj.objective.title if obj.objective_id else None

    def get_objective_status(self, obj):
        return obj.objective.status if obj.objective_id else None

    def get_objective_financial_year(self, obj):
        return obj.objective.financial_year if obj.objective_id else None

    def validate(self, attrs):
        """
        Enforce Direct KPI requirements.
        Activity-driven KPI (DERIVED) doesn't require annual KPI inputs.
        """
        instance = getattr(self, "instance", None)
        source_type = attrs.get("kpi_source_type", getattr(instance, "kpi_source_type", "DERIVED"))
        planned_value = attrs.get("kpi_planned_value", getattr(instance, "kpi_planned_value", None))
        direction = attrs.get("kpi_direction", getattr(instance, "kpi_direction", None))
        calculation_method = attrs.get(
            "kpi_calculation_method",
            getattr(instance, "kpi_calculation_method", None),
        )

        if source_type == "DIRECT":
            errors = {}
            if planned_value in (None, ""):
                errors["kpi_planned_value"] = "Annual KPI target is required for Direct KPI."
            if not direction:
                errors["kpi_direction"] = "KPI direction is required for Direct KPI."
            if not calculation_method:
                errors["kpi_calculation_method"] = "Calculation method is required for Direct KPI."
            if errors:
                raise serializers.ValidationError(errors)

        return attrs

    def get_responsible_officer_name(self, obj):
        officer_id = getattr(obj, "responsible_officer_id", None)
        if not officer_id:
            return None
        User = get_user_model()
        try:
            u = User.objects.using("default").filter(id=officer_id, is_deleted=False).first()
        except Exception:
            u = User.objects.filter(id=officer_id).first()
        if not u:
            return None
        full_name = (getattr(u, "get_full_name", lambda: "")() or "").strip()
        if not full_name:
            full_name = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
        return full_name or getattr(u, "username", None) or str(officer_id)

    def get_responsible_officer_profile(self, obj):
        """
        Return a rich profile for the responsible officer, similar to the internal portal:
        id, guid/uid, username, names, email, groups, and position/department info.
        """
        officer_id = getattr(obj, "responsible_officer_id", None)
        if not officer_id:
            return None
        User = get_user_model()
        try:
            u = User.objects.using("default").filter(id=officer_id, is_deleted=False).first()
        except Exception:
            u = User.objects.filter(id=officer_id).first()
        if not u:
            return None

        username = getattr(u, "username", "") or ""
        first_name = getattr(u, "first_name", "") or ""
        last_name = getattr(u, "last_name", "") or ""
        full_name = (getattr(u, "get_full_name", lambda: "")() or "").strip()
        if not full_name:
            full_name = f"{first_name} {last_name}".strip() or username

        dept_obj = getattr(u, "department", None)
        pos_obj = getattr(u, "position", None)
        dept_uid = getattr(dept_obj, "uid", None)
        dept_name = getattr(dept_obj, "name", "") or getattr(u, "current_department_name", "") or ""
        dept_code = getattr(dept_obj, "code", "") or ""
        level_uid = getattr(pos_obj, "uid", None)
        level_name = (
            getattr(pos_obj, "level_name", "")
            or getattr(pos_obj, "name", "")
            or getattr(u, "current_level_name", "")
            or ""
        )
        level_code = getattr(pos_obj, "code", "") or ""
        groups = list(u.groups.values_list("name", flat=True))

        return {
            "id": u.id,
            "guid": getattr(u, "guid", None) or getattr(u, "uid", None),
            "uid": getattr(u, "uid", None),
            "username": username,
            "email": getattr(u, "email", "") or None,
            "first_name": first_name or None,
            "last_name": last_name or None,
            "full_name": full_name,
            "status": "ACTIVE" if getattr(u, "is_active", False) else "INACTIVE",
            "is_active": getattr(u, "is_active", False),
            "is_staff": getattr(u, "is_staff", False),
            "phone_number": getattr(u, "phone_number", "") or None,
            "alternative_contact": getattr(u, "alternative_contact", "") or None,
            "groups": groups,
            "position": {
                "department_uid": dept_uid,
                "department_name": dept_name or None,
                "department_code": dept_code or None,
                "level_uid": level_uid,
                "level_name": level_name or None,
                "level_code": level_code or None,
            },
            "current_level_name": level_name or None,
            "current_department_name": dept_name or None,
        }

    def validate_responsible_officer_id(self, value):
        """
        Accept either a numeric id or a user uid for the responsible officer.
        Internally we still store the numeric auth_user.id in the performance DB.
        """
        if value in (None, "", 0, "0"):
            return None

        raw = value
        officer_id = None
        officer_uid = None

        # Try to interpret as integer id first
        try:
            officer_id = int(raw)
        except Exception:
            officer_id = None

        User = get_user_model()
        user = None
        # Prefer lookup by id when available
        if officer_id:
            try:
                user = User.objects.using("default").filter(id=officer_id, is_deleted=False).first()
            except Exception:
                user = User.objects.filter(id=officer_id).first()

        # If not found and value looks like a uid, try by uid
        if not user and isinstance(raw, str):
            officer_uid = raw.strip()
            if officer_uid:
                try:
                    user = User.objects.using("default").filter(uid=officer_uid, is_deleted=False).first()
                except Exception:
                    user = User.objects.filter(uid=officer_uid).first()

        if not user:
            raise serializers.ValidationError("Selected responsible officer not found.")
        # Check group membership by name; don't hard-fail if groups not available.
        try:
            if not user.groups.filter(name="SPISM Performance Officer").exists():
                raise serializers.ValidationError("Selected user is not a SPISM Performance Officer.")
        except Exception:
            # If groups table is unavailable, skip the strict check.
            pass

        # Always return the numeric id to be stored in performance DB
        return user.id


class ActivityListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = [
            "uid",
            "target",
            "title",
            "description",
            "weight",
            "planned_value",
            "planned_value_label",
            "planned_financial_year",
            "planned_quarter",
            "planned_quarters",
            "status",
            "created_at",
        ]


class ActivitySerializer(serializers.ModelSerializer):
    target = TargetUidField()
    target_title = serializers.SerializerMethodField()
    target_kpi_source_type = serializers.SerializerMethodField()
    quarterly_summary = serializers.SerializerMethodField()
    planned_quarters = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=4),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Activity
        fields = [
            "uid",
            "target",
            "target_title",
            "target_kpi_source_type",
            "title",
            "description",
            "weight",
            "planned_value",
            "planned_value_label",
            "planned_financial_year",
            "planned_quarter",
            "planned_quarters",
            "quarterly_summary",
            "status",
            "approval_comment",
            "approved_at",
            "implementation_submitted_at",
            "implementation_submitted_by_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "uid", "created_at", "updated_at", "approved_at",
            "target_title", "target_kpi_source_type", "quarterly_summary",
        ]

    def get_target_title(self, obj):
        return obj.target.title if obj.target_id else None

    def get_target_kpi_source_type(self, obj):
        """Return the parent target's KPI source type so consumers can skip KPI actual checks for DERIVED."""
        if obj.target_id:
            return getattr(obj.target, "kpi_source_type", "DERIVED")
        return "DERIVED"

    def get_quarterly_summary(self, obj):
        """Return per-quarter implementation status for this activity."""
        try:
            qs = obj.quarterly_data.all()
        except Exception:
            qs = QuarterlyData.objects.filter(activity=obj)
        return [
            {
                "uid": str(qd.uid),
                "quarter": qd.quarter,
                "financial_year": qd.financial_year,
                "actual_value": str(qd.actual_value),
                "computed_ai_percent": (
                    str(qd.computed_ai_percent) if qd.computed_ai_percent is not None else None
                ),
                "implementation_status": qd.implementation_status,
                "implementation_submitted_at": (
                    qd.implementation_submitted_at.isoformat()
                    if qd.implementation_submitted_at else None
                ),
                "is_locked": qd.is_locked,
            }
            for qd in qs
        ]

    def validate_planned_quarters(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        return [int(q) for q in value if q in (1, 2, 3, 4)]

    def create(self, validated_data):
        target = validated_data.get("target")
        if target and not validated_data.get("planned_financial_year"):
            validated_data["planned_financial_year"] = target.objective.financial_year
        return super().create(validated_data)

    def update(self, instance, validated_data):
        target = validated_data.get("target") or instance.target
        if target and not validated_data.get("planned_financial_year") and not instance.planned_financial_year:
            validated_data["planned_financial_year"] = target.objective.financial_year
        return super().update(instance, validated_data)


class KPIActualSerializer(serializers.ModelSerializer):
    class Meta:
        model = KPIActual
        fields = [
            "uid",
            "target",
            "reporting_period",
            "financial_year",
            "quarter",
            "actual_value",
            "computed_kpi_percent",
            "created_at",
        ]
        read_only_fields = ["uid", "computed_kpi_percent", "created_at"]


class ActivityDocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ActivityDocument
        fields = [
            "uid",
            "activity",
            "file_name",
            "file_type",
            "file_size",
            "file_path",
            "description",
            "quarter",
            "financial_year",
            "download_url",
            "created_at",
        ]
        read_only_fields = ["uid", "download_url", "created_at"]

    def get_download_url(self, obj):
        if not obj.file_path:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(
                f"/api/performance-dashboard/activity-documents/{obj.uid}/download"
            )
        return f"/api/performance-dashboard/activity-documents/{obj.uid}/download"


class PerformanceAuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceAuditLog
        fields = [
            "id",
            "uid",
            "entity_type",
            "entity_id",
            "action",
            "model_name",
            "object_repr",
            "old_value",
            "new_value",
            "comment",
            "user_id",
            "user_name",
            "ip_address",
            "user_agent",
            "timestamp",
        ]
        read_only_fields = ["id", "uid", "timestamp"]

    def get_user_name(self, obj):
        if not obj.user_id:
            return None
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.using("default").filter(pk=obj.user_id).first()
        return user.get_full_name() or user.username if user else None
