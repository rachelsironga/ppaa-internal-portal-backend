from datetime import datetime

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from api.serializers import DateRangeSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_model.models import DateRange
from utils.permissions import HasMethodPermission


class DateRangeView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = DateRangeSerializer
    required_permissions = {
        "get": [
            "view_daterange",  "can_view_date_range_lookup","can_edit_date_range","can_delete_date_range"
        ],
        "post": [
            "add_daterange",
            "can_view_date_range_lookup","can_edit_date_range","can_delete_date_range"
        ],
        "delete": [
            "change_daterange",
        ]
    }


    def get(self, request, uid=None):
        try:
            if uid:
                date_range = DateRange.objects.filter(uid=uid, is_deleted=False).first()
                if not date_range:
                    raise NotFound("Date Range not found")
                return CustomResponse.success(data=DateRangeSerializer(date_range).data)

            search_query = request.GET.get('search', '').strip()
            is_active = request.GET.get('is_active', None)

            date_ranges = DateRange.objects.filter(is_deleted=False)

            if is_active is not None:
                date_ranges = date_ranges.filter(is_active=str(is_active).capitalize())

            if search_query:
                date_ranges = date_ranges.filter(
                    Q(name__icontains=search_query) |
                    Q(type__icontains=search_query) |
                    Q(value__icontains=search_query)
                )

            if date_ranges.exists():
                return CustomPagination.paginate(view_class=self, results=date_ranges, request=request)

            return CustomResponse.errors(message="Date Range not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Date Ranges: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = DateRange.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except DateRange.DoesNotExist:
                        return CustomResponse.errors(message="Date Range not found")

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
            return CustomResponse.server_error(message=f'Failed to Change Date Range: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Date Range by UID """
                date_range = DateRange.objects.filter(uid=uid, is_deleted=False).first()
                if not date_range:
                    return CustomResponse.errors(message="Date Range Not Found or Deleted",)

                date_range.is_deleted = True
                date_range.deleted_at = datetime.now()
                date_range.deleted_by = request.user
                date_range.save()
                return CustomResponse.success(message='Date Range deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Date Range")
