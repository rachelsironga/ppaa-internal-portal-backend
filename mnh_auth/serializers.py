from django.conf import settings
from django.contrib.auth.models import Permission, Group
from django.db.models import Q
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated

from .models import User, GroupProfile
from rest_framework import status
from rest_framework.serializers import ModelSerializer



class UserSerializer(serializers.ModelSerializer):
    groups = serializers.SerializerMethodField(read_only=True)
    user_permissions = serializers.SerializerMethodField(read_only=True)
    photo = serializers.SerializerMethodField()
    signature = serializers.SerializerMethodField()
    position = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'guid','username','email','pf_number','check_number','first_name', 'middle_name','last_name','status',
            'account_type','dob','sex','is_active','is_staff','photo','signature','phone_number','alternative_contact',
            'account_number','created_at','updated_at','created_by','groups', 'user_permissions','position'
        ]
        read_only_fields = [
            'guid', 'username', 'status', 'updated_at','account_type', 'created_at', 'updated_at',
        ]

    def get_groups(self, obj):
        is_auth_view = self.context.get("is_auth_view", True)
        return obj.get_group_names() if is_auth_view else []

    def get_user_permissions(self, obj):
        is_auth_view = self.context.get("is_auth_view", True)
        return obj.get_permission_codes() if is_auth_view else []

    def get_position(self, obj):
        is_auth_view = self.context.get("is_auth_view", True)
        return obj.get_position() if is_auth_view else None

    def get_photo(self, obj):
        if obj.photo:
            # Ensure MEDIA_URL ends with /
            base_url = settings.MEDIA_URL if settings.MEDIA_URL.endswith('/') else settings.MEDIA_URL + '/'
            return f"{base_url}{obj.photo}"
        return None

    def get_signature(self, obj):
        if obj.photo:
            # Ensure MEDIA_URL ends with /
            base_url = settings.MEDIA_URL if settings.MEDIA_URL.endswith('/') else settings.MEDIA_URL + '/'
            return f"{base_url}{obj.signature}"
        return None

    def create(self, validated_data):
        validated_data['username'] = validated_data.get('pf_number')
        return super().create(validated_data)

class ActingUserSerializer(serializers.Serializer):
    delegated_user = serializers.UUIDField(
        write_only=True,
        required=True,
    )

class AssignUserRoleSerializer(serializers.Serializer):
    permitted_user = serializers.CharField(
        write_only=True,
        required=True,
    )
    selected_role = serializers.CharField(
        write_only=True,
        required=True,
    )

    def validate(self, data):
        permitted_user = data.pop('permitted_user')
        selected_role = data.pop('selected_role')

        data['user'] =User.objects.filter(guid=permitted_user,is_deleted=False).first()
        if not data['user']:
                raise serializers.ValidationError("The user not be verified may be or deleted")

        data['role'] =Group.objects.filter(id=int(selected_role)).first()
        if not data['role']:
                raise serializers.ValidationError("The role not be verified may be or deleted")

        if data['user'] in data['role'].user_set.all():
                raise serializers.ValidationError("The user already have the role")

        return data

    def create(self, validated_data):
        user = self.validated_data['user']
        role = self.validated_data['role']
        user.groups.add(role)
        user.save()
        return user

    def update(self, instance, validated_data):
        user = self.validated_data['user']
        role = self.validated_data['role']
        user.groups.remove(role)
        user.save()
        return user

    def delete(self, instance):
        user = self.validated_data['user']
        role = self.validated_data['role']
        user.groups.remove(role)
        user.save()
        return user


class GroupSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    users = serializers.SerializerMethodField()
    last_update_at = serializers.SerializerMethodField()
    update_count = serializers.SerializerMethodField()
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            "id", "name","permissions", "users", "last_update_at", "last_updated_by", "update_count",
        ]
        read_only_fields = ["id", "users","last_update_at", "last_updated_by", "update_count",]

    def get_permissions(self, obj):
        # List all permissions assigned to the group
        return list(obj.permissions.values('id', 'name', 'codename'))

    def get_users(self, obj):
        return obj.user_set.count()

    def get_last_update_at(self, obj):
        return (
            obj.group_profile.updated_at.strftime("%Y-%m-%d")
            if hasattr(obj, "group_profile") and obj.group_profile.updated_at
            else None
        )

    def get_update_count(self, obj):
        return obj.group_profile.update_count if hasattr(obj, "group_profile") else 0

    def get_last_updated_by(self, obj):
        return f'{obj.group_profile.updated_by.first_name} {obj.group_profile.updated_by.last_name}' if hasattr(obj, "group_profile") and obj.group_profile.updated_by else None

    def create(self, validated_data):
        user = self.context['request'].user
        group = Group.objects.create(**validated_data)

        GroupProfile.objects.create(
            group=group,
            created_by=user,
            updated_by=user,
            update_count=1
        )
        return group

    def update(self, instance, validated_data):
        user = self.context['request'].user
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update GroupProfile
        group_profile, _ = GroupProfile.objects.get_or_create(group=instance)
        group_profile.update_count += 1
        group_profile.updated_by = user
        group_profile.save()

        return instance


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'content_type']
        depth = 1



class FileUploadSerializer(serializers.Serializer):
    uid = serializers.UUIDField(write_only=True, required=True)
    based64_file = serializers.CharField(
        required=True,
        error_messages={
             'blank': 'You must provide a  File',
             'required': 'Uploaded File is required.',
        }
    )

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'username is required',
            'blank': 'username is required'
        }
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'password is required',
            'blank': 'password is required'
        }
    )


class CheckUserNameSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True, max_length=100)
    class Meta:
        model = User
        fields = '__all__'
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'password': {'required': False},
            'email': {'required': False}
        }




class RegistrationSerializer(serializers.ModelSerializer):
    groups = serializers.SerializerMethodField()
    user_permissions = serializers.SerializerMethodField()

    class Meta:
        username = None
        model = User
        # fields = ['first_name', 'last_name', 'email','phone_number','password']
        fields = '__all__'
        extra_kwargs = {
            'first_name': {
                'required': True,
                'error_messages': {
                    'blank': 'First name can not be empty.',
                    'required': 'First name is required.',
                }
            },
            'username': {
                'required': False
            },
            'last_name': {
                'required': True,
                'error_messages': {
                    'blank': 'Last name can not be empty.',
                    'required': 'Last name is required.',
                }
            },
            'phone_number': {
                'required': True,
                'error_messages': {
                    'required': 'Phone number is required',
                    'blank': 'Phone number is required.',
                }
            },
            'password': {
                'required': False,
                'write_only': True,
                'error_messages': {
                    'required': 'Password Field is required',
                    'blank': 'Password cannot be blank.',
                }
            },
            'email': {
                'required': True,
                'error_messages': {
                    'required': 'Email address is required.',
                    'blank': 'Email address cannot be blank.',
                }
            },
            'account_type': {
                'required': True,
                'error_messages': {
                    'required': 'Account Type is required.',
                    'blank': 'Account Type cannot be blank.',
                }
            },
        }

    def save(self):
        user = User(
            first_name=self.validated_data['first_name'],
            last_name=self.validated_data['last_name'],
            username=self.validated_data['email'],
            is_active=True,
            email=self.validated_data['email'],
            phone_number=self.validated_data['phone_number'],
        )
        password = self.validated_data['password']
        user.set_password(password)
        user.save()

        # Assign role-based permissions
        self.assign_role_permissions(user)

        return user

    def save_staff(self):
        user = User(
                      first_name=self.validated_data['first_name'],
                      email=self.validated_data['email'],
                      phone_number=self.validated_data['phone_number'],
                      last_name=self.validated_data['last_name'],
                      is_admin=self.validated_data['is_admin'],
        )
        password = self.validated_data['password']
        password2 = self.validated_data['password2']
        if password != password2:
            raise serializers.ValidationError(
                {'status': status.HTTP_400_BAD_REQUEST, 'message': 'Passwords must match.'})
        user.set_password(password)
        user.save()
        return user

    def assign_role_permissions(self, user):
        """Assign permissions based on the user's role"""
        if user.is_superuser:
            admin_group, created = Group.objects.get_or_create(name='admin')
            user.groups.add(admin_group)
            # Assign all permissions if admin
            permissions = Permission.objects.all()
            user.user_permissions.set(permissions)

        elif user.is_staff == 'staff':
            staff_group, created = Group.objects.get_or_create(name='admin')
            user.groups.add(staff_group)
            # Assign limited permissions for staff
            staff_permissions = Permission.objects.filter(codename__in=['view_user', 'change_user'])
            user.user_permissions.set(staff_permissions)

        else:  # Regular user
            user_group, created = Group.objects.get_or_create(name='contributer')
            user.groups.add(user_group)
            # Assign view-only permissions
            user_permissions = Permission.objects.filter(codename__in=['view_user'])
            user.user_permissions.set(user_permissions)

        user.save()



class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(style={"input_type": "password"}, required=True)
    new_password = serializers.CharField(style={"input_type": "password"}, required=True)

    def validate_current_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError(
                {'status': status.HTTP_400_BAD_REQUEST, 'message': 'Password Does not match'})
        return value


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'email', 'photo', 'signature', 'phone_number',
            'alternative_contact', 'account_number', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = { }


class UserIdentitySerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'guid']


class UserImportSerializer(serializers.Serializer):
    file = serializers.CharField(required=True)

class DesignationImportSerializer(serializers.Serializer):
    file = serializers.CharField(required=True)

