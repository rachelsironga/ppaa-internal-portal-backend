<<<<<<< HEAD
from django.db import DatabaseError, transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView

from api.serializers import UserProfileSerializer
from ppaa_auth.models import User, UserProfile
from ppaa_auth.modules.users import log_user_profile_audit
from ppaa_auth.serializers import ActingUserSerializer, UserSerializer
from ppaa_portal.pagination import CustomPagination
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class UserProfileViewPermission(BasePermission):
    """
    Allow any authenticated user to read their own positions (profile self-service)
    without can_view_sensitive_data. Listing or reading other users' data still
    requires the permissions declared on the view (same rule as HasMethodPermission).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        method = request.method.lower()
        required_perms_map = getattr(view, "required_permissions", {})
        required_perms = required_perms_map.get(method, [])

        if method == "get":
            user_uid = (request.GET.get("user_uid") or "").strip()
            if user_uid and str(request.user.guid) == user_uid:
                return True
            uid_kwarg = getattr(view, "kwargs", None) and view.kwargs.get("uid")
            if uid_kwarg:
                profile = (
                    UserProfile.objects.filter(uid=uid_kwarg, is_deleted=False)
                    .select_related("user")
                    .first()
                )
                if profile and str(profile.user.guid) == str(request.user.guid):
                    return True

        if not required_perms:
            return True

        user_permissions = request.user.get_permission_codes()
        return any(perm in user_permissions for perm in required_perms)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated, UserProfileViewPermission]
    serializer_class = UserProfileSerializer
    required_permissions = {
        "get": ["can_view_sensitive_data"],
        "post": ["can_view_sensitive_data"],
        "put": ["can_view_sensitive_data"],
    }
=======
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
from ppaa_portal.pagination import CustomPagination
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_auth.models import UserProfile, User, Department
from ppaa_auth.serializers import ActingUserSerializer, UserSerializer
from utils.permissions import HasMethodPermission
from ppaa_portal.models import AuditLog


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission, ]
    serializer_class = UserProfileSerializer
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92

    def get(self, request, uid=None):
        try:
            if uid:
<<<<<<< HEAD
                profile = UserProfile.objects.filter(uid=uid, is_deleted=False).first()
                if not profile:
                    raise NotFound("User Profile not found")
                ctx = {"is_auth_view": request.GET.get("is_auth_view", "").lower() == "true"}
                return CustomResponse.success(
                    data=self.serializer_class(profile, context=ctx).data
                )

            qs = UserProfile.objects.filter(is_deleted=False)
            user_uid = (request.GET.get("user_uid") or "").strip()
            if user_uid:
                qs = qs.filter(user__guid=user_uid)
            old_only = str(request.GET.get("old_only", "")).lower() in ("1", "true", "yes")
            if old_only:
                qs = qs.filter(is_active=False)
            else:
                qs = qs.filter(is_active=True)

            search = (request.GET.get("search") or "").strip()
            if search:
                qs = qs.filter(
                    Q(level__name__icontains=search)
                    | Q(level__code__icontains=search)
                    | Q(department__name__icontains=search)
                    | Q(department__code__icontains=search)
                )

            qs = qs.select_related("user", "level", "department", "acting_user")
            qs = qs.order_by("-updated_at")

            if not qs.exists():
                return CustomResponse.errors(message="No profiles found", data=[])

            context = {"is_auth_view": request.GET.get("is_auth_view", "").lower() == "true"}
            return CustomPagination.paginate(
                view_class=self,
                results=qs,
                request=request,
                serializer_context=context,
            )
        except NotFound as e:
            return CustomResponse.errors(message=str(e), data=None)
        except DatabaseError:
            paginated = str(request.GET.get("paginated", "")).lower() == "true"
            if uid:
                return CustomResponse.errors(
                    message="User profile data is unavailable. Run database migrations (ppaa_auth).",
                    data=None,
                    code=STATUS_CODES["DATA_NOT_FOUND"],
                )
            if paginated:
                return CustomResponse.success(
                    data=[],
                    message="No profiles found",
                    pagination={
                        "page": int(request.GET.get("page", 1) or 1),
                        "page_size": int(request.GET.get("page_size", 10) or 10),
                        "total": 0,
                    },
                )
            return CustomResponse.success(data=[], message="No profiles found")
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to Retrieve UserProfiles: {e!s}"
            )

    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=serializer.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            with transaction.atomic():
                serializer.save(
                    created_by=request.user,
                    updated_by=request.user,
                )
            inst = serializer.instance
            p = (
                UserProfile.objects.select_related("user", "level", "department")
                .filter(pk=inst.pk)
                .first()
            )
            if p:
                dept = p.department.name if p.department_id else "—"
                lvl = p.level.name if p.level_id else "—"
                u = p.user
                un = (
                    f"{u.first_name or ''} {u.middle_name or ''} {u.last_name or ''}".strip()
                    or (u.username or "")
                )
                rep = f"Position assigned · {dept} / {lvl} · {un}"
                log_user_profile_audit(
                    request, p, "CREATE", rep, {"summary": rep}
                )
            return CustomResponse.success(data=serializer.data)
        except DatabaseError as e:
            return CustomResponse.errors(
                message="User profile table is missing. Run: python manage.py migrate ppaa_auth",
                data={"detail": str(e)},
                code=STATUS_CODES["PROCESS_FAILED"],
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def put(self, request, uid=None):
        uid = uid or request.data.get("uid")
        if not uid:
            return CustomResponse.errors(message="uid is required", data=None)
        try:
            profile = UserProfile.objects.filter(uid=uid, is_deleted=False).first()
        except DatabaseError:
            return CustomResponse.errors(
                message="User profile table is missing. Run: python manage.py migrate ppaa_auth",
                data=None,
                code=STATUS_CODES["PROCESS_FAILED"],
            )
        if not profile:
            return CustomResponse.errors(message="User Profile not found", data=None)
        if not profile.is_active:
            return CustomResponse.errors(
                message="Your Cant Update. User Profile Is Already deleted",
                data=None,
            )
        profile = (
            UserProfile.objects.select_related("user", "level", "department")
            .filter(pk=profile.pk)
            .first()
        )
        old_dept = profile.department.name if profile.department_id else "—"
        old_lvl = profile.level.name if profile.level_id else "—"
        serializer = self.serializer_class(
            profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if not serializer.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=serializer.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            with transaction.atomic():
                serializer.save(updated_by=request.user)
            inst = serializer.instance
            p = (
                UserProfile.objects.select_related("user", "level", "department")
                .filter(pk=inst.pk)
                .first()
            )
            if p:
                new_dept = p.department.name if p.department_id else "—"
                new_lvl = p.level.name if p.level_id else "—"
                u = p.user
                un = (
                    f"{u.first_name or ''} {u.middle_name or ''} {u.last_name or ''}".strip()
                    or (u.username or "")
                )
                rep = (
                    f"Position updated · {old_dept} / {old_lvl} → {new_dept} / {new_lvl} · {un}"
                )
                log_user_profile_audit(
                    request,
                    p,
                    "UPDATE",
                    rep,
                    {
                        "summary": rep,
                        "previous_department": old_dept,
                        "previous_level": old_lvl,
                        "new_department": new_dept,
                        "new_level": new_lvl,
                    },
                )
            return CustomResponse.success(data=serializer.data)
        except DatabaseError as e:
            return CustomResponse.errors(
                message="User profile table is missing. Run: python manage.py migrate ppaa_auth",
                data={"detail": str(e)},
                code=STATUS_CODES["PROCESS_FAILED"],
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class ActingUser(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "post": ["can_assign_delegate"],
        "delete": ["can_remove_delegate"],
    }

    def post(self, request):
        ser = ActingUserSerializer(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        user_uid = str(ser.validated_data["user_uid"])
        delegated = ser.validated_data.get("delegated_user")
        if delegated is None:
            return CustomResponse.errors(message="delegated_user is required", data=None)
        target = User.objects.filter(guid=user_uid, is_deleted=False).first()
        delegate = User.objects.filter(guid=str(delegated), is_deleted=False).first()
        if not target or not delegate:
            return CustomResponse.errors(message="User not found", data=None)
        try:
            profile = (
                UserProfile.objects.filter(user=target, is_active=True, is_deleted=False)
                .order_by("-updated_at")
                .first()
            )
        except DatabaseError:
            return CustomResponse.errors(
                message="User profile table is missing. Run: python manage.py migrate ppaa_auth",
                data=None,
                code=STATUS_CODES["PROCESS_FAILED"],
            )
        if not profile:
            return CustomResponse.errors(message="No active profile for user", data=None)
        profile.acting_user = delegate
        profile.updated_by = request.user
        profile.save(update_fields=["acting_user", "updated_by", "updated_at"])
        return CustomResponse.success(
            data=UserSerializer(target, context={"is_auth_view": False}).data
        )

    def delete(self, request):
        user_uid = (request.GET.get("user_uid") or "").strip()
        if not user_uid:
            return CustomResponse.errors(message="user_uid is required", data=None)
        target = User.objects.filter(guid=user_uid, is_deleted=False).first()
        if not target:
            return CustomResponse.errors(message="User not found", data=None)
        try:
            profile = (
                UserProfile.objects.filter(user=target, is_active=True, is_deleted=False)
                .order_by("-updated_at")
                .first()
            )
        except DatabaseError:
            return CustomResponse.errors(
                message="User profile table is missing. Run: python manage.py migrate ppaa_auth",
                data=None,
                code=STATUS_CODES["PROCESS_FAILED"],
            )
        if profile:
            profile.acting_user = None
            profile.updated_by = request.user
            profile.save(update_fields=["acting_user", "updated_by", "updated_at"])
        return CustomResponse.success(message="Delegate removed")
=======
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
                    Q(department__name__icontains=search_query) |
                    Q(department__code__icontains=search_query)
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
                        profile = serializer.save(updated_by=request.user)
                        action = "UPDATE"
                    else:
                        profiles = UserProfile.objects.filter(user=serializer.validated_data['user'])

                        for profile in profiles:
                            if profile.is_active:
                                profile.end_date = timezone.datetime.now()
                            profile.is_active = False

                        UserProfile.objects.bulk_update(profiles, ['is_active', 'end_date'])
                        profile = serializer.save(created_by=request.user, updated_by=request.user)
                        action = "CREATE"
                    
                    # Log create/update action
                    try:
                        ip_address = request.META.get("REMOTE_ADDR")
                        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500] if request.META.get("HTTP_USER_AGENT") else ""
                        dept = profile.department if hasattr(profile, 'department') else None
                        AuditLog.objects.create(
                            user=request.user,
                            action=action,
                            model_name="UserProfile",
                            object_id=profile.uid,
                            object_repr=str(profile)[:200],
                            changes={"data": serializer.data},
                            ip_address=ip_address,
                            user_agent=user_agent,
                            department=dept,
                            created_by=request.user,
                            updated_by=request.user,
                        )
                    except Exception:
                        pass
                    
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
                
                # Log delete action
                try:
                    ip_address = request.META.get("REMOTE_ADDR")
                    user_agent = request.META.get("HTTP_USER_AGENT", "")[:500] if request.META.get("HTTP_USER_AGENT") else ""
                    dept = user_profile.department if hasattr(user_profile, 'department') else None
                    AuditLog.objects.create(
                        user=request.user,
                        action="DELETE",
                        model_name="UserProfile",
                        object_id=user_profile.uid,
                        object_repr=str(user_profile)[:200],
                        ip_address=ip_address,
                        user_agent=user_agent,
                        department=dept,
                        created_by=request.user,
                        updated_by=request.user,
                    )
                except Exception:
                    pass
                
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
                    
                    # Create audit log for delegation assignment
                    try:
                        from ppaa_portal.views import create_audit_log
                        create_audit_log(
                            request=request,
                            action="UPDATE",
                            model_name="UserProfile",
                            obj=active_profile,
                            changes={
                                "action": "Acting user assigned",
                                "delegated_to": f"{delegate_user.first_name} {delegate_user.last_name} ({delegate_user.username})",
                                "delegated_to_uid": str(delegate_user.guid)
                            }
                        )
                    except Exception:
                        pass
                    
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
                acting_user_before = active_profile.acting_user
                active_profile.acting_user = None
                active_profile.updated_by = request.user
                active_profile.updated_at = timezone.now()
                active_profile.save()
                
                # Create audit log for delegation removal
                try:
                    from ppaa_portal.views import create_audit_log
                    create_audit_log(
                        request=request,
                        action="UPDATE",
                        model_name="UserProfile",
                        obj=active_profile,
                        changes={
                            "action": "Acting user removed",
                            "removed_delegate": f"{acting_user_before.first_name} {acting_user_before.last_name} ({acting_user_before.username})" if acting_user_before else "Unknown"
                        }
                    )
                except Exception:
                    pass
                
                # if success returns User for Front end Update
                return CustomResponse.success(data=UserSerializer(user).data)

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Remove Deligation: {str(e)}', )
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
