# oxygen/services.py

from django.db import transaction
from django.utils import timezone
from .models import OxygenAllocation, LocationOxygenVolumes, OxygenReceiving


def verify_allocation(uid, user, verify_remarks=None):
    with (transaction.atomic()):
        oxygen_allocation = OxygenAllocation.objects.filter(uid=uid, is_deleted=False).first()
        if not oxygen_allocation:
            raise ValueError("Oxygen Allocation Not Found or Deleted")

        if oxygen_allocation.status == 'VERIFIED':
            raise ValueError("Oxygen Allocation Already Verified")

        # Update related location quantity
        location_from = oxygen_allocation.location_from
        location_to = oxygen_allocation.location_to
        if not (location_from and location_to):
            raise ValueError("Fail to read locations")

        if location_from == location_to:
            raise ValueError("You Cant Allocate to Same Location")

        if location_from.quantity < oxygen_allocation.quantity:
            raise ValueError(
                f"Low Stock: {location_from.name} has only {location_from.quantity} "
                f"Required {oxygen_allocation.quantity}"
            )


def verify_receiving(uid, user, verify_remarks=None):
    with (transaction.atomic()):
        oxygen_receiving = OxygenReceiving.objects.filter(uid=uid, is_deleted=False).first()
        if not oxygen_receiving:
            raise ValueError("Oxygen Receiving Not Found or Deleted")

        if oxygen_receiving.status == 'VERIFIED':
            raise ValueError("Oxygen Receiving Already Verified")

        # Update related location quantity
        location = oxygen_receiving.location
        if location:
            """location quantities"""
            location.quantity += oxygen_receiving.quantity
            location.save()

            # update the volumes stock for this location
            location_volume = LocationOxygenVolumes.objects.filter(
                volume=oxygen_receiving.volume,
                location=location
            ).first()

            # register volume if location doesn't have it
            if not location_volume:
                try:
                    location_volume = LocationOxygenVolumes.objects.create(
                        volume=oxygen_receiving.volume,
                        location=location,
                        quantity=0
                    )
                except Exception as e:
                    raise ValueError(f"The {location.name} is not registered to receive {oxygen_receiving.volume.name} Cylinder" )

            location_volume.quantity += oxygen_receiving.quantity
            location_volume.save()
        else :
            raise ValueError("Fail To Read Locations")

        # Update allocation fields
        oxygen_receiving.verify_remarks = verify_remarks.strip() if verify_remarks else None
        oxygen_receiving.status = 'VERIFIED'
        oxygen_receiving.verify_date = timezone.now()
        oxygen_receiving.verify_by = user.id
        # Save both serializer and allocation changes
        oxygen_receiving.save()
        return oxygen_receiving
