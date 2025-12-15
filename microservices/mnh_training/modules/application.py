# application.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_training.models import Application
from microservices.mnh_training.serializers import ApplicationSerializer, ApplicationListSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class ApplicationView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = ApplicationSerializer
    list_serializer_class = ApplicationListSerializer

    required_permissions = {
        "get": ["view_application"],
        "post": ["add_application", "change_application"],
        "put": ["change_application"],
        "patch": ["change_application"],
        "delete": ["delete_application"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                application = Application.objects.filter(uid=uid, is_deleted=False).first()
                if not application:
                    raise NotFound("Application not found")
                return CustomResponse.success(data=self.serializer_class(application).data)

            search_query = request.GET.get('search', '').strip()
            placement_type = request.GET.get('placement_type', '').strip()
            category = request.GET.get('category', '').strip()
            from_date = request.GET.get('from_date', '').strip()
            to_date = request.GET.get('to_date', '').strip()

            applications = Application.objects.filter(is_deleted=False)

            if placement_type:
                applications = applications.filter(placement_type=placement_type)

            if category:
                applications = applications.filter(category=category)

            if from_date:
                applications = applications.filter(from_date__gte=from_date)

            if to_date:
                applications = applications.filter(to_date__lte=to_date)

            if search_query:
                applications = applications.filter(
                    Q(application_number__icontains=search_query) |
                    Q(student__first_name__icontains=search_query) |
                    Q(student__last_name__icontains=search_query) |
                    Q(student__email__icontains=search_query)
                )

            if applications.exists():
                return CustomPagination.paginate(
                    view_class=self,
                    results=applications,
                    request=request,
                    serializer=self.list_serializer_class
                )

            return CustomResponse.errors(message="Applications not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Applications: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = Application.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Application not found")

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
                message=f'Failed to Create/Update Application: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = Application.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Application not found")

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
                message=f'Failed to Update Application: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = Application.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Application not found")

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
                message=f'Failed to Partially Update Application: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                application = Application.objects.filter(uid=uid, is_deleted=False).first()
                if not application:
                    return CustomResponse.errors(message="Application Not Found or Already Deleted")

                application.is_deleted = True
                application.deleted_at = datetime.now()
                application.deleted_by = request.user
                application.save()

                return CustomResponse.success(message='Application deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting Application"
            )
