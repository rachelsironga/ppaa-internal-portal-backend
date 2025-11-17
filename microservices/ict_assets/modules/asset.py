# asset.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import Asset
from microservices.ict_assets.serializers import AssetDetailSerializer, AssetListSerializer, AssetSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class AssetView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = AssetSerializer
    required_permissions = {
        "get": [
            "view_asset"
        ],
        "post": [
            "add_asset",
        ],
        "put": [
            "change_asset",
        ],
        "patch": [
            "change_asset",
        ],
        "delete": [
            "delete_asset",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                asset = Asset.objects.filter(uid=uid, is_deleted=False).first()
                if not asset:
                    raise NotFound("Asset not found")
                return CustomResponse.success(data=AssetSerializer(asset).data)

            search_query = request.GET.get('search', '').strip()
            asset_type_uid = request.GET.get('asset_type', '').strip()
            condition = request.GET.get('condition', '').strip()
            status = request.GET.get('status', '').strip()
            location_uid = request.GET.get('location', '').strip()
            
            assets = Asset.objects.filter(is_deleted=False)

            if search_query:
                assets = assets.filter(
                    Q(asset_tag__icontains=search_query) | 
                    Q(serial_number__icontains=search_query) | 
                    Q(model__icontains=search_query) |
                    Q(notes__icontains=search_query)
                )

            if asset_type_uid:
                assets = assets.filter(asset_type__uid=asset_type_uid)

            if condition:
                assets = assets.filter(condition=condition)

            if status:
                assets = assets.filter(status=status)

            if location_uid:
                assets = assets.filter(location__uid=location_uid)

            if assets.exists():
                return CustomPagination.paginate(view_class=self, results=assets, request=request)

            return CustomResponse.errors(message="Asset not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Asset: {str(e)}')
        
    def post(self, request):
        try:
            with transaction.atomic():
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
            return CustomResponse.server_error(message=f'Failed to Create Asset: {str(e)}')
    
    def put(self, request, uid):
        try:
            with transaction.atomic():
                try:
                    instance = Asset.objects.get(uid=uid, is_deleted=False)
                except Asset.DoesNotExist:
                    return CustomResponse.errors(message="Asset not found")
                
                serializer = self.serializer_class(instance, data=request.data, context={'request': request})

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Update Asset: {str(e)}')
    
    def patch(self, request, uid):
        try:
            with transaction.atomic():
                try:
                    instance = Asset.objects.get(uid=uid, is_deleted=False)
                except Asset.DoesNotExist:
                    return CustomResponse.errors(message="Asset not found")
                
                serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Update Asset: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                asset = Asset.objects.filter(uid=uid, is_deleted=False).first()
                if not asset:
                    return CustomResponse.errors(message="Asset Not Found or Already Deleted")

                asset.is_deleted = True
                asset.deleted_at = datetime.now()
                asset.deleted_by = request.user
                asset.save()
                return CustomResponse.success(message='Asset deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Asset")
        

