from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.http import Http404
from oauthlib.openid.connect.core.exceptions import LoginRequired
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.utils import timezone
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from api.serializers import DirectorySerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.models import Directory


class DirectoryView(APIView):
    permission_classes = [AllowAny]
    serializer_class = DirectorySerializer

    def get(self, request, uid=None):
        try:
            """ Retrieve a single Directory by UID or list directories with optional search """
            if uid:
                directory = Directory.objects.filter(uid=uid, is_deleted=False).first()
                if not directory:
                    raise NotFound("Directory not found")
                serializer = DirectorySerializer(directory, context={'include_departments': True})
                return CustomResponse.success(data=serializer.data)

            search_query = request.GET.get('search', '').strip()
            directories = Directory.objects.filter(is_deleted=False)

            if search_query:
                directories = directories.filter(
                    Q(name__icontains=search_query) | Q(code__icontains=search_query)
                )

            if directories.exists():
                return CustomPagination.paginate(view_class=self, results=directories, request=request)

            return CustomResponse.errors(message="Directory not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Directories: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)

                # Handle an Update case
                if uid:
                    try:
                        instance = Directory.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except Directory.DoesNotExist:
                        return CustomResponse.errors(message="Directory not found")

                # Handle Create a case (when no uid)
                else:
                    serializer = self.serializer_class(data=request.data)

                # Validate and save
                if serializer.is_valid():
                    serializer.save(created_by=request.user, updated_by=request.user)
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            # Catch unexpected errors that occur in the entire process
            return CustomResponse.server_error(message=f'Failed to Change Directory: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Directory by UID """
                directory = Directory.objects.filter(uid=uid, is_deleted=False).first()
                if not directory:
                    return CustomResponse.errors(message="Directory Not Found or Deleted", )

                directory.is_deleted = True
                directory.deleted_at = timezone.datetime.now()
                directory.deleted_by = request.user
                directory.save()
                return CustomResponse.success(message='Directory deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Directory")
