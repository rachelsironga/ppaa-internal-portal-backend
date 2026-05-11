from django.contrib import admin

from microservices.maoni.models import (
    MaoniCategory,
    MaoniSuggestion,
    MaoniSuggestionComment,
)


@admin.register(MaoniCategory)
class MaoniCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "uid", "is_active")


@admin.register(MaoniSuggestion)
class MaoniSuggestionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "priority",
        "submitted_by_guid",
        "department_received_at",
        "created_at",
    )
    list_filter = ("status", "priority")
    search_fields = ("title", "description")


@admin.register(MaoniSuggestionComment)
class MaoniSuggestionCommentAdmin(admin.ModelAdmin):
    list_display = ("suggestion", "commented_by_guid", "is_hr_reply", "created_at")
