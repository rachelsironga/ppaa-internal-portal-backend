"""
Create internal-portal and system custom permissions, then sync Django groups.

Run (from ppaa-internal-portal-backend):

    python manage.py custom_permissions

Groups:
  - admin: all Permission rows (unchanged)
  - staff: baseline portal access (profile, lookups)
  - content_editor: same scope as the former HR group — content + settings modules
    (documents, events, FAQs, announcements, todos, quick links, popup cards,
    departments, positional levels, document categories); not audit/ICT-only tools.
  - ICT: content_editor-equivalent portal permissions plus audit log view/export.
  - PR_Gallery_Manager: staff baseline plus full PR flyers/posters gallery (view/add/edit/delete);
    assign this group to Public Relations staff who manage the internal portal gallery only.

Permission codenames align with:
  - src/data/ppaaInternalPortal.json (role + permission gates)
  - src/router/ppaaInternalPortal.jsx (ProtectedRoute requiredPermissions / roles)
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand


# Custom auth.Permission rows (content_type = auth.permission) — UI + API aliases.
INTERNAL_PORTAL_CUSTOM_PERMISSIONS = [
    # System / users (existing + used by staff)
    ("can_view_system_permission", "Can View System Permission"),
    ("can_view_sensitive_data", "Can View Sensitive Data"),
    ("can_add_department", "Can Add Department"),
    ("can_view_department", "Can View Department"),
    ("can_edit_department", "Can Edit Department"),
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
    ("can_manage_user_lifecycle", "Can Manage User Lifecycle (retire, block, delete)"),
    ("can_upload_profile_photo", "Can Upload Profile Photo"),
    # Documents
    ("can_view_document", "Can View Portal Documents"),
    ("can_add_document", "Can Add Portal Documents"),
    ("can_edit_document", "Can Edit Portal Documents"),
    ("can_delete_document", "Can Delete Portal Documents"),
    # Events
    ("can_view_event", "Can View Portal Events"),
    ("can_add_event", "Can Add Portal Events"),
    ("can_edit_event", "Can Edit Portal Events"),
    ("can_delete_event", "Can Delete Portal Events"),
    # FAQs
    ("can_view_faq", "Can View Portal FAQs"),
    ("can_add_faq", "Can Add Portal FAQs"),
    ("can_edit_faq", "Can Edit Portal FAQs"),
    ("can_delete_faq", "Can Delete Portal FAQs"),
    # Announcements
    ("can_view_announcement", "Can View Portal Announcements"),
    ("can_add_announcement", "Can Add Portal Announcements"),
    ("can_edit_announcement", "Can Edit Portal Announcements"),
    ("can_delete_announcement", "Can Delete Portal Announcements"),
    # Todos
    ("can_view_todo", "Can View Portal Todos"),
    ("can_add_todo", "Can Add Portal Todos"),
    ("can_edit_todo", "Can Edit Portal Todos"),
    ("can_delete_todo", "Can Delete Portal Todos"),
    # Quick links
    ("can_view_quick_link", "Can View Portal Quick Links"),
    ("can_add_quick_link", "Can Add Portal Quick Links"),
    ("can_edit_quick_link", "Can Edit Portal Quick Links"),
    ("can_delete_quick_link", "Can Delete Portal Quick Links"),
    # Popup cards
    ("can_view_popup_card", "Can View Portal Popup Cards"),
    ("can_add_popup_card", "Can Add Portal Popup Cards"),
    ("can_edit_popup_card", "Can Edit Portal Popup Cards"),
    ("can_delete_popup_card", "Can Delete Portal Popup Cards"),
    ("can_change_popup_card", "Can Change Portal Popup Card State"),
    # PR flyers / posters
    ("can_view_pr_flyer", "Can View Portal PR Flyers"),
    ("can_add_pr_flyer", "Can Add Portal PR Flyers"),
    ("can_edit_pr_flyer", "Can Edit Portal PR Flyers"),
    ("can_delete_pr_flyer", "Can Delete Portal PR Flyers"),
    # Audit (ICT / admin; not part of content_editor / former HR scope)
    ("can_view_audit_log", "Can View Portal Audit Logs"),
    ("can_export_audit_log", "Can Export Portal Audit Logs"),
    # Positional levels (UI uses these on Open pages)
    ("can_view_positional_level", "Can View Positional Levels"),
    ("can_add_positional_level", "Can Add Positional Levels"),
    ("can_edit_positional_level", "Can Edit Positional Levels"),
    ("can_delete_positional_level", "Can Delete Positional Levels"),
]


def _content_editor_codenames():
    """Codenames assigned to group ``content_editor`` (frontend + aligned API aliases)."""
    return [
        # Profile / portal entry
        "can_view_own_profile",
        "can_change_own_password",
        "can_upload_profile_photo",
        "can_view_department_lookup",
        # Departments & positional (settings + DepartmentView / PositionalLevelView)
        "can_view_department",
        "can_add_department",
        "can_edit_department",
        "can_delete_department",
        "view_department",
        "add_department",
        "change_department",
        "delete_department",
        "can_view_positional_level",
        "can_add_positional_level",
        "can_edit_positional_level",
        "can_delete_positional_level",
        # Content modules
        "can_view_document",
        "can_add_document",
        "can_edit_document",
        "can_delete_document",
        "can_view_event",
        "can_add_event",
        "can_edit_event",
        "can_delete_event",
        "can_view_faq",
        "can_add_faq",
        "can_edit_faq",
        "can_delete_faq",
        "can_view_announcement",
        "can_add_announcement",
        "can_edit_announcement",
        "can_delete_announcement",
        "can_view_todo",
        "can_add_todo",
        "can_edit_todo",
        "can_delete_todo",
        "can_view_quick_link",
        "can_add_quick_link",
        "can_edit_quick_link",
        "can_delete_quick_link",
        "can_view_popup_card",
        "can_add_popup_card",
        "can_edit_popup_card",
        "can_delete_popup_card",
        "can_change_popup_card",
        "can_view_pr_flyer",
        "can_add_pr_flyer",
        "can_edit_pr_flyer",
        "can_delete_pr_flyer",
    ]


def _staff_codenames():
    return [
        "can_view_group",
        "can_view_own_profile",
        "can_change_own_password",
        "can_upload_profile_photo",
        "can_view_department_lookup",
    ]


def _pr_gallery_manager_codenames():
    """PR / communications: manage flyers & posters gallery only (no other content modules)."""
    return list(_staff_codenames()) + [
        "can_view_pr_flyer",
        "can_add_pr_flyer",
        "can_edit_pr_flyer",
        "can_delete_pr_flyer",
    ]


def _ict_codenames():
    """ICT: former HR-style portal access plus audit (does not replace content_editor)."""
    codes = list(_content_editor_codenames())
    for extra in ("can_view_audit_log", "can_export_audit_log"):
        if extra not in codes:
            codes.append(extra)
    return codes


class Command(BaseCommand):
    help = (
        "Create custom permissions and assign staff / content_editor / ICT / "
        "PR_Gallery_Manager / admin groups"
    )

    def handle(self, *args, **options):
        self.stdout.write("Processing custom permissions...")


        default_ct = ContentType.objects.get(app_label="auth", model="permission")

        seen = set()
        for codename, name in INTERNAL_PORTAL_CUSTOM_PERMISSIONS:
            if codename in seen:
                continue
            seen.add(codename)
            perm, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=default_ct,
                defaults={"name": name},
# (conflict marker removed)
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
# (conflict marker removed)
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created permission '{codename}'"))
            else:
                self.stdout.write(f"Permission '{codename}' already exists")


        groups_to_permissions = {
            "staff": _staff_codenames(),
            "content_editor": _content_editor_codenames(),
            "ICT": _ict_codenames(),
            "PR_Gallery_Manager": _pr_gallery_manager_codenames(),
        }

# (conflict marker removed)
# (conflict marker removed)
        self.stdout.write("Processing groups...")

        for group_name, perm_codes in groups_to_permissions.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created group '{group_name}'"))
            else:
                self.stdout.write(f"Group exists: {group_name}")


            group.permissions.clear()
            added = 0
            for code in perm_codes:
                qs = Permission.objects.filter(codename=code)
                n = qs.count()
                if n == 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Permission codename '{code}' not found — assign manually or run migrations."
                        )
                    )
                    continue
                for perm in qs:
                    group.permissions.add(perm)
                    added += 1
            self.stdout.write(
                self.style.SUCCESS(f"Group '{group_name}': linked {added} permission row(s).")
            )

        admin_group, created = Group.objects.get_or_create(name="admin")
        if created:
            self.stdout.write(self.style.SUCCESS("Created group 'admin'"))
        else:
            self.stdout.write("Group exists: admin")

        admin_group.permissions.clear()
        admin_group.permissions.add(*Permission.objects.all())
        self.stdout.write(
            self.style.SUCCESS("Assigned ALL available permissions to admin group")
        )

        self.stdout.write(self.style.SUCCESS("custom_permissions finished."))
# (conflict marker removed)
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
# (conflict marker removed)
