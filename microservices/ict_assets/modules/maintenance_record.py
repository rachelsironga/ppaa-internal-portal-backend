# maintenance_record.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import MaintenanceRecord
from microservices.ict_assets.serializers import MaintenanceRecordSerializer, MaintenanceRecordDetailSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class MaintenanceRecordView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = MaintenanceRecordSerializer
    required_permissions = {
        "get": [
            "view_maintenancerecord"
        ],
        "post": [
            "add_maintenancerecord",
            "change_maintenancerecord",
        ],
        "delete": [
            "delete_maintenancerecord",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                maintenance_record = MaintenanceRecord.objects.filter(uid=uid, is_deleted=False).first()
                if not maintenance_record:
                    raise NotFound("Maintenance Record not found")
                return CustomResponse.success(data=MaintenanceRecordDetailSerializer(maintenance_record).data)

            search_query = request.GET.get('search', '').strip()
            asset_uid = request.GET.get('asset', '').strip()
            maintenance_type = request.GET.get('maintenance_type', '').strip()
            status = request.GET.get('status', '').strip()
            
            maintenance_records = MaintenanceRecord.objects.filter(is_deleted=False)

            if asset_uid:
                maintenance_records = maintenance_records.filter(asset__uid=asset_uid)

            if maintenance_type:
                maintenance_records = maintenance_records.filter(maintenance_type=maintenance_type)

            if status:
                maintenance_records = maintenance_records.filter(status=status)

            if search_query:
                maintenance_records = maintenance_records.filter(
                    Q(asset__asset_tag__icontains=search_query) | 
                    Q(description__icontains=search_query) |
                    Q(technician__first_name__icontains=search_query) |
                    Q(technician__last_name__icontains=search_query) |
                    Q(technician__username__icontains=search_query) |
                    Q(notes__icontains=search_query)
                )

            if maintenance_records.exists():
                return CustomPagination.paginate(view_class=self, results=maintenance_records, request=request)

            return CustomResponse.errors(message="Maintenance Records not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Maintenance Records: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = MaintenanceRecord.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except MaintenanceRecord.DoesNotExist:
                        return CustomResponse.errors(message="Maintenance Record not found")
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
            return CustomResponse.server_error(message=f'Failed to Change Maintenance Record: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                maintenance_record = MaintenanceRecord.objects.filter(uid=uid, is_deleted=False).first()
                if not maintenance_record:
                    return CustomResponse.errors(message="Maintenance Record Not Found or Already Deleted")

                maintenance_record.is_deleted = True
                maintenance_record.deleted_at = datetime.now()
                maintenance_record.deleted_by = request.user
                maintenance_record.save()
                return CustomResponse.success(message='Maintenance Record deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Maintenance Record")
        


