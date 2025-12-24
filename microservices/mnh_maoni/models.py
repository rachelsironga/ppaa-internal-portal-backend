from django.db import models
import uuid
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from mnh_auth.models import BaseModel


class MaoniCategory(BaseModel):
    """
    Category for organizing suggestions (e.g., HR Processes, ICT Infrastructure)
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
        db_table = 'maoni_categories'
        verbose_name_plural = 'Maoni Categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class MaoniDirectory(BaseModel):
    """
    Directory/Department that suggestions can be directed to
    """
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    contact_person = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='sub_directories')

    class Meta:
        db_table = 'maoni_directories'
        verbose_name_plural = 'Maoni Directories'
        ordering = ['name']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Maoni(BaseModel):
    """
    Main Maoni (Suggestion/Contribution) model
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('PENDING_REVIEW', 'Pending Review'),
        ('UNDER_CONSIDERATION', 'Under Consideration'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('IMPLEMENTED', 'Implemented'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]

    VISIBILITY_CHOICES = [
        ('PUBLIC', 'Public'),
        ('PRIVATE', 'Private'),
        ('ANONYMOUS', 'Anonymous'),
        ('CONFIDENTIAL', 'Confidential'),
    ]

    # Basic information
    title = models.CharField(max_length=200)
    description = models.TextField()
    problem_statement = models.TextField(null=True, blank=True)  # What's the problem?
    proposed_solution = models.TextField(null=True, blank=True)  # What's the solution?
    expected_benefits = models.TextField(null=True, blank=True)  # Expected benefits
    estimated_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    estimated_implementation_time = models.CharField(max_length=50, null=True, blank=True)  # e.g., "2-4 weeks"

    # Classification
    category = models.ForeignKey(MaoniCategory, on_delete=models.SET_NULL, null=True,
                                 related_name='maoni')
    directory = models.ForeignKey(MaoniDirectory, on_delete=models.SET_NULL, null=True,
                                  related_name='maoni')

    # Status and tracking
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='ANONYMOUS')

    # Submission info
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by_id = models.IntegerField(null=True, blank=True)  # User ID (not ForeignKey for anonymity)

    # Review info
    assigned_to_id = models.IntegerField(null=True, blank=True)  # Reviewer/Admin ID
    review_deadline = models.DateTimeField(null=True, blank=True)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    last_reviewed_by_id = models.IntegerField(null=True, blank=True)

    # Implementation info
    implementation_date = models.DateField(null=True, blank=True)
    implementation_notes = models.TextField(null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    # Rejection info
    rejection_reason = models.TextField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by_id = models.IntegerField(null=True, blank=True)

    # Metrics
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)
    views = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)

    # Flags
    is_featured = models.BooleanField(default=False)
    is_urgent = models.BooleanField(default=False)
    requires_follow_up = models.BooleanField(default=False)

    # Audit trail
    version = models.IntegerField(default=1)
    previous_version = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='next_versions')

    class Meta:
        db_table = 'maoni'
        verbose_name_plural = 'Maoni'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['category']),
            models.Index(fields=['directory']),
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

        # Auto-set is_urgent based on priority
        self.is_urgent = self.priority in ['HIGH', 'URGENT']

        super().save(*args, **kwargs)

    def get_net_votes(self):
        return self.upvotes - self.downvotes

    def get_vote_percentage(self):
        total = self.upvotes + self.downvotes
        if total == 0:
            return 0
        return (self.upvotes / total) * 100

    def get_anonymous_identifier(self):
        """Generate anonymous identifier for the submitter"""
        if self.submitted_by_id:
            # Generate a consistent anonymous ID based on user ID
            import hashlib
            hash_obj = hashlib.md5(str(self.submitted_by_id).encode())
            return f"anonymous_{hash_obj.hexdigest()[:8]}"
        return "anonymous"


class MaoniAttachment(BaseModel):
    """
    Attachments for Maoni (documents, images, etc.)
    """
    maoni = models.ForeignKey(Maoni, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='maoni/attachments/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)  # e.g., 'pdf', 'image', 'document'
    file_size = models.IntegerField()  # Size in bytes
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'maoni_attachments'

    def __str__(self):
        return f"{self.file_name} ({self.maoni.title})"


class MaoniComment(BaseModel):
    """
    Comments on Maoni suggestions
    """
    maoni = models.ForeignKey(Maoni, on_delete=models.CASCADE, related_name='comments')
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                                       related_name='replies')
    comment = models.TextField()
    is_anonymous = models.BooleanField(default=True)
    commented_by_id = models.IntegerField(null=True, blank=True)  # User ID
    is_internal = models.BooleanField(default=False)  # Internal admin comments not visible to public
    likes = models.IntegerField(default=0)

    class Meta:
        db_table = 'maoni_comments'
        ordering = ['created_at']

    def __str__(self):
        return f"Comment on {self.maoni.title[:50]}..."


class MaoniVote(BaseModel):
    """
    User votes on Maoni suggestions
    """
    VOTE_TYPE_CHOICES = [
        ('UPVOTE', 'Upvote'),
        ('DOWNVOTE', 'Downvote'),
    ]

    maoni = models.ForeignKey(Maoni, on_delete=models.CASCADE, related_name='votes')
    vote_type = models.CharField(max_length=10, choices=VOTE_TYPE_CHOICES)
    voted_by_id = models.IntegerField()  # User ID (not ForeignKey for anonymity)
    is_anonymous = models.BooleanField(default=True)

    class Meta:
        db_table = 'maoni_votes'
        unique_together = ['maoni', 'voted_by_id']  # One vote per user per maoni

    def __str__(self):
        return f"{self.get_vote_type_display()} on {self.maoni.title}"


class MaoniFollow(BaseModel):
    """
    Users following specific Maoni for updates
    """
    maoni = models.ForeignKey(Maoni, on_delete=models.CASCADE, related_name='followers')
    followed_by_id = models.IntegerField()  # User ID
    notification_preferences = models.JSONField(default=dict)  # Store notification settings

    class Meta:
        db_table = 'maoni_follows'
        unique_together = ['maoni', 'followed_by_id']

    def __str__(self):
        return f"Follow: {self.followed_by_id} -> {self.maoni.title}"


class MaoniStatusHistory(BaseModel):
    """
    Track status changes for audit trail
    """
    maoni = models.ForeignKey(Maoni, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=30, choices=Maoni.STATUS_CHOICES)
    new_status = models.CharField(max_length=30, choices=Maoni.STATUS_CHOICES)
    notes = models.TextField(null=True, blank=True)
    changed_by_id = models.IntegerField()  # User ID who made the change

    class Meta:
        db_table = 'maoni_status_history'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.maoni.title}: {self.old_status} -> {self.new_status}"


class MaoniTag(BaseModel):
    """
    Tags for categorizing and searching Maoni
    """
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(null=True, blank=True)
    color = models.CharField(max_length=20, default='#6b7280')

    class Meta:
        db_table = 'maoni_tags'

    def __str__(self):
        return self.name


class MaoniTagging(BaseModel):
    """
    Many-to-many relationship between Maoni and Tags
    """
    maoni = models.ForeignKey(Maoni, on_delete=models.CASCADE, related_name='taggings')
    tag = models.ForeignKey(MaoniTag, on_delete=models.CASCADE, related_name='taggings')

    class Meta:
        db_table = 'maoni_taggings'
        unique_together = ['maoni', 'tag']

    def __str__(self):
        return f"{self.tag.name} -> {self.maoni.title}"


class MaoniReview(BaseModel):
    """
    Detailed reviews by administrators/committee
    """
    maoni = models.ForeignKey(Maoni, on_delete=models.CASCADE, related_name='reviews')
    reviewed_by_id = models.IntegerField()  # Reviewer ID
    review_notes = models.TextField()
    feasibility_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True
    )
    impact_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True
    )
    cost_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True
    )
    overall_score = models.FloatField(null=True, blank=True)
    recommendation = models.CharField(max_length=20, choices=[
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('MODIFY', 'Requires Modification'),
        ('MORE_INFO', 'More Information Needed'),
        ('HOLD', 'Put On Hold'),
    ])
    is_final = models.BooleanField(default=False)

    class Meta:
        db_table = 'maoni_reviews'
        ordering = ['-created_at']

    def __str__(self):
        return f"Review by {self.reviewed_by_id} for {self.maoni.title}"

    def calculate_overall_score(self):
        """Calculate weighted overall score"""
        if all([self.feasibility_score, self.impact_score, self.cost_score]):
            weights = {'feasibility': 0.4, 'impact': 0.4, 'cost': 0.2}
            self.overall_score = (
                    self.feasibility_score * weights['feasibility'] +
                    self.impact_score * weights['impact'] +
                    self.cost_score * weights['cost']
            )
        return self.overall_score

    def save(self, *args, **kwargs):
        self.calculate_overall_score()
        super().save(*args, **kwargs)


class MaoniNotification(BaseModel):
    """
    Notifications for Maoni-related events
    """
    NOTIFICATION_TYPE_CHOICES = [
        ('STATUS_CHANGE', 'Status Change'),
        ('NEW_COMMENT', 'New Comment'),
        ('NEW_VOTE', 'New Vote'),
        ('REVIEW_ASSIGNED', 'Review Assigned'),
        ('DEADLINE_REMINDER', 'Deadline Reminder'),
        ('IMPLEMENTATION_UPDATE', 'Implementation Update'),
        ('MENTION', 'Mention'),
    ]

    recipient_id = models.IntegerField()  # User ID
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE_CHOICES)
    maoni = models.ForeignKey(Maoni, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    action_url = models.URLField(null=True, blank=True)

    class Meta:
        db_table = 'maoni_notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.recipient_id}"


class MaoniAnalytics(BaseModel):
    """
    Analytics data for dashboard and reporting
    """
    date = models.DateField(unique=True)
    total_contributions = models.IntegerField(default=0)
    new_contributions = models.IntegerField(default=0)
    implemented_contributions = models.IntegerField(default=0)
    pending_review = models.IntegerField(default=0)
    unique_contributors = models.IntegerField(default=0)
    avg_response_time = models.FloatField(default=0)  # in days
    engagement_rate = models.FloatField(default=0)  # percentage

    # Category breakdown (stored as JSON)
    category_data = models.JSONField(default=dict)

    # Department breakdown
    department_data = models.JSONField(default=dict)

    class Meta:
        db_table = 'maoni_analytics'
        verbose_name_plural = 'Maoni Analytics'
        ordering = ['-date']

    def __str__(self):
        return f"Analytics for {self.date}"


class MaoniReport(BaseModel):
    """
    Generated reports for administrators
    """
    REPORT_TYPE_CHOICES = [
        ('DETAILED_ANALYTICS', 'Detailed Analytics'),
        ('EXECUTIVE_SUMMARY', 'Executive Summary'),
        ('OPERATIONAL', 'Operational Report'),
        ('DEPARTMENTAL', 'Departmental Report'),
        ('CUSTOM', 'Custom Report'),
    ]

    FORMAT_CHOICES = [
        ('PDF', 'PDF'),
        ('EXCEL', 'Excel'),
        ('JSON', 'JSON'),
        ('HTML', 'HTML'),
    ]

    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES)
    report_name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)

    # Date range
    start_date = models.DateField()
    end_date = models.DateField()

    # Report content
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='PDF')
    file = models.FileField(upload_to='maoni/reports/%Y/%m/%d/', null=True, blank=True)
    file_size = models.IntegerField(null=True, blank=True)  # Size in bytes

    # Generation info
    generated_by_id = models.IntegerField()
    generation_time = models.FloatField(null=True, blank=True)  # Time in seconds
    parameters = models.JSONField(default=dict)  # Store report parameters

    class Meta:
        db_table = 'maoni_reports'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.report_name} ({self.get_report_type_display()})"


class MaoniSetting(BaseModel):
    """
    System settings for Maoni application
    """
    SETTING_TYPE_CHOICES = [
        ('GENERAL', 'General Settings'),
        ('MODERATION', 'Moderation Settings'),
        ('NOTIFICATION', 'Notification Settings'),
        ('ANALYTICS', 'Analytics Settings'),
        ('INTEGRATION', 'Integration Settings'),
    ]

    setting_key = models.CharField(max_length=100, unique=True)
    setting_type = models.CharField(max_length=30, choices=SETTING_TYPE_CHOICES, default='GENERAL')
    value = models.JSONField(default=dict)
    description = models.TextField(null=True, blank=True)
    is_public = models.BooleanField(default=False)  # Whether users can see this setting

    class Meta:
        db_table = 'maoni_settings'

    def __str__(self):
        return self.setting_key


class MaoniFeedback(BaseModel):
    """
    Feedback on the Maoni system itself
    """
    FEEDBACK_TYPE_CHOICES = [
        ('SYSTEM_USABILITY', 'System Usability'),
        ('PROCESS_IMPROVEMENT', 'Process Improvement'),
        ('BUG_REPORT', 'Bug Report'),
        ('FEATURE_REQUEST', 'Feature Request'),
        ('GENERAL', 'General Feedback'),
    ]

    feedback_type = models.CharField(max_length=30, choices=FEEDBACK_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    submitted_by_id = models.IntegerField(null=True, blank=True)
    is_anonymous = models.BooleanField(default=True)

    # Response
    response = models.TextField(null=True, blank=True)
    responded_by_id = models.IntegerField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=[
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ], default='OPEN')

    class Meta:
        db_table = 'maoni_feedback'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.feedback_type}: {self.title}"