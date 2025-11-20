# peripheral.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import Peripheral
from microservices.ict_assets.serializers import PeripheralSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class PeripheralView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = PeripheralSerializer

    required_permissions = {
        "get": ["view_peripheral"],
        "post": ["add_peripheral", "change_peripheral"],
        "put": ["change_peripheral"],
        "patch": ["change_peripheral"],
        "delete": ["delete_peripheral"],
    }

    def _normalize_field_value(self, field_value):
        """Convert field value to lowercase for consistent handling"""
        if field_value:
            return field_value.strip().lower()
        return field_value

    def _prepare_request_data(self, request_data):
        """Prepare request data by normalizing peripheral_type and connection_type if present"""
        data = request_data.copy()
        if 'peripheral_type' in data and data['peripheral_type']:
            data['peripheral_type'] = self._normalize_field_value(data['peripheral_type'])
        if 'connection_type' in data and data['connection_type']:
            data['connection_type'] = self._normalize_field_value(data['connection_type'])
        return data

    def get(self, request, uid=None):
        try:
            if uid:
                peripheral = Peripheral.objects.filter(uid=uid, is_deleted=False).first()
                if not peripheral:
                    raise NotFound("Peripheral not found")
                return CustomResponse.success(data=self.serializer_class(peripheral).data)

            search_query = request.GET.get('search', '').strip()
            asset_uid = request.GET.get('asset', '').strip()
            peripheral_type = request.GET.get('peripheral_type', '').strip()
            connection_type = request.GET.get('connection_type', '').strip()
            
            peripherals = Peripheral.objects.filter(is_deleted=False)

            if asset_uid:
                peripherals = peripherals.filter(asset__uid=asset_uid)

            if peripheral_type:
                # Normalize peripheral_type for filtering
                normalized_peripheral_type = self._normalize_field_value(peripheral_type)
                peripherals = peripherals.filter(peripheral_type=normalized_peripheral_type)

            if connection_type:
                # Normalize connection_type for filtering
                normalized_connection_type = self._normalize_field_value(connection_type)
                peripherals = peripherals.filter(connection_type=normalized_connection_type)

            if search_query:
                peripherals = peripherals.filter(
                    Q(asset__asset_tag__icontains=search_query) |
                    Q(peripheral_type__icontains=search_query) |
                    Q(connection_type__icontains=search_query) |
                    Q(description__icontains=search_query)
                )

            if peripherals.exists():
                return CustomPagination.paginate(
                    view_class=self, 
                    results=peripherals, 
                    request=request
                )

            return CustomResponse.errors(message="Peripherals not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Peripherals: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                # Prepare data with normalized fields
                prepared_data = self._prepare_request_data(request.data)
                uid = prepared_data.get('uid')

                if uid:
                    instance = Peripheral.objects.filter(asset__uid=uid).first()
                    if not instance:
                        return CustomResponse.errors(message="Peripheral not found")

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
                message=f'Failed to Change Peripheral: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = Peripheral.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Peripheral not found")

                # Prepare data with normalized fields
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
                message=f'Failed to Update Peripheral: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = Peripheral.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Peripheral not found")

                # Prepare data with normalized fields
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
                message=f'Failed to Partially Update Peripheral: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                peripheral = Peripheral.objects.filter(uid=uid, is_deleted=False).first()
                if not peripheral:
                    return CustomResponse.errors(message="Peripheral Not Found or Already Deleted")

                peripheral.is_deleted = True
                peripheral.deleted_at = datetime.now()
                peripheral.deleted_by = request.user
                peripheral.save()

                return CustomResponse.success(message='Peripheral deleted successfully')

        except Exception:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting Peripheral"
            )