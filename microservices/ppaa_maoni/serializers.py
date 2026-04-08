from rest_framework import serializers
from django.utils import timezone
from .models import Maoni, MaoniComment, MaoniCategory
from ppaa_auth.models import User


class MaoniCategorySerializer(serializers.ModelSerializer):
    """Serializer for suggestion categories (area of concern)"""
    class Meta:
        model = MaoniCategory
        fields = ['id', 'uid', 'name', 'description', 'type', 'icon', 'color', 'order', 'is_public']
        read_only_fields = ['uid', 'id']


class MaoniCommentSerializer(serializers.ModelSerializer):
    """Serializer for suggestion replies/comments"""
    commented_by_name = serializers.SerializerMethodField()
    is_hr_reply = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = MaoniComment
        fields = [
            'uid', 'comment', 'commented_by_id', 'commented_by_name',
            'is_hr_reply', 'is_internal', 'parent_comment', 'replies',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uid', 'created_at', 'updated_at', 'commented_by_name', 'is_hr_reply', 'replies']
        extra_kwargs = {
            'parent_comment': {'required': False, 'allow_null': True},
            'maoni': {'required': True},
        }

    def get_commented_by_name(self, obj):
        """Get the name of the user who commented"""
        if obj.commented_by_id:
            try:
                user = User.objects.filter(id=obj.commented_by_id).first()
                if user:
                    return user.get_full_name() or user.username
            except:
                pass
        return "Anonymous"

    def get_is_hr_reply(self, obj):
        """Check if the comment is from an HR user"""
        if obj.commented_by_id:
            try:
                user = User.objects.filter(id=obj.commented_by_id).first()
                if user:
                    # Check if user has HR role (group name)
                    group_names = user.get_group_names()
                    return any('hr' in name.lower() for name in group_names)
            except:
                pass
        return False

    def get_replies(self, obj):
        """Get nested replies to this comment"""
        replies = MaoniComment.objects.filter(
            parent_comment=obj,
            is_deleted=False
        ).order_by('created_at')
        return MaoniCommentSerializer(replies, many=True).data


class MaoniSerializer(serializers.ModelSerializer):
    """Serializer for suggestions"""
    submitted_by_name = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    comment_count = serializers.IntegerField(read_only=True)
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = Maoni
        fields = [
            'uid', 'title', 'description', 'status', 'priority',
            'submitted_by_id', 'submitted_by_name', 'submitted_at',
            'comments', 'comment_count', 'created_at', 'updated_at',
            'category', 'category_name', 'department_uid'
        ]
        read_only_fields = ['uid', 'submitted_at', 'created_at', 'updated_at', 'comment_count', 'submitted_by_name', 'comments', 'category_name']
        extra_kwargs = {
            'category': {'required': False, 'allow_null': True},
            'department_uid': {'required': False, 'allow_null': True, 'allow_blank': True},
        }

    def get_submitted_by_name(self, obj):
        """Get the name of the user who submitted"""
        if obj.submitted_by_id:
            try:
                user = User.objects.filter(id=obj.submitted_by_id).first()
                if user:
                    return user.get_full_name() or user.username
            except:
                pass
        return "Anonymous"

    def get_comments(self, obj):
        """Get top-level comments (replies) for this suggestion"""
        comments = MaoniComment.objects.filter(
            maoni=obj,
            parent_comment__isnull=True,
            is_deleted=False
        ).order_by('created_at')
        return MaoniCommentSerializer(comments, many=True).data

    def get_category_name(self, obj):
        """Get category name"""
        return obj.category.name if obj.category else None

    def create(self, validated_data):
        """Create a new suggestion (supports DRAFT and SUBMITTED)"""
        request = self.context.get('request')

        # Determine desired status from payload; default to SUBMITTED
        requested_status = validated_data.get('status') or 'SUBMITTED'

        if request and request.user.is_authenticated:
            validated_data['submitted_by_id'] = request.user.id

        # Only set submitted_at automatically when status is SUBMITTED
        if requested_status == 'SUBMITTED':
            validated_data['status'] = 'SUBMITTED'
            validated_data['submitted_at'] = timezone.now()
        else:
            # Keep as DRAFT (or other allowed status) and do not set submitted_at
            validated_data['status'] = requested_status

        # Category is a ForeignKey; DRF will already convert a valid PK into a MaoniCategory instance.
        # Do NOT pop/convert it here (this breaks draft editing when frontend sends numeric PK).

        instance = super().create(validated_data)
        return instance

    def update(self, instance, validated_data):
        """Update an existing suggestion (supports DRAFT <-> SUBMITTED transitions)."""
        requested_status = validated_data.get('status')

        # If status is changing to SUBMITTED, set submitted_at
        if requested_status == 'SUBMITTED' and instance.status != 'SUBMITTED':
            validated_data['submitted_at'] = timezone.now()
        elif requested_status == 'DRAFT':
            # Keep drafts with no submitted_at
            validated_data['submitted_at'] = None

        return super().update(instance, validated_data)
