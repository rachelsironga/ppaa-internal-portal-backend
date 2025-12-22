# supervisor.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_training.models import Supervisor
from microservices.mnh_training.serializers import SupervisorSerializer, SupervisorListSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class SupervisorView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = SupervisorSerializer
    list_serializer_class = SupervisorListSerializer

    required_permissions = {
        "get": ["view_supervisor"],
        "post": ["add_supervisor", "change_supervisor"],
        "put": ["change_supervisor"],
        "patch": ["change_supervisor"],
        "delete": ["delete_supervisor"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                supervisor = Supervisor.objects.filter(uid=uid, is_deleted=False).first()
                if not supervisor:
                    raise NotFound("Supervisor not found")
                return CustomResponse.success(data=self.serializer_class(supervisor).data)

            search_query = request.GET.get('search', '').strip()
            department_uid = request.GET.get('department', '').strip()

            supervisors = Supervisor.objects.filter(is_deleted=False)

            if department_uid:
                supervisors = supervisors.filter(department_uid=department_uid)

            if search_query:
                supervisors = supervisors.filter(
                    Q(user_guid__icontains=search_query) |
                    Q(department_uid__icontains=search_query) |
                    Q(description__icontains=search_query)
                )

            if supervisors.exists():
               serializer = self.list_serializer_class(
                   supervisors,
                   many=True,
                   context={'request': request}
               )
               return CustomResponse.success(
                   data=serializer.data,
                   message="Success"
               )

            return CustomResponse.errors(message="Supervisors not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Supervisors: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = Supervisor.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Supervisor not found")

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
                message=f'Failed to Create/Update Supervisor: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = Supervisor.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Supervisor not found")

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
                message=f'Failed to Update Supervisor: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = Supervisor.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Supervisor not found")

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
                message=f'Failed to Partially Update Supervisor: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                supervisor = Supervisor.objects.filter(uid=uid, is_deleted=False).first()
                if not supervisor:
                    return CustomResponse.errors(message="Supervisor Not Found or Already Deleted")

                supervisor.is_deleted = True
                supervisor.deleted_at = datetime.now()
                supervisor.deleted_by = request.user
                supervisor.save()

                return CustomResponse.success(message='Supervisor deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting Supervisor"
            )
