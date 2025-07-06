# your_app/management/commands/sync_jeeva.py

from django.core.management.base import BaseCommand

from api.Services.jeeva_module import update_roles_and_permissions


class Command(BaseCommand):
    help = 'Sync Jeeva roles and permissions from remote API'

    def handle(self, *args, **kwargs):
        try:
            update_roles_and_permissions()
            self.stdout.write("🔄 Syncing Jeeva roles and permissions...")
            update_roles_and_permissions()
            self.stdout.write(self.style.SUCCESS('Successfully synced Jeeva roles and permissions.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))


