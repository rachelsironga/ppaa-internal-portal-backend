# network_device.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import NetworkDevice
from microservices.ict_assets.serializers import NetworkDeviceSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class NetworkDeviceView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = NetworkDeviceSerializer
    required_permissions = {
        "get": [
            "view_networkdevice"
        ],
        "post": [
            "add_networkdevice",
            "change_networkdevice",
        ],
        "delete": [
            "delete_networkdevice",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                network_device = NetworkDevice.objects.filter(uid=uid, is_deleted=False).first()
                if not network_device:
                    raise NotFound("Network Device not found")
                return CustomResponse.success(data=NetworkDeviceSerializer(network_device).data)

            search_query = request.GET.get('search', '').strip()
            asset_uid = request.GET.get('asset', '').strip()
            device_type = request.GET.get('device_type', '').strip()
            
            network_devices = NetworkDevice.objects.filter(is_deleted=False)

            if asset_uid:
                network_devices = network_devices.filter(asset__uid=asset_uid)

            if device_type:
                network_devices = network_devices.filter(device_type=device_type)

            if search_query:
                network_devices = network_devices.filter(
                    Q(asset__asset_tag__icontains=search_query) | 
                    Q(ip_address__icontains=search_query) |
                    Q(mac_address__icontains=search_query) |
                    Q(device_type__icontains=search_query)
                )

            if network_devices.exists():
                return CustomPagination.paginate(view_class=self, results=network_devices, request=request)

            return CustomResponse.errors(message="Network Devices not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Network Devices: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = NetworkDevice.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except NetworkDevice.DoesNotExist:
                        return CustomResponse.errors(message="Network Device not found")
                else:
                    serializer = self.serializer_class(data=request.data, context={'request': request})

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Change Network Device: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                network_device = NetworkDevice.objects.filter(uid=uid, is_deleted=False).first()
                if not network_device:
                    return CustomResponse.errors(message="Network Device Not Found or Already Deleted")

                network_device.is_deleted = True
                network_device.deleted_at = datetime.now()
                network_device.deleted_by = request.user
                network_device.save()
                return CustomResponse.success(message='Network Device deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Network Device")
        

        