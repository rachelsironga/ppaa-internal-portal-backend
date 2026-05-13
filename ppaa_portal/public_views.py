"""
Unauthenticated JSON endpoints for the public PPAA portal landing page (PortalPage.jsx).

Wire under /public/… so TokenAuthMiddleware skips token checks (see ppaa_portal/middleware.py).
"""
import io
import mimetypes
import posixpath

from django.core.files.storage import default_storage
from django.db.models import F
from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.storage_env import minio_media_env_configured

from ppaa_portal.internal_portal_serializers import (
    PortalAnnouncementBriefSerializer,
    PortalDocumentSerializer,
    PortalEventBriefSerializer,
    PortalFAQBriefSerializer,
    PortalPopupCardSerializer,
    PortalPrFlyerSerializer,
    PortalQuickLinkBriefSerializer,
    PortalTodoPublicBriefSerializer,
)
from ppaa_portal.dashboard_activity_filters import portal_dashboard_deadline_grace_q
from ppaa_portal.models import (
    PortalAnnouncement,
    PortalDocument,
    PortalEvent,
    PortalFAQ,
    PortalPopupCard,
    PortalPrFlyer,
    PortalQuickLink,
    PortalTodo,
)


def _file_response_from_storage_key(
    storage_key: str, original_filename: str, fallback_basename: str
) -> FileResponse:
    """
    Serve bytes for a storage object key.

    Quick-link logos (and similar) are often written with ``MinioStorage`` while this
    view historically used ``default_storage`` (boto3). When MinIO env is complete,
    read with the native MinIO client first so the same bucket/object names resolve.
    """
    key = (storage_key or "").strip()
    if not key:
        raise Http404()

    base_name = (
        (original_filename or "").strip()
        or posixpath.basename(key)
        or fallback_basename
    )
    content_type, _ = mimetypes.guess_type(base_name)
    if not content_type:
        content_type = "image/png"

    if minio_media_env_configured():
        try:
            from utils.minio_storage import MinioStorage

            raw = MinioStorage().get_object_bytes(key)
            if raw:
                return FileResponse(io.BytesIO(raw), content_type=content_type)
        except Exception:
            pass

    try:
        fh = default_storage.open(key, "rb")
    except Exception:
        raise Http404() from None
    return FileResponse(fh, content_type=content_type)


class PublicPpaaDashboardView(APIView):
    """GET /public/ppaa-dashboard/ — aggregate payload for the public portal."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        # Documents: only published + marked public (PortalPage.jsx also filters client-side).
        docs_qs = (
            PortalDocument.objects.filter(
                is_deleted=False,
                status=PortalDocument.DocStatus.PUBLISHED,
                is_public=True,
            )
            .select_related("category")
            .order_by("-updated_at")[:200]
        )
        docs_ser = PortalDocumentSerializer(docs_qs, many=True)

        # Events: same scope as internal staff dashboard (calendar + modals).
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
        todos_ser = PortalTodoPublicBriefSerializer(todos_qs, many=True)

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
            "documents": docs_ser.data,
            "todos": todos_ser.data,
            "popup_card": popup_payload,
            "pr_flyers": pr_flyers_ser.data,
        }
        return Response({"data": payload})


class PublicQuickLinkLogoView(APIView):
    """GET /public/quick-links/<uid>/logo/ — serve stored logo for <img src> (no JWT)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, uid):
        row = (
            PortalQuickLink.objects.filter(uid=uid, is_deleted=False)
            .exclude(logo_key="")
            .first()
        )
        if not row:
            raise Http404()
        return _file_response_from_storage_key(
            row.logo_key,
            row.logo_original_filename or "",
            "logo.png",
        )


class PublicPopupCardEsImageView(APIView):
    """GET /public/popup-cards/<uid>/es-image/ — ES image for <img src> (no JWT)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, uid):
        row = (
            PortalPopupCard.objects.filter(uid=uid, is_deleted=False)
            .exclude(es_image_key="")
            .first()
        )
        if not row:
            raise Http404()
        return _file_response_from_storage_key(
            row.es_image_key,
            row.es_image_original_filename or "",
            "image.png",
        )


class PublicPortalPrFlyerImageView(APIView):
    """GET /public/pr-flyers/<uid>/image/ — flyer image for <img src> (no JWT)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, uid):
        row = (
            PortalPrFlyer.filter_visible_at(
                PortalPrFlyer.objects.filter(
                    uid=uid, is_deleted=False, is_active=True
                ).exclude(image_key="")
            )
            .first()
        )
        if not row:
            raise Http404()
        return _file_response_from_storage_key(
            row.image_key,
            row.image_original_filename or "",
            "flyer.png",
        )


class PublicQuickLinkClickView(APIView):
    """POST /public/quick-links/<uid>/click/ — best-effort click tracking (sendBeacon)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, uid):
        PortalQuickLink.objects.filter(uid=uid, is_deleted=False).update(
            total_clicks=F("total_clicks") + 1
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
