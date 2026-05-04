from django.urls import path

from api.modules.department import DepartmentView
from api.modules.positional_level import PositionalLevelView
from api.modules.system.user_roles import SystemRoleView, SystemPermissionView, SystemAssignRoleUser, SystemRoleUsers, \
    SystemAssignRoleListToUser, SystemGroupView
from api.modules.system.permissions_by_app import SystemPermissionsByAppView

<<<<<<< HEAD
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
=======
from ppaa_portal.performance_views import (
    FinancialYearView,
    ObjectiveView,
    TargetView,
    TargetAssignOfficerView,
    PerformanceOfficersView,
    ActivityView,
    ImplementationActivitiesView,
    ImplementationTargetsView,
    ActivitySubmitImplementationView,
    ActivityImplementationApprovalView,
    QuarterlyDataView,
    KPIActualView,
    ActivityDocumentView,
    ActivityDocumentDownloadView,
    PerformanceDashboardSummaryView,
    PerformanceAnalyticsView,
    ObjectiveApprovalView,
    ObjectiveSubmitPackageView,
    TargetApprovalView,
    ActivityApprovalView,
)
from ppaa_performance.views import (
    PendingApprovalsView,
    PerformanceAuditLogListView,
    SPISMReportsView,
    SPISMConfigView,
)

from ppaa_portal.views import (
    DocumentCategoryView, DocumentView, AnnouncementView, EventView,
    FAQView, NotificationView, TodoListView, AuditLogView, QuickLinkView, QuickLinkClickView,
    PortalPopupCardView, InternalPortalDashboardSummaryView
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
)


urlpatterns = [

<<<<<<< HEAD
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
=======
    path('internal-portal/dashboard-summary', InternalPortalDashboardSummaryView.as_view(), name='internal-portal-dashboard-summary'),

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

    path('internal-portal/notifications', NotificationView.as_view(), name='notifications'),
    path('internal-portal/notifications/<str:uid>', NotificationView.as_view(), name='notification-detail'),
    # path('internal-portal/notifications-import', BulkNotificationImportView.as_view(), name='notifications-import'),

    path('internal-portal/todos', TodoListView.as_view(), name='todos'),
    path('internal-portal/todos/<str:uid>', TodoListView.as_view(), name='todo-detail'),
    # path('internal-portal/todos-import', BulkTodoImportView.as_view(), name='todos-import'),

    path('internal-portal/audit-logs', AuditLogView.as_view(), name='audit-logs'),
    path('internal-portal/audit-logs/<str:uid>', AuditLogView.as_view(), name='audit-log-detail'),
    # path('internal-portal/audit-logs-import', BulkAuditLogImportView.as_view(), name='audit-logs-import'),

    path('internal-portal/quick-links', QuickLinkView.as_view(), name='quick-links'),
    path('internal-portal/quick-links/<str:uid>', QuickLinkView.as_view(), name='quick-link-detail'),
    path('internal-portal/quick-links/<str:uid>/click', QuickLinkClickView.as_view(), name='quick-link-click'),

    path('internal-portal/popup-cards', PortalPopupCardView.as_view(), name='popup-cards'),
    path('internal-portal/popup-cards/<str:uid>', PortalPopupCardView.as_view(), name='popup-card-detail'),

    # Performance Dashboard (Strategic & Operational Performance Monitoring)
    path('performance-dashboard/financial-years', FinancialYearView.as_view(), name='performance-financial-years'),
    path('performance-dashboard/financial-years/<str:uid>', FinancialYearView.as_view(), name='performance-financial-year-detail'),
    path('performance-dashboard/objectives', ObjectiveView.as_view(), name='performance-objectives'),
    path('performance-dashboard/objectives/<str:uid>', ObjectiveView.as_view(), name='performance-objective-detail'),
    path('performance-dashboard/objectives/<str:uid>/approval', ObjectiveApprovalView.as_view(), name='performance-objective-approval'),
    path('performance-dashboard/objectives/<str:uid>/submit-package', ObjectiveSubmitPackageView.as_view(), name='performance-objective-submit-package'),
    path('performance-dashboard/targets', TargetView.as_view(), name='performance-targets'),
    path('performance-dashboard/targets/<str:uid>', TargetView.as_view(), name='performance-target-detail'),
    path('performance-dashboard/targets/<str:uid>/approval', TargetApprovalView.as_view(), name='performance-target-approval'),
    path('performance-dashboard/targets/<str:uid>/assign-officer', TargetAssignOfficerView.as_view(), name='performance-target-assign-officer'),
    path('performance-dashboard/performance-officers', PerformanceOfficersView.as_view(), name='spism-performance-officers'),
    path('performance-dashboard/activities', ActivityView.as_view(), name='performance-activities'),
    path('performance-dashboard/activities/<str:uid>', ActivityView.as_view(), name='performance-activity-detail'),
    path('performance-dashboard/activities/<str:uid>/approval', ActivityApprovalView.as_view(), name='performance-activity-approval'),
    path('performance-dashboard/activities/<str:uid>/submit-implementation', ActivitySubmitImplementationView.as_view(), name='performance-activity-submit-implementation'),
    path('performance-dashboard/activities/<str:uid>/implementation-approval', ActivityImplementationApprovalView.as_view(), name='performance-activity-implementation-approval'),
    path('performance-dashboard/implementation-activities', ImplementationActivitiesView.as_view(), name='performance-implementation-activities'),
    path('performance-dashboard/implementation-targets', ImplementationTargetsView.as_view(), name='performance-implementation-targets'),
    path('performance-dashboard/quarterly-data', QuarterlyDataView.as_view(), name='performance-quarterly-data'),
    path('performance-dashboard/quarterly-data/<str:uid>', QuarterlyDataView.as_view(), name='performance-quarterly-data-detail'),
    path('performance-dashboard/kpi-actuals', KPIActualView.as_view(), name='performance-kpi-actuals'),
    path('performance-dashboard/kpi-actuals/<str:uid>', KPIActualView.as_view(), name='performance-kpi-actual-detail'),
    path('performance-dashboard/activity-documents', ActivityDocumentView.as_view(), name='performance-activity-documents'),
    path('performance-dashboard/activity-documents/<str:uid>/download', ActivityDocumentDownloadView.as_view(), name='performance-activity-document-download'),
    path('performance-dashboard/activity-documents/<str:uid>', ActivityDocumentView.as_view(), name='performance-activity-document-detail'),
    path('performance-dashboard/summary', PerformanceDashboardSummaryView.as_view(), name='performance-dashboard-summary'),
    path('performance-dashboard/analytics', PerformanceAnalyticsView.as_view(), name='performance-dashboard-analytics'),
    # SPISM: Approval, Reports, Audit, Config
    path('performance-dashboard/pending-approvals', PendingApprovalsView.as_view(), name='spism-pending-approvals'),
    path('performance-dashboard/audit-logs', PerformanceAuditLogListView.as_view(), name='spism-audit-logs'),
    path('performance-dashboard/audit-logs/<str:uid>', PerformanceAuditLogListView.as_view(), name='spism-audit-log-detail'),
    path('performance-dashboard/reports', SPISMReportsView.as_view(), name='spism-reports'),
    path('performance-dashboard/config', SPISMConfigView.as_view(), name='spism-config'),
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92

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


