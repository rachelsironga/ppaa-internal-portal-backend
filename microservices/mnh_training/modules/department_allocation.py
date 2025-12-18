# department_allocation.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_training.models import DepartmentAllocation, Application
from microservices.mnh_training.serializers import DepartmentAllocationSerializer, DepartmentAllocationDetailSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class DepartmentAllocationView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = DepartmentAllocationSerializer
    detail_serializer_class = DepartmentAllocationDetailSerializer

    required_permissions = {
        "get": ["view_departmentallocation"],
        "post": ["add_departmentallocation", "change_departmentallocation"],
        "put": ["change_departmentallocation"],
        "patch": ["change_departmentallocation"],
        "delete": ["delete_departmentallocation"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                allocation = DepartmentAllocation.objects.filter(uid=uid, is_deleted=False).first()
                if not allocation:
                    raise NotFound("Department Allocation not found")
                return CustomResponse.success(data=self.detail_serializer_class(allocation).data)

            search_query = request.GET.get('search', '').strip()
            application_uid = request.GET.get('application', '').strip()

            allocations = DepartmentAllocation.objects.filter(is_deleted=False)

            if application_uid:
                allocations = allocations.filter(application__uid=application_uid)

            if search_query:
                allocations = allocations.filter(
                    Q(department__name__icontains=search_query) |
                    Q(application__application_number__icontains=search_query) |
                    Q(supervisor__user__username__icontains=search_query)
                )

            if allocations.exists():
               serializer = self.list_serializer_class(
                   allocations,
                   many=True,
                   context={'request': request}
               )
               return CustomResponse.success(
                   data=serializer.data,
                   message="Success"
               )

            return CustomResponse.errors(message="Department Allocations not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Department Allocations: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = DepartmentAllocation.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Department Allocation not found")

                    serializer = self.serializer_class(
                        instance,
                        data=request.data,
                        partial=True,
                        context={'request': request}
                    )
                else:
                    serializer = self.serializer_class(
                        data=request.data,
                        context={'request': request}
                    )

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Create/Update Department Allocation: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = DepartmentAllocation.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Department Allocation not found")

                serializer = self.serializer_class(
                    instance,
                    data=request.data,
                    partial=False,
                    context={'request': request}
                )

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Update Department Allocation: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = DepartmentAllocation.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Department Allocation not found")

                serializer = self.serializer_class(
                    instance,
                    data=request.data,
                    partial=True,
                    context={'request': request}
                )

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Partially Update Department Allocation: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                allocation = DepartmentAllocation.objects.filter(uid=uid, is_deleted=False).first()
                if not allocation:
                    return CustomResponse.errors(message="Department Allocation Not Found or Already Deleted")

                allocation.is_deleted = True
                allocation.deleted_at = datetime.now()
                allocation.deleted_by = request.user
                allocation.save()

                return CustomResponse.success(message='Department Allocation deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting Department Allocation"
            )
