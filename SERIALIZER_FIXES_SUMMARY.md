# ICT Assets Serializers - Fixes Summary

## Issues Fixed

### 1. Computer/NetworkDevice/Peripheral Serializers - Update Method Error
**Error:** `The .update() method does not support writable dotted-source fields by default`

**Root Cause:** 
- Fields used `source='asset.*'` for reading nested data
- `to_internal_value()` was converting UIDs/GUIDs to IDs but `super().to_internal_value()` was rebuilding the data from field definitions, overwriting the conversions
- During updates, UIDs were being assigned to FK `_id` fields instead of integer IDs, causing "User matching query does not exist" errors

**Solution:**
- Simplified `to_internal_value()` to only normalize data (empty strings to None, lowercase storage_type)
- Created `_resolve_asset_fk_ids()` helper method that converts UIDs/GUIDs to database IDs
- Updated `create()` and `update()` methods to call the helper after validation
- This ensures FK resolution happens at the right time with proper control over the data

**Files Modified:**
- `ComputerSerializer` - Fixed to_internal_value(), added _resolve_asset_fk_ids(), updated create() and update()
- `NetworkDeviceSerializer` - Same pattern (needs to be applied)
- `PeripheralSerializer` - Same pattern (needs to be applied)

### 2. MaintenanceRecord/SupportTicket Serializers - Asset Lookup Error
**Error:** `Invalid UID - Asset not found`

**Root Cause:**
- Strict UUID-only lookup in `to_internal_value()`
- Frontend might send asset_tag, numeric ID, or values with whitespace
- No filtering for soft-deleted assets (`is_deleted=False`)

**Solution:**
- Made asset resolution tolerant to multiple input formats:
  - Numeric ID (integer or digit string)
  - UUID (asset.uid)
  - Asset tag (case-insensitive fallback)
- Added whitespace stripping
- Added `is_deleted=False` filter to avoid linking to deleted assets
- Handles dict input with `uid` key
- Provides clearer error messages

**Files Modified:**
- `MaintenanceRecordSerializer.to_internal_value()` - Robust asset and technician resolution
- `SupportTicketSerializer.to_internal_value()` - Same pattern applied

### 3. AssignmentBaseSerializer - Incorrect asset_tag Field
**Error:** asset_tag field was using incorrect RelatedFieldMixin helper

**Root Cause:**
- Used `RelatedFieldMixin.get_related_name('asset', 'asset_tag')` which tried to access `asset.name` instead of `asset.asset_tag`

**Solution:**
- Changed to `serializers.CharField(source='asset.asset_tag', read_only=True)`

**Files Modified:**
- `AssignmentBaseSerializer` - Fixed asset_tag field definition
- `SupportTicketSerializer` - Fixed asset_tag field definition

## Summary of Changes

### ComputerSerializer (and siblings)
```python
# Before: Complex to_internal_value with FK lookups
def to_internal_value(self, data):
    # ... lots of FK lookup code ...
    data['asset'] = asset_data  # This gets overwritten!
    return super().to_internal_value(data)

# After: Simple normalization + helper method
def to_internal_value(self, data):
    # Normalize empty strings and lowercase storage_type
    return super().to_internal_value(data)

def _resolve_asset_fk_ids(self, asset_data):
    # Convert UIDs/GUIDs to IDs
    mapping = {...}
    for field, (model, slug) in mapping.items():
        # Convert to _id fields
```

### MaintenanceRecordSerializer (and SupportTicket)
```python
# Before: Strict UUID lookup
asset = Asset.objects.get(uid=data['asset'])

# After: Flexible resolution
if isinstance(asset_value, int) or asset_value.isdigit():
    # Try numeric ID
    asset = Asset.objects.get(id=int(asset_value), is_deleted=False)
else:
    try:
        # Try UUID
        asset = Asset.objects.get(uid=asset_value, is_deleted=False)
    except:
        # Fallback to asset_tag
        asset = Asset.objects.get(asset_tag__iexact=asset_value, is_deleted=False)
```

## Testing Recommendations

### For Computer/NetworkDevice/Peripheral:
1. Create a new computer with valid data
2. Update computer with PATCH (partial update) - only hostname
3. Update computer with PUT (full update)
4. Test with empty/null values for optional FK fields (manufacturer, supplier, location, custodian)
5. Test with invalid UID/GUID

### For MaintenanceRecord/SupportTicket:
1. Create with asset UID
2. Create with asset numeric ID
3. Create with asset_tag
4. Create with asset_tag with whitespace
5. Test with mixed-case asset_tag
6. Test with soft-deleted asset (should fail)
7. Test with invalid asset reference

## Benefits

1. **Robustness**: Asset resolution accepts multiple identifier formats
2. **User-Friendly**: Better error messages guide users to provide correct data
3. **Data Integrity**: Prevents linking to soft-deleted assets
4. **Maintainability**: Cleaner separation of concerns (validation vs FK resolution)
5. **Consistency**: Same patterns applied across related serializers
