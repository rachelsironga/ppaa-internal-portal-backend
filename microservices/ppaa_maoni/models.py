from django.db import models
import uuid
from django.utils import timezone

from ppaa_auth.models import BaseModel


class MaoniCategory(BaseModel):
    """
    Category for organizing suggestions (Area of Concern)
    """
    CATEGORY_TYPE_CHOICES = [
        ('GENERAL', 'General'),
        ('DEPARTMENTAL', 'Departmental'),
        ('STRATEGIC', 'Strategic'),
        ('OPERATIONAL', 'Operational'),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    type = models.CharField(max_length=20, choices=CATEGORY_TYPE_CHOICES, default='GENERAL')
    icon = models.CharField(max_length=50, null=True, blank=True)  # Icon class name
    color = models.CharField(max_length=20, default='#4f46e5')  # Hex color code
    order = models.IntegerField(default=0)  # For sorting categories
    is_public = models.BooleanField(default=True)  # Whether users can see/select this category

    class Meta:
        app_label = 'ppaa_maoni'
        db_table = 'maoni_categories'
        verbose_name_plural = 'Maoni Categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Maoni(BaseModel):
    """
    Main Maoni (Suggestion) model - Simplified for suggestion flow
    Flow: User sends suggestion -> HR receives -> HR replies -> User sees reply and can reply back -> HR can print
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]

    # Basic information
    title = models.CharField(max_length=200)
    description = models.TextField()

    # Classification
    category = models.ForeignKey(MaoniCategory, on_delete=models.SET_NULL, null=True,
                                 related_name='maoni', blank=True,
                                 help_text="Area of concern")
    # Department from ppaa_auth (stored as UID string, not ForeignKey)
    department_uid = models.CharField(max_length=100, null=True, blank=True, 
                                      help_text="Department UID from ppaa_auth app")

    # Status and tracking
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='SUBMITTED')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')

    # Submission info
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by_id = models.IntegerField(null=True, blank=True)  # User ID (not ForeignKey for anonymity)

    # Comment tracking
    comment_count = models.IntegerField(default=0)

    class Meta:
        app_label = 'ppaa_maoni'
        db_table = 'maoni'
        verbose_name_plural = 'Maoni'
        ordering = ['-submitted_at', '-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['category']),
            models.Index(fields=['department_uid']),
            models.Index(fields=['submitted_at']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Auto-set submitted_at when status changes to SUBMITTED
        if self.pk:
            old_status = Maoni.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            if old_status != 'SUBMITTED' and self.status == 'SUBMITTED' and not self.submitted_at:
                self.submitted_at = timezone.now()
        elif self.status == 'SUBMITTED' and not self.submitted_at:
            self.submitted_at = timezone.now()

        super().save(*args, **kwargs)


class MaoniComment(BaseModel):
    """
    Comments/Replies on Maoni suggestions
    Supports threaded replies: HR can reply to suggestions, users can reply to HR replies
    """
    maoni = models.ForeignKey(Maoni, on_delete=models.CASCADE, related_name='comments')
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                                       related_name='replies',
                                       help_text="Parent comment if this is a reply to another comment")
    comment = models.TextField()
    is_anonymous = models.BooleanField(default=True)
    commented_by_id = models.IntegerField(null=True, blank=True)  # User ID
    is_internal = models.BooleanField(default=False)  # Internal admin comments not visible to public

    class Meta:
        app_label = 'ppaa_maoni'
        db_table = 'maoni_comments'
        ordering = ['created_at']

    def __str__(self):
        return f"Comment on {self.maoni.title[:50]}..."
