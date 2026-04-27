from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, ContentType, Group
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = "Create custom permissions, assign them to groups, and give superusers all permissions"

    def handle(self, *args, **options):
        self.stdout.write("Processing custom permissions...")

        # Define your custom permissions as (codename, name)
        permissions_to_create = [
            ("can_view_system_permission", "Can View System Permission"),
            ("can_view_sensitive_data", "Can View Sensitive Data"),
            ("can_add_department", "Can Add Department"),
            ("can_view_department", "Can View Department"),
            ("can_view_department_lookup", "Can View Department Lookup"),
            ("can_delete_department", "Can Delete Department"),
            ("can_add_group", "Can Add Group"),
            ("can_delete_group", "Can Delete Group"),
            ("can_view_group", "Can View Group"),
            ("can_assign_user_to_group", "Can Assign User To Group"),
            ("can_remove_user_to_group", "Can Remove User From Group"),
            ("import_users", "Can Import Users"),
            ("import_designations", "Can Import Designations"),
            ("assign_user_permission", "Can Assign User Permission"),
            ("can_view_own_profile", "Can View Own Profile"),
            ("can_change_own_password", "Can Change Own Password"),
            ("can_upload_profile_photo", "Can Upload Profile Photo"),
            ("can_manage_user_lifecycle", "Can Manage User Lifecycle (retire, block, delete)"),
        ]

        # Groups and permission mapping for non-admins
        groups_to_permissions = {
        
            "staff": [
                "can_view_group",
                "can_view_own_profile",
                "can_change_own_password",
                "can_upload_profile_photo",
                "can_view_department_lookup",
            ]
        }

        # Use a default ContentType (fallback to auth.Permission)
        default_ct = ContentType.objects.get(app_label="auth", model="permission")

        # Create custom permissions
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

        # Assign permissions to groups
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

        # Handle admin group: assign all permissions
        admin_group, created = Group.objects.get_or_create(name="admin")
        if created:
            self.stdout.write(self.style.SUCCESS("Created group 'admin'"))
        else:
            self.stdout.write("Group exists: admin")

        all_permissions = Permission.objects.all()
        admin_group.permissions.set(all_permissions)
        self.stdout.write(self.style.SUCCESS("Assigned ALL available permissions to admin group"))

        # Assign all permissions to superusers
        User = get_user_model()
        superusers = User.objects.filter(is_superuser=True)

        for user in superusers:
            user.user_permissions.set(all_permissions)
            self.stdout.write(self.style.SUCCESS(
                f"Assigned ALL permissions to superuser '{user.username}'"
            ))

        self.stdout.write(self.style.SUCCESS("Custom permissions, groups, and superusers synchronized."))
