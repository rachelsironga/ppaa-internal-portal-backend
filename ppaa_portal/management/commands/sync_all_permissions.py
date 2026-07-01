"""
Run all portal permission setup commands in dependency order.

Local:
    python manage.py sync_all_permissions

Docker (from ppaa-internal-portal-backend, stack running):
    docker compose exec backend python manage.py sync_all_permissions
    # or: ./run_all_permissions.sh
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


# Order matters: portal base → module-specific → SPISM groups → SPISM role maps.
PERMISSION_COMMANDS = (
    "custom_permissions",
    "maoni_permissions",
    "rms_permission",
    "ensure_spism_groups",
    "spism_permissions",
    "ppaa_performance_permissions",
)


class Command(BaseCommand):
    help = (
        "Run all permission setup commands: internal portal, Maoni, RMS, and SPISM "
        "(custom_permissions → maoni_permissions → rms_permission → "
        "ensure_spism_groups → spism_permissions → ppaa_performance_permissions)."
    )

    def handle(self, *args, **options):
        total = len(PERMISSION_COMMANDS)
        for index, name in enumerate(PERMISSION_COMMANDS, start=1):
            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"[{index}/{total}] Running {name}..."
                )
            )
            call_command(name)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("All permission commands finished."))
