from django.contrib import admin
from .models import (
    AuditLog,
    PortalAnnouncement,
    PortalDocument,
    PortalDocumentCategory,
    PortalEvent,
    PortalFAQ,
    PortalPopupCard,
    PortalPrFlyer,
    PortalQuickLink,
    PortalTodo,
)


@admin.register(PortalDocumentCategory)
class PortalDocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "description"]
    readonly_fields = ["uid", "created_at", "updated_at"]


@admin.register(PortalDocument)
class PortalDocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "status", "is_public", "download_count", "updated_at"]
    list_filter = ["status", "is_public", "category"]
    search_fields = ["title", "description", "tags"]
    readonly_fields = ["uid", "download_count", "created_at", "updated_at"]


@admin.register(PortalAnnouncement)
class PortalAnnouncementAdmin(admin.ModelAdmin):
    list_display = ["title", "priority", "is_pinned", "is_active", "start_date", "end_date", "updated_at"]
    list_filter = ["priority", "is_pinned", "is_active"]
    search_fields = ["title", "content"]
    readonly_fields = ["uid", "created_at", "updated_at"]


@admin.register(PortalEvent)
class PortalEventAdmin(admin.ModelAdmin):
    list_display = ["title", "event_type", "start_date", "end_date", "location", "is_public", "updated_at"]
    list_filter = ["event_type", "is_public"]
    search_fields = ["title", "description", "location"]
    readonly_fields = ["uid", "created_at", "updated_at"]


@admin.register(PortalFAQ)
class PortalFAQAdmin(admin.ModelAdmin):
    list_display = ["question", "is_active", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["question", "answer"]
    readonly_fields = ["uid", "created_at", "updated_at"]


@admin.register(PortalTodo)
class PortalTodoAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "priority", "due_date", "department", "updated_at"]
    list_filter = ["status", "priority", "department"]
    search_fields = ["title", "description"]
    readonly_fields = ["uid", "created_at", "updated_at"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["action", "model_name", "user", "department", "created_at"]
    list_filter = ["action", "model_name", "created_at"]
    search_fields = ["model_name", "object_repr", "user__username"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "created_at"


@admin.register(PortalQuickLink)
class PortalQuickLinkAdmin(admin.ModelAdmin):
    list_display = ["name", "url", "total_clicks", "is_active", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "url"]
    readonly_fields = ["uid", "total_clicks", "created_at", "updated_at"]


@admin.register(PortalPopupCard)
class PortalPopupCardAdmin(admin.ModelAdmin):
    list_display = ["uid", "is_active", "updated_at"]
    search_fields = ["motivational_quote", "gratitude_message"]
    readonly_fields = ["uid", "created_at", "updated_at"]


@admin.register(PortalPrFlyer)
class PortalPrFlyerAdmin(admin.ModelAdmin):
    list_display = ["uid", "title", "sort_order", "is_active", "updated_at"]
    search_fields = ["title", "caption", "video_url"]
    readonly_fields = ["uid", "created_at", "updated_at"]
