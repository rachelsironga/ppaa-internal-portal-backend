"""
Create Strategic Performance (SPISM / ppaa_performance) custom permissions and assign groups.

Run: python manage.py ppaa_performance_permissions

Aligns with:
  - Frontend: src/data/performanceDashboardMenu.json, src/router/performanceDashboardRoutes.jsx
  - API enforcement: microservices.ppaa_performance.spism_permissions / SpismProtectedAPIView

Groups (Django ``Group.name``):
  - SPISM_Admin: full SPISM (all codenames below).
  - SPISM_Viewer: read-only staff / viewer experience (main + viewer dashboards, reports API).
  - SPISM_Approver: institutional ES / Executive Secretary profile — ``can_view_spism_analytics`` (Approver
    dashboard + reports), ``can_view_spism_approval`` + ``can_approve_spism_planning`` + ``can_approve_spism_implementation``
    (objectives, targets, activities, implementation review), full read across planning/implementation/KPIs,
    ``can_edit_spism_activity`` / ``can_edit_spism_quarterly_data`` where needed for review; not audit trail or FY setup.
  - SPISM_Dept_Head: department head / implementation lead (same permission set as legacy ``SPISM_Contributor``:
    planning read + targets edit where needed, activities CRUD, quarterly & documents, implementation;
    no approval, audit, or setup / FY admin UI). Users in ``SPISM_Contributor`` are migrated to this group
    when this command runs.
  - SPISM_Planning_Officer (alias ``SPIMS_Planning_Officer``): planning unit / HoP — objectives & targets
    CRUD, KPIs, implementation & activities, quarterly & documents, reports & main dashboard; no approval
    queue, audit log, setup / FY admin UI, or ``can_view_spism_analytics`` (ES approver API).
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

LEGACY_SPISM_CONTRIBUTOR_GROUP = "SPISM_Contributor"
SPISM_DEPT_HEAD_GROUP = "SPISM_Dept_Head"


# Custom auth.Permission rows (content_type = auth.permission) — same codenames as React ``user_permissions``.
SPISM_PERMISSIONS = [
    ("can_view_spism_dashboard", "Can view Strategic Performance dashboard"),
    ("can_view_spism_reports", "Can view SPISM reports / viewer dashboard"),
    ("can_view_spism_analytics", "Can view SPISM analytics / approver dashboard"),
    ("can_view_spism_objective", "Can view SPISM objectives"),
    ("can_add_spism_objective", "Can add SPISM objectives"),
    ("can_edit_spism_objective", "Can edit SPISM objectives"),
    ("can_delete_spism_objective", "Can delete SPISM objectives"),
    ("can_view_spism_target", "Can view SPISM targets (KPI)"),
    ("can_add_spism_target", "Can add SPISM targets"),
    ("can_edit_spism_target", "Can edit SPISM targets"),
    ("can_delete_spism_target", "Can delete SPISM targets"),
    ("can_view_spism_kpi_actual", "Can view SPISM KPI actuals"),
    ("can_add_spism_kpi_actual", "Can add SPISM KPI actuals"),
    ("can_edit_spism_kpi_actual", "Can edit SPISM KPI actuals"),
    ("can_view_spism_implementation", "Can view SPISM implementation"),
    ("can_view_spism_activity", "Can view SPISM activities"),
    ("can_add_spism_activity", "Can add SPISM activities"),
    ("can_edit_spism_activity", "Can edit SPISM activities"),
    ("can_delete_spism_activity", "Can delete SPISM activities"),
    ("can_add_spism_quarterly_data", "Can add SPISM quarterly data"),
    ("can_edit_spism_quarterly_data", "Can edit SPISM quarterly data"),
    ("can_add_spism_supporting_document", "Can add SPISM supporting documents"),
    ("can_edit_spism_supporting_document", "Can edit SPISM supporting documents"),
    ("can_delete_spism_supporting_document", "Can delete SPISM supporting documents"),
    ("can_view_spism_approval", "Can view SPISM approval queues"),
    ("can_approve_spism_planning", "Can approve SPISM planning (objectives/targets/activities)"),
    ("can_approve_spism_implementation", "Can approve SPISM implementation"),
    ("can_view_spism_audit_log", "Can view SPISM audit trail"),
    ("can_view_spism_setup", "Can view SPISM setup (financial years)"),
    ("can_edit_spism_setup", "Can edit SPISM setup (financial years)"),
]


def _all_spism_codenames():
    return [c for c, _ in SPISM_PERMISSIONS]


def _viewer_codenames():
    """Read-only: main + viewer dashboards, reports, and FY list (filters on dashboards)."""
    return sorted(
        {
            "can_view_spism_dashboard",
            "can_view_spism_reports",
            "can_view_spism_setup",
        }
    )


def _approver_codenames():
    """Broad planning/implementation read + approve; exclude audit log and setup/FY admin."""
    base = {
        c
        for c in _all_spism_codenames()
        if c.startswith("can_view_")
        or c.startswith("can_approve_")
        or c in ("can_edit_spism_activity", "can_edit_spism_quarterly_data")
    }
    base -= {
        "can_view_spism_audit_log",
        "can_view_spism_setup",
        "can_edit_spism_setup",
    }
    return sorted(base)


def _dept_head_codenames():
    """Department heads / implementation leads: no approval, audit, analytics, or setup (FY admin / notifications UI)."""
    return sorted(
        {
            "can_view_spism_dashboard",
            "can_view_spism_objective",
            "can_view_spism_target",
            "can_edit_spism_target",
            "can_view_spism_kpi_actual",
            "can_add_spism_kpi_actual",
            "can_edit_spism_kpi_actual",
            "can_view_spism_activity",
            "can_add_spism_activity",
            "can_edit_spism_activity",
            "can_delete_spism_activity",
            "can_view_spism_implementation",
            "can_add_spism_quarterly_data",
            "can_edit_spism_quarterly_data",
            "can_add_spism_supporting_document",
            "can_edit_spism_supporting_document",
            "can_delete_spism_supporting_document",
        }
    )


def _planning_officer_codenames():
    """Planning department leads: full planning + operational SPISM tabs; no setup/FY admin UI."""
    return sorted(
        {
            "can_view_spism_dashboard",
            "can_view_spism_reports",
            "can_view_spism_objective",
            "can_add_spism_objective",
            "can_edit_spism_objective",
            "can_delete_spism_objective",
            "can_view_spism_target",
            "can_add_spism_target",
            "can_edit_spism_target",
            "can_delete_spism_target",
            "can_view_spism_kpi_actual",
            "can_add_spism_kpi_actual",
            "can_edit_spism_kpi_actual",
            "can_view_spism_implementation",
            "can_view_spism_activity",
            "can_add_spism_activity",
            "can_edit_spism_activity",
            "can_delete_spism_activity",
            "can_add_spism_quarterly_data",
            "can_edit_spism_quarterly_data",
            "can_add_spism_supporting_document",
            "can_edit_spism_supporting_document",
            "can_delete_spism_supporting_document",
        }
    )


class Command(BaseCommand):
    help = "Create SPISM (Strategic Performance) permissions and assign SPISM_* groups"

    def handle(self, *args, **options):
        self.stdout.write("Processing SPISM / PPAA Performance permissions...")
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
                self.stdout.write(self.style.SUCCESS(f"Created permission {codename}"))
        self.stdout.write(f"Done. New permissions created: {created_count}")

        codenames = _all_spism_codenames()
        perm_qs = Permission.objects.filter(codename__in=codenames)

        planning_codes = _planning_officer_codenames()
        groups_map = {
            "SPISM_Admin": codenames,
            "SPISM_Viewer": _viewer_codenames(),
            "SPISM_Approver": _approver_codenames(),
            SPISM_DEPT_HEAD_GROUP: _dept_head_codenames(),
            "SPISM_Planning_Officer": planning_codes,
            "SPIMS_Planning_Officer": planning_codes,
        }

        for group_name, codes in groups_map.items():
            group, gcreated = Group.objects.get_or_create(name=group_name)
            if gcreated:
                self.stdout.write(self.style.SUCCESS(f"Created group {group_name}"))
            wanted = Permission.objects.filter(codename__in=codes)
            group.permissions.set(wanted)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Set group '{group_name}' to {wanted.count()} permission(s)"
                )
            )

        admin = Group.objects.filter(name__iexact="admin").first()
        if admin:
            admin.permissions.add(*perm_qs)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Merged SPISM permissions into 'admin' group ({perm_qs.count()} codenames)."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING("Group 'admin' not found — create it or run other setup commands.")
            )

        self._migrate_legacy_contributor_group_to_dept_head()

        self.stdout.write(self.style.SUCCESS("ppaa_performance_permissions finished."))

    def _migrate_legacy_contributor_group_to_dept_head(self):
        """Move members from ``SPISM_Contributor`` to ``SPISM_Dept_Head`` and remove the legacy group."""
        old = Group.objects.filter(name=LEGACY_SPISM_CONTRIBUTOR_GROUP).first()
        new = Group.objects.filter(name=SPISM_DEPT_HEAD_GROUP).first()
        if not old:
            return
        if not new:
            self.stdout.write(
                self.style.WARNING(
                    f"Group {SPISM_DEPT_HEAD_GROUP!r} missing — cannot migrate from {LEGACY_SPISM_CONTRIBUTOR_GROUP!r}."
                )
            )
            return
        moved = 0
        UserModel = get_user_model()
        for user in UserModel.objects.filter(groups=old).distinct():
            user.groups.add(new)
            user.groups.remove(old)
            moved += 1
        old.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Migrated {moved} user(s) from {LEGACY_SPISM_CONTRIBUTOR_GROUP!r} to "
                f"{SPISM_DEPT_HEAD_GROUP!r} and removed the legacy group."
            )
        )
