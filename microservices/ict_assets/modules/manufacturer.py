# manufacturer.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import Manufacturer
from microservices.ict_assets.serializers import ManufacturerSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class ManufacturerView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = ManufacturerSerializer
    required_permissions = {
        "get": [
            "view_manufacturer"
        ],
        "post": [
            "add_manufacturer",
            "change_manufacturer",
        ],
        "delete": [
            "delete_manufacturer",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                manufacturer = Manufacturer.objects.filter(uid=uid, is_deleted=False).first()
                if not manufacturer:
                    raise NotFound("Manufacturer not found")
                return CustomResponse.success(data=ManufacturerSerializer(manufacturer).data)

            search_query = request.GET.get('search', '').strip()
            manufacturers = Manufacturer.objects.filter(is_deleted=False)

            if search_query:
                manufacturers = manufacturers.filter(
                    Q(name__icontains=search_query) | 
                    Q(contact_email__icontains=search_query) |
                    Q(website__icontains=search_query)
                )

            if manufacturers.exists():
                return CustomPagination.paginate(view_class=self, results=manufacturers, request=request)

            return CustomResponse.errors(message="Manufacturers not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Manufacturers: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = Manufacturer.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except Manufacturer.DoesNotExist:
                        return CustomResponse.errors(message="Manufacturer not found")
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
            return CustomResponse.server_error(message=f'Failed to Change Manufacturer: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                manufacturer = Manufacturer.objects.filter(uid=uid, is_deleted=False).first()
                if not manufacturer:
                    return CustomResponse.errors(message="Manufacturer Not Found or Already Deleted")

                manufacturer.is_deleted = True
                manufacturer.deleted_at = datetime.now()
                manufacturer.deleted_by = request.user
                manufacturer.save()
                return CustomResponse.success(message='Manufacturer deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Manufacturer")
        

        