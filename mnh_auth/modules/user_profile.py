from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from yaml import serialize

from api.serializers import UserProfileSerializer, UserProfileSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.models import UserProfile, User
from mnh_auth.serializers import ActingUserSerializer, UserSerializer
from utils.permissions import HasMethodPermission


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission, ]
    serializer_class = UserProfileSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                user_profile = UserProfile.objects.filter(uid=uid, is_deleted=False).first()
                if not user_profile:
                    raise NotFound("User Profile not found")
                return CustomResponse.success(data=self.serializer_class(user_profile).data)

            search_query = request.GET.get('search', '').strip()
            user_uid = request.GET.get('user_uid', '').strip()
            old_only = request.GET.get('old_only', False)

            if old_only:
                user_profiles = UserProfile.objects.filter(is_active=False)
            else:
                user_profiles = UserProfile.objects.filter(is_deleted=False)

            if user_uid:
                user_profiles = user_profiles.filter(user__guid=user_uid).order_by('-updated_at', '-is_active')

            if search_query is not None:
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
                instance = None
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
                        profiles = UserProfile.objects.filter(user=serializer.validated_data['user'])

                        for profile in profiles:
                            if profile.is_active:
                                profile.end_date = timezone.datetime.now()
                            profile.is_active = False

                        UserProfile.objects.bulk_update(profiles, ['is_active', 'end_date'])
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
                user_profile = UserProfile.objects.filter(uid=uid, is_deleted=False).first()
                if not UserProfile:
                    return CustomResponse.errors(message="UserProfile Not Found or Already Deleted", )

                user_profile.is_deleted = True
                user_profile.deleted_at = timezone.datetime.now()
                user_profile.deleted_by = request.user
                user_profile.save()
                return CustomResponse.success(message='User Profile deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting User Profile")


class ActingUser(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission, ]
    serializer_class = ActingUserSerializer
    required_permissions = {
        "post": [
            "can_assign_delegate",
        ],
        "delete": [
            "can_assign_delegate",
        ]
    }

    def post(self, request):
        try:
            with (transaction.atomic()):
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    delegate_user = User.objects.filter(guid=serializer.validated_data['delegated_user']).first()
                    if not delegate_user:
                        return CustomResponse.errors(message="Delegate User not found")

                    user = request.user
                    user_position = user.get_position() if hasattr(user, "get_position") else None
                    if not user_position:
                        return CustomResponse.errors(
                            message="You are not assigned to any position. Please assign a position before delegating.",
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )
                    # Locate the active UserProfile for this level and department
                    active_profile = UserProfile.objects.filter(
                        is_active=True,
                        level__uid=user_position['level_uid'],
                        department__uid=user_position['department_uid'],
                        is_deleted=False
                    ).first()

                    if not active_profile:
                        return CustomResponse.errors(
                            message="No active profile found in your position. Cannot assign delegation.",
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )
                    active_profile.acting_user = delegate_user
                    active_profile.updated_by = request.user
                    active_profile.updated_at = timezone.now()
                    active_profile.save()
                    # if success returns User for Front end Update
                    return CustomResponse.success(data=UserSerializer(user).data)

            return CustomResponse.errors(
                message="Your Have sent Invalid User",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to create Deligation: {str(e)}', )

    def delete(self, request):
        try:
            with (transaction.atomic()):
                user = request.user
                user_position = user.get_position() if hasattr(user, "get_position") else None
                if not user_position:
                    return CustomResponse.errors(
                        message="You are not assigned to any position. Please assign a position before delegating.",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                # Locate the active UserProfile for this level and department
                active_profile = UserProfile.objects.filter(
                    is_active=True,
                    level__uid=user_position['level_uid'],
                    department__uid=user_position['department_uid'],
                    is_deleted=False
                ).first()

                if not active_profile:
                    return CustomResponse.errors(
                        message="No active profile found in your position. Cannot assign delegation.",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                active_profile.acting_user = None
                active_profile.updated_by = request.user
                active_profile.updated_at = timezone.now()
                active_profile.save()
                # if success returns User for Front end Update
                return CustomResponse.success(data=UserSerializer(user).data)

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Remove Deligation: {str(e)}', )
