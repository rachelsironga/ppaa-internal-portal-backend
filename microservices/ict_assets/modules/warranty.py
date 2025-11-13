# warranty.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import Warranty
from microservices.ict_assets.serializers import WarrantySerializer, WarrantyDetailSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class WarrantyView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = WarrantySerializer
    required_permissions = {
        "get": [
            "view_warranty"
        ],
        "post": [
            "add_warranty",
            "change_warranty",
        ],
        "delete": [
            "delete_warranty",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                warranty = Warranty.objects.filter(uid=uid, is_deleted=False).first()
                if not warranty:
                    raise NotFound("Warranty not found")
                return CustomResponse.success(data=WarrantyDetailSerializer(warranty).data)

            search_query = request.GET.get('search', '').strip()
            asset_uid = request.GET.get('asset', '').strip()
            provider = request.GET.get('provider', '').strip()
            
            warranties = Warranty.objects.filter(is_deleted=False)

            if asset_uid:
                warranties = warranties.filter(asset__uid=asset_uid)

            if provider:
                warranties = warranties.filter(provider__icontains=provider)

            if search_query:
                warranties = warranties.filter(
                    Q(asset__asset_tag__icontains=search_query) | 
                    Q(provider__icontains=search_query) |
                    Q(po_number__icontains=search_query) |
                    Q(coverage_details__icontains=search_query) |
                    Q(support_contact__icontains=search_query)
                )

            # Filter expired warranties if requested
            show_expired = request.GET.get('show_expired', 'false').lower() == 'true'
            if not show_expired:
                warranties = warranties.filter(end_date__gte=datetime.now().date())

            if warranties.exists():
                return CustomPagination.paginate(view_class=self, results=warranties, request=request)

            return CustomResponse.errors(message="Warranties not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Warranties: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = Warranty.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except Warranty.DoesNotExist:
                        return CustomResponse.errors(message="Warranty not found")
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
            return CustomResponse.server_error(message=f'Failed to Change Warranty: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                warranty = Warranty.objects.filter(uid=uid, is_deleted=False).first()
                if not warranty:
                    return CustomResponse.errors(message="Warranty Not Found or Already Deleted")

                warranty.is_deleted = True
                warranty.deleted_at = datetime.now()
                warranty.deleted_by = request.user
                warranty.save()
                return CustomResponse.success(message='Warranty deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Warranty")
        


        