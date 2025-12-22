# training_permissions.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, ContentType, Group
from django.contrib.auth import get_user_model
from django.apps import apps


class Command(BaseCommand):
    help = "Create Training permissions, assign them to groups, and give superusers all permissions"

    def handle(self, *args, **options):
        self.stdout.write("Processing Training permissions...")

        # Get all Training models
        training_models = [
            'Student', 'Affiliation', 'Application', 'DepartmentAllocation',
            'Supervisor', 'Institution', 'MOU', 'TrainingBatch'
        ]

        # Create standard Django permissions for all Training models
        permissions_created = 0
        for model_name in training_models:
            try:
                model = apps.get_model('mnh_training', model_name)
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
                self.stdout.write(self.style.WARNING(f"Model 'mnh_training.{model_name}' not found. Skipping."))

        self.stdout.write(f"Created {permissions_created} Training permissions")

        # Define custom permissions for Training
        custom_permissions_to_create = [
            # Student Management
            ("bulk_enroll_students", "Can Bulk Enroll Students"),
            ("bulk_update_students", "Can Bulk Update Students"),
            ("export_students", "Can Export Student Records"),
            
            # Application Management
            ("approve_application", "Can Approve Training Application"),
            ("reject_application", "Can Reject Training Application"),
            ("bulk_approve_applications", "Can Bulk Approve Applications"),
            ("export_applications", "Can Export Applications"),
            
            # Training Batch Management
            ("create_training_batch", "Can Create Training Batch"),
            ("finalize_training_batch", "Can Finalize Training Batch"),
            ("cancel_training_batch", "Can Cancel Training Batch"),
            
            # MOU Management
            ("create_mou", "Can Create MOU"),
            ("renew_mou", "Can Renew MOU"),
            ("track_mou_expiry", "Can Track MOU Expiration"),
            
            # Institution Management
            ("manage_institutions", "Can Manage Institutions"),
            ("create_institution", "Can Create Institution"),
            
            # Allocation & Scheduling
            ("allocate_departments", "Can Allocate Departments"),
            ("assign_supervisors", "Can Assign Supervisors"),
            
            # Reporting & Analytics
            ("view_training_dashboard", "Can View Training Dashboard"),
            ("view_training_reports", "Can View Training Reports"),
            ("generate_training_report", "Can Generate Training Reports"),
            ("export_training_data", "Can Export Training Data"),
            
            # Lookup Permissions
            ("view_student_lookup", "Can View Student Lookup"),
            ("view_institution_lookup", "Can View Institution Lookup"),
            ("view_mou_lookup", "Can View MOU Lookup"),
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

        self.stdout.write("Processing Training groups...")

        # Groups and permission mapping for Training
        groups_to_permissions = {
            "Training_Head": [
                # Full access to all training operations
                "add_student", "view_student", "change_student", "delete_student",
                "add_affiliation", "view_affiliation", "change_affiliation", "delete_affiliation",
                "add_application", "view_application", "change_application", "delete_application",
                "add_departmentallocation", "view_departmentallocation", "change_departmentallocation", "delete_departmentallocation",
                "add_supervisor", "view_supervisor", "change_supervisor", "delete_supervisor",
                "add_institution", "view_institution", "change_institution", "delete_institution",
                "add_mou", "view_mou", "change_mou", "delete_mou",
                "add_trainingbatch", "view_trainingbatch", "change_trainingbatch", "delete_trainingbatch",
                
                # Bulk operations
                "bulk_enroll_students", "bulk_update_students", "bulk_approve_applications",
                
                # Application management
                "approve_application", "reject_application", "bulk_approve_applications",
                
                # Training batch operations
                "create_training_batch", "finalize_training_batch", "cancel_training_batch",
                
                # MOU management
                "create_mou", "renew_mou", "track_mou_expiry",
                
                # Institution management
                "manage_institutions", "create_institution",
                
                # Allocation & scheduling
                "allocate_departments", "assign_supervisors",
                
                # Reporting and analytics
                "view_training_dashboard", "view_training_reports", "generate_training_report",
                "export_students", "export_applications", "export_training_data",
                
                # Lookup permissions
                "view_student_lookup", "view_institution_lookup", "view_mou_lookup",
            ],
            "Head_of_Training_Secretary": [
                # Full view and edit access to most operations
                "view_student", "change_student",
                "view_affiliation", "change_affiliation",
                "add_application", "view_application", "change_application",
                "add_departmentallocation", "view_departmentallocation", "change_departmentallocation",
                "view_supervisor", "change_supervisor",
                "view_institution", "change_institution",
                "add_mou", "view_mou", "change_mou",
                "add_trainingbatch", "view_trainingbatch", "change_trainingbatch",
                
                # Application management
                "approve_application", "reject_application",
                
                # Training batch operations
                "create_training_batch", "finalize_training_batch",
                
                # MOU management
                "create_mou", "renew_mou", "track_mou_expiry",
                
                # Allocation & scheduling
                "allocate_departments", "assign_supervisors",
                
                # Reporting
                "view_training_dashboard", "view_training_reports", "generate_training_report",
                "export_students", "export_applications",
                
                # Lookup permissions
                "view_student_lookup", "view_institution_lookup", "view_mou_lookup",
            ],
            "Training_Coordinator": [
                # View and limited edit access for operational tasks
                "view_student", "add_student",
                "view_affiliation", "add_affiliation",
                "add_application", "view_application", "change_application",
                "view_departmentallocation", "add_departmentallocation",
                "view_supervisor", "add_supervisor",
                "view_institution",
                "view_mou",
                "view_trainingbatch", "change_trainingbatch",
                
                # Limited application management
                "view_training_dashboard", "view_training_reports",
                "export_training_data",
                
                # Lookup permissions
                "view_student_lookup", "view_institution_lookup", "view_mou_lookup",
            ],
            "Training_Auditor": [
                # Read-only access for auditing
                "view_student", "view_affiliation", "view_application",
                "view_departmentallocation", "view_supervisor", "view_institution",
                "view_mou", "view_trainingbatch",
                
                # Reporting and export
                "view_training_dashboard", "view_training_reports", "generate_training_report",
                "export_students", "export_applications", "export_training_data",
            ],
            "Department_Training_User": [
                # Limited access for department-based operations
                "view_student", "view_application", "view_departmentallocation",
                "view_supervisor", "view_trainingbatch",
                
                # Limited operations
                "view_training_dashboard",
                
                # Lookup permissions
                "view_student_lookup",
            ],
            "Training_ReadOnly_User": [
                # General read-only access
                "view_student", "view_affiliation", "view_application",
                "view_departmentallocation", "view_supervisor", "view_institution",
                "view_mou", "view_trainingbatch",
                
                # Reporting access
                "view_training_dashboard", "export_training_data",
            ]
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

        # Handle superusers: assign all Training permissions
        all_training_permissions = self.get_all_training_permission_objects()
        User = get_user_model()
        superusers = User.objects.filter(is_superuser=True)

        for user in superusers:
            # Add user to Training_Superuser group
            training_superuser_group, created = Group.objects.get_or_create(name="Training_Superuser")
            if created:
                self.stdout.write(self.style.SUCCESS("Created group 'Training_Superuser'"))
                training_superuser_group.permissions.set(all_training_permissions)

            user.groups.add(training_superuser_group)
            
            # Also assign permissions directly (for redundancy)
            user.user_permissions.set(all_training_permissions)
            
            self.stdout.write(self.style.SUCCESS(
                f"Assigned ALL Training permissions to superuser '{user.username}'"
            ))

        self.stdout.write(self.style.SUCCESS("Training permissions, groups, and superusers synchronized successfully!"))

    def get_all_training_permissions(self):
        """Get all Training permission codenames"""
        training_models = [
            'student', 'affiliation', 'application', 'departmentallocation',
            'supervisor', 'institution', 'mou', 'trainingbatch'
        ]
        
        all_permissions = []
        for model in training_models:
            all_permissions.extend([f"add_{model}", f"view_{model}", f"change_{model}", f"delete_{model}"])
        
        # Add custom permissions
        custom_permissions = [
            "bulk_enroll_students", "bulk_update_students", "export_students",
            "approve_application", "reject_application", "bulk_approve_applications", "export_applications",
            "create_training_batch", "finalize_training_batch", "cancel_training_batch",
            "create_mou", "renew_mou", "track_mou_expiry",
            "manage_institutions", "create_institution",
            "allocate_departments", "assign_supervisors",
            "view_training_dashboard", "view_training_reports", "generate_training_report", "export_training_data",
            "view_student_lookup", "view_institution_lookup", "view_mou_lookup",
        ]
        
        all_permissions.extend(custom_permissions)
        return all_permissions

    def get_all_training_permission_objects(self):
        """Get all Training permission objects"""
        all_codenames = self.get_all_training_permissions()
        return Permission.objects.filter(codename__in=all_codenames)
