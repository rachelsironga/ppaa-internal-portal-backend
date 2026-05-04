from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

from ppaa_performance.constants import (
    SPISM_ROLE_HEAD_OF_PLANNING,
    SPISM_ROLE_HEAD_OF_UNIT,
    SPISM_ROLE_EXECUTIVE_SECRETARY,
    SPISM_ROLE_ICT_ADMINISTRATOR,
    SPISM_ROLE_INTERNAL_AUDIT,
    SPISM_ROLE_READ_ONLY,
)


class Command(BaseCommand):
    help = (
        "Rename existing SPISM Django Groups from the old role labels to the new ones.\n"
        "This keeps all existing role assignments and permissions but updates the group names.\n"
        "Safe to run multiple times; it will skip groups that are already renamed."
    )

    # Mapping of old group names in the DB -> new canonical names from constants
    OLD_TO_NEW = {
        "SPISM Head of Planning": SPISM_ROLE_HEAD_OF_PLANNING,
        "SPISM Head of Unit": SPISM_ROLE_HEAD_OF_UNIT,
        "SPISM Executive Secretary": SPISM_ROLE_EXECUTIVE_SECRETARY,
        "SPISM ICT Administrator": SPISM_ROLE_ICT_ADMINISTRATOR,
        "SPISM Internal Audit": SPISM_ROLE_INTERNAL_AUDIT,
        "SPISM Read-Only": SPISM_ROLE_READ_ONLY,
    }

    def handle(self, *args, **options):
        renamed = 0
        skipped = 0

        self.stdout.write("Checking SPISM role groups for rename...")

        for old_name, new_name in self.OLD_TO_NEW.items():
            try:
                group = Group.objects.get(name=old_name)
            except Group.DoesNotExist:
                self.stdout.write(f"Old group not found (already renamed or never created): {old_name}")
                skipped += 1
                continue

            # If a group with the new name already exists, do not overwrite it
            if Group.objects.filter(name=new_name).exclude(pk=group.pk).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"Group with new name already exists, skipping rename: {old_name} -> {new_name}"
                    )
                )
                skipped += 1
                continue

            group.name = new_name
            group.save(update_fields=["name"])
            renamed += 1
            self.stdout.write(self.style.SUCCESS(f"Renamed group '{old_name}' -> '{new_name}'"))

        self.stdout.write(self.style.SUCCESS(f"Done. Renamed {renamed} group(s), skipped {skipped}."))

