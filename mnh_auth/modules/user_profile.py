from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from api.serializers import UserProfileSerializer, UserProfileSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.models import UserProfile


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                user_profile = UserProfile.objects.filter(uid=uid, is_deleted=False).first()
                if not user_profile:
                    raise NotFound("User Profile not found")
                return CustomResponse.success(data=self.serializer_class(user_profile).data)

            search_query = request.GET.get('search', '').strip()
            user_uid = request.GET.get('user', '').strip()

            user_profiles = UserProfile.objects.filter(is_deleted=False)

            if user_uid:
                user_profiles = user_profiles.filter(user__uid=user_uid)

            if search_query:
                user_profiles = user_profiles.filter(
                    Q(level__name__icontains=search_query) |
                    Q(level__code__icontains=search_query) |
                    Q(directory__name__icontains=search_query) |
                    Q(directory__code__icontains=search_query) |
                    Q(department__name__icontains=search_query) |
                    Q(department__code__icontains=search_query) |
                    Q(directory__code__icontains=search_query)
                )

            if user_profiles.exists():
                return CustomPagination.paginate(view_class=self, results=user_profiles, request=request)

            return CustomResponse.errors(message="User Profile not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve UserProfiles: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = UserProfile.objects.get(uid=uid)
                        if instance.is_deleted:
                            return CustomResponse.errors(message="Your Cant Update. User Profile Is Already deleted")
                        if not instance.is_active:
                            return CustomResponse.errors(message="Your Cant Update Disabled Profile")
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except UserProfile.DoesNotExist:
                        return CustomResponse.errors(message="User Profile not found")
                else:
                    serializer = self.serializer_class(data=request.data)


                # Validate and save
                if serializer.is_valid():
                    if instance:
                        serializer.save(updated_by=request.user)
                    else:
                        UserProfile.objects.filter(user=serializer.validated_data['user']).all().update(is_active=True)
                        serializer.save(created_by=request.user, updated_by=request.user)
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Change User Profile: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                user_profile = UserProfile.objects.filter(uid=uid,is_deleted=False).first()
                if not UserProfile:
                    return CustomResponse.errors(message="UserProfile Not Found or Already Deleted", )

                user_profile.is_deleted = True
                user_profile.deleted_at=timezone.datetime.now()
                user_profile.deleted_by = request.user
                user_profile.save()
                return CustomResponse.success(message='User Profile deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting User Profile")
