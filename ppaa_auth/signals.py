from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from ppaa_auth.models import GroupProfile


@receiver(post_save, sender=Group)
def create_or_update_group_profile(sender, instance, created, **kwargs):
    profile, was_created = GroupProfile.objects.get_or_create(group=instance)
    if not was_created:
        profile.update_count = (profile.update_count or 0) + 1
    profile.save()
