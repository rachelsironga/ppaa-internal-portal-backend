"""
Create Reports Management System (RMS) model permissions and assign portal groups.

Aligns with frontend roles: RMS_SYS_ADMIN, RMS_REPORT_MANAGER, RMS_DEPT_REPORTER.

RMS_REPORT_MANAGER: all RMS view_*; full workflow on reports / period state / progress
(including delete_rmsreport); no add/change/delete on report types, categories, or stakeholders.
SPISM financial year mutations and global audit trail remain view-gated to RMS_SYS_ADMIN /
portal admin.

Also ensures Django model permissions for ``SpismFinancialYear`` (``ppaa_performance``) exist
and assigns them to ``RMS_SYS_ADMIN`` and the portal ``admin`` group so JWTs include FY
codenames (``add_spismfinancialyear``, …) for RMS Setup.

Run: python manage.py rms_permission
"""

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

APP_LABEL = "ppaa_portal"
RMS_MODEL_NAMES = (
    "RmsStakeholder",
    "RmsReportType",
    "RmsReportCategory",
    "RmsReport",
    "RmsReportPeriodState",
    "RmsReportProgressEntry",
)


class Command(BaseCommand):
    help = "Create RMS model permissions and assign RMS_* groups"

    def handle(self, *args, **options):
        self.stdout.write("Processing RMS permissions...")
        created = 0
        codenames_by_model = {}

        for model_name in RMS_MODEL_NAMES:
            try:
                model = apps.get_model(APP_LABEL, model_name)
            except LookupError:
                self.stdout.write(
                    self.style.WARNING(
                        f"Model {APP_LABEL}.{model_name} not found — skip."
                    )
                )
                continue
            ct = ContentType.objects.get_for_model(model)
            mn = model._meta.model_name
            label = model._meta.verbose_name or model_name
            codes = []
            for action in ("add", "change", "delete", "view"):
                codename = f"{action}_{mn}"
                _, was_created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=ct,
                    defaults={"name": f"Can {action} {label}"},
                )
                codes.append(codename)
                if was_created:
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f"Created {codename}"))
            codenames_by_model[mn] = codes

        all_codenames = sorted({c for codes in codenames_by_model.values() for c in codes})

        fy_app = "ppaa_performance"
        fy_model_name = "SpismFinancialYear"
        fy_codenames: list[str] = []
        try:
            fy_model = apps.get_model(fy_app, fy_model_name)
        except LookupError:
            fy_model = None
        if fy_model:
            ct_fy = ContentType.objects.get_for_model(fy_model)
            mn_fy = fy_model._meta.model_name
            label_fy = fy_model._meta.verbose_name or fy_model_name
            for action in ("add", "change", "delete", "view"):
                codename = f"{action}_{mn_fy}"
                _, was_created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=ct_fy,
                    defaults={"name": f"Can {action} {label_fy}"},
                )
                fy_codenames.append(codename)
                if was_created:
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f"Created {codename}"))
            self.stdout.write(
                self.style.SUCCESS(
                    f"Financial year (SPISM) permissions: {len(fy_codenames)} codenames"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"{fy_app}.{fy_model_name} not found — skip FY model permissions."
                )
            )

        rms_perm_qs = Permission.objects.filter(codename__in=all_codenames)
        self.stdout.write(
            f"RMS permissions: {rms_perm_qs.count()} total (new this run: {created})"
        )

        mn_report = "rmsreport"
        mn_period = "rmsreportperiodstate"
        mn_progress = "rmsreportprogressentry"

        def reporter_codenames():
            """Dept reporters: view all RMS models; add/change on report workflow models only (no deletes)."""
            out = []
            for cn in all_codenames:
                if cn.startswith("delete_"):
                    continue
                if cn.startswith("view_"):
                    out.append(cn)
                elif cn.startswith(("add_", "change_")) and any(
                    x in cn for x in (mn_report, mn_period, mn_progress)
                ):
                    out.append(cn)
            return sorted(set(out))

        def manager_codenames():
            """
            Institution report managers: read catalog (view_* on all RMS models); mutate
            reports, period states, and progress only (including soft-delete report). No
            stakeholder / type / category mutations.
            """
            setup_models = ("rmsreporttype", "rmsreportcategory", "rmsstakeholder")
            out = []
            for cn in all_codenames:
                if cn.startswith("view_"):
                    out.append(cn)
                    continue
                for action in ("add_", "change_", "delete_"):
                    if not cn.startswith(action):
                        continue
                    rest = cn[len(action) :]
                    if rest in setup_models:
                        break
                    if rest in (mn_report, mn_period, mn_progress):
                        out.append(cn)
                    break
            return sorted(set(out))

        sys_admin_codenames = sorted(set(all_codenames + fy_codenames))

        groups_map = {
            "RMS_SYS_ADMIN": sys_admin_codenames,
            "RMS_REPORT_MANAGER": manager_codenames(),
            "RMS_DEPT_REPORTER": reporter_codenames(),
        }

        for group_name, codes in groups_map.items():
            group, gcreated = Group.objects.get_or_create(name=group_name)
            if gcreated:
                self.stdout.write(self.style.SUCCESS(f"Created group '{group_name}'"))
            wanted = Permission.objects.filter(codename__in=codes)
            group.permissions.set(wanted)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Set group '{group_name}' to {wanted.count()} RMS permissions"
                )
            )

        admin = Group.objects.filter(name__iexact="admin").first()
        if admin:
            merge_codes = set(all_codenames) | set(fy_codenames)
            before = admin.permissions.filter(codename__in=merge_codes).count()
            admin.permissions.add(
                *list(rms_perm_qs),
                *list(Permission.objects.filter(codename__in=fy_codenames)),
            )
            after = admin.permissions.filter(codename__in=merge_codes).count()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Merged RMS + FY permissions into 'admin' (+{after - before} new links)."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Group 'admin' not found — run permissions_superuser first."
                )
            )

        self.stdout.write(self.style.SUCCESS("rms_permission finished."))
