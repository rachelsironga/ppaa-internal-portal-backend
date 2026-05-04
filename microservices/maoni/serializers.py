from rest_framework import serializers

from microservices.maoni.models import MaoniCategory, MaoniSuggestion, MaoniWorkflowSettings


class MaoniCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MaoniCategory
        fields = ("id", "uid", "name", "is_active")


class MaoniSuggestionWriteSerializer(serializers.ModelSerializer):
    """Create/update payload (category = PK)."""

    category = serializers.PrimaryKeyRelatedField(
        queryset=MaoniCategory.objects.filter(is_active=True),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = MaoniSuggestion
        fields = (
            "title",
            "description",
            "priority",
            "status",
            "category",
            "department_uid",
        )

    def validate_status(self, value):
        if value is None:
            return MaoniSuggestion.Status.DRAFT
        v = str(value).upper()
        valid = {c[0] for c in MaoniSuggestion.Status.choices}
        if v not in valid:
            raise serializers.ValidationError("Invalid status")
        return v

    def validate_priority(self, value):
        if value is None:
            return MaoniSuggestion.Priority.MEDIUM
        v = str(value).upper()
        valid = {c[0] for c in MaoniSuggestion.Priority.choices}
        if v not in valid:
            raise serializers.ValidationError("Invalid priority")
        return v

    def validate(self, attrs):
        status = attrs.get("status")
        if status is None and self.instance is not None:
            status = self.instance.status
        status = str(status or MaoniSuggestion.Status.DRAFT).upper()

        if "department_uid" in attrs:
            dept = attrs.get("department_uid")
        elif self.instance is not None:
            dept = self.instance.department_uid
        else:
            dept = None
        dept_str = (dept or "").strip() if dept is not None else ""

        if status != MaoniSuggestion.Status.DRAFT and not dept_str:
            raise serializers.ValidationError(
                {
                    "department_uid": (
                        "Please select which department your suggestion is for."
                    )
                }
            )
        return attrs


class MaoniSuggestionBriefSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    submitted_by_id = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()
    comment_count = serializers.IntegerField(read_only=True, default=0)
    last_comment_at = serializers.DateTimeField(read_only=True, allow_null=True)
    last_comment_by_id = serializers.IntegerField(read_only=True, allow_null=True)

    status = serializers.SerializerMethodField()

    class Meta:
        model = MaoniSuggestion
        fields = (
            "uid",
            "title",
            "description",
            "priority",
            "status",
            "category",
            "category_name",
            "department_uid",
            "submitted_by_id",
            "submitted_by_name",
            "submitted_at",
            "created_at",
            "updated_at",
            "comment_count",
            "last_comment_at",
            "last_comment_by_id",
        )

    def get_category_name(self, obj):
        if obj.category_id and obj.category:
            return obj.category.name
        return None

    def get_submitted_by_id(self, obj):
        if obj.submitted_by_id:
            return obj.submitted_by_id
        return None

    def get_submitted_by_name(self, obj):
        u = obj.submitted_by
        if not u:
            return None
        fn = u.get_full_name() if hasattr(u, "get_full_name") else ""
        return (fn or "").strip() or getattr(u, "username", None) or str(u.pk)

    def get_status(self, obj):
        raw = str(getattr(obj, "status", "")).upper()
        legacy_map = {
            "PENDING_REVIEW": "UNDER_HANDLER_REVIEW",
            "UNDER_CONSIDERATION": "ESCALATED_TO_REVIEWER",
            "APPROVED": "CLOSED_APPROVED",
            "IMPLEMENTED": "CLOSED_APPROVED",
            "REJECTED": "CLOSED_REJECTED",
        }
        return legacy_map.get(raw, raw)


class MaoniWorkflowSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaoniWorkflowSettings
        fields = ("escalation_days", "updated_at")


