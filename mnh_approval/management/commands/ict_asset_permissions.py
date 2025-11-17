# ict_assets_permissions.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, ContentType, Group
from django.contrib.auth import get_user_model
from django.apps import apps

class Command(BaseCommand):
    help = "Create ICT Assets permissions, assign them to groups, and give superusers all permissions"

    def handle(self, *args, **options):
        self.stdout.write("Processing ICT Assets permissions...")

        # Get all ICT Assets models
        ict_models = [
            'AssetCategory', 'AssetType', 'Asset', 'AssetAssignment',
            'Computer', 'NetworkDevice', 'Peripheral', 'Building', 
            'Floor', 'Location', 'Manufacturer', 'Supplier',
            'SoftwareCategory', 'Software', 'SoftwareInstallation',
            'MaintenanceRecord', 'SupportTicket', 'Warranty', 'DisposalRecord'
        ]

        # Create standard Django permissions for all ICT Assets models
        permissions_created = 0
        for model_name in ict_models:
            try:
                model = apps.get_model('ict_assets', model_name)
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
                self.stdout.write(self.style.WARNING(f"Model 'ict_assets.{model_name}' not found. Skipping."))

        self.stdout.write(f"Created {permissions_created} ICT Assets permissions")

        # Define custom permissions for ICT Assets
        custom_permissions_to_create = [
            # Bulk operations
            ("bulk_update_asset", "Can Bulk Update Assets"),
            ("bulk_delete_asset", "Can Bulk Delete Assets"),
            ("export_assets", "Can Export Assets"),
            
            # Dashboard and reporting
            ("view_dashboard", "Can View Dashboard"),
            ("view_reports", "Can View Reports"),
            ("generate_asset_report", "Can Generate Asset Reports"),
            
            # Lookup permissions
            ("view_assetcategory_lookup", "Can View Asset Category Lookup"),
            ("view_assettype_lookup", "Can View Asset Type Lookup"),
            ("view_location_lookup", "Can View Location Lookup"),
            ("view_manufacturer_lookup", "Can View Manufacturer Lookup"),
            ("view_softwarecategory_lookup", "Can View Software Category Lookup"),
            
            # Special operations
            ("assign_asset", "Can Assign Asset to User"),
            ("unassign_asset", "Can Unassign Asset from User"),
            ("schedule_maintenance", "Can Schedule Maintenance"),
            ("close_support_ticket", "Can Close Support Ticket"),
            ("approve_disposal", "Can Approve Asset Disposal"),
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

        self.stdout.write("Processing ICT Assets groups...")

        # Groups and permission mapping for ICT Assets
        groups_to_permissions = {
            "ICT_Superuser": self.get_all_ict_permissions(),
            "ICT_Admin": self.get_all_ict_permissions(),
            "ICT_Manager": [
                # Asset Management
                "add_assetcategory", "view_assetcategory", "change_assetcategory",
                "add_assettype", "view_assettype", "change_assettype",
                "add_asset", "view_asset", "change_asset",
                "add_assetassignment", "view_assetassignment", "change_assetassignment", "delete_assetassignment",
                
                # Hardware
                "add_computer", "view_computer", "change_computer",
                "add_networkdevice", "view_networkdevice", "change_networkdevice",
                "add_peripheral", "view_peripheral", "change_peripheral",
                
                # Location Management
                "add_building", "view_building", "change_building",
                "add_floor", "view_floor", "change_floor",
                "add_location", "view_location", "change_location",
                
                # Vendor Management
                "add_manufacturer", "view_manufacturer", "change_manufacturer",
                "add_supplier", "view_supplier", "change_supplier",
                
                # Software Management
                "add_softwarecategory", "view_softwarecategory", "change_softwarecategory",
                "add_software", "view_software", "change_software",
                "add_softwareinstallation", "view_softwareinstallation", "change_softwareinstallation", "delete_softwareinstallation",
                
                # Maintenance & Support
                "add_maintenancerecord", "view_maintenancerecord", "change_maintenancerecord", "delete_maintenancerecord",
                "add_supportticket", "view_supportticket", "change_supportticket", "delete_supportticket",
                
                # Lifecycle Management
                "add_warranty", "view_warranty", "change_warranty",
                "add_disposalrecord", "view_disposalrecord", "change_disposalrecord",
                
                # Special Operations
                "bulk_update_asset", "export_assets", "view_dashboard", "view_reports",
                "generate_asset_report", "view_assetcategory_lookup", "view_assettype_lookup",
                "view_location_lookup", "view_manufacturer_lookup", "view_softwarecategory_lookup",
                "assign_asset", "unassign_asset", "schedule_maintenance", "close_support_ticket", "approve_disposal"
            ],
            "ICT_Technician": [
                # Operational permissions
                "add_asset", "view_asset", "change_asset",
                "add_computer", "view_computer", "change_computer",
                "add_networkdevice", "view_networkdevice", "change_networkdevice",
                "add_peripheral", "view_peripheral", "change_peripheral",
                "add_softwareinstallation", "view_softwareinstallation", "change_softwareinstallation",
                "add_maintenancerecord", "view_maintenancerecord", "change_maintenancerecord",
                "add_supportticket", "view_supportticket", "change_support_ticket",
                "add_warranty", "view_warranty", "change_warranty",
                
                # View permissions for reference data
                "view_assetcategory", "view_assettype", "view_location", 
                "view_manufacturer", "view_softwarecategory", "view_software",
                
                # Special operations
                "view_dashboard", "export_assets", "view_assetcategory_lookup", 
                "view_assettype_lookup", "view_location_lookup", "view_manufacturer_lookup",
                "assign_asset", "unassign_asset", "schedule_maintenance", "close_support_ticket"
            ],
            "ICT_Auditor": [
                # Read-only access for auditing
                "view_assetcategory", "view_assettype", "view_asset", "view_assetassignment",
                "view_computer", "view_networkdevice", "view_peripheral",
                "view_software", "view_softwareinstallation", 
                "view_maintenancerecord", "view_warranty", "view_disposalrecord",
                "view_supportticket",
                
                # Reporting and export
                "view_dashboard", "view_reports", "generate_asset_report", "export_assets"
            ],
            "Department_User": [
                # Limited view access (department-based filtering in views)
                "view_asset", "view_computer", "view_softwareinstallation", 
                "view_supportticket", "view_assetassignment",
                
                # Basic operations
                "view_dashboard"
            ],
            "ReadOnly_User": [
                # General read-only access
                "view_assetcategory", "view_assettype", "view_asset", 
                "view_computer", "view_networkdevice", "view_peripheral",
                "view_software", "view_softwareinstallation", 
                "view_maintenancerecord", "view_supportticket",
                "view_dashboard", "export_assets"
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

        # Handle admin group: assign all ICT permissions
        admin_group, created = Group.objects.get_or_create(name="ICT_Admin")
        if created:
            self.stdout.write(self.style.SUCCESS("Created group 'ICT_Admin'"))

        all_ict_permissions = self.get_all_ict_permission_objects()
        admin_group.permissions.set(all_ict_permissions)
        self.stdout.write(self.style.SUCCESS(
            f"Assigned {len(all_ict_permissions)} ICT permissions to ICT_Admin group"
        ))

        # Assign all ICT permissions to superusers
        User = get_user_model()
        superusers = User.objects.filter(is_superuser=True)

        for user in superusers:
            # Add user to ICT_Superuser group
            ict_superuser_group = Group.objects.get(name="ICT_Superuser")
            user.groups.add(ict_superuser_group)
            
            # Also assign permissions directly (for redundancy)
            user.user_permissions.set(all_ict_permissions)
            
            self.stdout.write(self.style.SUCCESS(
                f"Assigned ALL ICT permissions to superuser '{user.username}'"
            ))

        self.stdout.write(self.style.SUCCESS("ICT Assets permissions, groups, and superusers synchronized successfully!"))

    def get_all_ict_permissions(self):
        """Get all ICT Assets permission codenames"""
        ict_models = [
            'assetcategory', 'assettype', 'asset', 'assetassignment',
            'computer', 'networkdevice', 'peripheral', 'building', 
            'floor', 'location', 'manufacturer', 'supplier',
            'softwarecategory', 'software', 'softwareinstallation',
            'maintenancerecord', 'supportticket', 'warranty', 'disposalrecord'
        ]
        
        all_permissions = []
        for model in ict_models:
            all_permissions.extend([f"add_{model}", f"view_{model}", f"change_{model}", f"delete_{model}"])
        
        # Add custom permissions
        custom_permissions = [
            "bulk_update_asset", "bulk_delete_asset", "export_assets",
            "view_dashboard", "view_reports", "generate_asset_report",
            "view_assetcategory_lookup", "view_assettype_lookup", "view_location_lookup",
            "view_manufacturer_lookup", "view_softwarecategory_lookup",
            "assign_asset", "unassign_asset", "schedule_maintenance", 
            "close_support_ticket", "approve_disposal"
        ]
        
        all_permissions.extend(custom_permissions)
        return all_permissions

    def get_all_ict_permission_objects(self):
        """Get all ICT Assets permission objects"""
        all_codenames = self.get_all_ict_permissions()
        return Permission.objects.filter(codename__in=all_codenames)
    