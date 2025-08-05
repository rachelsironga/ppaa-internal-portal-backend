from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.models import User, UserProfile
from mnh_auth.serializers import UserSerializer, FileUploadSerializer, GroupSerializer, PermissionSerializer
from utils.minio_storage import MinioStorage
from utils.permissions import HasMethodPermission

from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound
from rest_framework import serializers

from utils.permissions import HasMethodPermission

class SystemRoleView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = GroupSerializer
    required_permissions = {
        "get": ["can_view_group"],
        "post": ["can_add_group"],
        "delete": ["can_delete_group"]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                group = Group.objects.filter(id=uid).first()
                if not group:
                    raise NotFound("Group not found")
                return CustomResponse.success(data=self.serializer_class(group).data)

            # List all groups with optional search
            groups = Group.objects.all()
            search_query = request.GET.get('search', '').strip()
            if search_query:
                groups = groups.filter(Q(name__icontains=search_query))

            if groups.exists():
                return CustomPagination.paginate(
                    view_class=self,
                    results=groups,
                    request=request,
                    serializer_context={}
                )

            return CustomResponse.errors(message="No groups found", data=[])

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Groups: {str(e)}')

    def post(self, request, uid=None):
        """Create or update a group with permissions"""
        try:
            with transaction.atomic():
                instance = None
                is_update = False

                if uid:
                    instance = Group.objects.filter(id=uid).first()
                    if not instance:
                        return CustomResponse.errors(message="Group not found")
                    is_update = True

                serializer = self.serializer_class(
                    instance=instance,
                    data=request.data,
                    partial=is_update,
                    context={"request": request}
                )

                if not serializer.is_valid():
                    return CustomResponse.errors(
                        message="Validation failed",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )

                group = serializer.save()

                # Handle permissions if provided
                permissions = request.data.get("permissions", [])
                if isinstance(permissions, list):
                    group.permissions.set(Permission.objects.filter(id__in=permissions))

                return CustomResponse.success(data=self.serializer_class(group).data)

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Save Group: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                group = Group.objects.filter(id=uid).first()
                if not group:
                    return CustomResponse.errors(message="Group Not Found")

                group.delete()
                return CustomResponse.success(message='Group deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to Delete Group: {str(e)}")

class SystemPermissionView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = PermissionSerializer
    required_permissions = {
        "get": ["can_view_system_permission"]
    }

    def get(self, request):

        try:
            search_query = request.GET.get('search', '').strip()
            selected_role = request.GET.get("selected_role",None)

            if selected_role is not None :
                try:
                    group = Group.objects.get(id=selected_role)
                    permissions = Permission.objects.exclude(
                        id__in=group.permissions.values_list('id', flat=True)
                    )
                except Group.DoesNotExist:
                    permissions = Permission.objects.all()
            else:
                permissions = Permission.objects.all()

            # Optional search by name or codename
            if search_query:
                permissions = permissions.filter(
                    Q(name__icontains=search_query) |
                    Q(codename__icontains=search_query) |
                    Q(content_type__model__icontains=search_query)
                )


            if permissions.exists():
                return CustomPagination.paginate(
                    view_class=self,
                    results=permissions,
                    request=request,
                    serializer_context={}
                )

            return CustomResponse.errors(message="No Permission found", data=[])

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Permissions: {str(e)}')


class SystemRoleUsers(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = UserSerializer

    required_permissions = {
        "get": ["can_view_group"]
    }

    def get(self, request):
        try:
            role_id = request.GET.get('role_id', 0)
            if not role_id:
                return CustomResponse.errors(message=f'Users not Found', )

            users = User.objects.filter(is_deleted=False, groups__id=int(role_id))

            search_query = request.GET.get('search', '').strip()
            if search_query:
                users = users.filter(
                    Q(username__icontains=search_query) |
                    Q(email__icontains=search_query) |
                    Q(pf_number__icontains=search_query) |
                    Q(check_number__icontains=search_query) |
                    Q(first_name__icontains=search_query) |
                    Q(middle_name__icontains=search_query) |
                    Q(last_name__icontains=search_query) |
                    Q(phone_number__icontains=search_query) |
                    Q(alternative_contact__icontains=search_query)
                )

            if users.exists():
                context = {"is_auth_view": False}
                return CustomPagination.paginate(
                    view_class=self,
                    results=users,
                    request=request,
                    serializer_context=context
                )

            return CustomResponse.errors(message="User not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Users: {str(e)}', )
