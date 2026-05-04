from rest_framework import serializers
from .models import (
    DocumentCategory, Document, Announcement, Event, FAQ,
    Notification, TodoList, AuditLog, QuickLink, PortalPopupCard
)
from ppaa_auth.models import Department, User
from ppaa_auth.serializers import UserSerializer, DepartmentSerializer


class DocumentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentCategory
        fields = ['uid', 'name', 'description', 'is_active', 
                  'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at']


class DocumentSerializer(serializers.ModelSerializer):
    category = DocumentCategorySerializer(read_only=True)
    category_uid = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    file_url = serializers.SerializerMethodField()
    file_path = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Document
        fields = ['uid', 'title', 'description', 'file_url', 'file_path', 'category', 'category_uid', 
                  'status', 'is_public', 'download_count', 
                  'tags', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'download_count', 'created_at', 'updated_at']

    def get_file_url(self, obj):
        """Generate presigned URL for file access"""
        if not obj.file_url:
            return None
        
        # Handle legacy full URLs (for backward compatibility)
        if obj.file_url.startswith('http://') or obj.file_url.startswith('https://'):
            from django.conf import settings
            # If it's a direct MinIO URL, extract path and generate presigned URL
            if settings.MEDIA_URL and settings.MEDIA_URL in obj.file_url:
                try:
                    object_path = obj.file_url.replace(settings.MEDIA_URL, "")
                    from ppaa_portal.services.minio.minio_helpers import get_presigned_url
                    presigned_url = get_presigned_url(object_path, expires_hours=24)
                    return presigned_url if presigned_url else obj.file_url
                except Exception:
                    return obj.file_url
            # If it's already a presigned URL, return as-is
            return obj.file_url
        
        # file_url is a path (new format), generate presigned URL
        try:
            from ppaa_portal.services.minio.minio_helpers import get_presigned_url
            presigned_url = get_presigned_url(obj.file_url, expires_hours=24)
            return presigned_url if presigned_url else None
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            return None

    def validate(self, data):
        category_uid = data.pop('category_uid', None)
        
        if category_uid:
            try:
                data['category'] = DocumentCategory.objects.get(uid=category_uid, is_deleted=False)
            except DocumentCategory.DoesNotExist:
                raise serializers.ValidationError({"category_uid": "Invalid category"})
        
        return data

    def create(self, validated_data):
        """Override create to handle file_path"""
        file_path = validated_data.pop('file_path', None)
        instance = super().create(validated_data)
        if file_path:
            instance.file_url = file_path
            instance.save(update_fields=['file_url'])
        return instance

    def update(self, instance, validated_data):
        """Override update to handle file_path"""
        file_path = validated_data.pop('file_path', None)
        instance = super().update(instance, validated_data)
        if file_path is not None:  # Allow setting to empty string/null
            instance.file_url = file_path if file_path else None
            instance.save(update_fields=['file_url'])
        return instance


class AnnouncementSerializer(serializers.ModelSerializer):
    priority_choices = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    # Write-only field to accept the MinIO object path from the API (we store it in model.file_url)
    file_path = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Announcement
        fields = ['uid', 'title', 'content', 'priority', 'priority_choices', 'is_pinned', 
                  'is_active', 'start_date', 'end_date', 'file_url', 'file_path', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at', 'priority_choices']

    def get_priority_choices(self, obj):
        """Return available priority choices"""
        return [{'value': choice[0], 'label': choice[1]} for choice in Announcement.PRIORITY_CHOICES]

    def get_file_url(self, obj):
        """Generate presigned URL for file access"""
        if not obj.file_url:
            return None
        
        # Handle legacy full URLs (for backward compatibility)
        if obj.file_url.startswith('http://') or obj.file_url.startswith('https://'):
            from django.conf import settings
            # If it's a direct MinIO URL, extract path and generate presigned URL
            if settings.MEDIA_URL and settings.MEDIA_URL in obj.file_url:
                try:
                    object_path = obj.file_url.replace(settings.MEDIA_URL, "")
                    from ppaa_portal.services.minio.minio_helpers import get_presigned_url
                    presigned_url = get_presigned_url(object_path, expires_hours=24)
                    return presigned_url if presigned_url else obj.file_url
                except Exception:
                    return obj.file_url
            # If it's already a presigned URL, return as-is
            return obj.file_url
        
        # file_url is a path (new format), generate presigned URL
        try:
            from ppaa_portal.services.minio.minio_helpers import get_presigned_url
            presigned_url = get_presigned_url(obj.file_url, expires_hours=24)
            return presigned_url if presigned_url else None
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            return None

    def create(self, validated_data):
        # Persist uploaded file path into model.file_url
        file_path = validated_data.pop("file_path", None)
        if file_path:
            validated_data["file_url"] = file_path
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Persist uploaded file path into model.file_url
        file_path = validated_data.pop("file_path", None)
        if file_path:
            validated_data["file_url"] = file_path
        return super().update(instance, validated_data)


class EventSerializer(serializers.ModelSerializer):
    event_type_choices = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = ['uid', 'title', 'description', 'event_type', 'event_type_choices', 'start_date', 'end_date',
                  'location', 'is_all_day', 'is_public', 'file_url',
                  'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at', 'event_type_choices']

    def get_event_type_choices(self, obj):
        """Return available event type choices"""
        return [{'value': choice[0], 'label': choice[1]} for choice in Event.EVENT_TYPE_CHOICES]


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ['uid', 'question', 'answer', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at']


class NotificationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_uid = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = Notification
        fields = ['uid', 'user', 'user_uid', 'title', 'message', 'notification_type',
                  'is_read', 'read_at', 'link', 'related_object_type', 'related_object_id',
                  'created_at', 'updated_at']
        read_only_fields = ['uid', 'read_at', 'created_at', 'updated_at']

    def validate(self, data):
        user_uid = data.pop('user_uid', None)
        if user_uid:
            try:
                data['user'] = User.objects.get(guid=user_uid, is_deleted=False)
            except User.DoesNotExist:
                raise serializers.ValidationError({"user_uid": "Invalid user"})
        return data


class TodoListSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(read_only=True)
    department_uid = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = TodoList
        fields = ['uid', 'title', 'description', 'status', 'priority',
                  'start_date', 'due_date', 'completed_at', 'department', 'department_uid', 'is_active']
        read_only_fields = ['uid', 'completed_at', 'is_active']

    def validate(self, data):
        department_uid = data.pop('department_uid', None)
        
        if department_uid:
            try:
                data['department'] = Department.objects.get(uid=department_uid, is_deleted=False)
            except Department.DoesNotExist:
                raise serializers.ValidationError({"department_uid": "Invalid department"})
        else:
            # Explicitly set department to None when department_uid is not provided or is None
            # This allows clearing/removing the department on update
            data['department'] = None
        
        return data


class AuditLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = ['uid', 'user', 'action', 'model_name', 'object_id', 'object_repr',
                  'changes', 'ip_address', 'user_agent', 'department', 'created_at']
        read_only_fields = ['uid', 'created_at']


class QuickLinkSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()
    logo_path = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = QuickLink
        fields = ['uid', 'name', 'url', 'logo', 'logo_path',
                  'is_active', 'total_clicks']
        read_only_fields = ['uid', 'total_clicks']

    def create(self, validated_data):
        """Override create to handle logo_path"""
        logo_path = validated_data.pop('logo_path', None)
        instance = super().create(validated_data)
        if logo_path:
            instance.logo = logo_path
            instance.save()
        return instance

    def update(self, instance, validated_data):
        """Override update to handle logo_path"""
        logo_path = validated_data.pop('logo_path', None)
        instance = super().update(instance, validated_data)
        if logo_path is not None:  # Allow setting to None/empty
            instance.logo = logo_path if logo_path else None
            instance.save()
        return instance

    def get_logo(self, obj):
        """Generate presigned URL for logo access"""
        if not obj.logo:
            return None
        
        # Handle legacy full URLs (for backward compatibility)
        if obj.logo.startswith('http://') or obj.logo.startswith('https://'):
            from django.conf import settings
            # If it's a direct MinIO URL, extract path and generate presigned URL
            if settings.MEDIA_URL and settings.MEDIA_URL in obj.logo:
                try:
                    object_path = obj.logo.replace(settings.MEDIA_URL, "")
                    from ppaa_portal.services.minio.minio_helpers import get_presigned_url
                    presigned_url = get_presigned_url(object_path, expires_hours=24)
                    return presigned_url if presigned_url else obj.logo
                except Exception:
                    return obj.logo
            # If it's already a presigned URL, return as-is
            return obj.logo
        
        # logo is a path (new format), generate presigned URL
        try:
            from ppaa_portal.services.minio.minio_helpers import get_presigned_url
            presigned_url = get_presigned_url(obj.logo, expires_hours=24)
            return presigned_url if presigned_url else None
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            return None


class PortalPopupCardSerializer(serializers.ModelSerializer):
    """Popup card: motivational quote, gratitude, ES image (presigned)."""
    es_image_url = serializers.SerializerMethodField()
    es_image_base64 = serializers.CharField(write_only=True, required=False, allow_blank=True)
    es_image_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    es_image_path = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = PortalPopupCard
        fields = [
            'uid', 'motivational_quote', 'gratitude_message',
            'es_image_url', 'es_image_base64', 'es_image_name', 'es_image_path',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uid', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data.pop('es_image_base64', None)
        validated_data.pop('es_image_name', None)
        path = validated_data.pop('es_image_path', None)
        instance = super().create(validated_data)
        if path:
            instance.es_image_path = path
            instance.save(update_fields=['es_image_path'])
        return instance

    def update(self, instance, validated_data):
        validated_data.pop('es_image_base64', None)
        validated_data.pop('es_image_name', None)
        path = validated_data.pop('es_image_path', None)
        instance = super().update(instance, validated_data)
        if path is not None:
            instance.es_image_path = path or None
            instance.save(update_fields=['es_image_path'])
        return instance

    def get_es_image_url(self, obj):
        if not obj.es_image_path:
            return None
        if obj.es_image_path.startswith('http://') or obj.es_image_path.startswith('https://'):
            return obj.es_image_path
        try:
            from ppaa_portal.services.minio.minio_helpers import get_presigned_url
            return get_presigned_url(obj.es_image_path, expires_hours=24)
        except Exception:
            return obj.es_image_path
