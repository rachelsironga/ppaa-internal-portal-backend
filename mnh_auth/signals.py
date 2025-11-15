from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from .models import GroupProfile

@receiver(post_save, sender=Group)
def create_or_update_group_profile(sender, instance, created, **kwargs):
    """
    Signal to create or update GroupProfile whenever Group is saved
    """
    # Create a profile if not exist
    profile, was_created = GroupProfile.objects.get_or_create(group=instance)

    # If a group already existed (updated)
    if not created:
        profile.update_count += 1
        profile.save()
