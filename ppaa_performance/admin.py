from django.contrib import admin
from .models import (
    Objective, Target, Activity, QuarterlyData,
    KPIActual, ActivityDocument, PerformanceAuditLog,
)


@admin.register(Objective)
class ObjectiveAdmin(admin.ModelAdmin):
    list_display = ["title", "financial_year", "weight", "status", "created_at"]
    list_filter = ["financial_year", "status", "is_active"]
    search_fields = ["title", "description"]
    readonly_fields = ["uid", "approved_at", "created_at", "updated_at"]


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = ["title", "objective", "weight", "status", "kpi_name", "created_at"]
    list_filter = ["status", "objective__financial_year"]
    search_fields = ["title", "description", "kpi_name"]
    readonly_fields = ["uid", "approved_at", "created_at", "updated_at"]
    raw_id_fields = ["objective"]


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["title", "target", "weight", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["title", "description"]
    readonly_fields = ["uid", "approved_at", "created_at", "updated_at"]
    raw_id_fields = ["target"]


@admin.register(QuarterlyData)
class QuarterlyDataAdmin(admin.ModelAdmin):
    list_display = ["activity", "quarter", "financial_year", "actual_value", "computed_ai_percent", "is_locked"]
    list_filter = ["financial_year", "quarter", "is_locked"]
    readonly_fields = ["uid", "computed_ai_percent", "created_at", "updated_at"]
    raw_id_fields = ["activity"]


@admin.register(KPIActual)
class KPIActualAdmin(admin.ModelAdmin):
    list_display = ["target", "reporting_period", "financial_year", "actual_value", "computed_kpi_percent"]
    list_filter = ["financial_year"]
    readonly_fields = ["uid", "computed_kpi_percent", "created_at", "updated_at"]
    raw_id_fields = ["target"]


@admin.register(ActivityDocument)
class ActivityDocumentAdmin(admin.ModelAdmin):
    list_display = ["file_name", "activity", "file_type", "created_at"]
    list_filter = ["file_type"]
    search_fields = ["file_name", "description"]
    readonly_fields = ["uid", "created_at", "updated_at"]
    raw_id_fields = ["activity"]


@admin.register(PerformanceAuditLog)
class PerformanceAuditLogAdmin(admin.ModelAdmin):
    list_display = ["entity_type", "entity_id", "action", "user_id", "timestamp"]
    list_filter = ["entity_type", "action"]
    search_fields = ["entity_id", "comment"]
    readonly_fields = ["uid", "timestamp"]
    date_hierarchy = "timestamp"
