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
        "get": [
            "view_peripheral"
        ],
        "post": [
            "add_peripheral",
            "change_peripheral",
        ],
        "delete": [
            "delete_peripheral",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                peripheral = Peripheral.objects.filter(uid=uid, is_deleted=False).first()
                if not peripheral:
                    raise NotFound("Peripheral not found")
                return CustomResponse.success(data=PeripheralSerializer(peripheral).data)

            search_query = request.GET.get('search', '').strip()
            asset_uid = request.GET.get('asset', '').strip()
            peripheral_type = request.GET.get('peripheral_type', '').strip()
            connection_type = request.GET.get('connection_type', '').strip()
            
            peripherals = Peripheral.objects.filter(is_deleted=False)

            if asset_uid:
                peripherals = peripherals.filter(asset__uid=asset_uid)

            if peripheral_type:
                peripherals = peripherals.filter(peripheral_type=peripheral_type)

            if connection_type:
                peripherals = peripherals.filter(connection_type=connection_type)

            if search_query:
                peripherals = peripherals.filter(
                    Q(asset__asset_tag__icontains=search_query) | 
                    Q(peripheral_type__icontains=search_query) |
                    Q(connection_type__icontains=search_query)
                )

            if peripherals.exists():
                return CustomPagination.paginate(view_class=self, results=peripherals, request=request)

            return CustomResponse.errors(message="Peripherals not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Peripherals: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = Peripheral.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except Peripheral.DoesNotExist:
                        return CustomResponse.errors(message="Peripheral not found")
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
            return CustomResponse.server_error(message=f'Failed to Change Peripheral: {str(e)}')

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

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Peripheral")
        

        