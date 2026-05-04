"""
Create Maoni (PPAA suggestions) model permissions, optional custom codenames, and group mappings.

Aligns with:
  - microservices.maoni models: MaoniCategory, MaoniSuggestion, MaoniSuggestionComment
  - Frontend access: staff / Maoni_Reviewer / admin (PPAA Maoni & Maoni dashboard)

Run:
  python manage.py maoni_permissions

Merges Maoni permissions into admin / staff without removing their other permissions (reviewers use dedicated Maoni_Reviewer).
Dedicated groups (see MAONI_GROUP_* below) are fully (re)set to the mapped sets:
``Maoni_Reviewer`` gets institutional-reviewer permissions; ``Maoni_Handler`` gets department-queue
permissions (aligned with ``microservices.maoni.views`` workflow checks).
Removes obsolete groups ``ppaa_maoni_lead`` / ``PPAA_Maoni_Lead`` if present.
"""

import os

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db.models import Q

APP_LABEL = "maoni"

# --- Group names (django.contrib.auth.models.Group.name) ---
# Dedicated Maoni-only groups (templates you can assign users to):
MAONI_GROUP_ADMIN = "Maoni_Admin"
# Reviewer / moderator role (replaces legacy name "Maoni_HR"); override with env if needed:
MAONI_GROUP_REVIEWER = os.environ.get(
    "MAONI_REVIEWER_GROUP_NAME", "Maoni_Reviewer"
)
MAONI_GROUP_HANDLER_ALIAS = os.environ.get("MAONI_HANDLER_ALIAS_GROUP_NAME", "Maoni_Handler")
MAONI_GROUP_CONTRIBUTOR = "Maoni_Contributor"
# Historical reviewer group names we still accept and can rename in-place:
LEGACY_MAONI_REVIEWER_GROUP_NAMES = (
    "Moni_Reviewer",
    "Maoni_Reviewe",
    "PPAA_Maoni_Reviewer",
    "PPAA_MAONI_REVEIWE",
)
# Existing portal groups to merge permissions into (must match names in the database):
PORTAL_GROUP_ADMIN = "admin"
# Optional: also merge into legacy "HR" group if it still exists (migration aid)
PORTAL_GROUP_HR_LEGACY = os.environ.get("MAONI_PORTAL_HR_LEGACY_GROUP_NAME", "")
PORTAL_GROUP_STAFF = "staff"

MAONI_MODEL_NAMES = (
    "MaoniCategory",
    "MaoniSuggestion",
    "MaoniSuggestionComment",
)

MAONI_CUSTOM_PERMISSIONS = (
    ("can_view_maoni", "Can access Maoni service (dashboard and lists)"),
    ("can_view_maoni_dashboard", "Can view Maoni dashboard"),
    ("can_add_maoni_suggestion", "Can submit Maoni suggestions"),
    ("can_change_maoni_suggestion", "Can edit Maoni suggestions (e.g. status, content)"),
    ("can_handle_maoni_suggestion", "Can process handler-stage Maoni workflow actions (legacy umbrella)"),
    ("can_pickup_maoni_suggestion", "Can open a submitted Maoni suggestion for department handler review"),
    (
        "can_reviewer_pickup_maoni_suggestion",
        "Can open a submitted Maoni suggestion for review (institutional reviewer queue)",
    ),
    (
        "can_handler_respond_to_maoni_contributor",
        "Can move Maoni workflow to handler responded to contributor (official contributor channel)",
    ),
    (
        "can_handler_respond_to_maoni_reviewer",
        "Can send handler response to institutional reviewer on a Maoni suggestion",
    ),
    ("can_resume_maoni_from_returned", "Can resume Maoni in-progress review after reviewer returned the case"),
    (
        "can_resume_maoni_after_reviewer_response",
        "Can resume Maoni under handler review after messaging the reviewer",
    ),
    (
        "can_resume_maoni_after_contributor",
        "Can resume Maoni under handler review after contributor follow-up",
    ),
    ("can_escalate_maoni_suggestion", "Can escalate Maoni suggestions to reviewer"),
    ("can_return_maoni_suggestion", "Can return Maoni suggestions back to handler"),
    ("can_close_maoni_suggestion", "Can close Maoni suggestions as approved or rejected"),
    ("can_review_maoni_suggestion", "Can review and change status of Maoni suggestions (Maoni reviewers)"),
    ("can_reply_maoni_suggestion", "Can post official replies on Maoni suggestions (Maoni reviewers)"),
    ("can_print_maoni_suggestion", "Can print Maoni suggestions for official handling"),
    ("can_manage_maoni_categories", "Can manage Maoni categories"),
    ("can_view_maoni_escalation_days", "Can view Maoni escalation days setting"),
    ("can_add_maoni_escalation_days", "Can add/update Maoni escalation days setting"),
    ("can_delete_maoni_escalation_days", "Can reset/delete Maoni escalation days setting"),
)


class Command(BaseCommand):
    help = "Create Maoni permissions and assign them to groups"

    def handle(self, *args, **options):
        self.stdout.write("Processing Maoni permissions...")

        self._rename_legacy_reviewer_group()

        created_model = self._ensure_model_permissions()
        created_custom = self._ensure_custom_permissions()
        self.stdout.write(
            self.style.SUCCESS(
                f"Model permissions created (new): {created_model}; "
                f"custom permissions created (new): {created_custom}"
            )
        )

        all_maoni_perms = self._all_maoni_permission_queryset()
        all_codes = list(all_maoni_perms.values_list("codename", flat=True))

        dedicated = {
            MAONI_GROUP_ADMIN: all_codes,
            MAONI_GROUP_REVIEWER: self._maoni_institutional_reviewer_codenames(all_codes),
            MAONI_GROUP_HANDLER_ALIAS: self._maoni_department_handler_codenames(all_codes),
            MAONI_GROUP_CONTRIBUTOR: self._contributor_codenames(all_codes),
        }

        for group_name, codes in dedicated.items():
            group, gcreated = Group.objects.get_or_create(name=group_name)
            if gcreated:
                self.stdout.write(self.style.SUCCESS(f"Created group '{group_name}'"))
            wanted = Permission.objects.filter(codename__in=codes)
            group.permissions.set(wanted)
            self.stdout.write(
                f"Set group '{group_name}' to {wanted.count()} Maoni permissions"
            )

        merge_map = {
            PORTAL_GROUP_ADMIN: all_codes,
            PORTAL_GROUP_STAFF: self._contributor_codenames(all_codes),
        }
        for name, codes in merge_map.items():
            self._merge_into_group(
                name,
                Permission.objects.filter(codename__in=codes),
            )
        if PORTAL_GROUP_HR_LEGACY.strip():
            self._merge_into_group(
                PORTAL_GROUP_HR_LEGACY.strip(),
                Permission.objects.filter(codename__in=self._hr_codenames(all_codes)),
            )

        self._remove_obsolete_maoni_groups()

        self.stdout.write(self.style.SUCCESS("maoni_permissions finished."))

    def _rename_legacy_reviewer_group(self):
        """
        Prefer the current reviewer group name by renaming a legacy one in-place.

        This preserves memberships (users assigned to the old group automatically end up in the
        new group) without requiring manual reassignment.
        """
        wanted = (MAONI_GROUP_REVIEWER or "").strip()
        if not wanted:
            return

        existing_new = Group.objects.filter(name__iexact=wanted).first()
        if existing_new:
            return

        for legacy in LEGACY_MAONI_REVIEWER_GROUP_NAMES:
            old = Group.objects.filter(name__iexact=legacy).first()
            if not old:
                continue
            old_name = old.name
            old.name = wanted
            old.save(update_fields=["name"])
            self.stdout.write(
                self.style.WARNING(
                    f"Renamed legacy Maoni reviewer group '{old_name}' → '{wanted}'."
                )
            )
            return

    def _ensure_model_permissions(self) -> int:
        created = 0
        for model_name in MAONI_MODEL_NAMES:
            try:
                model = apps.get_model(APP_LABEL, model_name)
            except LookupError:
                self.stdout.write(
                    self.style.WARNING(
                        f"Model {APP_LABEL}.{model_name} not found — skip model permissions."
                    )
                )
                continue

            ct = ContentType.objects.get_for_model(model)
            for action in ("add", "change", "delete", "view"):
                codename = f"{action}_{model._meta.model_name}"
                label = model._meta.verbose_name or model_name
                _, was_created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=ct,
                    defaults={
                        "name": f"Can {action} {label}",
                    },
                )
                if was_created:
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f"Created {codename}"))
        return created

    def _ensure_custom_permissions(self) -> int:
        default_ct = ContentType.objects.get(app_label="auth", model="permission")
        created = 0
        for codename, name in MAONI_CUSTOM_PERMISSIONS:
            _, was_created = Permission.objects.get_or_create(
                codename=codename,
                content_type=default_ct,
                defaults={"name": name},
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created custom {codename}"))
        return created

    def _all_maoni_permission_queryset(self):
        """Permissions for Maoni content types plus custom Maoni codenames."""
        ct_ids = []
        for model_name in MAONI_MODEL_NAMES:
            try:
                model = apps.get_model(APP_LABEL, model_name)
                ct_ids.append(ContentType.objects.get_for_model(model).pk)
            except LookupError:
                continue

        custom_codes = [c for c, _ in MAONI_CUSTOM_PERMISSIONS]
        q = Q(codename__in=custom_codes)
        if ct_ids:
            q |= Q(content_type_id__in=ct_ids)
        return Permission.objects.filter(q).distinct()

    def _contributor_codenames(self, all_codes):
        """Staff / contributors: submit suggestions; no HR-only or category-admin rights."""
        hr_only_custom = {
            "can_handle_maoni_suggestion",
            "can_pickup_maoni_suggestion",
            "can_reviewer_pickup_maoni_suggestion",
            "can_handler_respond_to_maoni_contributor",
            "can_handler_respond_to_maoni_reviewer",
            "can_resume_maoni_from_returned",
            "can_resume_maoni_after_reviewer_response",
            "can_resume_maoni_after_contributor",
            "can_escalate_maoni_suggestion",
            "can_return_maoni_suggestion",
            "can_close_maoni_suggestion",
            "can_review_maoni_suggestion",
            "can_reply_maoni_suggestion",
            "can_print_maoni_suggestion",
            "can_manage_maoni_categories",
            "can_view_maoni_escalation_days",
            "can_add_maoni_escalation_days",
            "can_delete_maoni_escalation_days",
        }
        out = []
        for c in all_codes:
            if c in hr_only_custom:
                continue
            if c.startswith("delete_"):
                continue
            if c in (
                "add_maonicategory",
                "change_maonicategory",
                "delete_maonicategory",
            ):
                continue
            out.append(c)
        return sorted(set(out))

    def _hr_codenames(self, all_codes):
        """Maoni reviewers (IHRM / Exec Sec): full Maoni permission set."""
        return sorted(set(all_codes))

    def _maoni_institutional_reviewer_codenames(self, all_codes):
        """
        Institutional reviewer / ES role: thread, return-to-handler, reviewer pickup — not
        department-handler-only transitions (escalate, close, resume-from-returned, etc.).
        """
        exclude = frozenset(
            {
                "can_pickup_maoni_suggestion",
                "can_handler_respond_to_maoni_contributor",
                "can_handler_respond_to_maoni_reviewer",
                "can_resume_maoni_from_returned",
                "can_resume_maoni_after_reviewer_response",
                "can_resume_maoni_after_contributor",
                "can_escalate_maoni_suggestion",
                "can_close_maoni_suggestion",
                "can_handle_maoni_suggestion",
            }
        )
        return sorted(c for c in all_codes if c not in exclude)

    def _maoni_department_handler_codenames(self, all_codes):
        """Department handler queue: escalate, close, resumes, handler responses — not ES return or reviewer pickup."""
        exclude = frozenset(
            {
                "can_return_maoni_suggestion",
                "can_reviewer_pickup_maoni_suggestion",
            }
        )
        return sorted(c for c in all_codes if c not in exclude)

    def _remove_obsolete_maoni_groups(self):
        """Drop deprecated Maoni groups (replaced by Maoni_Reviewer / Maoni_Admin)."""
        obsolete_names = ("ppaa_maoni_lead", "PPAA_Maoni_Lead")
        for raw in obsolete_names:
            qs = Group.objects.filter(name__iexact=raw)
            n = qs.count()
            if n:
                qs.delete()
                self.stdout.write(
                    self.style.WARNING(
                        f"Removed obsolete Maoni group matching {raw!r} ({n} row(s))."
                    )
                )

    def _merge_into_group(self, name, permission_qs):
        group = Group.objects.filter(name__iexact=name).first()
        if not group:
            self.stdout.write(
                self.style.WARNING(f"Group '{name}' not found — skip merge.")
            )
            return
        before = group.permissions.filter(
            id__in=permission_qs.values_list("id", flat=True)
        ).count()
        group.permissions.add(*list(permission_qs))
        after = group.permissions.filter(
            id__in=permission_qs.values_list("id", flat=True)
        ).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Merged Maoni permissions into group '{group.name}' "
                f"({after} maoni-linked permissions present; +{after - before} new links)."
            )
        )
