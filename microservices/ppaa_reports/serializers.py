from rest_framework import serializers
from django.utils import timezone
from ppaa_auth.models import Department, UserProfile

# PPAA auth does not expose a separate Directory model; reuse Department.
Directory = Department
from .models import (
    FinancialYear,
    FinancialPeriod,
    Stakeholder,
    ReportType,
    ReportCategory,
    Report,
    ReportProgress,
    ReportComment,
    ReportAuditTrail,
    ReportReminder,
    ReportSetting,
)


class DirectorySerializer(serializers.ModelSerializer):
    """Serializer for Directory (Directorate)"""
    class Meta:
        model = Directory
        fields = ['uid', 'name', 'code', 'description', 'is_active']


class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department (Unit)"""
    directory_name = serializers.SerializerMethodField()
    directory_uid = serializers.SerializerMethodField()

    def get_directory_name(self, obj):
        return obj.name

    def get_directory_uid(self, obj):
        return str(obj.uid) if getattr(obj, "uid", None) else None

    class Meta:
        model = Department
        fields = ['uid', 'name', 'code', 'description', 'directory_uid', 'directory_name', 'is_active']


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """Serializer that allows dynamic field selection"""
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        exclude = kwargs.pop('exclude', None)
        super().__init__(*args, **kwargs)

        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

        if exclude is not None:
            for field_name in exclude:
                self.fields.pop(field_name, None)


class AuditMixin(serializers.Serializer):
    """Mixin for audit fields"""
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
        return None

    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return f"{obj.updated_by.first_name} {obj.updated_by.last_name}".strip()
        return None


class BaseModelSerializer(DynamicFieldsModelSerializer, AuditMixin):
    """Base serializer with common fields"""
    class Meta:
        fields = ['uid', 'is_active', 'is_deleted', 'created_at', 'updated_at', 
                  'created_by_name', 'updated_by_name']


class FinancialPeriodSerializer(BaseModelSerializer):
    """Serializer for Financial Period (Quarters, Months)"""
    period_type_display = serializers.CharField(
        source='get_period_type_display',
        read_only=True
    )
    display_name = serializers.CharField(read_only=True)
    financial_year_name = serializers.CharField(
        source='financial_year.name',
        read_only=True
    )

    class Meta:
        model = FinancialPeriod
        fields = [
            'uid', 'financial_year', 'financial_year_name', 'period_type', 
            'period_type_display', 'period_number', 'name', 'display_name',
            'start_date', 'end_date', 'is_active', 'created_at', 'updated_at',
            'created_by_name', 'updated_by_name'
        ]
        read_only_fields = ['uid', 'created_at', 'updated_at']


class FinancialYearSerializer(BaseModelSerializer):
    """Serializer for Financial Year"""
    quarters = serializers.SerializerMethodField()

    class Meta:
        model = FinancialYear
        fields = [
            'uid', 'name', 'start_date', 'end_date', 'is_current', 
            'description', 'is_active', 'created_at', 'updated_at',
            'created_by_name', 'updated_by_name', 'quarters'
        ]
        read_only_fields = ['uid', 'created_at', 'updated_at']

    def get_quarters(self, obj):
        """Get all quarters for this financial year"""
        quarters = obj.periods.filter(
            period_type='quarter',
            is_deleted=False,
            is_active=True
        ).order_by('period_number')
        return FinancialPeriodSerializer(quarters, many=True).data


class StakeholderSerializer(BaseModelSerializer):
    """Serializer for Stakeholder"""
    organization_type_display = serializers.CharField(
        source='get_organization_type_display', 
        read_only=True
    )

    class Meta:
        model = Stakeholder
        fields = [
            'uid', 'name', 'organization_type', 'organization_type_display',
            'contact_person', 'email', 'phone', 'address', 'website',
            'description', 'is_active', 'created_at', 'updated_at',
            'created_by_name', 'updated_by_name'
        ]
        read_only_fields = ['uid', 'created_at', 'updated_at']


class ReportTypeSerializer(BaseModelSerializer):
    """Serializer for Report Type"""
    frequency_display = serializers.CharField(
        source='get_frequency_display',
        read_only=True
    )

    class Meta:
        model = ReportType
        fields = [
            'uid', 'name', 'code', 'frequency', 'frequency_display',
            'description', 'submission_deadline_days',
            'before_reminder_days', 'after_reminder_days',
            'default_days_before_deadline', 'reminder_timing',
            'requires_attachment',
            'template_file', 'is_active', 'created_at', 'updated_at',
            'created_by_name', 'updated_by_name'
        ]
        read_only_fields = ['uid', 'created_at', 'updated_at']


class ReportCategorySerializer(BaseModelSerializer):
    """Serializer for Report Category"""
    class Meta:
        model = ReportCategory
        fields = [
            'uid', 'name', 'code', 'description', 'color', 'icon',
            'is_active', 'created_at', 'updated_at',
            'created_by_name', 'updated_by_name'
        ]
        read_only_fields = ['uid', 'created_at', 'updated_at']


class ReportProgressSerializer(BaseModelSerializer):
    """Serializer for Report Progress"""
    class Meta:
        model = ReportProgress
        fields = [
            'uid', 'percentage', 'notes', 'created_at', 'created_by_name'
        ]
        read_only_fields = ['uid', 'created_at']


class ReportCommentSerializer(BaseModelSerializer):
    """Serializer for Report Comment"""
    replies = serializers.SerializerMethodField()
    parent_uid = serializers.SlugRelatedField(
        slug_field='uid',
        queryset=ReportComment.objects.all(),
        source='parent',
        required=False,
        allow_null=True
    )
    directory_name = serializers.SerializerMethodField()
    sender_designation = serializers.SerializerMethodField()
    sender_directory_name = serializers.SerializerMethodField()
    sender_directory_code = serializers.SerializerMethodField()

    class Meta:
        model = ReportComment
        fields = [
            'uid', 'message', 'parent_uid', 'is_system_generated',
            'mentions_directory', 'directory_name',
            'sender_designation', 'sender_directory_name', 'sender_directory_code',
            'replies', 'created_at', 'created_by_name'
        ]
        read_only_fields = [
            'uid', 'created_at', 'is_system_generated', 'mentions_directory', 'directory_name',
            'sender_designation', 'sender_directory_name', 'sender_directory_code'
        ]

    def _get_sender_profile(self, obj):
        if not obj.created_by_id:
            return None
        cache = getattr(self, '_sender_profile_cache', {})
        if obj.created_by_id not in cache:
            cache[obj.created_by_id] = UserProfile.objects.filter(
                user=obj.created_by,
                is_active=True,
                is_deleted=False,
            ).select_related('level', 'department').first()
            self._sender_profile_cache = cache
        return cache[obj.created_by_id]

    def get_directory_name(self, obj):
        """When mentions_directory is True, show the report department name."""
        if obj.mentions_directory and obj.report and (obj.report.department or obj.report.directory):
            return (obj.report.department or obj.report.directory).name
        return None

    def get_sender_designation(self, obj):
        profile = self._get_sender_profile(obj)
        if profile and profile.level:
            return profile.level.name or profile.level.code
        return None

    def get_sender_directory_name(self, obj):
        profile = self._get_sender_profile(obj)
        if profile and profile.department:
            return profile.department.name
        return None

    def get_sender_directory_code(self, obj):
        profile = self._get_sender_profile(obj)
        if profile and profile.department:
            return profile.department.code
        return None

    def get_replies(self, obj):
        if obj.replies.exists():
            return ReportCommentSerializer(
                obj.replies.filter(is_deleted=False), 
                many=True
            ).data
        return []


class ReportAuditTrailSerializer(BaseModelSerializer):
    """Serializer for Report Audit Trail"""
    action_display = serializers.CharField(
        source='get_action_display',
        read_only=True
    )
    performed_by_name = serializers.SerializerMethodField()
    report_title = serializers.CharField(source='report.title', read_only=True)
    report_uid = serializers.UUIDField(source='report.uid', read_only=True)

    class Meta:
        model = ReportAuditTrail
        fields = [
            'uid', 'action', 'action_display', 'performed_by_name',
            'report_uid', 'report_title',
            'old_value', 'new_value', 'comments', 'created_at'
        ]
        read_only_fields = ['uid', 'created_at']

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return f"{obj.performed_by.first_name} {obj.performed_by.last_name}".strip()
        return "System"


class ReportListSerializer(BaseModelSerializer):
    """Serializer for Report list view (lightweight)"""
    report_type_name = serializers.CharField(source='report_type.name', read_only=True)
    report_type_frequency = serializers.CharField(source='report_type.frequency', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    stakeholder_name = serializers.CharField(source='effective_stakeholder_name', read_only=True)
    financial_year_name = serializers.CharField(source='financial_year.name', read_only=True)
    financial_period_name = serializers.CharField(source='financial_period.display_name', read_only=True, default=None)
    directory_name = serializers.CharField(source='department.name', read_only=True, default=None)
    directory_code = serializers.CharField(source='department.code', read_only=True, default=None)
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    deadline_state = serializers.CharField(read_only=True)
    days_until_deadline = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    submitted_late = serializers.BooleanField(read_only=True)
    days_overdue_on_submission = serializers.IntegerField(read_only=True)
    has_unread_comments = serializers.SerializerMethodField()
    period_done_count = serializers.IntegerField(read_only=True, default=None)
    period_pending_count = serializers.IntegerField(read_only=True, default=None)
    period_total_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Report
        fields = [
            'uid', 'title', 'reference_number', 'report_type_name',
            'report_type_frequency', 'category_name', 'stakeholder_name', 
            'financial_year_name', 'financial_period_name',
            'directory_name', 'directory_code', 'department_name',
            'scope', 'scope_display', 'status', 'status_display',
            'priority', 'priority_display', 'deadline_date',
            'deadline_state', 'days_until_deadline', 'is_overdue',
            'submitted_late', 'days_overdue_on_submission',
            'progress_percentage', 'submission_date', 'created_at',
            'has_unread_comments', 'period_done_count',
            'period_pending_count', 'period_total_count'
        ]

    def get_has_unread_comments(self, obj):
        """True if current user has unread comments (new comments since last view)"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        from .models import ReportCommentRead
        last_read = ReportCommentRead.objects.filter(
            report=obj, user=request.user
        ).values_list('last_read_at', flat=True).first()
        latest_comment = obj.comments.filter(is_deleted=False).order_by('-created_at').values_list('created_at', flat=True).first()
        if not latest_comment:
            return False
        if last_read is None:
            return True  # Never read = has unread
        return latest_comment > last_read


class ReportDetailSerializer(BaseModelSerializer):
    """Serializer for Report detail view (full data)"""
    report_type = ReportTypeSerializer(read_only=True)
    report_type_uid = serializers.SlugRelatedField(
        slug_field='uid',
        queryset=ReportType.objects.filter(is_deleted=False, is_active=True),
        source='report_type',
        write_only=True
    )
    category = ReportCategorySerializer(read_only=True)
    category_uid = serializers.SlugRelatedField(
        slug_field='uid',
        queryset=ReportCategory.objects.filter(is_deleted=False, is_active=True),
        source='category',
        required=False,
        allow_null=True,
        write_only=True
    )
    directory = DirectorySerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    stakeholder = StakeholderSerializer(read_only=True)
    stakeholder_uid = serializers.SlugRelatedField(
        slug_field='uid',
        queryset=Stakeholder.objects.filter(is_deleted=False, is_active=True),
        source='stakeholder',
        required=False,
        allow_null=True,
        write_only=True
    )
    financial_year = FinancialYearSerializer(read_only=True)
    financial_year_uid = serializers.SlugRelatedField(
        slug_field='uid',
        queryset=FinancialYear.objects.filter(is_deleted=False, is_active=True),
        source='financial_year',
        write_only=True
    )
    financial_period = FinancialPeriodSerializer(read_only=True)
    financial_period_uid = serializers.SlugRelatedField(
        slug_field='uid',
        queryset=FinancialPeriod.objects.filter(is_deleted=False, is_active=True),
        source='financial_period',
        required=False,
        allow_null=True,
        write_only=True
    )
    assigned_to_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    deadline_state = serializers.CharField(read_only=True)
    days_until_deadline = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    submitted_late = serializers.BooleanField(read_only=True)
    days_overdue_on_submission = serializers.IntegerField(read_only=True)
    effective_stakeholder_name = serializers.CharField(read_only=True)
    submitted_by_name = serializers.SerializerMethodField()
    progress_updates = ReportProgressSerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    latest_comments = serializers.SerializerMethodField()
    quarter_submissions = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'uid', 'title', 'reference_number', 
            'report_type', 'report_type_uid',
            'category', 'category_uid',
            'directory', 'department', 'assigned_to_name',
            'stakeholder', 'stakeholder_uid', 'other_stakeholder_name',
            'effective_stakeholder_name',
            'financial_year', 'financial_year_uid',
            'financial_period', 'financial_period_uid',
            'scope', 'scope_display',
            'status', 'status_display',
            'priority', 'priority_display',
            'deadline_date', 'deadline_state', 'days_until_deadline', 'is_overdue',
            'submitted_late', 'days_overdue_on_submission',
            'submission_date', 'submitted_by_name',
            'description', 'notes', 'attachment',
            'progress_percentage', 'progress_updates',
            'reminder_sent', 'reminder_sent_at',
            'comments_count', 'latest_comments', 'quarter_submissions',
            'is_active', 'created_at', 'updated_at',
            'created_by_name', 'updated_by_name'
        ]
        read_only_fields = [
            'uid', 'reference_number', 'submission_date', 'submitted_by_name',
            'reminder_sent', 'reminder_sent_at', 'created_at', 'updated_at',
            'directory', 'department'
        ]

    def get_submitted_by_name(self, obj):
        if obj.submitted_by:
            return f"{obj.submitted_by.first_name} {obj.submitted_by.last_name}".strip()
        return None

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}".strip()
        return None

    def get_comments_count(self, obj):
        return obj.comments.filter(is_deleted=False).count()

    def get_latest_comments(self, obj):
        latest = obj.comments.filter(is_deleted=False, parent__isnull=True).order_by('-created_at')[:3]
        return ReportCommentSerializer(latest, many=True).data

    def get_quarter_submissions(self, obj):
        try:
            if not obj.report_type or obj.report_type.frequency not in ('quarterly', 'biannual'):
                return []

            freq = obj.report_type.frequency
            period_type = 'quarter' if freq == 'quarterly' else 'biannual'
            qs = Report.objects.filter(
                is_deleted=False,
                report_type=obj.report_type,
                financial_year=obj.financial_year,
                department=obj.department,
                title=obj.title,
                scope=obj.scope,
                category=obj.category,
                stakeholder=obj.stakeholder,
                other_stakeholder_name=obj.other_stakeholder_name,
            ).select_related('financial_period').filter(
                financial_period__period_type=period_type
            ).order_by('financial_period__period_number', 'created_at')

            return [{
                "uid": str(r.uid),
                "period_uid": str(r.financial_period.uid) if r.financial_period else None,
                "period_name": r.financial_period.display_name if r.financial_period else None,
                "period_start_date": r.financial_period.start_date if r.financial_period else None,
                "period_end_date": r.financial_period.end_date if r.financial_period else None,
                "status": r.status,
                "status_display": r.get_status_display(),
                "progress_percentage": r.progress_percentage,
                "deadline_date": r.deadline_date,
                "submission_date": r.submission_date,
                "has_attachment": bool(getattr(r, "attachment", None)),
                "attachment_name": (getattr(r.attachment, "name", None) if getattr(r, "attachment", None) else None),
            } for r in qs]
        except Exception:
            return []


class ReportCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating reports - department is auto-filled from user profile"""
    report_type_uid = serializers.SlugRelatedField(
        slug_field='uid',
        queryset=ReportType.objects.filter(is_deleted=False, is_active=True),
        source='report_type'
    )
    category_uid = serializers.SlugRelatedField(
        slug_field='uid',
        queryset=ReportCategory.objects.filter(is_deleted=False, is_active=True),
        source='category',
        required=False,
        allow_null=True
    )
    stakeholder_uid = serializers.SlugRelatedField(
        slug_field='uid',
        queryset=Stakeholder.objects.filter(is_deleted=False, is_active=True),
        source='stakeholder',
        required=False,
        allow_null=True
    )
    financial_year_uid = serializers.SlugRelatedField(
        slug_field='uid',
        queryset=FinancialYear.objects.filter(is_deleted=False, is_active=True),
        source='financial_year'
    )
    financial_period_uid = serializers.SlugRelatedField(
        slug_field='uid',
        queryset=FinancialPeriod.objects.filter(is_deleted=False, is_active=True),
        source='financial_period',
        required=False,
        allow_null=True
    )
    deadline_date = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = Report
        fields = [
            'title', 'report_type_uid', 'category_uid',
            'stakeholder_uid', 'other_stakeholder_name',
            'financial_year_uid', 'financial_period_uid', 'scope', 'priority',
            'deadline_date', 'description', 'notes', 'attachment'
        ]

    def validate(self, data):
        scope = data.get('scope', 'internal')
        stakeholder = data.get('stakeholder')
        other_stakeholder_name = data.get('other_stakeholder_name')
        report_type = data.get('report_type')
        financial_period = data.get('financial_period')
        deadline_date = data.get('deadline_date')

        if scope == 'external' and not stakeholder and not other_stakeholder_name:
            raise serializers.ValidationError({
                'stakeholder_uid': 'External reports must have a stakeholder or other_stakeholder_name'
            })

        frequency = getattr(report_type, 'frequency', None) if report_type else None
        auto_deadline_frequencies = {'monthly', 'quarterly', 'biannual', 'annual'}

        if frequency in auto_deadline_frequencies:
            if frequency == 'annual':
                if not data.get('financial_year'):
                    raise serializers.ValidationError({
                        'financial_year_uid': 'Financial year is required for annual reports'
                    })
            elif frequency == 'quarterly':
                period_uids = []
                initial_data = getattr(self, "initial_data", {}) or {}
                if hasattr(initial_data, "getlist"):
                    period_uids = initial_data.getlist("financial_period_uids") or []
                elif isinstance(initial_data, dict):
                    raw = initial_data.get("financial_period_uids")
                    if isinstance(raw, list):
                        period_uids = raw
                    elif raw:
                        period_uids = [raw]

                has_multi_periods = any(str(uid).strip() for uid in period_uids)
                if not data.get('financial_period') and not has_multi_periods:
                    raise serializers.ValidationError({
                        'financial_period_uid': 'Reporting period is required for this report type'
                    })
            else:
                if not data.get('financial_period'):
                    raise serializers.ValidationError({
                        'financial_period_uid': 'Reporting period is required for this report type'
                    })
        else:
            if not deadline_date:
                raise serializers.ValidationError({
                    'deadline_date': 'Deadline date is required for this report type'
                })

        if (
            report_type
            and getattr(report_type, 'frequency', None) == 'biannual'
            and financial_period
            and deadline_date
        ):
            if deadline_date < financial_period.start_date or deadline_date > financial_period.end_date:
                raise serializers.ValidationError({
                    'deadline_date': (
                        f"Deadline must be within the selected half-year period "
                        f"({financial_period.start_date} to {financial_period.end_date})"
                    )
                })

        return data


class ReportUpdateStatusSerializer(serializers.Serializer):
    """Serializer for updating report status"""
    status = serializers.ChoiceField(choices=Report.STATUS_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)


class ReportSubmitSerializer(serializers.Serializer):
    """Serializer for submitting a report"""
    attachment = serializers.FileField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class ReportProgressUpdateSerializer(serializers.Serializer):
    """Serializer for updating report progress"""
    percentage = serializers.IntegerField(min_value=0, max_value=100)
    notes = serializers.CharField(required=False, allow_blank=True)


class ReportReminderSerializer(BaseModelSerializer):
    """Serializer for Report Reminder"""
    reminder_type_display = serializers.CharField(
        source='get_reminder_type_display',
        read_only=True
    )

    class Meta:
        model = ReportReminder
        fields = [
            'uid', 'reminder_type', 'reminder_type_display',
            'scheduled_date', 'sent_at', 'is_sent',
            'recipient_uids', 'subject', 'message',
            'created_at', 'created_by_name'
        ]
        read_only_fields = ['uid', 'sent_at', 'is_sent', 'created_at']


class ReportSettingSerializer(BaseModelSerializer):
    """Serializer for Report Settings"""
    class Meta:
        model = ReportSetting
        fields = [
            'reference_number_prefix', 'reference_number_counter',
            'reset_counter_yearly', 'default_reminder_days',
            'due_soon_threshold_days', 'enable_email_notifications',
            'enable_system_notifications', 'max_attachment_size_mb',
            'allowed_file_extensions', 'organization_name',
            'updated_at', 'updated_by_name'
        ]
        read_only_fields = ['reference_number_counter', 'updated_at']


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""
    status_summary = serializers.DictField()
    deadline_summary = serializers.DictField()
    total_reports = serializers.IntegerField()
    overdue_count = serializers.IntegerField()
    due_soon_count = serializers.IntegerField()
    due_today_count = serializers.IntegerField()
    submitted_this_month = serializers.IntegerField()
    by_directorate = serializers.ListField(required=False)
    by_report_type = serializers.ListField(required=False)
    recent_submissions = serializers.ListField(required=False)
    upcoming_deadlines = serializers.ListField(required=False)
