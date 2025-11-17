# software_installation.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import SoftwareInstallation
from microservices.ict_assets.serializers import SoftwareInstallationSerializer, SoftwareInstallationDetailSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class SoftwareInstallationView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = SoftwareInstallationSerializer
    required_permissions = {
        "get": [
            "view_softwareinstallation"
        ],
        "post": [
            "add_softwareinstallation",
            "change_softwareinstallation",
        ],
        "delete": [
            "delete_softwareinstallation",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                installation = SoftwareInstallation.objects.filter(uid=uid, is_deleted=False).first()
                if not installation:
                    raise NotFound("Software Installation not found")
                return CustomResponse.success(data=SoftwareInstallationDetailSerializer(installation).data)

            search_query = request.GET.get('search', '').strip()
            software_uid = request.GET.get('software', '').strip()
            asset_uid = request.GET.get('asset', '').strip()
            
            installations = SoftwareInstallation.objects.filter(is_deleted=False)

            if software_uid:
                installations = installations.filter(software__uid=software_uid)

            if asset_uid:
                installations = installations.filter(asset__uid=asset_uid)

            if search_query:
                installations = installations.filter(
                    Q(software__name__icontains=search_query) | 
                    Q(asset__asset_tag__icontains=search_query) |
                    Q(license_key__icontains=search_query)
                )

            if installations.exists():
                return CustomPagination.paginate(view_class=self, results=installations, request=request)

            return CustomResponse.errors(message="Software Installations not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Software Installations: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = SoftwareInstallation.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except SoftwareInstallation.DoesNotExist:
                        return CustomResponse.errors(message="Software Installation not found")
                else:
                    serializer = self.serializer_class(data=request.data, context={'request': request})

                if serializer.is_valid():
                    serializer.save(installed_by=request.user)
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Change Software Installation: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                installation = SoftwareInstallation.objects.filter(uid=uid, is_deleted=False).first()
                if not installation:
                    return CustomResponse.errors(message="Software Installation Not Found or Already Deleted")

                installation.is_deleted = True
                installation.deleted_at = datetime.now()
                installation.deleted_by = request.user
                installation.save()
                return CustomResponse.success(message='Software Installation deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Software Installation")
        


