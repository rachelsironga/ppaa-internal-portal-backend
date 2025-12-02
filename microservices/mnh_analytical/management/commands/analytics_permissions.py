# analytics_permissions.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, ContentType, Group
from django.contrib.auth import get_user_model
from django.apps import apps


class Command(BaseCommand):
    help = "Create Analytics permissions, assign them to groups, and give superusers all permissions"

    def handle(self, *args, **options):
        self.stdout.write("Processing Analytics permissions...")

        # Get all Analytics models
        analytics_models = [
            'Block', 'Clinic', 'PaymentMode', 'Attendance', 'PatientAttendance'
        ]

        # Create standard Django permissions for all Analytics models
        permissions_created = 0
        for model_name in analytics_models:
            try:
                model = apps.get_model('mnh_analytical', model_name)
                content_type = ContentType.objects.get_for_model(model)
                
                # Create the four standard permissions for each model
                for action in ['add', 'view', 'change', 'delete']:
                    codename = f"{action}_{model_name.lower()}"
                    name = f"Can {action} {model_name}"
                    
                    perm, created = Permission.objects.get_or_create(
                        codename=codename,
                        content_type=content_type,
                        defaults={"name": name}
                    )
                    if created:
                        permissions_created += 1
                        self.stdout.write(self.style.SUCCESS(f"Created permission '{codename}'"))
                    
            except LookupError:
                self.stdout.write(self.style.WARNING(f"Model 'mnh_analytical.{model_name}' not found. Skipping."))

        self.stdout.write(f"Created {permissions_created} Analytics permissions")

        # Define custom permissions for Analytics
        custom_permissions_to_create = [
            # Dashboard and reporting
            ("view_analytics_dashboard", "Can View Analytics Dashboard"),
            ("view_analytics_reports", "Can View Analytics Reports"),
            ("generate_analytics_report", "Can Generate Analytics Reports"),
            ("export_analytics", "Can Export Analytics Data"),
            
            # Attendance specific operations
            ("upload_attendance", "Can Upload Attendance File"),
            ("process_attendance", "Can Process Attendance Data"),
            ("bulk_create_attendance", "Can Bulk Create Attendance Records"),
            ("view_attendance_summary", "Can View Attendance Summary"),
            
            # Patient attendance operations
            ("bulk_create_patientattendance", "Can Bulk Create Patient Attendance"),
            ("view_patient_trends", "Can View Patient Trends"),
            
            # Lookup permissions
            ("view_block_lookup", "Can View Block Lookup"),
            ("view_clinic_lookup", "Can View Clinic Lookup"),
            ("view_paymentmode_lookup", "Can View Payment Mode Lookup"),
            
            # Block/Clinic distribution
            ("view_block_clinic_distribution", "Can View Block Clinic Distribution"),
            ("view_payment_distribution", "Can View Payment Distribution"),
            
            # Import operations
            ("import_blocks", "Can Import Blocks"),
            ("import_clinics", "Can Import Clinics"),
            ("import_paymentmodes", "Can Import Payment Modes"),
        ]

        # Use a default ContentType for custom permissions
        default_ct = ContentType.objects.get(app_label="auth", model="permission")

        # Create custom permissions
        for codename, name in custom_permissions_to_create:
            perm, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=default_ct,
                defaults={"name": name}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created custom permission '{codename}'"))
            else:
                self.stdout.write(f"Custom permission '{codename}' already exists")

        self.stdout.write("Processing Analytics groups...")

        # Groups and permission mapping for Analytics
        groups_to_permissions = {
            "Analytics_Superuser": self.get_all_analytics_permissions(),
            "Analytics_Admin": self.get_all_analytics_permissions(),
            "Analytics_Manager": [
                # Block Management
                "add_block", "view_block", "change_block", "delete_block",
                
                # Clinic Management
                "add_clinic", "view_clinic", "change_clinic", "delete_clinic",
                
                # Payment Mode Management
                "add_paymentmode", "view_paymentmode", "change_paymentmode", "delete_paymentmode",
                
                # Attendance Management
                "add_attendance", "view_attendance", "change_attendance", "delete_attendance",
                
                # Patient Attendance Management
                "add_patientattendance", "view_patientattendance", "change_patientattendance", "delete_patientattendance",
                
                # Dashboard & Reports
                "view_analytics_dashboard", "view_analytics_reports", "generate_analytics_report", "export_analytics",
                
                # Attendance Operations
                "upload_attendance", "process_attendance", "bulk_create_attendance", "view_attendance_summary",
                
                # Patient Trends
                "bulk_create_patientattendance", "view_patient_trends",
                
                # Lookups
                "view_block_lookup", "view_clinic_lookup", "view_paymentmode_lookup",
                
                # Distributions
                "view_block_clinic_distribution", "view_payment_distribution",
                
                # Imports
                "import_blocks", "import_clinics", "import_paymentmodes",
            ],
            "Analytics_DataEntry": [
                # View reference data
                "view_block", "view_clinic", "view_paymentmode",
                
                # Attendance operations
                "add_attendance", "view_attendance", "change_attendance",
                "upload_attendance", "process_attendance",
                
                # Patient attendance operations
                "add_patientattendance", "view_patientattendance", "change_patientattendance",
                "bulk_create_patientattendance",
                
                # Lookups
                "view_block_lookup", "view_clinic_lookup", "view_paymentmode_lookup",
                
                # Basic dashboard
                "view_analytics_dashboard", "view_attendance_summary",
            ],
            "Analytics_Viewer": [
                # Read-only access
                "view_block", "view_clinic", "view_paymentmode",
                "view_attendance", "view_patientattendance",
                
                # Dashboard & Reports
                "view_analytics_dashboard", "view_analytics_reports", "view_attendance_summary",
                "view_patient_trends", "view_block_clinic_distribution", "view_payment_distribution",
                
                # Export
                "export_analytics", "generate_analytics_report",
                
                # Lookups
                "view_block_lookup", "view_clinic_lookup", "view_paymentmode_lookup",
            ],
            "Analytics_Reporter": [
                # View all data
                "view_block", "view_clinic", "view_paymentmode",
                "view_attendance", "view_patientattendance",
                
                # Full reporting access
                "view_analytics_dashboard", "view_analytics_reports", "generate_analytics_report",
                "export_analytics", "view_attendance_summary", "view_patient_trends",
                "view_block_clinic_distribution", "view_payment_distribution",
                
                # Lookups
                "view_block_lookup", "view_clinic_lookup", "view_paymentmode_lookup",
            ],
        }

        # Assign permissions to groups
        for group_name, perm_codes in groups_to_permissions.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created group '{group_name}'"))
            else:
                self.stdout.write(f"Group exists: {group_name}")

            # Clear existing permissions
            group.permissions.clear()

            assigned_count = 0
            for code in perm_codes:
                try:
                    permission = Permission.objects.get(codename=code)
                    group.permissions.add(permission)
                    assigned_count += 1
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"Permission '{code}' does not exist. Skipped for group '{group_name}'."
                    ))

            self.stdout.write(self.style.SUCCESS(
                f"Assigned {assigned_count} permissions to group '{group_name}'"
            ))

        # Handle admin group: assign all Analytics permissions
        admin_group, created = Group.objects.get_or_create(name="Analytics_Admin")
        if created:
            self.stdout.write(self.style.SUCCESS("Created group 'Analytics_Admin'"))

        all_analytics_permissions = self.get_all_analytics_permission_objects()
        admin_group.permissions.set(all_analytics_permissions)
        self.stdout.write(self.style.SUCCESS(
            f"Assigned {len(all_analytics_permissions)} Analytics permissions to Analytics_Admin group"
        ))

        # Assign all Analytics permissions to superusers
        User = get_user_model()
        superusers = User.objects.filter(is_superuser=True)

        for user in superusers:
            # Add user to Analytics_Superuser group
            analytics_superuser_group = Group.objects.get(name="Analytics_Superuser")
            user.groups.add(analytics_superuser_group)
            
            # Also assign permissions directly (for redundancy)
            for perm in all_analytics_permissions:
                user.user_permissions.add(perm)
            
            self.stdout.write(self.style.SUCCESS(
                f"Assigned ALL Analytics permissions to superuser '{user.username}'"
            ))

        self.stdout.write(self.style.SUCCESS("Analytics permissions, groups, and superusers synchronized successfully!"))

    def get_all_analytics_permissions(self):
        """Get all Analytics permission codenames"""
        analytics_models = [
            'block', 'clinic', 'paymentmode', 'attendance', 'patientattendance'
        ]
        
        all_permissions = []
        for model in analytics_models:
            all_permissions.extend([f"add_{model}", f"view_{model}", f"change_{model}", f"delete_{model}"])
        
        # Add custom permissions
        custom_permissions = [
            # Dashboard and reporting
            "view_analytics_dashboard", "view_analytics_reports", 
            "generate_analytics_report", "export_analytics",
            
            # Attendance specific operations
            "upload_attendance", "process_attendance", 
            "bulk_create_attendance", "view_attendance_summary",
            
            # Patient attendance operations
            "bulk_create_patientattendance", "view_patient_trends",
            
            # Lookup permissions
            "view_block_lookup", "view_clinic_lookup", "view_paymentmode_lookup",
            
            # Block/Clinic distribution
            "view_block_clinic_distribution", "view_payment_distribution",
            
            # Import operations
            "import_blocks", "import_clinics", "import_paymentmodes",
        ]
        
        all_permissions.extend(custom_permissions)
        return all_permissions

    def get_all_analytics_permission_objects(self):
        """Get all Analytics permission objects"""
        all_codenames = self.get_all_analytics_permissions()
        return Permission.objects.filter(codename__in=all_codenames)
