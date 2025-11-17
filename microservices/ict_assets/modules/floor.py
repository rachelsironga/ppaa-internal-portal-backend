# floor.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import Floor
from microservices.ict_assets.serializers import FloorSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class FloorView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = FloorSerializer
    required_permissions = {
        "get": [
            "view_floor"
        ],
        "post": [
            "add_floor",
            "change_floor",
        ],
        "delete": [
            "delete_floor",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                floor = Floor.objects.filter(uid=uid, is_deleted=False).first()
                if not floor:
                    raise NotFound("Floor not found")
                return CustomResponse.success(data=FloorSerializer(floor).data)

            search_query = request.GET.get('search', '').strip()
            building_uid = request.GET.get('building', '').strip()
            
            floors = Floor.objects.filter(is_deleted=False)

            if building_uid:
                floors = floors.filter(building__uid=building_uid)

            if search_query:
                floors = floors.filter(
                    Q(name__icontains=search_query) | 
                    Q(building__name__icontains=search_query) |
                    Q(number__icontains=search_query)
                )

            if floors.exists():
                return CustomPagination.paginate(view_class=self, results=floors, request=request)

            return CustomResponse.errors(message="Floors not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Floors: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = Floor.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except Floor.DoesNotExist:
                        return CustomResponse.errors(message="Floor not found")
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
            return CustomResponse.server_error(message=f'Failed to Change Floor: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                floor = Floor.objects.filter(uid=uid, is_deleted=False).first()
                if not floor:
                    return CustomResponse.errors(message="Floor Not Found or Already Deleted")

                floor.is_deleted = True
                floor.deleted_at = datetime.now()
                floor.deleted_by = request.user
                floor.save()
                return CustomResponse.success(message='Floor deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Floor")
        

        