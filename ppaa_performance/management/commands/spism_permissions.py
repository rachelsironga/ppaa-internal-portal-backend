"""
SPISM custom permissions — aligned with internal portal naming (can_view_*, can_add_*, …).

Run after:
  python manage.py custom_permissions
  python manage.py ensure_spism_groups

Legacy codenames (spism_view_*, spism_manage_*, …) are migrated off groups when this command runs.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, ContentType, Group

from ppaa_performance.constants import (
    SPISM_ROLE_HEAD_OF_PLANNING,
    SPISM_ROLE_HEAD_OF_UNIT,
    SPISM_ROLE_EXECUTIVE_SECRETARY,
    SPISM_ROLE_ICT_ADMINISTRATOR,
    SPISM_ROLE_INTERNAL_AUDIT,
    SPISM_ROLE_READ_ONLY,
)

# (codename, verbose_name) — verbose_name follows Django style: "Can …"
SPISM_PERMISSIONS = [
    # Dashboard & analytics
    ("can_view_spism_dashboard", "Can view SPISM dashboard"),
    ("can_view_spism_analytics", "Can view SPISM trends and forecast analytics"),
    ("can_view_spism_reports", "Can view SPISM reports"),
    # Planning — objectives
    ("can_view_spism_objective", "Can view SPISM objectives"),
    ("can_add_spism_objective", "Can add SPISM objectives"),
    ("can_edit_spism_objective", "Can edit SPISM objectives"),
    ("can_delete_spism_objective", "Can delete SPISM objectives"),
    # Planning — targets (KPIs)
    ("can_view_spism_target", "Can view SPISM targets (KPIs)"),
    ("can_add_spism_target", "Can add SPISM targets (KPIs)"),
    ("can_edit_spism_target", "Can edit SPISM targets (KPIs)"),
    ("can_delete_spism_target", "Can delete SPISM targets (KPIs)"),
    # Planning — activities
    ("can_view_spism_activity", "Can view SPISM activities"),
    ("can_add_spism_activity", "Can add SPISM activities"),
    ("can_edit_spism_activity", "Can edit SPISM activities"),
    ("can_delete_spism_activity", "Can delete SPISM activities"),
    # Approvals
    ("can_view_spism_approval", "Can view SPISM approval queues"),
    (
        "can_approve_spism_planning",
        "Can approve or return SPISM planning (objectives, targets, activities)",
    ),
    (
        "can_approve_spism_implementation",
        "Can approve or return SPISM implementation",
    ),
    # Implementation
    ("can_view_spism_implementation", "Can view SPISM implementation"),
    ("can_add_spism_quarterly_data", "Can add SPISM quarterly implementation data"),
    ("can_edit_spism_quarterly_data", "Can edit SPISM quarterly implementation data"),
    ("can_delete_spism_quarterly_data", "Can delete SPISM quarterly implementation data"),
    ("can_add_spism_supporting_document", "Can add SPISM supporting documents"),
    ("can_edit_spism_supporting_document", "Can edit SPISM supporting documents"),
    ("can_delete_spism_supporting_document", "Can delete SPISM supporting documents"),
    ("can_view_spism_kpi_actual", "Can view SPISM KPI actual values"),
    ("can_add_spism_kpi_actual", "Can add SPISM KPI actual values"),
    ("can_edit_spism_kpi_actual", "Can edit SPISM KPI actual values"),
    ("can_delete_spism_kpi_actual", "Can delete SPISM KPI actual values"),
    # Audit & setup
    ("can_view_spism_audit_log", "Can view SPISM audit logs"),
    ("can_view_spism_setup", "Can view SPISM setup and financial years"),
    ("can_edit_spism_setup", "Can edit SPISM setup and financial years"),
]

# Old codename -> list of new codenames (for group migration)
LEGACY_TO_NEW = {
    "spism_view_dashboard": ["can_view_spism_dashboard"],
    "spism_view_analytics": ["can_view_spism_analytics"],
    "spism_view_reports": ["can_view_spism_reports"],
    "spism_view_objective": ["can_view_spism_objective"],
    "spism_manage_objective": [
        "can_add_spism_objective",
        "can_edit_spism_objective",
        "can_delete_spism_objective",
    ],
    "spism_view_target": ["can_view_spism_target"],
    "spism_manage_target": [
        "can_add_spism_target",
        "can_edit_spism_target",
        "can_delete_spism_target",
    ],
    "spism_view_activity": ["can_view_spism_activity"],
    "spism_manage_activity": [
        "can_add_spism_activity",
        "can_edit_spism_activity",
        "can_delete_spism_activity",
    ],
    "spism_view_approval": ["can_view_spism_approval"],
    "spism_approve_planning": ["can_approve_spism_planning"],
    "spism_approve_implementation": ["can_approve_spism_implementation"],
    "spism_view_implementation": ["can_view_spism_implementation"],
    "spism_manage_quarterly_data": [
        "can_add_spism_quarterly_data",
        "can_edit_spism_quarterly_data",
        "can_delete_spism_quarterly_data",
    ],
    "spism_manage_supporting_documents": [
        "can_add_spism_supporting_document",
        "can_edit_spism_supporting_document",
        "can_delete_spism_supporting_document",
    ],
    "spism_manage_kpi_actuals": [
        "can_add_spism_kpi_actual",
        "can_edit_spism_kpi_actual",
        "can_delete_spism_kpi_actual",
    ],
    "spism_view_audit_logs": ["can_view_spism_audit_log"],
    "spism_manage_setup": ["can_view_spism_setup", "can_edit_spism_setup"],
}

_OBJ_FULL = [
    "can_view_spism_objective",
    "can_add_spism_objective",
    "can_edit_spism_objective",
    "can_delete_spism_objective",
]
_TGT_FULL = [
    "can_view_spism_target",
    "can_add_spism_target",
    "can_edit_spism_target",
    "can_delete_spism_target",
]
_ACT_FULL = [
    "can_view_spism_activity",
    "can_add_spism_activity",
    "can_edit_spism_activity",
    "can_delete_spism_activity",
]
_Q_FULL = [
    "can_add_spism_quarterly_data",
    "can_edit_spism_quarterly_data",
    "can_delete_spism_quarterly_data",
]
_DOC_FULL = [
    "can_add_spism_supporting_document",
    "can_edit_spism_supporting_document",
    "can_delete_spism_supporting_document",
]
_KPI_FULL = [
    "can_add_spism_kpi_actual",
    "can_edit_spism_kpi_actual",
    "can_delete_spism_kpi_actual",
]


def _migrate_legacy_group_permissions(stdout, style):
    """Replace legacy spism_* permissions on all groups with new can_* equivalents."""
    replacements = 0
    for group in Group.objects.all():
        for old_code, new_codes in LEGACY_TO_NEW.items():
            try:
                old_perm = Permission.objects.get(codename=old_code)
            except Permission.DoesNotExist:
                continue
            if not group.permissions.filter(pk=old_perm.pk).exists():
                continue
            group.permissions.remove(old_perm)
            for nc in new_codes:
                try:
                    np = Permission.objects.get(codename=nc)
                    group.permissions.add(np)
                except Permission.DoesNotExist:
                    stdout.write(
                        style.WARNING(
                            f"Missing new permission '{nc}' while migrating group '{group.name}'"
                        )
                    )
            replacements += 1
    if replacements:
        stdout.write(
            style.SUCCESS(
                f"Migrated {replacements} legacy SPISM permission assignment(s) on groups."
            )
        )
    else:
        stdout.write(
            "No legacy SPISM permissions on groups (skip migration). "
            "Direct user_permissions are not changed — re-assign in Admin if needed."
        )


class Command(BaseCommand):
    help = (
        "Create SPISM permissions (can_* style, like internal portal) and assign them to SPISM role groups.\n"
        "Migrates legacy spism_* codenames on groups to the new permissions.\n"
        "Run after: custom_permissions, ensure_spism_groups."
    )

    def handle(self, *args, **options):
        self.stdout.write("Processing SPISM permissions (can_* naming)…")

        default_ct = ContentType.objects.get(app_label="auth", model="permission")

        created_count = 0
        for codename, name in SPISM_PERMISSIONS:
            _, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=default_ct,
                defaults={"name": name},
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Created permission '{codename}'")
                )
            else:
                # Keep human-readable label in sync if you change SPISM_PERMISSIONS
                Permission.objects.filter(
                    codename=codename, content_type=default_ct
                ).update(name=name)

        self.stdout.write(
            self.style.SUCCESS(
                f"SPISM permissions ready. Newly created this run: {created_count}"
            )
        )

        self.stdout.write("Migrating legacy spism_* permissions on groups…")
        _migrate_legacy_group_permissions(self.stdout, self.style)

        role_to_perms = {
            SPISM_ROLE_HEAD_OF_PLANNING: [
                "can_view_spism_dashboard",
                "can_view_spism_analytics",
                "can_view_spism_reports",
                *_OBJ_FULL,
                *_TGT_FULL,
                *_ACT_FULL,
                "can_view_spism_approval",
                "can_approve_spism_planning",
                "can_view_spism_implementation",
                *_Q_FULL,
                *_KPI_FULL,
            ],
            SPISM_ROLE_HEAD_OF_UNIT: [
                "can_view_spism_dashboard",
                "can_view_spism_analytics",
                "can_view_spism_objective",
                "can_view_spism_target",
                "can_view_spism_activity",
                "can_view_spism_implementation",
                *_Q_FULL,
                *_DOC_FULL,
                *_KPI_FULL,
            ],
            SPISM_ROLE_EXECUTIVE_SECRETARY: [
                "can_view_spism_dashboard",
                "can_view_spism_analytics",
                "can_view_spism_reports",
                "can_view_spism_objective",
                "can_view_spism_target",
                "can_view_spism_activity",
                "can_view_spism_approval",
                "can_approve_spism_planning",
                "can_approve_spism_implementation",
            ],
            SPISM_ROLE_INTERNAL_AUDIT: [
                "can_view_spism_dashboard",
                "can_view_spism_reports",
                "can_view_spism_analytics",
                "can_view_spism_objective",
                "can_view_spism_target",
                "can_view_spism_activity",
                "can_view_spism_implementation",
                "can_view_spism_audit_log",
            ],
            SPISM_ROLE_ICT_ADMINISTRATOR: [code for code, _ in SPISM_PERMISSIONS],
            SPISM_ROLE_READ_ONLY: [
                "can_view_spism_dashboard",
                "can_view_spism_analytics",
                "can_view_spism_reports",
                "can_view_spism_objective",
                "can_view_spism_target",
                "can_view_spism_activity",
                "can_view_spism_implementation",
            ],
        }

        self.stdout.write("Assigning SPISM permissions to SPISM role groups…")

        for group_name, perm_codenames in role_to_perms.items():
            group, _ = Group.objects.get_or_create(name=group_name)
            missing = []
            for code in perm_codenames:
                try:
                    perm = Permission.objects.get(codename=code)
                    group.permissions.add(perm)
                except Permission.DoesNotExist:
                    missing.append(code)
            if missing:
                self.stdout.write(
                    self.style.WARNING(
                        f"Group '{group_name}': missing permissions {missing}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Group '{group_name}': {len(perm_codenames)} permission(s) ensured."
                    )
                )

        self.stdout.write(
            self.style.SUCCESS("SPISM permissions and role mappings synchronized.")
        )
