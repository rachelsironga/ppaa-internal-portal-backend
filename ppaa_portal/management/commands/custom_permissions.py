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
            ("can_approve_request" ,"Can Approve Request"),
            # Internal Portal Permissions
            ("can_view_document_category", "Can View Document Category"),
            ("can_add_document_category", "Can Add Document Category"),
            ("can_edit_document_category", "Can Edit Document Category"),
            ("can_delete_document_category", "Can Delete Document Category"),
            ("can_view_document", "Can View Document"),
            ("can_add_document", "Can Add Document"),
            ("can_edit_document", "Can Edit Document"),
            ("can_delete_document", "Can Delete Document"),
            ("can_view_announcement", "Can View Announcement"),
            ("can_add_announcement", "Can Add Announcement"),
            ("can_edit_announcement", "Can Edit Announcement"),
            ("can_delete_announcement", "Can Delete Announcement"),
            ("can_view_event", "Can View Event"),
            ("can_add_event", "Can Add Event"),
            ("can_edit_event", "Can Edit Event"),
            ("can_delete_event", "Can Delete Event"),
            ("can_view_faq", "Can View FAQ"),
            ("can_add_faq", "Can Add FAQ"),
            ("can_edit_faq", "Can Edit FAQ"),
            ("can_delete_faq", "Can Delete FAQ"),
            ("can_view_notification", "Can View Notification"),
            ("can_add_notification", "Can Add Notification"),
            ("can_edit_notification", "Can Edit Notification"),
            ("can_delete_notification", "Can Delete Notification"),
            ("can_view_todo", "Can View Todo"),
            ("can_add_todo", "Can Add Todo"),
            ("can_edit_todo", "Can Edit Todo"),
            ("can_delete_todo", "Can Delete Todo"),
            ("can_view_quick_link", "Can View Quick Link"),
            ("can_add_quick_link", "Can Add Quick Link"),
            ("can_edit_quick_link", "Can Edit Quick Link"),
            ("can_delete_quick_link", "Can Delete Quick Link"),
            ("can_view_audit_log", "Can View Audit Log"),
        ]

        # Groups and permission mapping for non-admins
        groups_to_permissions = {
        
            "HR": [
                "can_view_department",
                "can_view_department_lookup",
                "can_view_document_category",
                "can_view_document",
                "can_add_document",
                "can_edit_document",
                "can_view_announcement",
                "can_add_announcement",
                "can_edit_announcement",
                "can_view_event",
                "can_add_event",
                "can_edit_event",
                "can_view_faq",
                "can_add_faq",
                "can_edit_faq",
                "can_view_quick_link",
                "can_add_quick_link",
                "can_edit_quick_link",
                "can_delete_quick_link",
                "can_view_notification",
                "can_add_notification",
                "can_view_todo",
                "can_add_todo",
                "can_edit_todo",
                "can_view_audit_log",
            ],
            "ICT": [
                "can_view_department",
                "can_view_department_lookup",
                "can_view_document_category",
                "can_add_document_category",
                "can_edit_document_category",
                "can_view_document",
                "can_add_document",
                "can_edit_document",
                "can_delete_document",
                "can_view_announcement",
                "can_add_announcement",
                "can_edit_announcement",
                "can_view_event",
                "can_add_event",
                "can_edit_event",
                "can_view_faq",
                "can_add_faq",
                "can_edit_faq",
                "can_view_notification",
                "can_add_notification",
                "can_view_todo",
                "can_add_todo",
                "can_edit_todo",
                "can_view_quick_link",
                "can_add_quick_link",
                "can_edit_quick_link",
                "can_delete_quick_link",
                "can_view_audit_log",
            ],
      
            "staff": [
                "can_view_group",
                "can_view_own_profile",
                "can_change_own_password",
                "can_update_approval_request_status",
                "can_upload_profile_photo",
                "can_view_department_lookup",
                "can_view_quick_link",
                "can_view_document",
                "can_view_announcement",
                "can_view_event",
                "can_view_faq",
                "can_view_notification",
                "can_view_todo",
                "can_add_todo",
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

        # Handle Admin group: assign all permissions
        admin_group, created = Group.objects.get_or_create(name="Admin")
        if created:
            self.stdout.write(self.style.SUCCESS("Created group 'Admin'"))
        else:
            self.stdout.write("Group exists: Admin")

        admin_group.permissions.clear()
        admin_group.permissions.add(*Permission.objects.all())
        self.stdout.write(self.style.SUCCESS("Assigned ALL available permissions to Admin group"))
        
        # Also handle lowercase 'admin' for backward compatibility
        admin_group_lower, created = Group.objects.get_or_create(name="admin")
        if created:
            self.stdout.write(self.style.SUCCESS("Created group 'admin'"))
        admin_group_lower.permissions.clear()
        admin_group_lower.permissions.add(*Permission.objects.all())
        self.stdout.write(self.style.SUCCESS("Assigned ALL available permissions to admin group"))

        self.stdout.write(self.style.SUCCESS("Custom permissions and groups synchronized."))
