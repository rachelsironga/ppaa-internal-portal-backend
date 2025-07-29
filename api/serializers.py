from rest_framework import serializers
from importlib import import_module
from django.core.exceptions import ImproperlyConfigured
from rest_framework.validators import UniqueTogetherValidator
from django.conf import settings

from mnh_auth.serializers import UserSerializer
from mnh_model.models import (
    ApprovalModule, ApprovalAction,
    ApprovalModuleLevel, ApprovalRequest, RequestJeevaAccess, RequestInternetEmailAccess, ApprovalRequestStep,
    JeevaRole, JeevaPermission, DateRange, ApprovalRequestHandler
)
from mnh_auth.models import PositionalLevel, Directory, Department, UserProfile, User

REQUEST_TYPE_SERIALIZER_IMPORTS = {
    'INTERNET_EMAIL_ACCESS': 'api.serializers.RequestInternetEmailAccessSerializer',
    'JEEVA_ACCESS': 'apps.mnh_approval.serializers.RequestJeeverAccessSerializer',
}


def get_serializer_class(request_type):
    path = REQUEST_TYPE_SERIALIZER_IMPORTS.get(request_type)
    if not path:
        raise ImproperlyConfigured(f"No serializer configured for request_type '{request_type}'")
    module_path, class_name = path.rsplit('.', 1)
    module = import_module(module_path)
    return getattr(module, class_name)


class DateRangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DateRange
        fields = ['uid', 'name', 'value', 'type', 'order', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }


class DirectoryImportSerializer(serializers.Serializer):
    file = serializers.CharField(required=True)  # base64 Excel string
    include_departments = serializers.BooleanField(required=False, default=True)



class DirectorySerializer(serializers.ModelSerializer):
    departments = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Directory
        fields = ['uid', 'name', 'code', 'description', 'created_at', 'updated_at', 'departments']
        read_only_fields = ['uid', 'created_at', 'updated_at']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }

    def get_departments(self, obj):
        if hasattr(self, 'context') and self.context.get('include_departments'):
            departments = obj.departments.filter(is_deleted=False)
            return DepartmentSerializer(departments, many=True).data
        return None

    def validate(self, data):
        name = data.get('name')
        code = data.get('code')
        uid = self.instance.uid if self.instance else None
        existing = PositionalLevel.objects.filter(name=name, code=code, deleted_at=None)
        if existing.exclude(uid=uid).exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("this name and code already exists.")

        return data


class DepartmentSerializer(serializers.ModelSerializer):
    directory_uid = serializers.UUIDField(write_only=True)
    directory = DirectorySerializer(read_only=True)

    class Meta:
        model = Department
        fields = ['uid', 'name', 'code', 'directory', 'directory_uid', 'description', 'is_active', 'created_at',
                  'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at', 'directory_uid']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }

    def validate(self, data):
        name = data.get('name')
        code = data.get('code')
        uid = self.instance.uid if self.instance else None

        directory_uid = data.get('directory_uid')
        try:
            data['directory'] = Directory.objects.get(uid=directory_uid, is_deleted=False)
        except Directory.DoesNotExist:
            raise serializers.ValidationError({"directory_uid": "Invalid Directory, not found or deleted"})

        # Check for existing department with the same name and code that is NOT deleted
        existing = Department.objects.filter(name=name, code=code, deleted_at=None)

        # If updating, ensure the existing record (if any) is not a different UID
        if existing.exclude(uid=uid).exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("this name and code already exists.")

        return data

    def create(self, validated_data):
        validated_data.pop('directory_uid')
        return Department.objects.create(**validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('directory_uid', None)
        return super().update(instance, validated_data)


class PositionalLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = PositionalLevel
        fields = ['uid', 'name', 'code', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }

    def validate(self, data):
        name = data.get('name')
        code = data.get('code')
        uid = self.instance.uid if self.instance else None
        existing = PositionalLevel.objects.filter(name=name, code=code, deleted_at=None)
        if existing.exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("this name and code already exists.")
        return data


class UserProfileViewSerializer(serializers.ModelSerializer):
    directory = DirectorySerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    level = PositionalLevelSerializer(read_only=True)


class UserProfileSerializer(serializers.ModelSerializer):
    user_uid = serializers.UUIDField(write_only=True, required=False)
    user = UserSerializer(read_only=True)

    directory_uid = serializers.UUIDField(write_only=True)
    directory = DirectorySerializer(read_only=True)

    department_uid = serializers.UUIDField(write_only=True, required=False)
    department = DepartmentSerializer(read_only=True)

    level_uid = serializers.UUIDField(write_only=True)
    level = PositionalLevelSerializer(read_only=True)

    end_date = serializers.DateTimeField(
        format="%d-%m-%Y %H:%M",
        input_formats=["%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M"],
        required=False,
    )

    created_at = serializers.DateTimeField(
        format="%d-%m-%Y %H:%M",
        input_formats=["%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M"],
        required=False,
    )

    class Meta:
        model = UserProfile
        fields = ['uid', 'user_uid', 'user', 'level', 'level_uid', 'directory', 'directory_uid', 'is_active',
                  'department_uid', 'department', 'created_at', 'updated_at', 'end_date'
                  ]
        read_only_fields = ['uid', 'created_at', 'updated_at', 'end_date']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }

    def validate(self, data):
        user_uid = data.pop('user_uid')
        level_uid = data.pop('level_uid')
        directory_uid = data.pop('directory_uid')
        department_uid = data.pop('department_uid', None)

        try:
            data['user'] = User.objects.get(guid=user_uid, is_active=True, is_deleted=False)
        except Exception as e:
            raise serializers.ValidationError({"user_uid": "Unable Find User,May be Deleted or Disabled"})

        try:
            data['department'] = Department.objects.get(uid=department_uid, is_deleted=False)
        except User.DoesNotExist:
            data['department'] = None

        try:
            data['directory'] = Directory.objects.get(uid=directory_uid, is_deleted=False)
        except Directory.DoesNotExist:
            raise serializers.ValidationError({"directory_uid": "Invalid Directory, not found or deleted"})

        try:
            data['level'] = PositionalLevel.objects.get(uid=level_uid, is_deleted=False)
        except PositionalLevel.DoesNotExist:
            raise serializers.ValidationError({"level_uid": "Invalid Level, not found or deleted"})

        return data


class ApprovalActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalAction
        fields = ['uid', 'name', 'code', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }

    def validate(self, data):
        name = data.get('name')
        code = data.get('code')
        uid = self.instance.uid if self.instance else None
        existing = ApprovalAction.objects.filter(name=name, code=code, deleted_at=None)
        if existing.exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("this name and code already exists.")

        return data


class ApprovalRequestStepSerializer(serializers.ModelSerializer):
    request_uid = serializers.UUIDField(write_only=True, required=False)
    handler_user = serializers.UUIDField(write_only=True, required=False)
    module_level_uid = serializers.UUIDField(write_only=True, required=False)
    action = serializers.ChoiceField(choices=["FORWARD", "RETURN"], write_only=True)


    approved_by = serializers.SerializerMethodField(read_only=True)
    approval_level = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ApprovalRequestStep
        fields = ['uid', 'approved_by', 'is_acting', 'is_approved','action_count','handler_user', 'comment','action',
                  'request_uid', 'module_level_uid', 'approval_level','created_at', 'updated_at']
        read_only_fields = ['uid', 'created_by', 'created_at', 'updated_at']

    def get_approved_by(self, obj):
        if obj.approved_by:
            user = {
                'uid': obj.approved_by.guid,
                'name': f'{obj.approved_by.first_name} {obj.approved_by.middle_name} {obj.approved_by.last_name}',
                'email': obj.approved_by.email,
                'position': obj.approved_by.get_position(),
                'signature': f'{settings.MEDIA_URL if settings.MEDIA_URL.endswith('/') else settings.MEDIA_URL + '/'}{obj.approved_by.signature}' if obj.approved_by.signature else "",
            }
            return user
        return None

    def get_approved_by(self, obj):
        if obj.approved_by:
            user = {
                'uid': obj.approved_by.guid,
                'name': f'{obj.approved_by.first_name} {obj.approved_by.middle_name} {obj.approved_by.last_name}',
                'email': obj.approved_by.email,
                'position': obj.approved_by.get_position(),
                'signature': f'{settings.MEDIA_URL if settings.MEDIA_URL.endswith('/') else settings.MEDIA_URL + '/'}{obj.approved_by.signature}' if obj.approved_by.signature else "",
            }
            return user
        return None

    def get_approval_level(self, obj):
        if obj.approval_module_level:
            return {
               'level': {
                   'uid': obj.approval_module_level.level.uid,
                   'name': obj.approval_module_level.level.name,
                   'code': obj.approval_module_level.level.code
               },
                'action' : {
                    'uid': obj.approval_module_level.action.uid,
                    'name': obj.approval_module_level.action.name,
                    'code': obj.approval_module_level.action.code
                }
            }
        return None

    def validate(self, data):
        request_uid = data.get('request_uid')
        module_level_uid = data.get('module_level_uid')

        try:
            data['approval_request'] = ApprovalRequest.objects.get(uid=request_uid, is_deleted=False)
        except ApprovalRequest.DoesNotExist:
            raise serializers.ValidationError({"request_uid": "Invalid Request, not found or deleted"})

        try:
            data['approval_module_level'] = ApprovalModuleLevel.objects.get(uid=module_level_uid, is_deleted=False)
        except ApprovalModuleLevel.DoesNotExist:
            raise serializers.ValidationError({"module_level_uid": "Invalid Module Level, not found or deleted"})

        return data

    def create(self, validated_data):
        """
        Create a new ApprovalModuleLevel instance using the validated objects.
        """
        validated_data.pop('module_level_uid')
        validated_data.pop('request_uid')
        return ApprovalModuleLevel.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """
        Update an existing ApprovalModuleLevel instance.
        """
        validated_data.pop('module_level_uid', None)
        validated_data.pop('request_uid', None)

        return super().update(instance, validated_data)


class ApprovalModuleLevelSerializer(serializers.ModelSerializer):
    module_uid = serializers.UUIDField(write_only=True)
    level_uid = serializers.UUIDField(write_only=True)
    action_uid = serializers.UUIDField(write_only=True)
    department_uid = serializers.UUIDField(write_only=True)

    level = PositionalLevelSerializer(read_only=True)
    action = ApprovalActionSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    step = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalModuleLevel
        fields = [
            'uid', 'module_uid', 'level_uid', 'level', 'step',
            'action_uid', 'action', 'order', 'department', 'department_uid',
            'is_active', 'is_signatory', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uid', 'created_at', 'updated_at']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }

    def get_step(self, obj):
        request_uid = self.context.get('approval_request_uid')
        if request_uid:
            try:
                step = ApprovalRequestStep.objects.get(
                    approval_request__uid=request_uid,
                    approval_module_level=obj,
                    is_active=True
                )
                return ApprovalRequestStepSerializer(step).data
            except ApprovalRequestStep.DoesNotExist:
                return None
        return None

    def validate(self, data):
        """
        Ensure that module_uid, level_uid, and action_uid exist in the database.
        """
        module_uid = data.get('module_uid')
        level_uid = data.get('level_uid')
        action_uid = data.get('action_uid')
        department_uid = data.get('department_uid')

        try:
            data['module'] = ApprovalModule.objects.get(uid=module_uid, is_deleted=False)
        except ApprovalModule.DoesNotExist:
            raise serializers.ValidationError({"module_uid": "Invalid Module, not found or deleted"})

        try:
            data['level'] = PositionalLevel.objects.get(uid=level_uid, is_deleted=False)
        except PositionalLevel.DoesNotExist:
            raise serializers.ValidationError({"level_uid": "Invalid Level, not found or deleted"})

        try:
            data['action'] = ApprovalAction.objects.get(uid=action_uid, is_deleted=False)
        except ApprovalAction.DoesNotExist:
            raise serializers.ValidationError({"action_uid": "Invalid Action, not found or deleted"})

        try:
            data['department'] = Department.objects.get(uid=department_uid, is_deleted=False)
        except ApprovalAction.DoesNotExist:
            raise serializers.ValidationError({"department_uid": "Invalid Department, not found or deleted"})

        return data

    def create(self, validated_data):
        """
        Create a new ApprovalModuleLevel instance using the validated objects.
        """
        validated_data.pop('module_uid')
        validated_data.pop('level_uid')
        validated_data.pop('action_uid')
        validated_data.pop('department_uid')
        return ApprovalModuleLevel.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """
        Update an existing ApprovalModuleLevel instance.
        """
        validated_data.pop('module_uid', None)
        validated_data.pop('level_uid', None)
        validated_data.pop('action_uid', None)
        validated_data.pop('department_uid')

        return super().update(instance, validated_data)


class ApprovalModuleSerializer(serializers.ModelSerializer):
    approval_module_levels = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalModule
        fields = ['uid', 'code', 'name', 'description', 'approval_module_levels', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'approval_module_levels', 'created_at', 'updated_at']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }

    def get_approval_module_levels(self, obj):
        related_name = 'approvalmodulelevel_set'
        related_objects = getattr(obj, related_name, None)

        if related_objects:
            # Filter is_deleted=False
            filtered = related_objects.filter(is_deleted=False)
            return ApprovalModuleLevelSerializer(
                filtered,
                many=True,
                context=self.context
            ).data
            # return ApprovalModuleLevelSerializer(related_objects.all(), many=True).data
        return []

    def validate(self, data):
        name = data.get('name')
        uid = self.instance.uid if self.instance else None
        existing = PositionalLevel.objects.filter(name=name, deleted_at=None)
        if existing.exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("this module already exists.")
        return data


class ApprovalRequestSerializer(serializers.ModelSerializer):
    module_uid = serializers.UUIDField(write_only=True)
    date_range_uid = serializers.UUIDField(write_only=True)
    department_uid = serializers.UUIDField(write_only=True, required=True, allow_null=False)

    request_data = serializers.DictField(write_only=True)

    module = ApprovalModuleSerializer(read_only=True)
    date_range = DateRangeSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    request_details = serializers.SerializerMethodField(read_only=True)
    requester_name = serializers.SerializerMethodField(read_only=True)
    created_by = UserSerializer(read_only=True)
    request_handler = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ApprovalRequest
        fields = [
            'uid', 'title', 'description', 'type', 'request_data', 'module_uid', 'date_range_uid', 'department_uid',
            'requester_name', 'current_state', 'module', 'department', 'date_range', 'created_by', 'status',
            'created_at', 'updated_at', 'request_details', 'request_handler'
        ]
        read_only_fields = ['uid', 'created_by', 'created_at', 'updated_at', 'status']

    def get_request_details(self, obj):
        return obj.request_data

    def get_created_by(self, obj):
        if self.context.get('show_full_user', False):
            return UserSerializer(obj.created_by).data if obj.created_by else None
        return {
            "guid": obj.created_by.guid,
        }

    def get_request_handler(self, obj):
        if self.context.get('show_full_user', False):
            if obj.status in ['APPROVED', 'REJECTED']:
                handler_user = ApprovalRequestHandler.objects.filter(
                    approval_request=obj,
                    is_deleted=False
                ).first()

                if handler_user and handler_user.handler:
                    return {
                        'name': handler_user.handler.first_name + " " + handler_user.handler.last_name,
                        'email': handler_user.handler.email,
                        'guid': handler_user.handler.guid,
                        'pf_number': handler_user.handler.pf_number,
                    }
        return None

    def get_requester_name(self, obj):
        user = obj.created_by  # created_by is already a related user instance if FK
        if user:
            return f"{user.first_name} {user.last_name}".strip() or user.username
        return "N/A"

    def validate(self, data):
        module_uid = data.pop('module_uid')
        date_range_uid = data.pop('date_range_uid')
        department_uid = data.pop('department_uid')

        try:
            data['date_range'] = DateRange.objects.get(uid=date_range_uid, is_deleted=False)
        except DateRange.DoesNotExist:
            raise serializers.ValidationError({"date_range_uid": "Invalid Date Range, not found or deleted"})

        try:
            data['module'] = ApprovalModule.objects.get(uid=module_uid, is_deleted=False)
            data['type'] = data['module'].code if data['module'] else None
        except ApprovalModule.DoesNotExist:
            raise serializers.ValidationError({"module_uid": "Invalid Module, not found or deleted"})

        try:
            data['department'] = Department.objects.get(uid=department_uid, is_deleted=False)
        except Department.DoesNotExist:
            raise serializers.ValidationError({"department_uid": "Invalid Department, not found or deleted"})

        return data

    def create(self, validated_data):
        return ApprovalRequest.objects.create(**validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class JeevaRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = JeevaRole
        fields = ['uid', 'name', 'code', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }

    def validate(self, data):
        name = data.get('name')
        code = data.get('code')
        uid = self.instance.uid if self.instance else None

        existing = JeevaRole.objects.filter(name=name, code=code, deleted_at=None)
        if existing.exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("this name and code already exists.")
        return data

class JeevaPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JeevaPermission
        fields = ['uid', 'name', 'code', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }

    def validate(self, data):
        name = data.get('name')
        code = data.get('code')
        uid = self.instance.uid if self.instance else None

        existing = JeevaRole.objects.filter(name=name, code=code, deleted_at=None)
        if existing.exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("this name and code already exists.")
        return data


class JeevaPermissionNestedSerializer(serializers.ModelSerializer):
    codename = serializers.CharField(source="code")

    class Meta:
        model = JeevaPermission
        fields = ["codename", "name"]

class JeevaRoleNestedSerializer(serializers.ModelSerializer):
    codename = serializers.CharField(source="code")
    Permissions = serializers.SerializerMethodField()

    class Meta:
        model = JeevaRole
        fields = ["codename", "name", "Permissions"]

    def get_Permissions(self, obj):
        permissions = obj.permissions.filter(is_active=True)
        return JeevaPermissionNestedSerializer(permissions, many=True).data


class RequestInternetEmailAccessSerializer(serializers.ModelSerializer):
    approval_request = ApprovalRequestSerializer(read_only=True)

    class Meta:
        model = RequestInternetEmailAccess
        fields = ['uid', 'approval_request', 'start_date', 'end_date', 'is_read_term', 'purpose']
        read_only_fields = ['uid', 'created_at', 'updated_at']


class RequestJeevaAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestJeevaAccess
        fields = '__all__'
