from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse
from datetime import date, timedelta
from urllib.parse import quote
import os

from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_portal.pagination import CustomPagination
from utils.permissions import HasMethodPermission, HasMethodPermissionOrRmsManager
from ppaa_auth.models import UserProfile
from utils.minio_storage import MinioStorage

from ..models import (
    Report, ReportProgress, ReportComment, ReportCommentRead, ReportAuditTrail,
    FinancialPeriod,
)
from ..serializers import (
    ReportListSerializer, ReportDetailSerializer, ReportCreateSerializer,
    ReportUpdateStatusSerializer, ReportSubmitSerializer,
    ReportProgressUpdateSerializer, ReportCommentSerializer,
    ReportAuditTrailSerializer
)

def get_minio_storage():
    """
    Lazily initialize MinIO client.
    Avoids trying to contact MinIO during management commands (makemigrations/migrate)
    and when MinIO is temporarily unavailable.
    """
    return MinioStorage(bucket_name=getattr(settings, "RMS_REPORTS_BUCKET", "reports-management"))


def _save_attachment_locally(report, attachment, file_name):
    """Fallback storage for RMS attachments when MinIO is unavailable."""
    department_code = (
        get_report_department(report).code
        if get_report_department(report) and hasattr(get_report_department(report), "code")
        else "UNKNOWN"
    )
    fy_name = report.financial_year.name if getattr(report, "financial_year", None) else "NO-FY"
    relative_dir = os.path.join("rms_local_reports", fy_name, department_code, str(report.uid))
    absolute_dir = os.path.join(settings.MEDIA_ROOT, relative_dir)
    os.makedirs(absolute_dir, exist_ok=True)

    relative_path = os.path.join(relative_dir, file_name)
    absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)

    old_path = getattr(report.attachment, "name", None) or str(report.attachment or "")
    if old_path and old_path.startswith("rms_local_reports/"):
        old_absolute_path = os.path.join(settings.MEDIA_ROOT, old_path)
        if os.path.exists(old_absolute_path):
            try:
                os.remove(old_absolute_path)
            except OSError:
                pass

    if hasattr(attachment, "seek"):
        attachment.seek(0)
    with open(absolute_path, "wb") as destination:
        for chunk in attachment.chunks() if hasattr(attachment, "chunks") else [attachment.read()]:
            destination.write(chunk)
    if hasattr(attachment, "seek"):
        attachment.seek(0)

    return relative_path.replace("\\", "/")


def _read_local_attachment(object_path):
    """Read attachment bytes from local fallback storage."""
    normalized_path = str(object_path or "").lstrip("/")
    absolute_path = os.path.join(settings.MEDIA_ROOT, normalized_path)
    if not os.path.exists(absolute_path):
        return b""
    with open(absolute_path, "rb") as source:
        return source.read()


def get_user_directory_info(user):
    """Get the user's department context from their active profile."""
    profile = UserProfile.objects.filter(
        user=user,
        is_active=True,
        is_deleted=False
    ).select_related('department').first()
    
    if profile:
        return {
            # PPAA auth only exposes `department`; reuse it as the report directory context.
            'directory': profile.department,
            'department': profile.department,
            'profile': profile
        }
    return None


def get_report_department(report):
    """Department is the PPAA report owner; fall back to legacy directory data if needed."""
    return getattr(report, "department", None) or getattr(report, "directory", None)


def user_can_access_report(report, user_department_info, is_admin=False):
    if is_admin:
        return True
    user_department = (user_department_info or {}).get("department")
    report_department = get_report_department(report)
    if not user_department or not report_department:
        return False
    return str(report_department.id) == str(user_department.id)


def is_admin_user(user):
    """Check if user is admin/superuser"""
    if user.is_superuser:
        return True
    user_groups = user.get_group_names() if hasattr(user, 'get_group_names') else []
    admin_groups = [
        "admin",
        "Admin",
        "Administrator",
        "ADMINISTRATOR",
        "CEO",
        "Executive Director",
        # RMS-specific elevated roles
        "RMS_REPORT_MANAGER",
        "RMS_SYS_ADMIN",
    ]
    return any(group in user_groups for group in admin_groups)


def is_rms_report_manager(user):
    """Check if user has RMS_REPORT_MANAGER role (ED who can direct messages to directory)"""
    if not user or not user.is_authenticated:
        return False
    user_groups = list(user.groups.values_list('name', flat=True))
    return "RMS_REPORT_MANAGER" in user_groups


def create_audit_trail(
    report,
    action,
    user,
    old_value=None,
    new_value=None,
    comments=None,
    request=None,
    entity_type=None,
    entity_uid=None,
    entity_name=None,
):
    """Helper function to create audit trail entries"""
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

    ReportAuditTrail.objects.create(
        report=report,
        entity_type=entity_type,
        entity_uid=entity_uid,
        entity_name=entity_name,
        action=action,
        performed_by=user,
        old_value=old_value,
        new_value=new_value,
        comments=comments,
        ip_address=ip_address,
        user_agent=user_agent,
        created_by=user,
        updated_by=user
    )


def compute_report_deadline(report_type, financial_year=None, financial_period=None, fallback_deadline=None):
    """Compute report deadline from report type settings and selected period/year."""
    frequency = getattr(report_type, "frequency", None) if report_type else None
    days_after_period = getattr(report_type, "submission_deadline_days", 0) or 0

    if frequency in {"monthly", "quarterly", "biannual"} and financial_period:
        return financial_period.end_date + timedelta(days=days_after_period)

    if frequency == "annual" and financial_year:
        return financial_year.end_date + timedelta(days=days_after_period)

    return fallback_deadline


class ReportView(APIView):
    """API view for Report management"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = ReportListSerializer
    required_permissions = {
        "get": ["view_report"],
        # RMS_REPORT_MANAGER typically has `view_institution_reports`; include it so
        # managers can create reports even before permission sync is re-run.
        "post": ["add_report", "view_institution_reports"],
        "put": ["change_report"],
        "patch": ["change_report"],
        "delete": ["delete_report"],
    }

    def get(self, request, uid=None):
        """Get report(s)"""
        try:
            # Get user's department info
            user_dir_info = get_user_directory_info(request.user)
            is_admin = is_admin_user(request.user)

            if uid:
                report = Report.objects.filter(
                    uid=uid, is_deleted=False
                ).select_related(
                    'report_type', 'category', 'stakeholder', 
                    'financial_year', 'directory', 'department',
                    'created_by', 'updated_by', 'submitted_by', 'assigned_to'
                ).prefetch_related('progress_updates', 'comments').first()
                
                if not report:
                    return CustomResponse.errors(
                        message="Report not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                
                if not user_can_access_report(report, user_dir_info, is_admin):
                    return CustomResponse.errors(
                        message="You don't have access to this report",
                        code=STATUS_CODES["PERMISSION_DENIED"]
                    )

                serializer = ReportDetailSerializer(report)
                return CustomResponse.success(
                    data=serializer.data,
                    message="Report retrieved successfully"
                )

            queryset = Report.objects.filter(is_deleted=False).select_related(
                'report_type', 'category', 'stakeholder', 'financial_year',
                'directory', 'department'
            )

            # Filter by user's department (unless admin)
            if not is_admin and user_dir_info and user_dir_info.get('department'):
                queryset = queryset.filter(department=user_dir_info['department'])

            # Filters
            status = request.query_params.get('status')
            if status:
                if ',' in status:
                    queryset = queryset.filter(status__in=status.split(','))
                else:
                    queryset = queryset.filter(status=status)

            priority = request.query_params.get('priority')
            if priority:
                if ',' in priority:
                    queryset = queryset.filter(priority__in=priority.split(','))
                else:
                    queryset = queryset.filter(priority=priority)

            scope = request.query_params.get('scope')
            if scope:
                if ',' in scope:
                    queryset = queryset.filter(scope__in=scope.split(','))
                else:
                    queryset = queryset.filter(scope=scope)

            financial_year_uid = request.query_params.get('financial_year_uid')
            if financial_year_uid:
                uids = [u.strip() for u in financial_year_uid.split(',') if u.strip()]
                if uids:
                    queryset = queryset.filter(financial_year__uid__in=uids)

            report_type_uid = request.query_params.get('report_type_uid')
            if report_type_uid:
                uids = [u.strip() for u in report_type_uid.split(',') if u.strip()]
                if uids:
                    queryset = queryset.filter(report_type__uid__in=uids)

            category_uid = request.query_params.get('category_uid')
            if category_uid:
                queryset = queryset.filter(category__uid=category_uid)

            department_uid = request.query_params.get('department_uid')
            if department_uid:
                queryset = queryset.filter(department__uid=department_uid)
            else:
                directory_uid = request.query_params.get('directory_uid') or request.query_params.get('directorate_uid')
                if directory_uid:
                    queryset = queryset.filter(department__uid=directory_uid)

            stakeholder_uid = request.query_params.get('stakeholder_uid')
            if stakeholder_uid:
                queryset = queryset.filter(stakeholder__uid=stakeholder_uid)

            assigned_to_uid = request.query_params.get('assigned_to_uid')
            if assigned_to_uid:
                queryset = queryset.filter(assigned_to__guid=assigned_to_uid)

            # Deadline state filter (supports comma-separated for multiple states)
            deadline_state = request.query_params.get('deadline_state')
            if deadline_state:
                states = [s.strip() for s in deadline_state.split(',') if s.strip()]
                if states:
                    today = date.today()
                    from datetime import timedelta
                    q_objects = Q()
                    for ds in states:
                        if ds == 'overdue':
                            q_objects |= Q(deadline_date__lt=today) & ~Q(status='submitted')
                        elif ds == 'due_today':
                            q_objects |= Q(deadline_date=today) & ~Q(status='submitted')
                        elif ds == 'due_soon':
                            q_objects |= Q(deadline_date__gt=today, deadline_date__lte=today + timedelta(days=3)) & ~Q(status='submitted')
                        elif ds == 'on_track':
                            q_objects |= Q(deadline_date__gt=today + timedelta(days=3)) & ~Q(status='submitted')
                        elif ds == 'completed':
                            q_objects |= Q(status='submitted')
                    if q_objects:
                        queryset = queryset.filter(q_objects)

            # Date range filters
            deadline_from = request.query_params.get('deadline_from')
            if deadline_from:
                queryset = queryset.filter(deadline_date__gte=deadline_from)

            deadline_to = request.query_params.get('deadline_to')
            if deadline_to:
                queryset = queryset.filter(deadline_date__lte=deadline_to)

            # My reports filter
            my_reports = request.query_params.get('my_reports')
            if my_reports and my_reports.lower() == 'true':
                queryset = queryset.filter(
                    Q(created_by=request.user) |
                    Q(assigned_to=request.user)
                )

            search = request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(reference_number__icontains=search) |
                    Q(description__icontains=search)
                )

            # Sorting
            ordering = request.query_params.get('ordering', '-deadline_date')
            queryset = queryset.order_by(ordering)

            if request.query_params.get('paginated', 'false').lower() == 'true':
                return CustomPagination.paginate(
                    view_class=self,
                    results=queryset,
                    request=request,
                    serializer_context={'request': request}
                )

            serializer = ReportListSerializer(queryset, many=True, context={'request': request})
            return CustomResponse.success(
                data=serializer.data,
                message="Reports retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve Reports: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def post(self, request):
        """Create a new report - Department is auto-filled from user profile"""
        try:
            # Get user's department from their profile
            user_dir_info = get_user_directory_info(request.user)
            
            if not user_dir_info or not user_dir_info.get('department'):
                return CustomResponse.errors(
                    message="Your profile does not have a department assigned. Please contact administrator.",
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            serializer = ReportCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            validated = serializer.validated_data
            report_type = validated.get('report_type')

            # Quarterly multi-select on create
            period_uids = request.data.get('financial_period_uids')
            frequency = getattr(report_type, 'frequency', None) if report_type else None
            if report_type and frequency == 'quarterly' and period_uids:
                # request.data may be a QueryDict (multipart/form-data) where list values arrive as strings.
                # Normalize to a python list of UID strings.
                if hasattr(request.data, "getlist"):
                    period_uids = request.data.getlist("financial_period_uids") or period_uids

                if isinstance(period_uids, str):
                    import json
                    raw = period_uids.strip()
                    try:
                        parsed = json.loads(raw)
                        period_uids = parsed
                    except Exception:
                        # Accept comma-separated: "uid1,uid2"
                        period_uids = [p.strip() for p in raw.split(",") if p.strip()]

                if not isinstance(period_uids, list):
                    period_uids = [str(period_uids)]

                # Clean
                period_uids = [str(u).strip() for u in period_uids if str(u).strip()]
                if not period_uids:
                    return CustomResponse.errors(
                        message="Please select at least one period",
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )

                fy = validated.get('financial_year')
                period_type = 'quarter'
                period_label = 'quarter'
                periods = list(FinancialPeriod.objects.filter(
                    uid__in=period_uids,
                    financial_year=fy,
                    period_type=period_type,
                    is_deleted=False,
                    is_active=True,
                ))

                if len(periods) != len(set(period_uids)):
                    return CustomResponse.errors(
                        message=f"One or more selected {period_label}(s) are invalid for the selected financial year",
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )

                created_reports = []

                for period in periods:
                    computed_deadline = compute_report_deadline(
                        report_type=report_type,
                        financial_year=fy,
                        financial_period=period,
                        fallback_deadline=validated.get('deadline_date'),
                    )
                    # Create a separate report per period so each can be updated/submitted independently
                    report = Report.objects.create(
                        title=validated.get('title'),
                        report_type=report_type,
                        category=validated.get('category'),
                        stakeholder=validated.get('stakeholder'),
                        other_stakeholder_name=validated.get('other_stakeholder_name'),
                        financial_year=fy,
                        financial_period=period,
                        scope=validated.get('scope', 'internal'),
                        priority=validated.get('priority', 'medium'),
                        deadline_date=computed_deadline,
                        description=validated.get('description'),
                        notes=validated.get('notes'),
                        attachment=validated.get('attachment'),
                        directory=user_dir_info['department'],
                        department=user_dir_info.get('department'),
                        created_by=request.user,
                        updated_by=request.user,
                        status='pending'
                    )
                    created_reports.append(report)

                    create_audit_trail(
                        report=report,
                        action='created',
                        user=request.user,
                        new_value=f"Report '{report.title}' created for {user_dir_info['department'].name} ({period.display_name})",
                        request=request
                    )

                result = ReportDetailSerializer(created_reports, many=True).data
                return CustomResponse.success(
                    data=result,
                    message=f"{len(created_reports)} report(s) created successfully"
                )

            # Default: single report
            computed_deadline = compute_report_deadline(
                report_type=report_type,
                financial_year=validated.get('financial_year'),
                financial_period=validated.get('financial_period'),
                fallback_deadline=validated.get('deadline_date'),
            )
            report = serializer.save(
                deadline_date=computed_deadline,
                directory=user_dir_info['department'],
                department=user_dir_info.get('department'),
                created_by=request.user,
                updated_by=request.user,
                status='pending'
            )

            create_audit_trail(
                report=report,
                action='created',
                user=request.user,
                new_value=f"Report '{report.title}' created for {user_dir_info['department'].name}",
                request=request
            )

            result = ReportDetailSerializer(report).data
            return CustomResponse.success(
                data=result,
                message="Report created successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to create Report: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def put(self, request, uid):
        """Update a report"""
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            if report.status == 'submitted':
                return CustomResponse.errors(
                    message="Cannot edit a submitted report",
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            old_title = report.title
            serializer = ReportCreateSerializer(
                report, data=request.data, partial=True
            )
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            validated = serializer.validated_data
            effective_report_type = validated.get("report_type", report.report_type)
            effective_financial_year = validated.get("financial_year", report.financial_year)
            effective_financial_period = validated.get("financial_period", report.financial_period)
            fallback_deadline = validated.get("deadline_date", report.deadline_date)

            computed_deadline = compute_report_deadline(
                report_type=effective_report_type,
                financial_year=effective_financial_year,
                financial_period=effective_financial_period,
                fallback_deadline=fallback_deadline,
            )

            serializer.save(
                deadline_date=computed_deadline,
                updated_by=request.user
            )

            create_audit_trail(
                report=report,
                action='updated',
                user=request.user,
                old_value=old_title,
                new_value=report.title,
                request=request
            )

            result = ReportDetailSerializer(report).data
            return CustomResponse.success(
                data=result,
                message="Report updated successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to update Report: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def delete(self, request, uid):
        """Soft delete a report"""
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            report.is_deleted = True
            report.deleted_at = timezone.now()
            report.deleted_by = request.user
            report.save()

            create_audit_trail(
                report=report,
                action='deleted',
                user=request.user,
                old_value=report.title,
                request=request
            )

            return CustomResponse.success(
                message="Report deleted successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to delete Report: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class ReportStatusView(APIView):
    """API view for updating report status"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "post": ["change_report"],
    }

    @transaction.atomic
    def post(self, request, uid):
        """Update report status"""
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            serializer = ReportUpdateStatusSerializer(data=request.data)
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            old_status = report.status
            new_status = serializer.validated_data['status']
            notes = serializer.validated_data.get('notes', '')

            report.status = new_status
            report.updated_by = request.user
            report.save()

            create_audit_trail(
                report=report,
                action='status_changed',
                user=request.user,
                old_value=old_status,
                new_value=new_status,
                comments=notes,
                request=request
            )

            result = ReportDetailSerializer(report).data
            return CustomResponse.success(
                data=result,
                message=f"Report status updated to '{new_status}'"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to update Report status: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class ReportSubmitView(APIView):
    """API view for submitting a report"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    required_permissions = {
        "post": ["submit_report"],
    }

    @transaction.atomic
    def post(self, request, uid):
        """Submit a report"""
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            if report.status == 'submitted':
                return CustomResponse.errors(
                    message="Report has already been submitted",
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            serializer = ReportSubmitSerializer(data=request.data)
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            attachment = serializer.validated_data.get('attachment')
            notes = serializer.validated_data.get('notes', '')

            old_status = report.status
            report.status = 'submitted'
            report.submission_date = timezone.now()
            report.submitted_by = request.user
            report.progress_percentage = 100
            report.updated_by = request.user

            if attachment:
                # Build a structured folder path for RMS reports - unique per report
                department_code = (
                    get_report_department(report).code
                    if get_report_department(report) and hasattr(get_report_department(report), "code")
                    else "UNKNOWN"
                )
                fy_name = report.financial_year.name if getattr(report, "financial_year", None) else "NO-FY"
                folder = f"reports/{fy_name}/{department_code}/{report.uid}"
                # Explicit unique filename so each report always fetches its own file
                import uuid as uuid_mod
                orig_name = getattr(attachment, "name", "") or "file"
                ext = orig_name.split(".")[-1] if "." in orig_name else "bin"
                unique_filename = f"{report.uid}_{uuid_mod.uuid4().hex}.{ext}"

                try:
                    minio_storage = get_minio_storage()
                    object_path = minio_storage.upload_file(
                        attachment,
                        folder=folder,
                        file_name=unique_filename,
                        old_object_path=report.attachment or None,
                    )
                except Exception:
                    object_path = _save_attachment_locally(report, attachment, unique_filename)
                report.attachment = object_path

            report.save()

            create_audit_trail(
                report=report,
                action='submitted',
                user=request.user,
                old_value=old_status,
                new_value='submitted',
                comments=notes,
                request=request
            )

            # Create progress update
            ReportProgress.objects.create(
                report=report,
                percentage=100,
                notes=f"Report submitted. {notes}".strip(),
                created_by=request.user,
                updated_by=request.user
            )

            result = ReportDetailSerializer(report).data
            return CustomResponse.success(
                data=result,
                message="Report submitted successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to submit Report: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class ReportAttachmentUrlView(APIView):
    """API view for getting a presigned URL to view/download report attachment"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_report"],
    }

    def get(self, request, uid):
        """Return a presigned URL for the report's attachment (valid for 1 hour)"""
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            user_dir_info = get_user_directory_info(request.user)
            is_admin = is_admin_user(request.user)

            if not user_can_access_report(report, user_dir_info, is_admin):
                return CustomResponse.errors(
                    message="You don't have access to this report",
                    code=STATUS_CODES["PERMISSION_DENIED"]
                )

            if not report.attachment:
                return CustomResponse.errors(
                    message="Report has no attachment",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            attachment_path = getattr(report.attachment, "name", None) or str(report.attachment)
            if not attachment_path:
                return CustomResponse.errors(
                    message="Invalid attachment path",
                    code=STATUS_CODES["SERVER_ERROR"]
                )

            if attachment_path.startswith("rms_local_reports/"):
                url = request.build_absolute_uri(f"/api/reports/reports/{uid}/download")
            else:
                minio_storage = get_minio_storage()
                url = minio_storage.get_presigned_url(object_path=attachment_path, expires_hours=1)

            if not url:
                return CustomResponse.errors(
                    message="Could not generate download URL: MinIO not configured",
                    code=STATUS_CODES["SERVER_ERROR"]
                )

            return CustomResponse.success(
                data={"url": url},
                message="Presigned URL generated"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to get attachment URL: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class ReportPreviewView(APIView):
    """API view for securely previewing a report attachment inline."""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_report"],
    }

    def get(self, request, uid):
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            user_dir_info = get_user_directory_info(request.user)
            is_admin = is_admin_user(request.user)

            if not user_can_access_report(report, user_dir_info, is_admin):
                return CustomResponse.errors(
                    message="You don't have access to this report",
                    code=STATUS_CODES["PERMISSION_DENIED"]
                )

            if not report.attachment:
                return CustomResponse.errors(
                    message="Report has no attachment",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            attachment_path = getattr(report.attachment, "name", None) or str(report.attachment)
            if not attachment_path:
                return CustomResponse.errors(
                    message="Invalid attachment path",
                    code=STATUS_CODES["SERVER_ERROR"]
                )

            if attachment_path.startswith("rms_local_reports/"):
                file_bytes = _read_local_attachment(attachment_path)
            else:
                minio_storage = get_minio_storage()
                file_bytes = minio_storage.get_object_bytes(attachment_path)

            if not file_bytes:
                return CustomResponse.errors(
                    message="Could not retrieve file from storage",
                    code=STATUS_CODES["SERVER_ERROR"]
                )

            filename = attachment_path.split("/")[-1] if "/" in attachment_path else "report-document"
            ext = filename.lower().split(".")[-1] if "." in filename else ""

            content_type = "application/octet-stream"
            if ext == "pdf":
                content_type = "application/pdf"
            elif ext in ("doc", "docx"):
                content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == "docx" else "application/msword"
            elif ext in ("xls", "xlsx"):
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if ext == "xlsx" else "application/vnd.ms-excel"
            elif ext in ("ppt", "pptx"):
                content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation" if ext == "pptx" else "application/vnd.ms-powerpoint"

            response = HttpResponse(file_bytes, content_type=content_type)
            safe_filename = quote(filename)
            response["Content-Disposition"] = f'inline; filename="{safe_filename}"'
            return response
        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to preview attachment: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class ReportDownloadView(APIView):
    """
    Download report attachment with security watermark (PDF, DOCX, XLSX).
    Watermark includes: download time, downloader name, department.
    """
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["download_report"],
    }

    def get(self, request, uid):
        """Stream the attachment; add watermark for PDF, DOCX, XLSX before returning."""
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).select_related(
                "directory", "financial_year"
            ).first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            user_dir_info = get_user_directory_info(request.user)
            is_admin = is_admin_user(request.user)

            if not user_can_access_report(report, user_dir_info, is_admin):
                return CustomResponse.errors(
                    message="You don't have access to this report",
                    code=STATUS_CODES["PERMISSION_DENIED"]
                )

            if not report.attachment:
                return CustomResponse.errors(
                    message="Report has no attachment",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            attachment_path = getattr(report.attachment, "name", None) or str(report.attachment)
            if not attachment_path:
                return CustomResponse.errors(
                    message="Invalid attachment path",
                    code=STATUS_CODES["SERVER_ERROR"]
                )

            if attachment_path.startswith("rms_local_reports/"):
                file_bytes = _read_local_attachment(attachment_path)
            else:
                minio_storage = get_minio_storage()
                file_bytes = minio_storage.get_object_bytes(attachment_path)
            if not file_bytes:
                return CustomResponse.errors(
                    message="Could not retrieve file from storage",
                    code=STATUS_CODES["SERVER_ERROR"]
                )

            # Get filename from path
            filename = attachment_path.split("/")[-1] if "/" in attachment_path else "report-document"

            # Watermark for PDF, Word (.docx), Excel (.xlsx)
            ext = filename.lower().split(".")[-1] if "." in filename else ""
            downloader_name = getattr(request.user, "get_full_name", lambda: "")() or str(request.user)
            department_name = get_report_department(report).name if get_report_department(report) else "N/A"
            if ext == "pdf":
                try:
                    from utils.pdf_watermark import add_watermark_to_pdf_stream
                    watermarked = add_watermark_to_pdf_stream(
                        pdf_bytes=file_bytes,
                        download_time=timezone.now(),
                        downloader_name=downloader_name,
                        directory_name=department_name,
                    )
                    if watermarked:
                        file_bytes = watermarked
                except Exception as e:
                    print(f"Warning: Could not add watermark to PDF: {e}")
            elif ext == "docx":
                try:
                    from utils.docx_watermark import add_watermark_to_docx_stream
                    watermarked = add_watermark_to_docx_stream(
                        docx_bytes=file_bytes,
                        download_time=timezone.now(),
                        downloader_name=downloader_name,
                        directory_name=department_name,
                    )
                    if watermarked:
                        file_bytes = watermarked
                except Exception as e:
                    print(f"Warning: Could not add watermark to DOCX: {e}")
            elif ext == "xlsx":
                try:
                    from utils.xlsx_watermark import add_watermark_to_xlsx_stream
                    watermarked = add_watermark_to_xlsx_stream(
                        xlsx_bytes=file_bytes,
                        download_time=timezone.now(),
                        downloader_name=downloader_name,
                        directory_name=department_name,
                    )
                    if watermarked:
                        file_bytes = watermarked
                except Exception as e:
                    print(f"Warning: Could not add watermark to XLSX: {e}")

            content_type = "application/pdf" if ext == "pdf" else "application/octet-stream"
            if ext in ("doc", "docx"):
                content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == "docx" else "application/msword"
            elif ext in ("xls", "xlsx"):
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if ext == "xlsx" else "application/vnd.ms-excel"

            response = HttpResponse(file_bytes, content_type=content_type)
            safe_filename = quote(filename)
            response["Content-Disposition"] = f'attachment; filename="{safe_filename}"'

            # Track every successful attachment download for compliance/audit visibility.
            download_time = timezone.now()
            downloader_department = (
                user_dir_info.get("department").name
                if user_dir_info and user_dir_info.get("department")
                else "N/A"
            )
            create_audit_trail(
                report=report,
                action='downloaded',
                user=request.user,
                old_value=report.title,
                new_value=filename,
                comments=(
                    f"Report '{report.title}' (file: {filename}) downloaded at "
                    f"{download_time.strftime('%Y-%m-%d %H:%M:%S %Z')} by {downloader_name} "
                    f"[user: {request.user}] from downloader department: {downloader_department}; "
                    f"report owner department: {department_name}"
                ),
                request=request
            )
            return response

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to download: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class ReportProgressView(APIView):
    """API view for updating report progress"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_report"],
        "post": ["change_report"],
    }

    def get(self, request, uid):
        """Get progress updates for a report"""
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            progress_updates = report.progress_updates.filter(
                is_deleted=False
            ).order_by('-created_at')

            serializer = ReportProgressSerializer(progress_updates, many=True)
            return CustomResponse.success(
                data=serializer.data,
                message="Progress updates retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve progress updates: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def post(self, request, uid):
        """Add progress update"""
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            if report.status == 'submitted':
                return CustomResponse.errors(
                    message="Cannot update progress of a submitted report",
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            serializer = ReportProgressUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            old_percentage = report.progress_percentage
            new_percentage = serializer.validated_data['percentage']
            notes = serializer.validated_data.get('notes', '')

            # Update report progress
            report.progress_percentage = new_percentage
            if report.status == 'pending' and new_percentage > 0:
                report.status = 'in_progress'
            report.updated_by = request.user
            report.save()

            # Create progress record
            ReportProgress.objects.create(
                report=report,
                percentage=new_percentage,
                notes=notes,
                created_by=request.user,
                updated_by=request.user
            )

            create_audit_trail(
                report=report,
                action='progress_updated',
                user=request.user,
                old_value=f"{old_percentage}%",
                new_value=f"{new_percentage}%",
                comments=notes,
                request=request
            )

            result = ReportDetailSerializer(report).data
            return CustomResponse.success(
                data=result,
                message=f"Progress updated to {new_percentage}%"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to update progress: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class ReportCommentView(APIView):
    """API view for report comments. RMS_REPORT_MANAGER (ED) can access and initiate on any report."""
    permission_classes = [IsAuthenticated, HasMethodPermissionOrRmsManager]
    # required_permissions checked by HasMethodPermissionOrRmsManager; RMS_REPORT_MANAGER bypasses
    serializer_class = ReportCommentSerializer
    required_permissions = {
        "get": ["view_report", "view_reportcomment", "view_institution_reports"],
        "post": ["add_reportcomment", "view_report", "view_institution_reports"],
        "delete": ["delete_reportcomment"],
    }

    def get(self, request, uid):
        """Get comments for a report"""
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).select_related('department').first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            user_dir_info = get_user_directory_info(request.user)
            is_admin = is_admin_user(request.user)
            if not user_can_access_report(report, user_dir_info, is_admin):
                return CustomResponse.errors(
                    message="You don't have access to this report",
                    code=STATUS_CODES["PERMISSION_DENIED"]
                )

            # Mark comments as read for this user when they view them
            ReportCommentRead.objects.update_or_create(
                report=report,
                user=request.user,
                defaults={'last_read_at': timezone.now()}
            )

            comments = report.comments.filter(
                is_deleted=False, parent__isnull=True
            ).order_by('-created_at')

            if request.query_params.get('paginated', 'false').lower() == 'true':
                return CustomPagination.paginate(
                    view_class=self,
                    results=comments,
                    request=request
                )

            serializer = ReportCommentSerializer(comments, many=True)
            return CustomResponse.success(
                data=serializer.data,
                message="Comments retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve comments: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def post(self, request, uid):
        """Add a comment to a report. RMS_REPORT_MANAGER can direct message to the report's department."""
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).select_related('department').first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            user_dir_info = get_user_directory_info(request.user)
            is_admin = is_admin_user(request.user)
            if not user_can_access_report(report, user_dir_info, is_admin):
                return CustomResponse.errors(
                    message="You don't have access to this report",
                    code=STATUS_CODES["PERMISSION_DENIED"]
                )

            message = request.data.get('message')
            if not message:
                return CustomResponse.errors(
                    message="Message is required",
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            # Only RMS_REPORT_MANAGER can direct message to department
            mentions_directory = False
            if is_rms_report_manager(request.user):
                mentions_directory = request.data.get('mentions_directory', False)

            parent_uid = request.data.get('parent_uid')
            parent = None
            if parent_uid:
                parent = ReportComment.objects.filter(
                    uid=parent_uid, is_deleted=False
                ).first()

            comment = ReportComment.objects.create(
                report=report,
                parent=parent,
                message=message,
                mentions_directory=mentions_directory,
                created_by=request.user,
                updated_by=request.user
            )

            create_audit_trail(
                report=report,
                action='comment_added',
                user=request.user,
                new_value=message[:100],
                request=request
            )

            serializer = ReportCommentSerializer(comment)
            return CustomResponse.success(
                data=serializer.data,
                message="Comment added successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to add comment: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def delete(self, request, uid, comment_uid):
        """Delete a comment"""
        try:
            comment = ReportComment.objects.filter(
                uid=comment_uid, report__uid=uid, is_deleted=False
            ).first()
            if not comment:
                return CustomResponse.errors(
                    message="Comment not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            comment.is_deleted = True
            comment.deleted_at = timezone.now()
            comment.deleted_by = request.user
            comment.save()

            return CustomResponse.success(
                message="Comment deleted successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to delete comment: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class ReportCommentMarkReadView(APIView):
    """Mark report comments as read for the current user (updates has_unread_comments)"""
    permission_classes = [IsAuthenticated, HasMethodPermissionOrRmsManager]
    required_permissions = {"post": ["view_report", "view_institution_reports"]}

    def post(self, request, uid):
        """Mark comments as read when user opens report/comments section"""
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            user_dir_info = get_user_directory_info(request.user)
            is_admin = is_admin_user(request.user)
            if not user_can_access_report(report, user_dir_info, is_admin):
                return CustomResponse.errors(
                    message="You don't have access to this report",
                    code=STATUS_CODES["PERMISSION_DENIED"]
                )

            ReportCommentRead.objects.update_or_create(
                report=report,
                user=request.user,
                defaults={'last_read_at': timezone.now()}
            )
            return CustomResponse.success(message="Comments marked as read")

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to mark comments as read: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class ReportAuditTrailView(APIView):
    """API view for report audit trail"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = ReportAuditTrailSerializer
    required_permissions = {
        "get": ["view_report"],
    }

    def get(self, request, uid):
        """Get audit trail for a report"""
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            audit_trail = report.audit_trail.all().order_by('-created_at')

            if request.query_params.get('paginated', 'false').lower() == 'true':
                return CustomPagination.paginate(
                    view_class=self,
                    results=audit_trail,
                    request=request
                )

            serializer = ReportAuditTrailSerializer(audit_trail, many=True)
            return CustomResponse.success(
                data=serializer.data,
                message="Audit trail retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve audit trail: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class ReportReassignView(APIView):
    """API view for reassigning a report"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "post": ["change_report"],
    }

    @transaction.atomic
    def post(self, request, uid):
        """Reassign a report to another user"""
        try:
            report = Report.objects.filter(uid=uid, is_deleted=False).first()
            if not report:
                return CustomResponse.errors(
                    message="Report not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            assigned_to_uid = request.data.get('assigned_to_uid')
            if not assigned_to_uid:
                return CustomResponse.errors(
                    message="assigned_to_uid is required",
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            old_assigned = report.assigned_to_uid
            report.assigned_to_uid = assigned_to_uid
            report.updated_by = request.user
            report.save()

            create_audit_trail(
                report=report,
                action='reassigned',
                user=request.user,
                old_value=old_assigned,
                new_value=assigned_to_uid,
                comments=request.data.get('notes', ''),
                request=request
            )

            result = ReportDetailSerializer(report).data
            return CustomResponse.success(
                data=result,
                message="Report reassigned successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to reassign report: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )
