import base64
import binascii
import io
import mimetypes
import posixpath
import uuid
from pathlib import Path
from urllib.parse import quote

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import DatabaseError
from django.db.models import F, Q
from django.http import FileResponse
from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from utils.permissions import HasMethodPermission

from ppaa_portal.internal_portal_serializers import (
    PortalAnnouncementBriefSerializer,
    PortalAnnouncementSerializer,
    PortalAuditLogSerializer,
    PortalDocumentCategorySerializer,
    PortalDocumentSerializer,
    PortalEventBriefSerializer,
    PortalEventSerializer,
    PortalFAQBriefSerializer,
    PortalFAQSerializer,
    PortalPopupCardSerializer,
    PortalPrFlyerSerializer,
    PortalQuickLinkBriefSerializer,
    PortalQuickLinkSerializer,
    PortalTodoBriefSerializer,
    PortalTodoSerializer,
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
from ppaa_portal.dashboard_activity_filters import portal_dashboard_deadline_grace_q
from ppaa_portal.pagination import CustomPagination
from ppaa_portal.portal_audit_utils import (
    action_key_filter_q,
    date_filter_q,
    stats_payload as portal_audit_stats_payload,
)
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from utils.storage_env import minio_media_env_configured


def _store_uploaded_data_url(
    data_url: str,
    preferred_name: str,
    *,
    storage_subdir: str = "documents",
    max_bytes: int | None = None,
    old_file_path: str | None = None,
) -> tuple[str, str]:
    """
    Decode a data URL and persist bytes.

    When MinIO/S3 credentials are set, uses ``MinioStorage`` (native put_object to the media bucket).
    Otherwise falls back to ``default_storage`` (filesystem or S3Boto3, depending on settings).
    """
    if not data_url or ";base64," not in data_url:
        return "", ""
    _, b64 = data_url.split(";base64,", 1)
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Invalid file encoding")
    limit = 20 * 1024 * 1024 if max_bytes is None else max_bytes
    if len(raw) > limit:
        raise ValueError(f"File too large (max {limit // (1024 * 1024)}MB)")
    display_name = (preferred_name or "document").strip() or "document"
    suf = Path(display_name).suffix.lower()
    allowed_ext = {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".csv",
        ".zip",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
    }
    ext = suf if suf in allowed_ext and len(suf) <= 12 else ""
    old = (old_file_path or "").strip()

    if minio_media_env_configured():
        from utils.minio_storage import MinioStorage

        try:
            minio = MinioStorage()
            stored = minio.upload_base64_file(
                data_url,
                folder=f"internal_portal/{storage_subdir}",
                file_name=uuid.uuid4().hex,
                old_file_path=old,
            )
            if not stored:
                raise ValueError("Storage returned no object key after upload")
            # Same SDK/bucket as public routes — fail fast if object is not readable
            probe = minio.get_object_bytes(stored)
            if not probe:
                raise ValueError(
                    "Upload failed verification (empty object in MinIO). "
                    "Check AWS_STORAGE_BUCKET_NAME, AWS_S3_ENDPOINT_URL, and credentials."
                )
            return stored, display_name
        except Exception as e:
            raise ValueError(str(e)) from e

    if old:
        try:
            default_storage.delete(old)
        except Exception:
            pass
    key = f"internal_portal/{storage_subdir}/{uuid.uuid4().hex}{ext}"
    stored = default_storage.save(key, ContentFile(raw))
    return stored, display_name


def _binary_stream_for_storage_key(storage_key: str):
    """
    Readable binary stream for an object key.

    Internal portal uploads often use ``MinioStorage`` (native SDK) into
    ``AWS_STORAGE_BUCKET_NAME``; ``default_storage.open`` (boto3) can still 404 on
    some stacks. Prefer MinIO when env is complete, then django-storages.
    """
    key = (storage_key or "").strip()
    if not key:
        return None
    if minio_media_env_configured():
        try:
            from utils.minio_storage import MinioStorage

            raw = MinioStorage().get_object_bytes(key)
            if raw:
                return io.BytesIO(raw)
        except Exception:
            pass
    try:
        return default_storage.open(key, "rb")
    except Exception:
        return None


def _parse_optional_datetime(raw: str):
    """Parse ISO datetime from query params (e.g. ``datetime-local`` or ISO-8601)."""
    if not raw or not str(raw).strip():
        return None
    from datetime import datetime

    from django.utils import timezone as dj_tz
    from django.utils.dateparse import parse_datetime

    s = str(raw).strip()
    dt = parse_datetime(s)
    if dt is None:
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dj_tz.is_naive(dt):
        dt = dj_tz.make_aware(dt, dj_tz.get_current_timezone())
    return dt


def _strip_file_fields(data):
    if hasattr(data, "copy"):
        payload = data.copy()
    else:
        payload = dict(data)
    file_b64 = payload.pop("file_base64", None)
    file_name = payload.pop("file_name", None)
    return payload, file_b64, file_name


def _strip_quick_link_logo_fields(data):
    if hasattr(data, "copy"):
        payload = data.copy()
    else:
        payload = dict(data)
    logo_b64 = payload.pop("logo_base64", None)
    logo_name = payload.pop("logo_name", None)
    return payload, logo_b64, logo_name


def _strip_popup_es_image_fields(data):
    if hasattr(data, "copy"):
        payload = data.copy()
    else:
        payload = dict(data)
    img_b64 = payload.pop("es_image_base64", None)
    img_name = payload.pop("es_image_name", None)
    return payload, img_b64, img_name


def _strip_pr_flyer_image_fields(data):
    if hasattr(data, "copy"):
        payload = data.copy()
    else:
        payload = dict(data)
    img_b64 = payload.pop("image_base64", None)
    img_name = payload.pop("image_name", None)
    # Multipart form fields can be lists; CharField expects a string for video_url.
    if hasattr(payload, "dict"):
        payload = dict(payload.dict())
    elif not isinstance(payload, dict):
        payload = dict(payload)
    return payload, img_b64, img_name


class InternalPortalDashboardSummaryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        docs = (
            PortalDocument.objects.filter(is_deleted=False, status=PortalDocument.DocStatus.PUBLISHED)
            .select_related("category")
            .order_by("-updated_at")[:200]
        )
        ser = PortalDocumentSerializer(docs, many=True)
        events_qs = (
            PortalEvent.objects.filter(is_deleted=False)
            .filter(portal_dashboard_deadline_grace_q("end_date"))
            .order_by("start_date")[:120]
        )
        events_ser = PortalEventBriefSerializer(events_qs, many=True)
        faqs_qs = (
            PortalFAQ.objects.filter(is_deleted=False, is_active=True)
            .order_by("-updated_at")[:50]
        )
        faqs_ser = PortalFAQBriefSerializer(faqs_qs, many=True)
        ann_qs = (
            PortalAnnouncement.objects.filter(is_deleted=False, is_active=True)
            .filter(portal_dashboard_deadline_grace_q("end_date"))
            .order_by("-is_pinned", "-updated_at")[:40]
        )
        ann_ser = PortalAnnouncementBriefSerializer(ann_qs, many=True)
        todos_qs = (
            PortalTodo.objects.filter(is_deleted=False)
            .exclude(
                status__in=[
                    PortalTodo.Status.COMPLETED,
                    PortalTodo.Status.CANCELLED,
                ]
            )
            .filter(portal_dashboard_deadline_grace_q("due_date"))
            .select_related("department")
            .order_by("due_date", "-updated_at")[:40]
        )
        todos_ser = PortalTodoBriefSerializer(todos_qs, many=True)
        ql_qs = (
            PortalQuickLink.objects.filter(is_deleted=False, is_active=True)
            .order_by("name")[:60]
        )
        ql_ser = PortalQuickLinkBriefSerializer(
            ql_qs, many=True, context={"request": request}
        )
        pc = (
            PortalPopupCard.objects.filter(is_deleted=False, is_active=True)
            .order_by("-updated_at")
            .first()
        )
        popup_payload = (
            PortalPopupCardSerializer(pc, context={"request": request}).data if pc else None
        )
        pr_flyers_qs = (
            PortalPrFlyer.filter_visible_at(
                PortalPrFlyer.objects.filter(is_deleted=False, is_active=True).exclude(
                    image_key="", video_url=""
                )
            )
            .order_by("sort_order", "-updated_at")[:24]
        )
        pr_flyers_ser = PortalPrFlyerSerializer(
            pr_flyers_qs, many=True, context={"request": request}
        )
        payload = {
            "stats": {},
            "announcements": ann_ser.data,
            "events": events_ser.data,
            "faqs": faqs_ser.data,
            "quick_links": ql_ser.data,
            "documents": ser.data,
            "todos": todos_ser.data,
            "popup_card": popup_payload,
            "pr_flyers": pr_flyers_ser.data,
        }
        return CustomResponse.success(data=payload, message="Success")


class PortalDocumentCategoryView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PortalDocumentCategorySerializer

    def get(self, request, uid=None):
        try:
            if uid:
                row = PortalDocumentCategory.objects.filter(uid=uid, is_deleted=False).first()
                if not row:
                    raise NotFound("Category not found")
                return CustomResponse.success(data=self.serializer_class(row).data)

            qs = PortalDocumentCategory.objects.filter(is_deleted=False).order_by("name")
            active_only = str(request.GET.get("active_only", "")).lower() in (
                "1",
                "true",
                "yes",
            )
            if active_only:
                qs = qs.filter(is_active=True)
            search = (request.GET.get("search") or "").strip()
            if search:
                qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
            if qs.exists():
                return CustomPagination.paginate(view_class=self, results=qs, request=request)
            return CustomResponse.success(
                data=[],
                message="Success",
                pagination={
                    "page": int(request.GET.get("page", 1) or 1),
                    "page_size": int(request.GET.get("page_size", 10) or 10),
                    "total": 0,
                },
            )
        except NotFound as e:
            return CustomResponse.errors(message=str(e), code=STATUS_CODES["DATA_NOT_FOUND"])
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to load categories: {e!s}")

    def post(self, request):
        ser = self.serializer_class(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        ser.save(created_by=request.user, updated_by=request.user)
        return CustomResponse.success(data=ser.data)

    def put(self, request, uid):
        row = PortalDocumentCategory.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Category not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        ser = self.serializer_class(row, data=request.data, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        ser.save(updated_by=request.user)
        return CustomResponse.success(data=ser.data)

    def delete(self, request, uid):
        row = PortalDocumentCategory.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Category not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        PortalDocument.objects.filter(category=row).update(category=None)
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


def _attachment_content_disposition(filename: str) -> str:
    raw = (filename or "").strip() or "document"
    ascii_fallback = (
        "".join(
            c if 32 <= ord(c) < 127 and c not in '\\/:*?"<>|' else "_"
            for c in raw
        )
        .strip("._")
        or "document"
    )
    if len(ascii_fallback) > 180:
        ascii_fallback = ascii_fallback[:180]
    return (
        f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{quote(raw, safe="")}'
    )


class PortalDocumentDownloadView(APIView):
    """Stream file from MinIO/S3 using the same storage backend as upload (avoids presign key mismatches)."""

    permission_classes = [AllowAny]

    def get(self, request, uid):
        row = PortalDocument.objects.filter(uid=uid, is_deleted=False).first()
        if not row or not (row.file_key or "").strip():
            return Response(
                {
                    "status": STATUS_CODES["DATA_NOT_FOUND"],
                    "message": "Document or file not found",
                    "data": None,
                },
                status=http_status.HTTP_404_NOT_FOUND,
            )

        if not request.user.is_authenticated:
            if row.status != PortalDocument.DocStatus.PUBLISHED:
                return Response(
                    {
                        "status": STATUS_CODES["DATA_NOT_FOUND"],
                        "message": "Document or file not found",
                        "data": None,
                    },
                    status=http_status.HTTP_404_NOT_FOUND,
                )

        file_handle = _binary_stream_for_storage_key(row.file_key)
        if file_handle is None:
            return Response(
                {
                    "status": STATUS_CODES["DATA_NOT_FOUND"],
                    "message": "File is missing from storage. Re-upload the document.",
                    "data": None,
                },
                status=http_status.HTTP_404_NOT_FOUND,
            )

        PortalDocument.objects.filter(pk=row.pk).update(
            download_count=F("download_count") + 1
        )

        base_name = (
            (row.original_filename or "").strip()
            or posixpath.basename(row.file_key)
            or "document"
        )
        content_type, _ = mimetypes.guess_type(base_name)
        if not content_type:
            content_type = "application/octet-stream"

        response = FileResponse(file_handle, content_type=content_type)
        response["Content-Disposition"] = _attachment_content_disposition(base_name)
        return response


class PortalAnnouncementDownloadView(APIView):
    """Stream announcement attachment via the same storage backend as upload."""

    permission_classes = [AllowAny]

    def get(self, request, uid):
        base = PortalAnnouncement.objects.filter(uid=uid, is_deleted=False)
        if request.user.is_authenticated:
            row = base.first()
        else:
            row = (
                base.filter(is_active=True)
                .filter(portal_dashboard_deadline_grace_q("end_date"))
                .first()
            )
        if not row or not (row.file_key or "").strip():
            return Response(
                {
                    "status": STATUS_CODES["DATA_NOT_FOUND"],
                    "message": "Announcement or attachment not found",
                    "data": None,
                },
                status=http_status.HTTP_404_NOT_FOUND,
            )

        file_handle = _binary_stream_for_storage_key(row.file_key)
        if file_handle is None:
            return Response(
                {
                    "status": STATUS_CODES["DATA_NOT_FOUND"],
                    "message": "File is missing from storage. Re-upload the attachment.",
                    "data": None,
                },
                status=http_status.HTTP_404_NOT_FOUND,
            )

        base_name = (
            (row.original_filename or "").strip()
            or posixpath.basename(row.file_key)
            or "attachment"
        )
        content_type, _ = mimetypes.guess_type(base_name)
        if not content_type:
            content_type = "application/octet-stream"

        response = FileResponse(file_handle, content_type=content_type)
        response["Content-Disposition"] = _attachment_content_disposition(base_name)
        return response


class PortalDocumentView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PortalDocumentSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                row = PortalDocument.objects.filter(uid=uid, is_deleted=False).select_related("category").first()
                if not row:
                    raise NotFound("Document not found")
                return CustomResponse.success(data=self.serializer_class(row).data)

            qs = PortalDocument.objects.filter(is_deleted=False).select_related("category").order_by("-updated_at")
            search = (request.GET.get("search") or "").strip()
            category = (request.GET.get("category") or "").strip()
            if search:
                qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))
            if category:
                qs = qs.filter(category__uid=category)

            if qs.exists():
                return CustomPagination.paginate(view_class=self, results=qs, request=request)
            return CustomResponse.success(
                data=[],
                message="Success",
                pagination={
                    "page": int(request.GET.get("page", 1) or 1),
                    "page_size": int(request.GET.get("page_size", 10) or 10),
                    "total": 0,
                },
            )
        except NotFound as e:
            return CustomResponse.errors(message=str(e), code=STATUS_CODES["DATA_NOT_FOUND"])
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to load documents: {e!s}")

    def post(self, request):
        payload, file_b64, file_name = _strip_file_fields(request.data)
        ser = self.serializer_class(data=payload)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        instance = ser.save(created_by=request.user, updated_by=request.user)
        if file_b64:
            try:
                key, oname = _store_uploaded_data_url(file_b64, file_name)
                if key:
                    instance.file_key = key
                    instance.original_filename = oname
                    instance.save(update_fields=["file_key", "original_filename", "updated_at"])
            except ValueError as e:
                instance.delete()
                return CustomResponse.errors(
                    message=str(e),
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        return CustomResponse.success(data=self.serializer_class(instance).data)

    def put(self, request, uid):
        row = PortalDocument.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Document not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        payload, file_b64, file_name = _strip_file_fields(request.data)
        ser = self.serializer_class(row, data=payload, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        instance = ser.save(updated_by=request.user)
        if file_b64:
            try:
                key, oname = _store_uploaded_data_url(
                    file_b64,
                    file_name,
                    old_file_path=instance.file_key or None,
                )
                if key:
                    instance.file_key = key
                    instance.original_filename = oname
                    instance.save(update_fields=["file_key", "original_filename", "updated_at"])
            except ValueError as e:
                return CustomResponse.errors(
                    message=str(e),
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        return CustomResponse.success(data=self.serializer_class(instance).data)

    def delete(self, request, uid):
        row = PortalDocument.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Document not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class PortalEventView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PortalEventSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                row = PortalEvent.objects.filter(uid=uid, is_deleted=False).first()
                if not row:
                    raise NotFound("Event not found")
                return CustomResponse.success(data=self.serializer_class(row).data)

            qs = PortalEvent.objects.filter(is_deleted=False)
            search = (request.GET.get("search") or "").strip()
            if search:
                qs = qs.filter(
                    Q(title__icontains=search)
                    | Q(description__icontains=search)
                    | Q(location__icontains=search)
                )
            sd = _parse_optional_datetime(request.GET.get("start_date", ""))
            if sd is not None:
                qs = qs.filter(start_date__gte=sd)
            ed = _parse_optional_datetime(request.GET.get("end_date", ""))
            if ed is not None:
                qs = qs.filter(end_date__lte=ed)

            filters_raw = (request.GET.get("filters") or "").strip()
            tokens = [f.strip().upper() for f in filters_raw.split(",") if f.strip()]
            if tokens and "ALL" not in tokens:
                qs = qs.filter(event_type__in=tokens)

            qs = qs.order_by("-start_date")

            if qs.exists():
                return CustomPagination.paginate(view_class=self, results=qs, request=request)
            return CustomResponse.success(
                data=[],
                message="Success",
                pagination={
                    "page": int(request.GET.get("page", 1) or 1),
                    "page_size": int(request.GET.get("page_size", 10) or 10),
                    "total": 0,
                },
            )
        except NotFound as e:
            return CustomResponse.errors(message=str(e), code=STATUS_CODES["DATA_NOT_FOUND"])
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to load events: {e!s}")

    def post(self, request):
        ser = self.serializer_class(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        ser.save(created_by=request.user, updated_by=request.user)
        return CustomResponse.success(data=ser.data)

    def put(self, request, uid):
        row = PortalEvent.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Event not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        ser = self.serializer_class(row, data=request.data, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        ser.save(updated_by=request.user)
        return CustomResponse.success(data=ser.data)

    def delete(self, request, uid):
        row = PortalEvent.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Event not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class PortalFAQView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PortalFAQSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                row = PortalFAQ.objects.filter(uid=uid, is_deleted=False).first()
                if not row:
                    raise NotFound("FAQ not found")
                return CustomResponse.success(data=self.serializer_class(row).data)

            qs = PortalFAQ.objects.filter(is_deleted=False)
            search = (request.GET.get("search") or "").strip()
            if search:
                qs = qs.filter(
                    Q(question__icontains=search) | Q(answer__icontains=search)
                )

            filters_raw = (request.GET.get("filters") or "").strip()
            tokens = {f.strip().upper() for f in filters_raw.split(",") if f.strip()}
            if tokens and "ALL" not in tokens:
                if "ACTIVE" in tokens and "INACTIVE" not in tokens:
                    qs = qs.filter(is_active=True)
                elif "INACTIVE" in tokens and "ACTIVE" not in tokens:
                    qs = qs.filter(is_active=False)

            qs = qs.order_by("-updated_at")

            if qs.exists():
                return CustomPagination.paginate(view_class=self, results=qs, request=request)
            return CustomResponse.success(
                data=[],
                message="Success",
                pagination={
                    "page": int(request.GET.get("page", 1) or 1),
                    "page_size": int(request.GET.get("page_size", 10) or 10),
                    "total": 0,
                },
            )
        except NotFound as e:
            return CustomResponse.errors(message=str(e), code=STATUS_CODES["DATA_NOT_FOUND"])
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to load FAQs: {e!s}")

    def post(self, request):
        ser = self.serializer_class(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        ser.save(created_by=request.user, updated_by=request.user)
        return CustomResponse.success(data=ser.data)

    def put(self, request, uid):
        row = PortalFAQ.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="FAQ not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        ser = self.serializer_class(row, data=request.data, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        ser.save(updated_by=request.user)
        return CustomResponse.success(data=ser.data)

    def delete(self, request, uid):
        row = PortalFAQ.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="FAQ not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class PortalTodoView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PortalTodoSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                row = (
                    PortalTodo.objects.filter(uid=uid, is_deleted=False)
                    .select_related("department")
                    .first()
                )
                if not row:
                    raise NotFound("Todo not found")
                return CustomResponse.success(data=self.serializer_class(row).data)

            qs = PortalTodo.objects.filter(is_deleted=False).select_related("department")
            search = (request.GET.get("search") or "").strip()
            if search:
                qs = qs.filter(
                    Q(title__icontains=search) | Q(description__icontains=search)
                )

            status_param = (request.GET.get("status") or "").strip().upper()
            valid_status = {s.value for s in PortalTodo.Status}
            if status_param and status_param in valid_status:
                qs = qs.filter(status=status_param)

            priority_param = (request.GET.get("priority") or "").strip().upper()
            valid_priority = {p.value for p in PortalTodo.Priority}
            if priority_param and priority_param in valid_priority:
                qs = qs.filter(priority=priority_param)

            department_q = (request.GET.get("department") or "").strip()
            if department_q:
                qs = qs.filter(
                    Q(department__name__icontains=department_q)
                    | Q(department__uid__iexact=department_q)
                )

            filters_raw = (request.GET.get("filters") or "").strip()
            tokens = {f.strip().upper() for f in filters_raw.split(",") if f.strip()}
            status_tokens = tokens & valid_status
            priority_tokens = tokens & valid_priority
            if tokens and "ALL" not in tokens:
                if status_tokens:
                    qs = qs.filter(status__in=status_tokens)
                if priority_tokens:
                    qs = qs.filter(priority__in=priority_tokens)

            qs = qs.order_by("due_date", "-updated_at")

            if qs.exists():
                return CustomPagination.paginate(view_class=self, results=qs, request=request)
            return CustomResponse.success(
                data=[],
                message="Success",
                pagination={
                    "page": int(request.GET.get("page", 1) or 1),
                    "page_size": int(request.GET.get("page_size", 10) or 10),
                    "total": 0,
                },
            )
        except NotFound as e:
            return CustomResponse.errors(message=str(e), code=STATUS_CODES["DATA_NOT_FOUND"])
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to load todos: {e!s}")

    def post(self, request):
        ser = self.serializer_class(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        ser.save(created_by=request.user, updated_by=request.user)
        return CustomResponse.success(data=ser.data)

    def put(self, request, uid):
        row = PortalTodo.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Todo not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        ser = self.serializer_class(row, data=request.data, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        ser.save(updated_by=request.user)
        return CustomResponse.success(data=ser.data)

    def delete(self, request, uid):
        row = PortalTodo.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(message="Todo not found", code=STATUS_CODES["DATA_NOT_FOUND"])
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class PortalQuickLinkClickView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uid):
        n = PortalQuickLink.objects.filter(uid=uid, is_deleted=False).update(
            total_clicks=F("total_clicks") + 1
        )
        if not n:
            return CustomResponse.errors(
                message="Quick link not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        return Response(status=http_status.HTTP_204_NO_CONTENT)


class PortalQuickLinkView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PortalQuickLinkSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                row = PortalQuickLink.objects.filter(uid=uid, is_deleted=False).first()
                if not row:
                    raise NotFound("Quick link not found")
                return CustomResponse.success(
                    data=self.serializer_class(row, context={"request": request}).data
                )

            qs = PortalQuickLink.objects.filter(is_deleted=False)
            search = (request.GET.get("search") or "").strip()
            if search:
                qs = qs.filter(Q(name__icontains=search) | Q(url__icontains=search))

            filters_raw = (request.GET.get("filters") or "").strip()
            tokens = {f.strip().upper() for f in filters_raw.split(",") if f.strip()}
            if tokens and "ALL" not in tokens:
                if "ACTIVE" in tokens and "INACTIVE" not in tokens:
                    qs = qs.filter(is_active=True)
                elif "INACTIVE" in tokens and "ACTIVE" not in tokens:
                    qs = qs.filter(is_active=False)

            qs = qs.order_by("name")

            if qs.exists():
                return CustomPagination.paginate(view_class=self, results=qs, request=request)
            return CustomResponse.success(
                data=[],
                message="Success",
                pagination={
                    "page": int(request.GET.get("page", 1) or 1),
                    "page_size": int(request.GET.get("page_size", 10) or 10),
                    "total": 0,
                },
            )
        except NotFound as e:
            return CustomResponse.errors(message=str(e), code=STATUS_CODES["DATA_NOT_FOUND"])
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to load quick links: {e!s}")

    def post(self, request):
        payload, logo_b64, logo_name = _strip_quick_link_logo_fields(request.data)
        ser = self.serializer_class(data=payload, context={"request": request})
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        instance = ser.save(created_by=request.user, updated_by=request.user)
        if logo_b64:
            if not str(logo_b64).strip().lower().startswith("data:image/"):
                instance.delete()
                return CustomResponse.errors(
                    message="Logo must be an image file",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            try:
                key, oname = _store_uploaded_data_url(
                    logo_b64,
                    logo_name,
                    storage_subdir="quick_links",
                    max_bytes=5 * 1024 * 1024,
                )
                if key:
                    instance.logo_key = key
                    instance.logo_original_filename = oname
                    instance.save(
                        update_fields=["logo_key", "logo_original_filename", "updated_at"]
                    )
            except ValueError as e:
                instance.delete()
                return CustomResponse.errors(
                    message=str(e),
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        return CustomResponse.success(
            data=self.serializer_class(instance, context={"request": request}).data
        )

    def put(self, request, uid):
        row = PortalQuickLink.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Quick link not found", code=STATUS_CODES["DATA_NOT_FOUND"]
            )
        payload, logo_b64, logo_name = _strip_quick_link_logo_fields(request.data)
        ser = self.serializer_class(
            row, data=payload, partial=True, context={"request": request}
        )
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        instance = ser.save(updated_by=request.user)
        if logo_b64:
            if not str(logo_b64).strip().lower().startswith("data:image/"):
                return CustomResponse.errors(
                    message="Logo must be an image file",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            try:
                key, oname = _store_uploaded_data_url(
                    logo_b64,
                    logo_name,
                    storage_subdir="quick_links",
                    max_bytes=5 * 1024 * 1024,
                    old_file_path=instance.logo_key or None,
                )
                if key:
                    instance.logo_key = key
                    instance.logo_original_filename = oname
                    instance.save(
                        update_fields=["logo_key", "logo_original_filename", "updated_at"]
                    )
            except ValueError as e:
                return CustomResponse.errors(
                    message=str(e),
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        return CustomResponse.success(
            data=self.serializer_class(instance, context={"request": request}).data
        )

    def delete(self, request, uid):
        row = PortalQuickLink.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Quick link not found", code=STATUS_CODES["DATA_NOT_FOUND"]
            )
        if row.logo_key:
            if minio_media_env_configured():
                try:
                    from utils.minio_storage import MinioStorage

                    MinioStorage().remove_file(row.logo_key)
                except Exception:
                    pass
            try:
                default_storage.delete(row.logo_key)
            except Exception:
                pass
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class PortalPopupCardView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PortalPopupCardSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                row = PortalPopupCard.objects.filter(uid=uid, is_deleted=False).first()
                if not row:
                    raise NotFound("Popup card not found")
                return CustomResponse.success(
                    data=self.serializer_class(row, context={"request": request}).data
                )

            qs = PortalPopupCard.objects.filter(is_deleted=False)
            search = (request.GET.get("search") or "").strip()
            if search:
                qs = qs.filter(
                    Q(motivational_quote__icontains=search)
                    | Q(gratitude_message__icontains=search)
                )

            filters_raw = (request.GET.get("filters") or "").strip()
            tokens = {f.strip().upper() for f in filters_raw.split(",") if f.strip()}
            if tokens and "ALL" not in tokens:
                if "ACTIVE" in tokens and "INACTIVE" not in tokens:
                    qs = qs.filter(is_active=True)
                elif "INACTIVE" in tokens and "ACTIVE" not in tokens:
                    qs = qs.filter(is_active=False)

            qs = qs.order_by("-updated_at")

            if qs.exists():
                return CustomPagination.paginate(view_class=self, results=qs, request=request)
            return CustomResponse.success(
                data=[],
                message="Success",
                pagination={
                    "page": int(request.GET.get("page", 1) or 1),
                    "page_size": int(request.GET.get("page_size", 10) or 10),
                    "total": 0,
                },
            )
        except NotFound as e:
            return CustomResponse.errors(message=str(e), code=STATUS_CODES["DATA_NOT_FOUND"])
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to load popup cards: {e!s}")

    def post(self, request):
        payload, img_b64, img_name = _strip_popup_es_image_fields(request.data)
        ser = self.serializer_class(data=payload, context={"request": request})
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        instance = ser.save(created_by=request.user, updated_by=request.user)
        if img_b64:
            if not str(img_b64).strip().lower().startswith("data:image/"):
                instance.delete()
                return CustomResponse.errors(
                    message="ES image must be an image file",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            try:
                key, oname = _store_uploaded_data_url(
                    img_b64,
                    img_name,
                    storage_subdir="popup_cards",
                    max_bytes=5 * 1024 * 1024,
                )
                if key:
                    instance.es_image_key = key
                    instance.es_image_original_filename = oname
                    instance.save(
                        update_fields=[
                            "es_image_key",
                            "es_image_original_filename",
                            "updated_at",
                        ]
                    )
            except ValueError as e:
                instance.delete()
                return CustomResponse.errors(
                    message=str(e),
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        return CustomResponse.success(
            data=self.serializer_class(instance, context={"request": request}).data
        )

    def put(self, request, uid):
        row = PortalPopupCard.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Popup card not found", code=STATUS_CODES["DATA_NOT_FOUND"]
            )
        payload, img_b64, img_name = _strip_popup_es_image_fields(request.data)
        ser = self.serializer_class(
            row, data=payload, partial=True, context={"request": request}
        )
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        instance = ser.save(updated_by=request.user)
        if img_b64:
            if not str(img_b64).strip().lower().startswith("data:image/"):
                return CustomResponse.errors(
                    message="ES image must be an image file",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            try:
                key, oname = _store_uploaded_data_url(
                    img_b64,
                    img_name,
                    storage_subdir="popup_cards",
                    max_bytes=5 * 1024 * 1024,
                    old_file_path=instance.es_image_key or None,
                )
                if key:
                    instance.es_image_key = key
                    instance.es_image_original_filename = oname
                    instance.save(
                        update_fields=[
                            "es_image_key",
                            "es_image_original_filename",
                            "updated_at",
                        ]
                    )
            except ValueError as e:
                return CustomResponse.errors(
                    message=str(e),
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        return CustomResponse.success(
            data=self.serializer_class(instance, context={"request": request}).data
        )

    def delete(self, request, uid):
        row = PortalPopupCard.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Popup card not found", code=STATUS_CODES["DATA_NOT_FOUND"]
            )
        if row.es_image_key:
            try:
                default_storage.delete(row.es_image_key)
            except Exception:
                pass
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class PortalPrFlyerView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = PortalPrFlyerSerializer
    required_permissions = {
        "get": [
            "can_view_pr_flyer",
            "can_add_pr_flyer",
            "can_edit_pr_flyer",
            "can_delete_pr_flyer",
        ],
        "post": ["can_add_pr_flyer"],
        "put": ["can_edit_pr_flyer"],
        "delete": ["can_delete_pr_flyer"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                row = PortalPrFlyer.objects.filter(uid=uid, is_deleted=False).first()
                if not row:
                    raise NotFound("PR flyer not found")
                return CustomResponse.success(
                    data=self.serializer_class(row, context={"request": request}).data
                )

            qs = PortalPrFlyer.objects.filter(is_deleted=False)
            search = (request.GET.get("search") or "").strip()
            if search:
                qs = qs.filter(Q(title__icontains=search) | Q(caption__icontains=search))

            filters_raw = (request.GET.get("filters") or "").strip()
            tokens = {f.strip().upper() for f in filters_raw.split(",") if f.strip()}
            if tokens and "ALL" not in tokens:
                if "ACTIVE" in tokens and "INACTIVE" not in tokens:
                    qs = qs.filter(is_active=True)
                elif "INACTIVE" in tokens and "ACTIVE" not in tokens:
                    qs = qs.filter(is_active=False)

            qs = qs.order_by("sort_order", "-updated_at")

            if qs.exists():
                return CustomPagination.paginate(view_class=self, results=qs, request=request)
            return CustomResponse.success(
                data=[],
                message="Success",
                pagination={
                    "page": int(request.GET.get("page", 1) or 1),
                    "page_size": int(request.GET.get("page_size", 10) or 10),
                    "total": 0,
                },
            )
        except NotFound as e:
            return CustomResponse.errors(message=str(e), code=STATUS_CODES["DATA_NOT_FOUND"])
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to load PR flyers: {e!s}")

    def post(self, request):
        payload, img_b64, img_name = _strip_pr_flyer_image_fields(request.data)
        ser = self.serializer_class(data=payload, context={"request": request})
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        future_video = (ser.validated_data.get("video_url") or "").strip()
        future_has_image = bool(img_b64 and str(img_b64).strip())
        if not future_has_image and not future_video:
            return CustomResponse.errors(
                message="Add a poster image or a YouTube/Instagram video link.",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        if future_has_image and not str(img_b64).strip().lower().startswith("data:image/"):
            return CustomResponse.errors(
                message="File must be an image",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        instance = ser.save(created_by=request.user, updated_by=request.user)
        if not future_has_image:
            return CustomResponse.success(
                data=self.serializer_class(instance, context={"request": request}).data
            )
        try:
            key, oname = _store_uploaded_data_url(
                img_b64,
                img_name,
                storage_subdir="pr_flyers",
                max_bytes=8 * 1024 * 1024,
            )
            if key:
                instance.image_key = key
                instance.image_original_filename = oname
                instance.save(
                    update_fields=["image_key", "image_original_filename", "updated_at"]
                )
        except ValueError as e:
            instance.delete()
            return CustomResponse.errors(
                message=str(e),
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        return CustomResponse.success(
            data=self.serializer_class(instance, context={"request": request}).data
        )

    def put(self, request, uid):
        row = PortalPrFlyer.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="PR flyer not found", code=STATUS_CODES["DATA_NOT_FOUND"]
            )
        payload, img_b64, img_name = _strip_pr_flyer_image_fields(request.data)
        ser = self.serializer_class(
            row, data=payload, partial=True, context={"request": request}
        )
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        future_video = row.video_url or ""
        if "video_url" in ser.validated_data:
            future_video = (ser.validated_data.get("video_url") or "").strip()
        future_has_image = bool((row.image_key or "").strip()) or bool(
            img_b64 and str(img_b64).strip()
        )
        if not future_has_image and not future_video:
            return CustomResponse.errors(
                message="Each item needs a poster image or a YouTube/Instagram video link.",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        if img_b64 and not str(img_b64).strip().lower().startswith("data:image/"):
            return CustomResponse.errors(
                message="File must be an image",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        instance = ser.save(updated_by=request.user)
        if img_b64:
            if not str(img_b64).strip().lower().startswith("data:image/"):
                return CustomResponse.errors(
                    message="File must be an image",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            try:
                key, oname = _store_uploaded_data_url(
                    img_b64,
                    img_name,
                    storage_subdir="pr_flyers",
                    max_bytes=8 * 1024 * 1024,
                    old_file_path=instance.image_key or None,
                )
                if key:
                    instance.image_key = key
                    instance.image_original_filename = oname
                    instance.save(
                        update_fields=[
                            "image_key",
                            "image_original_filename",
                            "updated_at",
                        ]
                    )
            except ValueError as e:
                return CustomResponse.errors(
                    message=str(e),
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        return CustomResponse.success(
            data=self.serializer_class(instance, context={"request": request}).data
        )

    def delete(self, request, uid):
        row = PortalPrFlyer.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="PR flyer not found", code=STATUS_CODES["DATA_NOT_FOUND"]
            )
        if row.image_key:
            try:
                default_storage.delete(row.image_key)
            except Exception:
                pass
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


class PortalAnnouncementView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PortalAnnouncementSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                row = PortalAnnouncement.objects.filter(uid=uid, is_deleted=False).first()
                if not row:
                    raise NotFound("Announcement not found")
                return CustomResponse.success(data=self.serializer_class(row).data)

            qs = PortalAnnouncement.objects.filter(is_deleted=False)
            search = (request.GET.get("search") or "").strip()
            if search:
                qs = qs.filter(Q(title__icontains=search) | Q(content__icontains=search))

            filters_raw = (request.GET.get("filters") or "").strip()
            tokens = {f.strip().upper() for f in filters_raw.split(",") if f.strip()}
            prio_set = {"LOW", "MEDIUM", "HIGH", "URGENT"}
            if tokens and "ALL" not in tokens:
                prios = tokens & prio_set
                if prios:
                    qs = qs.filter(priority__in=prios)
                if "ACTIVE" in tokens and "INACTIVE" not in tokens:
                    qs = qs.filter(is_active=True)
                elif "INACTIVE" in tokens and "ACTIVE" not in tokens:
                    qs = qs.filter(is_active=False)

            qs = qs.order_by("-is_pinned", "-updated_at")

            if qs.exists():
                return CustomPagination.paginate(view_class=self, results=qs, request=request)
            return CustomResponse.success(
                data=[],
                message="Success",
                pagination={
                    "page": int(request.GET.get("page", 1) or 1),
                    "page_size": int(request.GET.get("page_size", 10) or 10),
                    "total": 0,
                },
            )
        except NotFound as e:
            return CustomResponse.errors(message=str(e), code=STATUS_CODES["DATA_NOT_FOUND"])
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to load announcements: {e!s}")

    def post(self, request):
        payload, file_b64, file_name = _strip_file_fields(request.data)
        ser = self.serializer_class(data=payload)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        instance = ser.save(created_by=request.user, updated_by=request.user)
        if file_b64:
            try:
                key, oname = _store_uploaded_data_url(
                    file_b64, file_name, storage_subdir="announcements"
                )
                if key:
                    instance.file_key = key
                    instance.original_filename = oname
                    instance.save(update_fields=["file_key", "original_filename", "updated_at"])
            except ValueError as e:
                instance.delete()
                return CustomResponse.errors(
                    message=str(e),
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        return CustomResponse.success(data=self.serializer_class(instance).data)

    def put(self, request, uid):
        row = PortalAnnouncement.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Announcement not found", code=STATUS_CODES["DATA_NOT_FOUND"]
            )
        payload, file_b64, file_name = _strip_file_fields(request.data)
        ser = self.serializer_class(row, data=payload, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        instance = ser.save(updated_by=request.user)
        if file_b64:
            try:
                key, oname = _store_uploaded_data_url(
                    file_b64,
                    file_name,
                    storage_subdir="announcements",
                    old_file_path=instance.file_key or None,
                )
                if key:
                    instance.file_key = key
                    instance.original_filename = oname
                    instance.save(update_fields=["file_key", "original_filename", "updated_at"])
            except ValueError as e:
                return CustomResponse.errors(
                    message=str(e),
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        return CustomResponse.success(data=self.serializer_class(instance).data)

    def delete(self, request, uid):
        row = PortalAnnouncement.objects.filter(uid=uid, is_deleted=False).first()
        if not row:
            return CustomResponse.errors(
                message="Announcement not found", code=STATUS_CODES["DATA_NOT_FOUND"]
            )
        row.is_deleted = True
        row.updated_by = request.user
        row.save(update_fields=["is_deleted", "updated_at", "updated_by"])
        return CustomResponse.success(data={"uid": str(row.uid)}, message="Deleted")


def _audit_log_parse_pk(uid: str):
    try:
        return int(str(uid).strip())
    except ValueError:
        return None


class PortalAuditLogView(APIView):
    """List and detail for ``AuditLog`` under ``/api/internal-portal/audit-logs``."""

    permission_classes = [IsAuthenticated]
    serializer_class = PortalAuditLogSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                pk = _audit_log_parse_pk(uid)
                if pk is None:
                    return CustomResponse.errors(
                        message="Audit log not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                row = (
                    AuditLog.objects.filter(pk=pk)
                    .select_related("user", "department")
                    .first()
                )
                if not row:
                    return CustomResponse.errors(
                        message="Audit log not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                return CustomResponse.success(data=self.serializer_class(row).data)

            qs = AuditLog.objects.all().select_related("user", "department").order_by("-created_at")

            qs = qs.filter(date_filter_q(request))

            action_key_param = (request.GET.get("action_key") or "").strip()
            if action_key_param:
                ak_q = action_key_filter_q(action_key_param)
                if ak_q is not None:
                    qs = qs.filter(ak_q)

            filters_raw = (request.GET.get("filters") or "").strip()
            tokens = [f.strip().upper() for f in filters_raw.split(",") if f.strip()]
            if tokens and "ALL" not in tokens:
                qs = qs.filter(action__in=tokens)

            model_name = (request.GET.get("model_name") or "").strip()
            if model_name:
                qs = qs.filter(model_name__icontains=model_name)
            action_param = (request.GET.get("action") or "").strip()
            if action_param and not action_key_param:
                qs = qs.filter(action__iexact=action_param)
            user_q = (request.GET.get("user") or "").strip()
            if user_q:
                qs = qs.filter(
                    Q(user__username__icontains=user_q)
                    | Q(user__email__icontains=user_q)
                    | Q(user__first_name__icontains=user_q)
                    | Q(user__last_name__icontains=user_q)
                    | Q(user__guid__iexact=user_q)
                )
            department_q = (request.GET.get("department") or "").strip()
            if department_q:
                qs = qs.filter(
                    Q(department__name__icontains=department_q)
                    | Q(department__uid__iexact=department_q)
                )

            search = (request.GET.get("search") or "").strip()
            if search:
                qs = qs.filter(
                    Q(model_name__icontains=search)
                    | Q(object_repr__icontains=search)
                    | Q(object_id__icontains=search)
                    | Q(user__username__icontains=search)
                    | Q(user__email__icontains=search)
                    | Q(user__first_name__icontains=search)
                    | Q(user__last_name__icontains=search)
                    | Q(action__icontains=search)
                )

            if qs.exists():
                return CustomPagination.paginate(view_class=self, results=qs, request=request)
            return CustomResponse.success(
                data=[],
                message="Success",
                pagination={
                    "page": int(request.GET.get("page", 1) or 1),
                    "page_size": int(request.GET.get("page_size", 10) or 10),
                    "total": 0,
                },
            )
        except DatabaseError:
            return CustomResponse.success(
                data=[],
                message="Success",
                pagination={
                    "page": int(request.GET.get("page", 1) or 1),
                    "page_size": int(request.GET.get("page_size", 10) or 10),
                    "total": 0,
                },
            )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to load audit logs: {e!s}")


class PortalAuditTrailStatsView(APIView):
    """GET /api/internal-portal/audit-logs/stats — summary cards & sidebar (RMS-style)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            return CustomResponse.success(data=portal_audit_stats_payload(), message="Success")
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to load audit stats: {e!s}")
