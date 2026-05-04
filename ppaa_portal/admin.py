from django.contrib import admin
from .models import (
    DocumentCategory, Document, Announcement, Event, FAQ,
    Notification, TodoList, AuditLog, QuickLink, PortalPopupCard,
)


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['uid', 'created_at', 'updated_at']


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'department', 'status', 'is_public', 'download_count', 'created_at']
    list_filter = ['status', 'is_public', 'category', 'department', 'created_at']
    search_fields = ['title', 'description', 'tags']
    readonly_fields = ['uid', 'download_count', 'created_at', 'updated_at']


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'priority', 'is_pinned', 'is_active', 'start_date', 'end_date']
    list_filter = ['priority', 'is_pinned', 'is_active', 'created_at']
    search_fields = ['title', 'content']
    readonly_fields = ['uid', 'created_at', 'updated_at']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_type', 'start_date', 'end_date', 'location', 'is_public']
    list_filter = ['event_type', 'is_public', 'start_date']
    search_fields = ['title', 'description', 'location']
    readonly_fields = ['uid', 'created_at', 'updated_at']


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['question', 'answer']
    readonly_fields = ['uid', 'created_at', 'updated_at']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'notification_type', 'is_read', 'read_at', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'user__username']
    readonly_fields = ['uid', 'read_at', 'created_at', 'updated_at']


@admin.register(TodoList)
class TodoListAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'priority', 'due_date', 'department', 'created_at']
    list_filter = ['status', 'priority', 'department', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['uid', 'completed_at', 'created_at', 'updated_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'model_name', 'user', 'department', 'created_at']
    list_filter = ['action', 'model_name', 'created_at']
    search_fields = ['model_name', 'object_repr', 'user__username']
    readonly_fields = ['uid', 'created_at']
    date_hierarchy = 'created_at'


@admin.register(QuickLink)
class QuickLinkAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'order', 'is_active', 'total_clicks', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'url']
    readonly_fields = ['uid', 'total_clicks', 'created_at', 'updated_at']


@admin.register(PortalPopupCard)
class PortalPopupCardAdmin(admin.ModelAdmin):
    list_display = ['uid', 'created_at']
    search_fields = ['motivational_quote', 'gratitude_message']
    readonly_fields = ['uid', 'created_at', 'updated_at']
