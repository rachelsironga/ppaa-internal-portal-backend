# ict_assets/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Asset, AssetCustodianHistory, AssetLocationHistory


@receiver(pre_save, sender=Asset)
def track_asset_changes(sender, instance, **kwargs):
    """Track when custodian or location changes on an asset"""
    if instance.pk:
        try:
            old_asset = Asset.objects.get(pk=instance.pk)
            
            # Check if custodian has changed
            if old_asset.custodian != instance.custodian:
                instance._custodian_changed = True
                instance._previous_custodian = old_asset.custodian
            
            # Check if location has changed
            if old_asset.location != instance.location:
                instance._location_changed = True
                instance._previous_location = old_asset.location
        except Asset.DoesNotExist:
            pass
    # For new assets, only track if custodian/location are actually set
    if not instance.pk and instance.custodian:
        instance._custodian_changed = True
    if not instance.pk and instance.location:
        instance._location_changed = True


@receiver(post_save, sender=Asset)
def create_asset_history(sender, instance, created, **kwargs):
    """Create history records after asset is saved"""
    user = getattr(instance, 'updated_by', None) or getattr(instance, 'created_by', None)
    
    # Create custodian history if changed
    if getattr(instance, '_custodian_changed', False):
        AssetCustodianHistory.objects.create(
            asset=instance,
            custodian=instance.custodian,
            created_by=user
        )
        delattr(instance, '_custodian_changed')
        if hasattr(instance, '_previous_custodian'):
            delattr(instance, '_previous_custodian')
    
    # Create location history if changed
    if getattr(instance, '_location_changed', False):
        AssetLocationHistory.objects.create(
            asset=instance,
            location=instance.location,
            created_by=user
        )
        delattr(instance, '_location_changed')
        if hasattr(instance, '_previous_location'):
            delattr(instance, '_previous_location')
