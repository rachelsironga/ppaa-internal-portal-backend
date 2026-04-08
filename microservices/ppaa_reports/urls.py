from django.urls import path

from .modules.financial_year import FinancialYearView, FinancialPeriodView
from .modules.stakeholder import StakeholderView
from .modules.report_type import ReportTypeView
from .modules.report_category import ReportCategoryView
from .modules.report import (
    ReportView, ReportStatusView, ReportSubmitView,
    ReportAttachmentUrlView, ReportPreviewView, ReportDownloadView,
    ReportProgressView, ReportCommentView, ReportCommentMarkReadView,
    ReportAuditTrailView, ReportReassignView
)
from .modules.report_grouped import ReportGroupedView
from .modules.dashboard import (
    DashboardView, DirectorateDashboardView, DeadlineCalendarView
)
from .modules.settings import ReportSettingView
from .modules.directory import DirectoryView, DepartmentView, UserProfileInfoView
from .modules.audit_trail import SystemAuditTrailView, AuditTrailStatsView


urlpatterns = [
    # Financial Year
    path('financial-years', FinancialYearView.as_view(), name='financial-year-list'),
    path('financial-years/create', FinancialYearView.as_view(), name='financial-year-create'),
    path('financial-years/<uuid:uid>', FinancialYearView.as_view(), name='financial-year-detail'),
    path('financial-years/<uuid:uid>/update', FinancialYearView.as_view(), name='financial-year-update'),
    path('financial-years/<uuid:uid>/delete', FinancialYearView.as_view(), name='financial-year-delete'),
    
    # Financial Periods (Quarters)
    path('financial-periods', FinancialPeriodView.as_view(), name='financial-period-list'),
    path('financial-years/<uuid:financial_year_uid>/periods', FinancialPeriodView.as_view(), name='financial-year-periods'),
    path('financial-periods/<uuid:uid>', FinancialPeriodView.as_view(), name='financial-period-detail'),
    path('financial-periods/<uuid:uid>/update', FinancialPeriodView.as_view(), name='financial-period-update'),
    path('financial-periods/<uuid:uid>/delete', FinancialPeriodView.as_view(), name='financial-period-delete'),

    # Stakeholders
    path('stakeholders', StakeholderView.as_view(), name='stakeholder-list'),
    path('stakeholders/create', StakeholderView.as_view(), name='stakeholder-create'),
    path('stakeholders/<uuid:uid>', StakeholderView.as_view(), name='stakeholder-detail'),
    path('stakeholders/<uuid:uid>/update', StakeholderView.as_view(), name='stakeholder-update'),
    path('stakeholders/<uuid:uid>/delete', StakeholderView.as_view(), name='stakeholder-delete'),

    # Report Types
    path('report-types', ReportTypeView.as_view(), name='report-type-list'),
    path('report-types/create', ReportTypeView.as_view(), name='report-type-create'),
    path('report-types/<uuid:uid>', ReportTypeView.as_view(), name='report-type-detail'),
    path('report-types/<uuid:uid>/update', ReportTypeView.as_view(), name='report-type-update'),
    path('report-types/<uuid:uid>/delete', ReportTypeView.as_view(), name='report-type-delete'),

    # Report Categories
    path('report-categories', ReportCategoryView.as_view(), name='report-category-list'),
    path('report-categories/create', ReportCategoryView.as_view(), name='report-category-create'),
    path('report-categories/<uuid:uid>', ReportCategoryView.as_view(), name='report-category-detail'),
    path('report-categories/<uuid:uid>/update', ReportCategoryView.as_view(), name='report-category-update'),
    path('report-categories/<uuid:uid>/delete', ReportCategoryView.as_view(), name='report-category-delete'),

    # Reports
    path('reports', ReportView.as_view(), name='report-list'),
    path('reports-grouped', ReportGroupedView.as_view(), name='report-list-grouped'),
    path('reports/create', ReportView.as_view(), name='report-create'),
    path('reports/<uuid:uid>', ReportView.as_view(), name='report-detail'),
    path('reports/<uuid:uid>/update', ReportView.as_view(), name='report-update'),
    path('reports/<uuid:uid>/delete', ReportView.as_view(), name='report-delete'),
    
    # Report Actions
    path('reports/<uuid:uid>/status', ReportStatusView.as_view(), name='report-status'),
    path('reports/<uuid:uid>/submit', ReportSubmitView.as_view(), name='report-submit'),
    path('reports/<uuid:uid>/attachment-url', ReportAttachmentUrlView.as_view(), name='report-attachment-url'),
    path('reports/<uuid:uid>/preview', ReportPreviewView.as_view(), name='report-preview'),
    path('reports/<uuid:uid>/download', ReportDownloadView.as_view(), name='report-download'),
    path('reports/<uuid:uid>/reassign', ReportReassignView.as_view(), name='report-reassign'),
    
    # Report Progress
    path('reports/<uuid:uid>/progress', ReportProgressView.as_view(), name='report-progress'),
    
    # Report Comments
    path('reports/<uuid:uid>/comments', ReportCommentView.as_view(), name='report-comments'),
    path('reports/<uuid:uid>/comments/mark-read', ReportCommentMarkReadView.as_view(), name='report-comments-mark-read'),
    path('reports/<uuid:uid>/comments/<uuid:comment_uid>/delete', ReportCommentView.as_view(), name='report-comment-delete'),
    
    # Report Audit Trail
    path('reports/<uuid:uid>/audit-trail', ReportAuditTrailView.as_view(), name='report-audit-trail'),

    # Dashboard & Analytics
    path('dashboard', DashboardView.as_view(), name='dashboard'),
    path('dashboard/directorate/<str:directorate_uid>', DirectorateDashboardView.as_view(), name='directorate-dashboard'),
    path('dashboard/calendar', DeadlineCalendarView.as_view(), name='deadline-calendar'),

    # Settings
    path('settings', ReportSettingView.as_view(), name='report-settings'),

    # User Profile Info (for getting logged-in user's directory)
    path('user-profile', UserProfileInfoView.as_view(), name='user-profile-info'),

    # Directories (Directorates)
    path('directories', DirectoryView.as_view(), name='directory-list'),
    path('directories/<uuid:uid>', DirectoryView.as_view(), name='directory-detail'),

    # Departments (Units)
    path('departments', DepartmentView.as_view(), name='department-list'),
    path('directories/<uuid:directory_uid>/departments', DepartmentView.as_view(), name='directory-departments'),
    path('departments/<uuid:uid>', DepartmentView.as_view(), name='department-detail'),

    # System Audit Trail (all activities)
    path('audit-trail', SystemAuditTrailView.as_view(), name='system-audit-trail'),
    path('audit-trail/stats', AuditTrailStatsView.as_view(), name='audit-trail-stats'),
]
