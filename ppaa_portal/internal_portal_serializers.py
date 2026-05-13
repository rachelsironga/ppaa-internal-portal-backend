import re
import uuid as uuid_mod
from urllib.parse import parse_qs, urlparse

from django.conf import settings as django_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers

from ppaa_auth.models import Department
from ppaa_portal.portal_audit_utils import (
    audit_action_key,
    audit_action_label,
    audit_activity_subtitle,
    audit_activity_title,
    audit_http_status,
    audit_resource_label,
)
from ppaa_portal.models import (
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


class PortalDocumentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PortalDocumentCategory
        fields = ("uid", "name", "description", "is_active", "created_at", "updated_at")


class PortalDocumentSerializer(serializers.ModelSerializer):
    category = PortalDocumentCategorySerializer(read_only=True)
    category_uid = serializers.CharField(write_only=True, required=False, allow_blank=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = PortalDocument
        fields = (
            "uid",
            "title",
            "description",
            "category",
            "category_uid",
            "status",
            "download_count",
            "is_public",
            "tags",
            "file_key",
            "original_filename",
            "file_url",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "uid",
            "file_key",
            "download_count",
            "created_at",
            "updated_at",
        )

    def get_file_url(self, obj):
        # Downloads use JWT-authenticated GET …/documents/<uid>/download (streams via
        # default_storage — same key resolution as upload). Presigned MinIO URLs were
        # fragile for keys with spaces/special chars and AWS_LOCATION mismatches.
        return None

    def _parse_category_uid(self, raw):
        if raw is None:
            return None
        if isinstance(raw, str):
            raw = raw.strip()
        if raw == "":
            return None
        try:
            return uuid_mod.UUID(str(raw))
        except (ValueError, TypeError):
            raise serializers.ValidationError({"category_uid": "Invalid category id."})

    def create(self, validated_data):
        raw = validated_data.pop("category_uid", None)
        uid = self._parse_category_uid(raw)
        if uid is not None:
            cat = PortalDocumentCategory.objects.filter(uid=uid, is_deleted=False).first()
            if not cat:
                raise serializers.ValidationError({"category_uid": "Invalid category."})
            validated_data["category"] = cat
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "category_uid" in validated_data:
            raw = validated_data.pop("category_uid")
            uid = self._parse_category_uid(raw)
            if uid is None:
                validated_data["category"] = None
            else:
                cat = PortalDocumentCategory.objects.filter(uid=uid, is_deleted=False).first()
                if not cat:
                    raise serializers.ValidationError({"category_uid": "Invalid category."})
                validated_data["category"] = cat
        return super().update(instance, validated_data)


class PortalEventBriefSerializer(serializers.ModelSerializer):
    """Dashboard / calendar payload (no redundant ``event_type_choices`` per row)."""

    class Meta:
        model = PortalEvent
        fields = (
            "uid",
            "title",
            "description",
            "event_type",
            "start_date",
            "end_date",
            "location",
            "is_all_day",
            "is_public",
            "created_at",
        )


class PortalEventSerializer(serializers.ModelSerializer):
    event_type_choices = serializers.SerializerMethodField()

    class Meta:
        model = PortalEvent
        fields = (
            "uid",
            "title",
            "description",
            "event_type",
            "start_date",
            "end_date",
            "location",
            "is_all_day",
            "is_public",
            "event_type_choices",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uid", "created_at", "updated_at")

    def get_event_type_choices(self, obj):
        return [{"value": v, "label": lbl} for v, lbl in PortalEvent.EventType.choices]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "End date/time must be on or after start date/time."}
            )
        return attrs


class PortalFAQBriefSerializer(serializers.ModelSerializer):
    """Dashboard FAQ cards (question + answer snippet on the client)."""

    class Meta:
        model = PortalFAQ
        fields = ("uid", "question", "answer", "is_active")


class PortalFAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortalFAQ
        fields = (
            "uid",
            "question",
            "answer",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uid", "created_at", "updated_at")


class PortalAnnouncementBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortalAnnouncement
        fields = (
            "uid",
            "title",
            "content",
            "priority",
            "is_pinned",
            "start_date",
            "end_date",
            "is_active",
            "created_at",
            "file_key",
            "original_filename",
        )


class PortalAnnouncementSerializer(serializers.ModelSerializer):
    priority_choices = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = PortalAnnouncement
        fields = (
            "uid",
            "title",
            "content",
            "priority",
            "is_pinned",
            "is_active",
            "start_date",
            "end_date",
            "file_key",
            "original_filename",
            "file_url",
            "priority_choices",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uid", "file_key", "created_at", "updated_at")

    def get_priority_choices(self, obj):
        return [{"value": v, "label": lbl} for v, lbl in PortalAnnouncement.Priority.choices]

    def get_file_url(self, obj):
        # Use GET …/announcements/<uid>/download (JWT + default_storage) — same as portal documents.
        return None

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "End date/time must be on or after start date/time."}
            )
        return attrs


def _absolute_public_portal_asset_url(path: str, request) -> str:
    """
    Full URL for anonymous GET routes registered on the API site (e.g. ``/public/quick-links/…/logo/``).

    ``request.build_absolute_uri`` follows ``Host`` / proxy headers and often omits the API port or
    uses https on LAN → broken ``<img src>``. Prefer ``settings.PUBLIC_API_ORIGIN`` (see .env).
    """
    if not path:
        return ""
    p = path if str(path).startswith("/") else f"/{path}"
    origin = (getattr(django_settings, "PUBLIC_API_ORIGIN", None) or "").strip().rstrip("/")
    if origin:
        return f"{origin}{p}"
    if request:
        return request.build_absolute_uri(path)
    return p


def _absolute_public_quick_link_logo_url(obj, request):
    if not obj.logo_key:
        return ""
    path = reverse("public-quick-link-logo", kwargs={"uid": str(obj.uid)})
    return _absolute_public_portal_asset_url(path, request)


class PortalQuickLinkBriefSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()

    class Meta:
        model = PortalQuickLink
        fields = ("uid", "name", "url", "logo", "total_clicks", "is_active")

    def get_logo(self, obj):
        return _absolute_public_quick_link_logo_url(obj, self.context.get("request"))


class PortalQuickLinkSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()

    class Meta:
        model = PortalQuickLink
        fields = (
            "uid",
            "name",
            "url",
            "logo",
            "total_clicks",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uid", "total_clicks", "created_at", "updated_at")

    def get_logo(self, obj):
        return _absolute_public_quick_link_logo_url(obj, self.context.get("request"))


def _absolute_public_popup_es_image_url(obj, request):
    if not obj.es_image_key:
        return ""
    path = reverse("public-popup-card-es-image", kwargs={"uid": str(obj.uid)})
    return _absolute_public_portal_asset_url(path, request)


class PortalPopupCardSerializer(serializers.ModelSerializer):
    es_image_url = serializers.SerializerMethodField()

    class Meta:
        model = PortalPopupCard
        fields = (
            "uid",
            "motivational_quote",
            "gratitude_message",
            "es_image_url",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uid", "created_at", "updated_at")

    def get_es_image_url(self, obj):
        return _absolute_public_popup_es_image_url(obj, self.context.get("request"))


def _absolute_public_pr_flyer_image_url(obj, request):
    if not obj.image_key:
        return ""
    path = reverse("public-portal-pr-flyer-image", kwargs={"uid": str(obj.uid)})
    return _absolute_public_portal_asset_url(path, request)


def _youtube_video_id_from_url(url: str) -> str:
    """Return YouTube video id or empty string."""
    if not url or not str(url).strip():
        return ""
    try:
        p = urlparse(str(url).strip())
    except Exception:
        return ""
    host = (p.netloc or "").lower().split(":")[0]
    path = p.path or ""
    if host == "youtu.be" or host.endswith(".youtu.be"):
        seg = [s for s in path.split("/") if s]
        return seg[0] if seg else ""
    if "youtube" not in host:
        return ""
    if path.startswith("/shorts/") or path.startswith("/embed/"):
        parts = [s for s in path.split("/") if s]
        return parts[1] if len(parts) >= 2 else ""
    qs = parse_qs(p.query or "")
    v = (qs.get("v") or [None])[0]
    return v or ""


def _validate_pr_flyer_video_url(value: str) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    low = s.lower()
    if not (low.startswith("http://") or low.startswith("https://")):
        raise serializers.ValidationError("Video link must start with http:// or https://.")
    try:
        p = urlparse(s)
        netloc = (p.netloc or "").lower()
        path = p.path or ""
    except Exception as exc:
        raise serializers.ValidationError("Invalid URL.") from exc
    if "instagram.com" in netloc:
        if re.search(r"/(p|reel|reels|tv)/([^/?#]+)", path, re.I):
            return s
        raise serializers.ValidationError(
            "Use a full Instagram post, reel, or TV link (path must include /p/, /reel/, /reels/, or /tv/)."
        )
    if "youtu.be" in netloc or "youtube.com" in netloc:
        if _youtube_video_id_from_url(s):
            return s
        raise serializers.ValidationError("Could not read a YouTube video id from this link.")
    raise serializers.ValidationError("Only YouTube and Instagram video links are allowed.")


class PortalPrFlyerSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    video_thumb_url = serializers.SerializerMethodField()
    visible_until = serializers.DateTimeField(required=False, allow_null=True)
    video_url = serializers.CharField(
        required=False, allow_blank=True, max_length=2048, default=""
    )

    class Meta:
        model = PortalPrFlyer
        fields = (
            "uid",
            "title",
            "caption",
            "image_url",
            "video_url",
            "video_thumb_url",
            "sort_order",
            "visible_until",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uid", "created_at", "updated_at", "image_url", "video_thumb_url")

    def create(self, validated_data):
        from django.db.models import Max

        validated_data.pop("sort_order", None)
        current_max = (
            PortalPrFlyer.objects.filter(is_deleted=False)
            .aggregate(m=Max("sort_order"))
            .get("m")
        )
        next_order = (current_max if current_max is not None else 0) + 1
        validated_data["sort_order"] = next_order
        return super().create(validated_data)

    def validate_video_url(self, value):
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        if value is None:
            return ""
        return _validate_pr_flyer_video_url(str(value).strip())

    def get_image_url(self, obj):
        return _absolute_public_pr_flyer_image_url(obj, self.context.get("request"))

    def get_video_thumb_url(self, obj):
        vid = _youtube_video_id_from_url(obj.video_url or "")
        if vid:
            return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
        return ""


class PortalTodoDepartmentNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("uid", "name")


class PortalTodoBriefSerializer(serializers.ModelSerializer):
    department = PortalTodoDepartmentNestedSerializer(read_only=True)

    class Meta:
        model = PortalTodo
        fields = (
            "uid",
            "title",
            "description",
            "status",
            "priority",
            "department",
            "start_date",
            "due_date",
            "completed_at",
        )


class PortalTodoPublicBriefSerializer(PortalTodoBriefSerializer):
    """Public portal: PortalPage.jsx filters on ``is_active``; model has no flag — treat listed rows as active."""

    is_active = serializers.SerializerMethodField()

    class Meta(PortalTodoBriefSerializer.Meta):
        fields = (*PortalTodoBriefSerializer.Meta.fields, "is_active")

    def get_is_active(self, obj):
        return True


class PortalTodoSerializer(serializers.ModelSerializer):
    department = PortalTodoDepartmentNestedSerializer(read_only=True)
    department_uid = serializers.CharField(
        write_only=True, required=False, allow_null=True, allow_blank=True
    )

    class Meta:
        model = PortalTodo
        fields = (
            "uid",
            "title",
            "description",
            "status",
            "priority",
            "department",
            "department_uid",
            "start_date",
            "due_date",
            "completed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uid", "completed_at", "created_at", "updated_at")

    def _resolve_department(self, raw):
        if raw is None:
            return None
        if isinstance(raw, str) and not raw.strip():
            return None
        try:
            u = uuid_mod.UUID(str(raw).strip())
        except (ValueError, TypeError):
            raise serializers.ValidationError({"department_uid": "Invalid department id."})
        dept = Department.objects.filter(uid=u, is_deleted=False).first()
        if not dept:
            raise serializers.ValidationError({"department_uid": "Department not found."})
        return dept

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        due = attrs.get("due_date", getattr(self.instance, "due_date", None))
        if start and due and due < start:
            raise serializers.ValidationError(
                {"due_date": "Due date/time must be on or after start date/time."}
            )
        return attrs

    def create(self, validated_data):
        raw = validated_data.pop("department_uid", None)
        validated_data["department"] = self._resolve_department(raw)
        if validated_data.get("status") == PortalTodo.Status.COMPLETED:
            validated_data["completed_at"] = timezone.now()
        else:
            validated_data["completed_at"] = None
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "department_uid" in validated_data:
            raw = validated_data.pop("department_uid")
            validated_data["department"] = self._resolve_department(raw)
        status = validated_data.get("status", instance.status)
        if status == PortalTodo.Status.COMPLETED:
            if instance.status != PortalTodo.Status.COMPLETED:
                validated_data["completed_at"] = timezone.now()
        else:
            validated_data["completed_at"] = None
        return super().update(instance, validated_data)


class PortalAuditLogSerializer(serializers.ModelSerializer):
    """Audit rows for internal portal system logs (stable ``uid`` = string pk)."""

    uid = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    action_key = serializers.SerializerMethodField()
    action_label = serializers.SerializerMethodField()
    activity_title = serializers.SerializerMethodField()
    activity_subtitle = serializers.SerializerMethodField()
    http_status = serializers.SerializerMethodField()
    performed_by_name = serializers.SerializerMethodField()
    resource_label = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            "uid",
            "action",
            "action_key",
            "action_label",
            "activity_title",
            "activity_subtitle",
            "http_status",
            "performed_by_name",
            "resource_label",
            "model_name",
            "object_id",
            "object_repr",
            "changes",
            "user",
            "department",
            "ip_address",
            "user_agent",
            "created_at",
            "updated_at",
        )

    def get_uid(self, obj):
        return str(obj.pk)

    def get_action_key(self, obj):
        return audit_action_key(obj)

    def get_action_label(self, obj):
        return audit_action_label(obj)

    def get_activity_title(self, obj):
        return audit_activity_title(obj)

    def get_activity_subtitle(self, obj):
        return audit_activity_subtitle(obj)

    def get_http_status(self, obj):
        return audit_http_status(obj)

    def get_performed_by_name(self, obj):
        u = obj.user
        if not u:
            return "System"
        name = f"{u.first_name or ''} {u.last_name or ''}".strip()
        return name or (u.username or "") or "User"

    def get_resource_label(self, obj):
        return audit_resource_label(obj)

    def get_user(self, obj):
        u = obj.user
        if not u:
            return None
        return {
            "guid": str(u.guid),
            "username": u.username,
            "first_name": u.first_name or "",
            "last_name": u.last_name or "",
            "email": u.email or "",
        }

    def get_department(self, obj):
        d = obj.department
        if not d:
            return None
        return {"uid": str(d.uid), "name": d.name}
