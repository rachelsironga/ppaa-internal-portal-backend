from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_portal.pagination import CustomPagination
from utils.permissions import HasMethodPermission

from ..models import ReportType
from ..serializers import ReportTypeSerializer
from .report import create_audit_trail


class ReportTypeView(APIView):
    """API view for Report Type management"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = ReportTypeSerializer
    required_permissions = {
        "get": ["view_reporttype"],
        "post": ["add_reporttype"],
        "put": ["change_reporttype"],
        "patch": ["change_reporttype"],
        "delete": ["delete_reporttype"],
    }

    def get(self, request, uid=None):
        """Get report type(s)"""
        try:
            if uid:
                report_type = ReportType.objects.filter(
                    uid=uid, is_deleted=False
                ).first()
                if not report_type:
                    return CustomResponse.errors(
                        message="Report Type not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                serializer = ReportTypeSerializer(report_type)
                return CustomResponse.success(
                    data=serializer.data,
                    message="Report Type retrieved successfully"
                )

            queryset = ReportType.objects.filter(is_deleted=False)

            # Filters
            frequency = request.query_params.get('frequency')
            if frequency:
                queryset = queryset.filter(frequency=frequency)

            is_active = request.query_params.get('is_active')
            if is_active:
                queryset = queryset.filter(is_active=is_active.lower() == 'true')

            requires_attachment = request.query_params.get('requires_attachment')
            if requires_attachment:
                queryset = queryset.filter(
                    requires_attachment=requires_attachment.lower() == 'true'
                )

            search = request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(code__icontains=search)
                )

            queryset = queryset.order_by('name')

            if request.query_params.get('paginated', 'false').lower() == 'true':
                return CustomPagination.paginate(
                    view_class=self,
                    results=queryset,
                    request=request
                )

            serializer = ReportTypeSerializer(queryset, many=True)
            return CustomResponse.success(
                data=serializer.data,
                message="Report Types retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve Report Types: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def post(self, request):
        """Create a new report type"""
        try:
            serializer = ReportTypeSerializer(data=request.data)
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            report_type = serializer.save(created_by=request.user, updated_by=request.user)
            create_audit_trail(
                report=None,
                action="created",
                user=request.user,
                new_value=report_type.name,
                request=request,
                entity_type="Report Type",
                entity_uid=report_type.uid,
                entity_name=report_type.name,
            )
            return CustomResponse.success(
                data=serializer.data,
                message="Report Type created successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to create Report Type: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def put(self, request, uid):
        """Update a report type"""
        try:
            report_type = ReportType.objects.filter(
                uid=uid, is_deleted=False
            ).first()
            if not report_type:
                return CustomResponse.errors(
                    message="Report Type not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            serializer = ReportTypeSerializer(
                report_type, data=request.data, partial=True
            )
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            old_value = report_type.name
            report_type = serializer.save(updated_by=request.user)
            create_audit_trail(
                report=None,
                action="updated",
                user=request.user,
                old_value=old_value,
                new_value=report_type.name,
                request=request,
                entity_type="Report Type",
                entity_uid=report_type.uid,
                entity_name=report_type.name,
            )
            return CustomResponse.success(
                data=serializer.data,
                message="Report Type updated successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to update Report Type: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def delete(self, request, uid):
        """Soft delete a report type"""
        try:
            report_type = ReportType.objects.filter(
                uid=uid, is_deleted=False
            ).first()
            if not report_type:
                return CustomResponse.errors(
                    message="Report Type not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            # Check if report type is in use
            if report_type.reports.filter(is_deleted=False).exists():
                return CustomResponse.errors(
                    message="Cannot delete Report Type with associated reports",
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            old_value = report_type.name
            report_type.is_deleted = True
            report_type.deleted_at = timezone.now()
            report_type.deleted_by = request.user
            report_type.save()
            create_audit_trail(
                report=None,
                action="deleted",
                user=request.user,
                old_value=old_value,
                request=request,
                entity_type="Report Type",
                entity_uid=report_type.uid,
                entity_name=report_type.name,
            )

            return CustomResponse.success(
                message="Report Type deleted successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to delete Report Type: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )
