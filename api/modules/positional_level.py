from datetime import datetime

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from api.serializers import PositionalLevelSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.models import PositionalLevel
from utils.permissions import HasMethodPermission



class PositionalLevelView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = PositionalLevelSerializer
    required_permissions = {
        "get": [
            "view_positionallevel"
        ],
        "post": [
            "add_positionallevel",
            "change_positionallevel",
        ],
        "delete": [
            "delete_positionallevel",
        ]
    }

    def get(self, request, uid=None):
        try:
            """ Retrieve a single Positional Level by UID or list Positional Levels with optional search """
            if uid:
                positional_level = PositionalLevel.objects.filter(uid=uid, is_deleted=False).first()
                if not positional_level:
                    raise NotFound("Positional Level not found")
                return CustomResponse.success(data=PositionalLevelSerializer(positional_level).data)

            search_query = request.GET.get('search', '').strip()
            positional_levels = PositionalLevel.objects.filter(is_deleted=False)

            if search_query:
                positional_levels = positional_levels.filter(
                    Q(name__icontains=search_query) | Q(code__icontains=search_query)
                )

            if positional_levels.exists():
                return CustomPagination.paginate(view_class=self, results=positional_levels, request=request)

            return CustomResponse.errors(message="Positional Level not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Positional Levels: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)

                # Handle Update case
                if uid:
                    try:
                        instance = PositionalLevel.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except PositionalLevel.DoesNotExist:
                        return CustomResponse.errors(message="Positional Level not found")

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
            return CustomResponse.server_error(message=f'Failed to Change Positional Level: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Positional Level by UID """
                positional_level = PositionalLevel.objects.filter(uid=uid, is_deleted=False).first()
                if not positional_level:
                    return CustomResponse.errors(message="Positional Level Not Found or Deleted",)

                positional_level.is_deleted = True
                positional_level.deleted_at = datetime.now()
                positional_level.deleted_by = request.user.id
                positional_level.save()
                return CustomResponse.success(message='Positional Level deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Positional Level")
