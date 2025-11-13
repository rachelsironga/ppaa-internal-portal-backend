# building.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import Building
from microservices.ict_assets.serializers import BuildingSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class BuildingView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = BuildingSerializer
    required_permissions = {
        "get": [
            "view_building"
        ],
        "post": [
            "add_building",
            "change_building",
        ],
        "delete": [
            "delete_building",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                building = Building.objects.filter(uid=uid, is_deleted=False).first()
                if not building:
                    raise NotFound("Building not found")
                return CustomResponse.success(data=BuildingSerializer(building).data)

            search_query = request.GET.get('search', '').strip()
            buildings = Building.objects.filter(is_deleted=False)

            if search_query:
                buildings = buildings.filter(
                    Q(name__icontains=search_query) | 
                    Q(code__icontains=search_query) |
                    Q(address__icontains=search_query)
                )

            if buildings.exists():
                return CustomPagination.paginate(view_class=self, results=buildings, request=request)

            return CustomResponse.errors(message="Buildings not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Buildings: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = Building.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except Building.DoesNotExist:
                        return CustomResponse.errors(message="Building not found")
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
            return CustomResponse.server_error(message=f'Failed to Change Building: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                building = Building.objects.filter(uid=uid, is_deleted=False).first()
                if not building:
                    return CustomResponse.errors(message="Building Not Found or Already Deleted")

                building.is_deleted = True
                building.deleted_at = datetime.now()
                building.deleted_by = request.user
                building.save()
                return CustomResponse.success(message='Building deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Building")
        

