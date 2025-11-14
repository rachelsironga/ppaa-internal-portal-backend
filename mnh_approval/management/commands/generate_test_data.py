# generate_test_data.py
from django.core.management.base import BaseCommand
from microservices.ict_assets.factories import *
from microservices.ict_assets.models import (
    DisposalRecord, Warranty, SupportTicket, MaintenanceRecord,
    AssetAssignment, SoftwareInstallation, Peripheral, NetworkDevice,
    Computer, Asset, Software, SoftwareCategory, Location, Floor,
    Building, Supplier, Manufacturer, AssetType, AssetCategory
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
        
        # Create users
        users = UserFactory.create_batch(options['users'])
        self.stdout.write(f'Created {len(users)} users')

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
            location=factory.Iterator(locations)
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
                software=factory.Iterator(software_list)
            ))
        self.stdout.write(f'Created {len(installations)} software installations')

        # Create assignments
        assignments = AssetAssignmentFactory.create_batch(30, asset=factory.Iterator(assets[:30]))
        self.stdout.write(f'Created {len(assignments)} asset assignments')

        # Create maintenance records
        maintenance_records = MaintenanceRecordFactory.create_batch(25, asset=factory.Iterator(assets[:25]))
        self.stdout.write(f'Created {len(maintenance_records)} maintenance records')

        # Create support tickets
        support_tickets = SupportTicketFactory.create_batch(20, asset=factory.Iterator(assets[:20]))
        self.stdout.write(f'Created {len(support_tickets)} support tickets')

        # Create warranties
        warranties = WarrantyFactory.create_batch(40, asset=factory.Iterator(assets[:40]))
        self.stdout.write(f'Created {len(warranties)} warranties')
    def clear_data(self):
        models = [
            DisposalRecord, Warranty, SupportTicket, MaintenanceRecord,
            AssetAssignment, SoftwareInstallation, Peripheral, NetworkDevice,
            Computer, Asset, Software, SoftwareCategory, Location, Floor,
            Building, Supplier, Manufacturer, AssetType, AssetCategory
        ]
        
        for model in models:
            count, _ = model.objects.all().delete()
            self.stdout.write(f'Deleted {count} {model.__name__} records')
        
        User.objects.filter(username__startswith='testuser').delete()
        
        for model in models:
            count, _ = model.objects.all().delete()
            self.stdout.write(f'Deleted {count} {model.__name__} records')
        
        User.objects.filter(username__startswith='testuser').delete()

        