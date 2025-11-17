# disposal_record.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import DisposalRecord
from microservices.ict_assets.serializers import DisposalRecordSerializer, DisposalRecordDetailSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class DisposalRecordView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = DisposalRecordSerializer
    required_permissions = {
        "get": [
            "view_disposalrecord"
        ],
        "post": [
            "add_disposalrecord",
            "change_disposalrecord",
        ],
        "delete": [
            "delete_disposalrecord",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                disposal_record = DisposalRecord.objects.filter(uid=uid, is_deleted=False).first()
                if not disposal_record:
                    raise NotFound("Disposal Record not found")
                return CustomResponse.success(data=DisposalRecordDetailSerializer(disposal_record).data)

            search_query = request.GET.get('search', '').strip()
            asset_uid = request.GET.get('asset', '').strip()
            disposal_method = request.GET.get('disposal_method', '').strip()
            
            disposal_records = DisposalRecord.objects.filter(is_deleted=False)

            if asset_uid:
                disposal_records = disposal_records.filter(asset__uid=asset_uid)

            if disposal_method:
                disposal_records = disposal_records.filter(disposal_method=disposal_method)

            if search_query:
                disposal_records = disposal_records.filter(
                    Q(asset__asset_tag__icontains=search_query) | 
                    Q(disposal_reason__icontains=search_query) |
                    Q(approved_by__first_name__icontains=search_query) |
                    Q(approved_by__last_name__icontains=search_query) |
                    Q(notes__icontains=search_query)
                )

            if disposal_records.exists():
                return CustomPagination.paginate(view_class=self, results=disposal_records, request=request)

            return CustomResponse.errors(message="Disposal Records not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Disposal Records: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = DisposalRecord.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except DisposalRecord.DoesNotExist:
                        return CustomResponse.errors(message="Disposal Record not found")
                else:
                    serializer = self.serializer_class(data=request.data, context={'request': request})

                if serializer.is_valid():
                    serializer.save(approved_by=request.user)
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Change Disposal Record: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                disposal_record = DisposalRecord.objects.filter(uid=uid, is_deleted=False).first()
                if not disposal_record:
                    return CustomResponse.errors(message="Disposal Record Not Found or Already Deleted")

                disposal_record.is_deleted = True
                disposal_record.deleted_at = datetime.now()
                disposal_record.deleted_by = request.user
                disposal_record.save()
                return CustomResponse.success(message='Disposal Record deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Disposal Record")