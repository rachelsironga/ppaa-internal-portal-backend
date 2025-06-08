from django.urls import path

from api.modules.approval_action import ApprovalActionView
from api.modules.date_range import DateRangeView
from api.modules.positional_level import PositionalLevelView
from api.modules.approval_module import ApprovalModuleView
from api.modules.approval_module_level import ApprovalModuleLevelView
from api.modules.approval_request import ApprovalRequestView
from api.modules.department import DepartmentView
from api.modules.directory import DirectoryView
from api.modules.jeeva_roles import JeevaRoleView
from mnh_model.models import ApprovalRequest

urlpatterns = [
    path('date-range', DateRangeView.as_view(), name='date-range-view'),
    path('date-range/<str:uid>', DateRangeView.as_view(), name='date-range-open'),

    path('directory', DirectoryView.as_view(), name='directory-view'),
    path('directory/<str:uid>', DirectoryView.as_view(), name='directory-open'),

    path('departments', DepartmentView.as_view(), name='view'),
    path('departments/<str:uid>', DepartmentView.as_view(), name='open'),

    path('positional-level', PositionalLevelView.as_view(), name='view-positional-level'),
    path('positional-level/<str:uid>', PositionalLevelView.as_view(), name='open-positional-level'),

    path('approval-action', ApprovalActionView.as_view(), name='view-approval-action'),
    path('approval-action/<str:uid>', ApprovalActionView.as_view(), name='open-approval-action'),

    path('approval-module', ApprovalModuleView.as_view(), name='view-approval-module'),
    path('approval-module/<str:uid>', ApprovalModuleView.as_view(), name='open-approval-module'),

    path('approval-module-level', ApprovalModuleLevelView.as_view(), name='view-approval-module-level'),
    path('approval-module-level/<str:uid>', ApprovalModuleLevelView.as_view(), name='open-approval-module-level'),

    path('jeeva-role', JeevaRoleView.as_view(), name='all-jeeva-role'),
    path('jeeva-role/<str:uid>', JeevaRoleView.as_view(), name='one-jeeva-role'),

    path('approval-request', ApprovalRequestView.as_view(), name='view-approval-request'),
    path('approval-request/<str:uid>', ApprovalRequestView.as_view(), name='open-approval-request'),
]