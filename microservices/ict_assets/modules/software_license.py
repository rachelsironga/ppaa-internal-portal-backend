# software_license.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import SoftwareLicense
from microservices.ict_assets.serializers import SoftwareLicenseSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class SoftwareLicenseView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = SoftwareLicenseSerializer
    required_permissions = {
        "get": ["view_softwarelicense"],
        "post": ["add_softwarelicense", "change_softwarelicense"],
        "put": ["change_softwarelicense"],
        "patch": ["change_softwarelicense"],
        "delete": ["delete_softwarelicense"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                license_obj = SoftwareLicense.objects.filter(uid=uid, is_deleted=False).first()
                if not license_obj:
                    raise NotFound("Software License not found")
                return CustomResponse.success(data=self.serializer_class(license_obj).data)

            search_query = request.GET.get('search', '').strip()
            software_uid = request.GET.get('software', '').strip()
            status = request.GET.get('status', '').strip()

            licenses = SoftwareLicense.objects.filter(is_deleted=False)

            if software_uid:
                licenses = licenses.filter(software__uid=software_uid)

            if status:
                licenses = licenses.filter(status=status)

            if search_query:
                licenses = licenses.filter(
                    Q(software__software_name__icontains=search_query) |
                    Q(license_key__icontains=search_query) |
                    Q(assigned_to__first_name__icontains=search_query) |
                    Q(assigned_to__last_name__icontains=search_query)
                )

            if licenses.exists():
                return CustomPagination.paginate(
                    view_class=self, 
                    results=licenses, 
                    request=request
                )

            return CustomResponse.errors(message="Software Licenses not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Software Licenses: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = SoftwareLicense.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Software License not found")

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
                message=f'Failed to Change Software License: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = SoftwareLicense.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Software License not found")

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
                message=f'Failed to Update Software License: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = SoftwareLicense.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Software License not found")

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
                message=f'Failed to Partially Update Software License: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                license_obj = SoftwareLicense.objects.filter(uid=uid, is_deleted=False).first()
                if not license_obj:
                    return CustomResponse.errors(message="Software License Not Found or Already Deleted")

                license_obj.is_deleted = True
                license_obj.deleted_at = datetime.now()
                license_obj.deleted_by = request.user
                license_obj.save()

                return CustomResponse.success(message='Software License deleted successfully')

        except Exception:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting Software License"
            )
