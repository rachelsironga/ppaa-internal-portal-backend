"""REST API for SPISM (objectives, targets, activities, documents, KPIs, approvals)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .spism_permissions import (
    SpismAuditLogConversationPermission,
    SpismProtectedAPIView,
    spism_dept_head_targets_scope_only,
)

from .models import (
    SpismActivity,
    SpismActivityDocument,
    SpismKpiActual,
    SpismObjective,
    SpismPerformanceAuditLog,
    SpismQuarterlyData,
    SpismTarget,
)
from .serializers import (
    SpismActivityDocumentSerializer,
    SpismActivitySerializer,
    SpismAuditLogSerializer,
    SpismKpiActualSerializer,
    SpismObjectiveListSerializer,
    SpismObjectiveSerializer,
    SpismQuarterlyDataSerializer,
    SpismTargetSerializer,
)
from .spism_common import (
    apply_search_filter,
    paginated_queryset,
    parse_filters_param,
    to_decimal,
)
from ppaa_portal.internal_portal_views import (
    _attachment_content_disposition,
    _store_uploaded_data_url,
)
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from django.contrib.auth import get_user_model

User = get_user_model()


def _dept_head_scope_denies_target(request, target) -> bool:
    """True when dept-head scope applies and this target is not assigned to the current user."""
    if not spism_dept_head_targets_scope_only(request.user):
        return False
    if target is None:
        return True
    ro = getattr(target, "responsible_officer_id", None)
    return ro is None or ro != request.user.id


def _dept_head_scope_denies_activity(request, activity) -> bool:
    if not spism_dept_head_targets_scope_only(request.user):
        return False
    if activity is None:
        return True
    t = getattr(activity, "target", None)
    return _dept_head_scope_denies_target(request, t)


def _dept_head_scope_denies_objective(request, objective) -> bool:
    if not spism_dept_head_targets_scope_only(request.user):
        return False
    if objective is None:
        return True
    return not objective.targets.filter(is_deleted=False, responsible_officer=request.user).exists()


def _audit(request, entity_type: str, entity_uid, action: str, comment: str = "", payload=None):
    SpismPerformanceAuditLog.objects.create(
        entity_type=entity_type,
        entity_uid=entity_uid if isinstance(entity_uid, uuid.UUID) else uuid.UUID(str(entity_uid)),
        action=action.upper(),
        comment=comment or "",
        payload=payload or {},
        actor=request.user if request.user.is_authenticated else None,
        created_by=request.user if request.user.is_authenticated else None,
        updated_by=request.user if request.user.is_authenticated else None,
    )


# --- Objectives ---


class SpismObjectiveListCreateView(SpismProtectedAPIView):
    spism_perm_map = {
        "GET": ("can_view_spism_objective",),
        "POST": ("can_add_spism_objective",),
    }

    def get(self, request):
        qs = SpismObjective.objects.filter(is_deleted=False)
        qs = apply_search_filter(qs, request, "title", "description", "financial_year")
        fy = (request.GET.get("financial_year") or "").strip()
        if fy:
            qs = qs.filter(financial_year=fy)
        st = (request.GET.get("status") or "").strip()
        if st:
            qs = qs.filter(status=st)
        flt = parse_filters_param(request)
        if flt and "ALL" not in [x.upper() for x in flt]:
            qs = qs.filter(status__in=flt)
        if spism_dept_head_targets_scope_only(request.user):
            qs = qs.filter(
                Exists(
                    SpismTarget.objects.filter(
                        objective_id=OuterRef("pk"),
                        is_deleted=False,
                        responsible_officer=request.user,
                    )
                )
            )
        qs = qs.order_by("-created_at")
        ctx = {"request": request}
        if spism_dept_head_targets_scope_only(request.user):
            ctx["dept_head_targets_scope"] = True
        return paginated_queryset(qs, request, SpismObjectiveListSerializer, context_extra=ctx)

    def post(self, request):
        if spism_dept_head_targets_scope_only(request.user):
            return CustomResponse.forbidden(
                message="Only planning staff can create strategic objectives."
            )
        ser = SpismObjectiveSerializer(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed", data=ser.errors, code=STATUS_CODES["VALIDATION_ERROR"]
            )
        obj = ser.save(created_by=request.user, updated_by=request.user)
        return CustomResponse.success(
            data=SpismObjectiveSerializer(obj, context={"request": request}).data, message="Created"
        )


class SpismObjectiveDetailView(SpismProtectedAPIView):
    spism_perm_map = {
        "GET": ("can_view_spism_objective",),
        "PUT": ("can_edit_spism_objective",),
        "DELETE": ("can_delete_spism_objective",),
    }

    def get(self, request, uid):
        row = SpismObjective.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_objective(request, row):
            return CustomResponse.forbidden(
                message="You do not have access to this objective. It has no targets assigned to you."
            )
        ctx = {"request": request}
        if spism_dept_head_targets_scope_only(request.user):
            ctx["dept_head_targets_scope"] = True
        return CustomResponse.success(data=SpismObjectiveSerializer(row, context=ctx).data)

    def put(self, request, uid):
        row = SpismObjective.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_objective(request, row):
            return CustomResponse.forbidden(message="You do not have access to this objective.")
        ser = SpismObjectiveSerializer(row, data=request.data, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed", data=ser.errors, code=STATUS_CODES["VALIDATION_ERROR"]
            )
        ser.save(updated_by=request.user)
        ctx = {"request": request}
        if spism_dept_head_targets_scope_only(request.user):
            ctx["dept_head_targets_scope"] = True
        return CustomResponse.success(data=SpismObjectiveSerializer(row, context=ctx).data, message="Updated")

    def delete(self, request, uid):
        row = SpismObjective.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_objective(request, row):
            return CustomResponse.forbidden(message="You do not have access to this objective.")
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class SpismObjectiveSubmitPackageView(SpismProtectedAPIView):
    spism_perm_map = {"POST": ("can_edit_spism_objective",)}

    def post(self, request, uid):
        obj = SpismObjective.objects.filter(uid=uid, is_deleted=False).first()
        if not obj:
            return CustomResponse.errors(message="Objective not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if spism_dept_head_targets_scope_only(request.user):
            return CustomResponse.forbidden(
                message="Only planning staff can submit an objective package for institutional approval."
            )
        targets = list(obj.targets.filter(is_deleted=False))
        if not targets:
            return CustomResponse.errors(
                message="Add at least one target before submitting the package.",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        total = sum((to_decimal(t.weight, Decimal("0")) or Decimal("0")) for t in targets)
        if total > Decimal("100.01"):
            return CustomResponse.errors(
                message=f"Total target weight is {total}%; must not exceed 100%.",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        with transaction.atomic():
            obj.status = SpismObjective.Status.PENDING
            obj.save(update_fields=["status", "updated_at", "updated_by"])
            for t in targets:
                if t.status in (SpismTarget.Status.DRAFT, SpismTarget.Status.RETURNED):
                    t.status = SpismTarget.Status.PENDING
                    t.updated_by = request.user
                    t.save(update_fields=["status", "updated_at", "updated_by"])
            _audit(request, "objective", obj.uid, "SUBMIT_PACKAGE", "Package submitted")
        return CustomResponse.success(
            data=SpismObjectiveSerializer(obj, context={"request": request}).data,
            message="Package submitted for approval",
        )


class SpismObjectiveApprovalView(SpismProtectedAPIView):
    spism_perm_map = {"POST": ("can_approve_spism_planning",)}

    def post(self, request, uid):
        obj = SpismObjective.objects.filter(uid=uid, is_deleted=False).first()
        if not obj:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if spism_dept_head_targets_scope_only(request.user):
            return CustomResponse.forbidden(
                message="Only planning or approval roles can approve or return objective packages."
            )
        action = (request.data.get("action") or "").lower()
        comment = (request.data.get("comment") or "").strip()
        if action == "return" and not comment:
            return CustomResponse.errors(
                message="comment is required for return", code=STATUS_CODES["VALIDATION_ERROR"]
            )
        if action == "approve":
            obj.status = SpismObjective.Status.APPROVED
        elif action == "return":
            obj.status = SpismObjective.Status.RETURNED
        else:
            return CustomResponse.errors(message="Invalid action", code=STATUS_CODES["VALIDATION_ERROR"])
        obj.updated_by = request.user
        obj.save(update_fields=["status", "updated_at", "updated_by"])
        _audit(request, "objective", obj.uid, action.upper(), comment)
        return CustomResponse.success(
            data=SpismObjectiveSerializer(obj, context={"request": request}).data, message="OK"
        )


# --- Targets ---


class SpismTargetListCreateView(SpismProtectedAPIView):
    spism_perm_map = {
        "GET": ("can_view_spism_target",),
        "POST": ("can_add_spism_target",),
    }

    def get(self, request):
        qs = SpismTarget.objects.filter(is_deleted=False).select_related("objective", "responsible_officer")
        ouid = (request.GET.get("objective") or "").strip()
        if ouid:
            qs = qs.filter(objective__uid=ouid)
        fy = (request.GET.get("financial_year") or "").strip()
        if fy:
            qs = qs.filter(objective__financial_year=fy)
        assigned_me = str(request.GET.get("assigned_to_me", "")).lower() in ("1", "true", "yes")
        if assigned_me or spism_dept_head_targets_scope_only(request.user):
            qs = qs.filter(responsible_officer=request.user)
        qs = apply_search_filter(qs, request, "title", "description")
        return paginated_queryset(qs, request, SpismTargetSerializer)

    def post(self, request):
        if spism_dept_head_targets_scope_only(request.user):
            return CustomResponse.forbidden(message="Only planning staff can create targets.")
        ser = SpismTargetSerializer(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed", data=ser.errors, code=STATUS_CODES["VALIDATION_ERROR"]
            )
        t = ser.save(created_by=request.user, updated_by=request.user)
        return CustomResponse.success(
            data=SpismTargetSerializer(t, context={"request": request}).data, message="Created"
        )


class SpismTargetDetailView(SpismProtectedAPIView):
    spism_perm_map = {
        "GET": ("can_view_spism_target",),
        "PUT": ("can_edit_spism_target",),
        "DELETE": ("can_delete_spism_target",),
    }

    def get(self, request, uid):
        row = (
            SpismTarget.objects.filter(uid=uid, is_deleted=False)
            .select_related("objective", "responsible_officer")
            .first()
        )
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_target(request, row):
            return CustomResponse.forbidden(
                message="You do not have access to this target. It is not assigned to you as responsible officer."
            )
        return CustomResponse.success(data=SpismTargetSerializer(row, context={"request": request}).data)

    def put(self, request, uid):
        row = SpismTarget.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_target(request, row):
            return CustomResponse.forbidden(message="You do not have access to this target.")
        ser = SpismTargetSerializer(row, data=request.data, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed", data=ser.errors, code=STATUS_CODES["VALIDATION_ERROR"]
            )
        if spism_dept_head_targets_scope_only(request.user):
            if "responsible_officer" in ser.validated_data:
                new_ro = ser.validated_data["responsible_officer"]
                if new_ro is None or new_ro.pk != request.user.pk:
                    return CustomResponse.forbidden(
                        message="You cannot change the responsible officer on this target."
                    )
        ser.save(updated_by=request.user)
        return CustomResponse.success(
            data=SpismTargetSerializer(row, context={"request": request}).data, message="Updated"
        )

    def delete(self, request, uid):
        row = SpismTarget.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_target(request, row):
            return CustomResponse.forbidden(message="You do not have access to this target.")
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class SpismTargetAssignOfficerView(SpismProtectedAPIView):
    spism_perm_map = {"POST": ("can_edit_spism_target",)}

    def post(self, request, uid):
        if spism_dept_head_targets_scope_only(request.user):
            return CustomResponse.forbidden(
                message="Only planning staff can change the responsible officer on a target."
            )
        row = SpismTarget.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        rid = request.data.get("responsible_officer_id")
        if rid is None:
            return CustomResponse.errors(
                message="responsible_officer_id required", code=STATUS_CODES["VALIDATION_ERROR"]
            )
        u = User.objects.filter(pk=rid, is_active=True).first()
        if not u:
            return CustomResponse.errors(message="User not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        row.responsible_officer = u
        row.updated_by = request.user
        row.save(update_fields=["responsible_officer", "updated_at", "updated_by"])
        return CustomResponse.success(data=SpismTargetSerializer(row, context={"request": request}).data)


class SpismTargetApprovalView(SpismProtectedAPIView):
    spism_perm_map = {"POST": ("can_approve_spism_planning",)}

    def post(self, request, uid):
        row = SpismTarget.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if spism_dept_head_targets_scope_only(request.user):
            return CustomResponse.forbidden(
                message="Only planning or approval roles can approve or return targets."
            )
        action = (request.data.get("action") or "").lower()
        comment = (request.data.get("comment") or "").strip()
        if action == "return" and not comment:
            return CustomResponse.errors(
                message="comment is required", code=STATUS_CODES["VALIDATION_ERROR"]
            )
        if action == "approve":
            row.status = SpismTarget.Status.APPROVED
        elif action == "return":
            row.status = SpismTarget.Status.RETURNED
        else:
            return CustomResponse.errors(message="Invalid action", code=STATUS_CODES["VALIDATION_ERROR"])
        row.updated_by = request.user
        row.save(update_fields=["status", "updated_at", "updated_by"])
        _audit(request, "target", row.uid, action.upper(), comment)
        return CustomResponse.success(data=SpismTargetSerializer(row, context={"request": request}).data)


# --- Activities ---


class SpismActivityListCreateView(SpismProtectedAPIView):
    spism_perm_map = {
        "GET": ("can_view_spism_activity",),
        "POST": ("can_add_spism_activity",),
    }

    def get(self, request):
        qs = SpismActivity.objects.filter(is_deleted=False).select_related(
            "target", "target__objective"
        )
        tuid = (request.GET.get("target") or "").strip()
        if tuid:
            qs = qs.filter(target__uid=tuid)
        if spism_dept_head_targets_scope_only(request.user):
            qs = qs.filter(target__responsible_officer=request.user)
        qs = apply_search_filter(qs, request, "title", "description")
        return paginated_queryset(qs, request, SpismActivitySerializer)

    def post(self, request):
        ser = SpismActivitySerializer(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed", data=ser.errors, code=STATUS_CODES["VALIDATION_ERROR"]
            )
        tuid = ser.validated_data.get("target")
        t = SpismTarget.objects.filter(uid=tuid, is_deleted=False).first()
        if not t:
            return CustomResponse.errors(message="Target not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_target(request, t):
            return CustomResponse.forbidden(
                message="You can only create activities for targets assigned to you."
            )
        a = ser.save(created_by=request.user, updated_by=request.user)
        return CustomResponse.success(
            data=SpismActivitySerializer(a, context={"request": request}).data, message="Created"
        )


class SpismActivityDetailView(SpismProtectedAPIView):
    spism_perm_map = {
        "GET": ("can_view_spism_activity",),
        "PUT": ("can_edit_spism_activity",),
        "DELETE": ("can_delete_spism_activity",),
    }

    def get(self, request, uid):
        row = (
            SpismActivity.objects.filter(uid=uid, is_deleted=False)
            .select_related("target", "target__objective")
            .first()
        )
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_activity(request, row):
            return CustomResponse.forbidden(
                message="You do not have access to this activity. It belongs to a target not assigned to you."
            )
        return CustomResponse.success(data=SpismActivitySerializer(row, context={"request": request}).data)

    def put(self, request, uid):
        row = SpismActivity.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_activity(request, row):
            return CustomResponse.forbidden(message="You do not have access to this activity.")
        ser = SpismActivitySerializer(row, data=request.data, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed", data=ser.errors, code=STATUS_CODES["VALIDATION_ERROR"]
            )
        if "target" in ser.validated_data:
            ntuid = ser.validated_data["target"]
            nt = SpismTarget.objects.filter(uid=ntuid, is_deleted=False).first()
            if _dept_head_scope_denies_target(request, nt):
                return CustomResponse.forbidden(
                    message="You cannot move this activity to a target that is not assigned to you."
                )
        ser.save(updated_by=request.user)
        return CustomResponse.success(
            data=SpismActivitySerializer(row, context={"request": request}).data, message="Updated"
        )

    def delete(self, request, uid):
        row = SpismActivity.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_activity(request, row):
            return CustomResponse.forbidden(message="You do not have access to this activity.")
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class SpismActivityApprovalView(SpismProtectedAPIView):
    spism_perm_map = {"POST": ("can_approve_spism_planning",)}

    def post(self, request, uid):
        row = SpismActivity.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if spism_dept_head_targets_scope_only(request.user):
            return CustomResponse.forbidden(
                message="Only planning or approval roles can approve or return activities."
            )
        action = (request.data.get("action") or "").lower()
        comment = (request.data.get("comment") or "").strip()
        if action == "return" and not comment:
            return CustomResponse.errors(
                message="comment is required", code=STATUS_CODES["VALIDATION_ERROR"]
            )
        if action == "approve":
            row.status = SpismActivity.Status.APPROVED
            row.approval_comment = ""
        elif action == "return":
            row.status = SpismActivity.Status.RETURNED
            row.approval_comment = comment
        else:
            return CustomResponse.errors(message="Invalid action", code=STATUS_CODES["VALIDATION_ERROR"])
        row.updated_by = request.user
        row.save(update_fields=["status", "updated_at", "updated_by", "approval_comment"])
        _audit(request, "activity", row.uid, action.upper(), comment)
        return CustomResponse.success(data=SpismActivitySerializer(row, context={"request": request}).data)


class SpismActivityImplementationApprovalView(SpismProtectedAPIView):
    spism_perm_map = {"POST": ("can_approve_spism_implementation",)}

    def post(self, request, uid):
        row = SpismActivity.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if spism_dept_head_targets_scope_only(request.user):
            return CustomResponse.forbidden(
                message="Only implementation approval roles can review implementation submissions."
            )
        action = (request.data.get("action") or "").lower()
        comment = (request.data.get("comment") or "").strip()
        quarter = request.data.get("quarter")
        if action == "return" and not comment:
            return CustomResponse.errors(
                message="comment is required", code=STATUS_CODES["VALIDATION_ERROR"]
            )
        st = row.implementation_quarters_state or {}
        if not isinstance(st, dict):
            st = {}

        def _apply_decision(base_entry):
            entry = dict(base_entry) if isinstance(base_entry, dict) else {}
            if action == "approve":
                entry["status"] = "APPROVED"
            elif action == "return":
                entry["status"] = "RETURNED"
            else:
                return None
            entry["comment"] = comment
            return entry

        if quarter is not None and str(quarter) not in ("", "all"):
            qkey = str(int(quarter))
            new_e = _apply_decision(st.get(qkey, {}))
            if new_e is None:
                return CustomResponse.errors(message="Invalid action", code=STATUS_CODES["VALIDATION_ERROR"])
            st[qkey] = new_e
        else:
            pending_keys = [
                k
                for k, v in st.items()
                if isinstance(v, dict)
                and str(v.get("status", "")).upper() == "PENDING"
                and (k == "all" or (str(k).isdigit() and 1 <= int(k) <= 4))
            ]
            if pending_keys:
                for k in pending_keys:
                    new_e = _apply_decision(st.get(k, {}))
                    if new_e is None:
                        return CustomResponse.errors(message="Invalid action", code=STATUS_CODES["VALIDATION_ERROR"])
                    st[k] = new_e
            elif row.implementation_submitted_at:
                new_e = _apply_decision(st.get("all", {}))
                if new_e is None:
                    return CustomResponse.errors(message="Invalid action", code=STATUS_CODES["VALIDATION_ERROR"])
                st["all"] = new_e
            else:
                return CustomResponse.errors(
                    message="No pending implementation submission to review",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        row.implementation_quarters_state = st
        row.updated_by = request.user
        row.save(update_fields=["implementation_quarters_state", "updated_at", "updated_by"])
        _audit(request, "activity", row.uid, f"IMPL_{action.upper()}", comment, {"quarter": quarter})
        return CustomResponse.success(data=SpismActivitySerializer(row, context={"request": request}).data)


class SpismActivitySubmitImplementationView(SpismProtectedAPIView):
    spism_perm_map = {"POST": ("can_edit_spism_activity",)}

    def post(self, request, uid):
        row = SpismActivity.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_activity(request, row):
            return CustomResponse.forbidden(message="You do not have access to this activity.")
        quarter = request.data.get("quarter")
        st = row.implementation_quarters_state or {}
        if not isinstance(st, dict):
            st = {}
        if quarter is not None and str(quarter) not in ("", "all"):
            qk = str(int(quarter))
            st[qk] = {"status": "PENDING", "submitted_at": timezone.now().isoformat()}
        else:
            row.implementation_submitted_at = timezone.now()
        row.implementation_quarters_state = st
        row.updated_by = request.user
        row.save(
            update_fields=[
                "implementation_quarters_state",
                "implementation_submitted_at",
                "updated_at",
                "updated_by",
            ]
        )
        _audit(request, "activity", row.uid, "SUBMIT_IMPLEMENTATION", "", {"quarter": quarter})
        return CustomResponse.success(data=SpismActivitySerializer(row, context={"request": request}).data)


# --- Quarterly & KPI ---


class SpismQuarterlyDataListCreateView(SpismProtectedAPIView):
    spism_perm_map = {
        "GET": ("can_view_spism_implementation", "can_view_spism_activity"),
        "POST": ("can_add_spism_quarterly_data",),
    }

    def get(self, request):
        qs = SpismQuarterlyData.objects.filter(is_deleted=False).select_related(
            "activity", "activity__target"
        )
        au = (request.GET.get("activity") or "").strip()
        if au:
            qs = qs.filter(activity__uid=au)
        fy = (request.GET.get("financial_year") or "").strip()
        if fy:
            qs = qs.filter(financial_year=fy)
        if spism_dept_head_targets_scope_only(request.user):
            qs = qs.filter(activity__target__responsible_officer=request.user)
        return paginated_queryset(qs, request, SpismQuarterlyDataSerializer)

    def post(self, request):
        data = {k: v for k, v in request.data.items()}
        act_uid = data.get("activity") or data.get("activity_id")
        act = SpismActivity.objects.filter(uid=act_uid, is_deleted=False).select_related("target").first()
        if not act:
            return CustomResponse.errors(message="Activity not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_activity(request, act):
            return CustomResponse.forbidden(
                message="You can only add quarterly data for activities on targets assigned to you."
            )
        data.pop("activity", None)
        data.pop("activity_id", None)
        ser = SpismQuarterlyDataSerializer(data=data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed", data=ser.errors, code=STATUS_CODES["VALIDATION_ERROR"]
            )
        row = ser.save(activity=act, created_by=request.user, updated_by=request.user)
        return CustomResponse.success(
            data=SpismQuarterlyDataSerializer(row, context={"request": request}).data, message="Created"
        )


class SpismQuarterlyDataDetailView(SpismProtectedAPIView):
    spism_perm_map = {"PUT": ("can_edit_spism_quarterly_data",)}

    def put(self, request, uid):
        row = (
            SpismQuarterlyData.objects.filter(uid=uid, is_deleted=False)
            .select_related("activity", "activity__target")
            .first()
        )
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_activity(request, row.activity):
            return CustomResponse.forbidden(message="You do not have access to this quarterly record.")
        data = {k: v for k, v in request.data.items()}
        data.pop("activity", None)
        data.pop("activity_id", None)
        ser = SpismQuarterlyDataSerializer(row, data=data, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed", data=ser.errors, code=STATUS_CODES["VALIDATION_ERROR"]
            )
        ser.save(updated_by=request.user)
        return CustomResponse.success(
            data=SpismQuarterlyDataSerializer(row, context={"request": request}).data, message="Updated"
        )


class SpismKpiActualListCreateView(SpismProtectedAPIView):
    spism_perm_map = {
        "GET": ("can_view_spism_kpi_actual",),
        # POST upserts actuals — allow add or edit codename.
        "POST": ("can_add_spism_kpi_actual", "can_edit_spism_kpi_actual"),
    }

    def get(self, request):
        qs = SpismKpiActual.objects.filter(is_deleted=False).select_related("target")
        tu = (request.GET.get("target") or "").strip()
        if tu:
            qs = qs.filter(target__uid=tu)
        fy = (request.GET.get("financial_year") or "").strip()
        if fy:
            qs = qs.filter(financial_year=fy)
        if spism_dept_head_targets_scope_only(request.user):
            qs = qs.filter(target__responsible_officer=request.user)
        return paginated_queryset(qs, request, SpismKpiActualSerializer)

    def post(self, request):
        data = dict(request.data)
        tuid = data.get("target")
        tgt = SpismTarget.objects.filter(uid=tuid, is_deleted=False).first()
        if not tgt:
            return CustomResponse.errors(message="Target not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_target(request, tgt):
            return CustomResponse.forbidden(
                message="You can only record KPI actuals for targets assigned to you."
            )
        fy = (data.get("financial_year") or "").strip()
        if not fy:
            return CustomResponse.errors(
                message="financial_year is required", code=STATUS_CODES["VALIDATION_ERROR"]
            )
        actual = to_decimal(data.get("actual_value"))
        if actual is None:
            return CustomResponse.errors(
                message="actual_value required", code=STATUS_CODES["VALIDATION_ERROR"]
            )
        planned = tgt.kpi_planned_value
        pct = None
        if planned and planned > 0:
            pct = (actual / planned) * Decimal("100")
        row = SpismKpiActual.objects.filter(target=tgt, financial_year=fy).first()
        if row:
            row.actual_value = actual
            row.reporting_period = data.get("reporting_period") or row.reporting_period
            row.computed_kpi_percent = pct
            row.updated_by = request.user
            row.save()
        else:
            row = SpismKpiActual.objects.create(
                target=tgt,
                financial_year=fy[:32],
                reporting_period=(data.get("reporting_period") or "")[:128],
                actual_value=actual,
                computed_kpi_percent=pct,
                created_by=request.user,
                updated_by=request.user,
            )
        return CustomResponse.success(
            data=SpismKpiActualSerializer(row, context={"request": request}).data, message="Saved"
        )


class SpismKpiActualDetailView(SpismProtectedAPIView):
    spism_perm_map = {"PUT": ("can_edit_spism_kpi_actual",)}

    def put(self, request, uid):
        row = SpismKpiActual.objects.filter(uid=uid, is_deleted=False).select_related("target").first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_target(request, row.target):
            return CustomResponse.forbidden(message="You do not have access to this KPI actual.")
        data = dict(request.data)
        actual = to_decimal(data.get("actual_value"), row.actual_value)
        row.actual_value = actual
        if "reporting_period" in data:
            row.reporting_period = data.get("reporting_period") or ""
        planned = row.target.kpi_planned_value
        if planned and planned > 0:
            row.computed_kpi_percent = (actual / planned) * Decimal("100")
        row.updated_by = request.user
        row.save()
        return CustomResponse.success(
            data=SpismKpiActualSerializer(row, context={"request": request}).data, message="Updated"
        )


# --- Activity documents ---


class SpismActivityDocumentListCreateView(SpismProtectedAPIView):
    spism_perm_map = {
        "GET": ("can_view_spism_activity",),
        "POST": ("can_add_spism_supporting_document",),
    }

    def get(self, request):
        qs = SpismActivityDocument.objects.filter(is_deleted=False).select_related(
            "activity", "activity__target"
        )
        au = (request.GET.get("activity") or "").strip()
        if au:
            qs = qs.filter(activity__uid=au)
        if spism_dept_head_targets_scope_only(request.user):
            qs = qs.filter(activity__target__responsible_officer=request.user)
        ser = SpismActivityDocumentSerializer(qs.order_by("-created_at"), many=True, context={"request": request})
        return CustomResponse.success(data=ser.data)

    def post(self, request):
        act_uid = request.data.get("activity")
        act = SpismActivity.objects.filter(uid=act_uid, is_deleted=False).select_related("target").first()
        if not act:
            return CustomResponse.errors(message="Activity not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_activity(request, act):
            return CustomResponse.forbidden(
                message="You can only upload documents for activities on targets assigned to you."
            )
        b64 = request.data.get("file_base64")
        fname = request.data.get("file_name") or "document"
        if not b64:
            return CustomResponse.errors(message="file_base64 required", code=STATUS_CODES["VALIDATION_ERROR"])
        try:
            key, oname = _store_uploaded_data_url(str(b64), fname, storage_subdir="spism/activity_docs")
        except ValueError as e:
            return CustomResponse.errors(message=str(e), code=STATUS_CODES["VALIDATION_ERROR"])
        if not key:
            return CustomResponse.errors(message="Upload failed", code=STATUS_CODES["PROCESS_FAILED"])
        doc = SpismActivityDocument.objects.create(
            activity=act,
            file_key=key,
            original_filename=oname or fname,
            file_size=int(request.data.get("file_size") or 0),
            mime_type=(request.data.get("file_type") or "")[:128],
            description=(request.data.get("description") or "").strip(),
            quarter=request.data.get("quarter"),
            financial_year=(request.data.get("financial_year") or "")[:32],
            created_by=request.user,
            updated_by=request.user,
        )
        return CustomResponse.success(
            data=SpismActivityDocumentSerializer(doc, context={"request": request}).data, message="Uploaded"
        )


class SpismActivityDocumentDetailView(SpismProtectedAPIView):
    spism_perm_map = {
        "PUT": ("can_edit_spism_supporting_document",),
        "DELETE": ("can_delete_spism_supporting_document",),
    }

    def put(self, request, uid):
        doc = (
            SpismActivityDocument.objects.filter(uid=uid, is_deleted=False)
            .select_related("activity", "activity__target")
            .first()
        )
        if not doc:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_activity(request, doc.activity):
            return CustomResponse.forbidden(message="You do not have access to this document.")
        b64 = request.data.get("file_base64")
        if b64:
            try:
                key, oname = _store_uploaded_data_url(
                    str(b64), request.data.get("file_name") or doc.original_filename, storage_subdir="spism/activity_docs"
                )
                if key:
                    doc.file_key = key
                    doc.original_filename = oname or doc.original_filename
                    doc.file_size = int(request.data.get("file_size") or 0)
                    doc.mime_type = (request.data.get("file_type") or doc.mime_type)[:128]
            except ValueError as e:
                return CustomResponse.errors(message=str(e), code=STATUS_CODES["VALIDATION_ERROR"])
        if "description" in request.data:
            doc.description = (request.data.get("description") or "").strip()
        if "quarter" in request.data:
            doc.quarter = request.data.get("quarter")
        if "financial_year" in request.data:
            doc.financial_year = (request.data.get("financial_year") or "")[:32]
        doc.updated_by = request.user
        doc.save()
        return CustomResponse.success(
            data=SpismActivityDocumentSerializer(doc, context={"request": request}).data, message="Updated"
        )

    def delete(self, request, uid):
        doc = (
            SpismActivityDocument.objects.filter(uid=uid, is_deleted=False)
            .select_related("activity", "activity__target")
            .first()
        )
        if not doc:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        if _dept_head_scope_denies_activity(request, doc.activity):
            return CustomResponse.forbidden(message="You do not have access to this document.")
        doc.is_deleted = True
        doc.updated_by = request.user
        doc.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(doc.uid)}, message="Deleted")


class SpismActivityDocumentDownloadView(SpismProtectedAPIView):
    spism_perm_map = {
        "GET": ("can_view_spism_activity", "can_edit_spism_supporting_document"),
    }

    def get(self, request, uid):
        from django.core.files.storage import default_storage

        doc = (
            SpismActivityDocument.objects.filter(uid=uid, is_deleted=False)
            .select_related("activity", "activity__target")
            .first()
        )
        if not doc or not doc.file_key:
            return Response(
                {
                    "status": STATUS_CODES["DATA_NOT_FOUND"],
                    "message": "Document or file not found",
                    "data": None,
                },
                status=http_status.HTTP_404_NOT_FOUND,
            )
        if _dept_head_scope_denies_activity(request, doc.activity):
            return Response(
                {
                    "status": STATUS_CODES["FORBIDDEN"],
                    "message": "You do not have access to this document.",
                    "data": None,
                },
                status=http_status.HTTP_403_FORBIDDEN,
            )
        try:
            fh = default_storage.open(doc.file_key, "rb")
        except Exception:
            return Response(
                {
                    "status": STATUS_CODES["DATA_NOT_FOUND"],
                    "message": "File missing from storage",
                    "data": None,
                },
                status=http_status.HTTP_404_NOT_FOUND,
            )
        import mimetypes

        base = doc.original_filename or "document"
        content_type, _ = mimetypes.guess_type(base)
        if not content_type:
            content_type = "application/octet-stream"
        resp = FileResponse(fh, content_type=content_type)
        resp["Content-Disposition"] = _attachment_content_disposition(base)
        return resp


# --- Audit logs ---


class SpismAuditLogListCreateView(SpismProtectedAPIView):
    """Scoped GET/POST for conversation rows; see ``SpismAuditLogConversationPermission``."""

    permission_classes = [IsAuthenticated, SpismAuditLogConversationPermission]

    def get(self, request):
        qs = SpismPerformanceAuditLog.objects.filter(is_deleted=False)
        et = (request.GET.get("entity_type") or "").strip()
        if et:
            qs = qs.filter(entity_type=et)
        eid = (request.GET.get("entity_id") or "").strip()
        if eid:
            try:
                qs = qs.filter(entity_uid=uuid.UUID(eid))
            except ValueError:
                qs = qs.none()
        return paginated_queryset(qs, request, SpismAuditLogSerializer)

    def post(self, request):
        et = (request.data.get("entity_type") or "").strip()
        eid = (request.data.get("entity_id") or "").strip()
        comment = (request.data.get("comment") or "").strip()
        if not et or not eid or not comment:
            return CustomResponse.errors(
                message="entity_type, entity_id, comment required",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            euuid = uuid.UUID(eid)
        except ValueError:
            return CustomResponse.errors(message="Invalid entity_id", code=STATUS_CODES["VALIDATION_ERROR"])
        row = SpismPerformanceAuditLog.objects.create(
            entity_type=et,
            entity_uid=euuid,
            action="COMMENT",
            comment=comment,
            actor=request.user,
            created_by=request.user,
            updated_by=request.user,
        )
        return CustomResponse.success(
            data=SpismAuditLogSerializer(row, context={"request": request}).data, message="OK"
        )


class SpismAuditLogDetailView(SpismProtectedAPIView):
    spism_perm_map = {"GET": ("can_view_spism_audit_log",)}

    def get(self, request, uid):
        row = SpismPerformanceAuditLog.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        return CustomResponse.success(data=SpismAuditLogSerializer(row, context={"request": request}).data)


# --- Officers & approvals & implementation lists ---


class SpismPerformanceOfficersView(SpismProtectedAPIView):
    spism_perm_map = {
        "GET": (
            "can_view_spism_objective",
            "can_view_spism_target",
            "can_edit_spism_target",
            "can_view_spism_activity",
            "can_add_spism_activity",
            "can_view_spism_approval",
            "can_view_spism_implementation",
        ),
    }

    def get(self, request):
        if spism_dept_head_targets_scope_only(request.user):
            u = request.user
            data = [
                {
                    "id": u.pk,
                    "label": f"{u.first_name} {u.last_name}".strip() or u.username,
                    "full_name": f"{u.first_name} {u.last_name}".strip(),
                    "username": u.username,
                }
            ]
            return CustomResponse.success(data=data)
        q = (request.GET.get("search") or "").strip()
        qs = User.objects.filter(is_active=True)
        if q:
            qs = qs.filter(
                Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
            )
        qs = qs.order_by("first_name", "last_name")[:200]
        data = [
            {
                "id": u.pk,
                "label": f"{u.first_name} {u.last_name}".strip() or u.username,
                "full_name": f"{u.first_name} {u.last_name}".strip(),
                "username": u.username,
            }
            for u in qs
        ]
        return CustomResponse.success(data=data)


class SpismPendingApprovalsView(SpismProtectedAPIView):
    spism_perm_map = {"GET": ("can_view_spism_approval",)}

    def get(self, request):
        st = (request.GET.get("status") or "PENDING").strip()
        et = (request.GET.get("entity_type") or "").strip().lower()
        fy = (request.GET.get("financial_year") or "").strip()
        scoped = spism_dept_head_targets_scope_only(request.user)

        def filt_obj(qs):
            if fy:
                qs = qs.filter(financial_year=fy)
            qs = qs.filter(status=st)
            if scoped:
                qs = qs.filter(
                    Exists(
                        SpismTarget.objects.filter(
                            objective_id=OuterRef("pk"),
                            is_deleted=False,
                            responsible_officer=request.user,
                        )
                    )
                )
            return qs[:500]

        def filt_t(qs):
            if fy:
                qs = qs.filter(objective__financial_year=fy)
            qs = qs.filter(status=st)
            if scoped:
                qs = qs.filter(responsible_officer=request.user)
            return qs[:500]

        def filt_a(qs):
            if fy:
                qs = qs.filter(planned_financial_year=fy)
            qs = qs.filter(status=st)
            if scoped:
                qs = qs.filter(target__responsible_officer=request.user)
            return qs[:500]

        objectives = []
        targets = []
        activities = []
        obj_ctx = {"request": request}
        if scoped:
            obj_ctx["dept_head_targets_scope"] = True
        if not et or et == "objective":
            objectives = SpismObjectiveListSerializer(
                filt_obj(SpismObjective.objects.filter(is_deleted=False)),
                many=True,
                context=obj_ctx,
            ).data
        if not et or et == "target":
            targets = SpismTargetSerializer(
                filt_t(SpismTarget.objects.filter(is_deleted=False).select_related("objective")),
                many=True,
                context={"request": request},
            ).data
        if not et or et == "activity":
            activities = SpismActivitySerializer(
                filt_a(SpismActivity.objects.filter(is_deleted=False).select_related("target", "target__objective")),
                many=True,
                context={"request": request},
            ).data
        return CustomResponse.success(
            data={"objectives": objectives, "targets": targets, "activities": activities}
        )


class SpismImplementationActivitiesView(SpismProtectedAPIView):
    spism_perm_map = {"GET": ("can_view_spism_implementation",)}

    def get(self, request):
        qs = SpismActivity.objects.filter(is_deleted=False, status=SpismActivity.Status.APPROVED).select_related(
            "target", "target__objective"
        )
        fy = (request.GET.get("financial_year") or "").strip()
        if fy:
            qs = qs.filter(planned_financial_year=fy)
        sq = (request.GET.get("search") or "").strip()
        if sq:
            qs = qs.filter(
                Q(title__icontains=sq)
                | Q(target__title__icontains=sq)
                | Q(target__objective__title__icontains=sq)
            )
        queue = (request.GET.get("queue") or "").strip()
        if queue == "implementation_approval":
            qs = qs.filter(
                Q(implementation_submitted_at__isnull=False)
                | ~Q(implementation_quarters_state={})
            )
        if str(request.GET.get("submitted_only", "")).lower() == "true":
            qs = qs.filter(implementation_submitted_at__isnull=False)
        if spism_dept_head_targets_scope_only(request.user):
            qs = qs.filter(target__responsible_officer=request.user)
        return paginated_queryset(qs.order_by("-updated_at"), request, SpismActivitySerializer)


class SpismImplementationTargetsView(SpismProtectedAPIView):
    spism_perm_map = {"GET": ("can_view_spism_implementation",)}

    def get(self, request):
        fy = (request.GET.get("financial_year") or "").strip()
        qs = SpismTarget.objects.filter(is_deleted=False, status=SpismTarget.Status.APPROVED).select_related(
            "objective"
        )
        if fy:
            qs = qs.filter(objective__financial_year=fy)
        qs = qs.filter(kpi_planned_value__isnull=False).order_by("title")
        if spism_dept_head_targets_scope_only(request.user):
            qs = qs.filter(responsible_officer=request.user)
        ser = SpismTargetSerializer(qs[:500], many=True, context={"request": request})
        return CustomResponse.success(data=ser.data)
