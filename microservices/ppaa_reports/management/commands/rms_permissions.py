from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.apps import apps


class Command(BaseCommand):
    help = "Create RMS permissions, groups and assign them"

    def handle(self, *args, **options):

        self.stdout.write("Processing RMS permissions...")

        # RMS Models
        rms_models = [
            "FinancialYear",
            "Stakeholder",
            "ReportType",
            "ReportCategory",
            "Report",
            "ReportComment",
            "ReportSetting",
        ]

        permissions_created = 0

        # Create default Django permissions
        for model_name in rms_models:
            try:
                model = apps.get_model("ppaa_reports", model_name)
                content_type = ContentType.objects.get_for_model(model)

                for action in ["add", "view", "change", "delete"]:
                    codename = f"{action}_{model_name.lower()}"
                    name = f"Can {action} {model_name}"

                    perm, created = Permission.objects.get_or_create(
                        codename=codename,
                        content_type=content_type,
                        defaults={"name": name},
                    )

                    if created:
                        permissions_created += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"Created permission {codename}")
                        )

            except LookupError:
                self.stdout.write(
                    self.style.WARNING(f"Model ppaa_reports.{model_name} not found")
                )

        self.stdout.write(
            self.style.SUCCESS(f"{permissions_created} RMS model permissions created")
        )

        # Custom RMS permissions
        custom_permissions = [
            ("submit_report", "Can submit report"),
            ("download_report", "Can download report"),
            ("view_directory_reports", "Can view reports from own directory"),
            ("view_institution_reports", "Can view all institutional reports"),
            ("view_rms_dashboard", "Can view RMS dashboard"),
            ("manage_rms_settings", "Can manage RMS settings"),
            ("view_system_audit", "Can view system audit logs"),
            ("manage_security_alerts", "Can manage system alerts"),
        ]

        default_ct = ContentType.objects.get(app_label="auth", model="permission")

        for codename, name in custom_permissions:
            perm, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=default_ct,
                defaults={"name": name},
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created custom permission {codename}")
                )

        self.stdout.write("Custom RMS permissions processed")

        legacy_reporter_group = Group.objects.filter(name="RMS_DIR_REPORTER").first()
        if legacy_reporter_group and not Group.objects.filter(name="RMS_DEPT_REPORTER").exists():
            legacy_reporter_group.name = "RMS_DEPT_REPORTER"
            legacy_reporter_group.save(update_fields=["name"])
            self.stdout.write(
                self.style.SUCCESS("Renamed legacy RMS_DIR_REPORTER group to RMS_DEPT_REPORTER")
            )

        # Groups and permissions mapping
        groups_to_permissions = {

            # Department Reporter
            "RMS_DEPT_REPORTER": [
                "add_report",
                "view_report",
                "change_report",
                "submit_report",
                "download_report",
                "view_directory_reports",
                "view_financialyear",
                "view_reporttype",
                "view_reportcategory",
                "view_stakeholder",
                "add_reportcomment",
                "view_reportcomment",
            ],

            # Institutional Report Manager (ED - can view all reports, comment, and direct messages to directories)
            "RMS_REPORT_MANAGER": [
                "add_report",
                "view_report",
                "change_report",
                "submit_report",
                "download_report",
                "view_institution_reports",
                "view_financialyear",
                "view_reporttype",
                "view_reportcategory",
                "view_stakeholder",
                "view_reportcomment",
                "add_reportcomment",
                "view_rms_dashboard",
                "view_system_audit",
            ],

            # System Admin
            "RMS_SYS_ADMIN": self.get_all_rms_permissions(),
        }

        # Create groups and assign permissions
        for group_name, perm_codes in groups_to_permissions.items():

            group, created = Group.objects.get_or_create(name=group_name)

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created group {group_name}")
                )

            permissions = Permission.objects.filter(codename__in=perm_codes)

            group.permissions.set(permissions)

            self.stdout.write(
                self.style.SUCCESS(
                    f"{permissions.count()} permissions assigned to {group_name}"
                )
            )

        # Assign permissions to superusers
        User = get_user_model()
        superusers = User.objects.filter(is_superuser=True)

        all_permissions = self.get_all_rms_permission_objects()

        for user in superusers:

            group = Group.objects.get(name="RMS_SYS_ADMIN")
            user.groups.add(group)

            user.user_permissions.set(all_permissions)

            self.stdout.write(
                self.style.SUCCESS(
                    f"All RMS permissions assigned to superuser '{user.username}'"
                )
            )

        self.stdout.write(
            self.style.SUCCESS("RMS permissions and roles configured successfully")
        )

    def get_all_rms_permissions(self):

        models = [
            "financialyear",
            "stakeholder",
            "reporttype",
            "reportcategory",
            "report",
            "reportcomment",
            "reportsetting",
        ]

        perms = []

        for model in models:
            perms.extend(
                [
                    f"add_{model}",
                    f"view_{model}",
                    f"change_{model}",
                    f"delete_{model}",
                ]
            )

        perms.extend(
            [
                "submit_report",
                "download_report",
                "view_directory_reports",
                "view_institution_reports",
                "view_rms_dashboard",
                "manage_rms_settings",
                "view_system_audit",
                "manage_security_alerts",
            ]
        )

        return perms

    def get_all_rms_permission_objects(self):

        codenames = self.get_all_rms_permissions()

        return Permission.objects.filter(codename__in=codenames)