from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework.validators import UniqueTogetherValidator

from mnh_model.models import (
    ApprovalModule, ApprovalLevel, ApprovalAction,
    ApprovalModuleLevel, ApprovalRequest, RequestJeevaAccess, RequestInternetEmailAccess, ApprovalRequestStep,
    Department, JeevaRole, JeevaPermission
)


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
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
        uid = self.instance.uid if self.instance else None  # Get UID if updating

        # Check for existing department with same name & code that is NOT deleted
        existing = Department.objects.filter(name=name, code=code, deleted_at=None)

        # If updating, ensure the existing record (if any) is not a different UID
        if existing.exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("this name and code already exists.")

        return data

class ApprovalLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalLevel
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
        existing = ApprovalLevel.objects.filter(name=name, code=code, deleted_at=None)
        if existing.exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("this name and code already exists.")

        return data

class ApprovalActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalAction
        fields = ['uid', 'name', 'code','description', 'is_active', 'created_at', 'updated_at']
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
        existing = ApprovalLevel.objects.filter(name=name, code=code, deleted_at=None)
        if existing.exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("this name and code already exists.")

        return data


class ApprovalModuleLevelSerializer(serializers.ModelSerializer):
    module_uid = serializers.UUIDField(write_only=True)
    level_uid = serializers.UUIDField(write_only=True)
    action_uid = serializers.UUIDField(write_only=True)

    level = ApprovalLevelSerializer(read_only=True)
    action = ApprovalActionSerializer(read_only=True)

    class Meta:
        model = ApprovalModuleLevel
        fields = [
            'uid', 'module_uid', 'level_uid', 'level',
            'action_uid', 'action', 'order',
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

        try:
            data['module'] = ApprovalModule.objects.get(uid=module_uid, is_deleted=False)
        except ApprovalModule.DoesNotExist:
            raise serializers.ValidationError({"module_uid": "Invalid Module, not found or deleted"})

        try:
            data['level'] = ApprovalLevel.objects.get(uid=level_uid, is_deleted=False)
        except ApprovalLevel.DoesNotExist:
            raise serializers.ValidationError({"level_uid": "Invalid Level, not found or deleted"})

        try:
            data['action'] = ApprovalAction.objects.get(uid=action_uid, is_deleted=False)
        except ApprovalAction.DoesNotExist:
            raise serializers.ValidationError({"action_uid": "IInvalid Action, not found or deleted"})

        return data

    def create(self, validated_data):
        """
        Create a new ApprovalModuleLevel instance using the validated objects.
        """
        validated_data.pop('module_uid')
        validated_data.pop('level_uid')
        validated_data.pop('action_uid')
        return ApprovalModuleLevel.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """
        Update an existing ApprovalModuleLevel instance.
        """
        validated_data.pop('module_uid', None)
        validated_data.pop('level_uid', None)
        validated_data.pop('action_uid', None)

        return super().update(instance, validated_data)

class ApprovalModuleSerializer(serializers.ModelSerializer):
    approval_module_levels = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalModule
        fields = ['uid', 'name','description','approval_module_levels', 'created_at', 'updated_at']
        read_only_fields = ['uid','approval_module_levels', 'created_at', 'updated_at']
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
        existing = ApprovalLevel.objects.filter(name=name, deleted_at=None)
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




class ApprovalRequestSerializer(serializers.ModelSerializer):
    module_name = serializers.ReadOnlyField(source='module.name')
    department_name = serializers.ReadOnlyField(source='department.name')
    requested_by_username = serializers.ReadOnlyField(source='requested_by.username')

    class Meta:
        model = ApprovalRequest
        fields = '__all__'
        read_only_fields = ['status']

class ApprovalRequestStepSerializer(serializers.ModelSerializer):
    approval_request_title = serializers.ReadOnlyField(source='approval_request.title')
    approved_by_username = serializers.ReadOnlyField(source='approved_by.username')

    class Meta:
        model = ApprovalRequestStep
        fields = '__all__'

class RequestInternetEmailAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestInternetEmailAccess
        fields = '__all__'


class RequestJeevaAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestJeevaAccess
        fields = '__all__'

