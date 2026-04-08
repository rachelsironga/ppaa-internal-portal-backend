from django.contrib import admin
from .models import Maoni, MaoniComment, MaoniCategory


@admin.register(Maoni)
class MaoniAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'priority', 'category', 'submitted_by_id', 'submitted_at', 'comment_count']
    list_filter = ['status', 'priority', 'category', 'submitted_at', 'is_deleted']
    search_fields = ['title', 'description']
    readonly_fields = ['uid', 'submitted_at', 'created_at', 'updated_at', 'comment_count']
    date_hierarchy = 'submitted_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'category', 'department_uid')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority')
        }),
        ('Submission Details', {
            'fields': ('submitted_by_id', 'submitted_at', 'comment_count')
        }),
        ('Metadata', {
            'fields': ('uid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Use the maoni database for queries"""
        qs = super().get_queryset(request)
        return qs.using('maoni')
    
    def save_model(self, request, obj, form, change):
        """Save to maoni database"""
        obj.save(using='maoni')
    
    def delete_model(self, request, obj):
        """Delete from maoni database"""
        obj.delete(using='maoni')


@admin.register(MaoniComment)
class MaoniCommentAdmin(admin.ModelAdmin):
    list_display = ['maoni', 'comment_preview', 'commented_by_id', 'is_anonymous', 'is_internal', 'parent_comment', 'created_at']
    list_filter = ['is_anonymous', 'is_internal', 'created_at', 'is_deleted']
    search_fields = ['comment', 'maoni__title']
    readonly_fields = ['uid', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def comment_preview(self, obj):
        return obj.comment[:100] + '...' if len(obj.comment) > 100 else obj.comment
    comment_preview.short_description = 'Comment Preview'
    
    def get_queryset(self, request):
        """Use the maoni database for queries"""
        qs = super().get_queryset(request)
        return qs.using('maoni')
    
    def save_model(self, request, obj, form, change):
        """Save to maoni database"""
        obj.save(using='maoni')
    
    def delete_model(self, request, obj):
        """Delete from maoni database"""
        obj.delete(using='maoni')


@admin.register(MaoniCategory)
class MaoniCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'is_public', 'is_active', 'order', 'created_at']
    list_filter = ['type', 'is_public', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['uid', 'created_at', 'updated_at']
    list_editable = ['order', 'is_public', 'is_active']
    
    def get_queryset(self, request):
        """Use the maoni database for queries"""
        qs = super().get_queryset(request)
        return qs.using('maoni')
    
    def save_model(self, request, obj, form, change):
        """Save to maoni database"""
        obj.save(using='maoni')
    
    def delete_model(self, request, obj):
        """Delete from maoni database"""
        obj.delete(using='maoni')
