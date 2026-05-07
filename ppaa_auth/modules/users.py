import uuid

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView

from ppaa_auth.models import User
from ppaa_auth.serializers import FileUploadSerializer, UserSerializer
from ppaa_portal.models import audit_department_for_user, portal_client_ip, record_audit_log
from ppaa_portal.pagination import CustomPagination
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_portal.services.minio.minio_helpers import (
    PROFILE_MEDIA_PRESIGN_HOURS,
    get_presigned_url,
)
from django.db import models
from utils.minio_storage import MinioStorage
from utils.permissions import HasMethodPermission


def _can_manage_user_lifecycle(user) -> bool:
    """Portal system admins (admin group / explicit permission) and Django superusers."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    groups = user.get_groups() if hasattr(user, "get_groups") else []
    if "admin" in groups:
        return True
    return "can_manage_user_lifecycle" in user.get_permission_codes()


def _can_apply_lifecycle_to_target(request_user, target_user) -> bool:
    """
    Normal accounts: system admin / permission holders may set status or delete.
    Django superuser accounts: only another Django superuser may change lifecycle or delete.
    """
    if not target_user:
        return _can_manage_user_lifecycle(request_user)
    if target_user.is_superuser:
        return bool(getattr(request_user, "is_superuser", False))
    return _can_manage_user_lifecycle(request_user)


def _mutable_request_data(request):
    if hasattr(request.data, "copy"):
        return request.data.copy()
    return dict(request.data)


def _strip_lifecycle_fields(request, data, target_user=None):
    if target_user is None:
        if _can_manage_user_lifecycle(request.user):
            return data
    elif _can_apply_lifecycle_to_target(request.user, target_user):
        return data
    for key in ("status", "is_active"):
        if hasattr(data, "pop"):
            data.pop(key, None)
        elif isinstance(data, dict) and key in data:
            del data[key]
    return data


def _may_mark_retired(target_user: User) -> bool:
    """
    Some accounts cannot be set to RETIRED (e.g. temporal or staff-only); use SUSPENDED.
    """
    if target_user.account_type == User.AccountType.TEMPORALLY:
        return False
    names = list(target_user.groups.values_list("name", flat=True))
    if len(names) == 1 and str(names[0]).lower() == "staff":
        return False
    return True


def _reject_retired_if_not_allowed(user: User, validated_data: dict):
    if validated_data.get("status") != User.AccountStatus.RETIRED:
        return None
    if _may_mark_retired(user):
        return None
    return CustomResponse.errors(
        message="This account cannot be set to retired. Use suspended (blocked) status instead.",
        data=None,
        code=STATUS_CODES["VALIDATION_ERROR"],
    )


def _user_display_name(u: User) -> str:
    parts = [u.first_name or "", u.middle_name or "", u.last_name or ""]
    name = " ".join(p for p in parts if p).strip()
    if name:
        return name
    return (u.username or "") or "User"


def _log_user_account(
    request,
    *,
    target: User,
    action: str,
    object_repr: str,
    changes: dict | None = None,
) -> None:
    """RMS-style domain row for System Logs (no raw endpoints)."""
    ua = (request.META.get("HTTP_USER_AGENT") or "")[:512]
    record_audit_log(
        user=request.user,
        action=(action or "")[:64],
        model_name="User",
        object_id=str(target.guid)[:255],
        object_repr=(object_repr or "")[:255],
        changes=changes if changes is not None else {},
        ip_address=portal_client_ip(request) or None,
        user_agent=ua[:512] if ua else None,
        department=audit_department_for_user(request.user),
        created_by=request.user,
        updated_by=request.user,
    )


def _summarize_user_update(user_before: User, vd: dict) -> tuple[str, dict]:
    """Human-readable title + changes (passwords never stored)."""
    name = _user_display_name(user_before)
    email = (user_before.email or "").strip()
    base = f"{name}" + (f" ({email})" if email else "")
    changes: dict = {
        "summary": "User account updated",
        "target_name": name,
        "target_email": email or None,
    }
    parts = []
    if "status" in vd:
        old_s, new_s = user_before.status, vd["status"]
        if old_s != new_s:
            parts.append(f"Status {old_s} → {new_s}")
            changes["old_status"] = old_s
            changes["new_status"] = new_s
    if "is_active" in vd:
        old_a, new_a = user_before.is_active, vd["is_active"]
        if old_a != new_a:
            parts.append("Login disabled" if not new_a else "Login enabled")
            changes["old_is_active"] = old_a
            changes["new_is_active"] = new_a
    if "password" in vd:
        parts.append("Password changed")
        changes["password_changed"] = True
    profile_keys = (
        "first_name",
        "middle_name",
        "last_name",
        "email",
        "phone_number",
        "alternative_contact",
        "check_number",
        "sex",
        "dob",
    )
    touched = []
    for k in profile_keys:
        if k not in vd:
            continue
        old_v = getattr(user_before, k, None)
        new_v = vd.get(k)
        if old_v != new_v:
            touched.append(k)
    if touched:
        changes["fields_updated"] = touched
        parts.append("Updated: " + ", ".join(t.replace("_", " ") for t in touched))
    if parts:
        changes["summary"] = " · ".join(parts)
        obj_repr = f"{changes['summary']} · {base}"
    else:
        obj_repr = f"User account updated · {base}"
    return obj_repr[:255], changes


def log_user_profile_audit(
    request,
    profile,
    action: str,
    object_repr: str,
    changes: dict | None = None,
) -> None:
    """Position / assignment changes under User Management (same System Logs list)."""
    from ppaa_auth.models import UserProfile

    p = (
        UserProfile.objects.select_related("user", "level", "department")
        .filter(pk=getattr(profile, "pk", None))
        .first()
    )
    if not p:
        return
    ua = (request.META.get("HTTP_USER_AGENT") or "")[:512]
    u = p.user
    ch = dict(changes) if changes else {}
    ch.setdefault("summary", (object_repr or "")[:500])
    ch.setdefault("target_name", _user_display_name(u))
    em = (u.email or "").strip()
    if em:
        ch.setdefault("target_email", em)
    record_audit_log(
        user=request.user,
        action=(action or "")[:64],
        model_name="UserProfile",
        object_id=str(p.uid)[:255],
        object_repr=(object_repr or "")[:255],
        changes=ch,
        ip_address=portal_client_ip(request) or None,
        user_agent=ua[:512] if ua else None,
        department=audit_department_for_user(request.user),
        created_by=request.user,
        updated_by=request.user,
    )


def _first_scalar(val):
    if val is None:
        return None
    if isinstance(val, (list, tuple)):
        return val[0] if val else None
    return val


def _resolve_user_uuid_string(data) -> str:
    """
    Read user id from POST body (JSON or form). Handles QueryDict list values and
    normalizes to canonical UUID string for ORM lookup.
    """
    if not hasattr(data, "get"):
        return ""
    for key in ("user_guid", "guid", "uid", "user_uid"):
        raw = _first_scalar(data.get(key))
        if raw is None or raw == "":
            continue
        s = str(raw).strip()
        if not s:
            continue
        try:
            return str(uuid.UUID(s))
        except (ValueError, AttributeError, TypeError):
            continue
    return ""


class UserSetupViewPermission(BasePermission):
    """
    GET: ``can_view_sensitive_data`` or ``can_assign_delegate`` (pickers / delegation).

    POST/PUT: ``can_view_sensitive_data`` (create/edit). Status and ``is_active`` are
    applied only for users who may manage lifecycle (see ``_strip_lifecycle_fields``).

    DELETE: ``can_manage_user_lifecycle`` (system admins / superusers), not general HR.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        method = request.method.lower()
        required_perms_map = getattr(view, "required_permissions", {})
        required_perms = required_perms_map.get(method, [])
        codes = request.user.get_permission_codes()

        if method == "get":
            return (
                "can_view_sensitive_data" in codes or "can_assign_delegate" in codes
            )

        if not required_perms:
            return True
        return any(perm in codes for perm in required_perms)


class CurrentUserMeView(APIView):
    """Return the logged-in user with fresh MinIO presigned URLs for photo/signature."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return CustomResponse.success(data=UserSerializer(request.user).data)


class UserView(APIView):
    permission_classes = [IsAuthenticated, UserSetupViewPermission]
    serializer_class = UserSerializer
    required_permissions = {
        "get": ["can_view_sensitive_data"],
        "post": ["can_view_sensitive_data"],
        "put": ["can_view_sensitive_data"],
        "delete": ["can_manage_user_lifecycle"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                user = User.objects.filter(guid=uid, is_deleted=False).first()
                if not user:
                    raise NotFound("User not found")
                ctx = {"is_auth_view": request.GET.get("is_auth_view", "").lower() == "true"}
                return CustomResponse.success(data=self.serializer_class(user, context=ctx).data)

            qs = User.objects.filter(is_deleted=False)
            group_id = request.GET.get("group_id")
            if group_id:
                qs = qs.filter(groups__id=int(group_id))
            excluded = request.GET.get("excluded_group")
            if excluded:
                qs = qs.exclude(groups__id=int(excluded))

            search = (request.GET.get("search") or "").strip()
            if search:
                qs = qs.filter(
                    Q(username__icontains=search)
                    | Q(email__icontains=search)
                    | Q(check_number__icontains=search)
                    | Q(first_name__icontains=search)
                    | Q(middle_name__icontains=search)
                    | Q(last_name__icontains=search)
                    | Q(phone_number__icontains=search)
                    | Q(alternative_contact__icontains=search)
                )

            status_q = (request.GET.get("status") or "").strip()
            if status_q:
                qs = qs.filter(status__icontains=status_q)

            up_active = request.GET.get("user_profiles__is_active")
            if up_active is not None:
                qs = qs.filter(
                    user_profiles__is_active=str(up_active).lower() in ("1", "true", "yes")
                )
            up_del = request.GET.get("user_profiles__is_deleted")
            if up_del is not None:
                qs = qs.filter(
                    user_profiles__is_deleted=str(up_del).lower() in ("1", "true", "yes")
                )

            lvl = (request.GET.get("level_name") or "").strip()
            if lvl:
                qs = qs.filter(user_profiles__level__name__icontains=lvl)
            dept = (request.GET.get("department_name") or "").strip()
            if dept:
                qs = qs.filter(user_profiles__department__name__icontains=dept)

            qs = qs.distinct().order_by("-updated_at")

            if not qs.exists():
                return CustomResponse.errors(message="Fail to Retrieve Users ", data=[])

            ctx = {"is_auth_view": request.GET.get("is_auth_view", "").lower() == "true"}
            return CustomPagination.paginate(
                view_class=self,
                results=qs,
                request=request,
                serializer_context=ctx,
            )
        except NotFound as e:
            return CustomResponse.errors(message=str(e), data=None)
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to Retrieve Users: {e!s}"
            )

    def post(self, request):
        """
        Create a user, or update when the body includes ``user_guid`` / ``guid`` /
        ``uid`` (portal always POSTs; edit must not call ``create()``).
        """
        data = _mutable_request_data(request)
        uid = _resolve_user_uuid_string(data)

        if uid:
            user = User.objects.filter(guid=uid, is_deleted=False).first()
            if not user:
                return CustomResponse.errors(message="User not found", data=None)
            data = _strip_lifecycle_fields(request, data, user)
            serializer = self.serializer_class(
                user,
                data=data,
                partial=True,
                context={"request": request},
            )
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            bad = _reject_retired_if_not_allowed(user, serializer.validated_data)
            if bad is not None:
                return bad
            try:
                with transaction.atomic():
                    serializer.save()
                inst = serializer.instance
                obj_repr, ch = _summarize_user_update(user, serializer.validated_data)
                _log_user_account(
                    request,
                    target=inst,
                    action="UPDATE",
                    object_repr=obj_repr,
                    changes=ch,
                )
                return CustomResponse.success(data=serializer.data)
            except Exception as e:
                return CustomResponse.server_error(message=str(e))

        data = _strip_lifecycle_fields(request, data, None)
        serializer = self.serializer_class(data=data, context={"request": request})
        if not serializer.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=serializer.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            with transaction.atomic():
                serializer.save()
            nu = serializer.instance
            nm = _user_display_name(nu)
            em = (nu.email or "").strip()
            rep = f"User account created · {nm}" + (f" ({em})" if em else "")
            _log_user_account(
                request,
                target=nu,
                action="CREATE",
                object_repr=rep[:255],
                changes={
                    "summary": f"Created portal user {nm}",
                    "target_name": nm,
                    "target_email": em or None,
                },
            )
            return CustomResponse.success(data=serializer.data)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def put(self, request, uid=None):
        data = _mutable_request_data(request)
        uid = uid or _resolve_user_uuid_string(data)
        if not uid:
            return CustomResponse.errors(message="User uid required", data=None)
        user = User.objects.filter(guid=uid, is_deleted=False).first()
        if not user:
            return CustomResponse.errors(message="User not found", data=None)
        data = _strip_lifecycle_fields(request, data, user)
        serializer = self.serializer_class(
            user,
            data=data,
            partial=True,
            context={"request": request},
        )
        if not serializer.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=serializer.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        bad = _reject_retired_if_not_allowed(user, serializer.validated_data)
        if bad is not None:
            return bad
        try:
            with transaction.atomic():
                serializer.save()
            inst = serializer.instance
            obj_repr, ch = _summarize_user_update(user, serializer.validated_data)
            _log_user_account(
                request,
                target=inst,
                action="UPDATE",
                object_repr=obj_repr,
                changes=ch,
            )
            return CustomResponse.success(data=serializer.data)
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def delete(self, request, uid=None):
        uid = uid or request.data.get("guid")
        if not uid:
            return CustomResponse.errors(message="User uid required", data=None)
        user = User.objects.filter(guid=uid, is_deleted=False).first()
        if not user:
            return CustomResponse.errors(message="User not found", data=None)
        if str(user.guid) == str(request.user.guid):
            return CustomResponse.errors(
                message="You cannot delete your own account", data=None
            )
        if not _can_apply_lifecycle_to_target(request.user, user):
            return CustomResponse.errors(
                message="You do not have permission to delete this user", data=None
            )
        nm = _user_display_name(user)
        em = (user.email or "").strip()
        user.is_deleted = True
        user.is_active = False
        user.deleted_at = timezone.now()
        user.deleted_by = request.user
        user.save(
            update_fields=[
                "is_deleted",
                "is_active",
                "deleted_at",
                "deleted_by",
                "updated_at",
            ]
        )
        rep = f"User removed (soft delete) · {nm}" + (f" ({em})" if em else "")
        _log_user_account(
            request,
            target=user,
            action="DELETE",
            object_repr=rep[:255],
            changes={
                "summary": f"User removed from portal (soft delete) · {nm}",
                "target_name": nm,
                "target_email": em or None,
            },
        )
        return CustomResponse.success(message="User deleted")


class UserPhotoUpload(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = FileUploadSerializer
    required_permissions = {"post": ["can_upload_profile_photo"]}

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.errors(
                message="Invalid upload",
                data=serializer.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            storage = MinioStorage()
            raw = serializer.validated_data["based64_file"]
            path = storage.upload_base64_file(
                raw,
                folder="profile_photos",
                file_name=str(request.user.guid),
                old_file_path=request.user.photo or "",
            )
            request.user.photo = path
            request.user.save(update_fields=["photo", "updated_at"])
            photo_url = get_presigned_url(path, expires_hours=PROFILE_MEDIA_PRESIGN_HOURS)
            return CustomResponse.success(
                data={"photo": photo_url},
                message="Photo updated",
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))


class UserSignatureUpload(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = FileUploadSerializer
    required_permissions = {"post": ["can_upload_profile_signature"]}

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.errors(
                message="Invalid upload",
                data=serializer.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            storage = MinioStorage()
            raw = serializer.validated_data["based64_file"]
            path = storage.upload_base64_file(
                raw,
                folder="signatures",
                file_name=str(request.user.guid),
                old_file_path=request.user.signature or "",
            )
            request.user.signature = path
            request.user.save(update_fields=["signature", "updated_at"])
            signature_url = get_presigned_url(
                path, expires_hours=PROFILE_MEDIA_PRESIGN_HOURS
            )
            return CustomResponse.success(
                data={"signature": signature_url},
                message="Signature updated",
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

    def post(self, request):
        try:
            with transaction.atomic():
                # Accept both user_guid and guid (frontend may send either); treat empty string as missing
                raw_guid = request.data.get("user_guid") or request.data.get("guid")
                user_guid = (raw_guid or "").strip() or None
                instance = None
                is_update = False

                # ----------- Determine Update or Create -----------
                if user_guid:
                    print("-------------user_guid------------", user_guid)
                    try:
                        instance = User.objects.get(guid=user_guid)
                    except User.DoesNotExist:
                        return CustomResponse.errors(message="User not found")

                    if instance.is_deleted:
                        return CustomResponse.errors(message="User already deleted")

                    if not instance.is_active:
                        return CustomResponse.errors(message="Cannot update disabled user")

                    is_update = True

                # ----------- Prepare Data Before Validation -----------
                data = request.data.copy()

                # Uppercase formatting
                if "first_name" in data:
                    data["first_name"] = data["first_name"].strip().upper()

                if "middle_name" in data:
                    m = data.get("middle_name")
                    data["middle_name"] = m.strip().upper() if m else ""

                if "last_name" in data:
                    data["last_name"] = data["last_name"].strip().upper()

                # Set username for creation
                if not is_update:
                    if "first_name" in data and "last_name" in data:
                        data["username"] = f"{data['first_name']}.{data['last_name']}".lower()

                    data["status"] = "NEW"
                    data["created_by"] = request.user.id

                data["updated_by"] = request.user.id

                # ----------- Serializer -----------
                serializer = UserSerializer(
                    instance=instance,
                    data=data,
                    partial=is_update,
                    context={"request": request}
                )

                if not serializer.is_valid():
                    return CustomResponse.errors(
                        message="Validation failed",
                        data=serializer.errors
                    )
                user = serializer.save()
                # ----------- Set password on creation -----------
                print(is_update)
                if not is_update:
                    password = data.get("check_number", "")
                    user.set_password(password)
                    user.save(update_fields=["password"])

                # Create audit log for user create/update
                try:
                    from ppaa_portal.views import create_audit_log
                    action = "CREATE" if not is_update else "UPDATE"
                    create_audit_log(
                        request=request,
                        action=action,
                        model_name="User",
                        obj=user,
                        changes=serializer.data if is_update else None
                    )
                except Exception:
                    # Don't fail the request if audit log creation fails
                    pass

                return CustomResponse.success(data=serializer.data)

        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to Change User: {str(e)}")

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                user = User.objects.filter(uid=uid, is_deleted=False).first()
                if not User:
                    return CustomResponse.errors(message="User Not Found or Already Deleted", )

                user.is_deleted = True
                user.deleted_at = timezone.datetime.now()
                user.deleted_by = request.user
                user.save()
                
                # Create audit log for user deletion
                try:
                    from ppaa_portal.views import create_audit_log
                    create_audit_log(
                        request=request,
                        action="DELETE",
                        model_name="User",
                        obj=user,
                        changes={"deleted_by": request.user.username}
                    )
                except Exception:
                    # Don't fail the request if audit log creation fails
                    pass
                
                return CustomResponse.success(message='User deleted successfully')

        except SystemError as e:
            print(f'Failed to Perform Action: {str(e)}')
            return CustomResponse.server_error(message="Something went wrong While Deleting User")

class UserPhotoUpload(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = FileUploadSerializer

    def post(self, request):
        try:
            with (transaction.atomic()):
                serializer = self.serializer_class(
                    instance=None,
                    data=request.data,
                    partial=False
                )

                if not serializer.is_valid():
                    return CustomResponse.errors(
                        message="Validation failed, please try again"
                            if request.data.get('uid', None)
                            else "You can't update. You must Specify User to Update Photo",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )

                try:
                    instance = User.objects.get(guid=serializer.validated_data.get('uid'))
                    if instance.is_deleted:
                        return CustomResponse.errors(message="You can't update. Deleted User")
                except User.DoesNotExist:
                    return CustomResponse.errors(message="You can't update. You must Specify User to Update Photo")

                photo_base64 = serializer.validated_data.get('based64_file', '')
                minio = MinioStorage()
                file_name = instance.guid
                photo_url = minio.upload_base64_file(
                    photo_base64,
                    folder="user_photos",
                    file_name=file_name,
                    old_file_path=instance.photo
                )
                instance.photo = photo_url
                # User.updated_by is an IntegerField in ppaa_auth.models.User
                instance.updated_by = request.user.id
                instance.updated_at = timezone.now()
                instance.save(update_fields=["photo",'updated_by','updated_at'])
                
                # Create audit log for photo upload
                try:
                    from ppaa_portal.views import create_audit_log
                    create_audit_log(
                        request=request,
                        action="UPDATE",
                        model_name="UserPhoto",
                        obj=instance,
                        changes={"photo_updated": True, "photo_url": photo_url}
                    )
                except Exception:
                    # Don't fail the request if audit log creation fails
                    pass
                
                user_serializer = UserSerializer(instance)
                return CustomResponse.success(data=user_serializer.data)

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Change User Photo: {str(e)}', )

class UserSignatureUpload(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = FileUploadSerializer

    def post(self, request):
        try:
            with (transaction.atomic()):
                serializer = self.serializer_class(
                    instance=None,
                    data=request.data,
                    partial=False
                )

                if not serializer.is_valid():
                    return CustomResponse.errors(
                        message="Validation failed, please try again"
                            if request.data.get('uid', None)
                            else "You can't update. You must Specify User to Update Photo",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )

                try:
                    instance = User.objects.get(guid=serializer.validated_data.get('uid'))
                    if instance.is_deleted:
                        return CustomResponse.errors(message="You can't update. Deleted User")
                except User.DoesNotExist:
                    return CustomResponse.errors(message="You can't update. You must Specify User to Update Signature")

                file_base64 = serializer.validated_data.get('based64_file', '')
                minio = MinioStorage()
                file_name = instance.guid
                file_url = minio.upload_base64_file(
                    file_base64,
                    folder="user_signatures",
                    file_name=file_name,
                    old_file_path=instance.signature
                )
                instance.signature = file_url
                # User.updated_by is an IntegerField in ppaa_auth.models.User
                instance.updated_by = request.user.id
                instance.updated_at = timezone.now()
                instance.save(update_fields=["signature",'updated_by','updated_at'])
                
                # Create audit log for signature upload
                try:
                    from ppaa_portal.views import create_audit_log
                    create_audit_log(
                        request=request,
                        action="UPDATE",
                        model_name="UserSignature",
                        obj=instance,
                        changes={"signature_updated": True, "signature_url": file_url}
                    )
                except Exception:
                    # Don't fail the request if audit log creation fails
                    pass
                
                user_serializer = UserSerializer(instance)
                return CustomResponse.success(data=user_serializer.data)

        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to Change User signature: {str(e)}")
