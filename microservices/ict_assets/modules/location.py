# location.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import Location
from microservices.ict_assets.serializers import LocationSerializer, LocationDetailSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class LocationView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = LocationSerializer
    required_permissions = {
        "get": [
            "view_location"
        ],
        "post": [
            "add_location",
            "change_location",
        ],
        "delete": [
            "delete_location",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                location = Location.objects.filter(uid=uid, is_deleted=False).first()
                if not location:
                    raise NotFound("Location not found")
                return CustomResponse.success(data=LocationDetailSerializer(location).data)

            search_query = request.GET.get('search', '').strip()
            building_uid = request.GET.get('building', '').strip()
            floor_uid = request.GET.get('floor', '').strip()
            parent_uid = request.GET.get('parent', '').strip()
            
            locations = Location.objects.filter(is_deleted=False)

            if building_uid:
                locations = locations.filter(building__uid=building_uid)

            if floor_uid:
                locations = locations.filter(floor__uid=floor_uid)

            if parent_uid:
                locations = locations.filter(parent__uid=parent_uid)

            if search_query:
                locations = locations.filter(
                    Q(name__icontains=search_query) | 
                    Q(address__icontains=search_query) |
                    Q(room__icontains=search_query) |
                    Q(building__name__icontains=search_query)
                )

            if locations.exists():
                return CustomPagination.paginate(view_class=self, results=locations, request=request)

            return CustomResponse.errors(message="Locations not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Locations: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = Location.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except Location.DoesNotExist:
                        return CustomResponse.errors(message="Location not found")
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
            return CustomResponse.server_error(message=f'Failed to Change Location: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                location = Location.objects.filter(uid=uid, is_deleted=False).first()
                if not location:
                    return CustomResponse.errors(message="Location Not Found or Already Deleted")

                location.is_deleted = True
                location.deleted_at = datetime.now()
                location.deleted_by = request.user
                location.save()
                return CustomResponse.success(message='Location deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Location")
        

        