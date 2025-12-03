from datetime import datetime

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from microservices.oxygen_managements.models import LocationalOxygenUsage
from microservices.oxygen_managements.serializers import LocationalOxygenUsageSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES


class LocationalOxygenUsageView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LocationalOxygenUsageSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                oxygen_usage = LocationalOxygenUsage.objects.filter(uid=uid, is_deleted=False).first()
                if not oxygen_usage:
                    raise NotFound("Oxygen Device Usage record not found.")
                return CustomResponse.success(data=self.serializer_class(oxygen_usage).data)

            search_query = request.GET.get('search', '').strip()
            oxygen_usages = LocationalOxygenUsage.objects.filter(is_deleted=False)

            if search_query:
                oxygen_usages = oxygen_usages.filter(
                    Q(remarks__icontains=search_query) | Q(location__name__icontains=search_query)
                )

            if oxygen_usages.exists():
                return CustomPagination.paginate(view_class=self, results=oxygen_usages, request=request)

            return CustomResponse.errors(message="No Oxygen Device Usage records found.", data=[])

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to retrieve Oxygen Device Usage records: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = LocationalOxygenUsage.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except LocationalOxygenUsage.DoesNotExist:
                        return CustomResponse.errors(message="Oxygen Device Usage record not found.")
                else:
                    serializer = self.serializer_class(data=request.data)

                if serializer.is_valid():
                    serializer.save(created_by=request.user, updated_by=request.user)
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed. Please check the input and try again.",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to save Oxygen Device Usage: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                oxygen_usage = LocationalOxygenUsage.objects.filter(uid=uid, is_deleted=False).first()
                if not oxygen_usage:
                    return CustomResponse.errors(message="Oxygen Device Usage record not found or already deleted.")

                oxygen_usage.is_deleted = True
                oxygen_usage.deleted_at = datetime.now()
                oxygen_usage.deleted_by = request.user.id
                oxygen_usage.save()
                return CustomResponse.success(message="Oxygen Device Usage record deleted successfully.")

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to delete Oxygen Device Usage record: {str(e)}')
