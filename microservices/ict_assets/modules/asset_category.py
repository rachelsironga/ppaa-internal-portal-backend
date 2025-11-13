# asset_category.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from microservices.ict_assets.models import AssetCategory
from microservices.ict_assets.serializers import AssetCategorySerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class AssetCategoryView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = AssetCategorySerializer
    required_permissions = {
        "get": [
            "view_assetcategory"
        ],
        "post": [
            "add_assetcategory",
            "change_assetcategory",
        ],
        "delete": [
            "delete_assetcategory",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                asset_category = AssetCategory.objects.filter(uid=uid, is_deleted=False).first()
                if not asset_category:
                    raise NotFound("Asset Category not found")
                return CustomResponse.success(data=AssetCategorySerializer(asset_category).data)

            search_query = request.GET.get('search', '').strip()
            asset_categories = AssetCategory.objects.filter(is_deleted=False)

            if search_query:
                asset_categories = asset_categories.filter(
                    Q(name__icontains=search_query) | Q(description__icontains=search_query)
                )

            if asset_categories.exists():
                return CustomPagination.paginate(view_class=self, results=asset_categories, request=request)

            return CustomResponse.errors(message="Asset Categories not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Asset Categories: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = AssetCategory.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except AssetCategory.DoesNotExist:
                        return CustomResponse.errors(message="Asset Category not found")
                else:
                    # Handle Create case (when no uid)
                    serializer = self.serializer_class(data=request.data, context={'request': request})

                # Validate and save
                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                # Validation failed
                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Change Asset Category: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete an Asset Category by UID """
                asset_category = AssetCategory.objects.filter(uid=uid, is_deleted=False).first()
                if not asset_category:
                    return CustomResponse.errors(message="Asset Category Not Found or Already Deleted")

                asset_category.is_deleted = True
                asset_category.deleted_at = datetime.now()
                asset_category.deleted_by = request.user
                asset_category.save()
                return CustomResponse.success(message='Asset Category deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Asset Category")
        


