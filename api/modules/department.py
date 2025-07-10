from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.http import Http404
from oauthlib.openid.connect.core.exceptions import LoginRequired
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from api.serializers import DepartmentSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.models import Department
from utils.permissions import HasMethodPermission



class DepartmentView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = DepartmentSerializer

    def get(self, request, uid=None):
        try:
            """ Retrieve a single department by UID or list departments with optional search """
            if uid:
                department = Department.objects.filter(uid=uid, is_deleted=False).first()
                if not department:
                    raise NotFound("Department not found")
                return CustomResponse.success(data=DepartmentSerializer(department).data)

            search_query = request.GET.get('search', '').strip()
            directory_uid = request.GET.get('directory', '').strip()

            departments = Department.objects.filter(is_deleted=False)

            if directory_uid:
                departments = departments.filter(directory__uid=directory_uid)

            if search_query:
                departments = departments.filter(
                    Q(name__icontains=search_query) | Q(code__icontains=search_query)
                )

            if departments.exists():
                return CustomPagination.paginate(view_class=self, results=departments, request=request)

            return CustomResponse.errors(message="Department not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Departments: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)

                # Handle an Update case
                if uid:
                    try:
                        instance = Department.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except Department.DoesNotExist:
                        return CustomResponse.errors(message="Department not found")

                # Handle Create case (when no uid)
                else:
                    serializer = self.serializer_class(data=request.data)

                # Validate and save
                if serializer.is_valid():
                    serializer.save(created_by=request.user, updated_by=request.user)
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            # Catch unexpected errors that occur in the entire process
            return CustomResponse.server_error(message=f'Failed to Change Department: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a department by UID """
                department = Department.objects.filter(uid=uid, is_deleted=False).first()
                if not department:
                    return CustomResponse.errors(message="Department Not Found or Deleted", )

                department.is_deleted = True
                department.deleted_at = datetime.now()
                department.deleted_by = request.user.id
                department.save()
                return CustomResponse.success(message='Department deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Department")
