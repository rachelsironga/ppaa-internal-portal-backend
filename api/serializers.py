from rest_framework import serializers
from django.contrib.auth.models import User
from importlib import import_module
from django.core.exceptions import ImproperlyConfigured
from rest_framework.validators import UniqueTogetherValidator


from mnh_auth.serializers import UserSerializer
from mnh_model.models import (
    ApprovalModule, ApprovalAction,
    ApprovalModuleLevel, ApprovalRequest, RequestJeevaAccess, RequestInternetEmailAccess, ApprovalRequestStep,
    JeevaRole, JeevaPermission
)
from mnh_auth.models import PositionalLevel, Directory, Department

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


class ApprovalLevelSerializer(serializers.ModelSerializer):
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
        existing = PositionalLevel.objects.filter(name=name, code=code, deleted_at=None)
        if existing.exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("this name and code already exists.")

        return data


class ApprovalModuleLevelSerializer(serializers.ModelSerializer):
    module_uid = serializers.UUIDField(write_only=True)
    level_uid = serializers.UUIDField(write_only=True)
    action_uid = serializers.UUIDField(write_only=True)
    department_uid = serializers.UUIDField(write_only=True)

    level = ApprovalLevelSerializer(read_only=True)
    action = ApprovalActionSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)

    class Meta:
        model = ApprovalModuleLevel
        fields = [
            'uid', 'module_uid', 'level_uid', 'level',
            'action_uid', 'action', 'order', 'department', 'department_uid',
            'is_active', 'is_signatory', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uid', 'created_at', 'updated_at']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }

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
        fields = ['uid', 'name', 'description', 'approval_module_levels', 'created_at', 'updated_at']
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
            return ApprovalModuleLevelSerializer(filtered, many=True).data
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


class RequestInternetEmailAccessSerializer(serializers.ModelSerializer):
    approval_request = serializers.PrimaryKeyRelatedField(queryset=ApprovalRequest.objects.all())
    class Meta:
        model = RequestInternetEmailAccess
        fields = ['uid','approval_request', 'start_date', 'end_date', 'purpose']
        read_only_fields = ['uid', 'created_at','is_read_term', 'updated_at']


class ApprovalRequestSerializer(serializers.ModelSerializer):
    module_uid = serializers.UUIDField(write_only=True)
    department_uid = serializers.UUIDField(write_only=True, required=True, allow_null=False)

    type = serializers.ChoiceField(choices=ApprovalRequest.REQUEST_TYPES)
    request_data = serializers.DictField(write_only=True)

    module = ApprovalModuleSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)

    request_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ApprovalRequest
        fields = [
            'uid', 'title', 'description', 'type', 'request_data',
            'module_uid', 'department_uid','module', 'department', 'created_by',
            'status', 'created_at', 'updated_at','request_details'
        ]
        read_only_fields = ['uid', 'created_by','created_at', 'updated_at', 'status']

    def get_request_details(self, obj):
        try:
            inner_serializer = get_serializer_class(obj.type)
            if not inner_serializer:
                return None
            child_instance = getattr(obj, 'request_details')  # e.g., obj.internet_email_access
            return inner_serializer(child_instance).data
        except AttributeError:

            return None

    def validate(self, data):
        module_uid = data.get('module_uid')
        department_uid = data.get('department_uid')

        try:
            data['module'] = ApprovalModule.objects.get(uid=module_uid, is_deleted=False)
        except ApprovalModule.DoesNotExist:
            raise serializers.ValidationError({"module_uid": "Invalid Module, not found or deleted"})
        try:
            data['department'] = Department.objects.get(uid=department_uid, is_deleted=False)
        except Department.DoesNotExist:
            raise serializers.ValidationError({"department_uid": "Invalid Department, not found or deleted"})

        return data

    def create(self, validated_data):
        validated_data.pop('request_data')
        validated_data.pop('module_uid')
        validated_data.pop('department_uid')
        return ApprovalRequest.objects.create(**validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('request_data')
        validated_data.pop('module_uid')
        validated_data.pop('department_uid')

        return super().update(instance, validated_data)



class ApprovalRequestStepSerializer(serializers.ModelSerializer):
    approval_request_title = serializers.ReadOnlyField(source='approval_request.title')
    approved_by_username = serializers.ReadOnlyField(source='approved_by.username')

    class Meta:
        model = ApprovalRequestStep
        fields = '__all__'


class RequestJeevaAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestJeevaAccess
        fields = '__all__'
