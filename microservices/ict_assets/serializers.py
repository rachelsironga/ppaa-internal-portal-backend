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

# class ComputerSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
#     # Asset fields integrated directly - use source for reading from nested asset
#     asset_tag = serializers.CharField(source='asset.asset_tag')
#     barcode = serializers.CharField(source='asset.barcode', required=False, allow_blank=True)
#     serial_number = serializers.CharField(source='asset.serial_number', required=False, allow_blank=True)
#     asset_type = serializers.UUIDField(source='asset.asset_type')
#     manufacturer = serializers.UUIDField(source='asset.manufacturer', required=False, allow_null=True)
#     model = serializers.CharField(source='asset.model', required=False, allow_blank=True)
#     purchase_date = serializers.DateField(source='asset.purchase_date', required=False, allow_null=True)
#     purchase_cost = serializers.DecimalField(source='asset.purchase_cost', max_digits=10, decimal_places=2, required=False, allow_null=True)
#     supplier = serializers.UUIDField(source='asset.supplier', required=False, allow_null=True)
#     asset_status = serializers.ChoiceField(source='asset.status', choices=Asset.ASSET_STATUS, default='operational')
#     asset_condition = serializers.ChoiceField(source='asset.condition', choices=Asset.CONDITION_CHOICES, required=False, allow_blank=True)
#     location = serializers.UUIDField(source='asset.location', required=False, allow_null=True)
#     custodian = serializers.UUIDField(source='asset.custodian', required=False, allow_null=True)
#     warranty_expiry = serializers.DateField(source='asset.warranty_expiry', required=False, allow_null=True)
#     photo = serializers.CharField(source='asset.photo', max_length=200, required=False, allow_blank=True, allow_null=True)
#     is_active = serializers.BooleanField(source='asset.is_active', default=True)
#     last_audit_date = serializers.DateField(source='asset.last_audit_date', required=False, allow_null=True)
#     asset_notes = serializers.CharField(source='asset.notes', required=False, allow_blank=True)
    
#     # Read-only related fields
#     asset_type_name = RelatedFieldMixin.get_related_name('asset.asset_type')
#     manufacturer_name = RelatedFieldMixin.get_related_name('asset.manufacturer')
#     location_name = RelatedFieldMixin.get_related_name('asset.location')
#     custodian_name = RelatedFieldMixin.get_user_full_name('asset.custodian')
    
#     def get_custodian_name(self, obj):
#         if obj.asset and obj.asset.custodian:
#             return f"{obj.asset.custodian.first_name} {obj.asset.custodian.last_name}"
#         return None
    
#     class Meta:
#         model = Computer
#         fields = BaseModelSerializer.Meta.fields + [
#             # Asset fields
#             'asset_tag', 'barcode', 'serial_number', 'asset_type', 'asset_type_name',
#             'manufacturer', 'manufacturer_name', 'model', 'purchase_date', 'purchase_cost',
#             'supplier', 'asset_status', 'asset_condition', 'location', 'location_name',
#             'custodian', 'custodian_name', 'warranty_expiry', 'photo', 'is_active',
#             'last_audit_date', 'asset_notes',
#             # Computer-specific fields
#             'hostname', 'fqdn', 'processor', 'cpu_cores', 'cpu_speed_ghz', 'cpu_architecture',
#             'ram_gb', 'storage_type', 'storage_gb', 'disks', 'operating_system', 'os_version',
#             'mac_addresses', 'ip_addresses', 'management_ip', 'gpu', 'virtual',
#             'virtualization_host', 'bios_version', 'firmware_version', 'asset_tag_backup', 'notes'
#         ]
    
#     def validate_disks(self, value):
#         if not isinstance(value, list):
#             raise serializers.ValidationError("Must be a list of objects.")
#         for item in value:
#             if not isinstance(item, dict):
#                 raise serializers.ValidationError("Each item must be an object.")
#             if 'type' not in item or 'size_gb' not in item:
#                 raise serializers.ValidationError("Each item must have 'type' and 'size_gb'.")
#         return value
    
#     def to_internal_value(self, data):
#         # Make a copy to avoid modifying the original
#         data = data.copy() if hasattr(data, 'copy') else dict(data)
        
#         # Convert empty strings to None for date fields
#         date_fields = ['purchase_date', 'warranty_expiry', 'last_audit_date']
#         for field_name in date_fields:
#             if field_name in data and data[field_name] == '':
#                 data[field_name] = None
        
#         # Convert UIDs/GUIDs to model instances - store in nested 'asset' dict for parent processing
#         asset_data = {}
        
#         # Map input fields to asset fields
#         field_mapping = {
#             'asset_tag': 'asset_tag',
#             'barcode': 'barcode', 
#             'serial_number': 'serial_number',
#             'asset_type': 'asset_type',
#             'manufacturer': 'manufacturer',
#             'model': 'model',
#             'purchase_date': 'purchase_date',
#             'purchase_cost': 'purchase_cost',
#             'supplier': 'supplier',
#             'asset_status': 'status',
#             'asset_condition': 'condition',
#             'location': 'location',
#             'custodian': 'custodian',
#             'warranty_expiry': 'warranty_expiry',
#             'photo': 'photo',
#             'is_active': 'is_active',
#             'last_audit_date': 'last_audit_date',
#             'asset_notes': 'notes',
#         }
        
#         # Extract asset fields into nested structure
#         for input_field, asset_field in field_mapping.items():
#             if input_field in data:
#                 asset_data[asset_field] = data[input_field]
        
#         # Convert UIDs/GUIDs for foreign keys
#         if 'asset_type' in asset_data and asset_data['asset_type']:
#             try:
#                 asset_type = AssetType.objects.get(uid=asset_data['asset_type'])
#                 asset_data['asset_type'] = asset_type.id
#             except AssetType.DoesNotExist:
#                 raise serializers.ValidationError({'asset_type': 'Invalid UID - AssetType not found'})
        
#         if 'manufacturer' in asset_data and asset_data['manufacturer']:
#             try:
#                 manufacturer = Manufacturer.objects.get(uid=asset_data['manufacturer'])
#                 asset_data['manufacturer'] = manufacturer.id
#             except Manufacturer.DoesNotExist:
#                 raise serializers.ValidationError({'manufacturer': 'Invalid UID - Manufacturer not found'})
#         elif 'manufacturer' in asset_data and asset_data['manufacturer'] == '':
#             asset_data['manufacturer'] = None
            
#         if 'supplier' in asset_data and asset_data['supplier']:
#             try:
#                 supplier = Supplier.objects.get(uid=asset_data['supplier'])
#                 asset_data['supplier'] = supplier.id
#             except Supplier.DoesNotExist:
#                 raise serializers.ValidationError({'supplier': 'Invalid UID - Supplier not found'})
#         elif 'supplier' in asset_data and asset_data['supplier'] == '':
#             asset_data['supplier'] = None
            
#         if 'location' in asset_data and asset_data['location']:
#             try:
#                 location = Location.objects.get(uid=asset_data['location'])
#                 asset_data['location'] = location.id
#             except Location.DoesNotExist:
#                 raise serializers.ValidationError({'location': 'Invalid UID - Location not found'})
#         elif 'location' in asset_data and asset_data['location'] == '':
#             asset_data['location'] = None
            
#         if 'custodian' in asset_data and asset_data['custodian']:
#             try:
#                 custodian = User.objects.get(guid=asset_data['custodian'])
#                 asset_data['custodian'] = custodian.id
#             except User.DoesNotExist:
#                 raise serializers.ValidationError({'custodian': f"Invalid GUID - User with guid {asset_data['custodian']} not found"})
#         elif 'custodian' in asset_data and asset_data['custodian'] == '':
#             asset_data['custodian'] = None
        
#         # Add asset data back into data as nested dict
#         data['asset'] = asset_data
        
#         return super().to_internal_value(data)
    
#     def to_representation(self, instance):
#         """Convert IDs back to UIDs/GUIDs for response"""
#         representation = super().to_representation(instance)
        
#         if instance.asset.asset_type:
#             representation['asset_type'] = str(instance.asset.asset_type.uid)
#         if instance.asset.manufacturer:
#             representation['manufacturer'] = str(instance.asset.manufacturer.uid)
#         if instance.asset.supplier:
#             representation['supplier'] = str(instance.asset.supplier.uid)
#         if instance.asset.location:
#             representation['location'] = str(instance.asset.location.uid)
#         if instance.asset.custodian:
#             representation['custodian'] = str(instance.asset.custodian.guid)
        
#         return representation
    
#     @transaction.atomic
#     def create(self, validated_data):
#         # Extract asset data (already processed in to_internal_value)
#         asset_data = validated_data.pop('asset', {})
        
#         # Set asset_type_id if present
#         if 'asset_type' in asset_data:
#             asset_data['asset_type_id'] = asset_data.pop('asset_type')
        
#         # Set foreign key IDs (already converted to IDs in to_internal_value)
#         if 'manufacturer' in asset_data:
#             asset_data['manufacturer_id'] = asset_data.pop('manufacturer')
#         if 'supplier' in asset_data:
#             asset_data['supplier_id'] = asset_data.pop('supplier')
#         if 'location' in asset_data:
#             asset_data['location_id'] = asset_data.pop('location')
#         if 'custodian' in asset_data:
#             asset_data['custodian_id'] = asset_data.pop('custodian')
        
#         # Set user from request
#         request = self.context.get('request')
#         user = getattr(request, 'user', None) if request else None
#         if user and user.is_authenticated:
#             asset_data['created_by'] = user
#             asset_data['updated_by'] = user
        
#         # Create asset first
#         asset = Asset.objects.create(**asset_data)
        
#         # Create computer with the asset
#         validated_data['asset'] = asset
#         return super().create(validated_data)
    
#     @transaction.atomic
#     def update(self, instance, validated_data):
#         # Extract asset data (already processed in to_internal_value)
#         asset_data = validated_data.pop('asset', {})
        
#         # Update asset fields if present
#         if asset_data:
#             # Set asset_type_id if present
#             if 'asset_type' in asset_data:
#                 asset_data['asset_type_id'] = asset_data.pop('asset_type')
            
#             # Set foreign key IDs (already converted to IDs in to_internal_value)
#             if 'manufacturer' in asset_data:
#                 asset_data['manufacturer_id'] = asset_data.pop('manufacturer')
#             if 'supplier' in asset_data:
#                 asset_data['supplier_id'] = asset_data.pop('supplier')
#             if 'location' in asset_data:
#                 asset_data['location_id'] = asset_data.pop('location')
#             if 'custodian' in asset_data:
#                 asset_data['custodian_id'] = asset_data.pop('custodian')
            
#             # Set user from request
#             request = self.context.get('request')
#             user = getattr(request, 'user', None) if request else None
#             if user and user.is_authenticated:
#                 asset_data['updated_by'] = user
            
#             # Update the asset
#             for attr, value in asset_data.items():
#                 setattr(instance.asset, attr, value)
#             instance.asset.save()
        
#         # Update computer-specific fields
#         return super().update(instance, validated_data)

# class ComputerSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
#     # Asset fields integrated directly - use source for reading from nested asset
#     asset_tag = serializers.CharField(source='asset.asset_tag')
#     barcode = serializers.CharField(source='asset.barcode', required=False, allow_blank=True)
#     serial_number = serializers.CharField(source='asset.serial_number', required=False, allow_blank=True)
#     asset_type = serializers.UUIDField(source='asset.asset_type')
#     manufacturer = serializers.UUIDField(source='asset.manufacturer', required=False, allow_null=True)
#     model = serializers.CharField(source='asset.model', required=False, allow_blank=True)
#     purchase_date = serializers.DateField(source='asset.purchase_date', required=False, allow_null=True)
#     purchase_cost = serializers.DecimalField(source='asset.purchase_cost', max_digits=10, decimal_places=2, required=False, allow_null=True)
#     supplier = serializers.UUIDField(source='asset.supplier', required=False, allow_null=True)
#     asset_status = serializers.ChoiceField(source='asset.status', choices=Asset.ASSET_STATUS, default='operational')
#     asset_condition = serializers.ChoiceField(source='asset.condition', choices=Asset.CONDITION_CHOICES, required=False, allow_blank=True)
#     location = serializers.UUIDField(source='asset.location', required=False, allow_null=True)
#     custodian = serializers.UUIDField(source='asset.custodian', required=False, allow_null=True)
#     warranty_expiry = serializers.DateField(source='asset.warranty_expiry', required=False, allow_null=True)
#     photo = serializers.CharField(source='asset.photo', max_length=200, required=False, allow_blank=True, allow_null=True)
#     is_active = serializers.BooleanField(source='asset.is_active', default=True)
#     last_audit_date = serializers.DateField(source='asset.last_audit_date', required=False, allow_null=True)
#     asset_notes = serializers.CharField(source='asset.notes', required=False, allow_blank=True)
    
#     # Read-only related fields
#     asset_type_name = RelatedFieldMixin.get_related_name('asset.asset_type')
#     manufacturer_name = RelatedFieldMixin.get_related_name('asset.manufacturer')
#     location_name = RelatedFieldMixin.get_related_name('asset.location')
#     custodian_name = RelatedFieldMixin.get_user_full_name('asset.custodian')
    
#     def get_custodian_name(self, obj):
#         if obj.asset and obj.asset.custodian:
#             return f"{obj.asset.custodian.first_name} {obj.asset.custodian.last_name}"
#         return None
    
#     class Meta:
#         model = Computer
#         fields = BaseModelSerializer.Meta.fields + [
#             # Asset fields
#             'asset_tag', 'barcode', 'serial_number', 'asset_type', 'asset_type_name',
#             'manufacturer', 'manufacturer_name', 'model', 'purchase_date', 'purchase_cost',
#             'supplier', 'asset_status', 'asset_condition', 'location', 'location_name',
#             'custodian', 'custodian_name', 'warranty_expiry', 'photo', 'is_active',
#             'last_audit_date', 'asset_notes',
#             # Computer-specific fields
#             'hostname', 'fqdn', 'processor', 'cpu_cores', 'cpu_speed_ghz', 'cpu_architecture',
#             'ram_gb', 'storage_type', 'storage_gb', 'disks', 'operating_system', 'os_version',
#             'mac_addresses', 'ip_addresses', 'management_ip', 'gpu', 'virtual',
#             'virtualization_host', 'bios_version', 'firmware_version', 'asset_tag_backup', 'notes'
#         ]
    
#     def validate_storage_type(self, value):
#         """
#         Normalize storage_type to lowercase to handle case sensitivity issues
#         between frontend and backend.
#         """
#         if value:
#             # Convert to lowercase for consistency
#             normalized_value = value.lower()
            
#             # Check if the normalized value is a valid choice
#             valid_choices = [choice[0] for choice in Computer.STORAGE_TYPES]
#             if normalized_value not in valid_choices:
#                 raise serializers.ValidationError(
#                     f"'{value}' is not a valid choice. Valid choices are: {', '.join(valid_choices)}"
#                 )
            
#             return normalized_value
#         return value
    
#     def validate_disks(self, value):
#         if not isinstance(value, list):
#             raise serializers.ValidationError("Must be a list of objects.")
#         for item in value:
#             if not isinstance(item, dict):
#                 raise serializers.ValidationError("Each item must be an object.")
#             if 'type' not in item or 'size_gb' not in item:
#                 raise serializers.ValidationError("Each item must have 'type' and 'size_gb'.")
            
#             # Also normalize disk type if present
#             if 'type' in item and item['type']:
#                 disk_type = item['type'].lower()
#                 valid_disk_types = [choice[0] for choice in Computer.STORAGE_TYPES]
#                 if disk_type not in valid_disk_types:
#                     raise serializers.ValidationError(
#                         f"Disk type '{item['type']}' is not valid. Valid types: {', '.join(valid_disk_types)}"
#                     )
#                 item['type'] = disk_type
                
#         return value
    
#     def to_internal_value(self, data):
#         # Make a copy to avoid modifying the original
#         data = data.copy() if hasattr(data, 'copy') else dict(data)
        
#         # Convert empty strings to None for date fields
#         date_fields = ['purchase_date', 'warranty_expiry', 'last_audit_date']
#         for field_name in date_fields:
#             if field_name in data and data[field_name] == '':
#                 data[field_name] = None
        
#         # Convert empty strings to None for optional FK fields
#         fk_fields = ['manufacturer', 'supplier', 'location', 'custodian']
#         for field_name in fk_fields:
#             if field_name in data and data[field_name] == '':
#                 data[field_name] = None
        
#         # Normalize storage_type to lowercase if present
#         if 'storage_type' in data and data['storage_type']:
#             data['storage_type'] = str(data['storage_type']).lower()
        
#         return super().to_internal_value(data)
    
#     def _resolve_asset_fk_ids(self, asset_data):
#         """Helper method to resolve FK UIDs/GUIDs to database IDs"""
#         mapping = {
#             'asset_type': (AssetType, 'uid'),
#             'manufacturer': (Manufacturer, 'uid'),
#             'supplier': (Supplier, 'uid'),
#             'location': (Location, 'uid'),
#             'custodian': (User, 'guid'),
#         }
        
#         for field, (model, slug) in mapping.items():
#             if field not in asset_data:
#                 continue
            
#             value = asset_data.pop(field)
            
#             # Handle None or empty string - set FK to None
#             if value in (None, ''):
#                 asset_data[f'{field}_id'] = None
#                 continue
            
#             # Look up the related object and set the FK ID
#             try:
#                 obj = model.objects.only('id').get(**{slug: value})
#                 asset_data[f'{field}_id'] = obj.id
#             except model.DoesNotExist:
#                 raise serializers.ValidationError({
#                     field: f'Invalid {slug.upper()} - {model.__name__} not found'
#                 })
    
#     def to_representation(self, instance):
#         """Convert IDs back to UIDs/GUIDs for response"""
#         representation = super().to_representation(instance)
        
#         if instance.asset.asset_type:
#             representation['asset_type'] = str(instance.asset.asset_type.uid)
#         if instance.asset.manufacturer:
#             representation['manufacturer'] = str(instance.asset.manufacturer.uid)
#         if instance.asset.supplier:
#             representation['supplier'] = str(instance.asset.supplier.uid)
#         if instance.asset.location:
#             representation['location'] = str(instance.asset.location.uid)
#         if instance.asset.custodian:
#             representation['custodian'] = str(instance.asset.custodian.guid)
        
#         return representation
    
#     @transaction.atomic
#     def create(self, validated_data):
#         # Extract asset data (already processed in to_internal_value)
#         asset_data = validated_data.pop('asset', {})
        
#         # Resolve FK UIDs/GUIDs to database IDs
#         self._resolve_asset_fk_ids(asset_data)
        
#         # Set user from request
#         request = self.context.get('request')
#         user = getattr(request, 'user', None) if request else None
#         if user and user.is_authenticated:
#             asset_data['created_by'] = user
#             asset_data['updated_by'] = user
        
#         # Create asset first
#         asset = Asset.objects.create(**asset_data)
        
#         # Create computer with the asset
#         validated_data['asset'] = asset
#         return super().create(validated_data)
    
#     @transaction.atomic
#     def update(self, instance, validated_data):
#         # Extract asset data (already processed in to_internal_value)
#         asset_data = validated_data.pop('asset', {})
        
#         # Update asset fields if present
#         if asset_data:
#             # Resolve FK UIDs/GUIDs to database IDs
#             self._resolve_asset_fk_ids(asset_data)
            
#             # Set user from request
#             request = self.context.get('request')
#             user = getattr(request, 'user', None) if request else None
#             if user and user.is_authenticated:
#                 asset_data['updated_by'] = user
            
#             # Update the asset
#             for attr, value in asset_data.items():
#                 setattr(instance.asset, attr, value)
#             instance.asset.save()
        
#         # Update computer-specific fields
#         return super().update(instance, validated_data)

class ComputerSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    # Asset fields integrated directly - use source for reading from nested asset
    asset_tag = serializers.CharField(source='asset.asset_tag')
    barcode = serializers.CharField(source='asset.barcode', required=False, allow_blank=True)
    serial_number = serializers.CharField(source='asset.serial_number', required=False, allow_blank=True)
    asset_type = serializers.UUIDField(source='asset.asset_type')
    manufacturer = serializers.UUIDField(source='asset.manufacturer', required=False, allow_null=True)
    model = serializers.CharField(source='asset.model', required=False, allow_blank=True)
    purchase_date = serializers.DateField(source='asset.purchase_date', required=False, allow_null=True)
    purchase_cost = serializers.DecimalField(source='asset.purchase_cost', max_digits=10, decimal_places=2, required=False, allow_null=True)
    supplier = serializers.UUIDField(source='asset.supplier', required=False, allow_null=True)
    asset_status = serializers.ChoiceField(source='asset.status', choices=Asset.ASSET_STATUS, default='operational')
    asset_condition = serializers.ChoiceField(source='asset.condition', choices=Asset.CONDITION_CHOICES, required=False, allow_blank=True)
    location = serializers.UUIDField(source='asset.location', required=False, allow_null=True)
    custodian = serializers.UUIDField(source='asset.custodian', required=False, allow_null=True)
    warranty_expiry = serializers.DateField(source='asset.warranty_expiry', required=False, allow_null=True)
    photo = serializers.CharField(source='asset.photo', max_length=200, required=False, allow_blank=True, allow_null=True)
    is_active = serializers.BooleanField(source='asset.is_active', default=True)
    last_audit_date = serializers.DateField(source='asset.last_audit_date', required=False, allow_null=True)
    asset_notes = serializers.CharField(source='asset.notes', required=False, allow_blank=True)
    
    # Read-only related fields
    asset_type_name = RelatedFieldMixin.get_related_name('asset.asset_type')
    manufacturer_name = RelatedFieldMixin.get_related_name('asset.manufacturer')
    location_name = RelatedFieldMixin.get_related_name('asset.location')
    custodian_name = RelatedFieldMixin.get_user_full_name('asset.custodian')
    
    def get_custodian_name(self, obj):
        if obj.asset and obj.asset.custodian:
            return f"{obj.asset.custodian.first_name} {obj.asset.custodian.last_name}"
        return None
    
    class Meta:
        model = Computer
        fields = BaseModelSerializer.Meta.fields + [
            # Asset fields
            'asset_tag', 'barcode', 'serial_number', 'asset_type', 'asset_type_name',
            'manufacturer', 'manufacturer_name', 'model', 'purchase_date', 'purchase_cost',
            'supplier', 'asset_status', 'asset_condition', 'location', 'location_name',
            'custodian', 'custodian_name', 'warranty_expiry', 'photo', 'is_active',
            'last_audit_date', 'asset_notes',
            # Computer-specific fields
            'hostname', 'fqdn', 'processor', 'cpu_cores', 'cpu_speed_ghz', 'cpu_architecture',
            'ram_gb', 'storage_type', 'storage_gb', 'disks', 'operating_system', 'os_version',
            'mac_addresses', 'ip_addresses', 'management_ip', 'gpu', 'virtual',
            'virtualization_host', 'bios_version', 'firmware_version', 'asset_tag_backup', 'notes'
        ]
    
    def validate_storage_type(self, value):
        """
        Normalize storage_type to lowercase to handle case sensitivity issues
        between frontend and backend.
        """
        if value:
            # Convert to lowercase for consistency
            normalized_value = value.lower()
            
            # Check if the normalized value is a valid choice
            valid_choices = [choice[0] for choice in Computer.STORAGE_TYPES]
            if normalized_value not in valid_choices:
                raise serializers.ValidationError(
                    f"'{value}' is not a valid choice. Valid choices are: {', '.join(valid_choices)}"
                )
            
            return normalized_value
        return value
    
    def validate_disks(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a list of objects.")
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Each item must be an object.")
            if 'type' not in item or 'size_gb' not in item:
                raise serializers.ValidationError("Each item must have 'type' and 'size_gb'.")
            
            # Also normalize disk type if present
            if 'type' in item and item['type']:
                disk_type = item['type'].lower()
                valid_disk_types = [choice[0] for choice in Computer.STORAGE_TYPES]
                if disk_type not in valid_disk_types:
                    raise serializers.ValidationError(
                        f"Disk type '{item['type']}' is not valid. Valid types: {', '.join(valid_disk_types)}"
                    )
                item['type'] = disk_type
                
        return value
    
    def to_internal_value(self, data):
        # Make a copy to avoid modifying the original
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Convert empty strings to None for date fields
        date_fields = ['purchase_date', 'warranty_expiry', 'last_audit_date']
        for field_name in date_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        # Convert empty strings to None for optional FK fields
        fk_fields = ['manufacturer', 'supplier', 'location', 'custodian']
        for field_name in fk_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        # Normalize storage_type to lowercase if present
        if 'storage_type' in data and data['storage_type']:
            data['storage_type'] = str(data['storage_type']).lower()
        
        return super().to_internal_value(data)
    
    def _resolve_asset_fk_ids(self, asset_data):
        """Helper method to resolve FK UIDs/GUIDs to database IDs"""
        mapping = {
            'asset_type': (AssetType, 'uid'),
            'manufacturer': (Manufacturer, 'uid'),
            'supplier': (Supplier, 'uid'),
            'location': (Location, 'uid'),
            'custodian': (User, 'guid'),
        }
        
        for field, (model, slug) in mapping.items():
            if field not in asset_data:
                continue
            
            value = asset_data.pop(field)
            
            # Handle None or empty string - set FK to None
            if value in (None, ''):
                asset_data[f'{field}_id'] = None
                continue
            
            # Look up the related object and set the FK ID
            try:
                obj = model.objects.only('id').get(**{slug: value})
                asset_data[f'{field}_id'] = obj.id
            except model.DoesNotExist:
                raise serializers.ValidationError({
                    field: f'Invalid {slug.upper()} - {model.__name__} not found'
                })
    
    def to_representation(self, instance):
        """
        Convert IDs back to UIDs/GUIDs for response and include asset UID
        for frontend operations (maintenance records, support tickets, etc.)
        """
        representation = super().to_representation(instance)
        
        # CRITICAL: Add the asset UID so frontend can reference it
        if instance.asset:
            representation['asset_uid'] = str(instance.asset.uid)
            representation['asset'] = str(instance.asset.uid)  # For backward compatibility
            
            # Ensure all source-mapped fields are properly populated
            if not representation.get('asset_tag') and instance.asset.asset_tag:
                representation['asset_tag'] = instance.asset.asset_tag
            if not representation.get('serial_number') and instance.asset.serial_number:
                representation['serial_number'] = instance.asset.serial_number
            if not representation.get('barcode') and instance.asset.barcode:
                representation['barcode'] = instance.asset.barcode
        
        # Convert FK IDs to UIDs/GUIDs
        if instance.asset.asset_type:
            representation['asset_type'] = str(instance.asset.asset_type.uid)
        if instance.asset.manufacturer:
            representation['manufacturer'] = str(instance.asset.manufacturer.uid)
        if instance.asset.supplier:
            representation['supplier'] = str(instance.asset.supplier.uid)
        if instance.asset.location:
            representation['location'] = str(instance.asset.location.uid)
        if instance.asset.custodian:
            representation['custodian'] = str(instance.asset.custodian.guid)
        
        return representation
    
    @transaction.atomic
    def create(self, validated_data):
        # Extract asset data (already processed in to_internal_value)
        asset_data = validated_data.pop('asset', {})
        
        # Resolve FK UIDs/GUIDs to database IDs
        self._resolve_asset_fk_ids(asset_data)
        
        # Set user from request
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        if user and user.is_authenticated:
            asset_data['created_by'] = user
            asset_data['updated_by'] = user
        
        # Create asset first
        asset = Asset.objects.create(**asset_data)
        
        # Create computer with the asset
        validated_data['asset'] = asset
        return super().create(validated_data)
    
    @transaction.atomic
    def update(self, instance, validated_data):
        # Extract asset data (already processed in to_internal_value)
        asset_data = validated_data.pop('asset', {})
        
        # Update asset fields if present
        if asset_data:
            # Resolve FK UIDs/GUIDs to database IDs
            self._resolve_asset_fk_ids(asset_data)
            
            # Set user from request
            request = self.context.get('request')
            user = getattr(request, 'user', None) if request else None
            if user and user.is_authenticated:
                asset_data['updated_by'] = user
            
            # Update the asset
            for attr, value in asset_data.items():
                setattr(instance.asset, attr, value)
            instance.asset.save()
        
        # Update computer-specific fields
        return super().update(instance, validated_data)
    

# class NetworkDeviceSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
#     # Asset fields integrated directly - use source for reading from nested asset
#     asset_tag = serializers.CharField(source='asset.asset_tag')
#     barcode = serializers.CharField(source='asset.barcode', required=False, allow_blank=True)
#     serial_number = serializers.CharField(source='asset.serial_number', required=False, allow_blank=True, allow_null=True)
#     asset_type = serializers.UUIDField(source='asset.asset_type')
#     manufacturer = serializers.UUIDField(source='asset.manufacturer', required=False, allow_null=True)
#     model = serializers.CharField(source='asset.model', required=False, allow_blank=True)
#     purchase_date = serializers.DateField(source='asset.purchase_date', required=False, allow_null=True)
#     purchase_cost = serializers.DecimalField(source='asset.purchase_cost', max_digits=10, decimal_places=2, required=False, allow_null=True)
#     supplier = serializers.UUIDField(source='asset.supplier', required=False, allow_null=True)
#     asset_status = serializers.ChoiceField(source='asset.status', choices=Asset.ASSET_STATUS, default='operational')
#     asset_condition = serializers.ChoiceField(source='asset.condition', choices=Asset.CONDITION_CHOICES, required=False, allow_blank=True)
#     location = serializers.UUIDField(source='asset.location', required=False, allow_null=True)
#     custodian = serializers.UUIDField(source='asset.custodian', required=False, allow_null=True)
#     warranty_expiry = serializers.DateField(source='asset.warranty_expiry', required=False, allow_null=True)
#     photo = serializers.CharField(source='asset.photo', max_length=200, required=False, allow_blank=True, allow_null=True)
#     is_active = serializers.BooleanField(source='asset.is_active', default=True)
#     last_audit_date = serializers.DateField(source='asset.last_audit_date', required=False, allow_null=True)
#     asset_notes = serializers.CharField(source='asset.notes', required=False, allow_blank=True)
    
#     # Read-only related fields
#     asset_type_name = RelatedFieldMixin.get_related_name('asset.asset_type')
#     manufacturer_name = RelatedFieldMixin.get_related_name('asset.manufacturer')
#     location_name = RelatedFieldMixin.get_related_name('asset.location')
#     custodian_name = RelatedFieldMixin.get_user_full_name('asset.custodian')
    
#     def get_custodian_name(self, obj):
#         if obj.asset and obj.asset.custodian:
#             return f"{obj.asset.custodian.first_name} {obj.asset.custodian.last_name}"
#         return None
    
#     class Meta:
#         model = NetworkDevice
#         fields = BaseModelSerializer.Meta.fields + [
#             # Asset fields
#             'asset_tag', 'barcode', 'serial_number', 'asset_type', 'asset_type_name',
#             'manufacturer', 'manufacturer_name', 'model', 'purchase_date', 'purchase_cost',
#             'supplier', 'asset_status', 'asset_condition', 'location', 'location_name',
#             'custodian', 'custodian_name', 'warranty_expiry', 'photo', 'is_active',
#             'last_audit_date', 'asset_notes',
#             # NetworkDevice-specific fields
#             'device_type', 'ip_address', 'mac_address', 'ports'
#         ]
    
#     def to_internal_value(self, data):
#         # Make a copy to avoid modifying the original
#         data = data.copy() if hasattr(data, 'copy') else dict(data)
        
#         # Convert empty strings to None for date fields
#         date_fields = ['purchase_date', 'warranty_expiry', 'last_audit_date']
#         for field_name in date_fields:
#             if field_name in data and data[field_name] == '':
#                 data[field_name] = None
        
#         # Convert UIDs/GUIDs to model instances - store in nested 'asset' dict
#         asset_data = {}
        
#         # Map input fields to asset fields
#         field_mapping = {
#             'asset_tag': 'asset_tag',
#             'barcode': 'barcode', 
#             'serial_number': 'serial_number',
#             'asset_type': 'asset_type',
#             'manufacturer': 'manufacturer',
#             'model': 'model',
#             'purchase_date': 'purchase_date',
#             'purchase_cost': 'purchase_cost',
#             'supplier': 'supplier',
#             'asset_status': 'status',
#             'asset_condition': 'condition',
#             'location': 'location',
#             'custodian': 'custodian',
#             'warranty_expiry': 'warranty_expiry',
#             'photo': 'photo',
#             'is_active': 'is_active',
#             'last_audit_date': 'last_audit_date',
#             'asset_notes': 'notes',
#         }
        
#         # Extract asset fields into nested structure
#         for input_field, asset_field in field_mapping.items():
#             if input_field in data:
#                 asset_data[asset_field] = data[input_field]
        
#         # Convert UIDs/GUIDs for foreign keys
#         if 'asset_type' in asset_data and asset_data['asset_type']:
#             try:
#                 asset_type = AssetType.objects.get(uid=asset_data['asset_type'])
#                 asset_data['asset_type'] = asset_type.id
#             except AssetType.DoesNotExist:
#                 raise serializers.ValidationError({'asset_type': 'Invalid UID - AssetType not found'})
        
#         if 'manufacturer' in asset_data and asset_data['manufacturer']:
#             try:
#                 manufacturer = Manufacturer.objects.get(uid=asset_data['manufacturer'])
#                 asset_data['manufacturer'] = manufacturer.id
#             except Manufacturer.DoesNotExist:
#                 raise serializers.ValidationError({'manufacturer': 'Invalid UID - Manufacturer not found'})
#         elif 'manufacturer' in asset_data and asset_data['manufacturer'] == '':
#             asset_data['manufacturer'] = None
            
#         if 'supplier' in asset_data and asset_data['supplier']:
#             try:
#                 supplier = Supplier.objects.get(uid=asset_data['supplier'])
#                 asset_data['supplier'] = supplier.id
#             except Supplier.DoesNotExist:
#                 raise serializers.ValidationError({'supplier': 'Invalid UID - Supplier not found'})
#         elif 'supplier' in asset_data and asset_data['supplier'] == '':
#             asset_data['supplier'] = None
            
#         if 'location' in asset_data and asset_data['location']:
#             try:
#                 location = Location.objects.get(uid=asset_data['location'])
#                 asset_data['location'] = location.id
#             except Location.DoesNotExist:
#                 raise serializers.ValidationError({'location': 'Invalid UID - Location not found'})
#         elif 'location' in asset_data and asset_data['location'] == '':
#             asset_data['location'] = None
            
#         if 'custodian' in asset_data and asset_data['custodian']:
#             try:
#                 custodian = User.objects.get(guid=asset_data['custodian'])
#                 asset_data['custodian'] = custodian.id
#             except User.DoesNotExist:
#                 raise serializers.ValidationError({'custodian': f"Invalid GUID - User with guid {asset_data['custodian']} not found"})
#         elif 'custodian' in asset_data and asset_data['custodian'] == '':
#             asset_data['custodian'] = None
        
#         # Add asset data back into data as nested dict
#         data['asset'] = asset_data
        
#         return super().to_internal_value(data)
    
#     def to_representation(self, instance):
#         """Convert IDs back to UIDs/GUIDs for response"""
#         representation = super().to_representation(instance)
        
#         if instance.asset.asset_type:
#             representation['asset_type'] = str(instance.asset.asset_type.uid)
#         if instance.asset.manufacturer:
#             representation['manufacturer'] = str(instance.asset.manufacturer.uid)
#         if instance.asset.supplier:
#             representation['supplier'] = str(instance.asset.supplier.uid)
#         if instance.asset.location:
#             representation['location'] = str(instance.asset.location.uid)
#         if instance.asset.custodian:
#             representation['custodian'] = str(instance.asset.custodian.guid)
        
#         return representation
    
#     @transaction.atomic
#     def create(self, validated_data):
#         # Extract asset data (already processed in to_internal_value)
#         asset_data = validated_data.pop('asset', {})
        
#         # Set asset_type_id if present
#         if 'asset_type' in asset_data:
#             asset_data['asset_type_id'] = asset_data.pop('asset_type')
        
#         # Set foreign key IDs (already converted to IDs in to_internal_value)
#         if 'manufacturer' in asset_data:
#             asset_data['manufacturer_id'] = asset_data.pop('manufacturer')
#         if 'supplier' in asset_data:
#             asset_data['supplier_id'] = asset_data.pop('supplier')
#         if 'location' in asset_data:
#             asset_data['location_id'] = asset_data.pop('location')
#         if 'custodian' in asset_data:
#             asset_data['custodian_id'] = asset_data.pop('custodian')
        
#         # Set user from request
#         request = self.context.get('request')
#         user = getattr(request, 'user', None) if request else None
#         if user and user.is_authenticated:
#             asset_data['created_by'] = user
#             asset_data['updated_by'] = user
        
#         # Create asset first
#         asset = Asset.objects.create(**asset_data)
        
#         # Create network device with the asset
#         validated_data['asset'] = asset
#         return super().create(validated_data)
    
#     @transaction.atomic
#     def update(self, instance, validated_data):
#         # Extract asset data (already processed in to_internal_value)
#         asset_data = validated_data.pop('asset', {})
        
#         # Update asset fields if present
#         if asset_data:
#             # Set asset_type_id if present
#             if 'asset_type' in asset_data:
#                 asset_data['asset_type_id'] = asset_data.pop('asset_type')
            
#             # Set foreign key IDs (already converted to IDs in to_internal_value)
#             if 'manufacturer' in asset_data:
#                 asset_data['manufacturer_id'] = asset_data.pop('manufacturer')
#             if 'supplier' in asset_data:
#                 asset_data['supplier_id'] = asset_data.pop('supplier')
#             if 'location' in asset_data:
#                 asset_data['location_id'] = asset_data.pop('location')
#             if 'custodian' in asset_data:
#                 asset_data['custodian_id'] = asset_data.pop('custodian')
            
#             # Set user from request
#             request = self.context.get('request')
#             user = getattr(request, 'user', None) if request else None
#             if user and user.is_authenticated:
#                 asset_data['updated_by'] = user
            
#             # Update the asset
#             for attr, value in asset_data.items():
#                 setattr(instance.asset, attr, value)
#             instance.asset.save()
        
#         # Update network device-specific fields
#         return super().update(instance, validated_data)

class NetworkDeviceSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    # Asset fields integrated directly - use source for reading from nested asset
    asset_tag = serializers.CharField(source='asset.asset_tag')
    barcode = serializers.CharField(source='asset.barcode', required=False, allow_blank=True)
    serial_number = serializers.CharField(source='asset.serial_number', required=False, allow_blank=True, allow_null=True)
    asset_type = serializers.UUIDField(source='asset.asset_type')
    manufacturer = serializers.UUIDField(source='asset.manufacturer', required=False, allow_null=True)
    model = serializers.CharField(source='asset.model', required=False, allow_blank=True)
    purchase_date = serializers.DateField(source='asset.purchase_date', required=False, allow_null=True)
    purchase_cost = serializers.DecimalField(source='asset.purchase_cost', max_digits=10, decimal_places=2, required=False, allow_null=True)
    supplier = serializers.UUIDField(source='asset.supplier', required=False, allow_null=True)
    asset_status = serializers.ChoiceField(source='asset.status', choices=Asset.ASSET_STATUS, default='operational')
    asset_condition = serializers.ChoiceField(source='asset.condition', choices=Asset.CONDITION_CHOICES, required=False, allow_blank=True)
    location = serializers.UUIDField(source='asset.location', required=False, allow_null=True)
    custodian = serializers.UUIDField(source='asset.custodian', required=False, allow_null=True)
    warranty_expiry = serializers.DateField(source='asset.warranty_expiry', required=False, allow_null=True)
    photo = serializers.CharField(source='asset.photo', max_length=200, required=False, allow_blank=True, allow_null=True)
    is_active = serializers.BooleanField(source='asset.is_active', default=True)
    last_audit_date = serializers.DateField(source='asset.last_audit_date', required=False, allow_null=True)
    asset_notes = serializers.CharField(source='asset.notes', required=False, allow_blank=True)
    
    # Read-only related fields
    asset_type_name = RelatedFieldMixin.get_related_name('asset.asset_type')
    manufacturer_name = RelatedFieldMixin.get_related_name('asset.manufacturer')
    location_name = RelatedFieldMixin.get_related_name('asset.location')
    custodian_name = RelatedFieldMixin.get_user_full_name('asset.custodian')
    
    def get_custodian_name(self, obj):
        if obj.asset and obj.asset.custodian:
            return f"{obj.asset.custodian.first_name} {obj.asset.custodian.last_name}"
        return None
    
    class Meta:
        model = NetworkDevice
        fields = BaseModelSerializer.Meta.fields + [
            # Asset fields
            'asset_tag', 'barcode', 'serial_number', 'asset_type', 'asset_type_name',
            'manufacturer', 'manufacturer_name', 'model', 'purchase_date', 'purchase_cost',
            'supplier', 'asset_status', 'asset_condition', 'location', 'location_name',
            'custodian', 'custodian_name', 'warranty_expiry', 'photo', 'is_active',
            'last_audit_date', 'asset_notes',
            # NetworkDevice-specific fields
            'device_type', 'ip_address', 'mac_address', 'ports'
        ]
    
    def to_internal_value(self, data):
        # Make a copy to avoid modifying the original
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Convert empty strings to None for date fields
        date_fields = ['purchase_date', 'warranty_expiry', 'last_audit_date']
        for field_name in date_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        # Convert empty strings to None for optional FK fields
        fk_fields = ['manufacturer', 'supplier', 'location', 'custodian']
        for field_name in fk_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        return super().to_internal_value(data)
    
    def _resolve_asset_fk_ids(self, asset_data):
        """Helper method to resolve FK UIDs/GUIDs to database IDs"""
        mapping = {
            'asset_type': (AssetType, 'uid'),
            'manufacturer': (Manufacturer, 'uid'),
            'supplier': (Supplier, 'uid'),
            'location': (Location, 'uid'),
            'custodian': (User, 'guid'),
        }
        
        for field, (model, slug) in mapping.items():
            if field not in asset_data:
                continue
            
            value = asset_data.pop(field)
            
            # Handle None or empty string - set FK to None
            if value in (None, ''):
                asset_data[f'{field}_id'] = None
                continue
            
            # Look up the related object and set the FK ID
            try:
                obj = model.objects.only('id').get(**{slug: value})
                asset_data[f'{field}_id'] = obj.id
            except model.DoesNotExist:
                raise serializers.ValidationError({
                    field: f'Invalid {slug.upper()} - {model.__name__} not found'
                })
    
    def to_representation(self, instance):
        """
        Convert IDs back to UIDs/GUIDs for response and include asset UID
        for frontend operations (maintenance records, support tickets, etc.)
        """
        representation = super().to_representation(instance)
        
        # CRITICAL: Add the asset UID so frontend can reference it
        if instance.asset:
            representation['asset_uid'] = str(instance.asset.uid)
            representation['asset'] = str(instance.asset.uid)  # For backward compatibility
            
            # Ensure all source-mapped fields are properly populated
            if not representation.get('asset_tag') and instance.asset.asset_tag:
                representation['asset_tag'] = instance.asset.asset_tag
            if not representation.get('serial_number') and instance.asset.serial_number:
                representation['serial_number'] = instance.asset.serial_number
            if not representation.get('barcode') and instance.asset.barcode:
                representation['barcode'] = instance.asset.barcode
        
        # Convert FK IDs to UIDs/GUIDs
        if instance.asset.asset_type:
            representation['asset_type'] = str(instance.asset.asset_type.uid)
        if instance.asset.manufacturer:
            representation['manufacturer'] = str(instance.asset.manufacturer.uid)
        if instance.asset.supplier:
            representation['supplier'] = str(instance.asset.supplier.uid)
        if instance.asset.location:
            representation['location'] = str(instance.asset.location.uid)
        if instance.asset.custodian:
            representation['custodian'] = str(instance.asset.custodian.guid)
        
        return representation
    
    @transaction.atomic
    def create(self, validated_data):
        # Extract asset data (already processed via source mapping)
        asset_data = validated_data.pop('asset', {})
        
        # Resolve FK UIDs/GUIDs to database IDs
        self._resolve_asset_fk_ids(asset_data)
        
        # Set user from request for the Asset
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        if user and user.is_authenticated:
            asset_data['created_by'] = user
            asset_data['updated_by'] = user
        
        # Create asset first
        asset = Asset.objects.create(**asset_data)
        
        # Create network device with the asset
        validated_data['asset'] = asset
        return super().create(validated_data)
    
    @transaction.atomic
    def update(self, instance, validated_data):
        # Extract asset data (already processed via source mapping)
        asset_data = validated_data.pop('asset', {})
        
        # Update asset fields if present
        if asset_data:
            # Resolve FK UIDs/GUIDs to database IDs
            self._resolve_asset_fk_ids(asset_data)
            
            # Set user from request
            request = self.context.get('request')
            user = getattr(request, 'user', None) if request else None
            if user and user.is_authenticated:
                asset_data['updated_by'] = user
            
            # Update the asset
            for attr, value in asset_data.items():
                setattr(instance.asset, attr, value)
            instance.asset.save()
        
        # Update network device-specific fields
        return super().update(instance, validated_data)
    

# class PeripheralSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
#     # Asset fields integrated directly - use source for reading from nested asset
#     asset_tag = serializers.CharField(source='asset.asset_tag')
#     barcode = serializers.CharField(source='asset.barcode', required=False, allow_blank=True)
#     serial_number = serializers.CharField(source='asset.serial_number', required=False, allow_blank=True, allow_null=True)
#     asset_type = serializers.UUIDField(source='asset.asset_type')
#     manufacturer = serializers.UUIDField(source='asset.manufacturer', required=False, allow_null=True)
#     model = serializers.CharField(source='asset.model', required=False, allow_blank=True)
#     purchase_date = serializers.DateField(source='asset.purchase_date', required=False, allow_null=True)
#     purchase_cost = serializers.DecimalField(source='asset.purchase_cost', max_digits=10, decimal_places=2, required=False, allow_null=True)
#     supplier = serializers.UUIDField(source='asset.supplier', required=False, allow_null=True)
#     asset_status = serializers.ChoiceField(source='asset.status', choices=Asset.ASSET_STATUS, default='operational')
#     asset_condition = serializers.ChoiceField(source='asset.condition', choices=Asset.CONDITION_CHOICES, required=False, allow_blank=True)
#     location = serializers.UUIDField(source='asset.location', required=False, allow_null=True)
#     custodian = serializers.UUIDField(source='asset.custodian', required=False, allow_null=True)
#     warranty_expiry = serializers.DateField(source='asset.warranty_expiry', required=False, allow_null=True)
#     photo = serializers.CharField(source='asset.photo', max_length=200, required=False, allow_blank=True, allow_null=True)
#     is_active = serializers.BooleanField(source='asset.is_active', default=True)
#     last_audit_date = serializers.DateField(source='asset.last_audit_date', required=False, allow_null=True)
#     asset_notes = serializers.CharField(source='asset.notes', required=False, allow_blank=True)
    
#     # Read-only related fields
#     asset_type_name = RelatedFieldMixin.get_related_name('asset.asset_type')
#     manufacturer_name = RelatedFieldMixin.get_related_name('asset.manufacturer')
#     location_name = RelatedFieldMixin.get_related_name('asset.location')
#     custodian_name = RelatedFieldMixin.get_user_full_name('asset.custodian')
    
#     def get_custodian_name(self, obj):
#         if obj.asset and obj.asset.custodian:
#             return f"{obj.asset.custodian.first_name} {obj.asset.custodian.last_name}"
#         return None
    
#     class Meta:
#         model = Peripheral
#         fields = BaseModelSerializer.Meta.fields + [
#             # Asset fields
#             'asset_tag', 'barcode', 'serial_number', 'asset_type', 'asset_type_name',
#             'manufacturer', 'manufacturer_name', 'model', 'purchase_date', 'purchase_cost',
#             'supplier', 'asset_status', 'asset_condition', 'location', 'location_name',
#             'custodian', 'custodian_name', 'warranty_expiry', 'photo', 'is_active',
#             'last_audit_date', 'asset_notes',
#             # Peripheral-specific fields
#             'peripheral_type', 'connection_type'
#         ]
    
#     def to_internal_value(self, data):
#         # Make a copy to avoid modifying the original
#         data = data.copy() if hasattr(data, 'copy') else dict(data)
        
#         # Convert empty strings to None for date fields
#         date_fields = ['purchase_date', 'warranty_expiry', 'last_audit_date']
#         for field_name in date_fields:
#             if field_name in data and data[field_name] == '':
#                 data[field_name] = None
        
#         # Convert UIDs/GUIDs to model instances - store in nested 'asset' dict
#         asset_data = {}
        
#         # Map input fields to asset fields
#         field_mapping = {
#             'asset_tag': 'asset_tag',
#             'barcode': 'barcode', 
#             'serial_number': 'serial_number',
#             'asset_type': 'asset_type',
#             'manufacturer': 'manufacturer',
#             'model': 'model',
#             'purchase_date': 'purchase_date',
#             'purchase_cost': 'purchase_cost',
#             'supplier': 'supplier',
#             'asset_status': 'status',
#             'asset_condition': 'condition',
#             'location': 'location',
#             'custodian': 'custodian',
#             'warranty_expiry': 'warranty_expiry',
#             'photo': 'photo',
#             'is_active': 'is_active',
#             'last_audit_date': 'last_audit_date',
#             'asset_notes': 'notes',
#         }
        
#         # Extract asset fields into nested structure
#         for input_field, asset_field in field_mapping.items():
#             if input_field in data:
#                 asset_data[asset_field] = data[input_field]
        
#         # Convert UIDs/GUIDs for foreign keys
#         if 'asset_type' in asset_data and asset_data['asset_type']:
#             try:
#                 asset_type = AssetType.objects.get(uid=asset_data['asset_type'])
#                 asset_data['asset_type'] = asset_type.id
#             except AssetType.DoesNotExist:
#                 raise serializers.ValidationError({'asset_type': 'Invalid UID - AssetType not found'})
        
#         if 'manufacturer' in asset_data and asset_data['manufacturer']:
#             try:
#                 manufacturer = Manufacturer.objects.get(uid=asset_data['manufacturer'])
#                 asset_data['manufacturer'] = manufacturer.id
#             except Manufacturer.DoesNotExist:
#                 raise serializers.ValidationError({'manufacturer': 'Invalid UID - Manufacturer not found'})
#         elif 'manufacturer' in asset_data and asset_data['manufacturer'] == '':
#             asset_data['manufacturer'] = None
            
#         if 'supplier' in asset_data and asset_data['supplier']:
#             try:
#                 supplier = Supplier.objects.get(uid=asset_data['supplier'])
#                 asset_data['supplier'] = supplier.id
#             except Supplier.DoesNotExist:
#                 raise serializers.ValidationError({'supplier': 'Invalid UID - Supplier not found'})
#         elif 'supplier' in asset_data and asset_data['supplier'] == '':
#             asset_data['supplier'] = None
            
#         if 'location' in asset_data and asset_data['location']:
#             try:
#                 location = Location.objects.get(uid=asset_data['location'])
#                 asset_data['location'] = location.id
#             except Location.DoesNotExist:
#                 raise serializers.ValidationError({'location': 'Invalid UID - Location not found'})
#         elif 'location' in asset_data and asset_data['location'] == '':
#             asset_data['location'] = None
            
#         if 'custodian' in asset_data and asset_data['custodian']:
#             try:
#                 custodian = User.objects.get(guid=asset_data['custodian'])
#                 asset_data['custodian'] = custodian.id
#             except User.DoesNotExist:
#                 raise serializers.ValidationError({'custodian': f"Invalid GUID - User with guid {asset_data['custodian']} not found"})
#         elif 'custodian' in asset_data and asset_data['custodian'] == '':
#             asset_data['custodian'] = None
        
#         # Add asset data back into data as nested dict
#         data['asset'] = asset_data
        
#         return super().to_internal_value(data)
    
#     def to_representation(self, instance):
#         """Convert IDs back to UIDs/GUIDs for response"""
#         representation = super().to_representation(instance)
        
#         if instance.asset.asset_type:
#             representation['asset_type'] = str(instance.asset.asset_type.uid)
#         if instance.asset.manufacturer:
#             representation['manufacturer'] = str(instance.asset.manufacturer.uid)
#         if instance.asset.supplier:
#             representation['supplier'] = str(instance.asset.supplier.uid)
#         if instance.asset.location:
#             representation['location'] = str(instance.asset.location.uid)
#         if instance.asset.custodian:
#             representation['custodian'] = str(instance.asset.custodian.guid)
        
#         return representation
    
#     @transaction.atomic
#     def create(self, validated_data):
#         # Extract asset data (already processed in to_internal_value)
#         asset_data = validated_data.pop('asset', {})
        
#         # Set asset_type_id if present
#         if 'asset_type' in asset_data:
#             asset_data['asset_type_id'] = asset_data.pop('asset_type')
        
#         # Set foreign key IDs (already converted to IDs in to_internal_value)
#         if 'manufacturer' in asset_data:
#             asset_data['manufacturer_id'] = asset_data.pop('manufacturer')
#         if 'supplier' in asset_data:
#             asset_data['supplier_id'] = asset_data.pop('supplier')
#         if 'location' in asset_data:
#             asset_data['location_id'] = asset_data.pop('location')
#         if 'custodian' in asset_data:
#             asset_data['custodian_id'] = asset_data.pop('custodian')
        
#         # Set user from request
#         request = self.context.get('request')
#         user = getattr(request, 'user', None) if request else None
#         if user and user.is_authenticated:
#             asset_data['created_by'] = user
#             asset_data['updated_by'] = user
        
#         # Create asset first
#         asset = Asset.objects.create(**asset_data)
        
#         # Create peripheral with the asset
#         validated_data['asset'] = asset
#         return super().create(validated_data)
    
#     @transaction.atomic
#     def update(self, instance, validated_data):
#         # Extract asset data (already processed in to_internal_value)
#         asset_data = validated_data.pop('asset', {})
        
#         # Update asset fields if present
#         if asset_data:
#             # Set asset_type_id if present
#             if 'asset_type' in asset_data:
#                 asset_data['asset_type_id'] = asset_data.pop('asset_type')
            
#             # Set foreign key IDs (already converted to IDs in to_internal_value)
#             if 'manufacturer' in asset_data:
#                 asset_data['manufacturer_id'] = asset_data.pop('manufacturer')
#             if 'supplier' in asset_data:
#                 asset_data['supplier_id'] = asset_data.pop('supplier')
#             if 'location' in asset_data:
#                 asset_data['location_id'] = asset_data.pop('location')
#             if 'custodian' in asset_data:
#                 asset_data['custodian_id'] = asset_data.pop('custodian')
            
#             # Set user from request
#             request = self.context.get('request')
#             user = getattr(request, 'user', None) if request else None
#             if user and user.is_authenticated:
#                 asset_data['updated_by'] = user
            
#             # Update the asset
#             for attr, value in asset_data.items():
#                 setattr(instance.asset, attr, value)
#             instance.asset.save()
        
#         # Update peripheral-specific fields
#         return super().update(instance, validated_data)

class PeripheralSerializer(SaveWithRequestUserMixin, BaseModelSerializer): 
    # Asset fields integrated directly - use source for reading from nested asset
    asset_tag = serializers.CharField(source='asset.asset_tag')
    barcode = serializers.CharField(source='asset.barcode', required=False, allow_blank=True)
    serial_number = serializers.CharField(source='asset.serial_number', required=False, allow_blank=True, allow_null=True)
    asset_type = serializers.UUIDField(source='asset.asset_type')
    manufacturer = serializers.UUIDField(source='asset.manufacturer', required=False, allow_null=True)
    model = serializers.CharField(source='asset.model', required=False, allow_blank=True)
    purchase_date = serializers.DateField(source='asset.purchase_date', required=False, allow_null=True)
    purchase_cost = serializers.DecimalField(source='asset.purchase_cost', max_digits=10, decimal_places=2, required=False, allow_null=True)
    supplier = serializers.UUIDField(source='asset.supplier', required=False, allow_null=True)
    asset_status = serializers.ChoiceField(source='asset.status', choices=Asset.ASSET_STATUS, default='operational')
    asset_condition = serializers.ChoiceField(source='asset.condition', choices=Asset.CONDITION_CHOICES, required=False, allow_blank=True)
    location = serializers.UUIDField(source='asset.location', required=False, allow_null=True)
    custodian = serializers.UUIDField(source='asset.custodian', required=False, allow_null=True)
    warranty_expiry = serializers.DateField(source='asset.warranty_expiry', required=False, allow_null=True)
    photo = serializers.CharField(source='asset.photo', max_length=200, required=False, allow_blank=True, allow_null=True)
    is_active = serializers.BooleanField(source='asset.is_active', default=True)
    last_audit_date = serializers.DateField(source='asset.last_audit_date', required=False, allow_null=True)
    asset_notes = serializers.CharField(source='asset.notes', required=False, allow_blank=True)
    
    # Read-only related fields
    asset_type_name = RelatedFieldMixin.get_related_name('asset.asset_type')
    manufacturer_name = RelatedFieldMixin.get_related_name('asset.manufacturer')
    location_name = RelatedFieldMixin.get_related_name('asset.location')
    custodian_name = RelatedFieldMixin.get_user_full_name('asset.custodian')
    
    def get_custodian_name(self, obj):
        if obj.asset and obj.asset.custodian:
            return f"{obj.asset.custodian.first_name} {obj.asset.custodian.last_name}"
        return None
    
    class Meta:
        model = Peripheral
        fields = BaseModelSerializer.Meta.fields + [
            # Asset fields
            'asset_tag', 'barcode', 'serial_number', 'asset_type', 'asset_type_name',
            'manufacturer', 'manufacturer_name', 'model', 'purchase_date', 'purchase_cost',
            'supplier', 'asset_status', 'asset_condition', 'location', 'location_name',
            'custodian', 'custodian_name', 'warranty_expiry', 'photo', 'is_active',
            'last_audit_date', 'asset_notes',
            # Peripheral-specific fields
            'peripheral_type', 'connection_type'
        ]
    
    def to_internal_value(self, data):
        # Make a copy to avoid modifying the original
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Convert empty strings to None for date fields
        date_fields = ['purchase_date', 'warranty_expiry', 'last_audit_date']
        for field_name in date_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        # Convert empty strings to None for optional FK fields
        fk_fields = ['manufacturer', 'supplier', 'location', 'custodian']
        for field_name in fk_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        return super().to_internal_value(data)
    
    def _resolve_asset_fk_ids(self, asset_data):
        """Helper method to resolve FK UIDs/GUIDs to database IDs"""
        mapping = {
            'asset_type': (AssetType, 'uid'),
            'manufacturer': (Manufacturer, 'uid'),
            'supplier': (Supplier, 'uid'),
            'location': (Location, 'uid'),
            'custodian': (User, 'guid'),
        }
        
        for field, (model, slug) in mapping.items():
            if field not in asset_data:
                continue
            
            value = asset_data.pop(field)
            
            # Handle None or empty string - set FK to None
            if value in (None, ''):
                asset_data[f'{field}_id'] = None
                continue
            
            # Look up the related object and set the FK ID
            try:
                obj = model.objects.only('id').get(**{slug: value})
                asset_data[f'{field}_id'] = obj.id
            except model.DoesNotExist:
                raise serializers.ValidationError({
                    field: f'Invalid {slug.upper()} - {model.__name__} not found'
                })
    
    def to_representation(self, instance):
        """
        Convert IDs back to UIDs/GUIDs for response and include asset UID
        for frontend operations (maintenance records, support tickets, etc.)
        """
        representation = super().to_representation(instance)
        
        # CRITICAL: Add the asset UID so frontend can reference it
        if instance.asset:
            representation['asset_uid'] = str(instance.asset.uid)
            representation['asset'] = str(instance.asset.uid)  # For backward compatibility
            
            # Ensure all source-mapped fields are properly populated
            if not representation.get('asset_tag') and instance.asset.asset_tag:
                representation['asset_tag'] = instance.asset.asset_tag
            if not representation.get('serial_number') and instance.asset.serial_number:
                representation['serial_number'] = instance.asset.serial_number
            if not representation.get('barcode') and instance.asset.barcode:
                representation['barcode'] = instance.asset.barcode
        
        # Convert FK IDs to UIDs/GUIDs
        if instance.asset.asset_type:
            representation['asset_type'] = str(instance.asset.asset_type.uid)
        if instance.asset.manufacturer:
            representation['manufacturer'] = str(instance.asset.manufacturer.uid)
        if instance.asset.supplier:
            representation['supplier'] = str(instance.asset.supplier.uid)
        if instance.asset.location:
            representation['location'] = str(instance.asset.location.uid)
        if instance.asset.custodian:
            representation['custodian'] = str(instance.asset.custodian.guid)
        
        return representation
    
    @transaction.atomic
    def create(self, validated_data):
        # Extract asset data (already processed via source mapping)
        asset_data = validated_data.pop('asset', {})
        
        # Resolve FK UIDs/GUIDs to database IDs
        self._resolve_asset_fk_ids(asset_data)
        
        # Set user from request for the Asset
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        if user and user.is_authenticated:
            asset_data['created_by'] = user
            asset_data['updated_by'] = user
        
        # Create asset first
        asset = Asset.objects.create(**asset_data)
        
        # Create peripheral with the asset
        validated_data['asset'] = asset
        return super().create(validated_data)
    
    @transaction.atomic
    def update(self, instance, validated_data):
        # Extract asset data (already processed via source mapping)
        asset_data = validated_data.pop('asset', {})
        
        # Update asset fields if present
        if asset_data:
            # Resolve FK UIDs/GUIDs to database IDs
            self._resolve_asset_fk_ids(asset_data)
            
            # Set user from request
            request = self.context.get('request')
            user = getattr(request, 'user', None) if request else None
            if user and user.is_authenticated:
                asset_data['updated_by'] = user
            
            # Update the asset
            for attr, value in asset_data.items():
                setattr(instance.asset, attr, value)
            instance.asset.save()
        
        # Update peripheral-specific fields
        return super().update(instance, validated_data)

        
# Software Serializers
class SoftwareCategorySerializer(SaveWithRequestUserMixin, NameDescriptionSerializer):
    class Meta:
        model = SoftwareCategory
        fields = NameDescriptionSerializer.Meta.fields

class SoftwareSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    # Use UUIDs for foreign keys instead of integer IDs
    category = serializers.UUIDField(required=False, allow_null=True)
    asset_type = serializers.UUIDField(required=False, allow_null=True)
    supplier = serializers.UUIDField(required=False, allow_null=True)
    custodian = serializers.UUIDField(required=False, allow_null=True)
    location = serializers.UUIDField(required=False, allow_null=True)
    
    # Related field names (read-only)
    category_name = RelatedFieldMixin.get_related_name('category')
    asset_type_name = RelatedFieldMixin.get_related_name('asset_type')
    supplier_name = RelatedFieldMixin.get_related_name('supplier')
    location_name = RelatedFieldMixin.get_related_name('location')
    custodian_name = RelatedFieldMixin.get_user_full_name('custodian')
    
    def get_custodian_name(self, obj):
        if obj.custodian:
            return f"{obj.custodian.first_name} {obj.custodian.last_name}"
        return None
    
    class Meta:
        model = Software
        fields = BaseModelSerializer.Meta.fields + [
            # Basic Information
            'asset_tag', 'software_name', 'version', 'publisher', 'software_type', 'platform',
            'category', 'category_name',
            # Asset Management
            'asset_type', 'asset_type_name', 'status', 'condition', 'photo',
            # License Information
            'license_type', 'license_key', 'total_licenses', 'used_licenses', 'license_expiry',
            # Financial Information
            'purchase_cost', 'purchase_date', 'supplier', 'supplier_name', 'warranty_expiry',
            # Assignment & Location
            'custodian', 'custodian_name', 'location', 'location_name',
            # Technical Details
            'system_requirements', 'installation_path',
            # Support & Documentation
            'support_url', 'documentation_url',
            # Additional Information
            'notes', 'last_audit_date'
        ]
    
    def to_internal_value(self, data):
        # Make a copy to avoid modifying the original
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Convert empty strings to None for date fields
        date_fields = ['purchase_date', 'license_expiry', 'warranty_expiry', 'last_audit_date']
        for field_name in date_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        # Convert empty strings to None for optional FK fields
        fk_fields = ['category', 'asset_type', 'supplier', 'custodian', 'location']
        for field_name in fk_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        return super().to_internal_value(data)
    
    def to_representation(self, instance):
        """Convert model instances to UIDs/GUIDs for output"""
        representation = super().to_representation(instance)
        
        # Convert FK instances to UIDs
        if instance.category:
            representation['category'] = str(instance.category.uid)
        if instance.asset_type:
            representation['asset_type'] = str(instance.asset_type.uid)
        if instance.supplier:
            representation['supplier'] = str(instance.supplier.uid)
        if instance.custodian:
            representation['custodian'] = str(instance.custodian.guid)
        if instance.location:
            representation['location'] = str(instance.location.uid)
        
        return representation
    
    def validate(self, data):
        """Resolve UIDs/GUIDs to model instances"""
        # Resolve category
        if 'category' in data and data['category']:
            try:
                data['category'] = SoftwareCategory.objects.get(uid=data['category'], is_deleted=False)
            except SoftwareCategory.DoesNotExist:
                raise serializers.ValidationError({'category': 'Invalid category UID'})
        
        # Resolve asset_type
        if 'asset_type' in data and data['asset_type']:
            try:
                data['asset_type'] = AssetType.objects.get(uid=data['asset_type'], is_deleted=False)
            except AssetType.DoesNotExist:
                raise serializers.ValidationError({'asset_type': 'Invalid asset type UID'})
        
        # Resolve supplier
        if 'supplier' in data and data['supplier']:
            try:
                data['supplier'] = Supplier.objects.get(uid=data['supplier'], is_deleted=False)
            except Supplier.DoesNotExist:
                raise serializers.ValidationError({'supplier': 'Invalid supplier UID'})
        
        # Resolve custodian (User uses guid, not uid)
        if 'custodian' in data and data['custodian']:
            try:
                data['custodian'] = User.objects.get(guid=data['custodian'], is_active=True)
            except User.DoesNotExist:
                raise serializers.ValidationError({'custodian': 'Invalid custodian GUID'})
        
        # Resolve location
        if 'location' in data and data['location']:
            try:
                data['location'] = Location.objects.get(uid=data['location'], is_deleted=False)
            except Location.DoesNotExist:
                raise serializers.ValidationError({'location': 'Invalid location UID'})
        
        return data

class SoftwareInstallationSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    # Use UUIDs for foreign keys
    software = serializers.UUIDField()
    asset = serializers.UUIDField()
    installed_by = serializers.UUIDField(required=False, allow_null=True)
    verified_by = serializers.UUIDField(required=False, allow_null=True)
    uninstalled_by = serializers.UUIDField(required=False, allow_null=True)
    assigned_to = serializers.UUIDField(required=False, allow_null=True)
    license_assigned = serializers.UUIDField(required=False, allow_null=True)
    
    # Nested data (read-only)
    asset_details = serializers.SerializerMethodField()
    
    # Related field names (read-only)
    software_name = RelatedFieldMixin.get_related_name('software', 'software_name')
    asset_tag = RelatedFieldMixin.get_related_name('asset', 'asset_tag')
    installed_by_name = RelatedFieldMixin.get_user_full_name('installed_by')
    assigned_to_name = RelatedFieldMixin.get_user_full_name('assigned_to')
    verified_by_name = RelatedFieldMixin.get_user_full_name('verified_by')
    uninstalled_by_name = RelatedFieldMixin.get_user_full_name('uninstalled_by')
    
    def get_asset_details(self, obj):
        if obj.asset:
            from microservices.ict_assets.serializers import AssetSerializer
            return AssetSerializer(obj.asset).data
        return None
    
    def get_installed_by_name(self, obj):
        if obj.installed_by:
            return f"{obj.installed_by.first_name} {obj.installed_by.last_name}"
        return None
    
    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}"
        return None
    
    def get_verified_by_name(self, obj):
        if obj.verified_by:
            return f"{obj.verified_by.first_name} {obj.verified_by.last_name}"
        return None
    
    def get_uninstalled_by_name(self, obj):
        if obj.uninstalled_by:
            return f"{obj.uninstalled_by.first_name} {obj.uninstalled_by.last_name}"
        return None
    
    class Meta:
        model = SoftwareInstallation
        fields = BaseModelSerializer.Meta.fields + [
            # Core Relationships
            'software', 'software_name', 'asset', 'asset_tag', 'asset_details',
            # Installation Details
            'installation_date', 'installed_by', 'installed_by_name', 'installation_path', 'version_installed',
            # License Information
            'license_key_used', 'license_assigned',
            # Status & Verification
            'status', 'last_verified_date', 'verified_by', 'verified_by_name',
            # Uninstallation Details
            'uninstall_date', 'uninstalled_by', 'uninstalled_by_name', 'uninstall_reason',
            # Assignment
            'assigned_to', 'assigned_to_name',
            # Additional Information
            'installation_notes', 'configuration_notes',
            # Compliance & Audit
            'is_compliant', 'compliance_notes'
        ]
    
    def to_internal_value(self, data):
        # Make a copy to avoid modifying the original
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Convert empty strings to None for date fields
        date_fields = ['installation_date', 'last_verified_date', 'uninstall_date']
        for field_name in date_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        # Convert empty strings to None for optional FK fields
        fk_fields = ['installed_by', 'verified_by', 'uninstalled_by', 'assigned_to', 'license_assigned']
        for field_name in fk_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        return super().to_internal_value(data)
    
    def to_representation(self, instance):
        """Convert model instances to UIDs/GUIDs for output"""
        representation = super().to_representation(instance)
        
        # Convert FK instances to UIDs
        if instance.software:
            representation['software'] = str(instance.software.uid)
        if instance.asset:
            representation['asset'] = str(instance.asset.uid)
        if instance.installed_by:
            representation['installed_by'] = str(instance.installed_by.guid)
        if instance.verified_by:
            representation['verified_by'] = str(instance.verified_by.guid)
        if instance.uninstalled_by:
            representation['uninstalled_by'] = str(instance.uninstalled_by.guid)
        if instance.assigned_to:
            representation['assigned_to'] = str(instance.assigned_to.guid)
        if instance.license_assigned:
            representation['license_assigned'] = str(instance.license_assigned.uid)
        
        return representation
    
    def validate(self, data):
        """Resolve UIDs/GUIDs to model instances"""
        # Resolve software
        if 'software' in data and data['software']:
            try:
                data['software'] = Software.objects.get(uid=data['software'])
            except Software.DoesNotExist:
                raise serializers.ValidationError({'software': 'Invalid software UID'})
        
        # Resolve asset
        if 'asset' in data and data['asset']:
            try:
                data['asset'] = Asset.objects.get(uid=data['asset'])
            except Asset.DoesNotExist:
                raise serializers.ValidationError({'asset': 'Invalid asset UID'})
        
        # Resolve User foreign keys (use guid)
        user_fields = ['installed_by', 'verified_by', 'uninstalled_by', 'assigned_to']
        for field in user_fields:
            if field in data and data[field]:
                try:
                    data[field] = User.objects.get(guid=data[field], is_active=True)
                except User.DoesNotExist:
                    raise serializers.ValidationError({field: f'Invalid {field} GUID'})
        
        # Resolve license_assigned
        if 'license_assigned' in data and data['license_assigned']:
            try:
                data['license_assigned'] = SoftwareLicense.objects.get(uid=data['license_assigned'], is_deleted=False)
            except SoftwareLicense.DoesNotExist:
                raise serializers.ValidationError({'license_assigned': 'Invalid license UID'})
        
        return data

class SoftwareLicenseSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    # Use UUIDs for foreign keys
    software = serializers.UUIDField()
    assigned_to = serializers.UUIDField(required=False, allow_null=True)
    
    # Related field names (read-only)
    software_name = RelatedFieldMixin.get_related_name('software', 'software_name')
    assigned_to_name = RelatedFieldMixin.get_user_full_name('assigned_to')
    
    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}"
        return None
    
    class Meta:
        model = SoftwareLicense
        fields = BaseModelSerializer.Meta.fields + [
            'software', 'software_name', 'license_key', 'status',
            'assigned_to', 'assigned_to_name', 'assigned_date',
            'activation_date', 'expiry_date', 'notes'
        ]
    
    def to_internal_value(self, data):
        # Make a copy to avoid modifying the original
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Convert empty strings to None for date fields
        date_fields = ['assigned_date', 'activation_date', 'expiry_date']
        for field_name in date_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        # Convert empty strings to None for optional FK fields
        fk_fields = ['assigned_to']
        for field_name in fk_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        return super().to_internal_value(data)
    
    def to_representation(self, instance):
        """Convert model instances to UIDs/GUIDs for output"""
        representation = super().to_representation(instance)
        
        # Convert FK instances to UIDs
        if instance.software:
            representation['software'] = str(instance.software.uid)
        if instance.assigned_to:
            representation['assigned_to'] = str(instance.assigned_to.guid)
        
        return representation
    
    def validate(self, data):
        """Resolve UIDs/GUIDs to model instances"""
        # Resolve software
        if 'software' in data and data['software']:
            try:
                data['software'] = Software.objects.get(uid=data['software'], is_deleted=False)
            except Software.DoesNotExist:
                raise serializers.ValidationError({'software': 'Invalid software UID'})
        
        # Resolve assigned_to (User uses guid)
        if 'assigned_to' in data and data['assigned_to']:
            try:
                data['assigned_to'] = User.objects.get(guid=data['assigned_to'], is_active=True)
            except User.DoesNotExist:
                raise serializers.ValidationError({'assigned_to': 'Invalid assigned_to GUID'})
        
        return data

# Assignment and Maintenance Serializers
class AssignmentBaseSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    """Base serializer for assignment-like models"""
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    
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

# class MaintenanceRecordSerializer(AssignmentBaseSerializer):
#     asset_type_name = RelatedFieldMixin.get_related_name('asset.asset_type')
#     technician_name = RelatedFieldMixin.get_user_full_name('technician')

#     # Computer UID field for updates
#     uid = serializers.UUIDField(required=False, read_only=True)
#     asset_uid = serializers.UUIDField(source='asset.uid', required=False, read_only=True)
    
#     def get_technician_name(self, obj):
#         if obj.technician:
#             return f"{obj.technician.first_name} {obj.technician.last_name}"
#         return None
    
#     def validate(self, data):
#         return self.validate_dates('scheduled_date', 'completed_date', data)
    
#     def to_internal_value(self, data):
#         # Make a copy to avoid modifying QueryDict
#         data = data.copy() if hasattr(data, 'copy') else dict(data)
        
#         # Convert empty strings to None for date fields
#         date_fields = ['scheduled_date', 'completed_date']
#         for field_name in date_fields:
#             if field_name in data and data[field_name] == '':
#                 data[field_name] = None
        
#         # Resolve asset - accept UID, numeric ID, or asset_tag
#         if 'asset' in data:
#             asset_value = data['asset']

#             if isinstance(asset_value, dict) and 'uid' in asset_value:
#                 asset_value = asset_value['uid']

#             if isinstance(asset_value, str):
#                 asset_value = asset_value.strip()

#             if not asset_value:
#                 data['asset'] = None
#             else:
#                 try:
#                     # numeric ID
#                     if isinstance(asset_value, int) or (isinstance(asset_value, str) and asset_value.isdigit()):
#                         asset = Asset.objects.get(id=int(asset_value), is_deleted=False)
#                         data['asset'] = asset.id
#                     else:
#                         # UID
#                         try:
#                             asset = Asset.objects.get(uid=asset_value, is_deleted=False)
#                             data['asset'] = asset.id
#                         except (ValueError, Asset.DoesNotExist):
#                             # asset_tag
#                             asset = Asset.objects.get(asset_tag__iexact=asset_value, is_deleted=False)
#                             data['asset'] = asset.id

#                 except Asset.DoesNotExist:
#                     raise serializers.ValidationError({
#                         'asset': 'Invalid asset reference. Provide a valid asset UID, numeric ID, or asset_tag.'
#                     })
#                 except Exception as e:
#                     raise serializers.ValidationError({
#                         'asset': f'Error processing asset: {str(e)}'
#                     })

#         # Resolve technician GUID
#         if 'technician' in data:
#             technician_value = data['technician']
            
#             # Strip whitespace
#             if isinstance(technician_value, str):
#                 technician_value = technician_value.strip()
            
#             # Handle empty or None
#             if not technician_value:
#                 data['technician'] = None
#             else:
#                 try:
#                     technician = User.objects.only('id').get(guid=technician_value)
#                     data['technician'] = technician.id
#                 except User.DoesNotExist:
#                     raise serializers.ValidationError({
#                         'technician': 'Invalid GUID - Technician not found'
#                     })
#                 except Exception as e:
#                     raise serializers.ValidationError({
#                         'technician': f'Error processing technician: {str(e)}'
#                     })

#         return super().to_internal_value(data)
    
#     def to_representation(self, instance):
#         """Convert IDs back to UIDs/GUIDs for response"""
#         representation = super().to_representation(instance)
        
#         if instance.asset:
#             representation['asset'] = str(instance.asset.uid)
#         if instance.technician:
#             representation['technician'] = str(instance.technician.guid)
        
#         return representation
    
#     class Meta:
#         model = MaintenanceRecord
#         fields = BaseModelSerializer.Meta.fields + [
#             'asset', 'asset_uid', 'asset_tag', 'asset_type_name', 'maintenance_type',
#             'scheduled_date', 'completed_date', 'status', 'cost', 'description',
#             'technician', 'technician_name', 'notes'
#         ]
# class MaintenanceRecordSerializer(AssignmentBaseSerializer):
#     asset_type_name = RelatedFieldMixin.get_related_name('asset.asset_type')
#     technician_name = RelatedFieldMixin.get_user_full_name('technician')

#     # Computer UID field for updates
#     uid = serializers.UUIDField(required=False, read_only=True)
#     asset_uid = serializers.UUIDField(source='asset.uid', required=False, read_only=True)
    
#     def get_technician_name(self, obj):
#         if obj.technician:
#             return f"{obj.technician.first_name} {obj.technician.last_name}"
#         return None
    
#     def validate(self, data):
#         return self.validate_dates('scheduled_date', 'completed_date', data)
    
#     def to_internal_value(self, data):
#         # Make a copy to avoid modifying QueryDict
#         data = data.copy() if hasattr(data, 'copy') else dict(data)
        
#         # Convert empty strings to None for date fields
#         date_fields = ['scheduled_date', 'completed_date']
#         for field_name in date_fields:
#             if field_name in data and data[field_name] == '':
#                 data[field_name] = None
        
#         # Handle asset field - check for empty values first
#         if 'asset' in data:
#             asset_value = data['asset']
            
#             # Handle None, empty string, or empty dict
#             if asset_value is None or asset_value == '' or (isinstance(asset_value, dict) and not asset_value):
#                 data['asset'] = None
#             else:
#                 # If it's a dict with uid, extract the uid
#                 if isinstance(asset_value, dict) and 'uid' in asset_value:
#                     asset_value = asset_value['uid']
                
#                 # Convert to string and strip whitespace
#                 if isinstance(asset_value, str):
#                     asset_value = asset_value.strip()
                
#                 if not asset_value:
#                     data['asset'] = None
#                 else:
#                     try:
#                         # Try numeric ID first
#                         if isinstance(asset_value, int) or (isinstance(asset_value, str) and asset_value.isdigit()):
#                             asset = Asset.objects.get(id=int(asset_value), is_deleted=False)
#                             data['asset'] = asset.id
#                         else:
#                             # Try UID
#                             try:
#                                 asset = Asset.objects.get(uid=asset_value, is_deleted=False)
#                                 data['asset'] = asset.id
#                             except (ValueError, Asset.DoesNotExist):
#                                 # Try asset_tag as fallback
#                                 asset = Asset.objects.get(asset_tag__iexact=asset_value, is_deleted=False)
#                                 data['asset'] = asset.id
                                
#                     except Asset.DoesNotExist:
#                         raise serializers.ValidationError({
#                             'asset': 'Invalid asset reference. Provide a valid asset UID, numeric ID, or asset_tag.'
#                         })
#                     except Exception as e:
#                         raise serializers.ValidationError({
#                             'asset': f'Error processing asset: {str(e)}'
#                         })

#         # Handle technician field
#         if 'technician' in data:
#             technician_value = data['technician']
            
#             # Handle empty values
#             if technician_value is None or technician_value == '':
#                 data['technician'] = None
#             else:
#                 # Strip whitespace if it's a string
#                 if isinstance(technician_value, str):
#                     technician_value = technician_value.strip()
                
#                 if not technician_value:
#                     data['technician'] = None
#                 else:
#                     try:
#                         technician = User.objects.only('id').get(guid=technician_value)
#                         data['technician'] = technician.id
#                     except User.DoesNotExist:
#                         raise serializers.ValidationError({
#                             'technician': 'Invalid GUID - Technician not found'
#                         })
#                     except Exception as e:
#                         raise serializers.ValidationError({
#                             'technician': f'Error processing technician: {str(e)}'
#                         })

#         # Handle cost field - convert empty string to None
#         if 'cost' in data and data['cost'] == '':
#             data['cost'] = None

#         return super().to_internal_value(data)
    
#     def to_representation(self, instance):
#         """Convert IDs back to UIDs/GUIDs for response"""
#         representation = super().to_representation(instance)
        
#         # Convert asset ID to UID
#         if instance.asset:
#             representation['asset'] = str(instance.asset.uid)
#         else:
#             representation['asset'] = None
            
#         # Convert technician ID to GUID
#         if instance.technician:
#             representation['technician'] = str(instance.technician.guid)
#         else:
#             representation['technician'] = None
        
#         # Ensure cost is properly represented
#         if representation.get('cost') is None:
#             representation['cost'] = ''
            
#         return representation
    
#     def validate_asset(self, value):
#         """Additional validation for asset field"""
#         if value is None:
#             raise serializers.ValidationError("Asset is required.")
#         return value
    
#     def validate_maintenance_type(self, value):
#         """Validate maintenance_type choices"""
#         valid_types = dict(MaintenanceRecord.MAINTENANCE_TYPE_CHOICES)
#         if value not in valid_types:
#             raise serializers.ValidationError(f"Invalid maintenance type. Choose from: {', '.join(valid_types.keys())}")
#         return value
    
#     def validate_status(self, value):
#         """Validate status choices"""
#         valid_statuses = dict(MaintenanceRecord.STATUS_CHOICES)
#         if value not in valid_statuses:
#             raise serializers.ValidationError(f"Invalid status. Choose from: {', '.join(valid_statuses.keys())}")
#         return value
    
#     class Meta:
#         model = MaintenanceRecord
#         fields = BaseModelSerializer.Meta.fields + [
#             'asset', 'asset_uid', 'asset_tag', 'asset_type_name', 'maintenance_type',
#             'scheduled_date', 'completed_date', 'status', 'cost', 'description',
#             'technician', 'technician_name', 'notes'
#         ]

class MaintenanceRecordSerializer(AssignmentBaseSerializer):
    asset_type_name = RelatedFieldMixin.get_related_name('asset.asset_type')
    technician_name = RelatedFieldMixin.get_user_full_name('technician')

    # UID fields for read operations
    uid = serializers.UUIDField(required=False, read_only=True)
    asset_uid = serializers.UUIDField(source='asset.uid', required=False, read_only=True)
    
    def get_technician_name(self, obj):
        if obj.technician:
            return f"{obj.technician.first_name} {obj.technician.last_name}"
        return None
    
    def validate(self, data):
        return self.validate_dates('scheduled_date', 'completed_date', data)
    
    def to_internal_value(self, data):
        # Make a copy to avoid modifying QueryDict
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Convert empty strings to None for date fields
        date_fields = ['scheduled_date', 'completed_date']
        for field_name in date_fields:
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        
        # Handle asset field - flexible resolution (UID, numeric ID, asset_tag)
        if 'asset' in data:
            asset_value = data['asset']
            
            # Handle all cases of empty/None values
            if asset_value is None or asset_value == '' or asset_value == 'None':
                data['asset'] = None
            else:
                # If it's a dict with uid, extract the uid
                if isinstance(asset_value, dict):
                    if 'uid' in asset_value:
                        asset_value = asset_value['uid']
                    else:
                        # If it's an empty dict or doesn't have uid, treat as None
                        data['asset'] = None
                        return super().to_internal_value(data)
                
                # Convert to string and strip whitespace
                if isinstance(asset_value, str):
                    asset_value = asset_value.strip()
                
                # Final check for empty after processing
                if not asset_value or asset_value == 'None':
                    data['asset'] = None
                else:
                    try:
                        # Try numeric ID first
                        if isinstance(asset_value, int) or (isinstance(asset_value, str) and asset_value.isdigit()):
                            asset = Asset.objects.get(id=int(asset_value), is_deleted=False)
                            data['asset'] = asset.id
                        else:
                            # Try UID
                            try:
                                asset = Asset.objects.get(uid=asset_value, is_deleted=False)
                                data['asset'] = asset.id
                            except (ValueError, Asset.DoesNotExist):
                                # Try asset_tag as fallback
                                asset = Asset.objects.get(asset_tag__iexact=asset_value, is_deleted=False)
                                data['asset'] = asset.id
                                
                    except Asset.DoesNotExist:
                        raise serializers.ValidationError({
                            'asset': 'Invalid asset reference. Provide a valid asset UID, numeric ID, or asset_tag.'
                        })
                    except Exception as e:
                        raise serializers.ValidationError({
                            'asset': f'Error processing asset: {str(e)}'
                        })

        # Handle technician field - flexible GUID resolution
        if 'technician' in data:
            technician_value = data['technician']
            
            # Handle empty values
            if technician_value is None or technician_value == '' or technician_value == 'None':
                data['technician'] = None
            else:
                # Strip whitespace if it's a string
                if isinstance(technician_value, str):
                    technician_value = technician_value.strip()
                
                if not technician_value or technician_value == 'None':
                    data['technician'] = None
                else:
                    try:
                        technician = User.objects.only('id').get(guid=technician_value)
                        data['technician'] = technician.id
                    except User.DoesNotExist:
                        raise serializers.ValidationError({
                            'technician': 'Invalid GUID - Technician not found'
                        })
                    except Exception as e:
                        raise serializers.ValidationError({
                            'technician': f'Error processing technician: {str(e)}'
                        })

        # Handle cost field - convert empty string to None
        if 'cost' in data and (data['cost'] == '' or data['cost'] == 'None'):
            data['cost'] = None

        return super().to_internal_value(data)
    
    def to_representation(self, instance):
        """Convert IDs back to UIDs/GUIDs for response"""
        representation = super().to_representation(instance)
        
        # Convert asset ID to UID
        if instance.asset:
            representation['asset'] = str(instance.asset.uid)
        else:
            representation['asset'] = None
            
        # Convert technician ID to GUID
        if instance.technician:
            representation['technician'] = str(instance.technician.guid)
        else:
            representation['technician'] = None
        
        # Ensure cost is properly represented
        if representation.get('cost') is None:
            representation['cost'] = ''
            
        return representation
    
    def validate_maintenance_type(self, value):
        """Validate maintenance_type choices"""
        valid_types = dict(MaintenanceRecord.MAINTENANCE_TYPE_CHOICES)
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid maintenance type. Choose from: {', '.join(valid_types.keys())}")
        return value
    
    def validate_status(self, value):
        """Validate status choices"""
        valid_statuses = dict(MaintenanceRecord.MAINTENANCE_STATUS)
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Choose from: {', '.join(valid_statuses.keys())}")
        return value
    
    class Meta:
        model = MaintenanceRecord
        fields = BaseModelSerializer.Meta.fields + [
            'asset', 'asset_uid', 'asset_tag', 'asset_type_name', 'maintenance_type',
            'scheduled_date', 'completed_date', 'status', 'cost', 'description',
            'technician', 'technician_name', 'notes'
        ]
        
class SupportTicketSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    assigned_technician_name = RelatedFieldMixin.get_user_full_name('assigned_technician')
    ticket_id = serializers.CharField(read_only=True)
    
    # Read-only UID fields
    uid = serializers.UUIDField(required=False, read_only=True)
    asset_uid = serializers.UUIDField(source='asset.uid', required=False, read_only=True)
    
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
        # Make a copy to avoid modifying QueryDict
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Convert empty strings to None for datetime fields
        if 'resolved_date' in data and data['resolved_date'] == '':
            data['resolved_date'] = None
        
        # Resolve asset - accept UID, numeric ID, or asset_tag
        if 'asset' in data:
            asset_value = data['asset']
            
            # Handle empty/None values
            if asset_value is None or asset_value == '' or asset_value == 'None':
                data['asset'] = None
            else:
                # Handle dict with uid key
                if isinstance(asset_value, dict):
                    if 'uid' in asset_value:
                        asset_value = asset_value['uid']
                    else:
                        data['asset'] = None
                        return super().to_internal_value(data)
                
                # Strip whitespace
                if isinstance(asset_value, str):
                    asset_value = asset_value.strip()
                
                # Final check for empty
                if not asset_value or asset_value == 'None':
                    data['asset'] = None
                else:
                    try:
                        # Try numeric ID first
                        if isinstance(asset_value, int) or (isinstance(asset_value, str) and asset_value.isdigit()):
                            asset = Asset.objects.get(id=int(asset_value), is_deleted=False)
                            data['asset'] = asset.id
                        else:
                            # Try UUID uid
                            try:
                                asset = Asset.objects.get(uid=asset_value, is_deleted=False)
                                data['asset'] = asset.id
                            except (ValueError, Asset.DoesNotExist):
                                # Fallback to asset_tag (case-insensitive)
                                asset = Asset.objects.get(asset_tag__iexact=asset_value, is_deleted=False)
                                data['asset'] = asset.id
                    except Asset.DoesNotExist:
                        raise serializers.ValidationError({
                            'asset': 'Invalid asset reference. Provide a valid asset UID, numeric ID, or asset_tag.'
                        })
                    except Exception as e:
                        raise serializers.ValidationError({
                            'asset': f'Error processing asset: {str(e)}'
                        })
        
        # Resolve assigned_technician GUID
        if 'assigned_technician' in data:
            technician_value = data['assigned_technician']
            
            # Handle empty/None values
            if technician_value is None or technician_value == '' or technician_value == 'None':
                data['assigned_technician'] = None
            else:
                # Strip whitespace
                if isinstance(technician_value, str):
                    technician_value = technician_value.strip()
                
                if not technician_value or technician_value == 'None':
                    data['assigned_technician'] = None
                else:
                    try:
                        technician = User.objects.only('id').get(guid=technician_value)
                        data['assigned_technician'] = technician.id
                    except User.DoesNotExist:
                        raise serializers.ValidationError({
                            'assigned_technician': 'Invalid GUID - Technician not found'
                        })
                    except Exception as e:
                        raise serializers.ValidationError({
                            'assigned_technician': f'Error processing technician: {str(e)}'
                        })
        
        return super().to_internal_value(data)
    
    def to_representation(self, instance):
        """Convert IDs back to UIDs/GUIDs for response"""
        representation = super().to_representation(instance)
        
        # Convert asset ID to UID
        if instance.asset:
            representation['asset'] = str(instance.asset.uid)
        else:
            representation['asset'] = None
            
        # Convert technician ID to GUID
        if instance.assigned_technician:
            representation['assigned_technician'] = str(instance.assigned_technician.guid)
        else:
            representation['assigned_technician'] = None
        
        return representation
    
    def validate_priority(self, value):
        """Validate priority choices"""
        valid_priorities = dict(SupportTicket.PRIORITY_LEVELS)
        if value not in valid_priorities:
            raise serializers.ValidationError(f"Invalid priority. Choose from: {', '.join(valid_priorities.keys())}")
        return value
    
    def validate_status(self, value):
        """Validate status choices"""
        valid_statuses = dict(SupportTicket.TICKET_STATUS)
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Choose from: {', '.join(valid_statuses.keys())}")
        return value
    
    def create(self, validated_data):
        """Auto-generate ticket_id on creation"""
        validated_data['ticket_id'] = self.generate_ticket_id()
        return super().create(validated_data)
    
    class Meta:
        model = SupportTicket
        fields = BaseModelSerializer.Meta.fields + [
            'ticket_id', 'asset', 'asset_uid', 'asset_tag', 'issue_description', 'priority',
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



