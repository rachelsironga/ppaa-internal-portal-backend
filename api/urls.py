from django.urls import path

from api.modules.department import DepartmentView
from api.modules.positional_level import PositionalLevelView
from api.modules.system.user_roles import SystemRoleView, SystemPermissionView, SystemAssignRoleUser, SystemRoleUsers, \
    SystemAssignRoleListToUser, SystemGroupView
from api.modules.system.permissions_by_app import SystemPermissionsByAppView

from ppaa_portal.internal_portal_views import (
    PortalAnnouncementView as AnnouncementView,
    PortalAuditLogView as AuditLogView,
    PortalAuditTrailStatsView,
    PortalDocumentCategoryView as DocumentCategoryView,
    PortalDocumentView as DocumentView,
    PortalEventView as EventView,
    PortalFAQView as FAQView,
    PortalPopupCardView,
    PortalPrFlyerView,
    PortalQuickLinkClickView as QuickLinkClickView,
    PortalQuickLinkView as QuickLinkView,
    PortalTodoView as TodoListView,
)


urlpatterns = [

    path('internal-portal/document-categories', DocumentCategoryView.as_view(), name='document-categories'),
    path('internal-portal/document-categories/<str:uid>', DocumentCategoryView.as_view(), name='document-category-detail'),

    path('internal-portal/documents', DocumentView.as_view(), name='documents'),
    path('internal-portal/documents/<str:uid>', DocumentView.as_view(), name='document-detail'),

    path('internal-portal/announcements', AnnouncementView.as_view(), name='announcements'),
    path('internal-portal/announcements/<str:uid>', AnnouncementView.as_view(), name='announcement-detail'),

    path('internal-portal/departments', DepartmentView.as_view(), name='departments'),
    path('internal-portal/departments/<str:uid>', DepartmentView.as_view(), name='department-detail'),

    path('internal-portal/positional-levels', PositionalLevelView.as_view(), name='positional-levels'),
    path('internal-portal/positional-levels/<str:uid>', PositionalLevelView.as_view(), name='positional-level-detail'),

    path('internal-portal/events', EventView.as_view(), name='events'),
    path('internal-portal/events/<str:uid>', EventView.as_view(), name='event-detail'),
    # path('internal-portal/events-import', BulkEventImportView.as_view(), name='events-import'),

    path('internal-portal/faqs', FAQView.as_view(), name='faqs'),
    path('internal-portal/faqs/<str:uid>', FAQView.as_view(), name='faq-detail'),
    # path('internal-portal/faqs-import', BulkFAQImportView.as_view(), name='faqs-import'),

    path('internal-portal/todos', TodoListView.as_view(), name='todos'),
    path('internal-portal/todos/<str:uid>', TodoListView.as_view(), name='todo-detail'),
    # path('internal-portal/todos-import', BulkTodoImportView.as_view(), name='todos-import'),

    path('internal-portal/audit-logs/stats', PortalAuditTrailStatsView.as_view(), name='audit-logs-stats'),
    path('internal-portal/audit-logs', AuditLogView.as_view(), name='audit-logs'),
    path('internal-portal/audit-logs/<str:uid>', AuditLogView.as_view(), name='audit-log-detail'),
    # path('internal-portal/audit-logs-import', BulkAuditLogImportView.as_view(), name='audit-logs-import'),

    path('internal-portal/quick-links', QuickLinkView.as_view(), name='quick-links'),
    path('internal-portal/quick-links/<str:uid>', QuickLinkView.as_view(), name='quick-link-detail'),
    path('internal-portal/quick-links/<str:uid>/click', QuickLinkClickView.as_view(), name='quick-link-click'),

    path('internal-portal/popup-cards', PortalPopupCardView.as_view(), name='popup-cards'),
    path('internal-portal/popup-cards/<str:uid>', PortalPopupCardView.as_view(), name='popup-card-detail'),

    path('internal-portal/pr-flyers', PortalPrFlyerView.as_view(), name='pr-flyers'),
    path('internal-portal/pr-flyers/<str:uid>', PortalPrFlyerView.as_view(), name='pr-flyer-detail'),

    path('system/roles', SystemRoleView.as_view(), name='system-roles'),
    path('system/roles/<str:uid>', SystemRoleView.as_view(), name='open-system-roles'),
    path('system/roles-users', SystemRoleUsers.as_view(), name='view-system-roles-users'),

    path('system/roles-assign-users', SystemAssignRoleUser.as_view(), name='assign-system-roles-users'),
    path('system/roles-list-assign-users', SystemAssignRoleListToUser.as_view(), name='roles-list-assign-users'),

    path('system/system-permissions', SystemPermissionView.as_view(), name='system-permissions'),
    path('system/system-groups', SystemGroupView.as_view(), name='system-permissions'),
    path(
        'system/permissions-by-app',
        SystemPermissionsByAppView.as_view(),
        name='system-permissions-by-app',
    ),

]


