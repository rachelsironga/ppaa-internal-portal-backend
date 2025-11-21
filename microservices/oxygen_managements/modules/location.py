from datetime import datetime

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from microservices.oxygen_managements.models import OxygenLocation
from microservices.oxygen_managements.serializers import LocationOxygenSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES


class LocationView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LocationOxygenSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                location = OxygenLocation.objects.filter(uid=uid, is_deleted=False).first()
                if not location:
                    raise NotFound("Location not found")
                serializer = LocationOxygenSerializer(
                    location,
                    context={'location_uid': location.uid}
                )
                return CustomResponse.success(data=serializer.data)

            search_query = request.GET.get('search', '').strip()
            with_volumes = request.GET.get('with_volumes', False)
            locations = OxygenLocation.objects.filter(is_deleted=False)
            context = {"with_volumes": False}

            if search_query:
                locations = locations.filter(
                    Q(name__icontains=search_query) | Q(code__icontains=search_query)
                )

            if str(with_volumes).lower() == 'true':
                context = {"with_volumes": True}


            if locations.exists():
                return CustomPagination.paginate(view_class=self, results=locations, request=request,
                                                 serializer_context=context)

            return CustomResponse.errors(message="Location not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Locations: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = OxygenLocation.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except OxygenLocation.DoesNotExist:
                        return CustomResponse.errors(message="Location not found")

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
            return CustomResponse.server_error(message=f'Failed to Change Location: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Location by UID """
                location = OxygenLocation.objects.filter(uid=uid, is_deleted=False).first()
                if not location:
                    return CustomResponse.errors(message="Location Not Found or Deleted", )

                location.is_deleted = True
                location.deleted_at = datetime.now()
                location.deleted_by = request.user.id
                location.save()
                return CustomResponse.success(message='Location deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Location")
