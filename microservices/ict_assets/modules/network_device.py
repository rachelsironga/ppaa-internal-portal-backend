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
        "get": ["view_networkdevice"],
        "post": ["add_networkdevice", "change_networkdevice"],
        "put": ["change_networkdevice"],
        "patch": ["change_networkdevice"],
        "delete": ["delete_networkdevice"],
    }

    def _normalize_device_type(self, device_type):
        """Convert device type to lowercase for consistent handling"""
        if device_type:
            return device_type.strip().lower()
        return device_type

    def _prepare_request_data(self, request_data):
        """Prepare request data by normalizing device_type if present"""
        data = request_data.copy()
        if 'device_type' in data and data['device_type']:
            data['device_type'] = self._normalize_device_type(data['device_type'])
        return data

    def get(self, request, uid=None):
        try:
            if uid:
                network_device = NetworkDevice.objects.filter(uid=uid, is_deleted=False).first()
                if not network_device:
                    raise NotFound("Network Device not found")
                return CustomResponse.success(data=self.serializer_class(network_device).data)

            search_query = request.GET.get('search', '').strip()
            asset_uid = request.GET.get('asset', '').strip()
            device_type = request.GET.get('device_type', '').strip()
            
            network_devices = NetworkDevice.objects.filter(is_deleted=False)

            if asset_uid:
                network_devices = network_devices.filter(asset__uid=asset_uid)

            if device_type:
                # Normalize device_type for filtering
                normalized_device_type = self._normalize_device_type(device_type)
                network_devices = network_devices.filter(device_type=normalized_device_type)

            if search_query:
                network_devices = network_devices.filter(
                    Q(asset__asset_tag__icontains=search_query) |
                    Q(hostname__icontains=search_query) |
                    Q(ip_address__icontains=search_query) |
                    Q(mac_address__icontains=search_query) |
                    Q(device_type__icontains=search_query)
                )

            if network_devices.exists():
                return CustomPagination.paginate(
                    view_class=self, 
                    results=network_devices, 
                    request=request
                )

            return CustomResponse.errors(message="Network Devices not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Network Devices: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                # Prepare data with normalized device_type
                prepared_data = self._prepare_request_data(request.data)
                uid = prepared_data.get('uid')

                if uid:
                    instance = NetworkDevice.objects.filter(asset__uid=uid).first()
                    if not instance:
                        return CustomResponse.errors(message="Network Device not found")

                    serializer = self.serializer_class(
                        instance,
                        data=prepared_data,
                        partial=True,
                        context={'request': request}
                    )
                else:
                    serializer = self.serializer_class(
                        data=prepared_data,
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
                message=f'Failed to Change Network Device: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = NetworkDevice.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Network Device not found")

                # Prepare data with normalized device_type
                prepared_data = self._prepare_request_data(request.data)

                serializer = self.serializer_class(
                    instance,
                    data=prepared_data,
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
                message=f'Failed to Update Network Device: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = NetworkDevice.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Network Device not found")

                # Prepare data with normalized device_type
                prepared_data = self._prepare_request_data(request.data)

                serializer = self.serializer_class(
                    instance,
                    data=prepared_data,
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
                message=f'Failed to Partially Update Network Device: {str(e)}'
            )

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

        except Exception:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting Network Device"
            )