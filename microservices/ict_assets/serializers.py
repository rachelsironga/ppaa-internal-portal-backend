# ict_assets/serializers.py
from rest_framework import serializers
from django.db import transaction

from mnh_auth.serializers import UserSerializer
from .models import *

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

class TimestampMixin(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

class UserReferenceMixin(serializers.ModelSerializer):
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    updated_by = serializers.PrimaryKeyRelatedField(read_only=True)
    deleted_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    # Optional: Include user details for read operations
    created_by_details = serializers.SerializerMethodField()
    updated_by_details = serializers.SerializerMethodField()
    deleted_by_details = serializers.SerializerMethodField()
    
    def get_created_by_details(self, obj):
        if obj.created_by:
            return {
                'id': obj.created_by.id,
                'username': obj.created_by.username,
                'email': obj.created_by.email,
                'first_name': obj.created_by.first_name,
                'last_name': obj.created_by.last_name
            }
        return None
    
    def get_updated_by_details(self, obj):
        if obj.updated_by:
            return {
                'id': obj.updated_by.id,
                'username': obj.updated_by.username,
                'email': obj.updated_by.email,
                'first_name': obj.updated_by.first_name,
                'last_name': obj.updated_by.last_name
            }
        return None
    
    def get_deleted_by_details(self, obj):
        if obj.deleted_by:
            return {
                'id': obj.deleted_by.id,
                'username': obj.deleted_by.username,
                'email': obj.deleted_by.email,
                'first_name': obj.updated_by.first_name,
                'last_name': obj.updated_by.last_name
            }
        return None

class BaseModelSerializer(TimestampMixin, UserReferenceMixin, DynamicFieldsModelSerializer):
    """Base serializer with common functionality"""
    uid = serializers.UUIDField(read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    is_deleted = serializers.BooleanField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    updated_by = serializers.PrimaryKeyRelatedField(read_only=True)
    deleted_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        fields = [
            'uid', 'created_at', 'updated_at', 'deleted_at', 'is_deleted', 
            'created_by', 'updated_by', 'deleted_by',
            'created_by_details', 'updated_by_details', 'deleted_by_details'
        ]
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }


# Category and Type Serializers
class AssetCategorySerializer(BaseModelSerializer):
    parent_category_name = serializers.CharField(source='parent_category.name', read_only=True)
    
    class Meta:
        model = AssetCategory
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'description', 'parent_category', 'parent_category_name'
        ]

class AssetTypeSerializer(BaseModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = AssetType
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'category', 'category_name', 'specifications_template'
        ]

class AssetTypeDetailSerializer(AssetTypeSerializer):
    """Extended serializer with nested category"""
    category = AssetCategorySerializer(read_only=True)

class AssetCategoryDetailSerializer(AssetCategorySerializer):
    """Extended serializer with nested children"""
    subcategories = serializers.SerializerMethodField()
    
    def get_subcategories(self, obj):
        children = AssetCategory.objects.filter(parent_category=obj)
        return AssetCategorySerializer(children, many=True).data
    

# Manufacturer and Supplier Serializers
class ManufacturerSerializer(BaseModelSerializer):
    class Meta:
        model = Manufacturer
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'contact_email', 'support_phone', 'website'
        ]

class SupplierSerializer(BaseModelSerializer):
    class Meta:
        model = Supplier
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'contact_person', 'email', 'phone', 'address'
        ]


# Location Serializers
class BuildingSerializer(BaseModelSerializer):
    class Meta:
        model = Building
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'code', 'address'
        ]

class FloorSerializer(BaseModelSerializer):
    building_name = serializers.CharField(source='building.name', read_only=True)
    
    class Meta:
        model = Floor
        fields = BaseModelSerializer.Meta.fields + [
            'building', 'building_name', 'number', 'name'
        ]

class LocationSerializer(BaseModelSerializer):
    building_name = serializers.CharField(source='building.name', read_only=True)
    floor_number = serializers.IntegerField(source='floor.number', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    
    class Meta:
        model = Location
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'address', 'building', 'building_name', 'floor', 
            'floor_number', 'room', 'parent', 'parent_name'
        ]

class LocationDetailSerializer(LocationSerializer):
    """Extended location serializer with nested relationships"""
    building = BuildingSerializer(read_only=True)
    floor = FloorSerializer(read_only=True)
    parent = LocationSerializer(read_only=True)


# Core Asset Serializers
class AssetListSerializer(BaseModelSerializer):
    """Lightweight serializer for listing assets"""
    asset_type_name = serializers.CharField(source='asset_type.name', read_only=True)
    manufacturer_name = serializers.CharField(source='manufacturer.name', read_only=True)
    custodian_name = serializers.SerializerMethodField()
    location_name = serializers.CharField(source='location.name', read_only=True)
    
    class Meta:
        model = Asset
        fields = BaseModelSerializer.Meta.fields + [
            'asset_tag', 'serial_number', 'asset_type', 'asset_type_name',
            'manufacturer', 'manufacturer_name', 'model', 'status', 'condition',
            'custodian', 'custodian_name', 'location', 'location_name', 'is_active'
        ]
    
    def get_custodian_name(self, obj):
        return f"{obj.custodian.first_name} {obj.custodian.last_name}" if obj.custodian else None

class AssetSerializer(BaseModelSerializer):
    """Detailed asset serializer for create/update operations"""
    class Meta:
        model = Asset
        fields = BaseModelSerializer.Meta.fields + [
            'asset_tag', 'barcode', 'serial_number', 'asset_type', 'manufacturer',
            'model', 'purchase_date', 'purchase_cost', 'supplier', 'status',
            'condition', 'location', 'custodian', 'warranty_expiry', 'photo',
            'is_active', 'last_audit_date', 'notes'
        ]
    
    def validate_asset_tag(self, value):
        """Ensure asset tag is unique"""
        instance = getattr(self, 'instance', None)
        if instance and instance.asset_tag == value:
            return value
            
        if Asset.objects.filter(asset_tag=value).exists():
            raise serializers.ValidationError("An asset with this tag already exists.")
        return value
    
    def validate_serial_number(self, value):
        """Ensure serial number is unique if provided"""
        if not value:
            return value
            
        instance = getattr(self, 'instance', None)
        if instance and instance.serial_number == value:
            return value
            
        if Asset.objects.filter(serial_number=value).exists():
            raise serializers.ValidationError("An asset with this serial number already exists.")
        return value

class AssetDetailSerializer(AssetSerializer):
    """Extended asset serializer with nested relationships for read operations"""
    asset_type = AssetTypeSerializer(read_only=True)
    manufacturer = ManufacturerSerializer(read_only=True)
    supplier = SupplierSerializer(read_only=True)
    location = LocationSerializer(read_only=True)
    custodian = UserSerializer(read_only=True)
    
    # Computed fields
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
class ComputerSerializer(BaseModelSerializer):
    asset_details = AssetSerializer(source='asset', read_only=True)
    
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
        """Validate disks JSON structure"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Disks must be a list of disk objects.")
        
        for disk in value:
            if not isinstance(disk, dict):
                raise serializers.ValidationError("Each disk must be an object.")
            if 'type' not in disk or 'size_gb' not in disk:
                raise serializers.ValidationError("Each disk must have 'type' and 'size_gb'.")
        return value

class NetworkDeviceSerializer(BaseModelSerializer):
    asset_details = AssetSerializer(source='asset', read_only=True)
    
    class Meta:
        model = NetworkDevice
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_details', 'device_type', 'ip_address', 
            'mac_address', 'ports'
        ]

class PeripheralSerializer(BaseModelSerializer):
    asset_details = AssetSerializer(source='asset', read_only=True)
    
    class Meta:
        model = Peripheral
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_details', 'peripheral_type', 'connection_type'
        ]


# Software Serializers
class SoftwareCategorySerializer(BaseModelSerializer):
    class Meta:
        model = SoftwareCategory
        fields = BaseModelSerializer.Meta.fields + ['name', 'description']

class SoftwareSerializer(BaseModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Software
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'version', 'publisher', 'category', 'category_name',
            'license_type', 'cost', 'purchase_date', 'expiration_date', 'notes'
        ]

class SoftwareDetailSerializer(SoftwareSerializer):
    category = SoftwareCategorySerializer(read_only=True)

class SoftwareInstallationSerializer(BaseModelSerializer):
    software_name = serializers.CharField(source='software.name', read_only=True)
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    installed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = SoftwareInstallation
        fields = BaseModelSerializer.Meta.fields + [
            'software', 'software_name', 'asset', 'asset_tag', 'installed_date',
            'license_key', 'installed_by', 'installed_by_name'
        ]
    
    def get_installed_by_name(self, obj):
        return f"{obj.installed_by.first_name} {obj.installed_by.last_name}" if obj.installed_by else None

class SoftwareInstallationDetailSerializer(SoftwareInstallationSerializer):
    software = SoftwareSerializer(read_only=True)
    asset = AssetListSerializer(read_only=True)
    installed_by = UserSerializer(read_only=True)


# Assignment and Maintenance Serializers
class AssetAssignmentSerializer(BaseModelSerializer):
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AssetAssignment
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_tag', 'assigned_to', 'assigned_to_name',
            'assigned_date', 'return_date', 'condition_on_assignment', 'notes'
        ]
    
    def get_assigned_to_name(self, obj):
        return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}" if obj.assigned_to else None
    
    def validate(self, data):
        """Validate assignment dates"""
        if data.get('return_date') and data['assigned_date'] > data['return_date']:
            raise serializers.ValidationError({
                'return_date': 'Return date cannot be before assigned date.'
            })
        return data

class AssetAssignmentDetailSerializer(AssetAssignmentSerializer):
    asset = AssetListSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)

class MaintenanceRecordSerializer(BaseModelSerializer):
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    asset_type_name = serializers.CharField(source='asset.asset_type.name', read_only=True)
    
    class Meta:
        model = MaintenanceRecord
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_tag', 'asset_type_name', 'maintenance_type',
            'scheduled_date', 'completed_date', 'status', 'cost', 'description',
            'technician', 'notes'
        ]
    
    def validate(self, data):
        """Validate maintenance dates"""
        if data.get('completed_date') and data['scheduled_date'] > data['completed_date']:
            raise serializers.ValidationError({
                'completed_date': 'Completed date cannot be before scheduled date.'
            })
        return data

class MaintenanceRecordDetailSerializer(MaintenanceRecordSerializer):
    asset = AssetListSerializer(read_only=True)

class SupportTicketSerializer(BaseModelSerializer):
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    assigned_technician_name = serializers.SerializerMethodField()
    
    class Meta:
        model = SupportTicket
        fields = BaseModelSerializer.Meta.fields + [
            'ticket_id', 'asset', 'asset_tag', 'issue_description', 'priority',
            'status', 'created_date', 'resolved_date', 'assigned_technician',
            'assigned_technician_name', 'resolution_notes'
        ]
    
    def get_assigned_technician_name(self, obj):
        if obj.assigned_technician:
            return f"{obj.assigned_technician.first_name} {obj.assigned_technician.last_name}"
        return None

class SupportTicketDetailSerializer(SupportTicketSerializer):
    asset = AssetListSerializer(read_only=True)
    assigned_technician = UserSerializer(read_only=True)


# Procurement and Configuration Serializers
class DisposalRecordSerializer(BaseModelSerializer):
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    approved_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = DisposalRecord
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_tag', 'disposal_date', 'disposal_method',
            'disposal_reason', 'disposal_value', 'approved_by', 'approved_by_name', 'notes'
        ]
    
    def get_approved_by_name(self, obj):
        return f"{obj.approved_by.first_name} {obj.approved_by.last_name}" if obj.approved_by else None

class DisposalRecordDetailSerializer(DisposalRecordSerializer):
    asset = AssetListSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)

class DepreciationPolicySerializer(BaseModelSerializer):
    asset_category_name = serializers.CharField(source='asset_category.name', read_only=True)
    
    class Meta:
        model = DepreciationPolicy
        fields = BaseModelSerializer.Meta.fields + [
            'asset_category', 'asset_category_name', 'useful_life_years',
            'depreciation_rate', 'method'
        ]

class WarrantySerializer(BaseModelSerializer):
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    
    class Meta:
        model = Warranty
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_tag', 'start_date', 'end_date', 'provider',
            'po_number', 'po_date', 'po_amount', 'procurement_notes',
            'contract_file', 'coverage_details', 'support_contact'
        ]
    
    def validate(self, data):
        """Validate warranty dates"""
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError({
                'end_date': 'End date cannot be before start date.'
            })
        return data

class WarrantyDetailSerializer(WarrantySerializer):
    asset = AssetListSerializer(read_only=True)



# Specialized Serializers for Complex Operations
class AssetBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk asset updates"""
    asset_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    status = serializers.ChoiceField(choices=Asset.ASSET_STATUS, required=False)
    condition = serializers.ChoiceField(choices=Asset.CONDITION_CHOICES, required=False)
    location = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(), required=False
    )
    custodian = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False
    )

class AssetSearchSerializer(serializers.Serializer):
    """Serializer for asset search functionality"""
    query = serializers.CharField(required=False)
    asset_type = serializers.PrimaryKeyRelatedField(
        queryset=AssetType.objects.all(), required=False
    )
    status = serializers.ChoiceField(choices=Asset.ASSET_STATUS, required=False)
    location = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(), required=False
    )
    manufacturer = serializers.PrimaryKeyRelatedField(
        queryset=Manufacturer.objects.all(), required=False
    )

class AssetWithRelationsSerializer(AssetDetailSerializer):
    """Comprehensive asset serializer with all related data"""
    computer = serializers.SerializerMethodField()
    network_device = serializers.SerializerMethodField()
    peripheral = serializers.SerializerMethodField()
    software_installations = serializers.SerializerMethodField()
    maintenance_records = serializers.SerializerMethodField()
    warranty = serializers.SerializerMethodField()
    assignment = serializers.SerializerMethodField()
    
    def get_computer(self, obj):
        if hasattr(obj, 'computer'):
            return ComputerSerializer(obj.computer).data
        return None
    
    def get_network_device(self, obj):
        if hasattr(obj, 'networkdevice'):
            return NetworkDeviceSerializer(obj.networkdevice).data
        return None
    
    def get_peripheral(self, obj):
        if hasattr(obj, 'peripheral'):
            return PeripheralSerializer(obj.peripheral).data
        return None
    
    def get_software_installations(self, obj):
        installations = SoftwareInstallation.objects.filter(asset=obj)
        return SoftwareInstallationSerializer(installations, many=True).data
    
    def get_maintenance_records(self, obj):
        records = MaintenanceRecord.objects.filter(asset=obj)
        return MaintenanceRecordSerializer(records, many=True).data
    
    def get_warranty(self, obj):
        if hasattr(obj, 'warranty'):
            return WarrantySerializer(obj.warranty).data
        return None
    
    def get_assignment(self, obj):
        if hasattr(obj, 'assetassignment'):
            return AssetAssignmentSerializer(obj.assetassignment).data
        return None