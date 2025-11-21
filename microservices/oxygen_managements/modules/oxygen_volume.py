from datetime import datetime

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from microservices.oxygen_managements.models import OxygenVolume
from microservices.oxygen_managements.serializers import OxygenVolumeSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import STATUS_CODES, CustomResponse

class OxygenVolumeView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OxygenVolumeSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                oxygen_volume = OxygenVolume.objects.filter(uid=uid, is_deleted=False).first()
                if not oxygen_volume:
                    raise NotFound("Oxygen Volume not found")
                return CustomResponse.success(data=OxygenVolumeSerializer(oxygen_volume).data)

            search_query = request.GET.get('search', '').strip()
            location_uid = request.GET.get('location', None)

            # Start with volumes that are not deleted
            oxygen_volumes = OxygenVolume.objects.filter(is_deleted=False)

            # If a location is specified, filter volumes by that location
            if location_uid:
                oxygen_volumes = oxygen_volumes.filter(
                    location_volume__location__uid=location_uid,
                    location_volume__is_deleted=False
                ).distinct()

            # Apply search filtering
            if search_query:
                oxygen_volumes = oxygen_volumes.filter(
                    Q(name__icontains=search_query) | Q(code__icontains=search_query)
                )

            if oxygen_volumes.exists():
                return CustomPagination.paginate(view_class=self, results=oxygen_volumes, request=request)

            return CustomResponse.errors(message="Oxygen Volumes not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to retrieve Oxygen Volumes: {str(e)}')

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = OxygenVolume.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except OxygenVolume.DoesNotExist:
                        return CustomResponse.errors(message="Oxygen Volume  not found")

                # Handle Create case (when no uid)
                else:
                    serializer = self.serializer_class(data=request.data)

                # Validate and save
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
            # Catch unexpected errors that occur in the entire process
            return CustomResponse.server_error(message=f'Failed to Change Oxygen Volume : {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Oxygen Volume  by UID """
                oxygen_volume = OxygenVolume.objects.filter(uid=uid, is_deleted=False).first()
                if not oxygen_volume:
                    return CustomResponse.errors(message="Oxygen Volume  Not Found or Deleted",)

                oxygen_volume.is_deleted = True
                oxygen_volume.deleted_at = datetime.now()
                oxygen_volume.deleted_by = request.user.id
                oxygen_volume.save()
                return CustomResponse.success(message='Oxygen Volume  deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Oxygen Volume ")
