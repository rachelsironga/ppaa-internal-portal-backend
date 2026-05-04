<<<<<<< HEAD
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group
from django.core.validators import RegexValidator
from django.db import DatabaseError, models
from django.utils.text import slugify


class BaseModel(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_deleted",
    )
=======
from django.db import models
from django.core.validators import RegexValidator, FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.utils.text import slugify
import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager, PermissionsMixin, Permission
from django.db.models import Q, F
from django.contrib.auth.models import Group
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.utils import OperationalError, ProgrammingError


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not extra_fields.get('email'):
            raise ValueError('Every New User Must have Valid Email Address')
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
    check_number = models.CharField(max_length=50, default="****", null=True)
    office_location = models.CharField(max_length=70, default=None, null=True, blank=True)
    first_name = models.CharField(max_length=80, null=False, blank=False)
    middle_name = models.CharField(max_length=80, null=True, blank=True, default=" ")
    last_name = models.CharField(max_length=80, null=False, blank=False)
    status = models.CharField(max_length=20, choices=ACCOUNT_STATUS_CHOICES, default='ACTIVE')
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='NEW')
    dob = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=10, null=True, blank=True)
    # Other Personal Details
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    photo = models.TextField(max_length=200, null=True, blank=True)  # a file path
    phone_number = models.TextField(max_length=15, null=True, blank=True)
    alternative_contact = models.TextField(max_length=15, null=True, blank=True)
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
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    def get_full_name(self):
        return " ".join(filter(None, [
            self.first_name,
            self.middle_name,
            self.last_name
        ]))


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
            acting_user_updated_at=F("acting_user__updated_at"),
        ).first()
        if active_position:
            acting_first_name = active_position.pop("acting_user_first_name", "") or ""
            acting_last_name = active_position.pop("acting_user_last_name", "") or ""
            acting_middle_name = active_position.pop("acting_user_middle_name", "") or ""
            acting_user_uid = active_position.pop("acting_user_uid", "") or ""
            acting_email = active_position.pop("acting_user_email", "") or ""
            acting_created_at = active_position.pop("acting_user_updated_at", "") or ""

            if any([acting_first_name, acting_middle_name, acting_last_name, acting_user_uid, acting_email,
                    acting_created_at, ]):
                active_position["acting_user"] = {
                    "uid": acting_user_uid,
                    "name": f"{acting_first_name} {acting_middle_name} {acting_last_name}".strip(),
                    "email": acting_email,
                    "created_at": acting_created_at
                }
            else:
                active_position["acting_user"] = None

        return active_position or None

    def save(self, *args, **kwargs):
        # If account_type is SUPER_USER, ensure is_superuser and is_staff are True
        if self.account_type == 'SUPER_USER':
            self.is_superuser = True
            self.is_staff = True
        # If is_superuser is True, ensure account_type is SUPER_USER
        elif self.is_superuser:
            self.account_type = 'SUPER_USER'
        
        # Ensure email is set
        if not self.email:
            self.email = f"{self.username}@gmail.com" if self.username else None
        
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
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, related_name='created_%(class)s', 
                                   on_delete=models.SET_NULL, null=True,
                                   blank=True)
    updated_by = models.ForeignKey(User, related_name='updated_%(class)s', on_delete=models.SET_NULL, null=True,
                                   blank=True)
    deleted_by = models.ForeignKey(User, related_name='deleted_%(class)s', on_delete=models.SET_NULL, null=True,
                                   blank=True)
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92

    class Meta:
        abstract = True


<<<<<<< HEAD
class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, email=None, password=None, **extra_fields):
        if not email:
            raise ValueError("Every New User Must have Valid Email Address")
        email = self.normalize_email((email or "").strip().lower())
        username = (username or "").strip()
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have to be staff")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have to be superuser")
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    class AccountStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        NEW = "NEW", "New"
        RETIRED = "RETIRED", "Retired"
        SUSPENDED = "SUSPENDED", "Suspended"
        LONG_TERM = "LONG_TERM", "Long Term"

    class AccountType(models.TextChoices):
        SUPER_USER = "SUPER_USER", "Super User"
        TEMPORALLY = "TEMPORALLY", "Temporally"
        INDIVIDUAL = "individual", "Individual"

    guid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    middle_name = models.CharField(max_length=150, blank=True)
    check_number = models.CharField(max_length=100, blank=True)
    office_location = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=32,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
    )
    account_type = models.CharField(
        max_length=32,
        choices=AccountType.choices,
        default=AccountType.INDIVIDUAL,
    )
    dob = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=20, blank=True)
    photo = models.CharField(max_length=512, blank=True)
    signature = models.CharField(max_length=512, blank=True)
    phone_number = models.CharField(max_length=64, blank=True)
    alternative_contact = models.CharField(max_length=64, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users_created",
        db_column="created_by",
    )
    updated_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users_updated",
        db_column="updated_by",
    )
    deleted_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users_deleted",
        db_column="deleted_by",
    )

    objects = UserManager()

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "auth_user"

    def __str__(self):
        return self.username or str(self.guid)

    def get_groups(self):
        return [g.name.lower() for g in self.groups.all()]

    def get_group_names(self):
        return list(self.groups.values_list("name", flat=True))

    def get_permission_codes(self):
        from django.contrib.auth.models import Permission

        if self.is_superuser:
            return list(Permission.objects.values_list("codename", flat=True))
        user_perm = self.user_permissions.values_list("codename", flat=True)
        group_perm = Permission.objects.filter(group__user=self).values_list(
            "codename", flat=True
        )
        return list(set(user_perm).union(group_perm))

    def get_position(self):
        cache_attr = "_ppaa_position_cache"
        if hasattr(self, cache_attr):
            return getattr(self, cache_attr)
        try:
            profile = (
                self.user_profiles.filter(is_active=True, is_deleted=False)
                .select_related("level", "department", "acting_user")
                .order_by("-updated_at")
                .first()
            )
            if not profile:
                out = {}
            else:
                out = {}
                if profile.department_id:
                    d = profile.department
                    out["department_uid"] = str(d.uid)
                    out["department_name"] = d.name
                    out["department_code"] = d.code
                if profile.level_id:
                    lv = profile.level
                    out["level_uid"] = str(lv.uid)
                    out["level_name"] = lv.name
                    out["level_code"] = lv.code
                if profile.end_date:
                    out["end_date"] = profile.end_date
                if profile.acting_user_id:
                    a = profile.acting_user
                    out["acting_user_uid"] = str(a.guid)
                    out["acting_user_first_name"] = a.first_name
                    out["acting_user_middle_name"] = a.middle_name
                    out["acting_user_last_name"] = a.last_name
                    out["acting_user_email"] = a.email
                    out["acting_user_updated_at"] = a.updated_at
        except DatabaseError:
            out = {}
        setattr(self, cache_attr, out)
        return out

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.__class__.objects.normalize_email(self.email.strip())
        super().save(*args, **kwargs)


class Directory(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="directories_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="directories_updated",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="directories_deleted",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Department(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departments_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departments_updated",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departments_deleted",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PositionalLevel(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="positional_levels_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="positional_levels_updated",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="positional_levels_deleted",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_profiles",
    )
    level = models.ForeignKey(
        PositionalLevel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    acting_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acting_user_profiles",
    )
    is_active = models.BooleanField(default=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_profiles_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_profiles_updated",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_profiles_deleted",
    )

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user_id}:{self.uid}"


class Country(BaseModel):
    name = models.CharField(
        max_length=255,
        validators=[
            RegexValidator(
                regex=r"^[a-zA-Z\s\-]+$",
                message="Country name can only contain letters, spaces and hyphens",
            )
        ],
    )
    code = models.CharField(max_length=32, blank=True)
    iso_code = models.CharField(
        max_length=2,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{2}$",
                message="ISO code must be 2 uppercase letters",
            )
        ],
    )
    slug = models.SlugField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "countries"
        verbose_name_plural = "Countries"
        ordering = ["name"]
        indexes = [models.Index(fields=["name"])]
=======
class Currency(BaseModel):
    name = models.CharField(max_length=20, unique=True)
    code = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the project was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Timestamp when the project was last updated.")
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}"
    
    class Meta:
        db_table = 'currencies'
        verbose_name = "Currency"
        verbose_name_plural = "Currencies"  


class Country(BaseModel):
    """Country model without internationalization"""
    
    name = models.CharField(
        max_length=100,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z\s\-]+$',
                message='Country name can only contain letters, spaces and hyphens'
            )
        ]
    )
    
    iso_code = models.CharField(
        max_length=2,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r'^[A-Z]{2}$',
                message='ISO code must be 2 uppercase letters'
            )
        ],
        verbose_name="ISO Alpha-2 Code"
    )
    
    latitude = models.FloatField(
        blank=True,
        null=True,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90)
        ]
    )
    
    longitude = models.FloatField(
        blank=True,
        null=True,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180)
        ]
    )
    
    description = models.TextField(blank=True, null=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    
    # Timestamps and soft delete fields (if using BaseModel)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def clean(self):
        if self.name:
            self.name = self.name.strip().title()
        super().clean()
    
    class Meta:
        verbose_name_plural = "Countries"
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_deleted']),
        ]


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

class Department(BaseModel):
    name = models.CharField(max_length=150, null=True)
    code = models.CharField(max_length=100, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'departments'
        ordering = ['name', 'code']
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        indexes = [
            models.Index(fields=['name', 'code']),
            models.Index(fields=['uid']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class PositionalLevel(BaseModel):
    """Defines user positions/designations (e.g., Executive Secretary, HEAD OF ICT, Supervisor, Manager, Director)"""
    name = models.CharField(max_length=200, null=True, help_text="Position/Designation name (e.g., Executive Secretary, HEAD OF ICT)")
    code = models.CharField(max_length=200, null=True, help_text="Position/Designation code (optional)")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'positional_levels'
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92

    def __str__(self):
        return self.name

<<<<<<< HEAD
    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            self.slug = slugify(self.name)[:255]
        super().save(*args, **kwargs)


class Currency(BaseModel):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=16)

    class Meta:
        db_table = "currencies"
        verbose_name = "Currency"
        verbose_name_plural = "Currencies"
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class GroupProfile(models.Model):
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name="group_profile",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    update_count = models.PositiveIntegerField(default=0)
    last_updated_at = models.DateTimeField(null=True, blank=True)
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="group_profiles_updated",
    )

    class Meta:
        db_table = "auth_group_profile"

    def __str__(self):
        return f"Profile<{self.group_id}>"
=======

class UserProfile(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, related_name='user_profiles', on_delete=models.SET_NULL, null=True, blank=True)
    level = models.ForeignKey(PositionalLevel, on_delete=models.CASCADE)
    acting_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='acting_user')

    department = models.ForeignKey('Department', on_delete=models.CASCADE, related_name='user_profiles')
    is_active = models.BooleanField(default=True, null=False, blank=False)
    end_date = models.DateTimeField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'user_profile'

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.level.code})"


def _sync_user_to_reports_db(instance):
    """
    Mirror auth_user rows into the ppaa_reports DB so RMS FK constraints remain valid.
    """
    field_names = [
        field.attname
        for field in instance._meta.concrete_fields
        if not field.primary_key
    ]
    defaults = {name: getattr(instance, name) for name in field_names}
    User.objects.using("ppaa_reports").update_or_create(
        id=instance.id,
        defaults=defaults,
    )


def _sync_department_to_reports_db(instance):
    """
    Mirror departments rows into the ppaa_reports DB so RMS FK constraints remain valid.
    """
    field_names = [
        field.attname
        for field in instance._meta.concrete_fields
        if not field.primary_key
    ]
    defaults = {name: getattr(instance, name) for name in field_names}
    Department.objects.using("ppaa_reports").update_or_create(
        id=instance.id,
        defaults=defaults,
    )


@receiver(post_save, sender=User)
def sync_user_to_reports_db(sender, instance, raw=False, using=None, **kwargs):
    if raw or using == "ppaa_reports":
        return
    try:
        _sync_user_to_reports_db(instance)
    except (OperationalError, ProgrammingError):
        # RMS DB or auth tables may not be ready yet during early setup/migrations.
        return


@receiver(post_delete, sender=User)
def delete_user_from_reports_db(sender, instance, using=None, **kwargs):
    if using == "ppaa_reports":
        return
    try:
        User.objects.using("ppaa_reports").filter(id=instance.id).delete()
    except (OperationalError, ProgrammingError):
        return


@receiver(post_save, sender=Department)
def sync_department_to_reports_db(sender, instance, raw=False, using=None, **kwargs):
    if raw or using == "ppaa_reports":
        return
    try:
        _sync_department_to_reports_db(instance)
    except (OperationalError, ProgrammingError):
        return


@receiver(post_delete, sender=Department)
def delete_department_from_reports_db(sender, instance, using=None, **kwargs):
    if using == "ppaa_reports":
        return
    try:
        Department.objects.using("ppaa_reports").filter(id=instance.id).delete()
    except (OperationalError, ProgrammingError):
        return
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
