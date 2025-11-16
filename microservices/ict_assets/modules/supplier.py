# supplier.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import Supplier
from microservices.ict_assets.serializers import SupplierSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class SupplierView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = SupplierSerializer
    required_permissions = {
        "get": [
            "view_supplier"
        ],
        "post": [
            "add_supplier",
            "change_supplier",
        ], 
        "delete": [
            "delete_supplier",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                supplier = Supplier.objects.filter(uid=uid, is_deleted=False).first()
                if not supplier:
                    raise NotFound("Supplier not found")
                return CustomResponse.success(data=SupplierSerializer(supplier).data)

            search_query = request.GET.get('search', '').strip()
            suppliers = Supplier.objects.filter(is_deleted=False)

            if search_query:
                suppliers = suppliers.filter(
                    Q(name__icontains=search_query) | 
                    Q(contact_person__icontains=search_query) |
                    Q(email__icontains=search_query) |
                    Q(phone__icontains=search_query)
                )

            if suppliers.exists():
                return CustomPagination.paginate(view_class=self, results=suppliers, request=request)

            return CustomResponse.errors(message="Suppliers not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Suppliers: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = Supplier.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except Supplier.DoesNotExist:
                        return CustomResponse.errors(message="Supplier not found")
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
            return CustomResponse.server_error(message=f'Failed to Change Supplier: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                supplier = Supplier.objects.filter(uid=uid, is_deleted=False).first()
                if not supplier:
                    return CustomResponse.errors(message="Supplier Not Found or Already Deleted")

                supplier.is_deleted = True
                supplier.deleted_at = datetime.now()
                supplier.deleted_by = request.user
                supplier.save()
                return CustomResponse.success(message='Supplier deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Supplier")
        


        