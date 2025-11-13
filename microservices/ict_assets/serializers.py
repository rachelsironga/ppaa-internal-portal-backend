# ict_assets/serializers.py
from rest_framework import serializers
from django.db import transaction
from django.contrib.auth import get_user_model

from mnh_auth.serializers import UserSerializer
from .models import *

User = get_user_model()

class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        super().__init__(*args, **kwargs)

        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

class AuditMixin(serializers.ModelSerializer):
    """Mixin for audit fields with standardized formatting"""
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    updated_by = serializers.PrimaryKeyRelatedField(read_only=True)
    deleted_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    # User details for read operations
    created_by_details = serializers.SerializerMethodField()
    updated_by_details = serializers.SerializerMethodField()
    
    def get_user_details(self, user):
        """Helper method to get user details"""
        if not user:
            return None
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
    
    def get_created_by_details(self, obj):
        return self.get_user_details(obj.created_by)
    
    def get_updated_by_details(self, obj):
        return self.get_user_details(obj.updated_by)

class BaseModelSerializer(AuditMixin, DynamicFieldsModelSerializer):
    """Base serializer with common functionality for all models"""
    uid = serializers.UUIDField(read_only=True)
    is_deleted = serializers.BooleanField(read_only=True)
    
    class Meta:
        fields = [
            'uid', 'created_at', 'updated_at', 'deleted_at', 'is_deleted', 
            'created_by', 'updated_by', 'deleted_by',
            'created_by_details', 'updated_by_details'
        ]

class NameCodeSerializer(BaseModelSerializer):
    """Base serializer for simple name/code models"""
    class Meta:
        fields = BaseModelSerializer.Meta.fields + ['name', 'code']

class NameDescriptionSerializer(BaseModelSerializer):
    """Base serializer for name/description models"""
    class Meta:
        fields = BaseModelSerializer.Meta.fields + ['name', 'description']

class RelatedFieldMixin:
    """Mixin for common related field patterns"""
    
    @staticmethod
    def get_related_name(source, read_only=True):
        """Helper to create related name fields"""
        return serializers.CharField(source=f'{source}.name', read_only=read_only)
    
    @staticmethod
    def get_user_full_name(source, read_only=True):
        """Helper to get user's full name"""
        return serializers.SerializerMethodField(read_only=read_only)

class SaveWithRequestUserMixin:
    """Mixin to handle setting created_by/updated_by from request user"""
    
    def save(self, **kwargs):
        """Set created_by/updated_by from request user"""
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        
        if user and user.is_authenticated:
            if self.instance is None:
                kwargs['created_by'] = user
            kwargs['updated_by'] = user
        
        return super().save(**kwargs)

# Category and Type Serializers
class AssetCategorySerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    parent_category_name = RelatedFieldMixin.get_related_name('parent_category')

    class Meta:
        model = AssetCategory
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'description', 'parent_category', 'parent_category_name'
        ]

    def validate(self, data):
        name = data.get('name')
        parent = data.get('parent_category')
        instance = getattr(self, 'instance', None)

        if not name:
            raise serializers.ValidationError({'name': 'This field is required.'})

        # Unique within the same parent
        qs = AssetCategory.objects.filter(name__iexact=name, parent_category=parent)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError({
                'name': 'A category with this name already exists under the specified parent.'
            })

        # Prevent circular references
        if instance and parent:
            current = parent
            while current:
                if current.pk == instance.pk:
                    raise serializers.ValidationError({
                        'parent_category': 'Invalid parent - would create a circular category reference.'
                    })
                current = current.parent_category

        return data

class AssetTypeSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    category_name = RelatedFieldMixin.get_related_name('category')
    
    class Meta:
        model = AssetType
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'category', 'category_name', 'specifications_template'
        ]

# Manufacturer and Supplier Serializers
class ManufacturerSerializer(SaveWithRequestUserMixin, NameDescriptionSerializer):
    class Meta:
        model = Manufacturer
        fields = NameDescriptionSerializer.Meta.fields + [
            'contact_email', 'support_phone', 'website'
        ]

class SupplierSerializer(SaveWithRequestUserMixin, NameDescriptionSerializer):
    class Meta:
        model = Supplier
        fields = NameDescriptionSerializer.Meta.fields + [
            'contact_person', 'email', 'phone', 'address'
        ]

# Location Serializers
class BuildingSerializer(SaveWithRequestUserMixin, NameCodeSerializer):
    class Meta:
        model = Building
        fields = NameCodeSerializer.Meta.fields + ['address']

class FloorSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    building_name = RelatedFieldMixin.get_related_name('building')
    
    class Meta:
        model = Floor
        fields = BaseModelSerializer.Meta.fields + [
            'building', 'building_name', 'number', 'name'
        ]

class LocationSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    building_name = RelatedFieldMixin.get_related_name('building')
    floor_number = serializers.IntegerField(source='floor.number', read_only=True)
    parent_name = RelatedFieldMixin.get_related_name('parent')
    
    class Meta:
        model = Location
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'address', 'building', 'building_name', 'floor', 
            'floor_number', 'room', 'parent', 'parent_name'
        ]

# Core Asset Serializers
class AssetSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    """Base asset serializer for create/update operations"""
    class Meta:
        model = Asset
        fields = BaseModelSerializer.Meta.fields + [
            'asset_tag', 'barcode', 'serial_number', 'asset_type', 'manufacturer',
            'model', 'purchase_date', 'purchase_cost', 'supplier', 'status',
            'condition', 'location', 'custodian', 'warranty_expiry', 'photo',
            'is_active', 'last_audit_date', 'notes'
        ]
    
    def validate_unique_field(self, field_name, value):
        """Helper to validate unique fields"""
        if not value:
            return value
            
        instance = getattr(self, 'instance', None)
        if instance and getattr(instance, field_name) == value:
            return value
            
        if Asset.objects.filter(**{field_name: value}).exists():
            raise serializers.ValidationError(f"An asset with this {field_name.replace('_', ' ')} already exists.")
        return value
    
    def validate_asset_tag(self, value):
        return self.validate_unique_field('asset_tag', value)
    
    def validate_serial_number(self, value):
        return self.validate_unique_field('serial_number', value)

class AssetListSerializer(AssetSerializer):
    """Lightweight serializer for listing assets"""
    asset_type_name = RelatedFieldMixin.get_related_name('asset_type')
    manufacturer_name = RelatedFieldMixin.get_related_name('manufacturer')
    location_name = RelatedFieldMixin.get_related_name('location')
    custodian_name = RelatedFieldMixin.get_user_full_name('custodian')
    
    def get_custodian_name(self, obj):
        if obj.custodian:
            return f"{obj.custodian.first_name} {obj.custodian.last_name}"
        return None
    
    class Meta:
        model = Asset
        fields = [
            'uid', 'asset_tag', 'serial_number', 'asset_type', 'asset_type_name',
            'manufacturer', 'manufacturer_name', 'model', 'status', 'condition',
            'custodian', 'custodian_name', 'location', 'location_name', 'is_active'
        ]

class AssetDetailSerializer(AssetSerializer):
    """Extended asset serializer with nested relationships"""
    asset_type = AssetTypeSerializer(read_only=True)
    manufacturer = ManufacturerSerializer(read_only=True)
    supplier = SupplierSerializer(read_only=True)
    location = LocationSerializer(read_only=True)
    custodian = UserSerializer(read_only=True)
    
    # Hardware type flags
    has_computer = serializers.SerializerMethodField()
    has_network_device = serializers.SerializerMethodField()
    has_peripheral = serializers.SerializerMethodField()
    
    def get_has_computer(self, obj):
        return hasattr(obj, 'computer')
    
    def get_has_network_device(self, obj):
        return hasattr(obj, 'networkdevice')
    
    def get_has_peripheral(self, obj):
        return hasattr(obj, 'peripheral')

# Hardware Specific Serializers
class HardwareBaseSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    """Base serializer for hardware models"""
    asset_details = AssetSerializer(source='asset', read_only=True)
    
    def validate_json_field(self, value, required_fields):
        """Validate JSON field structure"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a list of objects.")
        
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Each item must be an object.")
            for field in required_fields:
                if field not in item:
                    raise serializers.ValidationError(f"Each item must have '{field}'.")
        return value

class ComputerSerializer(HardwareBaseSerializer):
    class Meta:
        model = Computer
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_details', 'hostname', 'fqdn', 'processor', 'cpu_cores',
            'cpu_speed_ghz', 'cpu_architecture', 'ram_gb', 'storage_type',
            'storage_gb', 'disks', 'operating_system', 'os_version', 'mac_addresses',
            'ip_addresses', 'management_ip', 'gpu', 'virtual', 'virtualization_host',
            'bios_version', 'firmware_version', 'asset_tag_backup', 'notes'
        ]
    
    def validate_disks(self, value):
        return self.validate_json_field(value, ['type', 'size_gb'])

class NetworkDeviceSerializer(HardwareBaseSerializer):
    class Meta:
        model = NetworkDevice
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_details', 'device_type', 'ip_address', 
            'mac_address', 'ports'
        ]

class PeripheralSerializer(HardwareBaseSerializer):
    class Meta:
        model = Peripheral
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_details', 'peripheral_type', 'connection_type'
        ]

# Software Serializers
class SoftwareCategorySerializer(SaveWithRequestUserMixin, NameDescriptionSerializer):
    class Meta:
        model = SoftwareCategory
        fields = NameDescriptionSerializer.Meta.fields

class SoftwareSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    category_name = RelatedFieldMixin.get_related_name('category')
    
    class Meta:
        model = Software
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'version', 'publisher', 'category', 'category_name',
            'license_type', 'cost', 'purchase_date', 'expiration_date', 'notes'
        ]

class SoftwareInstallationSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    software_name = RelatedFieldMixin.get_related_name('software')
    asset_tag = RelatedFieldMixin.get_related_name('asset', 'asset_tag')
    installed_by_name = RelatedFieldMixin.get_user_full_name('installed_by')
    
    def get_installed_by_name(self, obj):
        if obj.installed_by:
            return f"{obj.installed_by.first_name} {obj.installed_by.last_name}"
        return None
    
    class Meta:
        model = SoftwareInstallation
        fields = BaseModelSerializer.Meta.fields + [
            'software', 'software_name', 'asset', 'asset_tag', 'installed_date',
            'license_key', 'installed_by', 'installed_by_name'
        ]

# Assignment and Maintenance Serializers
class AssignmentBaseSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    """Base serializer for assignment-like models"""
    asset_tag = RelatedFieldMixin.get_related_name('asset', 'asset_tag')
    
    def validate_dates(self, start_date_field, end_date_field, data):
        """Validate that end date is not before start date"""
        start_date = data.get(start_date_field)
        end_date = data.get(end_date_field)
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({
                end_date_field: f'{end_date_field.replace("_", " ").title()} cannot be before {start_date_field.replace("_", " ")}.'
            })
        return data

class AssetAssignmentSerializer(AssignmentBaseSerializer):
    assigned_to_name = RelatedFieldMixin.get_user_full_name('assigned_to')
    
    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}"
        return None
    
    def validate(self, data):
        return self.validate_dates('assigned_date', 'return_date', data)
    
    class Meta:
        model = AssetAssignment
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_tag', 'assigned_to', 'assigned_to_name',
            'assigned_date', 'return_date', 'condition_on_assignment', 'notes'
        ]

class MaintenanceRecordSerializer(AssignmentBaseSerializer):
    asset_type_name = RelatedFieldMixin.get_related_name('asset.asset_type')
    
    def validate(self, data):
        return self.validate_dates('scheduled_date', 'completed_date', data)
    
    class Meta:
        model = MaintenanceRecord
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_tag', 'asset_type_name', 'maintenance_type',
            'scheduled_date', 'completed_date', 'status', 'cost', 'description',
            'technician', 'notes'
        ]

class SupportTicketSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    asset_tag = RelatedFieldMixin.get_related_name('asset', 'asset_tag')
    assigned_technician_name = RelatedFieldMixin.get_user_full_name('assigned_technician')
    
    def get_assigned_technician_name(self, obj):
        if obj.assigned_technician:
            return f"{obj.assigned_technician.first_name} {obj.assigned_technician.last_name}"
        return None
    
    class Meta:
        model = SupportTicket
        fields = BaseModelSerializer.Meta.fields + [
            'ticket_id', 'asset', 'asset_tag', 'issue_description', 'priority',
            'status', 'created_date', 'resolved_date', 'assigned_technician',
            'assigned_technician_name', 'resolution_notes'
        ]

# Procurement and Configuration Serializers
class DisposalRecordSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    asset_tag = RelatedFieldMixin.get_related_name('asset', 'asset_tag')
    approved_by_name = RelatedFieldMixin.get_user_full_name('approved_by')
    
    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return f"{obj.approved_by.first_name} {obj.approved_by.last_name}"
        return None
    
    class Meta:
        model = DisposalRecord
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_tag', 'disposal_date', 'disposal_method',
            'disposal_reason', 'disposal_value', 'approved_by', 'approved_by_name', 'notes'
        ]

class WarrantySerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    asset_tag = RelatedFieldMixin.get_related_name('asset', 'asset_tag')
    
    def validate(self, data):
        return self.validate_dates('start_date', 'end_date', data)
    
    class Meta:
        model = Warranty
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_tag', 'start_date', 'end_date', 'provider',
            'po_number', 'po_date', 'po_amount', 'procurement_notes',
            'contract_file', 'coverage_details', 'support_contact'
        ]

# Specialized Serializers for Complex Operations
class AssetBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk asset updates"""
    asset_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    status = serializers.ChoiceField(choices=Asset.ASSET_STATUS, required=False)
    condition = serializers.ChoiceField(choices=Asset.CONDITION_CHOICES, required=False)
    location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all(), required=False)
    custodian = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)

class AssetSearchSerializer(serializers.Serializer):
    """Serializer for asset search functionality"""
    query = serializers.CharField(required=False)
    asset_type = serializers.PrimaryKeyRelatedField(queryset=AssetType.objects.all(), required=False)
    status = serializers.ChoiceField(choices=Asset.ASSET_STATUS, required=False)
    location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all(), required=False)
    manufacturer = serializers.PrimaryKeyRelatedField(queryset=Manufacturer.objects.all(), required=False)

# Detail serializers with nested relationships
class AssetTypeDetailSerializer(AssetTypeSerializer):
    category = AssetCategorySerializer(read_only=True)

class AssetCategoryDetailSerializer(AssetCategorySerializer):
    subcategories = serializers.SerializerMethodField()
    
    def get_subcategories(self, obj):
        children = AssetCategory.objects.filter(parent_category=obj)
        return AssetCategorySerializer(children, many=True).data

class LocationDetailSerializer(LocationSerializer):
    building = BuildingSerializer(read_only=True)
    floor = FloorSerializer(read_only=True)
    parent = LocationSerializer(read_only=True)

class SoftwareDetailSerializer(SoftwareSerializer):
    category = SoftwareCategorySerializer(read_only=True)

class SoftwareInstallationDetailSerializer(SoftwareInstallationSerializer):
    software = SoftwareSerializer(read_only=True)
    asset = AssetListSerializer(read_only=True)
    installed_by = UserSerializer(read_only=True)

class AssetAssignmentDetailSerializer(AssetAssignmentSerializer):
    asset = AssetListSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)

class MaintenanceRecordDetailSerializer(MaintenanceRecordSerializer):
    asset = AssetListSerializer(read_only=True)

class SupportTicketDetailSerializer(SupportTicketSerializer):
    asset = AssetListSerializer(read_only=True)
    assigned_technician = UserSerializer(read_only=True)

class DisposalRecordDetailSerializer(DisposalRecordSerializer):
    asset = AssetListSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)

class WarrantyDetailSerializer(WarrantySerializer):
    asset = AssetListSerializer(read_only=True)


