from datetime import datetime

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from microservices.oxygen_managements.models import OxygenSupplier
from microservices.oxygen_managements.serializers import SupplierSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES


class SupplierView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SupplierSerializer


    def get(self, request, uid=None):
        try:
            if uid:   
                supplier = OxygenSupplier.objects.filter(uid=uid, is_deleted=False).first()
                if not supplier:
                    return CustomResponse.errors(message="supplier not found")
                return CustomResponse.success(data=SupplierSerializer(supplier).data)

            search_query = request.GET.get('search', '').strip()
            suppliers = OxygenSupplier.objects.filter(is_deleted=False)

            if search_query:
                suppliers = suppliers.filter(
                    Q(name__icontains=search_query) |
                    Q(physical_address__icontains=search_query) |
                    Q(contact__icontains=search_query) |
                    Q(email_address__icontains=search_query)
                )

            if suppliers.exists():
                return CustomPagination.paginate(view_class=self, results=suppliers, request=request)

            return CustomResponse.errors(message="supplier not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve suppliers: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = OxygenSupplier.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except OxygenSupplier.DoesNotExist:
                        return CustomResponse.errors(message="supplier not found")

                # Handle Create case (when no uid)
                else:
                    serializer = self.serializer_class(data=request.data)

                # Validate and save
                if serializer.is_valid():
                    serializer.save(created_by=request.user, updated_by=request.user)
                    return CustomResponse.success(data=serializer.data)

                # Validation failed
                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            # Catch unexpected errors that occur in the entire process
            return CustomResponse.server_error(message=f'Failed to Change supplier: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a supplier by UID """
                supplier = OxygenSupplier.objects.filter(uid=uid, is_deleted=False).first()
                if not supplier:
                    return CustomResponse.errors(message="supplier Not Found or Deleted",)

                supplier.is_deleted = True
                supplier.deleted_at = datetime.now()
                supplier.deleted_by = request.user.id
                supplier.save()
                return CustomResponse.success(message='supplier deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting supplier")
