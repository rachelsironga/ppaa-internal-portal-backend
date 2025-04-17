from django.contrib.auth import get_user_model
from django.db import models
import uuid
from polymorphic.models import PolymorphicModel


User = get_user_model()

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


class PolymorphicBaseModel(PolymorphicModel):
    id = models.BigAutoField(primary_key=True)
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateField(blank=True, null=True)
    updated_at = models.DateField(blank=True, null=True)
    deleted_at = models.DateField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, related_name='created_%(class)s', on_delete=models.SET_NULL, null=True,
                                   blank=True)
    updated_by = models.ForeignKey(User, related_name='updated_%(class)s', on_delete=models.SET_NULL, null=True,
                                   blank=True)
    deleted_by = models.ForeignKey(User, related_name='deleted_%(class)s', on_delete=models.SET_NULL, null=True,
                                   blank=True)

    class Meta:
        abstract = True


class Department(BaseModel):
    name = models.CharField(max_length=100, null=True)
    code = models.CharField(max_length=20, null=True)
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

class ApprovalLevel(BaseModel):
    """Defines different levels of approval (e.g., Supervisor, Manager, Director)"""
    name = models.CharField(max_length=100, null=True)
    code = models.CharField(max_length=20, null=True)
    is_active = models.BooleanField(default=True)


    class Meta:
        db_table = 'approval_levels'

    def __str__(self):
        return self.name

class ApprovalAction(BaseModel):
    """Defines predefined actions that can be taken at approval levels"""
    name = models.CharField(max_length=100)  # e.g., "Approve"
    code = models.CharField(max_length=20)  # e.g., "APPROVE"
    description = models.TextField(blank=True, null=True)  # Optional explanation
    is_active = models.BooleanField(default=True)


    class Meta:
        db_table = 'approval_actions'

    def __str__(self):
        return f"{self.name} ({self.code})"

class ApprovalModule(BaseModel):
    """Defines a module that requires approval processes"""
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'approval_modules'

    def __str__(self):
        return self.name

class ApprovalModuleLevel(BaseModel):
    """Links ApprovalModules to ApprovalLevels and defines required actions"""
    module = models.ForeignKey(ApprovalModule, on_delete=models.CASCADE)
    level = models.ForeignKey(ApprovalLevel, on_delete=models.CASCADE)
    action = models.ForeignKey(ApprovalAction, on_delete=models.CASCADE, related_name='approval_actions')
    order = models.PositiveIntegerField()
    is_signatory = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)


    class Meta:
        db_table = 'approval_module_levels'
        unique_together = ('module', 'level', 'action')
        ordering = ['order']

    def __str__(self):
        return f"{self.uid}"

class ApprovalRequest(PolymorphicBaseModel):
    title = models.CharField(max_length=255, default='')
    description = models.TextField(max_length=255, blank=True, null=True)
    module = models.ForeignKey(ApprovalModule, on_delete=models.RESTRICT, related_name='approval_module')
    department = models.ForeignKey(Department, models.DO_NOTHING, blank=True, null=True)
    requested_by = models.ForeignKey(User, on_delete=models.RESTRICT, blank=True, null=True, related_name="requested_by")
    status = models.CharField(max_length=50, default='pending', choices=[
        ('pending', 'PENDING'),
        ('approved', 'APPROVED'),
        ('rejected', 'REJECTED')
    ])
    class Meta:
        db_table = 'approval_requests'

    def __str__(self):
        return f"{self.module.name} - {self.status} - {self.created_at}"

class ApprovalRequestStep(BaseModel):
    approval_request = models.ForeignKey(ApprovalRequest, on_delete=models.CASCADE, related_name="steps")
    approval_module_level = models.ForeignKey(ApprovalModuleLevel, on_delete=models.CASCADE)  # ForeignKey, NOT OneToOneField
    approved_by = models.ForeignKey(User, on_delete=models.RESTRICT, null=True)
    is_acting = models.BooleanField(default=True, db_comment="if user is not the real signatory but acting one")
    comment = models.TextField(blank=True, null=True)
    class Meta:
        db_table = 'approval_request_steps'

# 🔹 Different Request Types (Each Inherits from ApprovalRequest)
class RequestInternetEmailAccess(ApprovalRequest):
    start_date: str = models.DateField(blank=True, null=True)
    end_date: str = models.DateField(blank=True, null=True)

    class Meta:
        db_table = 'request_internet_email_access'

    def __str__(self):
        return f"request_internet_email_access: {self.title} | {self.start_date} - {self.end_date}"

class RequestJeeverAccess(ApprovalRequest):
    start_date: str = models.DateField(blank=True, null=True)
    end_date: str = models.DateField(blank=True, null=True)
    access_data = models.JSONField()  # { "user":[], "revoke":[] }

    class Meta:
        db_table = 'request_jeever_access'

    def __str__(self):
        return f"request_jeever_access: {self.title} | {self.start_date} - {self.end_date}"


