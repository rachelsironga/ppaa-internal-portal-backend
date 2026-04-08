from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_portal.pagination import CustomPagination
from utils.permissions import HasMethodPermission

from ..models import Stakeholder
from ..serializers import StakeholderSerializer
from .report import create_audit_trail


class StakeholderView(APIView):
    """API view for Stakeholder management"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = StakeholderSerializer
    required_permissions = {
        "get": ["view_stakeholder"],
        "post": ["add_stakeholder"],
        "put": ["change_stakeholder"],
        "patch": ["change_stakeholder"],
        "delete": ["delete_stakeholder"],
    }

    def get(self, request, uid=None):
        """Get stakeholder(s)"""
        try:
            if uid:
                stakeholder = Stakeholder.objects.filter(
                    uid=uid, is_deleted=False
                ).first()
                if not stakeholder:
                    return CustomResponse.errors(
                        message="Stakeholder not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                serializer = StakeholderSerializer(stakeholder)
                return CustomResponse.success(
                    data=serializer.data,
                    message="Stakeholder retrieved successfully"
                )

            queryset = Stakeholder.objects.filter(is_deleted=False)

            # Filters
            organization_type = request.query_params.get('organization_type')
            if organization_type:
                queryset = queryset.filter(organization_type=organization_type)

            is_active = request.query_params.get('is_active')
            if is_active:
                queryset = queryset.filter(is_active=is_active.lower() == 'true')

            search = request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(contact_person__icontains=search) |
                    Q(email__icontains=search)
                )

            queryset = queryset.order_by('name')

            if request.query_params.get('paginated', 'false').lower() == 'true':
                return CustomPagination.paginate(
                    view_class=self,
                    results=queryset,
                    request=request
                )

            serializer = StakeholderSerializer(queryset, many=True)
            return CustomResponse.success(
                data=serializer.data,
                message="Stakeholders retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve Stakeholders: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def post(self, request):
        """Create a new stakeholder"""
        try:
            serializer = StakeholderSerializer(data=request.data)
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            stakeholder = serializer.save(created_by=request.user, updated_by=request.user)
            create_audit_trail(
                report=None,
                action="created",
                user=request.user,
                new_value=stakeholder.name,
                request=request,
                entity_type="Stakeholder",
                entity_uid=stakeholder.uid,
                entity_name=stakeholder.name,
            )
            return CustomResponse.success(
                data=serializer.data,
                message="Stakeholder created successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to create Stakeholder: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def put(self, request, uid):
        """Update a stakeholder"""
        try:
            stakeholder = Stakeholder.objects.filter(
                uid=uid, is_deleted=False
            ).first()
            if not stakeholder:
                return CustomResponse.errors(
                    message="Stakeholder not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            serializer = StakeholderSerializer(
                stakeholder, data=request.data, partial=True
            )
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            old_value = stakeholder.name
            stakeholder = serializer.save(updated_by=request.user)
            create_audit_trail(
                report=None,
                action="updated",
                user=request.user,
                old_value=old_value,
                new_value=stakeholder.name,
                request=request,
                entity_type="Stakeholder",
                entity_uid=stakeholder.uid,
                entity_name=stakeholder.name,
            )
            return CustomResponse.success(
                data=serializer.data,
                message="Stakeholder updated successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to update Stakeholder: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def delete(self, request, uid):
        """Soft delete a stakeholder"""
        try:
            stakeholder = Stakeholder.objects.filter(
                uid=uid, is_deleted=False
            ).first()
            if not stakeholder:
                return CustomResponse.errors(
                    message="Stakeholder not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            old_value = stakeholder.name
            stakeholder.is_deleted = True
            stakeholder.deleted_at = timezone.now()
            stakeholder.deleted_by = request.user
            stakeholder.save()
            create_audit_trail(
                report=None,
                action="deleted",
                user=request.user,
                old_value=old_value,
                request=request,
                entity_type="Stakeholder",
                entity_uid=stakeholder.uid,
                entity_name=stakeholder.name,
            )

            return CustomResponse.success(
                message="Stakeholder deleted successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to delete Stakeholder: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )
