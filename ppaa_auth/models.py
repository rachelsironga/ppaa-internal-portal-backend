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

    class Meta:
        abstract = True


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

    def __str__(self):
        return self.name

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
