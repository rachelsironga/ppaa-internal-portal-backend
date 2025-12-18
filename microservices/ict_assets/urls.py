from django.urls import path
from microservices.ict_assets.modules.asset import AssetView
from microservices.ict_assets.modules.asset_assignment import AssetAssignmentView
from microservices.ict_assets.modules.asset_category import AssetCategoryView
from microservices.ict_assets.modules.asset_history import AssetActivitiesAPIView, AssetCustodianHistoryView, AssetLocationHistoryView
from microservices.ict_assets.modules.asset_type import AssetTypeView
from microservices.ict_assets.modules.building import BuildingView
from microservices.ict_assets.modules.computer import ComputerView
from microservices.ict_assets.modules.custodian import CustodianListView
from microservices.ict_assets.modules.technician import TechnicianListView
from microservices.ict_assets.modules.dashboard_summary import (
    AssetTypeBreakdownAPIView,
    DashboardAPIView,
    FilteredDashboardAPIView,
    MaintenanceMetricsAPIView,
    RecentActivitiesAPIView,
    StatusDistributionAPIView,
    WarrantyAlertsAPIView,
)
from microservices.ict_assets.modules.disposal_record import (
    DisposalRecordView,
    DisposalAuditTrailView,
    DisposalConversationView,
    DisposalApprovalView,
    DisposalResubmitView,
    DisposalCancelView,
)
from microservices.ict_assets.modules.floor import FloorView
from microservices.ict_assets.modules.location import LocationView
from microservices.ict_assets.modules.maintenance_record import MaintenanceRecordView
from microservices.ict_assets.modules.manufacturer import ManufacturerView
from microservices.ict_assets.modules.network_device import NetworkDeviceView
from microservices.ict_assets.modules.peripheral import PeripheralView
from microservices.ict_assets.modules.software import SoftwareView
from microservices.ict_assets.modules.software_category import SoftwareCategoryView
from microservices.ict_assets.modules.software_installation import SoftwareInstallationView
from microservices.ict_assets.modules.software_license import SoftwareLicenseView
from microservices.ict_assets.modules.supplier import SupplierView
from microservices.ict_assets.modules.support_ticket import SupportTicketView
from microservices.ict_assets.modules.warranty import WarrantyView


urlpatterns = [
    # Asset Category URLs
    path('asset-categories', AssetCategoryView.as_view(), name='asset-category-list'),
    path('asset-categories/<str:uid>', AssetCategoryView.as_view(), name='asset-category-detail'),

    # Asset Type URLs
    path('asset-types', AssetTypeView.as_view(), name='asset-type-list'),
    path('asset-types/<str:uid>', AssetTypeView.as_view(), name='asset-type-create-update'),
    
    # Manufacturer URLs
   path('asset-manufacturers', ManufacturerView.as_view(), name='manufacturer-list'),
   path('asset-manufacturers/<str:uid>', ManufacturerView.as_view(), name='manufacturer-create-update'),
 
    # Supplier URLs assets-suppliers?
   path('asset-suppliers', SupplierView.as_view(), name='supplier-list'),
   path('asset-suppliers/<str:uid>', SupplierView.as_view(), name='supplier-create-update'),
 
    
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

    # Custodian URLs
    path('assets-custodians', CustodianListView.as_view(), name='asset-user-list'),
    path('assets-custodians/<uuid:guid>', CustodianListView.as_view(), name='asset-user-detail'),
    
    # Technician URLs
    path('assets-technicians', TechnicianListView.as_view(), name='asset-technician-list'),
    path('assets-technicians/<uuid:guid>', TechnicianListView.as_view(), name='asset-technician-detail'),
    
    # Asset History URLs
    # assets/assets-activities/54e36dff-d942-4276-b025-e1052a5dffed/history
    path('assets-activities/recent', AssetActivitiesAPIView.as_view(), name='recent-activities'),
    path('assets-activities/<uuid:uid>/history', AssetActivitiesAPIView.as_view(), name='asset-activities-history'),
    path('assets-custodian-history', AssetCustodianHistoryView.as_view(), name='asset-custodian-history-list'),
    path('assets-custodian-history/<uuid:uid>', AssetCustodianHistoryView.as_view(), name='asset-custodian-history-detail'),
    path('assets-location-history', AssetLocationHistoryView.as_view(), name='asset-location-history-list'),
    path('assets-location-history/<uuid:uid>', AssetLocationHistoryView.as_view(), name='asset-location-history-detail'),
    
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
   path('asset-software-installations/<uuid:uid>/verify', SoftwareInstallationView.as_view(), name='software-installation-verify'),
   path('asset-software-installations/<uuid:uid>/uninstall', SoftwareInstallationView.as_view(), name='software-installation-uninstall'),
   path('asset-software-installations/<uuid:uid>/delete', SoftwareInstallationView.as_view(), name='software-installation-delete'),
    
    # Software License URLs
   path('asset-software-licenses', SoftwareLicenseView.as_view(), name='software-license-list'),
   path('asset-software-licenses/create', SoftwareLicenseView.as_view(), name='software-license-create'),
   path('asset-software-licenses/<uuid:uid>', SoftwareLicenseView.as_view(), name='software-license-detail'),
   path('asset-software-licenses/<uuid:uid>/update', SoftwareLicenseView.as_view(), name='software-license-update'),
   path('asset-software-licenses/<uuid:uid>/delete', SoftwareLicenseView.as_view(), name='software-license-delete'),
    
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
    
    # Support Ticket URLsa
   path('asset-support-tickets', SupportTicketView.as_view(), name='support-ticket-list'),
   path('asset-support-tickets/create', SupportTicketView.as_view(), name='support-ticket-create'),
   path('asset-support-tickets/<uuid:uid>', SupportTicketView.as_view(), name='support-ticket-detail'),
   path('asset-support-tickets/<uuid:uid>/update', SupportTicketView.as_view(), name='support-ticket-update'),
   path('asset-support-tickets/<uuid:uid>/delete', SupportTicketView.as_view(), name='support-ticket-delete'),
    
    # Disposal Record URLs
   path('asset-disposal-records', DisposalRecordView.as_view(), name='disposal-record-list'),
   path('asset-disposal-records/<str:uid>', DisposalRecordView.as_view(), name='disposal-record-detail'),
   
   # Disposal Record Approval/Rejection URLs
   path('asset-disposal-records/<str:uid>/approve', DisposalApprovalView.as_view(), {'action': 'approve'}, name='disposal-record-approve'),
   path('asset-disposal-records/<str:uid>/reject', DisposalApprovalView.as_view(), {'action': 'reject'}, name='disposal-record-reject'),
   path('asset-disposal-records/<str:uid>/resubmit', DisposalResubmitView.as_view(), name='disposal-record-resubmit'),
   path('asset-disposal-records/<str:uid>/cancel', DisposalCancelView.as_view(), name='disposal-record-cancel'),
   
   path('asset-disposal-records/<str:uid>/audit-trail', DisposalAuditTrailView.as_view(), name='disposal-record-audit-trail'),
   path('asset-disposal-records/<str:uid>/conversations', DisposalConversationView.as_view(), name='disposal-record-conversations'),

    
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

