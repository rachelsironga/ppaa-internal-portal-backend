from django.urls import path

from api.modules.department import DepartmentView
from api.modules.positional_level import PositionalLevelView

from ppaa_portal.internal_portal_views import (
    InternalPortalDashboardSummaryView,
    PortalAuditLogView,
    PortalAuditTrailStatsView,
    PortalDocumentCategoryView,
    PortalDocumentDownloadView,
    PortalAnnouncementDownloadView,
    PortalDocumentView,
    PortalEventView,
    PortalFAQView,
    PortalAnnouncementView,
    PortalQuickLinkClickView,
    PortalQuickLinkView,
    PortalPopupCardView,
    PortalPrFlyerView,
    PortalTodoView,
)

# Aliases for the SPA, which calls /api/internal-portal/... ; core CRUD lives under /api/... in api.urls.
urlpatterns = [
    path("dashboard-summary", InternalPortalDashboardSummaryView.as_view()),
    path("document-categories", PortalDocumentCategoryView.as_view()),
    path("document-categories/<str:uid>", PortalDocumentCategoryView.as_view()),
    path("documents/<str:uid>/download", PortalDocumentDownloadView.as_view()),
    path("documents", PortalDocumentView.as_view()),
    path("documents/<str:uid>", PortalDocumentView.as_view()),
    path("departments", DepartmentView.as_view()),
    path("departments/<str:uid>", DepartmentView.as_view()),
    path("positional-levels", PositionalLevelView.as_view()),
    path("positional-levels/<str:uid>", PositionalLevelView.as_view()),
    path("audit-logs/stats", PortalAuditTrailStatsView.as_view()),
    path("audit-logs", PortalAuditLogView.as_view()),
    path("audit-logs/<str:uid>", PortalAuditLogView.as_view()),
    path("events", PortalEventView.as_view()),
    path("events/<str:uid>", PortalEventView.as_view()),
    path("announcements", PortalAnnouncementView.as_view()),
    path("announcements/<str:uid>/download", PortalAnnouncementDownloadView.as_view()),
    path("announcements/<str:uid>", PortalAnnouncementView.as_view()),
    path("faqs", PortalFAQView.as_view()),
    path("faqs/<str:uid>", PortalFAQView.as_view()),
    path("todos", PortalTodoView.as_view()),
    path("todos/<str:uid>", PortalTodoView.as_view()),
    path("quick-links/<str:uid>/click", PortalQuickLinkClickView.as_view()),
    path("quick-links", PortalQuickLinkView.as_view()),
    path("quick-links/<str:uid>", PortalQuickLinkView.as_view()),
    path("popup-cards", PortalPopupCardView.as_view()),
    path("popup-cards/<str:uid>", PortalPopupCardView.as_view()),
    path("pr-flyers", PortalPrFlyerView.as_view()),
    path("pr-flyers/<str:uid>", PortalPrFlyerView.as_view()),
]
