from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_analytical.models import PaymentMode
from microservices.mnh_analytical.serializers import PaymentModeSerializer, PaymentModeListSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class PaymentModeView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = PaymentModeSerializer
    required_permissions = {
        "get": ["view_paymentmode"],
        "post": ["add_paymentmode", "change_paymentmode"],
        "delete": ["delete_paymentmode"]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                payment_mode = PaymentMode.objects.filter(uid=uid, is_deleted=False).first()
                if not payment_mode:
                    raise NotFound("Payment mode not found")
                return CustomResponse.success(data=PaymentModeSerializer(payment_mode).data)

            search_query = request.GET.get('search', '').strip()
            payment_modes = PaymentMode.objects.filter(is_deleted=False)

            if search_query:
                payment_modes = payment_modes.filter(
                    Q(name__icontains=search_query) |
                    Q(code__icontains=search_query) |
                    Q(description__icontains=search_query)
                )

            if payment_modes.exists():
                return CustomPagination.paginate(view_class=self, results=payment_modes, request=request)

            return CustomResponse.errors(message="Payment modes not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Payment Modes: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = PaymentMode.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(
                            instance, data=request.data, partial=True, context={'request': request}
                        )
                    except PaymentMode.DoesNotExist:
                        return CustomResponse.errors(message="Payment mode not found")
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
            return CustomResponse.server_error(message=f'Failed to Save Payment Mode: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                payment_mode = PaymentMode.objects.filter(uid=uid, is_deleted=False).first()
                if not payment_mode:
                    return CustomResponse.errors(message="Payment Mode Not Found or Already Deleted")

                payment_mode.is_deleted = True
                payment_mode.deleted_at = datetime.now()
                payment_mode.deleted_by = request.user
                payment_mode.save()
                return CustomResponse.success(message='Payment mode deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Payment Mode")
