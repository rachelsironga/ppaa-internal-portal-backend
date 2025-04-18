from django.urls import path

from api.modules.approval_action import ApprovalActionView
from api.modules.approval_level import ApprovalLevelView
from api.modules.approval_module import ApprovalModuleView
from api.modules.approval_module_level import ApprovalModuleLevelView
from api.modules.department import DepartmentView

urlpatterns = [
    path('departments', DepartmentView.as_view(), name='view'),
    path('departments/<str:uid>', DepartmentView.as_view(), name='open'),

    path('approval-level', ApprovalLevelView.as_view(), name='view-approval-level'),
    path('approval-level/<str:uid>', ApprovalLevelView.as_view(), name='open-approval-level'),

    path('approval-action', ApprovalActionView.as_view(), name='view-approval-action'),
    path('approval-action/<str:uid>', ApprovalActionView.as_view(), name='open-approval-action'),

    path('approval-module', ApprovalModuleView.as_view(), name='view-approval-module'),
    path('approval-module/<str:uid>', ApprovalModuleView.as_view(), name='open-approval-module'),

    path('approval-module-level', ApprovalModuleLevelView.as_view(), name='view-approval-module-level'),
    path('approval-module-level/<str:uid>', ApprovalModuleLevelView.as_view(), name='open-approval-module-level'),
]