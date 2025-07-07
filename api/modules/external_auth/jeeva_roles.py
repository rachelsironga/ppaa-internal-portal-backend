from datetime import datetime

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from api.serializers import JeevaRoleSerializer, JeevaRoleNestedSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_model.models import JeevaRole


class JeevaRoleView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = JeevaRoleSerializer


    def get(self, request, uid=None):
        try:
            if uid:
                jeeva_role = JeevaRole.objects.filter(uid=uid, is_deleted=False).first()
                if not jeeva_role:
                    raise NotFound("Jeeva Role not found")
                return CustomResponse.success(data=JeevaRoleSerializer(jeeva_role).data)
    
            search_query = request.GET.get('search', '').strip()
            jeeva_roles = JeevaRole.objects.filter(is_deleted=False)
    
            if search_query:
                jeeva_roles = jeeva_roles.filter(
                    Q(name__icontains=search_query) | Q(code__icontains=search_query)
                )
    
            if jeeva_roles.exists():
                return CustomPagination.paginate(view_class=self, results=jeeva_roles, request=request)
    
            return CustomResponse.errors(message="Jeeva Role not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Jeeva Roles: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = JeevaRole.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except JeevaRole.DoesNotExist:
                        return CustomResponse.errors(message="Jeeva Role not found")
                else:
                    serializer = self.serializer_class(data=request.data)

                if serializer.is_valid():
                    serializer.save(created_by=request.user, updated_by=request.user)
                    return CustomResponse.success(data=serializer.data)

                # Validation failed
                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            # Catch unexpected errors that occur in the entire process
            return CustomResponse.server_error(message=f'Failed to Change Jeeva Role: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Jeeva Role by UID """
                jeeva_role = JeevaRole.objects.filter(uid=uid, is_deleted=False).first()
                if not jeeva_role:
                    return CustomResponse.errors(message="Jeeva Role Not Found or Deleted",)

                jeeva_role.is_deleted = True
                jeeva_role.deleted_at = datetime.now()
                jeeva_role.deleted_by = request.user.id
                jeeva_role.save()
                return CustomResponse.success(message='Jeeva Role deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Jeeva Role")


class JeevaRolePermissionListView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = JeevaRoleNestedSerializer

    def get(self, request, role_codename=None):
        try:
            if role_codename:
                jeeva_role = JeevaRole.objects.filter(is_deleted=False, code=role_codename, is_active=True).order_by("code")
                serializer = JeevaRoleNestedSerializer(jeeva_role, many=True)
                return CustomResponse.success(serializer.data)

            search_query = request.GET.get('search', '').strip()
            jeeva_roles = JeevaRole.objects.filter(is_deleted=False, is_active=True).order_by("code")

            if search_query:
                jeeva_roles = jeeva_roles.filter(
                    Q(name__icontains=search_query) | Q(code__icontains=search_query)
                )

            if jeeva_roles.exists():
                return CustomPagination.paginate(view_class=self, results=jeeva_roles, request=request)

            return CustomResponse.errors(message="Jeeva Role not found", data=[])
        except Exception as e:
            return CustomResponse.errors(message=f'Failed to Retrieve Jeeva Roles: {str(e)}', data=[])