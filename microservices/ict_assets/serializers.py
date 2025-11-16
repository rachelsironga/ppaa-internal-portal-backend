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

# Users/Custodian Serializers UserSerializer
class CustodianSerializer(serializers.ModelSerializer):
    """Lightweight serializer used only for listing/searching users."""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = [
            'guid',
            'username',
            'email',
            'pf_number',
            'first_name',
            'middle_name',
            'last_name',
            'full_name',
            'phone_number',
            'office_location',
        ]
        read_only_fields = fields


class TechnicianSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing/searching technicians."""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = [
            'guid',
            'username',
            'email',
            'pf_number',
            'first_name',
            'middle_name',
            'last_name',
            'full_name',
            'phone_number',
            'office_location',
        ]
        read_only_fields = fields

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
class ManufacturerSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    class Meta:
        model = Manufacturer
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'contact_email', 'support_phone', 'website'
        ]
        
class SupplierSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    class Meta:
        model = Supplier
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'contact_person', 'email', 'phone', 'address'
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
        fields = BaseModelSerializer.Meta.fields + [
            'asset_tag', 'barcode', 'serial_number', 'asset_type', 'asset_type_name', 'manufacturer', 'manufacturer_name',
            'model', 'purchase_date', 'purchase_cost', 'supplier', 'status',
            'condition', 'location', 'location_name', 'custodian', 'custodian_name', 'warranty_expiry', 'photo',
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
    
    def to_internal_value(self, data):
        # Convert empty strings to None for date fields
        date_fields = ['purchase_date', 'warranty_expiry']
        for field_name in date_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        # Define field lookup mappings
        field_mappings = {
            'asset_type': ('uid', None),
            'manufacturer': ('uid', None), 
            'supplier': ('uid', None),
            'location': ('uid', None),
            'custodian': ('guid', 'User')  # Special case for User model
        }
        
        for field_name, (lookup_field, custom_model) in field_mappings.items():
            if field_name in data and data[field_name]:
                try:
                    if custom_model == 'User':
                        from django.contrib.auth import get_user_model
                        related_model = get_user_model()
                    else:
                        related_model = self.Meta.model._meta.get_field(field_name).related_model
                    
                    instance = related_model.objects.get(**{lookup_field: data[field_name]})
                    data[field_name] = instance.id
                except related_model.DoesNotExist:
                    raise serializers.ValidationError({
                        field_name: f'Invalid {lookup_field.upper()} - {related_model.__name__} not found'
                    })
                except Exception as e:
                    raise serializers.ValidationError({
                        field_name: f'Error processing {field_name}: {str(e)}'
                    })
            elif field_name in data and data[field_name] == '':
                data[field_name] = None
            
        return super().to_internal_value(data)
    
    def to_representation(self, instance):
        """Convert IDs back to UIDs/GUIDs for response"""
        representation = super().to_representation(instance)
        
        # Convert foreign key IDs to UIDs/GUIDs
        if instance.asset_type:
            representation['asset_type'] = str(instance.asset_type.uid)
        if instance.manufacturer:
            representation['manufacturer'] = str(instance.manufacturer.uid)
        if instance.supplier:
            representation['supplier'] = str(instance.supplier.uid)
        if instance.location:
            representation['location'] = str(instance.location.uid)
        if instance.custodian:
            representation['custodian'] = str(instance.custodian.guid)
        
        return representation

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
    technician_name = RelatedFieldMixin.get_user_full_name('technician')
    
    def get_technician_name(self, obj):
        if obj.technician:
            return f"{obj.technician.first_name} {obj.technician.last_name}"
        return None
    
    def validate(self, data):
        return self.validate_dates('scheduled_date', 'completed_date', data)
    
    def to_internal_value(self, data):
        # Convert empty strings to None for date fields
        date_fields = ['scheduled_date', 'completed_date']
        for field_name in date_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        # Convert asset UID to ID
        if 'asset' in data and data['asset']:
            try:
                asset = Asset.objects.get(uid=data['asset'])
                data['asset'] = asset.id
            except Asset.DoesNotExist:
                raise serializers.ValidationError({
                    'asset': 'Invalid UID - Asset not found'
                })
            except Exception as e:
                raise serializers.ValidationError({
                    'asset': f'Error processing asset: {str(e)}'
                })
        elif 'asset' in data and data['asset'] == '':
            data['asset'] = None
        
        # Convert technician GUID to ID
        if 'technician' in data and data['technician']:
            try:
                technician = User.objects.get(guid=data['technician'])
                data['technician'] = technician.id
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'technician': 'Invalid GUID - Technician not found'
                })
            except Exception as e:
                raise serializers.ValidationError({
                    'technician': f'Error processing technician: {str(e)}'
                })
        elif 'technician' in data and data['technician'] == '':
            data['technician'] = None

        return super().to_internal_value(data)
    
    def to_representation(self, instance):
        """Convert IDs back to UIDs/GUIDs for response"""
        representation = super().to_representation(instance)
        
        if instance.asset:
            representation['asset'] = str(instance.asset.uid)
        if instance.technician:
            representation['technician'] = str(instance.technician.guid)
        
        return representation
    
    class Meta:
        model = MaintenanceRecord
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_tag', 'asset_type_name', 'maintenance_type',
            'scheduled_date', 'completed_date', 'status', 'cost', 'description',
            'technician', 'technician_name', 'notes'
        ]

class SupportTicketSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    asset_tag = RelatedFieldMixin.get_related_name('asset', 'asset_tag')
    assigned_technician_name = RelatedFieldMixin.get_user_full_name('assigned_technician')
    ticket_id = serializers.CharField(read_only=True)
    
    def get_assigned_technician_name(self, obj):
        if obj.assigned_technician:
            return f"{obj.assigned_technician.first_name} {obj.assigned_technician.last_name}"
        return None
    
    def generate_ticket_id(self):
        """Generate ticket ID in format: TKT-YYMMDD-XXXX"""
        from datetime import datetime
        
        date_prefix = datetime.now().strftime('%y%m%d')
        
        # Get the latest ticket for today
        today_tickets = SupportTicket.objects.filter(
            ticket_id__startswith=f'TKT-{date_prefix}'
        ).order_by('-ticket_id').first()
        
        if today_tickets:
            # Extract the sequence number and increment
            last_sequence = int(today_tickets.ticket_id.split('-')[-1])
            new_sequence = last_sequence + 1
        else:
            new_sequence = 1
        
        return f'TKT-{date_prefix}-{new_sequence:04d}'
    
    def to_internal_value(self, data):
        # Convert empty strings to None for datetime fields
        if 'resolved_date' in data and data['resolved_date'] == '':
            data['resolved_date'] = None
        
        # Convert asset UID to ID
        if 'asset' in data and data['asset']:
            try:
                asset = Asset.objects.get(uid=data['asset'])
                data['asset'] = asset.id
            except Asset.DoesNotExist:
                raise serializers.ValidationError({
                    'asset': 'Invalid UID - Asset not found'
                })
            except Exception as e:
                raise serializers.ValidationError({
                    'asset': f'Error processing asset: {str(e)}'
                })
        elif 'asset' in data and data['asset'] == '':
            data['asset'] = None
        
        # Convert assigned_technician GUID to ID
        if 'assigned_technician' in data and data['assigned_technician']:
            try:
                technician = User.objects.get(guid=data['assigned_technician'])
                data['assigned_technician'] = technician.id
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'assigned_technician': 'Invalid GUID - Technician not found'
                })
            except Exception as e:
                raise serializers.ValidationError({
                    'assigned_technician': f'Error processing technician: {str(e)}'
                })
        elif 'assigned_technician' in data and data['assigned_technician'] == '':
            data['assigned_technician'] = None
        
        return super().to_internal_value(data)
    
    def to_representation(self, instance):
        """Convert IDs back to UIDs/GUIDs for response"""
        representation = super().to_representation(instance)
        
        if instance.asset:
            representation['asset'] = str(instance.asset.uid)
        if instance.assigned_technician:
            representation['assigned_technician'] = str(instance.assigned_technician.guid)
        
        return representation
    
    def create(self, validated_data):
        """Auto-generate ticket_id on creation"""
        validated_data['ticket_id'] = self.generate_ticket_id()
        return super().create(validated_data)
    
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

class DashboardSummarySerializer(serializers.Serializer):
    """Main dashboard summary statistics"""
    total_assets = serializers.IntegerField()
    operational_assets = serializers.IntegerField()
    assets_in_repair = serializers.IntegerField()
    retired_assets = serializers.IntegerField()
    
    total_computers = serializers.IntegerField()
    total_network_devices = serializers.IntegerField()
    total_peripherals = serializers.IntegerField()
    
    # Cost statistics
    total_asset_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_asset_cost = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    # Maintenance stats
    pending_maintenance = serializers.IntegerField()
    open_tickets = serializers.IntegerField()
    
    # Warranty alerts
    expiring_warranties = serializers.IntegerField()

class AssetStatusDistributionSerializer(serializers.Serializer):
    """Asset status distribution for charts"""
    status = serializers.CharField()
    count = serializers.IntegerField()
    percentage = serializers.FloatField()

class AssetCategoryDistributionSerializer(serializers.Serializer):
    """Asset category distribution"""
    category = serializers.CharField()
    count = serializers.IntegerField()
    total_value = serializers.DecimalField(max_digits=12, decimal_places=2)

class MaintenanceMetricsSerializer(serializers.Serializer):
    """Maintenance performance metrics"""
    completed_this_month = serializers.IntegerField()
    scheduled_next_month = serializers.IntegerField()
    average_completion_time = serializers.FloatField()
    maintenance_cost_ytd = serializers.DecimalField(max_digits=12, decimal_places=2)

class RecentActivitySerializer(serializers.Serializer):
    """Recent system activities"""
    activity_type = serializers.CharField()
    description = serializers.CharField()
    asset_tag = serializers.CharField()
    timestamp = serializers.DateTimeField()
    user = serializers.CharField()


# History Tracking Serializers
class AssetCustodianHistorySerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    custodian_name = RelatedFieldMixin.get_user_full_name('custodian')
    
    def get_custodian_name(self, obj):
        if obj.custodian:
            return f"{obj.custodian.first_name} {obj.custodian.last_name}"
        return "Unassigned"
    
    class Meta:
        model = AssetCustodianHistory
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_tag', 'custodian', 'custodian_name', 
            'assigned_date', 'notes'
        ]


class AssetLocationHistorySerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    location_name = RelatedFieldMixin.get_related_name('location')
    
    class Meta:
        model = AssetLocationHistory
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_tag', 'location', 'location_name', 
            'moved_date', 'notes'
        ]



