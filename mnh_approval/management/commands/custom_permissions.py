from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, ContentType
from django.contrib.auth.models import Group
from django.apps import apps

class Command(BaseCommand):
    help = "Create custom permissions and assign them to groups"

    def handle(self, *args, **options):
        self.stdout.write("Processing custom permissions...")

        # Define your permissions as (codename, name)
        permissions_to_create = [
            ("can_view_system_permission", "Can View System Permission"),
            ("can_assign_delegate", "Can Assign Delegate User"),
            ("can_view_sensitive_data", "Can View Sensitive Data"),
            ("can_view_directory", "Can View Directory"),
            ("can_import_directory", "Import Directory From Excel File"),
            ("can_add_group", "Can Add Group"),
            ("can_delete_group", "Can Delete Group"),
            ("can_view_group", "Can View Group"),
            ("can_assign_user_to_group", "Can Assign User To Group"),
            ("can_remove_user_to_group", "Can Remove User From Group"),
            ("import_users", "Can Import Users"),

        ]

        # Define groups and the permissions to assign
        groups_to_permissions = {
            "Approvers": ["can_assign_delegate", "can_view_directory"],
            "Delegators": ["can_assign_delegate","can_import_directory", "can_view_sensitive_data"],
            "Admins": ["can_add_group", "can_delete_group", "can_view_group", "can_assign_user_to_group", "can_remove_user_to_group"],
        }

        # Use a default ContentType (you can pick any model)
        # Here, we'll fall back to auth.Permission itself (safe, always exists)
        try:
            default_ct = ContentType.objects.get(app_label="auth", model="permission")
        except ContentType.DoesNotExist:
            self.stdout.write(self.style.ERROR("Default ContentType does not exist. Aborting."))
            return

        for codename, name in permissions_to_create:
            perm, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=default_ct,
                defaults={"name": name}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created permission '{codename}'"))
            else:
                self.stdout.write(f"Permission '{codename}' already exists")

        self.stdout.write("Processing groups...")

        for group_name, perm_codes in groups_to_permissions.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created group '{group_name}'"))
            else:
                self.stdout.write(f"Group exists: {group_name}")

            # Remove all permissions before re-assigning
            group.permissions.clear()

            for code in perm_codes:
                try:
                    permission = Permission.objects.get(codename=code)
                    group.permissions.add(permission)
                    self.stdout.write(self.style.SUCCESS(
                        f"Assigned permission '{code}' to group '{group_name}'"
                    ))
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"Permission '{code}' does not exist. Skipped."
                    ))

        self.stdout.write(self.style.SUCCESS("Custom permissions and groups synchronized."))
