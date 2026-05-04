from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, ContentType, Group
from django.apps import apps

class Command(BaseCommand):
    help = "Create custom permissions and assign them to groups"

    def handle(self, *args, **options):
        self.stdout.write("Processing custom permissions...")

        # Define your custom permissions as (codename, name)
        permissions_to_create = [
            # Internal Portal Permissions - Document Categories
            ("can_view_department", "Can View Department"),
            ("can_view_department_lookup", "Can View Department Lookup"),
            ("can_add_department", "Can Add Department"),
            ("can_delete_department", "Can Delete Department"),
            ("can_edit_department", "Can Edit Department"),
            
            ("can_view_document_category", "Can View Document Category"),
            ("can_add_document_category", "Can Add Document Category"),
            ("can_edit_document_category", "Can Edit Document Category"),
            ("can_delete_document_category", "Can Delete Document Category"),
            # Internal Portal Permissions - Documents
            ("can_view_document", "Can View Document"),
            ("can_add_document", "Can Add Document"),
            ("can_edit_document", "Can Edit Document"),
            ("can_delete_document", "Can Delete Document"),
            ("can_download_document", "Can Download Document"),
            # Internal Portal Permissions - Announcements
            ("can_view_announcement", "Can View Announcement"),
            ("can_add_announcement", "Can Add Announcement"),
            ("can_edit_announcement", "Can Edit Announcement"),
            ("can_delete_announcement", "Can Delete Announcement"),
            ("can_pin_announcement", "Can Pin Announcement"),
            # Internal Portal Permissions - Events
            ("can_view_event", "Can View Event"),
            ("can_add_event", "Can Add Event"),
            ("can_edit_event", "Can Edit Event"),
            ("can_delete_event", "Can Delete Event"),
            ("can_manage_event_attendees", "Can Manage Event Attendees"),
            # Internal Portal Permissions - FAQs
            ("can_view_faq", "Can View FAQ"),
            ("can_add_faq", "Can Add FAQ"),
            ("can_edit_faq", "Can Edit FAQ"),
            ("can_delete_faq", "Can Delete FAQ"),
            # Internal Portal Permissions - Notifications
            ("can_view_notification", "Can View Notification"),
            ("can_add_notification", "Can Add Notification"),
            ("can_edit_notification", "Can Edit Notification"),
            ("can_delete_notification", "Can Delete Notification"),
            ("can_send_notification", "Can Send Notification"),
            # Internal Portal Permissions - Todo Lists
            ("can_view_todo", "Can View Todo"),
            ("can_add_todo", "Can Add Todo"),
            ("can_edit_todo", "Can Edit Todo"),
            ("can_delete_todo", "Can Delete Todo"),
            ("can_complete_todo", "Can Complete Todo"),
            # Internal Portal Permissions - Audit Logs
            ("can_view_audit_log", "Can View Audit Log"),
            ("can_export_audit_log", "Can Export Audit Log"),
        ]

        # Groups and permission mapping for non-admins
        groups_to_permissions = {
          
<<<<<<< HEAD
            "content_editor": [
=======
            "HR": [
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
                # Department Management
                "can_view_department",
                "can_view_department_lookup",
                "can_add_department",
                "can_delete_department",
                # Document Categories - View only
                "can_view_document_category",
                # Documents - Full access
                "can_view_document",
                "can_add_document",
                "can_edit_document",
                "can_delete_document",
                "can_download_document",
                # Announcements - Full access
                "can_view_announcement",
                "can_add_announcement",
                "can_edit_announcement",
                "can_delete_announcement",
                "can_pin_announcement",
                # Events - Full access
                "can_view_event",
                "can_add_event",
                "can_edit_event",
                "can_delete_event",
                "can_manage_event_attendees",
                # FAQs - Full access
                "can_view_faq",
                "can_add_faq",
                "can_edit_faq",
                "can_delete_faq",
                # Notifications - Full access
                "can_view_notification",
                "can_add_notification",
                "can_edit_notification",
                "can_delete_notification",
                "can_send_notification",
                # Todo Lists - Full access
                "can_view_todo",
                "can_add_todo",
                "can_edit_todo",
                "can_delete_todo",
                "can_complete_todo",
                # Audit Logs - View only
                "can_view_audit_log",
            ],
            "ICT": [
                # Department Management - View only
                "can_view_department",
                "can_view_department_lookup",
                # Document Categories - Full access
                "can_view_document_category",
                "can_add_document_category",
                "can_edit_document_category",
                "can_delete_document_category",
                # Documents - Full access
                "can_view_document",
                "can_add_document",
                "can_edit_document",
                "can_delete_document",
                "can_download_document",
                # Announcements - Full access
                "can_view_announcement",
                "can_add_announcement",
                "can_edit_announcement",
                "can_delete_announcement",
                "can_pin_announcement",
                # Events - Full access
                "can_view_event",
                "can_add_event",
                "can_edit_event",
                "can_delete_event",
                "can_manage_event_attendees",
                # FAQs - Full access
                "can_view_faq",
                "can_add_faq",
                "can_edit_faq",
                "can_delete_faq",
                # Notifications - Full access
                "can_view_notification",
                "can_add_notification",
                "can_edit_notification",
                "can_delete_notification",
                "can_send_notification",
                # Todo Lists - Full access
                "can_view_todo",
                "can_add_todo",
                "can_edit_todo",
                "can_delete_todo",
                "can_complete_todo",
                # Audit Logs - Full access
                "can_view_audit_log",
                "can_export_audit_log",
            ],
        
            "staff": [
                # Internal Portal - View and basic actions
                "can_view_document",
                "can_download_document",
                "can_view_announcement",
                "can_view_event",
                "can_view_faq",
                "can_view_notification",
                "can_view_todo",
                "can_view_department",
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
        else:
            self.stdout.write("Group exists: admin")
        
        admin_group_lower.permissions.clear()
        admin_group_lower.permissions.add(*Permission.objects.all())
        self.stdout.write(self.style.SUCCESS("Assigned ALL available permissions to admin group"))

        self.stdout.write(self.style.SUCCESS("Custom permissions and groups synchronized."))
