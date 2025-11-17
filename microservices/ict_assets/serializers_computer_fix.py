# FIXED ComputerSerializer methods to replace in serializers.py

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
