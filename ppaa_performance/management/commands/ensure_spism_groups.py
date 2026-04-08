"""
Create Django Groups for SPISM roles if they do not exist.
Assign these groups to users via Administration > Users & Roles (system groups).
Usage: python manage.py ensure_spism_groups
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

from ppaa_performance.constants import SPISM_ROLES


class Command(BaseCommand):
    help = "Create SPISM role groups (Django Group) for Strategic Performance Management Information System."

    def handle(self, *args, **options):
        created = 0
        for name in SPISM_ROLES:
            group, was_created = Group.objects.get_or_create(name=name)
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created group: {name}"))
            else:
                self.stdout.write(f"Group already exists: {name}")
        self.stdout.write(self.style.SUCCESS(f"Done. Created {created} new group(s). Assign roles in Administration > Users & Roles."))
