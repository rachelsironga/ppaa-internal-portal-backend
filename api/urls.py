from django.urls import path

from api.modules.approval_action import ApprovalActionView
from api.modules.approval_module_level_step import ApproveModuleLevelStepView, ApproveModuleLevelActingUser, \
    ApprovalRequestCustomise
from api.modules.date_range import DateRangeView
from api.modules.handler import RequestHandler
from api.modules.positional_level import PositionalLevelView, BulkDesignationImportView
from api.modules.approval_module import ApprovalModuleView
from api.modules.approval_module_level import ApprovalModuleLevelView
from api.modules.approval_request import ApprovalRequestView, ApprovalRequestHandlerView
from api.modules.department import DepartmentView
from api.modules.directory import DirectoryView, UploadDirectoryExcelView
from api.modules.external_auth.jeeva_roles import JeevaRoleView, JeevaRolePermissionListView
from api.modules.system.user_roles import SystemRoleView, SystemPermissionView, SystemAssignRoleUser, SystemRoleUsers, \
    SystemAssignRoleListToUser, SystemGroupView
from api.serializers import ApprovalRequestCustomiseSerializer


from microservices.ict_assets.modules.asset import AssetView
from microservices.ict_assets.modules.asset_assignment import AssetAssignmentView
from microservices.ict_assets.modules.asset_category import AssetCategoryView
from microservices.ict_assets.modules.asset_type import AssetTypeView
from microservices.ict_assets.modules.building import BuildingView
from microservices.ict_assets.modules.computer import ComputerView
from microservices.ict_assets.modules.dashboard_summary import (
    AssetTypeBreakdownAPIView,
    DashboardAPIView,
    FilteredDashboardAPIView,
    MaintenanceMetricsAPIView,
    RecentActivitiesAPIView,
    StatusDistributionAPIView,
    WarrantyAlertsAPIView,
)
from microservices.ict_assets.modules.disposal_record import DisposalRecordView
from microservices.ict_assets.modules.floor import FloorView
from microservices.ict_assets.modules.location import LocationView
from microservices.ict_assets.modules.maintenance_record import MaintenanceRecordView
from microservices.ict_assets.modules.manufacturer import ManufacturerView
from microservices.ict_assets.modules.network_device import NetworkDeviceView
from microservices.ict_assets.modules.peripheral import PeripheralView
from microservices.ict_assets.modules.software import SoftwareView
from microservices.ict_assets.modules.software_category import SoftwareCategoryView
from microservices.ict_assets.modules.software_installation import SoftwareInstallationView
from microservices.ict_assets.modules.supplier import SupplierView
from microservices.ict_assets.modules.support_ticket import SupportTicketView
from microservices.ict_assets.modules.warranty import WarrantyView

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
    path('handle-approval-request', ApprovalRequestHandlerView.as_view(), name='handle-approval-request'),

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



# Individual URL patterns for ICT ASSETS
urlpatterns += [
    # Asset Category URLs
    path('asset-categories', AssetCategoryView.as_view(), name='asset-category-list'),
    path('asset-categories/create', AssetCategoryView.as_view(), name='asset-category-create'),
    path('asset-categories/<uuid:uid>', AssetCategoryView.as_view(), name='asset-category-detail'),
    path('asset-categories/<uuid:uid>/update', AssetCategoryView.as_view(), name='asset-category-update'),
    path('asset-categories/<uuid:uid>/delete', AssetCategoryView.as_view(), name='asset-category-delete'),
    
    # Asset Type URLs
    path('asset-types', AssetTypeView.as_view(), name='asset-type-list'),
    path('asset-types/create', AssetTypeView.as_view(), name='asset-type-create'),
    path('asset-types/<uuid:uid>', AssetTypeView.as_view(), name='asset-type-detail'),
    path('asset-types/<uuid:uid>/update', AssetTypeView.as_view(), name='asset-type-update'),
    path('asset-types/<uuid:uid>/delete', AssetTypeView.as_view(), name='asset-type-delete'),
    
    # Manufacturer URLs
   path('asset-manufacturers', ManufacturerView.as_view(), name='manufacturer-list'),
   path('asset-manufacturers/create', ManufacturerView.as_view(), name='manufacturer-create'),
   path('asset-manufacturers/<uuid:uid>', ManufacturerView.as_view(), name='manufacturer-detail'),
   path('asset-manufacturers/<uuid:uid>/update', ManufacturerView.as_view(), name='manufacturer-update'),
   path('asset-manufacturers/<uuid:uid>/delete', ManufacturerView.as_view(), name='manufacturer-delete'),
    
    # Supplier URLs
   path('asset-suppliers', SupplierView.as_view(), name='supplier-list'),
   path('asset-suppliers/create', SupplierView.as_view(), name='supplier-create'),
   path('asset-suppliers/<uuid:uid>', SupplierView.as_view(), name='supplier-detail'),
   path('asset-suppliers/<uuid:uid>/update', SupplierView.as_view(), name='supplier-update'),
   path('asset-suppliers/<uuid:uid>/delete', SupplierView.as_view(), name='supplier-delete'),
    
    # Building URLs
   path('asset-buildings', BuildingView.as_view(), name='building-list'),
   path('asset-buildings/create', BuildingView.as_view(), name='building-create'),
   path('asset-buildings/<uuid:uid>', BuildingView.as_view(), name='building-detail'),
   path('asset-buildings/<uuid:uid>/update', BuildingView.as_view(), name='building-update'),
   path('asset-buildings/<uuid:uid>/delete', BuildingView.as_view(), name='building-delete'),
    
    # Floor URLs
   path('asset-floors', FloorView.as_view(), name='floor-list'),
   path('asset-floors/create', FloorView.as_view(), name='floor-create'),
   path('asset-floors/<uuid:uid>', FloorView.as_view(), name='floor-detail'),
   path('asset-floors/<uuid:uid>/update', FloorView.as_view(), name='floor-update'),
   path('asset-floors/<uuid:uid>/delete', FloorView.as_view(), name='floor-delete'),
    
    # Location URLs
   path('asset-locations', LocationView.as_view(), name='location-list'),
   path('asset-locations/create', LocationView.as_view(), name='location-create'),
   path('asset-locations/<uuid:uid>', LocationView.as_view(), name='location-detail'),
   path('asset-locations/<uuid:uid>/update', LocationView.as_view(), name='location-update'),
   path('asset-locations/<uuid:uid>/delete', LocationView.as_view(), name='location-delete'),
    
   # Asset URLs
    path('assets', AssetView.as_view(), name='asset-list'),
    path('assets/create', AssetView.as_view(), name='asset-create'),
    path('assets/<uuid:uid>', AssetView.as_view(), name='asset-detail'),
    path('assets/<uuid:uid>/update', AssetView.as_view(), name='asset-update'),
    path('assets/<uuid:uid>/delete', AssetView.as_view(), name='asset-delete'),
    
    # Computer URLs
   path('asset-computers', ComputerView.as_view(), name='computer-list'),
   path('asset-computers/create', ComputerView.as_view(), name='computer-create'),
   path('asset-computers/<uuid:uid>', ComputerView.as_view(), name='computer-detail'),
   path('asset-computers/<uuid:uid>/update', ComputerView.as_view(), name='computer-update'),
   path('asset-computers/<uuid:uid>/delete', ComputerView.as_view(), name='computer-delete'),
    
    # Network Device URLs
    path('asset-network-devices', NetworkDeviceView.as_view(), name='network-device-list'),
    path('asset-network-devices/create', NetworkDeviceView.as_view(), name='network-device-create'),
    path('asset-network-devices/<uuid:uid>', NetworkDeviceView.as_view(), name='network-device-detail'),
    path('asset-network-devices/<uuid:uid>/update', NetworkDeviceView.as_view(), name='network-device-update'),
    path('asset-network-devices/<uuid:uid>/delete', NetworkDeviceView.as_view(), name='network-device-delete'),
    
    # Peripheral URLs
    path('asset-peripherals', PeripheralView.as_view(), name='peripheral-list'),
    path('asset-peripherals/create', PeripheralView.as_view(), name='peripheral-create'),
    path('asset-peripherals/<uuid:uid>', PeripheralView.as_view(), name='peripheral-detail'),
    path('asset-peripherals/<uuid:uid>/update', PeripheralView.as_view(), name='peripheral-update'),
    path('asset-peripherals/<uuid:uid>/delete', PeripheralView.as_view(), name='peripheral-delete'),
    
    # Software Category URLs
    path('asset-software-categories', SoftwareCategoryView.as_view(), name='software-category-list'),
    path('asset-software-categories/create', SoftwareCategoryView.as_view(), name='software-category-create'),
    path('asset-software-categories/<uuid:uid>', SoftwareCategoryView.as_view(), name='software-category-detail'),
    path('asset-software-categories/<uuid:uid>/update', SoftwareCategoryView.as_view(), name='software-category-update'),
    path('asset-software-categories/<uuid:uid>/delete', SoftwareCategoryView.as_view(), name='software-category-delete'),
    
    # Software URLs
   path('asset-software', SoftwareView.as_view(), name='software-list'),
   path('asset-software/create', SoftwareView.as_view(), name='software-create'),
   path('asset-software/<uuid:uid>', SoftwareView.as_view(), name='software-detail'),
   path('asset-software/<uuid:uid>/update', SoftwareView.as_view(), name='software-update'),
   path('asset-software/<uuid:uid>/delete', SoftwareView.as_view(), name='software-delete'),
    
    # Software Installation URLs
   path('asset-software-installations', SoftwareInstallationView.as_view(), name='software-installation-list'),
   path('asset-software-installations/create', SoftwareInstallationView.as_view(), name='software-installation-create'),
   path('asset-software-installations/<uuid:uid>', SoftwareInstallationView.as_view(), name='software-installation-detail'),
   path('asset-software-installations/<uuid:uid>/update', SoftwareInstallationView.as_view(), name='software-installation-update'),
   path('asset-software-installations/<uuid:uid>/delete', SoftwareInstallationView.as_view(), name='software-installation-delete'),
    
    # Asset Assignment URLs
   path('asset-asset-assignments', AssetAssignmentView.as_view(), name='asset-assignment-list'),
   path('asset-asset-assignments/create', AssetAssignmentView.as_view(), name='asset-assignment-create'),
   path('asset-asset-assignments/<uuid:uid>', AssetAssignmentView.as_view(), name='asset-assignment-detail'),
   path('asset-asset-assignments/<uuid:uid>/update', AssetAssignmentView.as_view(), name='asset-assignment-update'),
   path('asset-asset-assignments/<uuid:uid>/delete', AssetAssignmentView.as_view(), name='asset-assignment-delete'),
    
    # Maintenance Record URLs
   path('asset-maintenance-records', MaintenanceRecordView.as_view(), name='maintenance-record-list'),
   path('asset-maintenance-records/create', MaintenanceRecordView.as_view(), name='maintenance-record-create'),
   path('asset-maintenance-records/<uuid:uid>', MaintenanceRecordView.as_view(), name='maintenance-record-detail'),
   path('asset-maintenance-records/<uuid:uid>/update', MaintenanceRecordView.as_view(), name='maintenance-record-update'),
   path('asset-maintenance-records/<uuid:uid>/delete', MaintenanceRecordView.as_view(), name='maintenance-record-delete'),
    
    # Support Ticket URLs
   path('asset-support-tickets', SupportTicketView.as_view(), name='support-ticket-list'),
   path('asset-support-tickets/create', SupportTicketView.as_view(), name='support-ticket-create'),
   path('asset-support-tickets/<uuid:uid>', SupportTicketView.as_view(), name='support-ticket-detail'),
   path('asset-support-tickets/<uuid:uid>/update', SupportTicketView.as_view(), name='support-ticket-update'),
   path('asset-support-tickets/<uuid:uid>/delete', SupportTicketView.as_view(), name='support-ticket-delete'),
    
    # Disposal Record URLs
   path('asset-disposal-records', DisposalRecordView.as_view(), name='disposal-record-list'),
   path('asset-disposal-records/create', DisposalRecordView.as_view(), name='disposal-record-create'),
   path('asset-disposal-records/<uuid:uid>', DisposalRecordView.as_view(), name='disposal-record-detail'),
   path('asset-disposal-records/<uuid:uid>/update', DisposalRecordView.as_view(), name='disposal-record-update'),
   path('asset-disposal-records/<uuid:uid>/delete', DisposalRecordView.as_view(), name='disposal-record-delete'),
    
    # Warranty URLs
   path('asset-warranties', WarrantyView.as_view(), name='warranty-list'),
   path('asset-warranties/create', WarrantyView.as_view(), name='warranty-create'),
   path('asset-warranties/<uuid:uid>', WarrantyView.as_view(), name='warranty-detail'),
   path('asset-warranties/<uuid:uid>/update', WarrantyView.as_view(), name='warranty-update'),
   path('asset-warranties/<uuid:uid>/delete', WarrantyView.as_view(), name='warranty-delete'),

    # Main dashboard endpoint
    path('asset-dashboard', DashboardAPIView.as_view(), name='asset-dashboard'),
    
    # Additional dashboard endpoints
    path('asset-dashboard/status-distribution', StatusDistributionAPIView.as_view(), name='status-distribution'),
    path('asset-dashboard/maintenance-metrics', MaintenanceMetricsAPIView.as_view(), name='maintenance-metrics'),
    path('asset-dashboard/recent-activities', RecentActivitiesAPIView.as_view(), name='recent-activities'),
    path('asset-dashboard/asset-type-breakdown', AssetTypeBreakdownAPIView.as_view(), name='asset-type-breakdown'),
    path('asset-dashboard/warranty-alerts', WarrantyAlertsAPIView.as_view(), name='warranty-alerts'),
    path('asset-dashboard/filtered', FilteredDashboardAPIView.as_view(), name='filtered-dashboard'),

]

