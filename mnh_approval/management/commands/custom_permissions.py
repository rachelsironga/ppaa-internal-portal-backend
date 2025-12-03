from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, ContentType, Group
from django.apps import apps

class Command(BaseCommand):
    help = "Create custom permissions and assign them to groups"

    def handle(self, *args, **options):
        self.stdout.write("Processing custom permissions...")

        # Define your custom permissions as (codename, name)
        permissions_to_create = [
            ("can_view_system_permission", "Can View System Permission"),
            ("can_assign_delegate", "Can Assign Delegate User"),
            ("can_remove_delegate", "Can Remove Delegate User"),
            ("can_view_sensitive_data", "Can View Sensitive Data"),
            ("can_add_directory", "Can add Directory"),
            ("can_update_directory", "Can update Directory"),
            ("can_view_directory", "Can View Directory"),
            ("can_view_directory_lookup", "Can View Directory Lookup"),
            ("can_import_directory", "Import Directory From Excel File"),
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
            ("can_change_user_password", "Can Change User Password"),
            ("can_view_approval_request", "Can View Approval Request"),
            ("can_create_approval_request", "Can Create Approval Request"),
            ("can_update_approval_request_status", "Can Update Approval Request Status"),
            ("can_upload_profile_photo", "Can Upload Profile Photo"),
            ("can_upload_profile_signature", "Can Upload Profile Signature"),
            ("can_view_request_handling","Can View Request Handling"),
            ("can_perform_request_handling", "Can Perform Request Handling"),
            ("change_approval_request","change Approval Request"),
            ("can_view_approval_request_step", "Can View Approval Request Step"),
            ("can_view_approval_modules","Can View Approval Module"),
            ("can_view_approval_module_lookup","Can View Approval Module Lookup"),
            ("can_add_approval_module","Can Add Approval Module"),
            ("can_edit_approval_module","Can Edit Approval Module"),
            ("can_delete_approval_module","Can Delete Approval Module"),
            ("can_view_date_range", "Can View Date Range"),
            ("can_view_date_range_lookup", "Can View Date Range Lookup"),
            ("can_edit_date_range","Can Edit Date Range"),
            ("can_delete_date_range","Can Delete Date Range"),
            ("can_approve_request" ,"Can Approve Request"),
        ]

        # Groups and permission mapping for non-admins
        groups_to_permissions = {
            "Approvers": [
                "can_assign_delegate",
                "can_view_directory_lookup",
                "can_view_department_lookup",
                "can_change_own_password",
                "can_view_approval_module_lookup",
                "can_approve_request"
            ],
            "Request_Handler" : [
                "can_view_own_profile",
                "can_change_own_password",
                "can_view_request_handling",
                "can_perform_request_handling",
                "can_view_approval_request",
            ],
            "Delegators": [
                "can_assign_delegate",
                "can_remove_delegate",
                "can_import_directory",
                "can_view_sensitive_data",
                "can_view_approval_module_lookup",
            ],
            "staff": [
                "can_view_group",
                "can_view_directory_lookup",
                "can_view_own_profile",
                "can_change_own_password",
                "can_view_approval_request",
                "can_create_approval_request",
                "can_update_approval_request_status",
                "can_upload_profile_photo",
                "can_view_department_lookup",
                'can_upload_profile_signature',
                'can_upload_profile_signature',
                'change_approval_request',
                "can_view_approval_module_lookup",
                "can_view_date_range_lookup",
                "can_view_approval_request_step",
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

        admin_group.permissions.clear()
        admin_group.permissions.add(*Permission.objects.all())
        self.stdout.write(self.style.SUCCESS("Assigned ALL available permissions to admin group"))

        self.stdout.write(self.style.SUCCESS("Custom permissions and groups synchronized."))
