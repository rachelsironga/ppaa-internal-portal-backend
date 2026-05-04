from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_portal.pagination import CustomPagination
from utils.permissions import HasMethodPermission

from ..models import ReportCategory
from ..serializers import ReportCategorySerializer
from .report import create_audit_trail


class ReportCategoryView(APIView):
    """API view for Report Category management"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = ReportCategorySerializer
    required_permissions = {
        "get": ["view_reportcategory"],
        "post": ["add_reportcategory"],
        "put": ["change_reportcategory"],
        "patch": ["change_reportcategory"],
        "delete": ["delete_reportcategory"],
    }

    def get(self, request, uid=None):
        """Get report category(ies)"""
        try:
            if uid:
                category = ReportCategory.objects.filter(
                    uid=uid, is_deleted=False
                ).first()
                if not category:
                    return CustomResponse.errors(
                        message="Report Category not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                serializer = ReportCategorySerializer(category)
                return CustomResponse.success(
                    data=serializer.data,
                    message="Report Category retrieved successfully"
                )

            queryset = ReportCategory.objects.filter(is_deleted=False)

            # Filters
            is_active = request.query_params.get('is_active')
            if is_active:
                queryset = queryset.filter(is_active=is_active.lower() == 'true')

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

            serializer = ReportCategorySerializer(queryset, many=True)
            return CustomResponse.success(
                data=serializer.data,
                message="Report Categories retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve Report Categories: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def post(self, request):
        """Create a new report category"""
        try:
            serializer = ReportCategorySerializer(data=request.data)
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            category = serializer.save(created_by=request.user, updated_by=request.user)
            create_audit_trail(
                report=None,
                action="created",
                user=request.user,
                new_value=category.name,
                request=request,
                entity_type="Report Category",
                entity_uid=category.uid,
                entity_name=category.name,
            )
            return CustomResponse.success(
                data=serializer.data,
                message="Report Category created successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to create Report Category: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def put(self, request, uid):
        """Update a report category"""
        try:
            category = ReportCategory.objects.filter(
                uid=uid, is_deleted=False
            ).first()
            if not category:
                return CustomResponse.errors(
                    message="Report Category not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            serializer = ReportCategorySerializer(
                category, data=request.data, partial=True
            )
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            old_value = category.name
            category = serializer.save(updated_by=request.user)
            create_audit_trail(
                report=None,
                action="updated",
                user=request.user,
                old_value=old_value,
                new_value=category.name,
                request=request,
                entity_type="Report Category",
                entity_uid=category.uid,
                entity_name=category.name,
            )
            return CustomResponse.success(
                data=serializer.data,
                message="Report Category updated successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to update Report Category: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def delete(self, request, uid):
        """Soft delete a report category"""
        try:
            category = ReportCategory.objects.filter(
                uid=uid, is_deleted=False
            ).first()
            if not category:
                return CustomResponse.errors(
                    message="Report Category not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            old_value = category.name
            category.is_deleted = True
            category.deleted_at = timezone.now()
            category.deleted_by = request.user
            category.save()
            create_audit_trail(
                report=None,
                action="deleted",
                user=request.user,
                old_value=old_value,
                request=request,
                entity_type="Report Category",
                entity_uid=category.uid,
                entity_name=category.name,
            )

            return CustomResponse.success(
                message="Report Category deleted successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to delete Report Category: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )
