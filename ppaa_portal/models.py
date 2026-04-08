from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from ppaa_auth.models import BaseModel, Department, User


class DocumentCategory(BaseModel):
    """Categories for organizing documents"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'document_categories'
        verbose_name_plural = 'Document Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Document(BaseModel):
    """Documents stored in the portal"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PUBLISHED', 'Published'),
        ('ARCHIVED', 'Archived'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    file_url = models.CharField(max_length=500, blank=True, null=True)  # Store MinIO object path, presigned URLs generated on-demand
    category = models.ForeignKey(DocumentCategory, on_delete=models.SET_NULL, null=True, related_name='documents')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    is_public = models.BooleanField(default=False)
    download_count = models.IntegerField(default=0)
    tags = models.CharField(max_length=500, blank=True, null=True)  # Comma-separated tags

    class Meta:
        db_table = 'documents'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Announcement(BaseModel):
    """Announcements for the portal"""
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    is_pinned = models.BooleanField(default=False)
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    # File upload fields - Store MinIO object path, presigned URLs generated on-demand
    file_url = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        db_table = 'announcements'
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return self.title


class Event(BaseModel):
    """Events calendar"""
    EVENT_TYPE_CHOICES = [
        ('MEETING', 'Meeting'),
        ('TRAINING', 'Training'),
        ('WORKSHOP', 'Workshop'),
        ('HOLIDAY', 'Holiday'),
        ('OTHER', 'Other'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='MEETING')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True, null=True)
    is_all_day = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    # File upload fields
    file_url = models.URLField(blank=True, null=True)

    class Meta:
        db_table = 'events'
        ordering = ['start_date']

    def __str__(self):
        return self.title


class FAQ(BaseModel):
    """Frequently Asked Questions"""
    question = models.TextField()
    answer = models.TextField()

    class Meta:
        db_table = 'faqs'
        ordering = ['-created_at']

    def __str__(self):
        return self.question[:50] + "..." if len(self.question) > 50 else self.question


class Notification(BaseModel):
    """User notifications"""
    NOTIFICATION_TYPE_CHOICES = [
        ('INFO', 'Information'),
        ('SUCCESS', 'Success'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('ANNOUNCEMENT', 'Announcement'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES, default='INFO')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    related_object_type = models.CharField(max_length=50, blank=True, null=True)  # e.g., "Document", "Announcement"
    related_object_id = models.UUIDField(blank=True, null=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.username}"


class TodoList(BaseModel):
    """Todo lists for users"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    start_date = models.DateTimeField(blank=True, null=True)
    due_date = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='todo_lists')

    class Meta:
        db_table = 'todo_lists'
        ordering = ['-priority', 'due_date', '-created_at']

    def __str__(self):
        return self.title


class AuditLog(BaseModel):
    """Audit logs for tracking changes"""
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('VIEW', 'View'),
        ('DOWNLOAD', 'Download'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)  # e.g., "Document", "Announcement"
    object_id = models.UUIDField(blank=True, null=True)
    object_repr = models.CharField(max_length=200, blank=True, null=True)
    changes = models.JSONField(blank=True, null=True)  # Store before/after changes
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} {self.model_name} by {self.user.username if self.user else 'System'}"


class QuickLink(BaseModel):
    """Quick links management for the portal"""
    name = models.CharField(max_length=200)
    url = models.URLField()
    logo = models.CharField(max_length=500, blank=True, null=True)  # Store MinIO object path, presigned URLs generated on-demand
    order = models.IntegerField(default=0)
    total_clicks = models.IntegerField(default=0)  # Total click count across all users

    class Meta:
        db_table = 'quick_links'
        ordering = ['name']

    def __str__(self):
        return self.name


class PortalPopupCard(BaseModel):
    """Floating popup card for portal: motivational quote, gratitude, ES image."""
    motivational_quote = models.TextField(blank=True, null=True)
    gratitude_message = models.TextField(blank=True, null=True)
    es_image_path = models.CharField(max_length=500, blank=True, null=True)  # MinIO path, presigned on-demand

    class Meta:
        db_table = 'portal_popup_cards'
        ordering = ['-created_at']

    def __str__(self):
        return f"Popup Card ({self.uid})"

