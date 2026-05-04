"""
Report Management System (RMS) API stubs under /api/reports/.

The internal-portal frontend expects these paths (see REPORT-MANAGEMENT/Queries.jsx).
Financial years are bridged from SPISM (ppaa_performance) so dashboards can filter by FY.
Other RMS entities return empty structures until a full RMS backend is added.
"""

import mimetypes
import os
import re
import uuid
from calendar import monthrange
from datetime import date, timedelta

from django.db import IntegrityError
from django.db.models import Count, F, Prefetch, Q
from django.db.models.functions import TruncDate
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.parsers import FormParser, MultiPartParser
from ppaa_portal.rms_permissions import (
    RmsProtectedAPIView,
    rms_apply_report_queryset_scope,
    rms_institution_scope,
    rms_reporter_department_id,
    rms_user_can_access_directorate_dashboard,
    rms_user_can_access_report,
)

from ppaa_auth.models import Department, UserProfile
from microservices.ppaa_performance.models import SpismFinancialYear
from microservices.ppaa_performance.serializers import SpismFinancialYearSerializer
from ppaa_portal.models import (
    AuditLog,
    RmsReport,
    RmsReportCategory,
    RmsReportPeriodState,
    RmsReportProgressEntry,
    RmsReportType,
    RmsStakeholder,
    audit_department_for_user,
    portal_client_ip,
    record_audit_log,
)
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES


def _rms_report_forbidden():
    return CustomResponse.forbidden(
        "You do not have access to this report or department."
    )


_RMS_ORG_TYPE_LABELS = {
    "government": "Government Agency",
    "regulatory": "Regulatory Body",
    "partner": "Partner Organization",
    "donor": "Donor/Funding Agency",
    "ngo": "NGO",
    "private": "Private Sector",
    "academic": "Academic Institution",
    "other": "Other",
}
_RMS_ORG_TYPES = frozenset(_RMS_ORG_TYPE_LABELS.keys())


class RmsStakeholderSerializer(serializers.ModelSerializer):
    """RMS stakeholder read/write; matches REPORT-MANAGEMENT StakeholderModal / detail page."""

    organization_type_display = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = RmsStakeholder
        fields = (
            "uid",
            "name",
            "organization_type",
            "organization_type_display",
            "contact_person",
            "email",
            "phone",
            "address",
            "website",
            "description",
            "is_active",
            "created_at",
            "updated_at",
            "created_by_name",
            "updated_by_name",
        )
        read_only_fields = (
            "uid",
            "created_at",
            "updated_at",
            "organization_type_display",
            "created_by_name",
            "updated_by_name",
        )

    def get_organization_type_display(self, obj):
        return _RMS_ORG_TYPE_LABELS.get(
            obj.organization_type,
            (obj.organization_type or "").replace("_", " ").title() or "",
        )

    @staticmethod
    def _user_label(user):
        if not user:
            return None
        first = (getattr(user, "first_name", None) or "").strip()
        last = (getattr(user, "last_name", None) or "").strip()
        name = f"{first} {last}".strip()
        return name or getattr(user, "email", None)

    def get_created_by_name(self, obj):
        return self._user_label(obj.created_by)

    def get_updated_by_name(self, obj):
        return self._user_label(obj.updated_by)

    def validate_organization_type(self, value):
        v = (value or "").strip().lower()
        if v not in _RMS_ORG_TYPES:
            raise serializers.ValidationError("Invalid organization type.")
        return v

    def validate_name(self, value):
        s = (value or "").strip()
        if len(s) < 2:
            raise serializers.ValidationError(
                "Name must be at least 2 characters."
            )
        return s


class RmsReportCategorySerializer(serializers.ModelSerializer):
    """RMS report category; matches ReportCategoryModal / list columns."""

    class Meta:
        model = RmsReportCategory
        fields = (
            "uid",
            "name",
            "code",
            "description",
            "color",
            "icon",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uid", "created_at", "updated_at")

    def validate_name(self, value):
        s = (value or "").strip()
        if len(s) < 2:
            raise serializers.ValidationError(
                "Name must be at least 2 characters."
            )
        return s

    def validate_code(self, value):
        s = (value or "").strip()
        if not s:
            raise serializers.ValidationError("This field is required.")
        if len(s) > 20:
            raise serializers.ValidationError(
                "Code must be at most 20 characters."
            )
        return s

    def validate_color(self, value):
        s = (value or "").strip()
        if not re.match(r"^#[0-9A-Fa-f]{6}$", s):
            raise serializers.ValidationError("Invalid hex color.")
        return s


_RMS_FREQUENCY_LABELS = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "quarterly": "Quarterly",
    "biannual": "Bi-Annual",
    "annual": "Annual",
    "adhoc": "Ad-hoc",
}
_RMS_FREQUENCY_TYPES = frozenset(_RMS_FREQUENCY_LABELS.keys())

_RMS_STATUS_LABEL = {
    "draft": "Draft",
    "pending": "Pending",
    "in_progress": "In Progress",
    "submitted": "Submitted",
}


class RmsReportTypeSerializer(serializers.ModelSerializer):
    """RMS report type; matches ReportTypeModal / ReportTypeListPage."""

    frequency_display = serializers.SerializerMethodField()

    class Meta:
        model = RmsReportType
        fields = (
            "uid",
            "name",
            "code",
            "frequency",
            "frequency_display",
            "description",
            "submission_deadline_days",
            "before_reminder_days",
            "after_reminder_days",
            "requires_attachment",
            "template_file",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "uid",
            "created_at",
            "updated_at",
            "frequency_display",
        )
        extra_kwargs = {"template_file": {"allow_blank": True}}

    def get_frequency_display(self, obj):
        return _RMS_FREQUENCY_LABELS.get(
            obj.frequency,
            (obj.frequency or "").replace("_", " ").title() or "",
        )

    def validate_name(self, value):
        s = (value or "").strip()
        if len(s) < 2:
            raise serializers.ValidationError(
                "Name must be at least 2 characters."
            )
        return s

    def validate_code(self, value):
        s = (value or "").strip()
        if not s:
            raise serializers.ValidationError("This field is required.")
        if len(s) > 20:
            raise serializers.ValidationError(
                "Code must be at most 20 characters."
            )
        return s

    def validate_frequency(self, value):
        v = (value or "").strip().lower()
        if v not in _RMS_FREQUENCY_TYPES:
            raise serializers.ValidationError("Invalid frequency.")
        return v

    @staticmethod
    def _day_field(value):
        if value is None:
            return value
        try:
            n = int(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError("Enter a whole number.")
        if n < 0 or n > 90:
            raise serializers.ValidationError("Must be between 0 and 90.")
        return n

    def validate_submission_deadline_days(self, value):
        return self._day_field(value)

    def validate_before_reminder_days(self, value):
        return self._day_field(value)

    def validate_after_reminder_days(self, value):
        return self._day_field(value)


def _rms_paginated_empty_list(request):
    """Shared empty list + pagination for RMS list stubs."""
    paginated = str(request.GET.get("paginated", "")).lower() == "true"
    if not paginated:
        return CustomResponse.success(data=[], message="Success")
    page = max(int(request.GET.get("page", 1) or 1), 1)
    page_size = min(max(int(request.GET.get("page_size", 10) or 10), 1), 500)
    return CustomResponse.success(
        data=[],
        pagination={"page": page, "page_size": page_size, "total": 0},
        message="Success",
    )


def _rms_financial_year_dict(fy: SpismFinancialYear) -> dict:
    today = date.today()
    sd, ed = fy.start_date, fy.end_date
    is_current = bool(sd and ed and sd <= today <= ed)
    return {
        "uid": str(fy.uid),
        "name": fy.name,
        "start_date": sd.isoformat() if sd else None,
        "end_date": ed.isoformat() if ed else None,
        "is_current": is_current,
        "is_active": bool(fy.is_active),
        "description": "",
    }


def _equal_date_segments(start: date, end: date, n: int) -> list[tuple[date, date]]:
    """Split inclusive range [start, end] into n contiguous segments (quarters / halves)."""
    if not start or not end or end < start or n < 1:
        return []
    total_days = (end - start).days + 1
    if total_days < 1:
        return []
    out: list[tuple[date, date]] = []
    for i in range(n):
        ai = (i * total_days) // n
        bi = ((i + 1) * total_days + n - 1) // n
        if ai >= bi:
            continue
        seg_start = start + timedelta(days=ai)
        seg_end = start + timedelta(days=bi - 1)
        if seg_end > end:
            seg_end = end
        if seg_start > end:
            break
        out.append((seg_start, seg_end))
    return out


def _calendar_month_segments(fy_start: date, fy_end: date) -> list[tuple[date, date]]:
    """One segment per calendar month overlapping the FY, clipped to FY bounds."""
    if not fy_start or not fy_end or fy_end < fy_start:
        return []
    periods: list[tuple[date, date]] = []
    cur = fy_start
    while cur <= fy_end:
        _, last_d = monthrange(cur.year, cur.month)
        month_end = date(cur.year, cur.month, last_d)
        seg_end = min(month_end, fy_end)
        periods.append((cur, seg_end))
        if seg_end >= fy_end:
            break
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return periods


def _rms_financial_period_payloads(
    fy: SpismFinancialYear, period_type: str
) -> list[dict]:
    """Synthetic periods derived from SpismFinancialYear bounds (RMS create-report UI)."""
    start, end = fy.start_date, fy.end_date
    if not start or not end or end < start:
        return []

    period_type = (period_type or "").strip().lower()
    fy_uid = str(fy.uid)

    if period_type == "quarter":
        segments = _equal_date_segments(start, end, 4)
        labels = ["Q1", "Q2", "Q3", "Q4"]
    elif period_type == "biannual":
        segments = _equal_date_segments(start, end, 2)
        labels = ["H1", "H2"]
    elif period_type == "month":
        segments = _calendar_month_segments(start, end)
        labels = []
    elif period_type == "annual":
        return [
            {
                "uid": f"{fy_uid}-pt-annual-1",
                "display_name": "Annual",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "period_type": "annual",
            }
        ]
    elif period_type == "adhoc":
        return [
            {
                "uid": f"{fy_uid}-pt-adhoc-1",
                "display_name": "Ad-hoc period",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "period_type": "adhoc",
            }
        ]
    else:
        return []

    data: list[dict] = []
    for i, (a, b) in enumerate(segments):
        if period_type == "month":
            display = a.strftime("%b %Y")
        else:
            display = labels[i] if i < len(labels) else f"P{i + 1}"
        uid = f"{fy_uid}-pt-{period_type}-{i + 1}"
        data.append(
            {
                "uid": uid,
                "display_name": display,
                "start_date": a.isoformat(),
                "end_date": b.isoformat(),
                "period_type": period_type,
            }
        )
    return data


class RmsFinancialPeriodsListView(RmsProtectedAPIView):
    """
    GET /api/reports/financial-periods?financial_year_uid=&period_type=

    period_type: quarter | month | biannual | annual | adhoc — matches REPORT-MANAGEMENT ReportModal.
    """

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request):
        fy_uid = (request.GET.get("financial_year_uid") or "").strip()
        period_type = (request.GET.get("period_type") or "").strip().lower()
        if not fy_uid or period_type not in (
            "quarter",
            "month",
            "biannual",
            "annual",
            "adhoc",
        ):
            return CustomResponse.success(data=[], message="Success")
        row = SpismFinancialYear.objects.filter(uid=fy_uid, is_deleted=False).first()
        if not row:
            return CustomResponse.success(data=[], message="Success")
        data = _rms_financial_period_payloads(row, period_type)
        return CustomResponse.success(data=data, message="Success")


class RmsFinancialYearPeriodsView(RmsProtectedAPIView):
    """GET /api/reports/financial-years/<uid>/periods — quarters (Queries.getQuartersByFinancialYear)."""

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request, uid):
        row = SpismFinancialYear.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.success(data=[], message="Success")
        data = _rms_financial_period_payloads(row, "quarter")
        return CustomResponse.success(data=data, message="Success")


class RmsFinancialYearsListView(RmsProtectedAPIView):
    """GET /api/reports/financial-years — list (optionally paginated)."""

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request):
        qs = SpismFinancialYear.objects.filter(is_deleted=False).order_by("-start_date")
        search = (request.GET.get("search") or "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        paginated = str(request.GET.get("paginated", "")).lower() == "true"
        if not paginated:
            data = [_rms_financial_year_dict(fy) for fy in qs]
            return CustomResponse.success(data=data, message="Success")

        page = max(int(request.GET.get("page", 1) or 1), 1)
        page_size = min(max(int(request.GET.get("page_size", 10) or 10), 1), 500)
        total = qs.count()
        start = (page - 1) * page_size
        chunk = qs[start : start + page_size]
        data = [_rms_financial_year_dict(fy) for fy in chunk]
        return CustomResponse.success(
            data=data,
            pagination={"page": page, "page_size": page_size, "total": total},
            message="Success",
        )


class RmsReportTypesListView(RmsProtectedAPIView):
    """GET /api/reports/report-types — list (dashboards + setup)."""

    rms_perm_map = {"GET": ("view_rmsreporttype",)}

    def get(self, request):
        qs = RmsReportType.objects.filter(is_deleted=False).order_by("name")
        search = (request.GET.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(code__icontains=search)
            )
        freq = (request.GET.get("frequency") or "").strip().lower()
        if freq:
            qs = qs.filter(frequency=freq)
        paginated = str(request.GET.get("paginated", "")).lower() == "true"
        if not paginated:
            data = [RmsReportTypeSerializer(r).data for r in qs]
            return CustomResponse.success(data=data, message="Success")
        page = max(int(request.GET.get("page", 1) or 1), 1)
        page_size = min(max(int(request.GET.get("page_size", 10) or 10), 1), 500)
        total = qs.count()
        start = (page - 1) * page_size
        chunk = qs[start : start + page_size]
        data = [RmsReportTypeSerializer(r).data for r in chunk]
        return CustomResponse.success(
            data=data,
            pagination={"page": page, "page_size": page_size, "total": total},
            message="Success",
        )


class RmsReportTypeCreateView(RmsProtectedAPIView):
    """POST /api/reports/report-types/create"""

    rms_perm_map = {"POST": ("add_rmsreporttype",)}

    def post(self, request):
        ser = RmsReportTypeSerializer(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            ser.save(created_by=request.user, updated_by=request.user)
        except IntegrityError:
            return CustomResponse.errors(
                message="Validation failed",
                data={"code": ["A report type with this code already exists."]},
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        return CustomResponse.success(data=ser.data, message="Created")


class RmsReportTypeUpdateView(RmsProtectedAPIView):
    """PUT /api/reports/report-types/<uid>/update"""

    rms_perm_map = {"PUT": ("change_rmsreporttype",)}

    def put(self, request, uid):
        row = RmsReportType.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Report type not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        ser = RmsReportTypeSerializer(row, data=request.data, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            ser.save(updated_by=request.user)
        except IntegrityError:
            return CustomResponse.errors(
                message="Validation failed",
                data={"code": ["A report type with this code already exists."]},
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        row.refresh_from_db()
        return CustomResponse.success(
            data=RmsReportTypeSerializer(row).data, message="Updated"
        )


class RmsReportTypeDeleteView(RmsProtectedAPIView):
    """DELETE /api/reports/report-types/<uid>/delete"""

    rms_perm_map = {"DELETE": ("delete_rmsreporttype",)}

    def delete(self, request, uid):
        row = RmsReportType.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Report type not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class RmsReportTypeDetailView(RmsProtectedAPIView):
    """GET /api/reports/report-types/<uid>"""

    rms_perm_map = {"GET": ("view_rmsreporttype",)}

    def get(self, request, uid):
        row = RmsReportType.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Report type not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        return CustomResponse.success(
            data=RmsReportTypeSerializer(row).data, message="Success"
        )


class RmsReportCategoriesListView(RmsProtectedAPIView):
    """GET /api/reports/report-categories — list (PaginatedTable)."""

    rms_perm_map = {"GET": ("view_rmsreportcategory",)}

    def get(self, request):
        qs = RmsReportCategory.objects.filter(is_deleted=False).order_by("name")
        search = (request.GET.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(code__icontains=search)
            )
        paginated = str(request.GET.get("paginated", "")).lower() == "true"
        if not paginated:
            data = [RmsReportCategorySerializer(r).data for r in qs]
            return CustomResponse.success(data=data, message="Success")
        page = max(int(request.GET.get("page", 1) or 1), 1)
        page_size = min(max(int(request.GET.get("page_size", 10) or 10), 1), 500)
        total = qs.count()
        start = (page - 1) * page_size
        chunk = qs[start : start + page_size]
        data = [RmsReportCategorySerializer(r).data for r in chunk]
        return CustomResponse.success(
            data=data,
            pagination={"page": page, "page_size": page_size, "total": total},
            message="Success",
        )


class RmsReportCategoryCreateView(RmsProtectedAPIView):
    """POST /api/reports/report-categories/create"""

    rms_perm_map = {"POST": ("add_rmsreportcategory",)}

    def post(self, request):
        ser = RmsReportCategorySerializer(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            ser.save(created_by=request.user, updated_by=request.user)
        except IntegrityError:
            return CustomResponse.errors(
                message="Validation failed",
                data={"code": ["A category with this code already exists."]},
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        return CustomResponse.success(data=ser.data, message="Created")


class RmsReportCategoryUpdateView(RmsProtectedAPIView):
    """PUT /api/reports/report-categories/<uid>/update"""

    rms_perm_map = {"PUT": ("change_rmsreportcategory",)}

    def put(self, request, uid):
        row = RmsReportCategory.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Category not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        ser = RmsReportCategorySerializer(row, data=request.data, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            ser.save(updated_by=request.user)
        except IntegrityError:
            return CustomResponse.errors(
                message="Validation failed",
                data={"code": ["A category with this code already exists."]},
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        row.refresh_from_db()
        return CustomResponse.success(
            data=RmsReportCategorySerializer(row).data, message="Updated"
        )


class RmsReportCategoryDeleteView(RmsProtectedAPIView):
    """DELETE /api/reports/report-categories/<uid>/delete"""

    rms_perm_map = {"DELETE": ("delete_rmsreportcategory",)}

    def delete(self, request, uid):
        row = RmsReportCategory.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Category not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class RmsReportCategoryDetailView(RmsProtectedAPIView):
    """GET /api/reports/report-categories/<uid>"""

    rms_perm_map = {"GET": ("view_rmsreportcategory",)}

    def get(self, request, uid):
        row = RmsReportCategory.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Category not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        return CustomResponse.success(
            data=RmsReportCategorySerializer(row).data, message="Success"
        )


class RmsDepartmentsListView(RmsProtectedAPIView):
    """GET /api/reports/departments — active departments (filters, DIR / ED dashboards)."""

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request):
        qs = Department.objects.filter(is_deleted=False, is_active=True).order_by("name")
        search = (request.GET.get("search") or "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search))

        if not rms_institution_scope(request.user):
            did = rms_reporter_department_id(request.user)
            if did:
                qs = qs.filter(pk=did)
            else:
                qs = qs.none()

        def row(d):
            return {"uid": str(d.uid), "name": d.name, "code": d.code}

        paginated = str(request.GET.get("paginated", "")).lower() == "true"
        if not paginated:
            data = [row(d) for d in qs[:500]]
            return CustomResponse.success(data=data, message="Success")
        page = max(int(request.GET.get("page", 1) or 1), 1)
        page_size = min(max(int(request.GET.get("page_size", 10) or 10), 1), 500)
        total = qs.count()
        start = (page - 1) * page_size
        data = [row(d) for d in qs[start : start + page_size]]
        return CustomResponse.success(
            data=data,
            pagination={"page": page, "page_size": page_size, "total": total},
            message="Success",
        )


class RmsStakeholdersListView(RmsProtectedAPIView):
    """GET /api/reports/stakeholders — list (PaginatedTable / RMS setup)."""

    rms_perm_map = {"GET": ("view_rmsstakeholder",)}

    def get(self, request):
        qs = RmsStakeholder.objects.filter(is_deleted=False).order_by("name")
        search = (request.GET.get("search") or "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        org = (request.GET.get("organization_type") or "").strip().lower()
        if org:
            qs = qs.filter(organization_type=org)
        paginated = str(request.GET.get("paginated", "")).lower() == "true"
        if not paginated:
            data = [RmsStakeholderSerializer(r).data for r in qs]
            return CustomResponse.success(data=data, message="Success")
        page = max(int(request.GET.get("page", 1) or 1), 1)
        page_size = min(max(int(request.GET.get("page_size", 10) or 10), 1), 500)
        total = qs.count()
        start = (page - 1) * page_size
        chunk = qs[start : start + page_size]
        data = [RmsStakeholderSerializer(r).data for r in chunk]
        return CustomResponse.success(
            data=data,
            pagination={"page": page, "page_size": page_size, "total": total},
            message="Success",
        )


class RmsStakeholderCreateView(RmsProtectedAPIView):
    """POST /api/reports/stakeholders/create"""

    rms_perm_map = {"POST": ("add_rmsstakeholder",)}

    def post(self, request):
        ser = RmsStakeholderSerializer(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        ser.save(created_by=request.user, updated_by=request.user)
        return CustomResponse.success(data=ser.data, message="Created")


class RmsStakeholderUpdateView(RmsProtectedAPIView):
    """PUT /api/reports/stakeholders/<uid>/update"""

    rms_perm_map = {"PUT": ("change_rmsstakeholder",)}

    def put(self, request, uid):
        row = RmsStakeholder.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Stakeholder not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        ser = RmsStakeholderSerializer(row, data=request.data, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        ser.save(updated_by=request.user)
        row.refresh_from_db()
        return CustomResponse.success(
            data=RmsStakeholderSerializer(row).data, message="Updated"
        )


class RmsStakeholderDeleteView(RmsProtectedAPIView):
    """DELETE /api/reports/stakeholders/<uid>/delete"""

    rms_perm_map = {"DELETE": ("delete_rmsstakeholder",)}

    def delete(self, request, uid):
        row = RmsStakeholder.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Stakeholder not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class RmsStakeholderDetailView(RmsProtectedAPIView):
    """GET /api/reports/stakeholders/<uid>"""

    rms_perm_map = {"GET": ("view_rmsstakeholder",)}

    def get(self, request, uid):
        row = RmsStakeholder.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Stakeholder not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        return CustomResponse.success(
            data=RmsStakeholderSerializer(row).data, message="Success"
        )


def _rms_form_to_dict(request) -> dict:
    """POST / multipart: single values as str; repeated keys (e.g. financial_period_uids) as list."""
    out: dict = {}
    for key in request.POST.keys():
        vals = request.POST.getlist(key)
        if len(vals) == 1:
            out[key] = vals[0]
        else:
            out[key] = vals
    return out


def _rms_external_scope_stakeholder_error(
    scope: str,
    stakeholder,
    other_name: str,
    stakeholder_uid_sent: str,
) -> object | None:
    """
    External scope requires a resolved stakeholder FK or other_stakeholder_name (min 2 chars).
    Returns a CustomResponse.errors(...) payload or None if valid.
    """
    if (scope or "internal").strip().lower() != "external":
        return None
    other = (other_name or "").strip()
    if stakeholder is not None:
        return None
    if len(other) >= 2:
        return None
    uid_raw = (stakeholder_uid_sent or "").strip()
    if uid_raw:
        return CustomResponse.errors(
            message="Validation failed",
            data={
                "stakeholder_uid": [
                    "The selected stakeholder was not found. Choose another from the list, or use Other with a name."
                ]
            },
            code=STATUS_CODES["VALIDATION_ERROR"],
        )
    return CustomResponse.errors(
        message="Validation failed",
        data={
            "stakeholder_uid": [
                "External reports require a stakeholder from the list, or choose Other and enter a name (at least 2 characters)."
            ]
        },
        code=STATUS_CODES["VALIDATION_ERROR"],
    )


def _rms_deadline_state_and_days(deadline: date | None) -> tuple[str, int]:
    if not deadline:
        return "unknown", 0
    today = timezone.localdate()
    diff = (deadline - today).days
    if diff < 0:
        return "overdue", diff
    if diff == 0:
        return "due_today", 0
    if diff <= 7:
        return "due_soon", diff
    return "on_track", diff


def _rms_deadline_state_filter_q(states: list[str]) -> Q | None:
    """OR-combine deadline_state query params (matches list row / DEADLINE_STATE_OPTIONS)."""
    if not states:
        return None
    today = timezone.localdate()
    end_soon = today + timedelta(days=7)
    q_acc: Q | None = None
    for raw in states:
        st = (raw or "").strip().lower()
        if not st:
            continue
        if st == "completed":
            qn = Q(status="submitted")
        elif st == "overdue":
            qn = Q(deadline_date__lt=today)
        elif st == "due_today":
            qn = Q(deadline_date=today)
        elif st == "due_soon":
            qn = Q(deadline_date__gt=today, deadline_date__lte=end_soon)
        elif st == "on_track":
            qn = Q(deadline_date__gt=end_soon)
        elif st == "unknown":
            qn = Q(deadline_date__isnull=True)
        else:
            continue
        q_acc = qn if q_acc is None else (q_acc | qn)
    return q_acc


def _rms_normalize_report_frequency(raw: str | None) -> str:
    s = (raw or "").strip().lower().replace(" ", "-").replace("_", "-")
    if s in (
        "biannual",
        "bi-annual",
        "semi-annual",
        "semiannual",
        "half-year",
        "half-yearly",
        "halfyear",
    ):
        return "biannual"
    if s in ("year", "yearly"):
        return "annual"
    if s in ("quarter", "qtr"):
        return "quarterly"
    if s == "month":
        return "monthly"
    if s in ("adhoc", "ad-hoc", "adhook", "ad-hook"):
        return "adhoc"
    return s


def _rms_ordered_period_uids(r: RmsReport) -> list[str]:
    uids: list[str] = []
    raw = r.financial_period_uids
    if raw and isinstance(raw, list):
        uids = [str(x).strip() for x in raw if str(x).strip()]
    if not uids and (r.financial_period_uid or "").strip():
        uids = [(r.financial_period_uid or "").strip()]
    if not uids:
        freq = _rms_normalize_report_frequency(r.report_type.frequency)
        if freq == "annual" and r.financial_year_uid:
            uids = [f"{str(r.financial_year_uid)}-pt-annual-1"]
        elif freq == "adhoc" and r.financial_year_uid:
            uids = [f"{str(r.financial_year_uid)}-pt-adhoc-1"]
    return uids


def _rms_payload_ptype_for_freq(freq: str) -> str | None:
    f = _rms_normalize_report_frequency(freq)
    return {
        "quarterly": "quarter",
        "biannual": "biannual",
        "monthly": "month",
        "annual": "annual",
        "adhoc": "adhoc",
    }.get(f)


def _rms_uses_per_period_implementation(r: RmsReport) -> bool:
    freq = _rms_normalize_report_frequency(r.report_type.frequency)
    if freq not in ("quarterly", "biannual", "monthly", "annual", "adhoc"):
        return False
    uids = _rms_ordered_period_uids(r)
    return len(uids) > 0


def _rms_period_status_display(status: str) -> str:
    return {
        "pending": "Pending",
        "in_progress": "In Progress",
        "submitted": "Submitted",
        "draft": "Draft",
    }.get((status or "").lower(), status or "")


def _sync_report_aggregate_from_periods(r: RmsReport, user):
    """Recompute report.progress_percentage (submitted periods / total) and status."""
    if not _rms_uses_per_period_implementation(r):
        return
    uids = _rms_ordered_period_uids(r)
    if not uids:
        return
    states = {s.period_uid: s for s in RmsReportPeriodState.objects.filter(report=r)}
    total = len(uids)
    done = sum(
        1 for uid in uids if states.get(uid) and states[uid].status == "submitted"
    )
    r.progress_percentage = int(round(100 * done / total)) if total > 0 else 0
    all_submitted = done == total and total > 0
    any_started = any(
        states.get(uid)
        and (
            states[uid].progress_percentage > 0
            or states[uid].status in ("in_progress", "submitted")
        )
        for uid in uids
    )
    if all_submitted:
        r.status = "submitted"
    elif any_started and (r.status or "").lower() in ("draft", "pending", ""):
        r.status = "in_progress"
    r.updated_by = user
    r.save(update_fields=["progress_percentage", "status", "updated_at", "updated_by"])


def _rms_build_quarter_submissions(request, r: RmsReport, fy: SpismFinancialYear | None) -> list[dict]:
    if not fy or not _rms_uses_per_period_implementation(r):
        return []
    freq = _rms_normalize_report_frequency(r.report_type.frequency)
    ptype = _rms_payload_ptype_for_freq(freq)
    if not ptype:
        return []
    uids = _rms_ordered_period_uids(r)
    if not uids:
        return []
    payload_by_uid = {p["uid"]: p for p in _rms_financial_period_payloads(fy, ptype)}
    states_by_uid = {s.period_uid: s for s in r.period_states.all()}
    out: list[dict] = []
    for uid in uids:
        p = payload_by_uid.get(uid)
        if not p:
            continue
        st = states_by_uid.get(uid)
        st_progress = st.progress_percentage if st else 0
        st_status = (st.status if st else "pending").lower()
        if st_status not in ("pending", "in_progress", "submitted"):
            st_status = "pending"
        dl = _rms_compute_deadline_date(r.report_type, fy, uid, [uid])
        has_att = bool(st and st.attachment)
        att_name = None
        if st and st.attachment:
            att_name = st.attachment.name
        fname = att_name.split("/")[-1] if att_name else None
        out.append(
            {
                "period_uid": uid,
                "uid": str(r.uid),
                "period_name": p.get("display_name") or uid,
                "period_start_date": p.get("start_date"),
                "period_end_date": p.get("end_date"),
                "status": st_status,
                "status_display": _rms_period_status_display(st_status),
                "progress_percentage": st_progress,
                "deadline_date": dl.isoformat() if dl else None,
                "has_attachment": has_att,
                "attachment_name": fname,
            }
        )
    return out


def _rms_compute_deadline_date(
    rt: RmsReportType,
    fy: SpismFinancialYear | None,
    fin_uid: str,
    fin_uids: list,
) -> date | None:
    if not rt or not fy:
        return None
    days = int(rt.submission_deadline_days or 0)
    freq = _rms_normalize_report_frequency(rt.frequency)
    base_end: date | None = None
    if freq == "annual":
        base_end = fy.end_date
    else:
        uids = [str(u) for u in fin_uids if u] if fin_uids else ([str(fin_uid)] if fin_uid else [])
        ptype = None
        if freq == "quarterly":
            ptype = "quarter"
        elif freq == "monthly":
            ptype = "month"
        elif freq == "biannual":
            ptype = "biannual"
        elif freq in ("adhoc", "daily", "weekly"):
            base_end = fy.end_date
        if ptype and base_end is None:
            payloads = _rms_financial_period_payloads(fy, ptype)
            ends = []
            for p in payloads:
                if p["uid"] in uids:
                    ends.append(date.fromisoformat(p["end_date"]))
            if ends:
                base_end = max(ends)
        if base_end is None:
            base_end = fy.end_date
    try:
        return base_end + timedelta(days=days)
    except TypeError:
        return None


def _rms_period_metrics(r: RmsReport) -> tuple[int, int, int]:
    if _rms_uses_per_period_implementation(r):
        uids = _rms_ordered_period_uids(r)
        total = len(uids)
        if total <= 0:
            return 0, 0, 0
        states = {s.period_uid: s for s in r.period_states.all()}
        done = sum(
            1
            for uid in uids
            if states.get(uid) and states[uid].status == "submitted"
        )
        pending = total - done
        return done, pending, total
    return 0, 0, 0


def _rms_user_display_name(user) -> str:
    if not user:
        return ""
    first = (getattr(user, "first_name", None) or "").strip()
    last = (getattr(user, "last_name", None) or "").strip()
    name = f"{first} {last}".strip()
    return name or getattr(user, "email", None) or ""


def _rms_pdf_bytes_with_download_watermark(request, raw: bytes, report: RmsReport) -> bytes:
    """Apply the same RMS security overlay used for downloads (also used for inline PDF preview)."""
    if not raw or not raw.startswith(b"%PDF"):
        return raw
    from ppaa_portal.rms_pdf_watermark import watermark_rms_pdf_download

    dept_label = ""
    prof = (
        UserProfile.objects.filter(
            user=request.user, is_active=True, is_deleted=False
        )
        .select_related("department")
        .first()
    )
    if prof and prof.department:
        d = prof.department
        dept_label = (d.code or d.name or "").strip()
    ts = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M %Z")
    return watermark_rms_pdf_download(
        raw,
        user_display=_rms_user_display_name(request.user),
        department=dept_label,
        report_ref=report.reference_number or "",
        downloaded_at=ts,
    )


def _rms_report_audit_log(
    request, report: RmsReport, action: str, changes: dict | None = None
):
    ua = request.META.get("HTTP_USER_AGENT") or ""
    record_audit_log(
        user=request.user,
        action=(action or "")[:64],
        model_name="RmsReport",
        object_id=str(report.uid),
        object_repr=(report.title or "")[:255],
        changes=changes if changes is not None else {},
        ip_address=portal_client_ip(request) or None,
        user_agent=ua[:512] if ua else None,
        department=audit_department_for_user(request.user),
        created_by=request.user,
        updated_by=request.user,
    )


def _rms_progress_updates_for_report(r: RmsReport) -> list[dict]:
    if (
        hasattr(r, "_prefetched_objects_cache")
        and "progress_entries" in r._prefetched_objects_cache
    ):
        entries = list(r.progress_entries.all())
    else:
        entries = list(
            r.progress_entries.order_by("created_at").select_related("created_by")
        )
    return [
        {
            "percentage": e.percentage,
            "notes": e.notes or "",
            "created_by_name": _rms_user_display_name(e.created_by),
            "created_at": e.created_at.isoformat(),
            "period_uid": (e.period_uid or "").strip() or None,
            "financial_period_uid": (e.period_uid or "").strip() or None,
        }
        for e in entries
    ]


def _rms_audit_trail_row(log: AuditLog, report: RmsReport | None) -> dict:
    ch = log.changes if isinstance(log.changes, dict) else {}
    dept = log.department
    rid = (log.object_id or "").strip()
    title = (report.title if report else None) or (log.object_repr or "")
    ref = report.reference_number if report else ""
    return {
        "uid": f"al-{log.pk}",
        "action": log.action,
        "created_at": log.created_at.isoformat(),
        "performed_by_name": _rms_user_display_name(log.user),
        "comments": ch.get("comments"),
        "old_value": ch.get("old_value"),
        "new_value": ch.get("new_value"),
        "report_uid": rid or None,
        "report_title": title,
        "report_reference": ref,
        "ip_address": log.ip_address or "",
        "directory_code": (dept.code if dept else "") or "",
    }


def _rms_audit_row_for_report(log: AuditLog, report: RmsReport) -> dict:
    return _rms_audit_trail_row(log, report)


def _rms_reports_by_uid_for_audit(
    logs: list[AuditLog],
) -> dict[str, RmsReport]:
    uids: list[uuid.UUID] = []
    for log in logs:
        try:
            uids.append(uuid.UUID(str(log.object_id).strip()))
        except (ValueError, TypeError, AttributeError):
            continue
    if not uids:
        return {}
    rows = RmsReport.objects.filter(uid__in=uids).only(
        "uid", "title", "reference_number", "is_deleted"
    )
    return {str(r.uid): r for r in rows}


_RMS_AUDIT_ACTION_LABELS = {
    "created": "Created",
    "updated": "Updated",
    "status_changed": "Status Changed",
    "submitted": "Submitted",
    "progress_updated": "Progress Updated",
    "comment_added": "Comment Added",
    "attachment_uploaded": "Attachment Uploaded",
    "file_downloaded": "File Downloaded",
    "file_previewed": "File Previewed",
    "reminder_sent": "Reminder Sent",
    "reassigned": "Reassigned",
    "deleted": "Deleted",
}


def _rms_audit_trail_queryset(request):
    qs = (
        AuditLog.objects.filter(model_name="RmsReport")
        .select_related("user", "department")
        .order_by("-created_at")
    )
    action = (request.GET.get("action") or "").strip().lower()
    if action and action not in ("all", "any"):
        qs = qs.filter(action=action)
    date_filter = (request.GET.get("date_filter") or "").strip().lower()
    now = timezone.now()
    if date_filter == "today":
        qs = qs.filter(created_at__date=timezone.localdate())
    elif date_filter == "yesterday":
        qs = qs.filter(created_at__date=timezone.localdate() - timedelta(days=1))
    elif date_filter in ("week",):
        qs = qs.filter(created_at__gte=now - timedelta(days=7))
    elif date_filter in ("month",):
        qs = qs.filter(created_at__gte=now - timedelta(days=30))
    term = (request.GET.get("search") or "").strip()
    if term:
        q = (
            Q(object_repr__icontains=term)
            | Q(object_id__icontains=term)
            | Q(user__email__icontains=term)
            | Q(user__first_name__icontains=term)
            | Q(user__last_name__icontains=term)
        )
        try:
            q |= Q(
                object_id__in=[
                    str(u)
                    for u in RmsReport.objects.filter(
                        reference_number__icontains=term
                    ).values_list("uid", flat=True)[:300]
                ]
            )
        except Exception:
            pass
        qs = qs.filter(q)
    return qs


def _rms_resolve_financial_period(
    r: RmsReport, fy: SpismFinancialYear | None
) -> dict | None:
    if not fy:
        return None
    freq = _rms_normalize_report_frequency(r.report_type.frequency)
    ptype = {
        "quarterly": "quarter",
        "monthly": "month",
        "biannual": "biannual",
        "annual": "annual",
        "adhoc": "adhoc",
    }.get(freq)
    if not ptype:
        return None
    payloads = _rms_financial_period_payloads(fy, ptype)
    lookup = set()
    if r.financial_period_uids:
        lookup.update(str(x) for x in r.financial_period_uids)
    if r.financial_period_uid:
        lookup.add(str(r.financial_period_uid))
    for p in payloads:
        if p["uid"] in lookup:
            return {
                "uid": p["uid"],
                "display_name": p["display_name"],
                "start_date": p["start_date"],
                "end_date": p["end_date"],
            }
    return payloads[0] if payloads else None


def _rms_report_list_row(r: RmsReport) -> dict:
    done, pending, total = _rms_period_metrics(r)
    dl_state, days_until = _rms_deadline_state_and_days(r.deadline_date)
    dept = r.department
    freq = (r.report_type.frequency or "").lower()
    prog = r.progress_percentage
    if _rms_uses_per_period_implementation(r) and total > 0:
        prog = int(round(100 * done / total))
    return {
        "uid": str(r.uid),
        "reference_number": r.reference_number,
        "title": r.title,
        "report_type_name": r.report_type.name,
        "report_type_frequency": freq,
        "department_name": dept.name if dept else "",
        "directory_name": dept.name if dept else "",
        "deadline_date": r.deadline_date.isoformat() if r.deadline_date else None,
        "deadline_state": dl_state,
        "days_until_deadline": days_until,
        "status": r.status,
        "progress_percentage": prog,
        "period_done_count": done,
        "period_pending_count": pending,
        "period_total_count": total,
        "financial_year_uid": str(r.financial_year_uid),
    }


def _rms_report_to_detail_dict(request, r: RmsReport) -> dict:
    fy = SpismFinancialYear.objects.filter(
        uid=r.financial_year_uid, is_deleted=False
    ).first()
    done, pending, total = _rms_period_metrics(r)
    dl_state, days_until = _rms_deadline_state_and_days(r.deadline_date)
    freq = (r.report_type.frequency or "").lower()
    progress = r.progress_percentage
    if _rms_uses_per_period_implementation(r) and total > 0:
        progress = int(round(100 * done / total))
    att = None
    if r.attachment:
        att = request.build_absolute_uri(r.attachment.url)
    dept = r.department
    stakeholder_obj = r.stakeholder
    effective_stakeholder = ""
    if stakeholder_obj:
        effective_stakeholder = stakeholder_obj.name
    elif r.other_stakeholder_name:
        effective_stakeholder = r.other_stakeholder_name.strip()
    return {
        "uid": str(r.uid),
        "title": r.title,
        "reference_number": r.reference_number,
        "status": r.status,
        "priority": r.priority,
        "scope": r.scope,
        "deadline_date": r.deadline_date.isoformat() if r.deadline_date else None,
        "deadline_state": dl_state,
        "days_until_deadline": days_until,
        "progress_percentage": progress,
        "description": r.description,
        "notes": r.notes,
        "report_type": RmsReportTypeSerializer(r.report_type).data,
        "financial_year": _rms_financial_year_dict(fy) if fy else None,
        "financial_period": _rms_resolve_financial_period(r, fy),
        "category": RmsReportCategorySerializer(r.category).data
        if r.category_id
        else None,
        "department": {
            "uid": str(dept.uid),
            "name": dept.name,
            "code": dept.code,
        }
        if dept
        else None,
        "directory": {
            "uid": str(dept.uid),
            "name": dept.name,
            "code": dept.code,
        }
        if dept
        else None,
        "stakeholder": RmsStakeholderSerializer(stakeholder_obj).data
        if stakeholder_obj
        else None,
        "other_stakeholder_name": r.other_stakeholder_name,
        "effective_stakeholder_name": effective_stakeholder,
        "created_by_name": _rms_user_display_name(r.created_by),
        "attachment": att,
        "quarter_submissions": _rms_build_quarter_submissions(request, r, fy),
        "progress_updates": _rms_progress_updates_for_report(r),
    }


class RmsReportsGroupedListView(RmsProtectedAPIView):
    """GET /api/reports/reports-grouped — paginated list for RMS reports table."""

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request):
        qs = (
            RmsReport.objects.filter(is_deleted=False)
            .select_related("report_type", "department")
            .order_by("-created_at")
        )
        fy_f = (request.GET.get("financial_year_uid") or "").strip()
        if fy_f:
            try:
                qs = qs.filter(financial_year_uid=uuid.UUID(fy_f))
            except ValueError:
                pass
        rt_f = (request.GET.get("report_type_uid") or "").strip()
        if rt_f:
            try:
                qs = qs.filter(report_type__uid=uuid.UUID(rt_f))
            except ValueError:
                pass
        dep_f = (request.GET.get("department_uid") or request.GET.get("directorate_uid") or "").strip()
        if dep_f and rms_institution_scope(request.user):
            try:
                qs = qs.filter(department__uid=uuid.UUID(dep_f))
            except ValueError:
                pass
        cat_f = (request.GET.get("category_uid") or "").strip()
        if cat_f:
            try:
                qs = qs.filter(category__uid=uuid.UUID(cat_f))
            except ValueError:
                pass
        st_f = (request.GET.get("stakeholder_uid") or "").strip()
        if st_f:
            try:
                qs = qs.filter(stakeholder__uid=uuid.UUID(st_f))
            except ValueError:
                pass
        status_f = (request.GET.get("status") or "").strip()
        if status_f:
            statuses = [x.strip() for x in status_f.split(",") if x.strip()]
            if statuses:
                qs = qs.filter(status__in=statuses)
        priority_f = (request.GET.get("priority") or "").strip()
        if priority_f:
            prs = [x.strip() for x in priority_f.split(",") if x.strip()]
            if prs:
                qs = qs.filter(priority__in=prs)
        scope_f = (request.GET.get("scope") or "").strip()
        if scope_f:
            scs = [x.strip() for x in scope_f.split(",") if x.strip()]
            if scs:
                qs = qs.filter(scope__in=scs)
        ds_f = (request.GET.get("deadline_state") or "").strip()
        if ds_f:
            dstates = [x.strip() for x in ds_f.split(",") if x.strip()]
            dq = _rms_deadline_state_filter_q(dstates)
            if dq is not None:
                qs = qs.filter(dq)
        search = (request.GET.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search) | Q(reference_number__icontains=search)
            )
        qs = rms_apply_report_queryset_scope(request.user, qs)
        qs = qs.prefetch_related(
            Prefetch(
                "period_states",
                queryset=RmsReportPeriodState.objects.all(),
            )
        )
        paginated = str(request.GET.get("paginated", "")).lower() == "true"
        if not paginated:
            rows = [_rms_report_list_row(r) for r in qs[:500]]
            return CustomResponse.success(data=rows, message="Success")
        page = max(int(request.GET.get("page", 1) or 1), 1)
        page_size = min(max(int(request.GET.get("page_size", 10) or 10), 1), 500)
        total = qs.count()
        start = (page - 1) * page_size
        chunk = list(qs[start : start + page_size])
        rows = [_rms_report_list_row(r) for r in chunk]
        return CustomResponse.success(
            data=rows,
            pagination={"page": page, "page_size": page_size, "total": total},
            message="Success",
        )


class RmsReportCreateView(RmsProtectedAPIView):
    """POST /api/reports/reports/create — multipart form (ReportModal)."""

    rms_perm_map = {"POST": ("add_rmsreport",)}
    parser_classes = (FormParser, MultiPartParser)

    def post(self, request):
        data = _rms_form_to_dict(request)

        def gv(k: str, default: str = "") -> str:
            v = data.get(k, default)
            if isinstance(v, list):
                v = v[0] if v else default
            return (str(v) if v is not None else "").strip()

        title = gv("title")
        if len(title) < 5:
            return CustomResponse.errors(
                message="Validation failed",
                data={"title": ["Title must be at least 5 characters."]},
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            rt_uid = uuid.UUID(gv("report_type_uid"))
            fy_uid = uuid.UUID(gv("financial_year_uid"))
        except ValueError:
            return CustomResponse.errors(
                message="Validation failed",
                data={"report_type_uid": ["Invalid report type or financial year."]},
                code=STATUS_CODES["VALIDATION_ERROR"],
            )

        rt = RmsReportType.objects.filter(uid=rt_uid, is_deleted=False).first()
        if not rt:
            return CustomResponse.errors(
                message="Report type not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        fy = SpismFinancialYear.objects.filter(uid=fy_uid, is_deleted=False).first()
        if not fy:
            return CustomResponse.errors(
                message="Financial year not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )

        raw_uids = data.get("financial_period_uids")
        if isinstance(raw_uids, list):
            fin_uids = [str(x).strip() for x in raw_uids if str(x).strip()]
        elif raw_uids:
            fin_uids = [str(raw_uids).strip()]
        else:
            fin_uids = []
        fin_uid = gv("financial_period_uid")

        profile = (
            UserProfile.objects.filter(
                user=request.user, is_active=True, is_deleted=False
            )
            .select_related("department")
            .first()
        )
        dept = profile.department if profile else None

        cat = None
        cuid = gv("category_uid")
        if cuid:
            try:
                cat = RmsReportCategory.objects.filter(
                    uid=uuid.UUID(cuid), is_deleted=False
                ).first()
            except ValueError:
                pass

        st = None
        suid = gv("stakeholder_uid")
        if suid:
            try:
                st = RmsStakeholder.objects.filter(
                    uid=uuid.UUID(suid), is_deleted=False
                ).first()
            except ValueError:
                pass

        scope_val = gv("scope") or "internal"
        ext_err = _rms_external_scope_stakeholder_error(
            scope_val, st, gv("other_stakeholder_name"), suid
        )
        if ext_err:
            return ext_err

        freq = (rt.frequency or "").strip().lower()
        deadline = _rms_compute_deadline_date(rt, fy, fin_uid, fin_uids)
        dd_raw = gv("deadline_date")
        if freq == "adhoc" and dd_raw:
            try:
                deadline = date.fromisoformat(dd_raw[:10])
            except ValueError:
                pass

        ref_tmp = f"TMP-{uuid.uuid4().hex[:16].upper()}"
        report = RmsReport(
            reference_number=ref_tmp,
            title=title,
            report_type=rt,
            category=cat,
            financial_year_uid=fy_uid,
            financial_period_uid=fin_uid,
            financial_period_uids=list(fin_uids),
            scope=scope_val,
            priority=gv("priority") or "medium",
            status="draft",
            deadline_date=deadline,
            stakeholder=st,
            other_stakeholder_name=gv("other_stakeholder_name"),
            description=gv("description"),
            notes=gv("notes"),
            department=dept,
            created_by=request.user,
            updated_by=request.user,
        )
        f = request.FILES.get("attachment")
        if f:
            report.attachment = f
        report.save()
        report.reference_number = f"PPAA-{report.created_at.year}-{report.pk:05d}"
        report.save(update_fields=["reference_number"])
        report.refresh_from_db()
        _rms_report_audit_log(
            request,
            report,
            "created",
            {
                "comments": "Report created",
                "new_value": report.reference_number,
            },
        )
        if f:
            _rms_report_audit_log(
                request,
                report,
                "attachment_uploaded",
                {
                    "new_value": os.path.basename(f.name),
                    "comments": "Attachment uploaded on create",
                },
            )
        return CustomResponse.success(
            data=_rms_report_to_detail_dict(request, report), message="Created"
        )


class RmsReportDetailView(RmsProtectedAPIView):
    """GET /api/reports/reports/<uid>"""

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request, uid):
        r = (
            RmsReport.objects.filter(uid=uid, is_deleted=False)
            .select_related(
                "report_type",
                "category",
                "stakeholder",
                "department",
                "created_by",
            )
            .prefetch_related(
                Prefetch(
                    "progress_entries",
                    queryset=RmsReportProgressEntry.objects.select_related(
                        "created_by"
                    ).order_by("created_at"),
                ),
                Prefetch(
                    "period_states",
                    queryset=RmsReportPeriodState.objects.all(),
                ),
            )
            .first()
        )
        if not r:
            return CustomResponse.errors(
                message="Report not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        if not rms_user_can_access_report(request.user, r):
            return _rms_report_forbidden()
        return CustomResponse.success(
            data=_rms_report_to_detail_dict(request, r), message="Success"
        )


class RmsReportUpdateView(RmsProtectedAPIView):
    """PUT /api/reports/reports/<uid>/update"""

    rms_perm_map = {"PUT": ("change_rmsreport",)}
    parser_classes = (FormParser, MultiPartParser)

    def put(self, request, uid):
        r = RmsReport.objects.filter(uid=uid, is_deleted=False).first()
        if not r:
            return CustomResponse.errors(
                message="Report not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        if not rms_user_can_access_report(request.user, r):
            return _rms_report_forbidden()
        data = _rms_form_to_dict(request)

        def gv(k: str, default: str = "") -> str:
            v = data.get(k, default)
            if isinstance(v, list):
                v = v[0] if v else default
            return (str(v) if v is not None else "").strip()

        if gv("title"):
            r.title = gv("title")
        if gv("financial_year_uid"):
            try:
                r.financial_year_uid = uuid.UUID(gv("financial_year_uid"))
            except ValueError:
                pass
        raw_uids = data.get("financial_period_uids")
        if isinstance(raw_uids, list):
            r.financial_period_uids = [str(x).strip() for x in raw_uids if str(x).strip()]
        elif raw_uids:
            r.financial_period_uids = [str(raw_uids).strip()]
        if "financial_period_uid" in data:
            r.financial_period_uid = gv("financial_period_uid")
        if gv("scope"):
            r.scope = gv("scope")
        if gv("priority"):
            r.priority = gv("priority")
        if gv("description") is not None:
            r.description = gv("description")
        if gv("notes") is not None:
            r.notes = gv("notes")
        if gv("other_stakeholder_name") is not None:
            r.other_stakeholder_name = gv("other_stakeholder_name")
        cuid = gv("category_uid")
        if cuid:
            try:
                r.category = RmsReportCategory.objects.filter(
                    uid=uuid.UUID(cuid), is_deleted=False
                ).first()
            except ValueError:
                pass
        elif "category_uid" in data and not cuid:
            r.category = None
        suid = gv("stakeholder_uid")
        if suid:
            try:
                r.stakeholder = RmsStakeholder.objects.filter(
                    uid=uuid.UUID(suid), is_deleted=False
                ).first()
            except ValueError:
                pass
        elif "stakeholder_uid" in data and not suid:
            r.stakeholder = None

        fy = SpismFinancialYear.objects.filter(
            uid=r.financial_year_uid, is_deleted=False
        ).first()
        r.deadline_date = _rms_compute_deadline_date(
            r.report_type,
            fy,
            r.financial_period_uid,
            r.financial_period_uids or [],
        )
        dd_raw = gv("deadline_date")
        if (r.report_type.frequency or "").strip().lower() == "adhoc" and dd_raw:
            try:
                r.deadline_date = date.fromisoformat(dd_raw[:10])
            except ValueError:
                pass

        f = request.FILES.get("attachment")
        if f:
            r.attachment = f
        r.updated_by = request.user
        ext_err = _rms_external_scope_stakeholder_error(
            r.scope or "internal",
            r.stakeholder,
            r.other_stakeholder_name or "",
            gv("stakeholder_uid"),
        )
        if ext_err:
            return ext_err
        r.save()
        r.refresh_from_db()
        _rms_report_audit_log(
            request,
            r,
            "updated",
            {"comments": "Report updated"},
        )
        if f:
            _rms_report_audit_log(
                request,
                r,
                "attachment_uploaded",
                {
                    "new_value": (getattr(f, "name", "") or "").split("/")[-1],
                    "comments": "Main report attachment uploaded or replaced",
                },
            )
        return CustomResponse.success(
            data=_rms_report_to_detail_dict(request, r), message="Updated"
        )


class RmsReportProgressView(RmsProtectedAPIView):
    """POST /api/reports/reports/<uid>/progress — save progress % and notes."""

    rms_perm_map = {"POST": ("add_rmsreportprogressentry",)}

    def post(self, request, uid):
        r = (
            RmsReport.objects.filter(uid=uid, is_deleted=False)
            .select_related("report_type")
            .first()
        )
        if not r:
            return CustomResponse.errors(
                message="Report not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        if not rms_user_can_access_report(request.user, r):
            return _rms_report_forbidden()
        if (r.status or "").lower() == "submitted":
            return CustomResponse.errors(
                message="Cannot update progress on a submitted report",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            percentage = int(request.data.get("percentage", 0))
        except (TypeError, ValueError):
            return CustomResponse.errors(
                message="Validation failed",
                data={"percentage": ["Must be an integer between 0 and 100."]},
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        if percentage < 0 or percentage > 100:
            return CustomResponse.errors(
                message="Validation failed",
                data={"percentage": ["Must be between 0 and 100."]},
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        notes = (request.data.get("notes") or "").strip()

        if _rms_uses_per_period_implementation(r):
            pu = (request.data.get("financial_period_uid") or "").strip()
            allowed = set(_rms_ordered_period_uids(r))
            if not pu or pu not in allowed:
                return CustomResponse.errors(
                    message="Validation failed",
                    data={
                        "financial_period_uid": [
                            "Select a valid implementation period (e.g. Q1–Q4)."
                        ]
                    },
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            st, _ = RmsReportPeriodState.objects.get_or_create(
                report=r,
                period_uid=pu,
                defaults={
                    "progress_percentage": 0,
                    "status": "pending",
                    "updated_by": request.user,
                },
            )
            if (st.status or "").lower() == "submitted":
                return CustomResponse.errors(
                    message="This period is already submitted",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            if percentage == st.progress_percentage and not notes:
                return CustomResponse.errors(
                    message="No changes to save",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            st.progress_percentage = percentage
            if (st.status or "").lower() == "pending" and percentage > 0:
                st.status = "in_progress"
            st.updated_by = request.user
            st.save(
                update_fields=[
                    "progress_percentage",
                    "status",
                    "updated_at",
                    "updated_by",
                ]
            )
            RmsReportProgressEntry.objects.create(
                report=r,
                period_uid=pu,
                percentage=percentage,
                notes=notes,
                created_by=request.user,
            )
            _sync_report_aggregate_from_periods(r, request.user)
            _rms_report_audit_log(
                request,
                r,
                "progress_updated",
                {
                    "new_value": f"{pu}: {percentage}%",
                    "comments": notes or None,
                },
            )
        else:
            if percentage == r.progress_percentage and not notes:
                return CustomResponse.errors(
                    message="No changes to save",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            RmsReportProgressEntry.objects.create(
                report=r,
                period_uid="",
                percentage=percentage,
                notes=notes,
                created_by=request.user,
            )
            r.progress_percentage = percentage
            r.updated_by = request.user
            r.save(update_fields=["progress_percentage", "updated_at", "updated_by"])
            _rms_report_audit_log(
                request,
                r,
                "progress_updated",
                {
                    "new_value": f"{percentage}%",
                    "comments": notes or None,
                },
            )

        r = (
            RmsReport.objects.filter(pk=r.pk, is_deleted=False)
            .select_related(
                "report_type",
                "category",
                "stakeholder",
                "department",
                "created_by",
            )
            .prefetch_related(
                Prefetch(
                    "progress_entries",
                    queryset=RmsReportProgressEntry.objects.select_related(
                        "created_by"
                    ).order_by("created_at"),
                ),
                Prefetch(
                    "period_states",
                    queryset=RmsReportPeriodState.objects.all(),
                ),
            )
            .first()
        )
        return CustomResponse.success(
            data=_rms_report_to_detail_dict(request, r), message="Success"
        )


class RmsReportSubmitView(RmsProtectedAPIView):
    """POST /api/reports/reports/<uid>/submit — multipart: notes, optional attachment."""

    rms_perm_map = {"POST": ("change_rmsreport",)}
    parser_classes = (FormParser, MultiPartParser)

    def post(self, request, uid):
        r = (
            RmsReport.objects.filter(uid=uid, is_deleted=False)
            .select_related("report_type")
            .first()
        )
        if not r:
            return CustomResponse.errors(
                message="Report not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        if not rms_user_can_access_report(request.user, r):
            return _rms_report_forbidden()
        if (r.status or "").lower() == "submitted":
            return CustomResponse.errors(
                message="Report is already submitted",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )

        data = _rms_form_to_dict(request)

        def gv(k: str, default: str = "") -> str:
            v = data.get(k, default)
            if isinstance(v, list):
                v = v[0] if v else default
            return (str(v) if v is not None else "").strip()

        notes = gv("notes")
        f = request.FILES.get("attachment")
        rt = r.report_type

        if _rms_uses_per_period_implementation(r):
            pu = gv("financial_period_uid")
            allowed = _rms_ordered_period_uids(r)
            if not pu or pu not in allowed:
                return CustomResponse.errors(
                    message="Validation failed",
                    data={
                        "financial_period_uid": [
                            "Select which quarter or period you are submitting."
                        ]
                    },
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            st, _ = RmsReportPeriodState.objects.get_or_create(
                report=r,
                period_uid=pu,
                defaults={
                    "progress_percentage": 0,
                    "status": "pending",
                    "updated_by": request.user,
                },
            )
            if (st.status or "").lower() == "submitted":
                return CustomResponse.errors(
                    message="This period is already submitted",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            if rt.requires_attachment and not f and not st.attachment:
                return CustomResponse.errors(
                    message="This report type requires an attachment to submit.",
                    data={"attachment": ["Please upload a document."]},
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            if f:
                st.attachment = f
            st.status = "submitted"
            st.progress_percentage = 100
            st.submitted_at = timezone.now()
            st.updated_by = request.user
            if notes:
                prev = (st.notes or "").strip()
                st.notes = f"{prev}\n{notes}".strip() if prev else notes
            st.save()
            RmsReportProgressEntry.objects.create(
                report=r,
                period_uid=pu,
                percentage=100,
                notes=notes or "Period submitted",
                created_by=request.user,
            )
            _sync_report_aggregate_from_periods(r, request.user)
            _rms_report_audit_log(
                request,
                r,
                "submitted",
                {
                    "comments": notes or None,
                    "new_value": f"{pu}: submitted",
                },
            )
            if f:
                _rms_report_audit_log(
                    request,
                    r,
                    "attachment_uploaded",
                    {
                        "new_value": os.path.basename(f.name),
                        "comments": f"Attachment uploaded on submit (period {pu})",
                    },
                )
        else:
            if rt.requires_attachment and not f and not r.attachment:
                return CustomResponse.errors(
                    message="This report type requires an attachment to submit.",
                    data={"attachment": ["Please upload a document."]},
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

            if f:
                r.attachment = f
            if notes:
                sep = "\n\n--- Submission ---\n"
                if (r.notes or "").strip():
                    r.notes = f"{r.notes.strip()}{sep}{notes}"
                else:
                    r.notes = notes

            r.status = "submitted"
            r.progress_percentage = 100
            r.updated_by = request.user
            r.save()
            RmsReportProgressEntry.objects.create(
                report=r,
                period_uid="",
                percentage=100,
                notes=notes or "Report submitted",
                created_by=request.user,
            )
            _rms_report_audit_log(
                request,
                r,
                "submitted",
                {"comments": notes or None, "new_value": "submitted"},
            )
            if f:
                _rms_report_audit_log(
                    request,
                    r,
                    "attachment_uploaded",
                    {
                        "new_value": os.path.basename(f.name),
                        "comments": "Attachment on report submit",
                    },
                )

        r = (
            RmsReport.objects.filter(pk=r.pk, is_deleted=False)
            .select_related(
                "report_type",
                "category",
                "stakeholder",
                "department",
                "created_by",
            )
            .prefetch_related(
                Prefetch(
                    "progress_entries",
                    queryset=RmsReportProgressEntry.objects.select_related(
                        "created_by"
                    ).order_by("created_at"),
                ),
                Prefetch(
                    "period_states",
                    queryset=RmsReportPeriodState.objects.all(),
                ),
            )
            .first()
        )
        return CustomResponse.success(
            data=_rms_report_to_detail_dict(request, r), message="Submitted"
        )


def _rms_report_attachment_file(r: RmsReport, financial_period_uid: str):
    """Return a FileField (or None) for main report or a specific implementation period."""
    pu = (financial_period_uid or "").strip()
    if pu:
        st = RmsReportPeriodState.objects.filter(report=r, period_uid=pu).first()
        if st and st.attachment:
            return st.attachment
        return None
    if r.attachment:
        return r.attachment
    return None


class RmsReportAttachmentPreviewView(RmsProtectedAPIView):
    """GET /api/reports/reports/<uid>/preview — optional ?financial_period_uid= for per-period file."""

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request, uid):
        r = RmsReport.objects.filter(uid=uid, is_deleted=False).first()
        if not r:
            raise Http404
        if not rms_user_can_access_report(request.user, r):
            return _rms_report_forbidden()
        pu = (request.GET.get("financial_period_uid") or "").strip()
        field = _rms_report_attachment_file(r, pu)
        if not field:
            raise Http404
        content_type, _ = mimetypes.guess_type(field.name)
        fname = field.name.split("/")[-1]
        _rms_report_audit_log(
            request,
            r,
            "file_previewed",
            {
                "new_value": fname,
                "comments": f"Preview: {fname}"
                + (f" (period {pu})" if pu else " (main attachment)"),
            },
        )
        is_pdf = (content_type == "application/pdf") or fname.lower().endswith(".pdf")
        if is_pdf:
            try:
                raw = field.read()
            finally:
                try:
                    field.close()
                except Exception:
                    pass
            if raw.startswith(b"%PDF"):
                out_bytes = _rms_pdf_bytes_with_download_watermark(request, raw, r)
                resp = HttpResponse(out_bytes, content_type="application/pdf")
                resp["Content-Disposition"] = f'inline; filename="{fname}"'
                return resp
            resp = HttpResponse(raw, content_type=content_type or "application/octet-stream")
            resp["Content-Disposition"] = f'inline; filename="{fname}"'
            return resp
        resp = FileResponse(
            field.open("rb"),
            content_type=content_type or "application/octet-stream",
        )
        resp["Content-Disposition"] = f'inline; filename="{fname}"'
        return resp


class RmsReportAttachmentDownloadView(RmsProtectedAPIView):
    """GET /api/reports/reports/<uid>/download — optional ?financial_period_uid="""

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request, uid):
        r = RmsReport.objects.filter(uid=uid, is_deleted=False).first()
        if not r:
            raise Http404
        if not rms_user_can_access_report(request.user, r):
            return _rms_report_forbidden()
        pu = (request.GET.get("financial_period_uid") or "").strip()
        field = _rms_report_attachment_file(r, pu)
        if not field:
            raise Http404
        content_type, _ = mimetypes.guess_type(field.name)
        fname = field.name.split("/")[-1]
        try:
            raw = field.read()
        finally:
            try:
                field.close()
            except Exception:
                pass

        _rms_report_audit_log(
            request,
            r,
            "file_downloaded",
            {
                "new_value": fname,
                "comments": f"Download: {fname}"
                + (f" (period {pu})" if pu else " (main attachment)"),
            },
        )

        out_ct = content_type or "application/octet-stream"
        is_pdf = (out_ct == "application/pdf") or fname.lower().endswith(".pdf")
        if is_pdf and raw.startswith(b"%PDF"):
            out_bytes = _rms_pdf_bytes_with_download_watermark(request, raw, r)
            out_ct = "application/pdf"
        else:
            out_bytes = raw

        resp = HttpResponse(out_bytes, content_type=out_ct)
        safe = fname.replace('"', "_").replace("\r", "").replace("\n", "")
        resp["Content-Disposition"] = f'attachment; filename="{safe}"'
        return resp


class RmsReportAuditTrailForReportView(RmsProtectedAPIView):
    """GET /api/reports/reports/<uid>/audit-trail"""

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request, uid):
        r = RmsReport.objects.filter(uid=uid, is_deleted=False).first()
        if not r:
            return CustomResponse.errors(
                message="Report not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        if not rms_user_can_access_report(request.user, r):
            return _rms_report_forbidden()
        qs = (
            AuditLog.objects.filter(
                model_name="RmsReport",
                object_id=str(r.uid),
            )
            .select_related("user", "department")
            .order_by("-created_at")
        )
        paginated = str(request.GET.get("paginated", "")).lower() == "true"
        if not paginated:
            rows = [_rms_audit_row_for_report(log, r) for log in qs[:300]]
            return CustomResponse.success(data=rows, message="Success")
        page = max(int(request.GET.get("page", 1) or 1), 1)
        page_size = min(max(int(request.GET.get("page_size", 10) or 10), 1), 500)
        total = qs.count()
        start = (page - 1) * page_size
        chunk = qs[start : start + page_size]
        rows = [_rms_audit_row_for_report(log, r) for log in chunk]
        return CustomResponse.success(
            data=rows,
            pagination={"page": page, "page_size": page_size, "total": total},
            message="Success",
        )


class RmsReportDeleteView(RmsProtectedAPIView):
    """DELETE /api/reports/reports/<uid>/delete"""

    rms_perm_map = {"DELETE": ("delete_rmsreport",)}

    def delete(self, request, uid):
        r = RmsReport.objects.filter(uid=uid, is_deleted=False).first()
        if not r:
            return CustomResponse.errors(
                message="Report not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        if not rms_user_can_access_report(request.user, r):
            return _rms_report_forbidden()
        _rms_report_audit_log(
            request,
            r,
            "deleted",
            {
                "comments": "Report soft-deleted",
                "old_value": r.reference_number,
            },
        )
        r.is_deleted = True
        r.updated_by = request.user
        r.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(r.uid)}, message="Deleted")


def _rms_dashboard_base_qs(request, department_uid_override: str | None = None):
    """Active reports queryset with optional GET filters (FY, dept/directorate, scope, type)."""
    qs = RmsReport.objects.filter(is_deleted=False)
    fy_f = (request.GET.get("financial_year_uid") or "").strip()
    if fy_f:
        try:
            qs = qs.filter(financial_year_uid=uuid.UUID(fy_f))
        except ValueError:
            pass
    user = request.user
    if rms_institution_scope(user):
        dep = (
            (department_uid_override or "").strip()
            or (request.GET.get("department_uid") or "").strip()
            or (request.GET.get("directorate_uid") or "").strip()
        )
        if dep:
            try:
                qs = qs.filter(department__uid=uuid.UUID(dep))
            except ValueError:
                pass
    else:
        did = rms_reporter_department_id(user)
        if not did:
            qs = qs.none()
        else:
            qs = qs.filter(department_id=did)
    scope_f = (request.GET.get("scope") or "").strip()
    if scope_f:
        qs = qs.filter(scope=scope_f)
    rt_f = (request.GET.get("report_type_uid") or "").strip()
    if rt_f:
        try:
            qs = qs.filter(report_type__uid=uuid.UUID(rt_f))
        except ValueError:
            pass
    return qs.select_related("report_type", "category", "department")


def _rms_dashboard_stats_payload(
    request, department_uid_override: str | None = None
) -> dict:
    """Aggregate RMS metrics for director and ED dashboards (matches frontend shapes)."""
    qs = _rms_dashboard_base_qs(request, department_uid_override)
    total_reports = qs.count()
    today = timezone.localdate()
    now = timezone.now()
    month_start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    status_summary = {
        "pending": qs.exclude(
            status__in=("submitted", "in_progress")
        ).count(),
        "in_progress": qs.filter(status="in_progress").count(),
        "submitted": qs.filter(status="submitted").count(),
    }

    completed = qs.filter(status="submitted").count()
    overdue = (
        qs.exclude(status="submitted")
        .filter(deadline_date__isnull=False, deadline_date__lt=today)
        .count()
    )
    due_today = (
        qs.exclude(status="submitted").filter(deadline_date=today).count()
    )
    due_soon = (
        qs.exclude(status="submitted")
        .filter(
            deadline_date__gt=today,
            deadline_date__lte=today + timedelta(days=7),
        )
        .count()
    )
    on_track = (
        qs.exclude(status="submitted")
        .filter(
            Q(deadline_date__gt=today + timedelta(days=7))
            | Q(deadline_date__isnull=True)
        )
        .count()
    )
    deadline_summary = {
        "on_track": on_track,
        "due_soon": due_soon,
        "due_today": due_today,
        "overdue": overdue,
        "completed": completed,
    }

    by_report_type = list(
        qs.values("report_type__uid", "report_type__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    for row in by_report_type:
        if row.get("report_type__uid") is not None:
            row["report_type__uid"] = str(row["report_type__uid"])

    by_category = list(
        qs.values("category__name", "category__color")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    for row in by_category:
        if not row.get("category__name"):
            row["category__name"] = "Uncategorized"
        if not row.get("category__color"):
            row["category__color"] = "#6c757d"

    by_department = list(
        qs.values("department__uid", "department__name", "department__code")
        .annotate(
            total=Count("id"),
            submitted=Count("id", filter=Q(status="submitted")),
            submitted_this_month=Count(
                "id",
                filter=Q(status="submitted", updated_at__gte=month_start_dt),
            ),
        )
        .order_by("-total")
    )
    for row in by_department:
        uid = row.get("department__uid")
        row["department__uid"] = str(uid) if uid else ""
        if not row.get("department__name"):
            row["department__name"] = "Unassigned"
        if row.get("department__code") in (None, ""):
            row["department__code"] = row["department__name"][:16] or "—"

    fy_sel = None
    fy_uid_s = (request.GET.get("financial_year_uid") or "").strip()
    if fy_uid_s:
        try:
            fy_obj = SpismFinancialYear.objects.filter(
                uid=uuid.UUID(fy_uid_s), is_deleted=False
            ).first()
            if fy_obj:
                fy_sel = _rms_financial_year_dict(fy_obj)
        except ValueError:
            pass

    upcoming_deadlines = []
    for r in (
        qs.exclude(status="submitted")
        .filter(deadline_date__gte=today)
        .select_related("report_type")
        .order_by("deadline_date")[:20]
    ):
        st, days = _rms_deadline_state_and_days(r.deadline_date)
        upcoming_deadlines.append(
            {
                "uid": str(r.uid),
                "title": r.title,
                "report_type_name": r.report_type.name if r.report_type else "",
                "days_until_deadline": days,
                "deadline_state": st,
                "deadline_date": r.deadline_date.isoformat()
                if r.deadline_date
                else None,
            }
        )

    recent_submissions = []
    for r in (
        qs.filter(status="submitted")
        .select_related("report_type")
        .order_by("-updated_at")[:5]
    ):
        recent_submissions.append(
            {
                "uid": str(r.uid),
                "title": r.title,
                "report_type_name": r.report_type.name if r.report_type else "",
                "submission_date": r.updated_at.isoformat()
                if r.updated_at
                else None,
            }
        )

    submitted_this_month = qs.filter(
        status="submitted", updated_at__gte=month_start_dt
    ).count()

    overdue_reports = []
    for r in (
        qs.exclude(status="submitted")
        .filter(deadline_date__isnull=False, deadline_date__lt=today)
        .select_related("report_type")
        .order_by("deadline_date")[:10]
    ):
        _, days = _rms_deadline_state_and_days(r.deadline_date)
        st = (r.status or "").lower()
        overdue_reports.append(
            {
                "uid": str(r.uid),
                "title": r.title,
                "reference_number": r.reference_number,
                "report_type_name": r.report_type.name if r.report_type else "",
                "deadline_date": r.deadline_date.isoformat()
                if r.deadline_date
                else None,
                "days_until_deadline": days,
                "status": r.status,
                "status_display": _RMS_STATUS_LABEL.get(st, r.status or ""),
            }
        )

    late_base = (
        qs.filter(status="submitted")
        .exclude(deadline_date__isnull=True)
        .annotate(_sub_date=TruncDate("updated_at"))
    )
    late_submissions_count = late_base.filter(_sub_date__gt=F("deadline_date")).count()
    late_submissions = []
    for r in (
        late_base.filter(_sub_date__gt=F("deadline_date"))
        .select_related("report_type", "department")
        .order_by("-updated_at")[:25]
    ):
        sub_d = r._sub_date
        days_late = (sub_d - r.deadline_date).days if sub_d and r.deadline_date else 0
        late_submissions.append(
            {
                "uid": str(r.uid),
                "title": r.title,
                "reference_number": r.reference_number,
                "report_type_name": r.report_type.name if r.report_type else "",
                "department_name": r.department.name if r.department else "",
                "directory_name": r.department.name if r.department else "",
                "deadline_date": r.deadline_date.isoformat()
                if r.deadline_date
                else None,
                "submission_date": r.updated_at.isoformat()
                if r.updated_at
                else None,
                "days_overdue_on_submission": days_late,
            }
        )

    return {
        "total_reports": total_reports,
        "status_summary": status_summary,
        "deadline_summary": deadline_summary,
        "by_report_type": by_report_type,
        "by_category": by_category,
        "by_department": by_department,
        "by_directory": by_department,
        "selected_financial_year": fy_sel,
        "due_today_count": due_today,
        "upcoming_deadlines": upcoming_deadlines,
        "recent_submissions": recent_submissions,
        "submitted_this_month": submitted_this_month,
        "overdue_reports": overdue_reports,
        "overdue_count": overdue,
        "late_submissions": late_submissions,
        "late_submissions_count": late_submissions_count,
    }


class RmsDashboardStatsView(RmsProtectedAPIView):
    """GET /api/reports/dashboard — aggregates for RMS director + ED dashboards."""

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request):
        return CustomResponse.success(
            data=_rms_dashboard_stats_payload(request), message="Success"
        )


class RmsDashboardDirectorateView(RmsProtectedAPIView):
    """GET /api/reports/dashboard/directorate/<uid> — same stats scoped to one department."""

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request, uid):
        if not rms_user_can_access_directorate_dashboard(request.user, str(uid)):
            return _rms_report_forbidden()
        return CustomResponse.success(
            data=_rms_dashboard_stats_payload(request, department_uid_override=str(uid)),
            message="Success",
        )


class RmsDashboardCalendarView(RmsProtectedAPIView):
    """GET /api/reports/dashboard/calendar — deadlines in a date range (optional filters)."""

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request):
        qs = _rms_dashboard_base_qs(request).exclude(deadline_date__isnull=True)
        start_s = (request.GET.get("start_date") or "").strip()
        end_s = (request.GET.get("end_date") or "").strip()
        if start_s:
            try:
                qs = qs.filter(deadline_date__gte=date.fromisoformat(start_s[:10]))
            except ValueError:
                pass
        if end_s:
            try:
                qs = qs.filter(deadline_date__lte=date.fromisoformat(end_s[:10]))
            except ValueError:
                pass
        events = []
        for r in qs.select_related("report_type").order_by("deadline_date")[:500]:
            events.append(
                {
                    "uid": str(r.uid),
                    "title": r.title,
                    "reference_number": r.reference_number,
                    "deadline_date": r.deadline_date.isoformat()
                    if r.deadline_date
                    else None,
                    "report_type_name": r.report_type.name if r.report_type else "",
                    "status": r.status,
                    "deadline_state": _rms_deadline_state_and_days(r.deadline_date)[0],
                }
            )
        return CustomResponse.success(data={"events": events}, message="Success")


class RmsFinancialYearCreateView(RmsProtectedAPIView):
    """POST /api/reports/financial-years/create — persists to SPISM financial years."""

    rms_requires_sys_admin = True

    def post(self, request):
        ser = SpismFinancialYearSerializer(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            ser.save(created_by=request.user, updated_by=request.user)
        except IntegrityError:
            return CustomResponse.errors(
                message="Validation failed",
                data={"name": ["A financial year with this name already exists."]},
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        return CustomResponse.success(
            data=_rms_financial_year_dict(ser.instance), message="Created"
        )


class RmsFinancialYearUpdateView(RmsProtectedAPIView):
    """PUT /api/reports/financial-years/<uid>/update"""

    rms_requires_sys_admin = True

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
        try:
            ser.save(updated_by=request.user)
        except IntegrityError:
            return CustomResponse.errors(
                message="Validation failed",
                data={"name": ["A financial year with this name already exists."]},
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        row.refresh_from_db()
        return CustomResponse.success(data=_rms_financial_year_dict(row), message="Updated")


class RmsFinancialYearDeleteView(RmsProtectedAPIView):
    """DELETE /api/reports/financial-years/<uid>/delete"""

    rms_requires_sys_admin = True

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


class RmsFinancialYearDetailView(RmsProtectedAPIView):
    """GET /api/reports/financial-years/<uid> — matches RMS Queries.getFinancialYears({ uid })."""

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request, uid):
        row = SpismFinancialYear.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Financial year not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        return CustomResponse.success(data=_rms_financial_year_dict(row), message="Success")


class RmsUserProfileForReportsView(RmsProtectedAPIView):
    """GET /api/reports/user-profile — current user's department for ReportModal (RMS)."""

    rms_perm_map = {"GET": ("view_rmsreport",)}

    def get(self, request):
        profile = (
            UserProfile.objects.filter(
                user=request.user, is_active=True, is_deleted=False
            )
            .select_related("department")
            .order_by("-updated_at")
            .first()
        )
        if not profile or not profile.department_id:
            return CustomResponse.success(
                data={"department": None}, message="Success"
            )
        dept = profile.department
        return CustomResponse.success(
            data={
                "department": {
                    "uid": str(dept.uid),
                    "name": dept.name,
                    "code": dept.code,
                }
            },
            message="Success",
        )


def _rms_audit_trail_list_rows(qs_slice):
    logs = list(qs_slice)
    by_uid = _rms_reports_by_uid_for_audit(logs)
    rows = []
    for log in logs:
        rid = (log.object_id or "").strip()
        report = by_uid.get(rid)
        rows.append(_rms_audit_trail_row(log, report))
    return rows


def _rms_audit_trail_stats_payload() -> dict:
    base = AuditLog.objects.filter(model_name="RmsReport")
    now = timezone.now()
    today = timezone.localdate()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    overall = {
        "today": base.filter(created_at__date=today).count(),
        "week": base.filter(created_at__gte=week_ago).count(),
        "month": base.filter(created_at__gte=month_ago).count(),
        "total": base.count(),
    }
    by_action: dict = {}
    for row in (
        base.values("action").annotate(total=Count("id")).order_by("-total")
    ):
        act = row["action"] or ""
        by_action[act] = {
            "label": _RMS_AUDIT_ACTION_LABELS.get(
                act, (act or "unknown").replace("_", " ").title()
            ),
            "total": row["total"],
        }
    top_raw = (
        base.filter(created_at__gte=week_ago, user_id__isnull=False)
        .values(
            "user__first_name",
            "user__last_name",
            "user__email",
        )
        .annotate(action_count=Count("id"))
        .order_by("-action_count")[:10]
    )
    most_active_users = [
        {
            "first_name": r.get("user__first_name") or "",
            "last_name": r.get("user__last_name") or "",
            "email": r.get("user__email") or "",
            "action_count": r["action_count"],
        }
        for r in top_raw
    ]
    return {
        "overall": overall,
        "by_action": by_action,
        "most_active_users": most_active_users,
    }


class RmsAuditTrailListView(RmsProtectedAPIView):
    """GET /api/reports/audit-trail — paginated RMS report activity log."""

    rms_requires_sys_admin = True

    def get(self, request):
        qs = _rms_audit_trail_queryset(request)
        paginated = str(request.GET.get("paginated", "")).lower() == "true"
        if not paginated:
            rows = _rms_audit_trail_list_rows(qs[:500])
            return CustomResponse.success(data=rows, message="Success")
        page = max(int(request.GET.get("page", 1) or 1), 1)
        page_size = min(max(int(request.GET.get("page_size", 10) or 10), 1), 500)
        total = qs.count()
        start = (page - 1) * page_size
        chunk = qs[start : start + page_size]
        rows = _rms_audit_trail_list_rows(chunk)
        return CustomResponse.success(
            data=rows,
            pagination={"page": page, "page_size": page_size, "total": total},
            message="Success",
        )


class RmsAuditTrailStatsView(RmsProtectedAPIView):
    """GET /api/reports/audit-trail/stats — summary for AuditTrailPage."""

    rms_requires_sys_admin = True

    def get(self, request):
        return CustomResponse.success(
            data=_rms_audit_trail_stats_payload(), message="Success"
        )
