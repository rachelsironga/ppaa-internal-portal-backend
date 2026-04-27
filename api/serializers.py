from rest_framework import serializers
from importlib import import_module
from django.core.exceptions import ImproperlyConfigured
from rest_framework.validators import UniqueTogetherValidator
from django.conf import settings

from ppaa_auth.serializers import UserSerializer

from ppaa_auth.models import PositionalLevel, Department, UserProfile, User




def get_serializer_class(request_type):
    path = REQUEST_TYPE_SERIALIZER_IMPORTS.get(request_type)
    if not path:
        raise ImproperlyConfigured(f"No serializer configured for request_type '{request_type}'")
    module_path, class_name = path.rsplit('.', 1)
    module = import_module(module_path)
    return getattr(module, class_name)


class DepartmentImportSerializer(serializers.Serializer):
    file = serializers.CharField(required=True)  # base64 Excel string
    include_departments = serializers.BooleanField(required=False, default=True)



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
        uid = self.instance.uid if self.instance else None
        existing = Department.objects.filter(name=name, code=code, deleted_at=None)
        if existing.exclude(uid=uid).exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("this name and code already exists.")

        return data



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
    department = DepartmentSerializer(read_only=True)
    level = PositionalLevelSerializer(read_only=True)


class UserProfileSerializer(serializers.ModelSerializer):
    user_uid = serializers.UUIDField(write_only=True, required=False)
    user = UserSerializer(read_only=True)

    department_uid = serializers.UUIDField(write_only=True, required=True)
    department = DepartmentSerializer(read_only=True)

    level_uid = serializers.UUIDField(write_only=True, required=False, allow_null=True)
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
        fields = ['uid', 'user_uid', 'user', 'level', 'level_uid', 'department', 'department_uid', 'is_active',
                   'created_at', 'updated_at', 'end_date', 'description'
                  ]
        read_only_fields = ['uid', 'created_at', 'updated_at', 'end_date']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }

    def validate(self, data):
        user_uid = data.pop('user_uid', None)
        level_uid = data.pop('level_uid', None)
        department_uid = data.pop('department_uid', None)
        
        if not user_uid:
            raise serializers.ValidationError({"user_uid": "User UID is required"})
        
        if not department_uid:
            raise serializers.ValidationError({"department_uid": "Department UID is required"})

        try:
            data['user'] = User.objects.get(guid=user_uid, is_active=True, is_deleted=False)
        except Exception as e:
            raise serializers.ValidationError({"user_uid": "Unable Find User,May be Deleted or Disabled"})

        try:
            data['department'] = Department.objects.get(uid=department_uid, is_deleted=False)
        except Department.DoesNotExist:
            raise serializers.ValidationError({"department_uid": "Invalid Department, not found or deleted"})

        if level_uid:
            try:
                data['level'] = PositionalLevel.objects.get(uid=level_uid, is_deleted=False)
            except PositionalLevel.DoesNotExist:
                raise serializers.ValidationError({"level_uid": "Invalid Level, not found or deleted"})
        else:
            # If no level_uid provided, get the first active level as default
            default_level = PositionalLevel.objects.filter(is_active=True, is_deleted=False).first()
            if default_level:
                data['level'] = default_level
            else:
                raise serializers.ValidationError({"level_uid": "No active level available. Please provide a level or create one."})

        # Check if another user already has an active position with the same level and department
        user = data.get('user')
        level = data.get('level')
        department = data.get('department')
        
        if user and level and department:
            # Query for existing active positions with the same level and department
            existing_position = UserProfile.objects.filter(
                level=level,
                department=department,
                is_active=True,
                is_deleted=False
            )
            
            # If updating, exclude the current instance (allows updating the same position)
            if self.instance:
                existing_position = existing_position.exclude(uid=self.instance.uid)
            
            # Check if another user already has this position
            if existing_position.exists():
                raise serializers.ValidationError({
                    "position": "A user with the same position already exists."
                })

        return data


