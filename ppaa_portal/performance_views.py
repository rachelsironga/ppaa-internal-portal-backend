from decimal import Decimal
import re
import os
import base64
import uuid as _uuid_mod
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import HttpResponse
from urllib.parse import quote
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from utils.permissions import HasMethodPermission

from .pagination import CustomPagination
from .response_codes import CustomResponse, STATUS_CODES
from utils.minio_storage import MinioStorage

SPIMS_LOCAL_PREFIX = "spims_local_activity_documents"


def _save_spims_document_locally(file_base64: str, activity_uid: str, file_name: str) -> str:
    """Fallback: save SPIMS activity document to local disk when MinIO is unavailable."""
    if ';base64,' not in file_base64:
        raise ValueError("Invalid base64 format. Missing ';base64,'")
    header, data = file_base64.split(';base64,', 1)
    file_bytes = base64.b64decode(data)
    content_type = header.split(':')[-1]
    ext = content_type.split('/')[-1]
    if not file_name.lower().endswith(f".{ext}"):
        file_name = f"{file_name}.{ext}"
    unique_name = f"{_uuid_mod.uuid4().hex[:8]}_{file_name}"
    relative_dir = os.path.join(SPIMS_LOCAL_PREFIX, "activities", activity_uid or "unknown")
    absolute_dir = os.path.join(settings.MEDIA_ROOT, relative_dir)
    os.makedirs(absolute_dir, exist_ok=True)
    relative_path = os.path.join(relative_dir, unique_name)
    absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)
    with open(absolute_path, "wb") as f:
        f.write(file_bytes)
    return relative_path.replace("\\", "/")


def _read_spims_local_document(file_path: str) -> bytes:
    """Read bytes from local SPIMS document fallback storage."""
    normalized = str(file_path or "").lstrip("/")
    absolute_path = os.path.join(settings.MEDIA_ROOT, normalized)
    if not os.path.exists(absolute_path):
        return b""
    with open(absolute_path, "rb") as f:
        return f.read()


def _delete_spims_local_document(file_path: str) -> None:
    """Delete a locally stored SPIMS document if it exists."""
    normalized = str(file_path or "").lstrip("/")
    absolute_path = os.path.join(settings.MEDIA_ROOT, normalized)
    if os.path.exists(absolute_path):
        try:
            os.remove(absolute_path)
        except OSError:
            pass

from ppaa_performance.models import Objective, Target, Activity, QuarterlyData, KPIActual, ActivityDocument, FinancialYear, PerformanceAuditLog
from .performance_serializers import (
    FinancialYearSerializer,
    ObjectiveSerializer,
    TargetSerializer,
    TargetListSerializer,
    ActivitySerializer,
    ActivityListSerializer,
    ImplementationActivityListSerializer,
    ImplementationTargetListSerializer,
    QuarterlyDataSerializer,
    KPIActualSerializer,
    KPIActualWriteSerializer,
    ActivityDocumentSerializer,
    ActivityDocumentWriteSerializer,
)


TARGET_WEIGHT_MAX = Decimal("100")


def _validate_objective_weight_for_year(financial_year, new_weight, exclude_objective_uid=None):
    """
    Ensure total objective weight for the financial year does not exceed 100%.
    Returns (is_valid, error_message).
    """
    fy = (financial_year or "").strip()
    if not fy or new_weight is None:
        return True, None
    qs = Objective.objects.filter(is_deleted=False, financial_year=fy)
    if exclude_objective_uid:
        qs = qs.exclude(uid=exclude_objective_uid)
    existing_sum = qs.aggregate(s=Sum("weight"))["s"] or Decimal("0")
    total = existing_sum + Decimal(str(new_weight))
    if total > TARGET_WEIGHT_MAX:
        return False, (
            f"The total objective weight for financial year {fy} has reached 100%. "
            "Please adjust objective weights based on priority before adding another."
        )
    return True, None


def _validate_activity_weight_for_target(target, new_weight, planned_financial_year=None, exclude_activity_uid=None):
    """
    Ensure total activity weight under the target for the given financial year does not exceed 100%.
    Scopes by target + planned_financial_year. Activities with null/empty FY are grouped together.
    Returns (is_valid, error_message).
    """
    if not target or new_weight is None:
        return True, None
    qs = Activity.objects.filter(target=target, is_deleted=False)
    fy = (planned_financial_year or "").strip() or None
    if fy:
        qs = qs.filter(planned_financial_year=fy)
    else:
        qs = qs.filter(Q(planned_financial_year__isnull=True) | Q(planned_financial_year=""))
    if exclude_activity_uid:
        qs = qs.exclude(uid=exclude_activity_uid)
    existing_sum = qs.aggregate(s=Sum("weight"))["s"] or Decimal("0")
    total = existing_sum + Decimal(str(new_weight))
    if total > TARGET_WEIGHT_MAX:
        fy_label = fy or "no financial year"
        return False, (
            f"The total weight under the selected target for financial year {fy_label} has reached 100%. "
            "Please adjust the weight based on priority to continue."
        )
    return True, None


def _compute_activity_ai_percent(qd):
    """AI% = (Actual / Planned) * 100, cap 100. Save on QuarterlyData."""
    if not qd.activity.planned_value or qd.activity.planned_value <= 0:
        return
    pct = (qd.actual_value / qd.activity.planned_value) * 100
    qd.computed_ai_percent = min(Decimal("100"), pct)
    qd.save(update_fields=["computed_ai_percent"])


def _compute_kpi_percent(kpi_actual):
    """KPI% by direction: increase favorable = (actual/planned)*100; decrease = (planned/actual)*100; cap 100."""
    t = kpi_actual.target
    if not t or not t.kpi_planned_value or t.kpi_planned_value <= 0 or not kpi_actual.actual_value or kpi_actual.actual_value <= 0:
        return
    planned = t.kpi_planned_value
    actual = kpi_actual.actual_value
    if t.kpi_direction == "INCREASE":
        pct = (actual / planned) * 100
    else:
        pct = (planned / actual) * 100
    kpi_actual.computed_kpi_percent = min(Decimal("100"), pct)
    kpi_actual.save(update_fields=["computed_kpi_percent"])


def _status_color(status):
    colors = {
        "DRAFT": "#6c757d",
        "PENDING": "#ffc107",
        "APPROVED": "#28a745",
        "RETURNED": "#dc3545",
    }
    return colors.get(status, "#6c757d")


def _validate_financial_year_name(name):
    """Format must be YYYY/YYYY e.g. 2025/2026."""
    if not name or not isinstance(name, str):
        return False, "Name is required"
    name = name.strip()
    if not re.match(r"^\d{4}/\d{4}$", name):
        return False, "Format must be YYYY/YYYY (e.g. 2025/2026)"
    parts = name.split("/")
    if int(parts[1]) != int(parts[0]) + 1:
        return False, "End year must be start year + 1 (e.g. 2025/2026)"
    return True, name


def _create_performance_audit_log(
    request,
    *,
    entity_type,
    entity_id,
    action,
    model_name=None,
    object_repr=None,
    old_value=None,
    new_value=None,
    comment=None,
):
    """
    Helper to create a PerformanceAuditLog entry for SPISM.
    Mirrors the behaviour of the internal portal System Logs helper but targets PerformanceAuditLog.
    Never interrupts the main request flow.
    """
    try:
        user_id = None
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            user_id = user.id

        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "") or ""
        if user_agent:
            user_agent = user_agent[:500]

        PerformanceAuditLog.objects.create(
            entity_type=str(entity_type or "").lower(),
            entity_id=str(entity_id or ""),
            action=str(action or "").lower(),
            model_name=model_name,
            object_repr=(str(object_repr)[:300] if object_repr else None),
            old_value=old_value,
            new_value=new_value,
            comment=comment,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        # Never break the main request because of logging issues
        pass


class FinancialYearView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FinancialYearSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                obj = FinancialYear.objects.filter(uid=uid, is_deleted=False).first()
                if not obj:
                    return CustomResponse.errors(
                        message="Financial year not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                serializer = self.serializer_class(obj)
                return CustomResponse.success(data=serializer.data)
            qs = FinancialYear.objects.filter(is_deleted=False).order_by("-start_date")
            serializer = self.serializer_class(qs, many=True)
            return CustomResponse.success(data=serializer.data)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def post(self, request):
        try:
            name = (request.data.get("name") or "").strip()
            ok, msg = _validate_financial_year_name(name)
            if not ok:
                return CustomResponse.errors(message=msg, code=STATUS_CODES["VALIDATION_ERROR"])
            start_date = request.data.get("start_date")
            end_date = request.data.get("end_date")
            if not start_date or not end_date:
                return CustomResponse.errors(
                    message="Start date and end date are required",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            from datetime import datetime
            try:
                start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_d = datetime.strptime(end_date, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                return CustomResponse.errors(
                    message="Dates must be in YYYY-MM-DD format",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            if start_d >= end_d:
                return CustomResponse.errors(
                    message="Start date must be before end date",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            if FinancialYear.objects.filter(name=msg, is_deleted=False).exists():
                return CustomResponse.errors(
                    message=f"Financial year '{msg}' already exists",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    obj = serializer.save(created_by_id=request.user.id, updated_by_id=request.user.id)
                    _create_performance_audit_log(
                        request,
                        entity_type="financial_year",
                        entity_id=obj.uid,
                        action="create",
                        model_name="FinancialYear",
                        object_repr=obj.name,
                        old_value=None,
                        new_value=serializer.data,
                    )
                    return CustomResponse.success(
                        message="Financial year created successfully",
                        data=serializer.data,
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def put(self, request, uid):
        try:
            obj = FinancialYear.objects.filter(uid=uid, is_deleted=False).first()
            if not obj:
                return CustomResponse.errors(
                    message="Financial year not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            name = (request.data.get("name") or getattr(obj, "name", "") or "").strip()
            if name:
                ok, msg = _validate_financial_year_name(name)
                if not ok:
                    return CustomResponse.errors(message=msg, code=STATUS_CODES["VALIDATION_ERROR"])
            start_date = request.data.get("start_date") or getattr(obj, "start_date", None)
            end_date = request.data.get("end_date") or getattr(obj, "end_date", None)
            if start_date and end_date:
                from datetime import datetime
                try:
                    start_d = datetime.strptime(str(start_date), "%Y-%m-%d").date() if isinstance(start_date, str) else start_date
                    end_d = datetime.strptime(str(end_date), "%Y-%m-%d").date() if isinstance(end_date, str) else end_date
                    if start_d >= end_d:
                        return CustomResponse.errors(
                            message="Start date must be before end date",
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )
                except (ValueError, TypeError):
                    pass
            old_data = self.serializer_class(obj).data
            serializer = self.serializer_class(obj, data=request.data, partial=True)
            if serializer.is_valid():
                obj = serializer.save(updated_by_id=request.user.id)
                _create_performance_audit_log(
                    request,
                    entity_type="financial_year",
                    entity_id=obj.uid,
                    action="update",
                    model_name="FinancialYear",
                    object_repr=obj.name,
                    old_value=old_data,
                    new_value=serializer.data,
                )
                return CustomResponse.success(
                    message="Financial year updated successfully",
                    data=serializer.data,
                )
            return CustomResponse.errors(
                message="Validation failed",
                data=serializer.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def delete(self, request, uid):
        try:
            obj = FinancialYear.objects.filter(uid=uid, is_deleted=False).first()
            if not obj:
                return CustomResponse.errors(
                    message="Financial year not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            old_data = FinancialYearSerializer(obj).data
            obj.is_deleted = True
            obj.deleted_at = timezone.now()
            obj.save(update_fields=["is_deleted", "deleted_at"])
            _create_performance_audit_log(
                request,
                entity_type="financial_year",
                entity_id=obj.uid,
                action="delete",
                model_name="FinancialYear",
                object_repr=obj.name,
                old_value=old_data,
                new_value=None,
            )
            return CustomResponse.success(message="Financial year deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class ObjectiveView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ObjectiveSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                obj = Objective.objects.filter(uid=uid, is_deleted=False).first()
                if not obj:
                    return CustomResponse.errors(
                        message="Objective not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                serializer = self.serializer_class(obj)
                return CustomResponse.success(data=serializer.data)
            search = request.GET.get("search", "")
            financial_year = request.GET.get("financial_year", "")
            status = request.GET.get("status", "")
            qs = Objective.objects.filter(is_deleted=False)
            if search:
                qs = qs.filter(
                    Q(title__icontains=search) | Q(description__icontains=search)
                )
            if financial_year:
                qs = qs.filter(financial_year=financial_year)
            if status:
                qs = qs.filter(status=status)
            qs = qs.order_by("-created_at")
            return CustomPagination.paginate(view_class=self, results=qs, request=request)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    new_weight = serializer.validated_data.get("weight")
                    financial_year = serializer.validated_data.get("financial_year")
                    valid, err_msg = _validate_objective_weight_for_year(financial_year, new_weight)
                    if not valid:
                        return CustomResponse.errors(
                            message=err_msg,
                            data={"weight": [err_msg]},
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )
                    obj = serializer.save(
                        created_by_id=request.user.id,
                        updated_by_id=request.user.id,
                    )
                    _create_performance_audit_log(
                        request,
                        entity_type="objective",
                        entity_id=obj.uid,
                        action="create",
                        model_name="Objective",
                        object_repr=obj.title,
                        old_value=None,
                        new_value=serializer.data,
                    )
                    return CustomResponse.success(
                        message="Objective created successfully",
                        data=serializer.data,
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def put(self, request, uid):
        try:
            with transaction.atomic():
                obj = Objective.objects.filter(uid=uid, is_deleted=False).first()
                if not obj:
                    return CustomResponse.errors(
                        message="Objective not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                old_data = self.serializer_class(obj).data
                serializer = self.serializer_class(obj, data=request.data, partial=True)
                if serializer.is_valid():
                    new_weight = serializer.validated_data.get("weight")
                    if new_weight is None:
                        new_weight = getattr(obj, "weight", None)
                    financial_year = serializer.validated_data.get("financial_year") or getattr(
                        obj, "financial_year", None
                    )
                    valid, err_msg = _validate_objective_weight_for_year(
                        financial_year, new_weight, exclude_objective_uid=obj.uid
                    )
                    if not valid:
                        return CustomResponse.errors(
                            message=err_msg,
                            data={"weight": [err_msg]},
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )
                    obj = serializer.save(updated_by_id=request.user.id)
                    _create_performance_audit_log(
                        request,
                        entity_type="objective",
                        entity_id=obj.uid,
                        action="update",
                        model_name="Objective",
                        object_repr=obj.title,
                        old_value=old_data,
                        new_value=serializer.data,
                    )
                    return CustomResponse.success(
                        message="Objective updated successfully",
                        data=serializer.data,
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def delete(self, request, uid):
        try:
            obj = Objective.objects.filter(uid=uid, is_deleted=False).first()
            if not obj:
                return CustomResponse.errors(
                    message="Objective not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            old_data = ObjectiveSerializer(obj).data
            obj.is_deleted = True
            obj.deleted_at = timezone.now()
            obj.save(update_fields=["is_deleted", "deleted_at"])
            _create_performance_audit_log(
                request,
                entity_type="objective",
                entity_id=obj.uid,
                action="delete",
                model_name="Objective",
                object_repr=obj.title,
                old_value=old_data,
                new_value=None,
            )
            return CustomResponse.success(message="Objective deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class TargetView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TargetSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                obj = Target.objects.filter(uid=uid, is_deleted=False).first()
                if not obj:
                    return CustomResponse.errors(
                        message="Target not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                serializer = self.serializer_class(obj)
                return CustomResponse.success(data=serializer.data)
            objective_uid = request.GET.get("objective", "")
            financial_year = request.GET.get("financial_year", "")
            search = request.GET.get("search", "")
            qs = Target.objects.filter(is_deleted=False)
            if objective_uid:
                qs = qs.filter(objective__uid=objective_uid)
            if financial_year:
                # Support multi-select values like "2025/2026,2026/2027"
                years = [y.strip() for y in financial_year.split(",") if y.strip()]
                if years:
                    qs = qs.filter(objective__financial_year__in=years)
            if search:
                qs = qs.filter(
                    Q(title__icontains=search) | Q(description__icontains=search)
                )
            # Role-based visibility:
            # - Planning Managers and Approvers can see all targets.
            # - Performance Officers should only see targets assigned to them.
            try:
                is_officer = request.user.groups.filter(name="SPISM Performance Officer").exists()
                is_planning_manager = request.user.groups.filter(name="SPISM Planning Manager").exists()
                is_approver = request.user.groups.filter(name="SPISM Approver").exists()
                if is_officer and not is_planning_manager and not is_approver:
                    qs = qs.filter(responsible_officer_id=request.user.id)
            except Exception:
                # If group lookup fails, do not restrict the queryset.
                pass
            qs = qs.order_by("objective", "title")
            return CustomPagination.paginate(
                view_class=self, results=qs, request=request
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    obj = serializer.save(
                        created_by_id=request.user.id,
                        updated_by_id=request.user.id,
                    )
                    _create_performance_audit_log(
                        request,
                        entity_type="target",
                        entity_id=obj.uid,
                        action="create",
                        model_name="Target",
                        object_repr=obj.title,
                        old_value=None,
                        new_value=serializer.data,
                    )
                    return CustomResponse.success(
                        message="Target created successfully",
                        data=serializer.data,
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def put(self, request, uid):
        try:
            with transaction.atomic():
                obj = Target.objects.filter(uid=uid, is_deleted=False).first()
                if not obj:
                    return CustomResponse.errors(
                        message="Target not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                old_data = self.serializer_class(obj).data
                serializer = self.serializer_class(obj, data=request.data, partial=True)
                if serializer.is_valid():
                    obj = serializer.save(updated_by_id=request.user.id)
                    _create_performance_audit_log(
                        request,
                        entity_type="target",
                        entity_id=obj.uid,
                        action="update",
                        model_name="Target",
                        object_repr=obj.title,
                        old_value=old_data,
                        new_value=serializer.data,
                    )
                    return CustomResponse.success(
                        message="Target updated successfully",
                        data=serializer.data,
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def delete(self, request, uid):
        try:
            obj = Target.objects.filter(uid=uid, is_deleted=False).first()
            if not obj:
                return CustomResponse.errors(
                    message="Target not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            old_data = TargetSerializer(obj).data
            obj.is_deleted = True
            obj.deleted_at = timezone.now()
            obj.save(update_fields=["is_deleted", "deleted_at"])
            _create_performance_audit_log(
                request,
                entity_type="target",
                entity_id=obj.uid,
                action="delete",
                model_name="Target",
                object_repr=obj.title,
                old_value=old_data,
                new_value=None,
            )
            return CustomResponse.success(message="Target deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class PerformanceOfficersView(APIView):
    """List SPISM Performance Officers for assignment dropdown."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            User = get_user_model()
            qs = User.objects.filter(is_deleted=False, is_active=True, groups__name="SPISM Performance Officer").distinct()
            search = (request.GET.get("search") or "").strip()
            if search:
                qs = qs.filter(
                    Q(first_name__icontains=search)
                    | Q(last_name__icontains=search)
                    | Q(username__icontains=search)
                    | Q(email__icontains=search)
                )

            data = []
            for u in qs.order_by("first_name", "last_name")[:500]:
                # Basic identity
                username = getattr(u, "username", "") or ""
                first_name = getattr(u, "first_name", "") or ""
                last_name = getattr(u, "last_name", "") or ""
                full_name = (u.get_full_name() or "").strip()
                if not full_name:
                    full_name = f"{first_name} {last_name}".strip() or username

                # Department & position info (mirroring internal portal style)
                dept_obj = getattr(u, "department", None)
                pos_obj = getattr(u, "position", None)

                # Try to get department/level from relations first
                dept_uid = getattr(dept_obj, "uid", None)
                dept_name = getattr(dept_obj, "name", "") or ""
                dept_code = getattr(dept_obj, "code", "") or ""
                level_uid = getattr(pos_obj, "uid", None)
                level_name = (
                    getattr(pos_obj, "level_name", "")
                    or getattr(pos_obj, "name", "")
                    or ""
                )
                level_code = getattr(pos_obj, "code", "") or ""

                # Fallback to computed "current_*" attributes used in the internal portal
                if not level_name:
                    level_name = getattr(u, "current_level_name", "") or ""
                if not dept_name:
                    dept_name = getattr(u, "current_department_name", "") or ""

                # Groups as names (like internal portal)
                groups = list(u.groups.values_list("name", flat=True))

                # Build a friendly label like "Full Name (Dept - Level)"
                extra = " - ".join([x for x in [dept_name, level_name] if x])
                label = f"{full_name}{f' ({extra})' if extra else ''}"

                data.append({
                    "id": u.id,
                    "guid": getattr(u, "guid", None) or getattr(u, "uid", None),
                    "uid": getattr(u, "uid", None),
                    "username": username,
                    "email": getattr(u, "email", "") or None,
                    "first_name": first_name or None,
                    "middle_name": getattr(u, "middle_name", None),
                    "last_name": last_name or None,
                    "full_name": full_name,
                    "status": "ACTIVE" if getattr(u, "is_active", False) else "INACTIVE",
                    "is_active": getattr(u, "is_active", False),
                    "is_staff": getattr(u, "is_staff", False),
                    "phone_number": getattr(u, "phone_number", "") or None,
                    "alternative_contact": getattr(u, "alternative_contact", "") or None,
                    "groups": groups,
                    # Position block similar to internal portal
                    "position": {
                        "department_uid": dept_uid,
                        "department_name": dept_name or None,
                        "department_code": dept_code or None,
                        "level_uid": level_uid,
                        "level_name": level_name or getattr(u, "current_level_name", None),
                        "level_code": level_code or None,
                    },
                    "current_level_name": level_name or getattr(u, "current_level_name", None),
                    "current_department_name": dept_name or getattr(u, "current_department_name", None),
                    # Convenience display label for dropdowns
                    "label": label,
                })
            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class TargetAssignOfficerView(APIView):
    """Assign responsible SPISM Performance Officer to a target."""
    permission_classes = [IsAuthenticated]

    def post(self, request, uid):
        try:
            target = Target.objects.filter(uid=uid, is_deleted=False).first()
            if not target:
                return CustomResponse.errors(message="Target not found", code=STATUS_CODES["DATA_NOT_FOUND"])

            # Only planning manager can assign
            try:
                if not request.user.groups.filter(name="SPISM Planning Manager").exists():
                    return CustomResponse.errors(
                        message="You are not allowed to assign targets.",
                        code=STATUS_CODES["PERMISSION_DENIED"],
                    )
            except Exception:
                pass

            officer_id = request.data.get("responsible_officer_id")
            if officer_id in (None, ""):
                return CustomResponse.errors(
                    message="responsible_officer_id is required.",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            User = get_user_model()
            officer = None

            # Accept either numeric id or uid string
            raw = str(officer_id).strip()
            tmp_id = None
            try:
                tmp_id = int(raw)
            except Exception:
                tmp_id = None

            if tmp_id:
                officer = User.objects.filter(id=tmp_id, is_deleted=False, is_active=True).first()
            if not officer:
                officer = User.objects.filter(uid=raw, is_deleted=False, is_active=True).first()

            if not officer:
                return CustomResponse.errors(message="Selected officer not found", code=STATUS_CODES["DATA_NOT_FOUND"])
            try:
                if not officer.groups.filter(name="SPISM Performance Officer").exists():
                    return CustomResponse.errors(
                        message="Selected user is not a SPISM Performance Officer.",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
            except Exception:
                pass

            old_data = TargetSerializer(target).data
            target.responsible_officer_id = officer.id
            target.assigned_at = timezone.now()
            target.assigned_by_id = request.user.id
            target.save(update_fields=["responsible_officer_id", "assigned_at", "assigned_by_id"])
            new_data = TargetSerializer(target).data
            _create_performance_audit_log(
                request,
                entity_type="target",
                entity_id=target.uid,
                action="assign_officer",
                model_name="Target",
                object_repr=target.title,
                old_value=old_data,
                new_value=new_data,
            )
            return CustomResponse.success(message="Officer assigned", data=new_data)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class ActivityView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ActivitySerializer

    def get(self, request, uid=None):
        try:
            if uid:
                obj = Activity.objects.filter(uid=uid, is_deleted=False).prefetch_related(
                    "quarterly_data"
                ).select_related("target").first()
                if not obj:
                    return CustomResponse.errors(
                        message="Activity not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                serializer = self.serializer_class(obj)
                return CustomResponse.success(data=serializer.data)
            target_uid = request.GET.get("target", "")
            search = request.GET.get("search", "")
            qs = Activity.objects.filter(is_deleted=False).prefetch_related(
                "quarterly_data"
            ).select_related("target")
            if target_uid:
                qs = qs.filter(target__uid=target_uid)
            if search:
                qs = qs.filter(
                    Q(title__icontains=search) | Q(description__icontains=search)
                )
            qs = qs.order_by("target", "title")
            return CustomPagination.paginate(
                view_class=self, results=qs, request=request
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    target = serializer.validated_data.get("target")
                    new_weight = serializer.validated_data.get("weight")
                    planned_fy = serializer.validated_data.get("planned_financial_year") or ""
                    if target:
                        target_with_obj = Target.objects.select_related("objective").filter(pk=target.pk).first()
                        if target_with_obj and (
                            target_with_obj.status != "APPROVED"
                            or (target_with_obj.objective and target_with_obj.objective.status != "APPROVED")
                        ):
                            return CustomResponse.errors(
                                message="Target and its objective must be approved before adding activities. (Structured hierarchical workflow: approve objective and target first, then add activities.)",
                                code=STATUS_CODES["VALIDATION_ERROR"],
                            )
                        valid, err_msg = _validate_activity_weight_for_target(
                            target, new_weight, planned_financial_year=planned_fy
                        )
                        if not valid:
                            return CustomResponse.errors(
                                message=err_msg,
                                code=STATUS_CODES["VALIDATION_ERROR"],
                            )
                    obj = serializer.save(
                        created_by_id=request.user.id,
                        updated_by_id=request.user.id,
                    )
                    _create_performance_audit_log(
                        request,
                        entity_type="activity",
                        entity_id=obj.uid,
                        action="create",
                        model_name="Activity",
                        object_repr=obj.title,
                        old_value=None,
                        new_value=serializer.data,
                    )
                    return CustomResponse.success(
                        message="Activity created successfully",
                        data=serializer.data,
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def put(self, request, uid):
        try:
            with transaction.atomic():
                obj = Activity.objects.select_related("target", "target__objective").filter(uid=uid, is_deleted=False).first()
                if not obj:
                    return CustomResponse.errors(
                        message="Activity not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                new_status = (request.data.get("status") or "").upper()
                if new_status == "PENDING":
                    if obj.target.status != "APPROVED" or (obj.target.objective and obj.target.objective.status != "APPROVED"):
                        return CustomResponse.errors(
                            message="Target and its objective must be approved before submitting this activity for approval.",
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )
                old_data = self.serializer_class(obj).data
                serializer = self.serializer_class(obj, data=request.data, partial=True)
                if serializer.is_valid():
                    target = serializer.validated_data.get("target") or obj.target
                    new_weight = serializer.validated_data.get("weight")
                    if new_weight is None:
                        new_weight = getattr(obj, "weight", None)
                    planned_fy = serializer.validated_data.get("planned_financial_year")
                    if planned_fy is None:
                        planned_fy = getattr(obj, "planned_financial_year", None) or ""
                    if new_weight is not None:
                        valid, err_msg = _validate_activity_weight_for_target(
                            target, new_weight,
                            planned_financial_year=planned_fy,
                            exclude_activity_uid=obj.uid,
                        )
                        if not valid:
                            return CustomResponse.errors(
                                message=err_msg,
                                code=STATUS_CODES["VALIDATION_ERROR"],
                            )
                    obj = serializer.save(updated_by_id=request.user.id)
                    _create_performance_audit_log(
                        request,
                        entity_type="activity",
                        entity_id=obj.uid,
                        action="update",
                        model_name="Activity",
                        object_repr=obj.title,
                        old_value=old_data,
                        new_value=serializer.data,
                    )
                    return CustomResponse.success(
                        message="Activity updated successfully",
                        data=serializer.data,
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def delete(self, request, uid):
        try:
            obj = Activity.objects.filter(uid=uid, is_deleted=False).first()
            if not obj:
                return CustomResponse.errors(
                    message="Activity not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            old_data = ActivitySerializer(obj).data
            obj.is_deleted = True
            obj.deleted_at = timezone.now()
            obj.save(update_fields=["is_deleted", "deleted_at"])
            _create_performance_audit_log(
                request,
                entity_type="activity",
                entity_id=obj.uid,
                action="delete",
                model_name="Activity",
                object_repr=obj.title,
                old_value=old_data,
                new_value=None,
            )
            return CustomResponse.success(message="Activity deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class ImplementationActivitiesView(APIView):
    """GET: List approved activities for Implementation page with quarterly/documents counts.

    Query params:
      financial_year — filter by activity planned_financial_year
      search — icontains on activity title, target title, objective title
      quarter — 1–4: activity planned for that quarter (planned_quarter or planned_quarters JSON)
      queue=implementation_approval — only activities with full implementation submit and/or
        quarters awaiting implementation approval (submitted but not approved)
      submitted_only — true: implementation_submitted_at is set (legacy; prefer queue)
      implementation_approval_filter — pending | approved (narrow queue results)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ImplementationActivityListSerializer

    def get(self, request):
        try:
            financial_year = (request.GET.get("financial_year") or "").strip()
            search = (request.GET.get("search") or "").strip()
            quarter_raw = (request.GET.get("quarter") or "").strip()
            queue = (request.GET.get("queue") or "").strip().lower()
            submitted_only = str(request.GET.get("submitted_only", "")).lower() in (
                "1", "true", "yes",
            )
            approval_filter = (request.GET.get("implementation_approval_filter") or "").strip().lower()

            base_qs = Activity.objects.filter(is_deleted=False, status="APPROVED").select_related(
                "target", "target__objective"
            )

            if financial_year:
                base_qs = base_qs.filter(planned_financial_year=financial_year)

            pending_q = Q(
                quarterly_data__is_locked=True,
                quarterly_data__implementation_status="SUBMITTED",
                quarterly_data__implementation_approved_at__isnull=True,
            )
            if financial_year:
                pending_q &= Q(quarterly_data__financial_year=financial_year)

            if financial_year:
                qs = base_qs.annotate(
                    quarterly_data_count=Count(
                        "quarterly_data",
                        filter=Q(quarterly_data__financial_year=financial_year),
                        distinct=True,
                    ),
                    documents_count=Count("documents", distinct=True),
                    pending_implementation_approval_count=Count(
                        "quarterly_data",
                        filter=pending_q,
                        distinct=True,
                    ),
                )
            else:
                qs = base_qs.annotate(
                    quarterly_data_count=Count("quarterly_data", distinct=True),
                    documents_count=Count("documents", distinct=True),
                    pending_implementation_approval_count=Count(
                        "quarterly_data",
                        filter=pending_q,
                        distinct=True,
                    ),
                )

            if search:
                qs = qs.filter(
                    Q(title__icontains=search)
                    | Q(target__title__icontains=search)
                    | Q(target__objective__title__icontains=search)
                )

            if quarter_raw:
                try:
                    pq = int(quarter_raw)
                    if pq in (1, 2, 3, 4):
                        qs = qs.filter(
                            Q(planned_quarter=pq) | Q(planned_quarters__contains=[pq])
                        )
                except (ValueError, TypeError):
                    pass

            if queue == "implementation_approval":
                qs = qs.filter(
                    Q(implementation_submitted_at__isnull=False)
                    | Q(pending_implementation_approval_count__gt=0)
                )
            elif submitted_only:
                qs = qs.filter(implementation_submitted_at__isnull=False)

            if approval_filter == "pending":
                qs = qs.filter(pending_implementation_approval_count__gt=0)
            elif approval_filter == "approved":
                qs = qs.filter(
                    pending_implementation_approval_count=0,
                    implementation_submitted_at__isnull=False,
                )

            qs = qs.order_by("target__objective", "target", "title")

            serializer = self.serializer_class(qs, many=True)
            return CustomResponse.success(data=serializer.data)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class ImplementationTargetsView(APIView):
    """GET: List approved targets for Implementation page KPI tab with kpi_actuals count."""
    permission_classes = [IsAuthenticated]
    serializer_class = ImplementationTargetListSerializer

    def get(self, request):
        try:
            financial_year = (request.GET.get("financial_year") or "").strip()
            base_qs = Target.objects.filter(is_deleted=False, status="APPROVED").select_related("objective")
            if financial_year:
                qs = (
                    base_qs.filter(objective__financial_year=financial_year)
                    .annotate(
                        kpi_actuals_count=Count(
                            "kpi_actuals",
                            filter=Q(kpi_actuals__financial_year=financial_year),
                            distinct=True,
                        ),
                    )
                    .order_by("objective", "title")
                )
            else:
                qs = base_qs.annotate(kpi_actuals_count=Count("kpi_actuals", distinct=True)).order_by(
                    "objective", "title"
                )
            serializer = self.serializer_class(qs, many=True)
            return CustomResponse.success(data=serializer.data)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class ActivitySubmitImplementationView(APIView):
    """POST: Submit implementation per quarter or for the whole activity.

    Body (optional):
      { "quarter": 1|2|3|4 }   — submit a single quarter
      {}                        — submit all remaining planned quarters at once
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, uid):
        try:
            from ppaa_performance.models import QuarterlyData as QD
            obj = Activity.objects.filter(uid=uid, is_deleted=False).select_related("target").first()
            if not obj:
                return CustomResponse.errors(
                    message="Activity not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            if obj.status != "APPROVED":
                return CustomResponse.errors(
                    message="Only approved activities can have implementation submitted.",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

            quarter_raw = request.data.get("quarter")
            planned_quarters = sorted(
                set(obj.planned_quarters or ([obj.planned_quarter] if obj.planned_quarter else []))
            )

            if quarter_raw is not None:
                # ── Per-quarter submission ──────────────────────────────────────
                try:
                    quarter = int(quarter_raw)
                    assert quarter in (1, 2, 3, 4)
                except (ValueError, TypeError, AssertionError):
                    return CustomResponse.errors(
                        message="Invalid quarter. Must be 1, 2, 3, or 4.",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                # DIRECT KPI: require at least one KPI actual before per-quarter submission too
                target = obj.target
                kpi_source_type = getattr(target, "kpi_source_type", "DERIVED") if target else "DERIVED"
                if kpi_source_type == "DIRECT" and obj.planned_financial_year:
                    has_kpi_actual = KPIActual.objects.filter(
                        target=target, financial_year=obj.planned_financial_year,
                    ).exists()
                    if not has_kpi_actual:
                        return CustomResponse.errors(
                            message=(
                                "This activity's target uses a Direct KPI. "
                                f"Please record at least one KPI actual value for "
                                f"'{obj.planned_financial_year}' before submitting Q{quarter}."
                            ),
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )
                fy = obj.planned_financial_year or ""
                qd = QD.objects.filter(activity=obj, quarter=quarter, financial_year=fy).first()
                if not qd:
                    return CustomResponse.errors(
                        message=f"No quarterly data found for Q{quarter} ({fy}). Please record actual data first.",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                if qd.is_locked:
                    return CustomResponse.errors(
                        message=f"Q{quarter} has already been submitted and is locked.",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                qd.implementation_status = "SUBMITTED"
                qd.implementation_submitted_at = timezone.now()
                qd.implementation_submitted_by_id = request.user.id
                qd.is_locked = True
                qd.save(update_fields=[
                    "implementation_status", "implementation_submitted_at",
                    "implementation_submitted_by_id", "is_locked",
                ])
                _create_performance_audit_log(
                    request,
                    entity_type="activity",
                    entity_id=obj.uid,
                    action="submit_quarter_implementation",
                    model_name="Activity",
                    object_repr=f"{obj.title} — Q{quarter}",
                    old_value={"quarter": quarter, "implementation_status": "DRAFT"},
                    new_value={"quarter": quarter, "implementation_status": "SUBMITTED"},
                )
                # Check if all planned quarters are now submitted
                all_locked = (
                    all(
                        QD.objects.filter(activity=obj, quarter=q, is_locked=True).exists()
                        for q in planned_quarters
                    )
                    if planned_quarters else False
                )
                if all_locked and not obj.implementation_submitted_at:
                    obj.implementation_submitted_at = timezone.now()
                    obj.implementation_submitted_by_id = request.user.id
                    obj.save(update_fields=["implementation_submitted_at", "implementation_submitted_by_id"])
                message = f"Q{quarter} submitted successfully."
                if all_locked:
                    message += " All planned quarters submitted — activity implementation is now fully locked."
            else:
                # ── Bulk submission (all remaining quarters) ────────────────────
                if obj.implementation_submitted_at:
                    return CustomResponse.errors(
                        message="Implementation for this activity has already been fully submitted and is locked.",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                target = obj.target
                kpi_source_type = getattr(target, "kpi_source_type", "DERIVED") if target else "DERIVED"
                if kpi_source_type == "DIRECT" and obj.planned_financial_year:
                    has_kpi_actual = KPIActual.objects.filter(
                        target=target, financial_year=obj.planned_financial_year,
                    ).exists()
                    if not has_kpi_actual:
                        return CustomResponse.errors(
                            message=(
                                "This activity's target uses a Direct KPI. "
                                "Please record at least one KPI actual value for "
                                f"'{obj.planned_financial_year}' before submitting."
                            ),
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )
                qd_qs = QD.objects.filter(activity=obj, is_locked=False)
                if obj.planned_financial_year:
                    qd_qs = qd_qs.filter(financial_year=obj.planned_financial_year)
                qd_qs.update(
                    implementation_status="SUBMITTED",
                    implementation_submitted_at=timezone.now(),
                    implementation_submitted_by_id=request.user.id,
                    is_locked=True,
                )
                obj.implementation_submitted_at = timezone.now()
                obj.implementation_submitted_by_id = request.user.id
                obj.save(update_fields=["implementation_submitted_at", "implementation_submitted_by_id"])
                _create_performance_audit_log(
                    request,
                    entity_type="activity",
                    entity_id=obj.uid,
                    action="submit_implementation",
                    model_name="Activity",
                    object_repr=obj.title,
                    old_value={"implementation_submitted_at": None},
                    new_value={"implementation_submitted_at": obj.implementation_submitted_at.isoformat()},
                )
                message = "Implementation submitted successfully. All quarterly data is now locked."

            serializer = ActivitySerializer(obj)
            return CustomResponse.success(message=message, data=serializer.data)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class ActivityImplementationApprovalView(APIView):
    """POST: Executive Secretariat approves or returns submitted quarterly implementation.

    Body:
      { "action": "approve" | "return", "comment": "..." (required for return),
        "quarter": 1–4 optional — one quarter only; omit / null to approve or return all pending quarters }
    """
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "post": [
            "can_approve_spism_implementation",
            "can_approve_spism_planning",
        ],
    }

    def post(self, request, uid):
        try:
            from ppaa_performance.models import QuarterlyData as QD

            with transaction.atomic():
                obj = Activity.objects.filter(uid=uid, is_deleted=False).select_related(
                    "target", "target__objective"
                ).first()
                if not obj:
                    return CustomResponse.errors(
                        message="Activity not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                if obj.status != "APPROVED":
                    return CustomResponse.errors(
                        message="Only approved activities can have implementation reviewed.",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )

                action = (request.data.get("action") or "").lower()
                comment = (request.data.get("comment") or "").strip()
                fy = (obj.planned_financial_year or "").strip()

                pending_qs = QD.objects.filter(
                    activity=obj,
                    is_locked=True,
                    implementation_status="SUBMITTED",
                    implementation_approved_at__isnull=True,
                )
                if fy:
                    pending_qs = pending_qs.filter(financial_year=fy)

                quarter_raw = request.data.get("quarter")
                if quarter_raw is not None and quarter_raw != "":
                    try:
                        qn = int(quarter_raw)
                        if qn not in (1, 2, 3, 4):
                            raise ValueError
                        pending_qs = pending_qs.filter(quarter=qn)
                    except (ValueError, TypeError):
                        return CustomResponse.errors(
                            message="Invalid quarter. Use 1, 2, 3, or 4.",
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )

                if action == "approve":
                    if not pending_qs.exists():
                        return CustomResponse.errors(
                            message="No quarterly implementation is pending approval for this activity.",
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )
                    quarter_nums = sorted(pending_qs.values_list("quarter", flat=True))
                    qlabel = ", ".join(f"Q{q}" for q in quarter_nums)
                    now = timezone.now()
                    n = pending_qs.update(
                        implementation_status="APPROVED",
                        implementation_approved_at=now,
                        implementation_approved_by_id=request.user.id,
                        implementation_approval_comment=None,
                    )
                    _create_performance_audit_log(
                        request,
                        entity_type="activity",
                        entity_id=obj.uid,
                        action="approve_implementation",
                        model_name="Activity",
                        object_repr=obj.title,
                        old_value={"quarters": quarter_nums},
                        new_value={"quarters_approved": quarter_nums},
                        comment=None,
                    )
                    obj.refresh_from_db()
                    msg = (
                        f"Implementation approved for {qlabel}."
                        if n == 1
                        else f"Implementation approved for {n} quarters: {qlabel}."
                    )
                    return CustomResponse.success(
                        message=msg,
                        data=ActivitySerializer(obj).data,
                    )

                if action == "return":
                    if not comment:
                        return CustomResponse.errors(
                            message="Comment is required when returning implementation.",
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )
                    if not pending_qs.exists():
                        return CustomResponse.errors(
                            message="No quarterly implementation is pending return for this activity.",
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )
                    quarter_nums = sorted(pending_qs.values_list("quarter", flat=True))
                    qlabel = ", ".join(f"Q{q}" for q in quarter_nums)
                    n = pending_qs.update(
                        is_locked=False,
                        implementation_status="RETURNED",
                        implementation_submitted_at=None,
                        implementation_submitted_by_id=None,
                        implementation_approved_at=None,
                        implementation_approved_by_id=None,
                        implementation_approval_comment=comment,
                    )
                    obj.implementation_submitted_at = None
                    obj.implementation_submitted_by_id = None
                    obj.save(
                        update_fields=["implementation_submitted_at", "implementation_submitted_by_id"]
                    )
                    _create_performance_audit_log(
                        request,
                        entity_type="activity",
                        entity_id=obj.uid,
                        action="return_implementation",
                        model_name="Activity",
                        object_repr=obj.title,
                        old_value={"returned_quarters": quarter_nums},
                        new_value={"comment": comment},
                        comment=comment,
                    )
                    obj.refresh_from_db()
                    msg = (
                        f"Implementation returned for revision: {qlabel}."
                        if n == 1
                        else f"Implementation returned for revision ({n} quarters: {qlabel})."
                    )
                    return CustomResponse.success(
                        message=msg,
                        data=ActivitySerializer(obj).data,
                    )

                return CustomResponse.errors(
                    message="Invalid action. Use 'approve' or 'return'.",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class QuarterlyDataView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = QuarterlyDataSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                obj = QuarterlyData.objects.filter(uid=uid).first()
                if not obj:
                    return CustomResponse.errors(
                        message="Quarterly data not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                serializer = self.serializer_class(obj)
                return CustomResponse.success(data=serializer.data)
            activity_uid = request.GET.get("activity", "")
            financial_year = request.GET.get("financial_year", "")
            qs = QuarterlyData.objects.all()
            if activity_uid:
                qs = qs.filter(activity__uid=activity_uid)
            if financial_year:
                qs = qs.filter(financial_year=financial_year)
            qs = qs.order_by("activity", "financial_year", "quarter")
            return CustomPagination.paginate(
                view_class=self, results=qs, request=request
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    qd = serializer.save(
                        created_by_id=request.user.id,
                        updated_by_id=request.user.id,
                    )
                    _compute_activity_ai_percent(qd)
                    return CustomResponse.success(
                        message="Quarterly data saved successfully",
                        data=serializer.data,
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def put(self, request, uid):
        try:
            obj = QuarterlyData.objects.filter(uid=uid).first()
            if not obj:
                return CustomResponse.errors(
                    message="Quarterly data not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            if obj.is_locked:
                return CustomResponse.errors(
                    message="This quarter is locked and cannot be edited",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            serializer = self.serializer_class(obj, data=request.data, partial=True)
            if serializer.is_valid():
                qd = serializer.save(updated_by_id=request.user.id)
                _compute_activity_ai_percent(qd)
                return CustomResponse.success(
                    message="Quarterly data updated successfully",
                    data=QuarterlyDataSerializer(qd).data,
                )
            return CustomResponse.errors(
                message="Validation failed",
                data=serializer.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class KPIActualView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = KPIActualSerializer
    write_serializer_class = KPIActualWriteSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                obj = KPIActual.objects.filter(uid=uid).first()
                if not obj:
                    return CustomResponse.errors(
                        message="KPI actual not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                serializer = self.serializer_class(obj)
                return CustomResponse.success(data=serializer.data)
            target_uid = request.GET.get("target", "")
            financial_year = request.GET.get("financial_year", "")
            qs = KPIActual.objects.all()
            if target_uid:
                qs = qs.filter(target__uid=target_uid)
            if financial_year:
                qs = qs.filter(financial_year=financial_year)
            qs = qs.order_by("target", "financial_year", "quarter")
            return CustomPagination.paginate(
                view_class=self, results=qs, request=request
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.write_serializer_class(data=request.data)
                if serializer.is_valid():
                    kpi = serializer.save(
                        created_by_id=request.user.id,
                        updated_by_id=request.user.id,
                    )
                    _compute_kpi_percent(kpi)
                    return CustomResponse.success(
                        message="KPI actual saved successfully",
                        data=KPIActualSerializer(kpi).data,
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def put(self, request, uid):
        """Update an existing KPI actual (frontend uses PUT when uid is present)."""
        try:
            with transaction.atomic():
                obj = KPIActual.objects.filter(uid=uid).first()
                if not obj:
                    return CustomResponse.errors(
                        message="KPI actual not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                serializer = self.write_serializer_class(
                    obj, data=request.data, partial=True
                )
                if serializer.is_valid():
                    kpi = serializer.save(updated_by_id=request.user.id)
                    _compute_kpi_percent(kpi)
                    return CustomResponse.success(
                        message="KPI actual updated successfully",
                        data=KPIActualSerializer(kpi).data,
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class ActivityDocumentView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ActivityDocumentSerializer
    write_serializer_class = ActivityDocumentWriteSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                obj = ActivityDocument.objects.filter(uid=uid).first()
                if not obj:
                    return CustomResponse.errors(
                        message="Document not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                serializer = self.serializer_class(obj, context={"request": request})
                return CustomResponse.success(data=serializer.data)
            activity_uid = request.GET.get("activity", "")
            qs = ActivityDocument.objects.all()
            if activity_uid:
                qs = qs.filter(activity__uid=activity_uid)
            qs = qs.order_by("-created_at")
            return CustomPagination.paginate(
                view_class=self, results=qs, request=request,
                serializer_context={"request": request},
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def post(self, request):
        try:
            with transaction.atomic():
                data = request.data.copy()
                file_base64 = data.pop("file_base64", "")
                file_name = data.get("file_name") or f"perf_doc_{timezone.now().strftime('%Y%m%d%H%M%S')}"
                activity_uid = (data.get("activity") or "").strip()
                folder = f"performance_documents/activities/{activity_uid}" if activity_uid else "performance_documents"
                if file_base64:
                    try:
                        minio = MinioStorage()
                        file_path = minio.upload_base64_file(
                            file_base64,
                            folder=folder,
                            file_name=file_name,
                            old_file_path=None,
                        )
                    except Exception:
                        file_path = _save_spims_document_locally(file_base64, activity_uid, file_name)
                    data["file_path"] = file_path
                    if not data.get("file_type") and file_name:
                        ext = file_name.split(".")[-1].lower() if "." in file_name else ""
                        data["file_type"] = ext or "application/octet-stream"
                serializer = self.write_serializer_class(data=data)
                if serializer.is_valid():
                    doc = serializer.save(
                        created_by_id=request.user.id,
                        updated_by_id=request.user.id,
                    )
                    return CustomResponse.success(
                        message="Document uploaded successfully",
                        data=self.serializer_class(doc, context={"request": request}).data,
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def put(self, request, uid):
        try:
            obj = ActivityDocument.objects.filter(uid=uid).first()
            if not obj:
                return CustomResponse.errors(
                    message="Document not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            data = request.data.copy()
            file_base64 = data.pop("file_base64", None)
            activity_uid = str(obj.activity.uid) if obj.activity else ""
            folder = f"performance_documents/activities/{activity_uid}" if activity_uid else "performance_documents"
            if file_base64:
                file_name = data.get("file_name") or obj.file_name or f"perf_doc_{timezone.now().strftime('%Y%m%d%H%M%S')}"
                old_path = obj.file_path or None
                try:
                    minio = MinioStorage()
                    file_path = minio.upload_base64_file(
                        file_base64,
                        folder=folder,
                        file_name=file_name,
                        old_file_path=old_path if old_path and not old_path.startswith(SPIMS_LOCAL_PREFIX) else None,
                    )
                    if old_path and old_path.startswith(SPIMS_LOCAL_PREFIX):
                        _delete_spims_local_document(old_path)
                except Exception:
                    if old_path and old_path.startswith(SPIMS_LOCAL_PREFIX):
                        _delete_spims_local_document(old_path)
                    file_path = _save_spims_document_locally(file_base64, activity_uid, file_name)
                data["file_path"] = file_path
                data["file_name"] = file_name
                if file_name:
                    ext = file_name.split(".")[-1].lower() if "." in file_name else ""
                    data["file_type"] = ext or obj.file_type or "application/octet-stream"
            if "description" in data:
                obj.description = (data.get("description") or "").strip() or None
            if "file_path" in data:
                obj.file_path = data["file_path"]
            if "file_name" in data:
                obj.file_name = data["file_name"]
            if "file_type" in data:
                obj.file_type = data["file_type"]
            if "file_size" in data:
                obj.file_size = data.get("file_size") or 0
            if "quarter" in data:
                try:
                    q = data["quarter"]
                    obj.quarter = int(q) if q is not None and q != "" and int(q) in (1, 2, 3, 4) else None
                except (ValueError, TypeError):
                    obj.quarter = None
            if "financial_year" in data:
                obj.financial_year = (data.get("financial_year") or "").strip() or None
            obj.updated_by_id = request.user.id
            obj.save()
            return CustomResponse.success(
                message="Document updated successfully",
                data=self.serializer_class(obj, context={"request": request}).data,
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def delete(self, request, uid):
        try:
            obj = ActivityDocument.objects.filter(uid=uid).first()
            if not obj:
                return CustomResponse.errors(
                    message="Document not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            file_path = getattr(obj, "file_path", None)
            obj.delete()
            if file_path:
                if file_path.startswith(SPIMS_LOCAL_PREFIX):
                    _delete_spims_local_document(file_path)
                else:
                    try:
                        MinioStorage().remove_file(file_path)
                    except Exception:
                        pass
            return CustomResponse.success(message="Document deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class ActivityDocumentDownloadView(APIView):
    """Stream an activity document — local fallback or MinIO presigned redirect."""
    permission_classes = [IsAuthenticated]

    def get(self, request, uid):
        try:
            obj = ActivityDocument.objects.filter(uid=uid).first()
            if not obj:
                return CustomResponse.errors(
                    message="Document not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            file_path = obj.file_path or ""
            if not file_path:
                return CustomResponse.errors(
                    message="Document has no file attached",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            if file_path.startswith(SPIMS_LOCAL_PREFIX):
                file_bytes = _read_spims_local_document(file_path)
                if not file_bytes:
                    return CustomResponse.errors(
                        message="File not found in local storage",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
            else:
                try:
                    minio = MinioStorage()
                    file_bytes = minio.get_object_bytes(file_path)
                except Exception:
                    return CustomResponse.errors(
                        message="Could not retrieve file from storage. MinIO may be unavailable.",
                        code=STATUS_CODES["SERVER_ERROR"],
                    )
                if not file_bytes:
                    return CustomResponse.errors(
                        message="File not found in storage",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
            filename = (obj.file_name or file_path.split("/")[-1] or "document")
            ext = filename.lower().split(".")[-1] if "." in filename else ""
            content_type_map = {
                "pdf": "application/pdf",
                "doc": "application/msword",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "xls": "application/vnd.ms-excel",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "ppt": "application/vnd.ms-powerpoint",
                "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "gif": "image/gif",
                "csv": "text/csv",
                "txt": "text/plain",
            }
            content_type = content_type_map.get(ext, "application/octet-stream")
            response = HttpResponse(file_bytes, content_type=content_type)
            safe_filename = quote(filename)
            response["Content-Disposition"] = f'attachment; filename="{safe_filename}"'
            return response
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class ObjectiveApprovalView(APIView):
    """POST body: { action: 'approve'|'return', comment?: string }"""
    permission_classes = [IsAuthenticated]

    def post(self, request, uid):
        try:
            obj = Objective.objects.filter(uid=uid, is_deleted=False).first()
            if not obj:
                return CustomResponse.errors(
                    message="Objective not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            action = (request.data.get("action") or "").lower()
            comment = (request.data.get("comment") or "").strip()
            if action == "approve":
                old_status = obj.status
                obj.status = "APPROVED"
                obj.approval_comment = None
                obj.approved_at = timezone.now()
                obj.approved_by_id = request.user.id
                obj.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
                _create_performance_audit_log(
                    request,
                    entity_type="objective",
                    entity_id=obj.uid,
                    action="approve",
                    model_name="Objective",
                    object_repr=obj.title,
                    old_value={"status": old_status},
                    new_value={"status": obj.status},
                    comment=None,
                )
                return CustomResponse.success(message="Objective approved", data=ObjectiveSerializer(obj).data)
            if action == "return":
                if not comment:
                    return CustomResponse.errors(
                        message="Comment is required when returning",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                old_status = obj.status
                obj.status = "RETURNED"
                obj.approval_comment = comment
                obj.approved_at = None
                obj.approved_by_id = None
                obj.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
                _create_performance_audit_log(
                    request,
                    entity_type="objective",
                    entity_id=obj.uid,
                    action="return",
                    model_name="Objective",
                    object_repr=obj.title,
                    old_value={"status": old_status},
                    new_value={"status": obj.status},
                    comment=comment,
                )
                return CustomResponse.success(message="Objective returned", data=ObjectiveSerializer(obj).data)
            return CustomResponse.errors(
                message="Invalid action. Use 'approve' or 'return'",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class ObjectiveSubmitPackageView(APIView):
    """
    Structured hierarchical submission: submit the objective and all its targets (DRAFT or RETURNED)
    as one package for approval. Approver then approves per level (objective first, then targets).
    Activities can be added only after the target and objective are approved.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, uid):
        try:
            obj = Objective.objects.filter(uid=uid, is_deleted=False).first()
            if not obj:
                return CustomResponse.errors(
                    message="Objective not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            if obj.status not in ("DRAFT", "RETURNED"):
                return CustomResponse.errors(
                    message="Only draft or returned objectives can be submitted as a package.",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            with transaction.atomic():
                obj.status = "PENDING"
                obj.approval_comment = None
                obj.approved_at = None
                obj.approved_by_id = None
                obj.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
                targets = Target.objects.filter(
                    objective=obj, is_deleted=False, status__in=("DRAFT", "RETURNED")
                )
                updated_count = 0
                for t in targets:
                    t.status = "PENDING"
                    t.approval_comment = None
                    t.approved_at = None
                    t.approved_by_id = None
                    t.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
                    updated_count += 1
            return CustomResponse.success(
                message="Package submitted for approval: 1 objective and {} target(s). Approve the objective first, then each target. Activities can be added after the target and objective are approved.".format(
                    updated_count
                ),
                data={
                    "objective_uid": str(obj.uid),
                    "objective_status": obj.status,
                    "targets_submitted": updated_count,
                },
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class TargetApprovalView(APIView):
    """Hierarchical workflow: parent objective must be APPROVED before a target can be approved."""
    permission_classes = [IsAuthenticated]

    def post(self, request, uid):
        try:
            obj = Target.objects.select_related("objective").filter(uid=uid, is_deleted=False).first()
            if not obj:
                return CustomResponse.errors(
                    message="Target not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            action = (request.data.get("action") or "").lower()
            comment = (request.data.get("comment") or "").strip()
            if action == "approve":
                if obj.objective.status != "APPROVED":
                    return CustomResponse.errors(
                        message="Approve the parent objective first. (Structured hierarchical workflow: Objective → Targets → Activities.)",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                old_status = obj.status
                obj.status = "APPROVED"
                obj.approval_comment = None
                obj.approved_at = timezone.now()
                obj.approved_by_id = request.user.id
                obj.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
                _create_performance_audit_log(
                    request,
                    entity_type="target",
                    entity_id=obj.uid,
                    action="approve",
                    model_name="Target",
                    object_repr=obj.title,
                    old_value={"status": old_status},
                    new_value={"status": obj.status},
                    comment=None,
                )
                return CustomResponse.success(message="Target approved", data=TargetSerializer(obj).data)
            if action == "return":
                if not comment:
                    return CustomResponse.errors(
                        message="Comment is required when returning",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                old_status = obj.status
                obj.status = "RETURNED"
                obj.approval_comment = comment
                obj.approved_at = None
                obj.approved_by_id = None
                obj.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
                _create_performance_audit_log(
                    request,
                    entity_type="target",
                    entity_id=obj.uid,
                    action="return",
                    model_name="Target",
                    object_repr=obj.title,
                    old_value={"status": old_status},
                    new_value={"status": obj.status},
                    comment=comment,
                )
                return CustomResponse.success(message="Target returned", data=TargetSerializer(obj).data)
            return CustomResponse.errors(
                message="Invalid action. Use 'approve' or 'return'",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class ActivityApprovalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uid):
        try:
            obj = Activity.objects.filter(uid=uid, is_deleted=False).first()
            if not obj:
                return CustomResponse.errors(
                    message="Activity not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            action = (request.data.get("action") or "").lower()
            comment = (request.data.get("comment") or "").strip()
            if action == "approve":
                old_status = obj.status
                obj.status = "APPROVED"
                obj.approval_comment = None
                obj.approved_at = timezone.now()
                obj.approved_by_id = request.user.id
                obj.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
                _create_performance_audit_log(
                    request,
                    entity_type="activity",
                    entity_id=obj.uid,
                    action="approve",
                    model_name="Activity",
                    object_repr=obj.title,
                    old_value={"status": old_status},
                    new_value={"status": obj.status},
                    comment=None,
                )
                return CustomResponse.success(message="Activity approved", data=ActivitySerializer(obj).data)
            if action == "return":
                if not comment:
                    return CustomResponse.errors(
                        message="Comment is required when returning",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                old_status = obj.status
                obj.status = "RETURNED"
                obj.approval_comment = comment
                obj.approved_at = None
                obj.approved_by_id = None
                obj.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
                _create_performance_audit_log(
                    request,
                    entity_type="activity",
                    entity_id=obj.uid,
                    action="return",
                    model_name="Activity",
                    object_repr=obj.title,
                    old_value={"status": old_status},
                    new_value={"status": obj.status},
                    comment=comment,
                )
                return CustomResponse.success(message="Activity returned", data=ActivitySerializer(obj).data)
            return CustomResponse.errors(
                message="Invalid action. Use 'approve' or 'return'",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class PerformanceDashboardSummaryView(APIView):
    """Summary for dashboard: institutional and objective-level performance."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            financial_year = request.GET.get("financial_year", "")
            if not financial_year:
                objectives = Objective.objects.filter(
                    is_deleted=False, status="APPROVED"
                ).order_by("financial_year", "title")[:50]
            else:
                objectives = Objective.objects.filter(
                    is_deleted=False,
                    status="APPROVED",
                    financial_year=financial_year,
                ).order_by("title")
            data = ObjectiveSerializer(objectives, many=True).data
            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class PerformanceAnalyticsView(APIView):
    """
    Analytics for dashboard charts.
    GET ?financial_year=2024/2025
    Returns: status_distribution, objectives_by_fy, quarterly_trend, institutional_performance, objective_performance.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .performance_calculations import (
                status_counts,
                get_quarterly_trend,
                institutional_performance,
                objective_score,
            )

            financial_year = (request.GET.get("financial_year") or "").strip()

            obj_status = status_counts(
                Objective,
                {"financial_year": financial_year} if financial_year else None,
            )
            tgt_status = status_counts(Target)
            act_status = status_counts(Activity)

            def to_chart(rows, status_col="status"):
                total = sum(r["count"] for r in rows)
                return [
                    {
                        "status": r[status_col],
                        "label": r[status_col],
                        "count": r["count"],
                        "percentage": round((r["count"] / total * 100), 1) if total else 0,
                        "color": _status_color(r[status_col]),
                    }
                    for r in rows
                ]

            status_objectives = to_chart(obj_status)
            status_targets = to_chart(tgt_status)
            status_activities = to_chart(act_status)

            fy_counts = (
                Objective.objects.filter(is_deleted=False)
                .values("financial_year")
                .annotate(count=Count("id"))
                .order_by("financial_year")
            )
            objectives_by_fy = [
                {"label": r["financial_year"], "value": r["count"], "category": r["financial_year"]}
                for r in fy_counts
            ]

            quarterly_trend = get_quarterly_trend(financial_year) if financial_year else []

            inst_perf = None
            if financial_year:
                inst_perf = institutional_performance(financial_year)

            objective_performance = []
            if financial_year:
                objs = Objective.objects.filter(
                    is_deleted=False, status="APPROVED", financial_year=financial_year
                ).order_by("title")
                for o in objs:
                    score = objective_score(o, financial_year)
                    objective_performance.append({
                        "category": o.title[:40] + ("..." if len(o.title) > 40 else ""),
                        "label": o.title[:40],
                        "full_label": o.title,
                        "value": float(score or 0),
                        "count": float(score or 0),
                    })

            progress_status = [
                {"label": "Approved", "value": sum(r["count"] for r in obj_status if r["status"] == "APPROVED"), "color": "bg-success"},
                {"label": "Pending", "value": sum(r["count"] for r in obj_status if r["status"] == "PENDING"), "color": "bg-warning"},
                {"label": "Draft", "value": sum(r["count"] for r in obj_status if r["status"] == "DRAFT"), "color": "bg-secondary"},
                {"label": "Returned", "value": sum(r["count"] for r in obj_status if r["status"] == "RETURNED"), "color": "bg-danger"},
            ]
            progress_status = [x for x in progress_status if x["value"] > 0]

            data = {
                "status_distribution": {
                    "objectives": status_objectives,
                    "targets": status_targets,
                    "activities": status_activities,
                },
                "objectives_by_financial_year": objectives_by_fy,
                "quarterly_trend": quarterly_trend,
                "institutional_performance": inst_perf,
                "objective_performance": objective_performance,
                "progress_status": progress_status,
                "financial_year": financial_year or None,
            }
            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))
