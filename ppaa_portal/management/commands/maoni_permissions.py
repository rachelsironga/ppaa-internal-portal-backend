"""
Create Maoni (PPAA suggestions) model permissions, optional custom codenames, and group mappings.

Aligns with:
  - microservices.maoni models: MaoniCategory, MaoniSuggestion, MaoniSuggestionComment
  - Frontend access: staff / PPAA_Maoni_Reviewer / admin (PPAA Maoni & Maoni dashboard)

Run:
  python manage.py maoni_permissions

Merges Maoni permissions into admin / staff without removing their other permissions (reviewers use dedicated PPAA_Maoni_Reviewer).
Dedicated groups (see MAONI_GROUP_* below) are fully (re)set to the mapped sets.
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
    "MAONI_REVIEWER_GROUP_NAME", "PPAA_Maoni_Reviewer"
)
MAONI_GROUP_CONTRIBUTOR = "Maoni_Contributor"
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
    ("can_review_maoni_suggestion", "Can review and change status of Maoni suggestions (Maoni reviewers)"),
    ("can_reply_maoni_suggestion", "Can post official replies on Maoni suggestions (Maoni reviewers)"),
    ("can_manage_maoni_categories", "Can manage Maoni categories"),
)


class Command(BaseCommand):
    help = "Create Maoni permissions and assign them to groups"

    def handle(self, *args, **options):
        self.stdout.write("Processing Maoni permissions...")

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
            MAONI_GROUP_REVIEWER: self._hr_codenames(all_codes),
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
            "can_review_maoni_suggestion",
            "can_reply_maoni_suggestion",
            "can_manage_maoni_categories",
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

    def _remove_obsolete_maoni_groups(self):
        """Drop deprecated Maoni groups (replaced by PPAA_Maoni_Reviewer / Maoni_Admin)."""
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
