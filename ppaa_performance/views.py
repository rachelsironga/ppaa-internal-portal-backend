from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ppaa_portal.pagination import CustomPagination
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from utils.minio_storage import MinioStorage

from .models import Objective, Target, Activity, QuarterlyData, KPIActual, ActivityDocument, PerformanceAuditLog
from .serializers import (
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
    PerformanceAuditLogSerializer,
)


def _validate_objective_weights(financial_year):
    """Ensure sum of objective weights for the FY = 100%."""
    total = (
        Objective.objects.filter(
            financial_year=financial_year, is_deleted=False, status="APPROVED"
        ).aggregate(s=Sum("weight"))["s"]
        or Decimal("0")
    )
    return total == Decimal("100")


def _validate_target_weights(objective_uid):
    """Ensure sum of target weights for the objective = 100%."""
    total = (
        Target.objects.filter(
            objective__uid=objective_uid, is_deleted=False
        ).aggregate(s=Sum("weight"))["s"]
        or Decimal("0")
    )
    return total == Decimal("100")


def _validate_activity_weights(target_uid):
    """Ensure sum of activity weights for the target = 100%."""
    total = (
        Activity.objects.filter(
            target__uid=target_uid, is_deleted=False
        ).aggregate(s=Sum("weight"))["s"]
        or Decimal("0")
    )
    return total == Decimal("100")


def _kpi_complete(target):
    """Check KPI fields are set for target."""
    return bool(
        target.kpi_name
        and target.kpi_unit is not None
        and target.kpi_planned_value is not None
        and target.kpi_direction
    )


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
                    serializer.save(
                        created_by_id=request.user.id,
                        updated_by_id=request.user.id,
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
                serializer = self.serializer_class(obj, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save(updated_by_id=request.user.id)
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
            obj.is_deleted = True
            obj.deleted_at = timezone.now()
            obj.save(update_fields=["is_deleted", "deleted_at"])
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
                # The frontend may send comma-separated values when multi-select is enabled.
                years = [y.strip() for y in financial_year.split(",") if y.strip()]
                qs = qs.filter(objective__financial_year__in=years)
            if search:
                qs = qs.filter(
                    Q(title__icontains=search) | Q(description__icontains=search)
                )
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
                    serializer.save(
                        created_by_id=request.user.id,
                        updated_by_id=request.user.id,
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
                serializer = self.serializer_class(obj, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save(updated_by_id=request.user.id)
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
            obj.is_deleted = True
            obj.deleted_at = timezone.now()
            obj.save(update_fields=["is_deleted", "deleted_at"])
            return CustomResponse.success(message="Target deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class ActivityView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ActivitySerializer

    def get(self, request, uid=None):
        try:
            if uid:
                obj = Activity.objects.filter(uid=uid, is_deleted=False).first()
                if not obj:
                    return CustomResponse.errors(
                        message="Activity not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                serializer = self.serializer_class(obj)
                return CustomResponse.success(data=serializer.data)
            target_uid = request.GET.get("target", "")
            search = request.GET.get("search", "")
            qs = Activity.objects.filter(is_deleted=False)
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
                    serializer.save(
                        created_by_id=request.user.id,
                        updated_by_id=request.user.id,
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
                obj = Activity.objects.filter(uid=uid, is_deleted=False).first()
                if not obj:
                    return CustomResponse.errors(
                        message="Activity not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                serializer = self.serializer_class(obj, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save(updated_by_id=request.user.id)
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
            obj.is_deleted = True
            obj.deleted_at = timezone.now()
            obj.save(update_fields=["is_deleted", "deleted_at"])
            return CustomResponse.success(message="Activity deleted successfully")
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


def _compute_activity_ai_percent(qd):
    """AI% = (Actual / Planned) * 100, cap 100. Save on QuarterlyData."""
    if not qd.activity.planned_value or qd.activity.planned_value <= 0:
        return
    pct = (qd.actual_value / qd.activity.planned_value) * 100
    qd.computed_ai_percent = min(Decimal("100"), pct)
    qd.save(update_fields=["computed_ai_percent"])


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
                serializer = self.serializer_class(obj)
                return CustomResponse.success(data=serializer.data)
            activity_uid = request.GET.get("activity", "")
            qs = ActivityDocument.objects.all()
            if activity_uid:
                qs = qs.filter(activity__uid=activity_uid)
            qs = qs.order_by("-created_at")
            return CustomPagination.paginate(
                view_class=self, results=qs, request=request
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
                    minio = MinioStorage()
                    file_path = minio.upload_base64_file(
                        file_base64,
                        folder=folder,
                        file_name=file_name,
                        old_file_path=None,
                    )
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
                        data=self.serializer_class(doc).data,
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
            obj = ActivityDocument.objects.filter(uid=uid).first()
            if not obj:
                return CustomResponse.errors(
                    message="Document not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            file_path = getattr(obj, "file_path", None)
            obj.delete()
            if file_path:
                try:
                    MinioStorage().remove_file(file_path)
                except Exception:
                    pass
            return CustomResponse.success(message="Document deleted successfully")
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
                obj.status = "APPROVED"
                obj.approval_comment = None
                obj.approved_at = timezone.now()
                obj.approved_by_id = request.user.id
                obj.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
                return CustomResponse.success(message="Objective approved", data=ObjectiveSerializer(obj).data)
            if action == "return":
                if not comment:
                    return CustomResponse.errors(
                        message="Comment is required when returning",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                obj.status = "RETURNED"
                obj.approval_comment = comment
                obj.approved_at = None
                obj.approved_by_id = None
                obj.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
                return CustomResponse.success(message="Objective returned", data=ObjectiveSerializer(obj).data)
            return CustomResponse.errors(
                message="Invalid action. Use 'approve' or 'return'",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class TargetApprovalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uid):
        try:
            obj = Target.objects.filter(uid=uid, is_deleted=False).first()
            if not obj:
                return CustomResponse.errors(
                    message="Target not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            action = (request.data.get("action") or "").lower()
            comment = (request.data.get("comment") or "").strip()
            if action == "approve":
                obj.status = "APPROVED"
                obj.approval_comment = None
                obj.approved_at = timezone.now()
                obj.approved_by_id = request.user.id
                obj.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
                return CustomResponse.success(message="Target approved", data=TargetSerializer(obj).data)
            if action == "return":
                if not comment:
                    return CustomResponse.errors(
                        message="Comment is required when returning",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                obj.status = "RETURNED"
                obj.approval_comment = comment
                obj.approved_at = None
                obj.approved_by_id = None
                obj.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
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
                obj.status = "APPROVED"
                obj.approval_comment = None
                obj.approved_at = timezone.now()
                obj.approved_by_id = request.user.id
                obj.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
                return CustomResponse.success(message="Activity approved", data=ActivitySerializer(obj).data)
            if action == "return":
                if not comment:
                    return CustomResponse.errors(
                        message="Comment is required when returning",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                obj.status = "RETURNED"
                obj.approval_comment = comment
                obj.approved_at = None
                obj.approved_by_id = None
                obj.save(update_fields=["status", "approval_comment", "approved_at", "approved_by_id"])
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
            from django.db.models import Count
            from .calculations import (
                status_counts,
                get_quarterly_trend,
                institutional_performance,
                objective_score,
                target_kpi_score,
            )

            financial_year = (request.GET.get("financial_year") or "").strip()

            # Status distribution for Objectives, Targets, Activities (for DoughnutChart)
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

            # Objectives count by financial year (for BarChart)
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

            # Quarterly trend (average AI% per quarter for selected FY)
            quarterly_trend = get_quarterly_trend(financial_year) if financial_year else []

            # Institutional performance % for selected FY
            inst_perf = None
            if financial_year:
                inst_perf = institutional_performance(financial_year)

            # Objective-level performance (for BarChart) for selected FY
            objective_performance = []
            # Objective contribution to institutional performance (for Viewer pie-style distribution)
            objective_contribution_distribution = []
            # Target-level KPI evaluation (for Approver dashboard)
            kpi_targets = []
            if financial_year:
                objs = Objective.objects.filter(
                    is_deleted=False, status="APPROVED", financial_year=financial_year
                ).order_by("title")
                objective_contributions = []
                for o in objs:
                    score = objective_score(o, financial_year)
                    score_f = float(score or 0)
                    objective_performance.append(
                        {
                            "category": o.title[:40]
                            + ("..." if len(o.title) > 40 else ""),
                            "label": o.title[:40],
                            "full_label": o.title,
                            "value": score_f,
                            "count": score_f,
                        }
                    )
                    # Contribution points = objective score (OI%) weighted by objective weight
                    try:
                        contrib = score_f * (float(o.weight or 0) / 100.0)
                    except Exception:
                        contrib = 0.0
                    if contrib > 0:
                        label = o.title[:40] + ("..." if len(o.title) > 40 else "")
                        objective_contributions.append(
                            {
                                "uid": str(o.uid),
                                "label": label,
                                "category": label,
                                "value": round(contrib, 2),
                                "count": round(contrib, 2),
                            }
                        )

                # Build a compact distribution: top objectives + "Others"
                if objective_contributions:
                    objective_contributions_sorted = sorted(
                        objective_contributions, key=lambda x: x["value"], reverse=True
                    )
                    top_n = 6
                    top = objective_contributions_sorted[:top_n]
                    others = objective_contributions_sorted[top_n:]
                    others_sum = round(sum((x["value"] or 0) for x in others), 2)
                    objective_contribution_distribution = top
                    if others_sum > 0:
                        objective_contribution_distribution = [
                            *top,
                            {
                                "label": "Others",
                                "category": "Others",
                                "value": others_sum,
                                "count": others_sum,
                            },
                        ]

                # Evaluate KPI performance per approved target under approved objectives
                approved_targets = Target.objects.filter(
                    is_deleted=False,
                    status="APPROVED",
                    objective__financial_year=financial_year,
                    objective__status="APPROVED",
                ).select_related("objective")
                for t in approved_targets:
                    kpi_pct = target_kpi_score(t, financial_year)
                    if kpi_pct is None:
                        continue
                    v = float(kpi_pct or 0)
                    title_short = t.title[:50] + ("..." if len(t.title) > 50 else "")
                    kpi_targets.append(
                        {
                            "uid": str(t.uid),
                            "title": title_short,
                            "full_title": t.title,
                            "objective_title": t.objective.title,
                            "value": v,
                            "count": v,
                            "category": title_short,
                            "label": title_short,
                        }
                    )

            kpi_targets_sorted = sorted(
                kpi_targets, key=lambda x: x["value"], reverse=True
            )
            kpi_targets_top = kpi_targets_sorted[:5]
            kpi_targets_bottom = (
                list(reversed(kpi_targets_sorted[-5:])) if kpi_targets_sorted else []
            )

            # KPI band distribution for institution-wide picture
            kpi_band_distribution = []
            if kpi_targets:
                bands = [
                    ("Excellent (≥85%)", 85, 101),
                    ("Good (70–84%)", 70, 85),
                    ("Fair (50–69%)", 50, 70),
                    ("Weak (<50%)", 0, 50),
                ]
                for label, min_v, max_v in bands:
                    c = sum(
                        1
                        for t in kpi_targets
                        if min_v <= (t["value"] or 0) < max_v
                    )
                    if c > 0:
                        kpi_band_distribution.append(
                            {
                                "label": label,
                                "category": label,
                                "value": c,
                                "count": c,
                            }
                        )

            # Progress-style: status breakdown for objectives in selected FY
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
                "objective_contribution_distribution": objective_contribution_distribution,
                "kpi_targets_top": kpi_targets_top,
                "kpi_targets_bottom": kpi_targets_bottom,
                "kpi_band_distribution": kpi_band_distribution,
                "progress_status": progress_status,
                "financial_year": financial_year or None,
            }
            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


def _status_color(status):
    colors = {
        "DRAFT": "#6c757d",
        "PENDING": "#ffc107",
        "APPROVED": "#28a745",
        "RETURNED": "#dc3545",
    }
    return colors.get(status, "#6c757d")


# ----- SPISM: Approval, Reports, Audit -----


class PendingApprovalsView(APIView):
    """
    List items pending approval or returned (for Approval module).
    GET ?entity_type=objective|target|activity&status=PENDING|RETURNED&financial_year=
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            entity_type = (request.GET.get("entity_type") or "").strip().lower()
            status_filter = (request.GET.get("status") or "PENDING").strip().upper()
            financial_year = (request.GET.get("financial_year") or "").strip()
            if status_filter not in ("PENDING", "RETURNED"):
                status_filter = "PENDING"

            result = {"objectives": [], "targets": [], "activities": []}
            if entity_type in ("", "objective"):
                qs = Objective.objects.filter(is_deleted=False, status=status_filter)
                if financial_year:
                    qs = qs.filter(financial_year=financial_year)
                result["objectives"] = ObjectiveSerializer(qs.order_by("-updated_at"), many=True).data
            if entity_type in ("", "target"):
                qs = Target.objects.filter(is_deleted=False, status=status_filter)
                if financial_year:
                    qs = qs.filter(objective__financial_year=financial_year)
                result["targets"] = TargetSerializer(qs.order_by("-updated_at"), many=True).data
            if entity_type in ("", "activity"):
                qs = Activity.objects.filter(is_deleted=False, status=status_filter)
                if financial_year:
                    qs = qs.filter(target__objective__financial_year=financial_year)
                result["activities"] = ActivitySerializer(qs.order_by("-updated_at"), many=True).data
            return CustomResponse.success(data=result)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class PerformanceAuditLogListView(APIView):
    """
    List audit logs for SPISM Audit & Logs module.
    GET ?entity_type=&entity_id=&model_name=&action=&page=&page_size=&paginated=true
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PerformanceAuditLogSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                log = PerformanceAuditLog.objects.filter(uid=uid).first()
                if not log:
                    return CustomResponse.errors(
                        message="Audit log not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                serializer = self.serializer_class(log)
                return CustomResponse.success(data=serializer.data)

            qs = PerformanceAuditLog.objects.all().order_by("-timestamp")
            entity_type = request.GET.get("entity_type", "").strip()
            entity_id = request.GET.get("entity_id", "").strip()
            model_name = request.GET.get("model_name", "").strip()
            # Optional filters similar to internal portal System Logs
            # action can be passed directly or via 'filters' query param (first value)
            action = (request.GET.get("action") or "").strip().lower()
            filters_param = (request.GET.get("filters") or "").strip()
            if not action and filters_param and filters_param.upper() != "ALL":
                first = filters_param.split(",")[0].strip()
                if first and first.upper() != "ALL":
                    action = first.lower()

            if entity_type:
                qs = qs.filter(entity_type=entity_type)
            if entity_id:
                qs = qs.filter(entity_id=entity_id)
            if model_name:
                qs = qs.filter(model_name=model_name)
            if action:
                qs = qs.filter(action=action)
            return CustomPagination.paginate(view_class=self, results=qs, request=request)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def post(self, request):
        """Post a conversation comment. Body: { entity_type, entity_id, comment }"""
        try:
            entity_type = (request.data.get("entity_type") or "").strip().lower()
            entity_id = (request.data.get("entity_id") or "").strip()
            comment = (request.data.get("comment") or "").strip()
            if entity_type not in ("objective", "target", "activity"):
                return CustomResponse.errors(
                    message="entity_type must be objective, target, or activity",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            if not entity_id:
                return CustomResponse.errors(
                    message="entity_id is required",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            if not comment:
                return CustomResponse.errors(
                    message="comment is required",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            log = PerformanceAuditLog.objects.create(
                entity_type=entity_type,
                entity_id=entity_id,
                action="comment",
                comment=comment,
                user_id=request.user.id,
            )
            data = PerformanceAuditLogSerializer(log).data
            return CustomResponse.success(message="Comment added", data=data)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class SPISMReportsView(APIView):
    """
    Report data for SPISM Reports module (quarterly, annual, KPI, objective performance).
    GET ?report_type=quarterly|annual|kpi|objective&financial_year=2024/2025
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .calculations import (
                institutional_performance,
                objective_score,
                target_operational_score,
                target_kpi_score,
                get_quarterly_trend,
            )
            report_type = (request.GET.get("report_type") or "quarterly").strip().lower()
            financial_year = (request.GET.get("financial_year") or "").strip()
            valid_report_types = {"quarterly", "annual", "kpi", "objective"}
            if not financial_year:
                return CustomResponse.errors(
                    message="financial_year is required for reports",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            if report_type not in valid_report_types:
                return CustomResponse.errors(
                    message="Invalid report_type. Use quarterly, annual, objective, or kpi.",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

            data = {
                "financial_year": financial_year,
                "report_type": report_type,
                "generated_at": timezone.now().isoformat(),
                "summary": {},
            }
            if report_type == "quarterly":
                quarterly_trend = get_quarterly_trend(financial_year)
                inst_perf = institutional_performance(financial_year)
                data["quarterly_trend"] = quarterly_trend
                data["institutional_performance"] = inst_perf
                data["summary"] = {
                    "quarters_reported": len(quarterly_trend or []),
                    "institutional_performance": float(inst_perf or 0),
                }
            elif report_type == "annual":
                inst_perf = institutional_performance(financial_year)
                data["institutional_performance"] = inst_perf
                objectives = Objective.objects.filter(
                    is_deleted=False, status="APPROVED", financial_year=financial_year
                ).order_by("title")
                objective_rows = [
                    {
                        "uid": str(o.uid),
                        "title": o.title,
                        "weight": float(o.weight),
                        "score": float(objective_score(o, financial_year) or 0),
                    }
                    for o in objectives
                ]
                data["objectives"] = objective_rows
                data["summary"] = {
                    "objective_count": len(objective_rows),
                    "institutional_performance": float(inst_perf or 0),
                }
            elif report_type == "objective":
                objectives = Objective.objects.filter(
                    is_deleted=False, status="APPROVED", financial_year=financial_year
                ).order_by("title")
                objective_rows = [
                    {
                        "uid": str(o.uid),
                        "title": o.title,
                        "weight": float(o.weight),
                        "score": float(objective_score(o, financial_year) or 0),
                        "targets": [
                            {
                                "uid": str(t.uid),
                                "title": t.title,
                                "weight": float(t.weight),
                                "operational_score": float(target_operational_score(t, financial_year) or 0),
                                "kpi_score": float(target_kpi_score(t, financial_year) or 0),
                            }
                            for t in o.targets.filter(is_deleted=False, status="APPROVED")
                        ],
                    }
                    for o in objectives
                ]
                data["objectives"] = objective_rows
                data["summary"] = {
                    "objective_count": len(objective_rows),
                    "target_count": sum(len(o.get("targets", [])) for o in objective_rows),
                }
            elif report_type == "kpi":
                targets = Target.objects.filter(
                    objective__financial_year=financial_year,
                    objective__is_deleted=False,
                    objective__status="APPROVED",
                    is_deleted=False,
                    status="APPROVED",
                ).order_by("objective", "title")
                kpi_rows = [
                    {
                        "uid": str(t.uid),
                        "title": t.title,
                        "objective_title": t.objective.title,
                        "kpi_name": t.kpi_name,
                        "kpi_planned_value": float(t.kpi_planned_value or 0),
                        "kpi_score": float(target_kpi_score(t, financial_year) or 0),
                    }
                    for t in targets
                ]
                data["kpi_targets"] = kpi_rows
                avg_score = (
                    sum((row.get("kpi_score") or 0) for row in kpi_rows) / len(kpi_rows)
                    if kpi_rows else 0
                )
                data["summary"] = {
                    "target_count": len(kpi_rows),
                    "average_kpi_score": round(avg_score, 2),
                }
            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class SPISMConfigView(APIView):
    """System name and SPISM role names for frontend (Administration / branding)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .constants import SPISM_SYSTEM_NAME, SPISM_ROLES
            return CustomResponse.success(data={
                "system_name": SPISM_SYSTEM_NAME,
                "spism_roles": SPISM_ROLES,
            })
        except Exception as e:
            return CustomResponse.server_error(message=str(e))
