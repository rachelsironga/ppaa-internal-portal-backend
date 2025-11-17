# asset_type.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import AssetType
from microservices.ict_assets.serializers import AssetTypeSerializer, AssetTypeDetailSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class AssetTypeView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = AssetTypeSerializer
    required_permissions = {
        "get": [
            "view_assettype"
        ],
        "post": [
            "add_assettype",
            "change_assettype",
        ],
        "delete": [
            "delete_assettype",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                asset_type = AssetType.objects.filter(uid=uid, is_deleted=False).first()
                if not asset_type:
                    raise NotFound("Asset Type not found")
                return CustomResponse.success(data=AssetTypeDetailSerializer(asset_type).data)

            search_query = request.GET.get('search', '').strip()
            category_uid = request.GET.get('category', '').strip()
            
            asset_types = AssetType.objects.filter(is_deleted=False)

            if category_uid:
                asset_types = asset_types.filter(category__uid=category_uid)

            if search_query:
                asset_types = asset_types.filter(
                    Q(name__icontains=search_query) | 
                    Q(category__name__icontains=search_query)
                )

            if asset_types.exists():
                return CustomPagination.paginate(view_class=self, results=asset_types, request=request)

            return CustomResponse.errors(message="Asset Types not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Asset Types: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = AssetType.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except AssetType.DoesNotExist:
                        return CustomResponse.errors(message="Asset Type not found")
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
            return CustomResponse.server_error(message=f'Failed to Change Asset Type: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                asset_type = AssetType.objects.filter(uid=uid, is_deleted=False).first()
                if not asset_type:
                    return CustomResponse.errors(message="Asset Type Not Found or Already Deleted")

                asset_type.is_deleted = True
                asset_type.deleted_at = datetime.now()
                asset_type.deleted_by = request.user
                asset_type.save()
                return CustomResponse.success(message='Asset Type deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Asset Type")