from django.contrib import admin
from .models import (
    Affiliation, Student, Application, DepartmentAllocation,
    Supervisor, Institution, MOU, TrainingBatch, TrainingSetting
)


@admin.register(Affiliation)
class AffiliationAdmin(admin.ModelAdmin):
    list_display = ('uid', 'type', 'name', 'level', 'is_deleted', 'created_at')
    list_filter = ('type', 'level', 'is_deleted', 'created_at')
    search_fields = ('name', 'course')
    readonly_fields = ('uid', 'created_at', 'updated_at', 'deleted_at')


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('uid', 'full_name', 'email', 'student_id', 'type', 'is_deleted')
    list_filter = ('type', 'sex', 'is_deleted', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'student_id')
    readonly_fields = ('uid', 'created_at', 'updated_at', 'deleted_at', 'type')


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('uid', 'application_number', 'student', 'placement_type', 'category', 'is_deleted')
    list_filter = ('placement_type', 'category', 'campus', 'is_deleted', 'from_date')
    search_fields = ('application_number', 'student__first_name', 'student__last_name')
    readonly_fields = ('uid', 'created_at', 'updated_at', 'deleted_at')


@admin.register(DepartmentAllocation)
class DepartmentAllocationAdmin(admin.ModelAdmin):
    list_display = ('uid', 'application', 'department_uid', 'supervisor', 'is_deleted')
    list_filter = ('is_deleted', 'start_date', 'end_date')
    search_fields = ('department_uid', 'description')
    readonly_fields = ('uid', 'created_at', 'updated_at', 'deleted_at', 'duration_days')


@admin.register(Supervisor)
class SupervisorAdmin(admin.ModelAdmin):
    list_display = ('uid', 'user_guid', 'department_uid', 'is_deleted')
    list_filter = ('is_deleted', 'created_at')
    search_fields = ('user_guid', 'department_uid', 'description')
    readonly_fields = ('uid', 'created_at', 'updated_at', 'deleted_at')


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ('uid', 'name', 'institution_code', 'institution_type', 'is_deleted')
    list_filter = ('institution_type', 'is_deleted', 'created_at')
    search_fields = ('name', 'institution_code', 'contact_email')
    readonly_fields = ('uid', 'created_at', 'updated_at', 'deleted_at')


@admin.register(MOU)
class MOUAdmin(admin.ModelAdmin):
    list_display = ('uid', 'mou_number', 'institution', 'start_date', 'end_date', 'is_deleted')
    list_filter = ('is_deleted', 'start_date', 'created_at')
    search_fields = ('mou_number', 'institution__name')
    readonly_fields = ('uid', 'created_at', 'updated_at', 'deleted_at', 'duration', 'duration_display')


@admin.register(TrainingBatch)
class TrainingBatchAdmin(admin.ModelAdmin):
    list_display = ('uid', 'batch_number', 'mou', 'status', 'training_start_date', 'training_end_date', 'is_deleted')
    list_filter = ('status', 'is_deleted', 'training_start_date')
    search_fields = ('batch_number', 'mou__mou_number')
    readonly_fields = ('uid', 'created_at', 'updated_at', 'deleted_at', 'batch_number', 'duration', 'duration_display')
    fieldsets = (
        ('Basic Information', {
            'fields': ('batch_number', 'mou', 'number_of_students', 'departments')
        }),
        ('Training Details', {
            'fields': ('training_start_date', 'training_end_date', 'duration', 'duration_display')
        }),
        ('Financial Information', {
            'fields': ('invoiced_amount', 'currency')
        }),
        ('Status & Notes', {
            'fields': ('status', 'notes', 'application_letter')
        }),
        ('Cancellation Information', {
            'fields': ('cancellation_reason', 'cancelled_by_guid', 'cancelled_at'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'created_by', 'updated_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TrainingSetting)
class TrainingSettingAdmin(admin.ModelAdmin):
    list_display = ('organization_name', 'training_hours_per_week', 'last_modified_at', 'is_active')
    readonly_fields = ('uid', 'created_at', 'updated_at', 'deleted_at', 'last_modified_at')
    
    fieldsets = (
        ('Organization Settings', {
            'fields': ('organization_name', 'is_active')
        }),
        ('Student ID Settings', {
            'fields': ('student_id_format', 'student_id_prefix', 'student_id_increment_counter', 'reset_student_counter_yearly')
        }),
        ('Application Reference Settings', {
            'fields': ('application_ref_format', 'application_ref_prefix', 'application_ref_counter', 'reset_application_counter_yearly')
        }),
        ('Certificate Settings', {
            'fields': ('certificate_number_format', 'certificate_number_prefix', 'certificate_counter', 'reset_certificate_counter_yearly', 'certificate_validity_years')
        }),
        ('Training Schedule Settings', {
            'fields': ('training_hours_per_week', 'training_days_per_week', 'standard_training_duration', 'standard_training_duration_unit')
        }),
        ('Department Settings', {
            'fields': ('special_departments', 'min_training_days', 'max_training_days', 'allow_overlapping_departments')
        }),
        ('Compliance Settings', {
            'fields': ('minimum_attendance_percentage', 'require_supervisor_approval')
        }),
        ('Notification Settings', {
            'fields': ('days_before_training_reminder', 'notify_on_completion')
        }),
        ('Audit Information', {
            'fields': ('last_modified_by_guid', 'last_modified_at', 'created_at', 'updated_at', 'deleted_at', 'created_by', 'updated_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Allow only one TrainingSetting instance"""
        return not TrainingSetting.objects.exists()
