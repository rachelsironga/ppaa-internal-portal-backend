from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    SpismActivity,
    SpismActivityDocument,
    SpismFinancialYear,
    SpismKpiActual,
    SpismObjective,
    SpismPerformanceAuditLog,
    SpismQuarterlyData,
    SpismTarget,
)

User = get_user_model()


class SpismFinancialYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpismFinancialYear
        fields = (
            "uid",
            "name",
            "start_date",
            "end_date",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uid", "created_at", "updated_at")


class SpismObjectiveListSerializer(serializers.ModelSerializer):
    targets_count = serializers.SerializerMethodField()

    class Meta:
        model = SpismObjective
        fields = (
            "uid",
            "title",
            "description",
            "weight",
            "financial_year",
            "status",
            "created_at",
            "updated_at",
            "targets_count",
        )

    def get_targets_count(self, obj):
        qs = obj.targets.filter(is_deleted=False)
        if self.context.get("dept_head_targets_scope"):
            req = self.context.get("request")
            if req and getattr(req, "user", None) and req.user.is_authenticated:
                qs = qs.filter(responsible_officer=req.user)
        return qs.count()


class SpismObjectiveSerializer(serializers.ModelSerializer):
    targets_count = serializers.SerializerMethodField()
    description = serializers.CharField(allow_blank=True, allow_null=True, required=False)

    class Meta:
        model = SpismObjective
        fields = (
            "uid",
            "title",
            "description",
            "weight",
            "financial_year",
            "status",
            "created_at",
            "updated_at",
            "targets_count",
        )
        read_only_fields = ("uid", "created_at", "updated_at")

    def validate_description(self, value):
        return "" if value is None else value

    def get_targets_count(self, obj):
        qs = obj.targets.filter(is_deleted=False)
        if self.context.get("dept_head_targets_scope"):
            req = self.context.get("request")
            if req and getattr(req, "user", None) and req.user.is_authenticated:
                qs = qs.filter(responsible_officer=req.user)
        return qs.count()


class SpismTargetSerializer(serializers.ModelSerializer):
    objective_uid = serializers.UUIDField(source="objective.uid", read_only=True)
    objective = serializers.UUIDField(required=False)
    description = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    responsible_officer = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = SpismTarget
        fields = (
            "uid",
            "objective",
            "objective_uid",
            "title",
            "description",
            "weight",
            "planned_value",
            "responsible_officer",
            "kpi_name",
            "kpi_source_type",
            "kpi_unit",
            "kpi_planned_value",
            "kpi_direction",
            "kpi_calculation_method",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uid", "objective_uid", "created_at", "updated_at")

    def validate_description(self, value):
        return "" if value is None else value

    def _resolve_objective(self, uid):
        if uid is None:
            return None
        return SpismObjective.objects.filter(uid=uid, is_deleted=False).first()

    def create(self, validated_data):
        ouid = validated_data.pop("objective", None)
        obj = self._resolve_objective(ouid)
        if not obj:
            raise serializers.ValidationError({"objective": "Valid objective is required"})
        validated_data["objective"] = obj
        return super().create(validated_data)

    def update(self, instance, validated_data):
        ouid = validated_data.pop("objective", None)
        if ouid is not None:
            obj = self._resolve_objective(ouid)
            if not obj:
                raise serializers.ValidationError({"objective": "Invalid objective"})
            validated_data["objective"] = obj
        return super().update(instance, validated_data)

    def to_internal_value(self, data):
        if isinstance(data, dict) and "responsible_officer_id" in data and "responsible_officer" not in data:
            data = {**data, "responsible_officer": data.get("responsible_officer_id")}
        return super().to_internal_value(data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        o = instance.objective
        data["objective"] = str(o.uid)
        data["objective_status"] = o.status
        data["objective_title"] = o.title
        data["objective_description"] = o.description or ""
        data["objective_financial_year"] = o.financial_year
        data["objective_weight"] = o.weight
        ro = instance.responsible_officer
        data["responsible_officer_id"] = ro.pk if ro else None
        data.pop("responsible_officer", None)
        if ro:
            name = f"{ro.first_name} {ro.last_name}".strip() or ro.username
            data["responsible_officer_name"] = name
            data["responsible_officer_label"] = name
            pos = ro.get_position() if hasattr(ro, "get_position") else {}
            data["responsible_officer_designation"] = (pos or {}).get("level_name") or None
        else:
            data["responsible_officer_name"] = None
            data["responsible_officer_label"] = None
            data["responsible_officer_designation"] = None
        return data


class SpismActivitySerializer(serializers.ModelSerializer):
    target = serializers.UUIDField(required=False)
    description = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    planned_financial_year = serializers.CharField(
        max_length=32, required=False, allow_blank=True, allow_null=True
    )
    target_uid = serializers.SerializerMethodField()
    target_title = serializers.SerializerMethodField()
    objective_title = serializers.SerializerMethodField()
    target_kpi_source_type = serializers.SerializerMethodField()
    quarterly_data_count = serializers.SerializerMethodField()
    documents_count = serializers.SerializerMethodField()
    pending_implementation_approval_count = serializers.SerializerMethodField()
    implementation_review_status = serializers.SerializerMethodField()

    class Meta:
        model = SpismActivity
        fields = (
            "uid",
            "target",
            "target_uid",
            "target_title",
            "objective_title",
            "target_kpi_source_type",
            "title",
            "description",
            "weight",
            "planned_value",
            "planned_value_label",
            "planned_financial_year",
            "planned_quarters",
            "planned_quarter",
            "status",
            "approval_comment",
            "implementation_submitted_at",
            "implementation_quarters_state",
            "pending_implementation_approval_count",
            "implementation_review_status",
            "created_at",
            "updated_at",
            "quarterly_data_count",
            "documents_count",
        )
        read_only_fields = (
            "uid",
            "target_uid",
            "target_title",
            "objective_title",
            "target_kpi_source_type",
            "approval_comment",
            "implementation_submitted_at",
            "implementation_quarters_state",
            "pending_implementation_approval_count",
            "implementation_review_status",
            "created_at",
            "updated_at",
            "quarterly_data_count",
            "documents_count",
        )

    planned_quarter = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    def validate_description(self, value):
        return "" if value is None else value

    def _resolve_target(self, uid):
        if uid is None:
            return None
        return (
            SpismTarget.objects.filter(uid=uid, is_deleted=False)
            .select_related("objective")
            .first()
        )

    def _default_planned_financial_year(self, target, value):
        if value is None:
            return target.objective.financial_year
        if isinstance(value, str) and not value.strip():
            return target.objective.financial_year
        return value.strip() if isinstance(value, str) else value

    def create(self, validated_data):
        tuid = validated_data.pop("target", None)
        tr = self._resolve_target(tuid)
        if not tr:
            raise serializers.ValidationError({"target": "Valid target is required"})
        pq_one = validated_data.pop("planned_quarter", None)
        pqs = validated_data.get("planned_quarters")
        if not pqs and pq_one is not None:
            validated_data["planned_quarters"] = [int(pq_one)]
        validated_data["target"] = tr
        validated_data["planned_financial_year"] = self._default_planned_financial_year(
            tr, validated_data.get("planned_financial_year")
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("planned_quarter", None)
        tuid = validated_data.pop("target", None)
        if tuid is not None:
            tr = self._resolve_target(tuid)
            if not tr:
                raise serializers.ValidationError({"target": "Invalid target"})
            validated_data["target"] = tr
        resolved_target = validated_data.get("target", instance.target)
        if "planned_financial_year" in validated_data:
            validated_data["planned_financial_year"] = self._default_planned_financial_year(
                resolved_target, validated_data.get("planned_financial_year")
            )
        inst = super().update(instance, validated_data)
        if validated_data.get("status") == SpismActivity.Status.PENDING:
            SpismActivity.objects.filter(pk=inst.pk).update(approval_comment="")
            inst.refresh_from_db()
        return inst

    def get_target_uid(self, obj):
        t = getattr(obj, "target", None)
        return str(t.uid) if t else None

    def get_target_title(self, obj):
        t = getattr(obj, "target", None)
        return getattr(t, "title", None) if t else None

    def get_objective_title(self, obj):
        t = getattr(obj, "target", None)
        if not t:
            return None
        o = getattr(t, "objective", None)
        return getattr(o, "title", None) if o else None

    def get_target_kpi_source_type(self, obj):
        t = getattr(obj, "target", None)
        if not t:
            return "DERIVED"
        return t.kpi_source_type or "DERIVED"

    def get_quarterly_data_count(self, obj):
        return obj.quarterly_rows.filter(is_deleted=False).count()

    def get_documents_count(self, obj):
        return obj.documents.filter(is_deleted=False).count()

    @staticmethod
    def _implementation_pending_count(obj):
        st = obj.implementation_quarters_state or {}
        if not isinstance(st, dict):
            st = {}
        n = 0
        for k, v in st.items():
            if not isinstance(v, dict):
                continue
            if str(v.get("status", "")).upper() != "PENDING":
                continue
            ks = str(k)
            if ks == "all" or (ks.isdigit() and 1 <= int(ks) <= 4):
                n += 1
        if n == 0 and obj.implementation_submitted_at:
            all_e = st.get("all")
            if isinstance(all_e, dict) and str(all_e.get("status", "")).upper() in (
                "APPROVED",
                "RETURNED",
            ):
                return 0
            if not st:
                return 1
        return n

    def get_pending_implementation_approval_count(self, obj):
        return self._implementation_pending_count(obj)

    def get_implementation_review_status(self, obj):
        if self._implementation_pending_count(obj) > 0:
            return "PENDING_APPROVAL"
        st = obj.implementation_quarters_state or {}
        if not isinstance(st, dict):
            st = {}
        if any(
            isinstance(v, dict) and str(v.get("status", "")).upper() == "APPROVED"
            for v in st.values()
        ):
            return "APPROVED"
        if obj.implementation_submitted_at:
            all_e = st.get("all")
            if isinstance(all_e, dict) and str(all_e.get("status", "")).upper() == "APPROVED":
                return "APPROVED"
            if not st:
                return "PENDING_APPROVAL"
        return "IN_PROGRESS"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        t = getattr(instance, "target", None)
        data["target"] = str(t.uid) if t else None
        pq = instance.planned_quarters or []
        data["planned_quarters"] = pq if isinstance(pq, list) else []
        st = instance.implementation_quarters_state or {}
        data["implementation_quarters_state"] = st if isinstance(st, dict) else {}
        return data


class SpismQuarterlyDataSerializer(serializers.ModelSerializer):
    """Activity is set by the list/create view via save(activity=...), not from validated body."""

    class Meta:
        model = SpismQuarterlyData
        fields = (
            "uid",
            "quarter",
            "financial_year",
            "actual_value",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uid", "created_at", "updated_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["activity"] = str(instance.activity.uid)
        return data


class SpismKpiActualSerializer(serializers.ModelSerializer):
    target = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = SpismKpiActual
        fields = (
            "uid",
            "target",
            "financial_year",
            "reporting_period",
            "actual_value",
            "computed_kpi_percent",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uid", "computed_kpi_percent", "created_at", "updated_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["target"] = str(instance.target.uid)
        return data


class SpismActivityDocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    file_name = serializers.CharField(source="original_filename", read_only=True)

    class Meta:
        model = SpismActivityDocument
        fields = (
            "uid",
            "activity",
            "file_key",
            "file_name",
            "original_filename",
            "file_size",
            "mime_type",
            "description",
            "quarter",
            "financial_year",
            "download_url",
            "created_at",
        )
        read_only_fields = (
            "uid",
            "file_key",
            "original_filename",
            "download_url",
            "created_at",
        )

    def get_download_url(self, obj):
        request = self.context.get("request")
        if not request:
            return f"/api/performance-dashboard/activity-documents/{obj.uid}/download/"
        return request.build_absolute_uri(
            f"/api/performance-dashboard/activity-documents/{obj.uid}/download/"
        )


class SpismAuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SpismPerformanceAuditLog
        fields = (
            "uid",
            "entity_type",
            "entity_uid",
            "action",
            "comment",
            "payload",
            "created_at",
            "user_name",
            "created_by_name",
        )

    def get_user_name(self, obj):
        u = obj.actor
        if not u:
            return None
        return f"{u.first_name} {u.last_name}".strip() or u.username

    def get_created_by_name(self, obj):
        return self.get_user_name(obj)
