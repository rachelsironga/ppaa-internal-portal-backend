from django.db import models
import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager, PermissionsMixin, Permission
from django.db.models import Q, F
from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not extra_fields.get('pf_number'):
            raise ValueError('Every New User Must have Valid Registered PF-Number')
        username = str(username).strip().lower()
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_active') is not True:
            raise ValueError('Superuser must have have to be active')
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have to be staff')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have to be superuser')
        return self.create_user(username, password, **extra_fields)


class User(AbstractUser, PermissionsMixin):
    ACCOUNT_STATUS_CHOICES = {
        ('NEW', 'New'),
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('RETIRED', 'Retired'),
    }

    ACCOUNT_TYPE_CHOICES = {
        ('TEMPORALLY', 'Temporally'),
        ('LONG_TERM', 'Long Term'),
        ('SUPER_USER', 'Super User'),
    }

    # User Columns
    guid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    email = models.EmailField(max_length=70, unique=True,  db_index=True)
    pf_number = models.CharField(max_length=50, unique=True, db_index=True)
    check_number = models.CharField(max_length=50, default=None, null=True)
    office_location = models.CharField(max_length=70, default=None, null=True, blank=True)
    first_name = models.CharField(max_length=80, null=False, blank=False)
    middle_name = models.CharField(max_length=80, null=True, blank=True)
    last_name = models.CharField(max_length=80, null=False, blank=False)
    status = models.CharField(max_length=20, choices=ACCOUNT_STATUS_CHOICES, default='ACTIVE')
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='LONG_TERM')
    dob = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=10, null=True, blank=True)
    # Other Personal Details
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    signature = models.TextField(max_length=200, null=True, blank=True)  # a file path
    photo = models.TextField(max_length=200, null=True, blank=True)  # a file path
    phone_number = models.TextField(max_length=15, null=True, blank=True)
    alternative_contact = models.TextField(max_length=15, null=True, blank=True)
    account_number = models.TextField(max_length=20, null=True, blank=True)
    # default Columns
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    updated_by = models.IntegerField(null=True, blank=True, default=1)
    created_by = models.IntegerField(null=True, blank=True, default=1)
    is_deleted = models.BooleanField(default=False)
    deleted_by = models.IntegerField(null=True, blank=True, default=1)

    objects = UserManager()
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['pf_number', 'first_name', 'last_name']

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    def get_full_name(self):
        return self.first_name + ' ' + self.middle_name + ' ' + self.last_name

    def get_short_name(self):
        return self.first_name

    def has_perm(self, perm, obj=None):
        """
        Checks if the user has the specified permission string.
        """
        if self.is_superuser:
            return True

        # Direct permissions
        if self.user_permissions.filter(codename=perm.split('.')[-1]).exists():
            return True

        # Permissions via groups
        if Permission.objects.filter(
                group__user=self,
                codename=perm.split('.')[-1]
        ).exists():
            return True

        return False

    def has_module_perms(self, app_label):
        """
        Returns True if the user has any permissions in the given app_label.
        """
        if self.is_superuser:
            return True

        # Check direct permissions
        if self.user_permissions.filter(content_type__app_label=app_label).exists():
            return True

        # Check group permissions
        if Permission.objects.filter(
                group__user=self,
                content_type__app_label=app_label
        ).exists():
            return True

        return False

    def get_groups(self):
        """
        Returns QuerySet of groups the user belongs to.
        """
        return self.groups.all()

    def get_group_names(self):
        """Returns a list of group names the user belongs to."""
        return list(self.groups.values_list('name', flat=True))

    def get_permission_codes(self):
        """Returns a list of permission codes assigned to the user."""
        permissions = set(self.user_permissions.values_list('codename', flat=True))
        group_permissions = set(Permission.objects.filter(group__user=self).values_list('codename', flat=True))
        return list(permissions.union(group_permissions))

    def get_position(self):
        active_position = UserProfile.objects.filter(
            is_active=True, is_deleted=False, user=self
        ).select_related('acting_user').values(
            department_uid=F("department__uid"),
            department_name=F("department__name"),
            department_code=F("department__code"),
            directory_uid=F("directory__uid"),
            directory_code=F("directory__code"),
            directory_name=F("directory__name"),
            level_uid=F("level__uid"),
            level_name=F("level__name"),
            level_code=F("level__code"),
            start_date=F("created_at"),
            last_date=F("end_date"),
            acting_user_uid=F("acting_user__guid"),
            acting_user_first_name=F("acting_user__first_name"),
            acting_user_middle_name=F("acting_user__middle_name"),
            acting_user_last_name=F("acting_user__last_name"),
            acting_user_email=F("acting_user__email"),
            acting_user_pf_number=F("acting_user__pf_number"),
            acting_user_updated_at=F("acting_user__updated_at"),
        ).first()
        if active_position:
            acting_first_name = active_position.pop("acting_user_first_name", "") or ""
            acting_last_name = active_position.pop("acting_user_last_name", "") or ""
            acting_middle_name = active_position.pop("acting_user_middle_name", "") or ""
            acting_user_uid = active_position.pop("acting_user_uid", "") or ""
            acting_email = active_position.pop("acting_user_email", "") or ""
            acting_pf_number = active_position.pop("acting_user_pf_number", "") or ""
            acting_created_at = active_position.pop("acting_user_updated_at", "") or ""

            if any([acting_first_name, acting_middle_name, acting_last_name, acting_user_uid, acting_email,
                    acting_pf_number,acting_created_at, ]):
                active_position["acting_user"] = {
                    "uid": acting_user_uid,
                    "name": f"{acting_first_name} {acting_middle_name} {acting_last_name}".strip(),
                    "email": acting_email,
                    "pf_number": acting_pf_number,
                    "created_at": acting_created_at
                }
            else:
                active_position["acting_user"] = None

        return active_position or None

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.account_type = 'SUPER_USER'
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'auth_user'


class BaseModel(models.Model):
    id = models.BigAutoField(primary_key=True)
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, related_name='created_%(class)s', on_delete=models.SET_NULL, null=True,
                                   blank=True)
    updated_by = models.ForeignKey(User, related_name='updated_%(class)s', on_delete=models.SET_NULL, null=True,
                                   blank=True)
    deleted_by = models.ForeignKey(User, related_name='deleted_%(class)s', on_delete=models.SET_NULL, null=True,
                                   blank=True)

    class Meta:
        abstract = True


class GroupProfile(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name="group_profile")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='group_created')
    updated_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='group_updated')
    update_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'auth_group_profile'

    def __str__(self):
        return self.group.name

class Directory(BaseModel):
    name = models.CharField(max_length=150, null=True)
    code = models.CharField(max_length=100, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'directories'
        ordering = ['name', 'code']
        verbose_name = "Directory"
        verbose_name_plural = "Directories"
        indexes = [
            models.Index(fields=['name', 'code']),
            models.Index(fields=['uid']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Department(BaseModel):
    name = models.CharField(max_length=150, null=True)
    code = models.CharField(max_length=100, null=True)
    directory = models.ForeignKey('Directory', on_delete=models.CASCADE, related_name='departments')

    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'departments'
        ordering = ['name']
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        indexes = [
            models.Index(fields=['name', 'code']),  # Optimized query performance
            models.Index(fields=['is_active']),  # Faster queries on active departments
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class PositionalLevel(BaseModel):
    """Defines different levels of approval (e.g., Supervisor, Manager, Director)"""
    name = models.CharField(max_length=200, null=True)
    code = models.CharField(max_length=200, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'positional_levels'

    def __str__(self):
        return self.name


class UserProfile(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, related_name='user_profiles', on_delete=models.SET_NULL, null=True, blank=True)
    level = models.ForeignKey(PositionalLevel, on_delete=models.CASCADE)
    directory = models.ForeignKey('Directory', on_delete=models.CASCADE, related_name='user_profiles')
    acting_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='acting_user')

    department = models.ForeignKey('Department', models.DO_NOTHING, blank=True, null=True, default=None)
    is_active = models.BooleanField(default=True, null=False, blank=False)
    end_date = models.DateTimeField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'user_profile'

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.level.code})"
