# generate_test_data.py
from django.core.management.base import BaseCommand
from django.db import IntegrityError
import factory
from microservices.ict_assets.factories import *
from microservices.ict_assets.models import (
    DisposalRecord, Warranty, SupportTicket, MaintenanceRecord,
    AssetAssignment, SoftwareInstallation, Peripheral, NetworkDevice,
    Computer, Asset, Software, SoftwareCategory, Location, Floor,
    Building, Supplier, Manufacturer, AssetType, AssetCategory,
    AssetCustodianHistory, AssetLocationHistory, DepreciationPolicy
)

from django.contrib.auth import get_user_model
User = get_user_model()

class Command(BaseCommand):
    help = 'Generate test data using Factory Boy'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=10,
            help='Number of users to create'
        )
        parser.add_argument(
            '--assets',
            type=int,
            default=50,
            help='Number of assets to create'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data first'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.clear_data()

        self.stdout.write('Generating test data with Factory Boy...')
        
        # Create or get existing users
        users = []
        existing_users = list(User.objects.filter(username__startswith='testuser'))
        
        if len(existing_users) >= options['users']:
            users = existing_users[:options['users']]
            self.stdout.write(f'Using {len(users)} existing users')
        else:
            users = existing_users
            needed = options['users'] - len(existing_users)
            for i in range(needed):
                try:
                    users.append(UserFactory.create())
                except IntegrityError:
                    self.stdout.write(self.style.WARNING(f'User creation failed, skipping...'))
            self.stdout.write(f'Created {len(users) - len(existing_users)} new users, using {len(existing_users)} existing users')

        # Create asset categories and types
        categories = AssetCategoryFactory.create_batch(5)
        asset_types = []
        for category in categories:
            asset_types.extend(AssetTypeFactory.create_batch(3, category=category))
        self.stdout.write(f'Created {len(asset_types)} asset types')

        # Create manufacturers and suppliers
        manufacturers = ManufacturerFactory.create_batch(6)
        suppliers = SupplierFactory.create_batch(3)
        self.stdout.write(f'Created {len(manufacturers)} manufacturers and {len(suppliers)} suppliers')

        # Create locations
        buildings = BuildingFactory.create_batch(3)
        floors = []
        for building in buildings:
            floors.extend(FloorFactory.create_batch(4, building=building))
        
        locations = []
        for floor in floors:
            locations.extend(LocationFactory.create_batch(3, building=floor.building, floor=floor))
        self.stdout.write(f'Created {len(locations)} locations')

        # Create software
        software_categories = SoftwareCategoryFactory.create_batch(4)
        software_list = []
        for category in software_categories:
            software_list.extend(SoftwareFactory.create_batch(5, category=category))
        self.stdout.write(f'Created {len(software_list)} software items')

        # Create assets
        assets = AssetFactory.create_batch(
            options['assets'],
            asset_type=factory.Iterator(asset_types),
            manufacturer=factory.Iterator(manufacturers),
            supplier=factory.Iterator(suppliers),
            location=factory.Iterator(locations),
            custodian=factory.Iterator(users)
        )
        self.stdout.write(f'Created {len(assets)} assets')

        # Create hardware specifics
        computers = ComputerFactory.create_batch(20, asset=factory.Iterator(assets[:20]))
        network_devices = NetworkDeviceFactory.create_batch(10, asset=factory.Iterator(assets[20:30]))
        peripherals = PeripheralFactory.create_batch(15, asset=factory.Iterator(assets[30:45]))
        self.stdout.write(f'Created {len(computers)} computers, {len(network_devices)} network devices, {len(peripherals)} peripherals')

        # Create software installations
        installations = []
        for computer in computers:
            installations.extend(SoftwareInstallationFactory.create_batch(
                3, 
                asset=computer.asset,
                software=factory.Iterator(software_list),
                installed_by=factory.Iterator(users)
            ))
        self.stdout.write(f'Created {len(installations)} software installations')

        # Create assignments
        assignments = AssetAssignmentFactory.create_batch(
            30, 
            asset=factory.Iterator(assets[:30]),
            assigned_to=factory.Iterator(users)
        )
        self.stdout.write(f'Created {len(assignments)} asset assignments')

        # Create maintenance records
        maintenance_records = MaintenanceRecordFactory.create_batch(
            25, 
            asset=factory.Iterator(assets[:25]),
            technician=factory.Iterator(users)
        )
        self.stdout.write(f'Created {len(maintenance_records)} maintenance records')

        # Create support tickets
        support_tickets = SupportTicketFactory.create_batch(
            20, 
            asset=factory.Iterator(assets[:20]),
            assigned_technician=factory.Iterator(users)
        )
        self.stdout.write(f'Created {len(support_tickets)} support tickets')

        # Create warranties
        warranties = WarrantyFactory.create_batch(40, asset=factory.Iterator(assets[:40]))
        self.stdout.write(f'Created {len(warranties)} warranties')
        
        # Create disposal records with approved_by
        disposal_records = []
        for i, asset in enumerate(assets[45:50]):
            try:
                disposal_records.append(DisposalRecordFactory.create(
                    asset=asset,
                    approved_by=users[i % len(users)]
                ))
            except IntegrityError:
                pass
        self.stdout.write(f'Created {len(disposal_records)} disposal records')
        
        # Create asset custodian history
        custodian_history = []
        for asset in assets[:30]:
            for i in range(2):
                try:
                    custodian_history.append(AssetCustodianHistoryFactory.create(
                        asset=asset,
                        custodian=users[i % len(users)]
                    ))
                except IntegrityError:
                    pass
        self.stdout.write(f'Created {len(custodian_history)} custodian history records')
        
        # Create asset location history
        location_history = []
        for asset in assets[:30]:
            for i in range(2):
                try:
                    location_history.append(AssetLocationHistoryFactory.create(
                        asset=asset,
                        location=locations[i % len(locations)]
                    ))
                except IntegrityError:
                    pass
        self.stdout.write(f'Created {len(location_history)} location history records')
        
        # Create depreciation policies
        depreciation_policies = DepreciationPolicyFactory.create_batch(
            len(categories),
            asset_category=factory.Iterator(categories)
        )
        self.stdout.write(f'Created {len(depreciation_policies)} depreciation policies')

        self.stdout.write(self.style.SUCCESS('Test data generation completed!'))

    def clear_data(self):
        self.stdout.write('Clearing existing test data...')
        
        models = [
            DisposalRecord, Warranty, SupportTicket, MaintenanceRecord,
            AssetAssignment, SoftwareInstallation, Peripheral, NetworkDevice,
            Computer, Asset, AssetCustodianHistory, AssetLocationHistory,
            Software, SoftwareCategory, Location, Floor, Building, 
            Supplier, Manufacturer, AssetType, AssetCategory, DepreciationPolicy
        ]
        
        for model in models:
            count, _ = model.objects.all().delete()
            self.stdout.write(f'Deleted {count} {model.__name__} records')
        
        user_count, _ = User.objects.filter(username__startswith='testuser').delete()
        self.stdout.write(f'Deleted {user_count} test users')
