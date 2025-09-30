from django.urls import path

from api.modules.approval_action import ApprovalActionView
from api.modules.approval_module_level_step import ApproveModuleLevelStepView, ApproveModuleLevelActingUser, \
    ApprovalRequestCustomise
from api.modules.date_range import DateRangeView
from api.modules.handler import RequestHandler
from api.modules.positional_level import PositionalLevelView, BulkDesignationImportView
from api.modules.approval_module import ApprovalModuleView
from api.modules.approval_module_level import ApprovalModuleLevelView
from api.modules.approval_request import ApprovalRequestView
from api.modules.department import DepartmentView
from api.modules.directory import DirectoryView, UploadDirectoryExcelView
from api.modules.external_auth.jeeva_roles import JeevaRoleView, JeevaRolePermissionListView
from api.modules.system.user_roles import SystemRoleView, SystemPermissionView, SystemAssignRoleUser, SystemRoleUsers, \
    SystemAssignRoleListToUser, SystemGroupView
from api.serializers import ApprovalRequestCustomiseSerializer

urlpatterns = [
    path('date-range', DateRangeView.as_view(), name='date-range-view'),
    path('date-range/<str:uid>', DateRangeView.as_view(), name='date-range-open'),

    path('directory', DirectoryView.as_view(), name='directory-view'),
    path('directory/<str:uid>', DirectoryView.as_view(), name='directory-open'),

    path('departments', DepartmentView.as_view(), name='view'),
    path('departments/<str:uid>', DepartmentView.as_view(), name='open'),
path('import-directories', UploadDirectoryExcelView.as_view(), name='view'),

    path('positional-level', PositionalLevelView.as_view(), name='view-positional-level'),
    path('positional-level/<str:uid>', PositionalLevelView.as_view(), name='open-positional-level'),
    path('positional-level-import', BulkDesignationImportView.as_view(), name='positional-level-import'),

    path('approval-action', ApprovalActionView.as_view(), name='view-approval-action'),
    path('approval-action/<str:uid>', ApprovalActionView.as_view(), name='open-approval-action'),

    path('approval-module', ApprovalModuleView.as_view(), name='view-approval-module'),
    path('approval-module/<str:uid>', ApprovalModuleView.as_view(), name='open-approval-module'),

    path('approval-module-level', ApprovalModuleLevelView.as_view(), name='view-approval-module-level'),
    path('approval-module-level/<str:uid>', ApprovalModuleLevelView.as_view(), name='open-approval-module-level'),

    path('jeeva-role', JeevaRoleView.as_view(), name='all-jeeva-role'),
    path('jeeva-role/<str:uid>', JeevaRoleView.as_view(), name='one-jeeva-role'),
    path('jeeva-role-perm-list', JeevaRolePermissionListView.as_view(), name='jeeva-role-perm-list'),
    path('jeeva-role-perm-by-code/<str:role_codename>', JeevaRolePermissionListView.as_view(), name='jeeva-role-perm-by-code'),

    path('approval-request', ApprovalRequestView.as_view(), name='view-approval-request'),
    path('approval-request/<str:uid>', ApprovalRequestView.as_view(), name='open-approval-request'),

    path('approval-request-handler', RequestHandler.as_view(), name='approval-request-handler'),
    path('approval-request-handler/<str:uid>', RequestHandler.as_view(), name='approval-request-handler'),

    path('approve-reject-request', ApproveModuleLevelStepView.as_view(), name='approve-reject-request'),

    path('approval-request-step/<str:request_uid>', ApproveModuleLevelStepView.as_view(), name='one-approval-request-step'),
    path('get-acting-user', ApproveModuleLevelActingUser.as_view(), name='get-acting-user'),
    path('approval-request-update-permissions/<str:request_uid>', ApprovalRequestCustomise.as_view(), name='approval-request-update-permissions'),

    path('system/roles', SystemRoleView.as_view(), name='system-roles'),
    path('system/roles/<str:uid>', SystemRoleView.as_view(), name='open-system-roles'),
    path('system/roles-users', SystemRoleUsers.as_view(), name='view-system-roles-users'),

    path('system/roles-assign-users', SystemAssignRoleUser.as_view(), name='assign-system-roles-users'),
    path('system/roles-list-assign-users', SystemAssignRoleListToUser.as_view(), name='roles-list-assign-users'),

    path('system/system-permissions', SystemPermissionView.as_view(), name='system-permissions'),
    path('system/system-groups', SystemGroupView.as_view(), name='system-permissions'),

]

