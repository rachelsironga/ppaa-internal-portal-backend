from django.db.models import Count, Exists, OuterRef

from .models import (
    SpismActivity,
    SpismFinancialYear,
    SpismObjective,
    SpismTarget,
)
from .reporting import build_report
from .serializers import SpismFinancialYearSerializer, SpismObjectiveListSerializer
from .spism_permissions import SpismProtectedAPIView, spism_dept_head_targets_scope_only
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES


def _empty_analytics_payload():
    return {
        "institutional_performance": 0,
        "status_distribution": {
            "objectives": [],
            "targets": [],
            "activities": [],
        },
        "objectives_by_financial_year": [],
        "quarterly_trend": [],
        "objective_performance": [],
        "progress_status": [],
    }


class FinancialYearListCreateView(SpismProtectedAPIView):
    # GET list: setup admins, or anyone who needs FY options on operational screens (dashboard, etc.).
    spism_perm_map = {
        "GET": ("can_view_spism_setup", "can_view_spism_dashboard"),
        "POST": ("can_edit_spism_setup",),
    }

    def get(self, request):
        qs = SpismFinancialYear.objects.filter(is_deleted=False).order_by("-start_date")
        ser = SpismFinancialYearSerializer(qs, many=True)
        return CustomResponse.success(data=ser.data, message="Success")

    def post(self, request):
        ser = SpismFinancialYearSerializer(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        ser.save(created_by=request.user, updated_by=request.user)
        return CustomResponse.success(data=ser.data, message="Created")


class FinancialYearDetailView(SpismProtectedAPIView):
    spism_perm_map = {
        "GET": ("can_view_spism_setup", "can_view_spism_dashboard"),
        "PUT": ("can_edit_spism_setup",),
        "DELETE": ("can_edit_spism_setup",),
    }

    def get(self, request, uid):
        row = SpismFinancialYear.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Financial year not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        return CustomResponse.success(
            data=SpismFinancialYearSerializer(row).data, message="Success"
        )

    def put(self, request, uid):
        row = SpismFinancialYear.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Financial year not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        ser = SpismFinancialYearSerializer(row, data=request.data, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        ser.save(updated_by=request.user)
        return CustomResponse.success(data=ser.data, message="Updated")

    def delete(self, request, uid):
        row = SpismFinancialYear.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Financial year not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class PerformanceAnalyticsView(SpismProtectedAPIView):
    # Dashboard + reports roles need scoped or read-only charts (dept heads / viewers do not carry analytics codename).
    spism_perm_map = {
        "GET": (
            "can_view_spism_analytics",
            "can_view_spism_dashboard",
            "can_view_spism_reports",
            "can_view_spism_approval",
        ),
    }

    def get(self, request):
        fy = (request.GET.get("financial_year") or "").strip()
        payload = _empty_analytics_payload()
        scoped = spism_dept_head_targets_scope_only(request.user)

        def status_counts(model, fy_field=None):
            qs = model.objects.filter(is_deleted=False)
            if fy and fy_field:
                qs = qs.filter(**{fy_field: fy})
            if scoped and model is SpismObjective:
                qs = qs.filter(
                    Exists(
                        SpismTarget.objects.filter(
                            objective_id=OuterRef("pk"),
                            is_deleted=False,
                            responsible_officer=request.user,
                        )
                    )
                )
            if scoped and model is SpismTarget:
                qs = qs.filter(responsible_officer=request.user)
            if scoped and model is SpismActivity:
                qs = qs.filter(target__responsible_officer=request.user)
            rows = qs.values("status").annotate(c=Count("id"))
            return [{"status": r["status"], "count": r["c"]} for r in rows]

        payload["status_distribution"]["objectives"] = status_counts(
            SpismObjective, "financial_year" if fy else None
        )
        if fy:
            tgt_qs = SpismTarget.objects.filter(is_deleted=False, objective__financial_year=fy)
            act_qs = SpismActivity.objects.filter(is_deleted=False, planned_financial_year=fy)
        else:
            tgt_qs = SpismTarget.objects.filter(is_deleted=False)
            act_qs = SpismActivity.objects.filter(is_deleted=False)
        if scoped:
            tgt_qs = tgt_qs.filter(responsible_officer=request.user)
            act_qs = act_qs.filter(target__responsible_officer=request.user)
        payload["status_distribution"]["targets"] = [
            {"status": r["status"], "count": r["c"]}
            for r in tgt_qs.values("status").annotate(c=Count("id"))
        ]
        payload["status_distribution"]["activities"] = [
            {"status": r["status"], "count": r["c"]}
            for r in act_qs.values("status").annotate(c=Count("id"))
        ]
        return CustomResponse.success(data=payload, message="Success")


class PerformanceReportsView(SpismProtectedAPIView):
    spism_perm_map = {"GET": ("can_view_spism_reports",)}

    def get(self, request):
        report_type = (request.GET.get("report_type") or "quarterly").strip()
        financial_year = (request.GET.get("financial_year") or "").strip()
        if not financial_year:
            return CustomResponse.errors(
                message="financial_year is required",
                data=None,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        body = build_report(report_type, financial_year)
        return CustomResponse.success(data=body, message="Success")


class DashboardSummaryView(SpismProtectedAPIView):
    """Objectives for dashboard cards (optionally filtered by financial_year)."""

    spism_perm_map = {"GET": ("can_view_spism_dashboard",)}

    def get(self, request):
        fy = (request.GET.get("financial_year") or "").strip()
        qs = SpismObjective.objects.filter(is_deleted=False)
        if fy:
            qs = qs.filter(financial_year=fy)
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
        qs = qs.order_by("-created_at")[:500]
        ctx = {"request": request}
        if spism_dept_head_targets_scope_only(request.user):
            ctx["dept_head_targets_scope"] = True
        ser = SpismObjectiveListSerializer(qs, many=True, context=ctx)
        return CustomResponse.success(data=ser.data, message="Success")


class SpismConfigView(SpismProtectedAPIView):
    spism_perm_map = {"GET": ("can_view_spism_dashboard",)}

    def get(self, request):
        return CustomResponse.success(
            data={
                "system_name": "SPISM",
                "roles": [],
            },
            message="Success",
        )
