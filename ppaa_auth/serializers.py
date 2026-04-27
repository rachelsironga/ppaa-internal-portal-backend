import re

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from ppaa_auth.models import Department, GroupProfile, UserProfile
from ppaa_portal.services.minio.minio_helpers import (
    PROFILE_MEDIA_PRESIGN_HOURS,
    get_presigned_url,
)

User = get_user_model()


def _allocate_unique_username_from_email(email: str) -> str:
    """Build a non-empty unique username from email local-part (fallback only)."""
    raw = (email or "").strip()
    local = raw.split("@", 1)[0] if "@" in raw else ""
    local = re.sub(r"[^\w.\-]", "_", local) or "user"
    local = local.strip("._-") or "user"
    base = local[:120]
    candidate = base
    n = 0
    while User.objects.filter(username__iexact=candidate).exists():
        n += 1
        suffix = f"_{n}"
        candidate = (base[: 150 - len(suffix)] + suffix)
    return candidate[:150]


def _slug_username_segment(name: str, max_len: int = 60) -> str:
    """Lowercase letters/digits only (Unicode word chars) for a username segment."""
    s = (name or "").strip().lower()
    s = re.sub(r"[^\w]+", "", s, flags=re.UNICODE)
    return s[:max_len]


def _first_given_token(first_name: str) -> str:
    parts = (first_name or "").strip().split()
    return parts[0] if parts else ""


def _allocate_unique_username_from_names(
    first_name: str, last_name: str, email: str
) -> str:
    """
    System username: ``firstname.lastname`` (first word of first name + whole last name),
    lowercased and uniquified. Falls back to email-based username if names produce nothing.
    """
    first = _slug_username_segment(_first_given_token(first_name))
    last = _slug_username_segment((last_name or "").strip())
    if first and last:
        base = f"{first}.{last}"
    elif first:
        base = first
    elif last:
        base = last
    else:
        return _allocate_unique_username_from_email(email)
    base = (base or "").strip(".")[:150]
    if not base or base == ".":
        return _allocate_unique_username_from_email(email)
    candidate = base
    n = 0
    while User.objects.filter(username__iexact=candidate).exists():
        n += 1
        suffix = f"_{n}"
        candidate = (base[: 150 - len(suffix)] + suffix)
    return candidate[:150]


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class CheckUserNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username",)


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("uid", "name", "code", "description", "is_active", "created_at", "updated_at")
        read_only_fields = ("uid", "created_at", "updated_at")


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ("id", "name", "codename", "content_type")


class GroupListSerializer(serializers.ModelSerializer):
    uid = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ("uid", "name")

    def get_uid(self, obj):
        return str(obj.pk)


class GroupSerializer(serializers.ModelSerializer):
    uid = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    users = serializers.SerializerMethodField()
    last_update_at = serializers.SerializerMethodField()
    update_count = serializers.SerializerMethodField()
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = (
            "uid",
            "name",
            "permissions",
            "users",
            "last_update_at",
            "last_updated_by",
            "update_count",
        )
        read_only_fields = (
            "uid",
            "users",
            "last_update_at",
            "last_updated_by",
            "update_count",
        )

    def get_uid(self, obj):
        return str(obj.pk)

    def get_permissions(self, obj):
        perms = obj.permissions.all().order_by(
            "content_type__app_label", "content_type__model", "codename"
        )
        return PermissionSerializer(perms, many=True).data

    def get_users(self, obj):
        return [
            str(u)
            for u in obj.user_set.filter(is_deleted=False).values_list(
                "guid", flat=True
            )
        ]

    def get_last_update_at(self, obj):
        p = getattr(obj, "group_profile", None)
        return p.last_updated_at if p else None

    def get_update_count(self, obj):
        p = getattr(obj, "group_profile", None)
        return p.update_count if p else 0

    def get_last_updated_by(self, obj):
        p = getattr(obj, "group_profile", None)
        if p and p.last_updated_by_id:
            return p.last_updated_by_id
        return None

    def create(self, validated_data):
        name = validated_data.get("name")
        group = Group.objects.create(name=name)
        GroupProfile.objects.get_or_create(group=group)
        return group

    def update(self, instance, validated_data):
        name = validated_data.get("name")
        if name is not None:
            instance.name = name
            instance.save(update_fields=["name"])
        profile, _ = GroupProfile.objects.get_or_create(group=instance)
        request = self.context.get("request")
        from django.utils import timezone

        profile.last_updated_at = timezone.now()
        if request and request.user.is_authenticated:
            profile.last_updated_by = request.user
        profile.save()
        return instance


class AssignUserRoleSerializer(serializers.Serializer):
    permitted_user = serializers.CharField()
    selected_role = serializers.CharField()

    def validate(self, attrs):
        uid = attrs["permitted_user"].strip()
        role = attrs["selected_role"].strip()
        user = User.objects.filter(guid=uid, is_deleted=False).first()
        if not user:
            raise serializers.ValidationError({"permitted_user": "User not found"})
        group = Group.objects.filter(id=int(role)).first()
        if not group:
            raise serializers.ValidationError({"selected_role": "Role not found"})
        attrs["_user"] = user
        attrs["_group"] = group
        return attrs

    def create(self, validated_data):
        user = validated_data["_user"]
        group = validated_data["_group"]
        user.groups.add(group)
        return user

    def update(self, instance, validated_data):
        return instance

    def delete(self):
        pass


class AssignUserRolesListSerializer(serializers.Serializer):
    permitted_user = serializers.CharField()
    selected_roles = serializers.ListField(child=serializers.IntegerField())

    def validate(self, attrs):
        uid = attrs["permitted_user"].strip()
        user = User.objects.filter(guid=uid, is_deleted=False).first()
        if not user:
            raise serializers.ValidationError({"permitted_user": "User not found"})
        roles = Group.objects.filter(id__in=attrs["selected_roles"])
        if roles.count() != len(set(attrs["selected_roles"])):
            raise serializers.ValidationError({"selected_roles": "Invalid role id"})
        attrs["_user"] = user
        attrs["_groups"] = roles
        return attrs

    def create(self, validated_data):
        user = validated_data["_user"]
        # Replace membership to match the submitted list (add + remove in one save)
        user.groups.set(validated_data["_groups"])
        return user


class UserSerializer(serializers.ModelSerializer):
    user_guid = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()
    user_permissions = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    signature = serializers.SerializerMethodField()
    position = serializers.SerializerMethodField()
    current_department_name = serializers.SerializerMethodField()
    current_level_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "guid",
            "user_guid",
            "username",
            "email",
            "check_number",
            "first_name",
            "middle_name",
            "last_name",
            "status",
            "account_type",
            "dob",
            "sex",
            "is_active",
            "is_staff",
            "is_superuser",
            "photo",
            "phone_number",
            "alternative_contact",
            "signature",
            "password",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "groups",
            "user_permissions",
            "position",
            "current_level_name",
            "current_department_name",
        )
        read_only_fields = (
            "id",
            "guid",
            "username",
            "account_type",
            "is_superuser",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "password": {"write_only": True, "required": False},
        }

    def get_user_guid(self, obj):
        return str(obj.guid)

    def get_groups(self, obj):
        # Portal UI expects role names (e.g. staff, admin), not group PKs.
        if hasattr(obj, "get_groups"):
            return obj.get_groups()
        return [n.lower() for n in obj.groups.values_list("name", flat=True)]

    def get_user_permissions(self, obj):
        # Portal checks codenames (e.g. can_view_spism_dashboard), not permission PKs.
        if hasattr(obj, "get_permission_codes"):
            return obj.get_permission_codes()
        return list(obj.user_permissions.values_list("codename", flat=True))

    def get_photo(self, obj):
        if not obj.photo:
            return None
        url = get_presigned_url(obj.photo, expires_hours=PROFILE_MEDIA_PRESIGN_HOURS)
        return url

    def get_signature(self, obj):
        if not obj.signature:
            return None
        url = get_presigned_url(obj.signature, expires_hours=PROFILE_MEDIA_PRESIGN_HOURS)
        return url

    def get_position(self, obj):
        return obj.get_position() if hasattr(obj, "get_position") else {}

    def get_current_level_name(self, obj):
        pos = obj.get_position() if hasattr(obj, "get_position") else {}
        return pos.get("level_name")

    def get_current_department_name(self, obj):
        pos = obj.get_position() if hasattr(obj, "get_position") else {}
        return pos.get("department_name")

    def validate(self, data):
        return data

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        validated_data.pop("groups", None)
        validated_data.pop("user_permissions", None)
        email = validated_data.pop("email", None)
        username = validated_data.pop("username", None)
        username = (username or "").strip()
        if not username:
            username = _allocate_unique_username_from_names(
                validated_data.get("first_name") or "",
                validated_data.get("last_name") or "",
                email or "",
            )
        # Staff-created portal users start as NEW until first login / activation
        validated_data.setdefault("status", User.AccountStatus.NEW)
        user = User.objects.create_user(
            username=username,
            email=email or "",
            password=password,
            **validated_data,
        )
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        validated_data.pop("groups", None)
        validated_data.pop("user_permissions", None)
        # Wizard does not send username; never blank it (duplicate '' usernames).
        if "username" in validated_data:
            new_u = (validated_data.get("username") or "").strip()
            if not new_u:
                validated_data.pop("username", None)
            else:
                validated_data["username"] = new_u
        status_val = validated_data.get("status", instance.status)
        if "status" in validated_data:
            if status_val in (
                User.AccountStatus.SUSPENDED,
                User.AccountStatus.RETIRED,
            ):
                validated_data.setdefault("is_active", False)
            elif status_val == User.AccountStatus.ACTIVE:
                validated_data.setdefault("is_active", True)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class RegistrationSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField()
    account_type = serializers.CharField()

    class Meta:
        model = User
        fields = (
            "first_name",
            "username",
            "last_name",
            "phone_number",
            "password",
            "email",
            "account_type",
        )

    def save(self, **kwargs):
        data = {**self.validated_data, **kwargs}
        with transaction.atomic():
            user = User.objects.create_user(
                username=data["username"],
                email=data["email"],
                password=data["password"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                phone_number=data["phone_number"],
                account_type=data.get("account_type") or User.AccountType.INDIVIDUAL,
            )
            self.assign_role_permissions(user, data.get("account_type"))
        return user

    def assign_role_permissions(self, user, account_type):
        if not account_type:
            return
        group = Group.objects.filter(name__iexact=str(account_type)).first()
        if group:
            user.groups.add(group)


class NewUserLoginSerializer(serializers.Serializer):
    """Activate NEW accounts: verify ``initial_password`` (check no.), set ``new_password``, profile fields."""

    username = serializers.CharField()
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=64)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    initial_password = serializers.CharField(
        write_only=True,
        help_text="Same secret used on first login (check number or temporary password).",
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords must match"}
            )
        return attrs

    def save(self, **kwargs):
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField()

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect")
        return value


class PasswordNewChangeSerializer(serializers.Serializer):
    uid = serializers.UUIDField()
    new_password = serializers.CharField()
    confirm_password = serializers.CharField()

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError("Passwords do not match")
        return attrs


class PasswordResetSerializer(serializers.Serializer):
    user_guid = serializers.UUIDField()

    def validate_user_guid(self, value):
        if not User.objects.filter(guid=value, is_deleted=False).exists():
            raise serializers.ValidationError("User not found")
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email__iexact=value, is_deleted=False).exists():
            raise serializers.ValidationError("Unknown email")
        return value


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "email",
            "photo",
            "phone_number",
            "alternative_contact",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class UserIdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "guid", "username", "email", "first_name", "last_name")


class UserImportSerializer(serializers.Serializer):
    file = serializers.CharField()


class DesignationImportSerializer(serializers.Serializer):
    file = serializers.CharField()


class FileUploadSerializer(serializers.Serializer):
    uid = serializers.UUIDField(required=False, allow_null=True)
    based64_file = serializers.CharField()


class ActingUserSerializer(serializers.Serializer):
    user_uid = serializers.UUIDField()
    delegated_user = serializers.UUIDField(required=False, allow_null=True)
