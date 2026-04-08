from django.db import transaction
from django.db.models import F
from django.db.models import Q
from django.utils import timezone
from django.core.cache import cache
from rest_framework import permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound

from .models import (
    DocumentCategory, Document, Announcement, Event, FAQ,
    Notification, TodoList, AuditLog, QuickLink, PortalPopupCard
)
from .serializers import (
    DocumentCategorySerializer, DocumentSerializer, AnnouncementSerializer,
    EventSerializer, FAQSerializer, NotificationSerializer, TodoListSerializer,
    AuditLogSerializer, QuickLinkSerializer, PortalPopupCardSerializer
)
from .pagination import CustomPagination
from .response_codes import CustomResponse, STATUS_CODES
from ppaa_auth.models import Department, User
from utils.permissions import HasMethodPermission
from utils.minio_storage import MinioStorage
from django.conf import settings


def _build_portal_dashboard_payload(include_public_only=False):
    """Build a lightweight portal dashboard payload for public/internal pages."""
    now = timezone.now()
    today = now.date()

    announcements_qs = Announcement.objects.filter(
        is_deleted=False,
        is_active=True,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=now)
    ).only(
        "uid", "title", "content", "priority", "is_pinned",
        "is_active", "start_date", "end_date", "file_url",
        "created_at", "updated_at"
    ).order_by("-is_pinned", "start_date", "-created_at")[:5]

    documents_filter = {"is_deleted": False}
    if include_public_only:
        documents_filter["is_public"] = True

    documents_qs = Document.objects.filter(**documents_filter).select_related("category").only(
        "uid", "title", "description", "file_url", "category__uid",
        "category__name", "category__description", "status",
        "is_public", "download_count", "tags", "created_at", "updated_at"
    ).order_by("-created_at")[:5]

    events_base_qs = Event.objects.filter(
        is_deleted=False,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=now)
    )
    events_qs = events_base_qs.only(
        "uid", "title", "description", "event_type",
        "start_date", "end_date", "location", "is_all_day",
        "is_public", "file_url", "created_at", "updated_at"
    ).order_by("start_date")[:20]

    faqs_qs = FAQ.objects.filter(
        is_deleted=False,
        is_active=True,
    ).only(
        "uid", "question", "answer", "is_active", "created_at", "updated_at"
    ).order_by("-created_at")[:5]

    quick_links_qs = QuickLink.objects.filter(
        is_deleted=False,
        is_active=True,
    ).only(
        "uid", "name", "url", "logo", "is_active", "total_clicks"
    ).order_by("name")[:12]

    todos_qs = TodoList.objects.filter(
        is_deleted=False,
        is_active=True,
    ).exclude(status__in=["COMPLETED", "CANCELLED"]).filter(
        Q(due_date__isnull=True) | Q(due_date__gte=today)
    ).select_related("department").order_by(
        "start_date", "due_date", "-created_at"
    )[:10]

    announcements = AnnouncementSerializer(announcements_qs, many=True).data
    documents = DocumentSerializer(documents_qs, many=True).data
    events = EventSerializer(events_qs, many=True).data
    faqs = FAQSerializer(faqs_qs, many=True).data
    quick_links = QuickLinkSerializer(quick_links_qs, many=True).data
    todos = TodoListSerializer(todos_qs, many=True).data

    popup_card_qs = PortalPopupCard.objects.filter(
        is_deleted=False,
    ).only(
        "uid", "motivational_quote", "gratitude_message",
        "es_image_path", "created_at", "updated_at"
    ).order_by("-created_at")[:1]
    popup_card = PortalPopupCardSerializer(popup_card_qs[0]).data if popup_card_qs else None

    announcements_base = Announcement.objects.filter(
        is_deleted=False, is_active=True
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=now))

    upcoming_events_count = events_base_qs.filter(start_date__gte=now).count()

    data = {
        "announcements": announcements,
        "documents": documents,
        "events": events,
        "faqs": faqs,
        "quick_links": quick_links,
        "todos": todos,
        "stats": {
            "totalAnnouncements": announcements_base.count(),
            "totalDocuments": Document.objects.filter(is_deleted=False).count(),
            "totalEvents": Event.objects.filter(is_deleted=False).count(),
            "totalFAQs": FAQ.objects.filter(is_deleted=False).count(),
            "totalQuickLinks": QuickLink.objects.filter(is_deleted=False).count(),
            "activeTodos": len(todos),
            "pinnedAnnouncements": announcements_base.filter(is_pinned=True).count(),
            "upcomingEvents": upcoming_events_count,
        },
        "popup_card": popup_card,
    }
    return data


class PublicPPaaDashboardView(APIView):
    """
    Public (unauthenticated) summary of PPAA Internal Portal dashboard data.
    Returns limited, read-only slices of announcements, documents, events, FAQs,
    quick links and todos, plus basic statistics.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        try:
            cache_key = "public_ppaa_dashboard_v1"
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return CustomResponse.success(data=cached_data)
            data = _build_portal_dashboard_payload(include_public_only=True)

            cache.set(cache_key, data, timeout=120)

            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to build public dashboard: {str(e)}"
            )


class InternalPortalDashboardSummaryView(APIView):
    """Authenticated summary endpoint for the internal portal dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            cache_key = "internal_portal_dashboard_summary_v1"
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return CustomResponse.success(data=cached_data)

            data = _build_portal_dashboard_payload(include_public_only=False)
            cache.set(cache_key, data, timeout=60)
            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to build internal portal dashboard: {str(e)}"
            )


def create_audit_log(request, action, model_name, obj=None, changes=None):
    """
    Helper to safely create an AuditLog entry.
    This should NEVER break the main request flow, so all exceptions are swallowed.
    """
    try:
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None

        # Try to resolve the user's current department (if any) using User.get_position()
        department = None
        try:
            if user and hasattr(user, "get_position") and callable(user.get_position):
                position = user.get_position() or {}
                dept_uid = position.get("department_uid")
                if dept_uid:
                    department = Department.objects.filter(uid=dept_uid, is_deleted=False).first()
        except Exception:
            # If anything goes wrong while resolving department, skip it
            department = None

        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500] if request.META.get("HTTP_USER_AGENT") else ""

        AuditLog.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            object_id=getattr(obj, "uid", None) if obj is not None else None,
            object_repr=str(obj)[:200] if obj is not None else None,
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
            department=department,
            # created_by/updated_by are ForeignKeys (see migrations), so pass the user object (not user.id)
            created_by=user if user else None,
            updated_by=user if user else None,
        )
    except Exception:
        # Never interrupt the main request because of logging failures
        pass


class DocumentCategoryView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = DocumentCategorySerializer
    required_permissions = {
        "get": ["can_view_document_category"],
        "post": ["can_add_document_category"],
        "put": ["can_edit_document_category"],
        "delete": ["can_delete_document_category"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                category = DocumentCategory.objects.filter(uid=uid, is_deleted=False).first()
                if not category:
                    return CustomResponse.errors(
                        message="Document category not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                
                # Log view action
                create_audit_log(
                    request=request,
                    action="VIEW",
                    model_name="DocumentCategory",
                    obj=category,
                )
                
                serializer = self.serializer_class(category)
                return CustomResponse.success(data=serializer.data)
            else:
                categories = DocumentCategory.objects.filter(is_deleted=False).order_by('name')
                serializer = self.serializer_class(categories, many=True)
                return CustomResponse.success(data=serializer.data)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve categories: {str(e)}")

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    category = serializer.save(created_by=request.user, updated_by=request.user)

                    # Log create action
                    create_audit_log(
                        request=request,
                        action="CREATE",
                        model_name="DocumentCategory",
                        obj=category,
                        changes={"data": serializer.data},
                    )

                    return CustomResponse.success(
                        message="Document category created successfully",
                        data=serializer.data
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to create category: {str(e)}")

    def put(self, request, uid):
        try:
            with transaction.atomic():
                category = DocumentCategory.objects.filter(uid=uid, is_deleted=False).first()
                if not category:
                    return CustomResponse.errors(
                        message="Document category not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                old_repr = self.serializer_class(category).data
                serializer = self.serializer_class(category, data=request.data, partial=True)
                if serializer.is_valid():
                    updated_category = serializer.save(updated_by=request.user)

                    # Log update action
                    create_audit_log(
                        request=request,
                        action="UPDATE",
                        model_name="DocumentCategory",
                        obj=updated_category,
                        changes={
                            "before": old_repr,
                            "after": serializer.data,
                        },
                    )

                    return CustomResponse.success(data=serializer.data)
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to update category: {str(e)}")

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                category = DocumentCategory.objects.filter(uid=uid, is_deleted=False).first()
                if not category:
                    return CustomResponse.errors(
                        message="Document category not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                category.is_deleted = True
                category.deleted_by = request.user
                category.deleted_at = timezone.now()
                category.save()

                # Log delete action
                create_audit_log(
                    request=request,
                    action="DELETE",
                    model_name="DocumentCategory",
                    obj=category,
                )

                return CustomResponse.success(message="Category deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to delete category: {str(e)}")


class DocumentView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = DocumentSerializer
    required_permissions = {
        "get": ["can_view_document"],
        "post": ["can_add_document"],
        "put": ["can_edit_document"],
        "delete": ["can_delete_document"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                document = Document.objects.filter(uid=uid, is_deleted=False).first()
                if not document:
                    return CustomResponse.errors(
                        message="Document not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                # Increment download count if viewing
                document.download_count += 1
                document.save(update_fields=['download_count'])

                # Log view/download action
                create_audit_log(
                    request=request,
                    action="VIEW",
                    model_name="Document",
                    obj=document,
                )

                serializer = self.serializer_class(document)
                return CustomResponse.success(data=serializer.data)
            else:
                search = request.GET.get('search', '')
                category_uid = request.GET.get('category', '')
                department_uid = request.GET.get('department', '')
                
                documents = Document.objects.filter(is_deleted=False)
                
                if search:
                    documents = documents.filter(
                        Q(title__icontains=search) | Q(description__icontains=search) | Q(tags__icontains=search)
                    )
                if category_uid:
                    documents = documents.filter(category__uid=category_uid)
                if department_uid:
                    documents = documents.filter(department__uid=department_uid)
                
                documents = documents.order_by('-created_at')
                return CustomPagination.paginate(view_class=self, results=documents, request=request)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve documents: {str(e)}")

    def post(self, request):
        try:
            with transaction.atomic():
                data = request.data.copy()
                
                # Handle file upload if provided
                file_base64 = data.get('file_base64', '')
                if file_base64:
                    minio = MinioStorage()
                    file_name = data.get('file_name', f"document_{timezone.now().strftime('%Y%m%d%H%M%S')}")
                    file_path = minio.upload_base64_file(
                        file_base64,
                        folder="documents",
                        file_name=file_name,
                        old_file_path=None
                    )
                    # Store only the file path (object name), presigned URLs will be generated in serializer
                    data['file_path'] = file_path
                
                serializer = self.serializer_class(data=data)
                if serializer.is_valid():
                    document = serializer.save(created_by=request.user, updated_by=request.user)

                    # Log create action
                    create_audit_log(
                        request=request,
                        action="CREATE",
                        model_name="Document",
                        obj=document,
                        changes={"data": serializer.data},
                    )

                    return CustomResponse.success(
                        message="Document created successfully",
                        data=serializer.data
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to create document: {str(e)}")

    def put(self, request, uid):
        try:
            with transaction.atomic():
                document = Document.objects.filter(uid=uid, is_deleted=False).first()
                if not document:
                    return CustomResponse.errors(
                        message="Document not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                
                data = request.data.copy()
                
                # Handle file upload if provided
                file_base64 = data.get('file_base64', '')
                if file_base64:
                    minio = MinioStorage()
                    file_name = data.get('file_name', f"document_{timezone.now().strftime('%Y%m%d%H%M%S')}")
                    # Extract old file path from existing file_url if it exists
                    old_file_path = None
                    if document.file_url:
                        # If it's a full URL, extract the path; otherwise use as-is
                        if settings.MEDIA_URL in document.file_url:
                            old_file_path = document.file_url.replace(settings.MEDIA_URL, "")
                        else:
                            # Already just a path
                            old_file_path = document.file_url
                    file_path = minio.upload_base64_file(
                        file_base64,
                        folder="documents",
                        file_name=file_name,
                        old_file_path=old_file_path
                    )
                    # Store only the file path (object name), presigned URLs will be generated in serializer
                    data['file_path'] = file_path
                
                # Capture old representation for change tracking
                old_repr = self.serializer_class(document).data

                serializer = self.serializer_class(document, data=data, partial=True)
                if serializer.is_valid():
                    updated_document = serializer.save(updated_by=request.user)

                    # Log update action
                    create_audit_log(
                        request=request,
                        action="UPDATE",
                        model_name="Document",
                        obj=updated_document,
                        changes={
                            "before": old_repr,
                            "after": serializer.data,
                        },
                    )

                    return CustomResponse.success(data=serializer.data)
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to update document: {str(e)}")

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                document = Document.objects.filter(uid=uid, is_deleted=False).first()
                if not document:
                    return CustomResponse.errors(
                        message="Document not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                document.is_deleted = True
                document.deleted_by = request.user
                document.deleted_at = timezone.now()
                document.save()

                # Log delete action
                create_audit_log(
                    request=request,
                    action="DELETE",
                    model_name="Document",
                    obj=document,
                )

                return CustomResponse.success(message="Document deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to delete document: {str(e)}")


class AnnouncementView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = AnnouncementSerializer
    required_permissions = {
        "get": ["can_view_announcement"],
        "post": ["can_add_announcement"],
        "put": ["can_edit_announcement"],
        "delete": ["can_delete_announcement"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                announcement = Announcement.objects.filter(uid=uid, is_deleted=False, is_active=True).first()
                if not announcement:
                    return CustomResponse.errors(
                        message="Announcement not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                
                # Log view action
                create_audit_log(
                    request=request,
                    action="VIEW",
                    model_name="Announcement",
                    obj=announcement,
                )
                
                serializer = self.serializer_class(announcement)
                return CustomResponse.success(data=serializer.data)
            else:
                now = timezone.now()
                announcements = Announcement.objects.filter(
                    is_deleted=False,
                    is_active=True,
                ).filter(
                    Q(end_date__isnull=True) | Q(end_date__gte=now)
                ).order_by('-is_pinned', '-created_at')
                return CustomPagination.paginate(view_class=self, results=announcements, request=request)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve announcements: {str(e)}")

    def post(self, request):
        try:
            with transaction.atomic():
                data = request.data.copy()
                
                # Handle file upload if provided
                file_base64 = data.get('file_base64', '')
                if file_base64:
                    minio = MinioStorage()
                    file_name = data.get('file_name', f"announcement_{timezone.now().strftime('%Y%m%d%H%M%S')}")
                    file_path = minio.upload_base64_file(
                        file_base64,
                        folder="announcements",
                        file_name=file_name,
                        old_file_path=None
                    )
                    # Store only the file path (object name), presigned URLs will be generated in serializer
                    data['file_path'] = file_path
                
                serializer = self.serializer_class(data=data)
                if serializer.is_valid():
                    announcement = serializer.save(created_by=request.user, updated_by=request.user)

                    # Log create action
                    create_audit_log(
                        request=request,
                        action="CREATE",
                        model_name="Announcement",
                        obj=announcement,
                        changes={"data": serializer.data},
                    )

                    return CustomResponse.success(
                        message="Announcement created successfully",
                        data=serializer.data
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to create announcement: {str(e)}")

    def put(self, request, uid):
        try:
            with transaction.atomic():
                announcement = Announcement.objects.filter(uid=uid, is_deleted=False).first()
                if not announcement:
                    return CustomResponse.errors(
                        message="Announcement not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                
                data = request.data.copy()
                
                # Handle file upload if provided
                file_base64 = data.get('file_base64', '')
                if file_base64:
                    minio = MinioStorage()
                    file_name = data.get('file_name', f"announcement_{timezone.now().strftime('%Y%m%d%H%M%S')}")
                    # Extract old file path from existing file_url if it exists
                    old_file_path = None
                    if announcement.file_url:
                        # If it's a full URL, extract the path; otherwise use as-is
                        if settings.MEDIA_URL in announcement.file_url:
                            old_file_path = announcement.file_url.replace(settings.MEDIA_URL, "")
                        else:
                            # Already just a path
                            old_file_path = announcement.file_url
                    file_path = minio.upload_base64_file(
                        file_base64,
                        folder="announcements",
                        file_name=file_name,
                        old_file_path=old_file_path
                    )
                    # Store only the file path (object name), presigned URLs will be generated in serializer
                    data['file_path'] = file_path
                
                old_repr = self.serializer_class(announcement).data
                serializer = self.serializer_class(announcement, data=data, partial=True)
                if serializer.is_valid():
                    updated_announcement = serializer.save(updated_by=request.user)

                    # Log update action
                    create_audit_log(
                        request=request,
                        action="UPDATE",
                        model_name="Announcement",
                        obj=updated_announcement,
                        changes={
                            "before": old_repr,
                            "after": serializer.data,
                        },
                    )

                    return CustomResponse.success(data=serializer.data)
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to update announcement: {str(e)}")

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                announcement = Announcement.objects.filter(uid=uid, is_deleted=False).first()
                if not announcement:
                    return CustomResponse.errors(
                        message="Announcement not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                announcement.is_deleted = True
                announcement.deleted_by = request.user
                announcement.deleted_at = timezone.now()
                announcement.save()

                # Log delete action
                create_audit_log(
                    request=request,
                    action="DELETE",
                    model_name="Announcement",
                    obj=announcement,
                )

                return CustomResponse.success(message="Announcement deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to delete announcement: {str(e)}")


class EventView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = EventSerializer
    required_permissions = {
        "get": ["can_view_event"],
        "post": ["can_add_event"],
        "put": ["can_edit_event"],
        "delete": ["can_delete_event"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                event = Event.objects.filter(uid=uid, is_deleted=False).first()
                if not event:
                    return CustomResponse.errors(
                        message="Event not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                
                # Log view action
                create_audit_log(
                    request=request,
                    action="VIEW",
                    model_name="Event",
                    obj=event,
                )
                
                serializer = self.serializer_class(event)
                return CustomResponse.success(data=serializer.data)
            else:
                start_date = request.GET.get('start_date')
                end_date = request.GET.get('end_date')
                
                events = Event.objects.filter(is_deleted=False)
                
                if start_date:
                    events = events.filter(start_date__gte=start_date)
                if end_date:
                    events = events.filter(end_date__lte=end_date)
                
                events = events.order_by('start_date')
                return CustomPagination.paginate(view_class=self, results=events, request=request)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve events: {str(e)}")

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    event = serializer.save(created_by=request.user, updated_by=request.user)

                    # Log create action
                    create_audit_log(
                        request=request,
                        action="CREATE",
                        model_name="Event",
                        obj=event,
                        changes={"data": serializer.data},
                    )

                    return CustomResponse.success(
                        message="Event created successfully",
                        data=serializer.data
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to create event: {str(e)}")

    def put(self, request, uid):
        try:
            with transaction.atomic():
                event = Event.objects.filter(uid=uid, is_deleted=False).first()
                if not event:
                    return CustomResponse.errors(
                        message="Event not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                old_repr = self.serializer_class(event).data
                serializer = self.serializer_class(event, data=request.data, partial=True)
                if serializer.is_valid():
                    updated_event = serializer.save(updated_by=request.user)

                    # Log update action
                    create_audit_log(
                        request=request,
                        action="UPDATE",
                        model_name="Event",
                        obj=updated_event,
                        changes={
                            "before": old_repr,
                            "after": serializer.data,
                        },
                    )

                    return CustomResponse.success(data=serializer.data)
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to update event: {str(e)}")

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                event = Event.objects.filter(uid=uid, is_deleted=False).first()
                if not event:
                    return CustomResponse.errors(
                        message="Event not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                event.is_deleted = True
                event.deleted_by = request.user
                event.deleted_at = timezone.now()
                event.save()

                # Log delete action
                create_audit_log(
                    request=request,
                    action="DELETE",
                    model_name="Event",
                    obj=event,
                )

                return CustomResponse.success(message="Event deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to delete event: {str(e)}")


class FAQView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = FAQSerializer
    required_permissions = {
        "get": ["can_view_faq"],
        "post": ["can_add_faq"],
        "put": ["can_edit_faq"],
        "delete": ["can_delete_faq"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                faq = FAQ.objects.filter(uid=uid, is_deleted=False, is_active=True).first()
                if not faq:
                    return CustomResponse.errors(
                        message="FAQ not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                
                # Log view action
                create_audit_log(
                    request=request,
                    action="VIEW",
                    model_name="FAQ",
                    obj=faq,
                )
                
                serializer = self.serializer_class(faq)
                return CustomResponse.success(data=serializer.data)
            else:
                faqs = FAQ.objects.filter(is_deleted=False, is_active=True)
                faqs = faqs.order_by('-created_at')
                return CustomPagination.paginate(view_class=self, results=faqs, request=request)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve FAQs: {str(e)}")

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    faq = serializer.save(created_by=request.user, updated_by=request.user)

                    # Log create action
                    create_audit_log(
                        request=request,
                        action="CREATE",
                        model_name="FAQ",
                        obj=faq,
                        changes={"data": serializer.data},
                    )

                    return CustomResponse.success(
                        message="FAQ created successfully",
                        data=serializer.data
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to create FAQ: {str(e)}")

    def put(self, request, uid):
        try:
            with transaction.atomic():
                faq = FAQ.objects.filter(uid=uid, is_deleted=False).first()
                if not faq:
                    return CustomResponse.errors(
                        message="FAQ not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                old_repr = self.serializer_class(faq).data
                serializer = self.serializer_class(faq, data=request.data, partial=True)
                if serializer.is_valid():
                    updated_faq = serializer.save(updated_by=request.user)

                    # Log update action
                    create_audit_log(
                        request=request,
                        action="UPDATE",
                        model_name="FAQ",
                        obj=updated_faq,
                        changes={
                            "before": old_repr,
                            "after": serializer.data,
                        },
                    )

                    return CustomResponse.success(data=serializer.data)
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to update FAQ: {str(e)}")

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                faq = FAQ.objects.filter(uid=uid, is_deleted=False).first()
                if not faq:
                    return CustomResponse.errors(
                        message="FAQ not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                faq.is_deleted = True
                faq.deleted_by = request.user
                faq.deleted_at = timezone.now()
                faq.save()

                # Log delete action
                create_audit_log(
                    request=request,
                    action="DELETE",
                    model_name="FAQ",
                    obj=faq,
                )

                return CustomResponse.success(message="FAQ deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to delete FAQ: {str(e)}")


class NotificationView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = NotificationSerializer
    required_permissions = {
        "get": ["can_view_notification"],
        "post": ["can_add_notification"],
        "put": ["can_edit_notification"],
        "delete": ["can_delete_notification"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                notification = Notification.objects.filter(uid=uid, is_deleted=False).first()
                if not notification:
                    return CustomResponse.errors(
                        message="Notification not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                
                # Log view action
                create_audit_log(
                    request=request,
                    action="VIEW",
                    model_name="Notification",
                    obj=notification,
                )
                
                serializer = self.serializer_class(notification)
                return CustomResponse.success(data=serializer.data)
            else:
                # Get notifications for current user
                is_read = request.GET.get('is_read')
                notifications = Notification.objects.filter(
                    user=request.user, is_deleted=False
                )
                
                if is_read is not None:
                    notifications = notifications.filter(is_read=is_read.lower() == 'true')
                
                notifications = notifications.order_by('-created_at')
                return CustomPagination.paginate(view_class=self, results=notifications, request=request)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve notifications: {str(e)}")

    def post(self, request):
        try:
            with transaction.atomic():
                # Set user to current user if not provided
                data = request.data.copy()
                if 'user_uid' not in data:
                    data['user_uid'] = str(request.user.guid)
                
                serializer = self.serializer_class(data=data)
                if serializer.is_valid():
                    notification = serializer.save(created_by=request.user, updated_by=request.user)

                    # Log create action
                    create_audit_log(
                        request=request,
                        action="CREATE",
                        model_name="Notification",
                        obj=notification,
                        changes={"data": serializer.data},
                    )

                    return CustomResponse.success(
                        message="Notification created successfully",
                        data=serializer.data
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to create notification: {str(e)}")

    def put(self, request, uid):
        try:
            with transaction.atomic():
                notification = Notification.objects.filter(uid=uid, is_deleted=False).first()
                if not notification:
                    return CustomResponse.errors(
                        message="Notification not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                
                # Mark as read if is_read is True
                if request.data.get('is_read') and not notification.is_read:
                    notification.is_read = True
                    notification.read_at = timezone.now()
                    notification.save()
                    serializer = self.serializer_class(notification)

                    # Log view/read action
                    create_audit_log(
                        request=request,
                        action="VIEW",
                        model_name="Notification",
                        obj=notification,
                    )

                    return CustomResponse.success(data=serializer.data)
                
                old_repr = self.serializer_class(notification).data
                serializer = self.serializer_class(notification, data=request.data, partial=True)
                if serializer.is_valid():
                    updated_notification = serializer.save(updated_by=request.user)

                    # Log update action
                    create_audit_log(
                        request=request,
                        action="UPDATE",
                        model_name="Notification",
                        obj=updated_notification,
                        changes={
                            "before": old_repr,
                            "after": serializer.data,
                        },
                    )

                    return CustomResponse.success(data=serializer.data)
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to update notification: {str(e)}")

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                notification = Notification.objects.filter(uid=uid, is_deleted=False).first()
                if not notification:
                    return CustomResponse.errors(
                        message="Notification not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                notification.is_deleted = True
                notification.deleted_by = request.user
                notification.deleted_at = timezone.now()
                notification.save()

                # Log delete action
                create_audit_log(
                    request=request,
                    action="DELETE",
                    model_name="Notification",
                    obj=notification,
                )

                return CustomResponse.success(message="Notification deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to delete notification: {str(e)}")


class TodoListView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = TodoListSerializer
    required_permissions = {
        "get": ["can_view_todo"],
        "post": ["can_add_todo"],
        "put": ["can_edit_todo"],
        "delete": ["can_delete_todo"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                todo = TodoList.objects.filter(uid=uid, is_deleted=False).first()
                if not todo:
                    return CustomResponse.errors(
                        message="Todo not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                
                # Log view action
                create_audit_log(
                    request=request,
                    action="VIEW",
                    model_name="TodoList",
                    obj=todo,
                )
                
                serializer = self.serializer_class(todo)
                return CustomResponse.success(data=serializer.data)
            else:
                # Get todos
                status_filter = request.GET.get('status', '')
                priority_filter = request.GET.get('priority', '')
                department_uid = request.GET.get('department', '')
                
                todos = TodoList.objects.filter(is_deleted=False)
                
                if status_filter:
                    todos = todos.filter(status=status_filter)
                if priority_filter:
                    todos = todos.filter(priority=priority_filter)
                if department_uid:
                    todos = todos.filter(department__uid=department_uid)
                
                todos = todos.order_by('-priority', 'due_date', '-created_at')
                return CustomPagination.paginate(view_class=self, results=todos, request=request)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve todos: {str(e)}")

    def post(self, request):
        try:
            with transaction.atomic():
                # Set user to current user if not provided
                data = request.data.copy()
                if 'user_uid' not in data:
                    data['user_uid'] = str(request.user.guid)
                
                serializer = self.serializer_class(data=data)
                if serializer.is_valid():
                    todo = serializer.save(created_by=request.user, updated_by=request.user)

                    # Log create action
                    create_audit_log(
                        request=request,
                        action="CREATE",
                        model_name="TodoList",
                        obj=todo,
                        changes={"data": serializer.data},
                    )

                    return CustomResponse.success(
                        message="Todo created successfully",
                        data=serializer.data
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to create todo: {str(e)}")

    def put(self, request, uid):
        try:
            with transaction.atomic():
                todo = TodoList.objects.filter(uid=uid, is_deleted=False).first()
                if not todo:
                    return CustomResponse.errors(
                        message="Todo not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                
                # Mark as completed if status is COMPLETED
                if request.data.get('status') == 'COMPLETED' and todo.status != 'COMPLETED':
                    todo.completed_at = timezone.now()
                
                old_repr = self.serializer_class(todo).data
                serializer = self.serializer_class(todo, data=request.data, partial=True)
                if serializer.is_valid():
                    updated_todo = serializer.save(updated_by=request.user)

                    # Log update action
                    create_audit_log(
                        request=request,
                        action="UPDATE",
                        model_name="TodoList",
                        obj=updated_todo,
                        changes={
                            "before": old_repr,
                            "after": serializer.data,
                        },
                    )

                    return CustomResponse.success(data=serializer.data)
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to update todo: {str(e)}")

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                todo = TodoList.objects.filter(uid=uid, is_deleted=False).first()
                if not todo:
                    return CustomResponse.errors(
                        message="Todo not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                todo.is_deleted = True
                todo.deleted_by = request.user
                todo.deleted_at = timezone.now()
                todo.save()

                # Log delete action
                create_audit_log(
                    request=request,
                    action="DELETE",
                    model_name="TodoList",
                    obj=todo,
                )

                return CustomResponse.success(message="Todo deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to delete todo: {str(e)}")


class QuickLinkView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = QuickLinkSerializer
    required_permissions = {
        "get": ["can_view_quick_link"],
        "post": ["can_add_quick_link"],
        "put": ["can_edit_quick_link"],
        "delete": ["can_delete_quick_link"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                quick_link = QuickLink.objects.filter(uid=uid, is_deleted=False).first()
                if not quick_link:
                    return CustomResponse.errors(
                        message="Quick link not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                
                # Log view action
                create_audit_log(
                    request=request,
                    action="VIEW",
                    model_name="QuickLink",
                    obj=quick_link,
                )
                
                serializer = self.serializer_class(quick_link)
                return CustomResponse.success(data=serializer.data)
            else:
                quick_links = QuickLink.objects.filter(is_deleted=False).order_by('name')
                return CustomPagination.paginate(view_class=self, results=quick_links, request=request)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve quick links: {str(e)}")

    def post(self, request):
        try:
            with transaction.atomic():
                data = request.data.copy()
                
                # Handle logo upload if provided
                logo_base64 = data.get('logo_base64', '')
                if logo_base64:
                    minio = MinioStorage()
                    logo_name = data.get('logo_name', f"quicklink_logo_{timezone.now().strftime('%Y%m%d%H%M%S')}")
                    logo_path = minio.upload_base64_file(
                        logo_base64,
                        folder="links",
                        file_name=logo_name,
                        old_file_path=None
                    )
                    # Store only the file path (object name), presigned URLs will be generated in serializer
                    data['logo_path'] = logo_path
                    # Remove base64 data from serializer input
                    data.pop('logo_base64', None)
                    data.pop('logo_name', None)
                
                serializer = self.serializer_class(data=data)
                if serializer.is_valid():
                    quick_link = serializer.save(created_by=request.user, updated_by=request.user)

                    # Log create action
                    create_audit_log(
                        request=request,
                        action="CREATE",
                        model_name="QuickLink",
                        obj=quick_link,
                        changes={"data": serializer.data},
                    )

                    return CustomResponse.success(
                        data=serializer.data,
                        message="Quick link created successfully"
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to create quick link: {str(e)}")

    def put(self, request, uid):
        try:
            with transaction.atomic():
                quick_link = QuickLink.objects.filter(uid=uid, is_deleted=False).first()
                if not quick_link:
                    return CustomResponse.errors(
                        message="Quick link not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                
                data = request.data.copy()
                
                # Handle logo upload if provided
                logo_base64 = data.get('logo_base64', '')
                if logo_base64:
                    minio = MinioStorage()
                    logo_name = data.get('logo_name', f"quicklink_logo_{timezone.now().strftime('%Y%m%d%H%M%S')}")
                    # Extract old logo path from existing logo if it exists
                    old_logo_path = None
                    if quick_link.logo:
                        # If it's a full URL, extract the path; otherwise use as-is
                        if settings.MEDIA_URL in quick_link.logo:
                            old_logo_path = quick_link.logo.replace(settings.MEDIA_URL, "")
                        else:
                            # Already just a path
                            old_logo_path = quick_link.logo
                    logo_path = minio.upload_base64_file(
                        logo_base64,
                        folder="links",
                        file_name=logo_name,
                        old_file_path=old_logo_path
                    )
                    # Store only the file path (object name), presigned URLs will be generated in serializer
                    data['logo_path'] = logo_path
                    # Remove base64 data from serializer input
                    data.pop('logo_base64', None)
                    data.pop('logo_name', None)
                
                old_repr = self.serializer_class(quick_link).data
                serializer = self.serializer_class(quick_link, data=data, partial=True)
                if serializer.is_valid():
                    updated_quick_link = serializer.save(updated_by=request.user)

                    # Log update action
                    create_audit_log(
                        request=request,
                        action="UPDATE",
                        model_name="QuickLink",
                        obj=updated_quick_link,
                        changes={
                            "before": old_repr,
                            "after": serializer.data,
                        },
                    )

                    return CustomResponse.success(data=serializer.data)
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to update quick link: {str(e)}")

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                quick_link = QuickLink.objects.filter(uid=uid, is_deleted=False).first()
                if not quick_link:
                    return CustomResponse.errors(
                        message="Quick link not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                quick_link.is_deleted = True
                quick_link.deleted_by = request.user
                quick_link.deleted_at = timezone.now()
                quick_link.save()

                # Log delete action
                create_audit_log(
                    request=request,
                    action="DELETE",
                    model_name="QuickLink",
                    obj=quick_link,
                )

                return CustomResponse.success(message="Quick link deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to delete quick link: {str(e)}")


class QuickLinkClickView(APIView):
    """
    Increment quick link click count.
    - Public endpoint (no auth required): used by PortalPage
    - Also works for authenticated users (will capture request.user if available)
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, uid):
        try:
            with transaction.atomic():
                quick_link = QuickLink.objects.filter(uid=uid, is_deleted=False, is_active=True).first()
                if not quick_link:
                    return CustomResponse.errors(
                        message="Quick link not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )

                QuickLink.objects.filter(uid=uid).update(total_clicks=F("total_clicks") + 1)
                quick_link.refresh_from_db(fields=["total_clicks"])

                # Optional: log click as a VIEW action
                create_audit_log(
                    request=request,
                    action="VIEW",
                    model_name="QuickLink",
                    obj=quick_link,
                    changes={"action": "CLICK", "total_clicks": quick_link.total_clicks},
                )

                serializer = QuickLinkSerializer(quick_link)
                return CustomResponse.success(data=serializer.data)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to record click: {str(e)}")


class PortalPopupCardView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = PortalPopupCardSerializer
    required_permissions = {
        "get": ["can_view_popup_card"],
        "post": ["can_add_popup_card"],
        "put": ["can_edit_popup_card"],
        "delete": ["can_delete_popup_card"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                card = PortalPopupCard.objects.filter(uid=uid, is_deleted=False).first()
                if not card:
                    return CustomResponse.errors(
                        message="Popup card not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                create_audit_log(request=request, action="VIEW", model_name="PortalPopupCard", obj=card)
                serializer = self.serializer_class(card)
                return CustomResponse.success(data=serializer.data)
            qs = PortalPopupCard.objects.filter(is_deleted=False).order_by("-created_at")
            return CustomPagination.paginate(view_class=self, results=qs, request=request)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve popup cards: {str(e)}")

    def post(self, request):
        try:
            with transaction.atomic():
                data = request.data.copy()
                es_base64 = data.get("es_image_base64", "")
                if es_base64:
                    minio = MinioStorage()
                    name = data.get("es_image_name", f"popup_es_{timezone.now().strftime('%Y%m%d%H%M%S')}")
                    path = minio.upload_base64_file(es_base64, folder="popup_cards", file_name=name, old_file_path=None)
                    data["es_image_path"] = path
                    data.pop("es_image_base64", None)
                    data.pop("es_image_name", None)
                # Ensure there is only ONE popup card record (upsert semantics).
                # If a card already exists, update it instead of creating a new row.
                existing_card = PortalPopupCard.objects.filter(is_deleted=False).order_by("-created_at").first()
                if existing_card:
                    serializer = self.serializer_class(existing_card, data=data, partial=True)
                else:
                    serializer = self.serializer_class(data=data)

                if serializer.is_valid():
                    card = serializer.save(created_by=request.user, updated_by=request.user)
                    action = "UPDATE" if existing_card else "CREATE"
                    create_audit_log(
                        request=request,
                        action=action,
                        model_name="PortalPopupCard",
                        obj=card,
                        changes={"data": serializer.data},
                    )
                    message = "Popup card updated successfully" if existing_card else "Popup card created successfully"
                    return CustomResponse.success(data=serializer.data, message=message)
                return CustomResponse.errors(message="Validation failed", data=serializer.errors, code=STATUS_CODES["VALIDATION_ERROR"])
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to create popup card: {str(e)}")

    def put(self, request, uid):
        try:
            with transaction.atomic():
                card = PortalPopupCard.objects.filter(uid=uid, is_deleted=False).first()
                if not card:
                    return CustomResponse.errors(message="Popup card not found", code=STATUS_CODES["DATA_NOT_FOUND"])
                data = request.data.copy()
                es_base64 = data.get("es_image_base64", "")
                if es_base64:
                    minio = MinioStorage()
                    name = data.get("es_image_name", f"popup_es_{timezone.now().strftime('%Y%m%d%H%M%S')}")
                    old_path = getattr(card, "es_image_path", None) or None
                    path = minio.upload_base64_file(es_base64, folder="popup_cards", file_name=name, old_file_path=old_path)
                    data["es_image_path"] = path
                    data.pop("es_image_base64", None)
                    data.pop("es_image_name", None)
                old_repr = self.serializer_class(card).data
                serializer = self.serializer_class(card, data=data, partial=True)
                if serializer.is_valid():
                    serializer.save(updated_by=request.user)
                    create_audit_log(request=request, action="UPDATE", model_name="PortalPopupCard", obj=card, changes={"before": old_repr, "after": serializer.data})
                    return CustomResponse.success(data=serializer.data)
                return CustomResponse.errors(message="Validation failed", data=serializer.errors, code=STATUS_CODES["VALIDATION_ERROR"])
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to update popup card: {str(e)}")

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                card = PortalPopupCard.objects.filter(uid=uid, is_deleted=False).first()
                if not card:
                    return CustomResponse.errors(message="Popup card not found", code=STATUS_CODES["DATA_NOT_FOUND"])
                card.is_deleted = True
                card.deleted_by = request.user
                card.deleted_at = timezone.now()
                card.save()
                create_audit_log(request=request, action="DELETE", model_name="PortalPopupCard", obj=card)
                return CustomResponse.success(message="Popup card deleted successfully")
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to delete popup card: {str(e)}")


class AuditLogView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = AuditLogSerializer
    required_permissions = {
        "get": ["can_view_audit_log"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                log = AuditLog.objects.filter(uid=uid).first()
                if not log:
                    return CustomResponse.errors(
                        message="Audit log not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                serializer = self.serializer_class(log)
                return CustomResponse.success(data=serializer.data)
            else:
                model_name = request.GET.get('model_name', '')
                action = request.GET.get('action', '') or request.GET.get('filters', '').split(',')[0] if request.GET.get('filters', '') and request.GET.get('filters', '') != 'ALL' else ''
                user_uid = request.GET.get('user', '')
                department_uid = request.GET.get('department', '')
                
                # Audit logs should be permanent records, so we don't filter by is_deleted
                logs = AuditLog.objects.all()
                
                if model_name:
                    logs = logs.filter(model_name=model_name)
                if action:
                    logs = logs.filter(action=action)
                if user_uid:
                    logs = logs.filter(user__guid=user_uid)
                if department_uid:
                    logs = logs.filter(department__uid=department_uid)
                
                logs = logs.order_by('-created_at')
                return CustomPagination.paginate(view_class=self, results=logs, request=request)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve audit logs: {str(e)}")

