from django.conf import settings
from django.contrib.auth.models import Permission, Group
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated

from ppaa_portal.services.minio.minio_helpers import get_presigned_url
from .models import User, GroupProfile, Department
from rest_framework import status
from rest_framework.serializers import ModelSerializer


class UserSerializer(serializers.ModelSerializer):
    user_guid = serializers.CharField(write_only=True, required=False)
    groups = serializers.SerializerMethodField(read_only=True)
    user_permissions = serializers.SerializerMethodField(read_only=True)
    photo = serializers.SerializerMethodField()
    position = serializers.SerializerMethodField(read_only=True)
    email = serializers.CharField(required=False, allow_blank=False)
    current_department_name = serializers.SerializerMethodField(read_only=True)
    current_level_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'guid', 'user_guid','username', 'email', 'check_number', 'first_name',
            'middle_name', 'last_name', 'status', 'account_type', 'dob', 'sex', 'is_active', 'is_staff', 'photo',
            'phone_number', 'alternative_contact', 'created_at', 'updated_at',
            'created_by','updated_by', 'groups', 'user_permissions', 'position', 'current_level_name',
            'current_department_name'
        ]
        read_only_fields = [
            'id', 'guid', 'username', 'status', 'updated_at', 'account_type', 'created_at', 'updated_at',
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
            # Assuming obj.photo holds the path/key in the bucket
            return get_presigned_url(str(obj.photo))
        return None

    def get_current_level_name(self, obj):
        """Get current level name from position or annotation"""
        # Check if annotation exists (from queryset annotation)
        if hasattr(obj, 'current_level_name'):
            return obj.current_level_name
        # Otherwise get from position
        position = obj.get_position() if hasattr(obj, 'get_position') else None
        return position.get('level_name') if position else None

    def get_current_department_name(self, obj):
        """Get current department name from position or annotation"""
        # Check if annotation exists (from queryset annotation)
        if hasattr(obj, 'current_department_name'):
            return obj.current_department_name
        # Otherwise get from position
        position = obj.get_position() if hasattr(obj, 'get_position') else None
        return position.get('department_name') if position else None


    def validate(self, attrs):
        instance = self.instance

        if 'user_guid' not in attrs:
            attrs['status'] = "NEW"
            #create username
            attrs['username'] = f"{attrs['first_name'].lower()}.{attrs['last_name'].lower()}"
            users = User.objects.filter(username=attrs["username"])
            if users:
                attrs['username'] = f"{attrs['username']}.{users.count()}"

        # Check email unique
        if "email" in attrs:
            qs = User.objects.filter(email=attrs["email"])
            if instance:
                qs = qs.exclude(id=instance.id)
            if qs.exists():
                raise serializers.ValidationError({"email": "Email already exists."})

        # Check phone number unique
        if "phone_number" in attrs:
            qs = User.objects.filter(phone_number=attrs["phone_number"])
            if instance:
                qs = qs.exclude(id=instance.id)
            if qs.exists():
                raise serializers.ValidationError({"phone_number": "Phone number already exists."})

        return attrs


    def create(self, validated_data):
        return User.objects.create(**validated_data)

    def update(self, instance, validated_data):
        # Use the instance passed from the view; only remove user_guid so it isn't written to the model
        validated_data.pop("user_guid", None)
        return super().update(instance, validated_data)


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

        data['user'] = User.objects.filter(guid=permitted_user, is_deleted=False).first()
        if not data['user']:
            raise serializers.ValidationError("The user not be verified may be or deleted")

        data['role'] = Group.objects.filter(id=int(selected_role)).first()
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


class AssignUserRolesListSerializer(serializers.Serializer):
    permitted_user = serializers.CharField(
        write_only=True,
        required=True,
    )
    selected_roles = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=True,
    )

    def validate(self, data):
        permitted_user = data.pop("permitted_user")
        selected_roles = data.pop("selected_roles")

        # validate user
        user = User.objects.filter(guid=permitted_user, is_deleted=False).first()
        if not user:
            raise serializers.ValidationError("The user could not be verified or may be deleted")

        # validate roles
        selected_roles = [int(role) for role in selected_roles]
        roles = Group.objects.filter(id__in=selected_roles)
        if not roles.exists():
            raise serializers.ValidationError("No valid roles found for given IDs")

        # check missing roles (invalid IDs)
        invalid_roles = set(selected_roles) - set(roles.values_list("id", flat=True))
        if invalid_roles:
            raise serializers.ValidationError(f"Invalid role IDs: {list(invalid_roles)}")

        data["user"] = user
        data["roles"] = roles
        return data

    def create(self, validated_data):
        user = validated_data["user"]
        roles = validated_data["roles"]

        # Replace all user roles with the new list (this removes roles not in the list)
        # This ensures that when roles are removed from the UI, they are also removed from the database
        user.groups.set(roles)
        user.save()
        return user

    def update(self, instance, validated_data):
        user = validated_data["user"]
        roles = validated_data["roles"]

        # replace user roles with new ones
        user.groups.set(roles)
        user.save()
        return user

    def delete(self, instance):
        user = self.validated_data["user"]
        roles = self.validated_data["roles"]

        for role in roles:
            if role in user.groups.all():
                user.groups.remove(role)

        user.save()
        return user


class GroupListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'name']
        depth = 1


class GroupSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    users = serializers.SerializerMethodField()
    last_update_at = serializers.SerializerMethodField()
    update_count = serializers.SerializerMethodField()
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            "id", "name", "permissions", "users", "last_update_at", "last_updated_by", "update_count",
        ]
        read_only_fields = ["id", "users", "last_update_at", "last_updated_by", "update_count", ]

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
        return f'{obj.group_profile.updated_by.first_name} {obj.group_profile.updated_by.last_name}' if hasattr(obj,
                                                                                                                "group_profile") and obj.group_profile.updated_by else None

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


class NewUserLoginSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True, allow_blank=False, write_only=True)
    password = serializers.CharField(required=True, allow_blank=False, write_only=True)
    email = serializers.CharField(required=True, allow_blank=False, write_only=True)

    class Meta:
        model = User
        fields = [
            "username", "password", "phone_number", "email",
        ]

    def validate(self, data):
        permitted_user = data.pop('username')
        email = data.get('email')

        data['user'] = User.objects.filter(username=permitted_user, is_deleted=False).first()
        if not data['user']:
            raise serializers.ValidationError("The user is not verified or may be removed")

        if User.objects.filter(email=email, is_deleted=False).exclude(guid=data['user'].guid).first():
            raise serializers.ValidationError("The email Already Exists")

        return data

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['password'])
        user.status = 'ACTIVE'
        user_group = Group.objects.filter(name='staff').first()
        if user_group:
            user.groups.add(user_group)

        user.save()

        return user


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
    check_number = serializers.CharField(required=False, )

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
        account_type = self.validated_data.get('account_type', 'LONG_TERM')
        
        # If account_type is SUPER_USER, set is_superuser and is_staff to True
        is_superuser = (account_type == 'SUPER_USER')
        
        user = User(
            first_name=self.validated_data['first_name'],
            last_name=self.validated_data['last_name'],
            username=self.validated_data['email'],
            is_active=True,
            email=self.validated_data['email'],
            phone_number=self.validated_data['phone_number'],
            account_type=account_type,
            is_superuser=is_superuser,
            is_staff=is_superuser,  # Superusers should also be staff
        )
        password = f"{str(self.validated_data['first_name']).upper()}@{self.validated_data['last_name']}"
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
        # Check if user is superuser OR has SUPER_USER account type
        if user.is_superuser or user.account_type == 'SUPER_USER':
            # Set is_superuser and is_staff if account_type is SUPER_USER
            if user.account_type == 'SUPER_USER' and not user.is_superuser:
                user.is_superuser = True
                user.is_staff = True
                user.save()
            
            # Assign admin group
            admin_group, created = Group.objects.get_or_create(name='admin')
            if not user.groups.filter(id=admin_group.id).exists():
                user.groups.add(admin_group)
            
            # Also add Admin group (capitalized) if it exists
            admin_group_capital, created = Group.objects.get_or_create(name='Admin')
            if not user.groups.filter(id=admin_group_capital.id).exists():
                user.groups.add(admin_group_capital)
            
            # Assign all permissions if superuser
            permissions = Permission.objects.all()
            user.user_permissions.set(permissions)

        elif user.is_staff == 'staff':
            staff_group, created = Group.objects.get_or_create(name='admin')
            user.groups.add(staff_group)
            # Assign limited permissions for staff
            staff_permissions = Permission.objects.filter(codename__in=['view_user', 'change_user'])
            user.user_permissions.set(staff_permissions)

        else:  # Regular user
            user_group, created = Group.objects.get_or_create(name='staff')
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

class PasswordNewChangeSerializer(serializers.Serializer):
    uid = serializers.UUIDField(write_only=True, required=True)
    new_password = serializers.CharField(style={"input_type": "password"}, required=True)
    confirm_password = serializers.CharField(style={"input_type": "password"}, required=True)

    def validate(self, data):
        uid = data.pop('uid')
        try:
            data['user'] = User.objects.get(guid=uid)
        except User.DoesNotExist:
            raise serializers.ValidationError("User Does not exist")

        confirm_password = data.pop('confirm_password')
        new_password = data.pop('new_password')
        if confirm_password != new_password:
            raise serializers.ValidationError("Passwords do not match")
        data['new_password'] = new_password
        return data


class PasswordResetSerializer(serializers.Serializer):
    user_guid = serializers.CharField(
        write_only=True,
        required=True,
    )

    def validate(self, data):
        user_guid = data.pop('user_guid')
        data['user'] = User.objects.filter(guid=user_guid, is_deleted=False).first()
        if not data['user']:
            raise serializers.ValidationError("The user not be verified may be or deleted")
        return data


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """Check if user with this email exists"""
        user = User.objects.filter(email=value, is_deleted=False).first()
        if not user:
            raise serializers.ValidationError("No account found with this email address.")
        return value


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'email', 'photo', 'phone_number',
            'alternative_contact', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {}


class UserIdentitySerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'guid']


class UserImportSerializer(serializers.Serializer):
    file = serializers.CharField(required=True)


class DesignationImportSerializer(serializers.Serializer):
    file = serializers.CharField(required=True)


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['uid', 'name', 'code', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at']
