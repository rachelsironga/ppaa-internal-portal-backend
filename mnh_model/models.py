from django.contrib.auth import get_user_model
from django.db import models

from mnh_auth.models import PositionalLevel, Directory, Department, BaseModel

User = get_user_model()


class ApprovalAction(BaseModel):
    """Defines predefined actions that can be taken at Positional Levels"""
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
    level = models.ForeignKey(PositionalLevel, on_delete=models.CASCADE)
    action = models.ForeignKey(ApprovalAction, on_delete=models.CASCADE, related_name='approval_actions')
    department = models.ForeignKey('mnh_auth.Department', models.DO_NOTHING, related_name='departments')
    order = models.PositiveIntegerField()
    is_signatory = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)


    class Meta:
        db_table = 'approval_module_levels'
        unique_together = ('module', 'level', 'action')
        ordering = ['order']

    def __str__(self):
        return f"{self.uid}"

class ApprovalRequest(BaseModel):
    REQUEST_TYPES = [
        ('JEEVA_ACCESS', 'JEEVA Access Request'),
        ('INTERNET_EMAIL_ACCESS', 'Internet Email Access Request'),
        ('EDMS_ACCESS', 'EDMS Access Request'),
    ]
    REQUEST_CHOICES = [
        ('NEW', 'NEW'),
        ('PENDING', 'PENDING'),
        ('APPROVED', 'APPROVED'),
        ('REJECTED', 'REJECTED')
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(max_length=255, blank=True, null=True)
    module = models.ForeignKey(ApprovalModule, on_delete=models.RESTRICT, related_name='approval_module')
    department = models.ForeignKey('mnh_auth.Department', models.DO_NOTHING, blank=True, null=True)
    type = models.CharField(max_length=50, choices=REQUEST_TYPES, default='N/A')
    status = models.CharField(max_length=15, default='NEW', choices=REQUEST_CHOICES)

    class Meta:
        db_table = 'approval_requests'

    def __str__(self):
        return f"{self.title} - {self.module.name} - {self.created_at}"

class ApprovalRequestStep(BaseModel):
    approval_request = models.ForeignKey(ApprovalRequest, on_delete=models.CASCADE, related_name="steps")
    approval_module_level = models.ForeignKey(ApprovalModuleLevel, on_delete=models.CASCADE)  # ForeignKey, NOT OneToOneField
    approved_by = models.ForeignKey(User, on_delete=models.RESTRICT, null=True)
    is_acting = models.BooleanField(default=True, db_comment="if user is not the real signatory but acting one")
    comment = models.TextField(blank=True, null=True)
    class Meta:
        db_table = 'approval_request_steps'

class RequestInternetEmailAccess(BaseModel):
    approval_request = models.OneToOneField(
        ApprovalRequest,unique=True, on_delete=models.CASCADE, related_name="internet_email_access"
    )
    start_date: str = models.DateTimeField(blank=True, null=True)
    end_date: str = models.DateTimeField(blank=True, null=True)
    is_read_term = models.BooleanField(default=False)
    purpose = models.JSONField(blank=True, null=True)
    class Meta:
        db_table = 'request_internet_email_access'

    def __str__(self):
        return f"{self.created_at}"

class RequestJeevaAccess(BaseModel):
    approval_request = models.OneToOneField(
        ApprovalRequest,unique=True, on_delete=models.CASCADE, related_name="jeeva_access"
    )
    access_data = models.JSONField()
    start_date: str = models.DateTimeField(blank=True, null=True)
    end_date: str = models.DateTimeField(blank=True, null=True)
    class Meta:
        db_table = 'request_jeeva_access'

    def __str__(self):
        return f"{self.created_at}"


class JeevaRole(BaseModel):
    """Defines a jeeva roles"""
    name = models.CharField(max_length=255, unique=True)
    code = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'jeeva_roles'
        unique_together = ('name', 'code')
        ordering = ['name']

    def __str__(self):
        return self.uid

class JeevaPermission(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    code = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)


    class Meta:
        db_table = 'jeeva_permissions'
        unique_together = ('name', 'code')
        ordering = ['name']

    def __str__(self):
        return f"{self.uid}"




