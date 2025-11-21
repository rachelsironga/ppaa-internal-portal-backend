from datetime import datetime

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from microservices.oxygen_managements.models import LocationOxygenVolumes
from microservices.oxygen_managements.serializers import LocationOxygenVolumeSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES


class LocationOxygenVolumesView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LocationOxygenVolumeSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                location_oxygen_volume = LocationOxygenVolumes.objects.filter(uid=uid, is_deleted=False).first()
                if not location_oxygen_volume:
                    raise NotFound("Location Oxygen Volume not found")
                return CustomResponse.success(data=LocationOxygenVolumeSerializer(location_oxygen_volume).data)

            search_query = request.GET.get('search', '').strip()
            location_oxygen_volumes = LocationOxygenVolumes.objects.filter(is_deleted=False)

            if search_query:
                location_oxygen_volumes = location_oxygen_volumes.filter(
                    Q(location__name__icontains=search_query) | Q(location__code__icontains=search_query)
                )

            if location_oxygen_volumes.exists():
                return CustomPagination.paginate(view_class=self, results=location_oxygen_volumes, request=request)

            return CustomResponse.errors(message="Location Oxygen Volume not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Location Oxygen Volumes: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = LocationOxygenVolumes.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except LocationOxygenVolumes.DoesNotExist:
                        return CustomResponse.errors(message="Location Volume not found")

                else:
                    serializer = self.serializer_class(data=request.data)


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
            return CustomResponse.server_error(message=f'Failed to Change Oxygen Volume Location: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Location Oxygen Volume by UID """
                location_oxygen_volume = LocationOxygenVolumes.objects.filter(uid=uid, is_deleted=False).first()
                if not location_oxygen_volume:
                    return CustomResponse.errors(message="Location Oxygen Volume Not Found or Deleted",)

                location_oxygen_volume.is_deleted = True
                location_oxygen_volume.deleted_at = datetime.now()
                location_oxygen_volume.deleted_by = request.user.id
                location_oxygen_volume.save()
                return CustomResponse.success(message='Location Oxygen Volume deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Location Oxygen Volume")
