# admin.py
from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count

from .models import *

# Unregister default Group if you want to use custom groups
# admin.site.unregister(Group)

class BaseAdmin(admin.ModelAdmin):
    """Base admin class with common functionality"""
    list_display = ['name', 'created_at', 'updated_at', 'is_deleted']
    list_filter = ['is_deleted', 'created_at', 'updated_at']
    search_fields = ['name', 'description']
    readonly_fields = ['uid', 'created_at', 'updated_at', 'deleted_at']
    actions = ['soft_delete_selected', 'restore_selected']
    
    def get_queryset(self, request):
        """Override to show deleted objects to superusers"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(is_deleted=False)
    
    def soft_delete_selected(self, request, queryset):
        """Custom action to soft delete objects"""
        updated = queryset.update(is_deleted=True)
        self.message_user(request, f'{updated} items successfully soft deleted.')
    soft_delete_selected.short_description = "Soft delete selected items"
    
    def restore_selected(self, request, queryset):
        """Custom action to restore soft deleted objects"""
        updated = queryset.update(is_deleted=False)
        self.message_user(request, f'{updated} items successfully restored.')
    restore_selected.short_description = "Restore selected items"

class AuditMixinAdmin(admin.ModelAdmin):
    """Mixin for models with audit fields"""
    readonly_fields = ['created_by', 'updated_by', 'deleted_by', 'created_at', 'updated_at', 'deleted_at']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

# Category and Type Admins
@admin.register(AssetCategory)
class AssetCategoryAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = ['name', 'parent_category', 'subcategory_count', 'created_at', 'is_deleted']
    list_filter = ['is_deleted', 'parent_category', 'created_at']
    search_fields = ['name', 'description']
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'description', 'parent_category']
        }),
        ('Audit Information', {
            'fields': ['uid', 'created_by', 'updated_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
        ('Deletion Status', {
            'fields': ['is_deleted', 'deleted_by', 'deleted_at'],
            'classes': ['collapse']
        })
    ]
    
    def subcategory_count(self, obj):
        return obj.assetcategory_set.filter(is_deleted=False).count()
    subcategory_count.short_description = 'Subcategories'

@admin.register(AssetType)
class AssetTypeAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = ['name', 'category', 'asset_count', 'created_at']
    list_filter = ['category', 'is_deleted', 'created_at']
    search_fields = ['name', 'category__name']
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'category', 'specifications_template']
        }),
        ('Audit Information', {
            'fields': ['uid', 'created_by', 'updated_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def asset_count(self, obj):
        return obj.asset_set.filter(is_deleted=False).count()
    asset_count.short_description = 'Assets'

# Manufacturer and Supplier Admins
@admin.register(Manufacturer)
class ManufacturerAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = ['name', 'contact_email', 'support_phone', 'asset_count', 'created_at']
    list_filter = ['is_deleted', 'created_at']
    search_fields = ['name', 'contact_email', 'website']
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'contact_email', 'support_phone', 'website']
        }),
        ('Audit Information', {
            'fields': ['uid', 'created_by', 'updated_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def asset_count(self, obj):
        return obj.asset_set.filter(is_deleted=False).count()
    asset_count.short_description = 'Assets'

@admin.register(Supplier)
class SupplierAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = ['name', 'contact_person', 'email', 'phone', 'asset_count', 'created_at']
    list_filter = ['is_deleted', 'created_at']
    search_fields = ['name', 'contact_person', 'email', 'phone']
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'contact_person', 'email', 'phone', 'address']
        }),
        ('Audit Information', {
            'fields': ['uid', 'created_by', 'updated_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def asset_count(self, obj):
        return obj.asset_set.filter(is_deleted=False).count()
    asset_count.short_description = 'Assets'

# Location Admins
@admin.register(Building)
class BuildingAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = ['name', 'code', 'address', 'floor_count', 'location_count', 'asset_count', 'created_at']
    list_filter = ['is_deleted', 'created_at']
    search_fields = ['name', 'code', 'address']
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'code', 'address']
        }),
        ('Audit Information', {
            'fields': ['uid', 'created_by', 'updated_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def floor_count(self, obj):
        return obj.floors.filter(is_deleted=False).count()
    floor_count.short_description = 'Floors'
    
    def location_count(self, obj):
        from microservices.ict_assets.models import Location
        return Location.objects.filter(building=obj, is_deleted=False).count()
    location_count.short_description = 'Locations'
    
    def asset_count(self, obj):
        from microservices.ict_assets.models import Asset
        return Asset.objects.filter(location__building=obj, is_deleted=False).count()
    asset_count.short_description = 'Assets'

@admin.register(Floor)
class FloorAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = ['building', 'number', 'name', 'location_count', 'created_at']
    list_filter = ['building', 'is_deleted', 'created_at']
    search_fields = ['name', 'building__name', 'number']
    fieldsets = [
        ('Basic Information', {
            'fields': ['building', 'number', 'name']
        }),
        ('Audit Information', {
            'fields': ['uid', 'created_by', 'updated_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def location_count(self, obj):
        return Location.objects.filter(floor=obj, is_deleted=False).count()
    location_count.short_description = 'Locations'

@admin.register(Location)
class LocationAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = ['name', 'building', 'floor', 'room', 'parent', 'asset_count', 'created_at']
    list_filter = ['building', 'floor', 'is_deleted', 'created_at']
    search_fields = ['name', 'building__name', 'room']
    fieldsets = [
        ('Location Information', {
            'fields': ['name', 'address', 'building', 'floor', 'room', 'parent']
        }),
        ('Audit Information', {
            'fields': ['uid', 'created_by', 'updated_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def asset_count(self, obj):
        return Asset.objects.filter(location=obj, is_deleted=False).count()
    asset_count.short_description = 'Assets'

# Asset Admin with Inlines
class ComputerInline(admin.StackedInline):
    model = Computer
    extra = 0
    fields = ['hostname', 'processor', 'ram_gb', 'storage_gb', 'operating_system']
    readonly_fields = ['uid', 'created_at', 'updated_at']

class NetworkDeviceInline(admin.StackedInline):
    model = NetworkDevice
    extra = 0
    fields = ['device_type', 'ip_address', 'mac_address', 'ports']
    readonly_fields = ['uid', 'created_at', 'updated_at']

class PeripheralInline(admin.StackedInline):
    model = Peripheral
    extra = 0
    fields = ['peripheral_type', 'connection_type']
    readonly_fields = ['uid', 'created_at', 'updated_at']

class SoftwareInstallationInline(admin.TabularInline):
    model = SoftwareInstallation
    extra = 0
    fields = ['software', 'installed_date', 'license_key']
    readonly_fields = ['uid', 'created_at', 'updated_at']

class MaintenanceRecordInline(admin.TabularInline):
    model = MaintenanceRecord
    extra = 0
    fields = ['maintenance_type', 'scheduled_date', 'completed_date', 'status']
    readonly_fields = ['uid', 'created_at', 'updated_at']

class AssetAssignmentInline(admin.TabularInline):
    model = AssetAssignment
    extra = 0
    fields = ['assigned_to', 'assigned_date', 'return_date', 'condition_on_assignment']
    readonly_fields = ['uid', 'created_at', 'updated_at']

class WarrantyInline(admin.StackedInline):
    model = Warranty
    extra = 0
    fields = ['start_date', 'end_date', 'provider', 'coverage_details']
    readonly_fields = ['uid', 'created_at', 'updated_at']

@admin.register(Asset)
class AssetAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = [
        'asset_tag', 'serial_number', 'asset_type', 'manufacturer', 'model', 
        'status', 'condition', 'location', 'custodian', 'is_active', 'created_at'
    ]
    list_filter = [
        'asset_type', 'manufacturer', 'status', 'condition', 'location', 
        'is_active', 'is_deleted', 'created_at'
    ]
    search_fields = [
        'asset_tag', 'serial_number', 'model', 'manufacturer__name', 
        'asset_type__name', 'location__name'
    ]
    readonly_fields = ['uid', 'created_at', 'updated_at', 'asset_link']
    fieldsets = [
        ('Basic Information', {
            'fields': [
                'asset_tag', 'barcode', 'serial_number', 'asset_type', 'manufacturer', 'model'
            ]
        }),
        ('Purchase Information', {
            'fields': [
                'purchase_date', 'purchase_cost', 'supplier', 'warranty_expiry'
            ],
            'classes': ['collapse']
        }),
        ('Status & Location', {
            'fields': [
                'status', 'condition', 'location', 'custodian', 'is_active', 'last_audit_date'
            ]
        }),
        ('Additional Information', {
            'fields': ['photo', 'notes'],
            'classes': ['collapse']
        }),
        ('Audit Information', {
            'fields': ['uid', 'asset_link', 'created_by', 'updated_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    inlines = [
        ComputerInline,
        NetworkDeviceInline,
        PeripheralInline,
        SoftwareInstallationInline,
        MaintenanceRecordInline,
        AssetAssignmentInline,
        WarrantyInline,
    ]
    
    def asset_link(self, obj):
        if obj.pk:
            url = reverse('admin:ict_assets_asset_change', args=[obj.pk])
            return format_html('<a href="{}">View Asset Details</a>', url)
        return "-"
    asset_link.short_description = "Admin Link"

# Hardware Specific Admins
@admin.register(Computer)
class ComputerAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = [
        'asset', 'hostname', 'processor', 'ram_gb', 'storage_gb', 
        'operating_system', 'created_at'
    ]
    list_filter = ['operating_system', 'storage_type', 'is_deleted', 'created_at']
    search_fields = [
        'asset__asset_tag', 'hostname', 'processor', 'operating_system'
    ]
    readonly_fields = ['asset_details']
    fieldsets = [
        ('Asset Information', {
            'fields': ['asset', 'asset_details']
        }),
        ('Hardware Specifications', {
            'fields': [
                'hostname', 'fqdn', 'processor', 'cpu_cores', 'cpu_speed_ghz',
                'cpu_architecture', 'ram_gb', 'storage_type', 'storage_gb', 'disks'
            ]
        }),
        ('Software & Networking', {
            'fields': [
                'operating_system', 'os_version', 'mac_addresses', 
                'ip_addresses', 'management_ip'
            ]
        }),
        ('Additional Information', {
            'fields': [
                'gpu', 'virtual', 'virtualization_host', 'bios_version',
                'firmware_version', 'asset_tag_backup', 'notes'
            ],
            'classes': ['collapse']
        }),
        ('Audit Information', {
            'fields': ['uid', 'created_by', 'updated_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def asset_details(self, obj):
        if obj.asset:
            return f"{obj.asset.asset_tag} - {obj.asset.model} ({obj.asset.status})"
        return "No asset linked"
    asset_details.short_description = "Asset Details"

@admin.register(NetworkDevice)
class NetworkDeviceAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = ['asset', 'device_type', 'ip_address', 'mac_address', 'ports', 'created_at']
    list_filter = ['device_type', 'is_deleted', 'created_at']
    search_fields = ['asset__asset_tag', 'ip_address', 'mac_address']
    readonly_fields = ['asset_details']
    
    def asset_details(self, obj):
        if obj.asset:
            return f"{obj.asset.asset_tag} - {obj.asset.model}"
        return "No asset linked"
    asset_details.short_description = "Asset Details"

@admin.register(Peripheral)
class PeripheralAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = ['asset', 'peripheral_type', 'connection_type', 'created_at']
    list_filter = ['peripheral_type', 'connection_type', 'is_deleted', 'created_at']
    search_fields = ['asset__asset_tag', 'peripheral_type']
    readonly_fields = ['asset_details']
    
    def asset_details(self, obj):
        if obj.asset:
            return f"{obj.asset.asset_tag} - {obj.asset.model}"
        return "No asset linked"
    asset_details.short_description = "Asset Details"

# Software Admins
@admin.register(SoftwareCategory)
class SoftwareCategoryAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = ['name', 'software_count', 'created_at']
    
    def software_count(self, obj):
        return obj.software_set.filter(is_deleted=False).count()
    software_count.short_description = 'Software'

@admin.register(Software)
class SoftwareAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = [
        'name', 'version', 'publisher', 'category', 'license_type', 
        'installation_count', 'created_at'
    ]
    list_filter = ['category', 'license_type', 'is_deleted', 'created_at']
    search_fields = ['name', 'version', 'publisher', 'category__name']
    fieldsets = [
        ('Software Information', {
            'fields': ['name', 'version', 'publisher', 'category']
        }),
        ('License Information', {
            'fields': ['license_type', 'cost', 'purchase_date', 'expiration_date']
        }),
        ('Additional Information', {
            'fields': ['notes'],
            'classes': ['collapse']
        }),
        ('Audit Information', {
            'fields': ['uid', 'created_by', 'updated_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def installation_count(self, obj):
        return obj.softwareinstallation_set.filter(is_deleted=False).count()
    installation_count.short_description = 'Installations'

@admin.register(SoftwareInstallation)
class SoftwareInstallationAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = ['software', 'asset', 'installed_date', 'installed_by', 'created_at']
    list_filter = ['software', 'installed_date', 'is_deleted', 'created_at']
    search_fields = ['software__name', 'asset__asset_tag', 'license_key']
    readonly_fields = ['software_details', 'asset_details']
    
    def software_details(self, obj):
        if obj.software:
            return f"{obj.software.name} {obj.software.version}"
        return "No software linked"
    software_details.short_description = "Software Details"
    
    def asset_details(self, obj):
        if obj.asset:
            return f"{obj.asset.asset_tag} - {obj.asset.model}"
        return "No asset linked"
    asset_details.short_description = "Asset Details"

# Operational Admins
@admin.register(AssetAssignment)
class AssetAssignmentAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = ['asset', 'assigned_to', 'assigned_date', 'return_date', 'created_at']
    list_filter = ['assigned_date', 'return_date', 'is_deleted', 'created_at']
    search_fields = ['asset__asset_tag', 'assigned_to__username', 'assigned_to__email']
    readonly_fields = ['asset_details', 'user_details']
    
    def asset_details(self, obj):
        if obj.asset:
            return f"{obj.asset.asset_tag} - {obj.asset.model}"
        return "No asset linked"
    asset_details.short_description = "Asset Details"
    
    def user_details(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.get_full_name()} ({obj.assigned_to.email})"
        return "No user assigned"
    user_details.short_description = "User Details"

@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = [
        'asset', 'maintenance_type', 'scheduled_date', 'completed_date', 
        'status', 'cost', 'created_at'
    ]
    list_filter = ['maintenance_type', 'status', 'scheduled_date', 'is_deleted', 'created_at']
    search_fields = ['asset__asset_tag', 'description', 'technician']
    readonly_fields = ['asset_details']
    
    def asset_details(self, obj):
        if obj.asset:
            return f"{obj.asset.asset_tag} - {obj.asset.model} ({obj.asset.status})"
        return "No asset linked"
    asset_details.short_description = "Asset Details"

@admin.register(SupportTicket)
class SupportTicketAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = [
        'ticket_id', 'asset', 'priority', 'status', 'created_date', 
        'resolved_date', 'assigned_technician', 'created_at'
    ]
    list_filter = ['priority', 'status', 'created_date', 'is_deleted', 'created_at']
    search_fields = ['ticket_id', 'asset__asset_tag', 'issue_description']
    readonly_fields = ['asset_details', 'technician_details']
    
    def asset_details(self, obj):
        if obj.asset:
            return f"{obj.asset.asset_tag} - {obj.asset.model}"
        return "No asset linked"
    asset_details.short_description = "Asset Details"
    
    def technician_details(self, obj):
        if obj.assigned_technician:
            return f"{obj.assigned_technician.get_full_name()} ({obj.assigned_technician.email})"
        return "No technician assigned"
    technician_details.short_description = "Technician Details"

# Lifecycle Management Admins
@admin.register(Warranty)
class WarrantyAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = [
        'asset', 'provider', 'start_date', 'end_date', 'is_active', 'created_at'
    ]
    list_filter = ['provider', 'start_date', 'end_date', 'is_deleted', 'created_at']
    search_fields = ['asset__asset_tag', 'provider', 'po_number']
    readonly_fields = ['asset_details', 'is_active']
    
    def asset_details(self, obj):
        if obj.asset:
            return f"{obj.asset.asset_tag} - {obj.asset.model}"
        return "No asset linked"
    asset_details.short_description = "Asset Details"
    
    def is_active(self, obj):
        from django.utils import timezone
        if obj.end_date and obj.end_date >= timezone.now().date():
            return True
        return False
    is_active.boolean = True
    is_active.short_description = 'Active'

@admin.register(DisposalRecord)
class DisposalRecordAdmin(BaseAdmin, AuditMixinAdmin):
    list_display = [
        'asset', 'disposal_date', 'disposal_method', 'disposal_reason', 
        'approved_by', 'created_at'
    ]
    list_filter = ['disposal_method', 'disposal_date', 'is_deleted', 'created_at']
    search_fields = ['asset__asset_tag', 'disposal_reason', 'approved_by__username']
    readonly_fields = ['asset_details', 'approver_details']
    
    def asset_details(self, obj):
        if obj.asset:
            return f"{obj.asset.asset_tag} - {obj.asset.model} (Disposed)"
        return "No asset linked"
    asset_details.short_description = "Asset Details"
    
    def approver_details(self, obj):
        if obj.approved_by:
            return f"{obj.approved_by.get_full_name()} ({obj.approved_by.email})"
        return "No approver assigned"
    approver_details.short_description = "Approver Details"

# Custom Admin Site Configuration
class ICTAssetsAdminSite(admin.AdminSite):
    site_header = "ICT Assets Management System"
    site_title = "ICT Assets Admin"
    index_title = "ICT Assets Administration"

# Optional: Custom admin site instance
# ict_assets_admin = ICTAssetsAdminSite(name='ict_assets_admin')

# Register Permission model for easy management
@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'codename', 'content_type']
    list_filter = ['content_type']
    search_fields = ['name', 'codename']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('content_type')

# Dashboard customization
# admin.site.index_template = 'admin/ict_assets_index.html'