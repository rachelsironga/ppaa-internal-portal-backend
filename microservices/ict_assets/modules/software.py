# software.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import Software
from microservices.ict_assets.serializers import SoftwareSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class SoftwareView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = SoftwareSerializer
    
    required_permissions = {
        "get": ["view_software"],
        "post": ["add_software", "change_software"],
        "put": ["change_software"],
        "patch": ["change_software"],
        "delete": ["delete_software"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                software = Software.objects.filter(uid=uid, is_deleted=False).first()
                if not software:
                    raise NotFound("Software not found")
                return CustomResponse.success(data=self.serializer_class(software).data)

            search_query = request.GET.get('search', '').strip()
            category_uid = request.GET.get('category', '').strip()
            license_type = request.GET.get('license_type', '').strip()
            
            software_list = Software.objects.filter(is_deleted=False)

            if category_uid:
                software_list = software_list.filter(category__uid=category_uid)

            if license_type:
                software_list = software_list.filter(license_type=license_type)

            if search_query:
                software_list = software_list.filter(
                    Q(software_name__icontains=search_query) | 
                    Q(version__icontains=search_query) |
                    Q(publisher__icontains=search_query) |
                    Q(asset_tag__icontains=search_query) |
                    Q(category__name__icontains=search_query)
                )

            if software_list.exists():
                return CustomPagination.paginate(
                    view_class=self, 
                    results=software_list, 
                    request=request
                )

            return CustomResponse.errors(message="Software not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Software: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = Software.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Software not found")

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
                message=f'Failed to Change Software: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = Software.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Software not found")

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
                message=f'Failed to Update Software: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = Software.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Software not found")

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
                message=f'Failed to Partially Update Software: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                software = Software.objects.filter(uid=uid, is_deleted=False).first()
                if not software:
                    return CustomResponse.errors(message="Software Not Found or Already Deleted")

                software.is_deleted = True
                software.deleted_at = datetime.now()
                software.deleted_by = request.user
                software.save()

                return CustomResponse.success(message='Software deleted successfully')

        except Exception:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting Software"
            )