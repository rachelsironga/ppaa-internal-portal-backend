from django.contrib import admin
from .models import (
    FinancialYear, FinancialPeriod, Stakeholder, ReportType, ReportCategory,
    Report, ReportProgress, ReportComment, ReportAuditTrail,
    ReportReminder, ReportSetting
)


class FinancialPeriodInline(admin.TabularInline):
    model = FinancialPeriod
    extra = 0
    fields = ['period_type', 'period_number', 'name', 'start_date', 'end_date', 'is_active']
    readonly_fields = []
    ordering = ['period_type', 'period_number']


@admin.register(FinancialYear)
class FinancialYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'is_current', 'is_active']
    list_filter = ['is_current', 'is_active']
    search_fields = ['name']
    ordering = ['-start_date']
    inlines = [FinancialPeriodInline]


@admin.register(FinancialPeriod)
class FinancialPeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'financial_year', 'period_type', 'period_number', 'start_date', 'end_date', 'is_active']
    list_filter = ['financial_year', 'period_type', 'is_active']
    search_fields = ['name']
    ordering = ['financial_year', 'period_type', 'period_number']


@admin.register(Stakeholder)
class StakeholderAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization_type', 'contact_person', 'email', 'is_active']
    list_filter = ['organization_type', 'is_active']
    search_fields = ['name', 'contact_person', 'email']
    ordering = ['name']


@admin.register(ReportType)
class ReportTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'frequency', 'requires_attachment', 'is_active']
    list_filter = ['frequency', 'requires_attachment', 'is_active']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(ReportCategory)
class ReportCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'color', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = [
        'reference_number', 'title', 'report_type', 'status',
        'deadline_date', 'deadline_state', 'priority', 'is_active'
    ]
    list_filter = ['status', 'priority', 'scope', 'report_type', 'financial_year']
    search_fields = ['reference_number', 'title', 'description']
    ordering = ['-deadline_date']
    readonly_fields = ['reference_number', 'submission_date', 'deadline_state']
    
    def deadline_state(self, obj):
        return obj.deadline_state
    deadline_state.short_description = 'Deadline State'


@admin.register(ReportProgress)
class ReportProgressAdmin(admin.ModelAdmin):
    list_display = ['report', 'percentage', 'created_at']
    list_filter = ['created_at']
    ordering = ['-created_at']


@admin.register(ReportComment)
class ReportCommentAdmin(admin.ModelAdmin):
    list_display = ['report', 'message', 'mentions_directory', 'is_system_generated', 'created_at']
    list_filter = ['mentions_directory', 'is_system_generated', 'created_at']
    ordering = ['-created_at']


@admin.register(ReportAuditTrail)
class ReportAuditTrailAdmin(admin.ModelAdmin):
    list_display = ['report', 'action', 'performed_by', 'created_at']
    list_filter = ['action', 'created_at']
    ordering = ['-created_at']


@admin.register(ReportReminder)
class ReportReminderAdmin(admin.ModelAdmin):
    list_display = ['report', 'reminder_type', 'scheduled_date', 'is_sent']
    list_filter = ['reminder_type', 'is_sent', 'scheduled_date']
    ordering = ['scheduled_date']


@admin.register(ReportSetting)
class ReportSettingAdmin(admin.ModelAdmin):
    list_display = ['organization_name', 'reference_number_prefix', 'enable_email_notifications']
