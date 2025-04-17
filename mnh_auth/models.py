from django.db import models
import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager, PermissionsMixin, Permission


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_active') is not True:
            raise ValueError('Superuser must have have to be active')
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have to be staff')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have to be superuser')
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser, PermissionsMixin):
    ACCOUNT_TYPE_CHOICES = [
        ('ORGANIZATION', 'Organization'),
        ('COMPANY', 'Company'),
        ('INDIVIDUAL', 'Individual'),
    ]


    email = models.EmailField(max_length=255, unique=True)
    guid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    account_type = models.CharField( max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='individual')
    account_name = models.CharField(max_length=80, default='')
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=11, unique=False, default='0')
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.first_name + ' ' + self.last_name

    def get_short_name(self):
        return self.first_name

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    def get_groups(self):
        return []

    def get_group_names(self):
        """Returns a list of group names the user belongs to."""
        print(list(self.groups.values_list('name', flat=True)))
        return list(self.groups.values_list('name', flat=True))

    def get_permission_codes(self):
        """Returns a list of permission codes assigned to the user."""
        permissions = set(self.user_permissions.values_list('codename', flat=True))
        group_permissions = set(Permission.objects.filter(group__user=self).values_list('codename', flat=True))
        return list(permissions.union(group_permissions))

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.account_type = 'individual'
        super().save(*args, **kwargs)


    class Meta:
        db_table = 'auth_user'


class AccountSetup(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='account_setup')
    name = models.CharField(max_length=255)
    contact_person_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    user_address = models.TextField()
    post_address = models.TextField()
    account_type = models.CharField(
        max_length=20,
        choices=User.ACCOUNT_TYPE_CHOICES
    )

    class Meta:
        db_table = 'account_setup'

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()})"