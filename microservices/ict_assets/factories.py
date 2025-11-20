# ict_assets/factories.py
import factory
from django.contrib.auth.models import Permission
from django.utils import timezone
from datetime import timedelta
import random
from faker import Faker

from mnh_auth.models import User
from .models import *

fake = Faker()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f'testuser{n}')
    pf_number = factory.Sequence(lambda n: f'PF{n:05d}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    middle_name = factory.Faker('last_name')
    check_number = factory.LazyFunction(lambda: f'CHK{fake.random_number(digits=6)}')
    office_location = factory.Faker('city')
    status = 'ACTIVE'
    account_type = 'LONG_TERM'
    is_active = True
    is_staff = True
    phone_number = factory.LazyFunction(lambda: fake.phone_number()[:15])
    alternative_contact = factory.LazyFunction(lambda: fake.phone_number()[:15])
    account_number = factory.LazyFunction(lambda: fake.bban())

    @factory.lazy_attribute
    def dob(self):
        return fake.date_of_birth(minimum_age=25, maximum_age=60)

    @factory.lazy_attribute
    def sex(self):
        return random.choice(['Male', 'Female'])

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to handle custom UserManager with pf_number requirement"""
        # Check if we should create a new user or use existing one
        existing_users_count = User.objects.count()
        
        # If there are already 5 or more users, use a random existing user
        if existing_users_count >= 5:
            return random.choice(User.objects.all())
        
        # Otherwise, create a new user
        password = kwargs.pop('password', 'password123')
        
        # Ensure required fields are present
        if 'pf_number' not in kwargs:
            # Generate unique PF number
            existing_pf_numbers = set(User.objects.values_list('pf_number', flat=True))
            pf_number = f'PF{fake.random_number(digits=6)}'
            while pf_number in existing_pf_numbers:
                pf_number = f'PF{fake.random_number(digits=6)}'
            kwargs['pf_number'] = pf_number
        
        if 'first_name' not in kwargs:
            kwargs['first_name'] = fake.first_name()
            
        if 'last_name' not in kwargs:
            kwargs['last_name'] = fake.last_name()

        # Generate unique username
        if 'username' not in kwargs:
            base_username = f'testuser{random.randint(1000, 9999)}'
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f'{base_username}_{counter}'
                counter += 1
            kwargs['username'] = username
        
        # Use the custom UserManager
        manager = cls._get_manager(model_class)
        
        # Create user using the custom manager
        user = manager.create_user(
            username=kwargs.get('username'),
            email=kwargs.get('email'),
            pf_number=kwargs.get('pf_number'),
            first_name=kwargs.get('first_name'),
            last_name=kwargs.get('last_name'),
            password=password,
            **{k: v for k, v in kwargs.items() if k not in ['username', 'email', 'pf_number', 'first_name', 'last_name', 'password']}
        )
        
        return user

    @classmethod
    def get_or_create_user(cls, **kwargs):
        """Helper method to get existing user or create new one based on count"""
        existing_users_count = User.objects.count()
        
        if existing_users_count >= 5:
            # Return a random existing user
            return random.choice(User.objects.all())
        else:
            # Create a new user
            return cls(**kwargs)
    
# SuperUser factory for admin users
class SuperUserFactory(UserFactory):
    username = factory.Sequence(lambda n: f'admin{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@company.com')
    first_name = 'Admin'
    last_name = 'User'
    is_staff = True
    is_superuser = True
    account_type = 'SUPER_USER'

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to create superuser"""
        # Check if we should create a new superuser or use existing one
        existing_superusers_count = User.objects.filter(is_superuser=True).count()
        existing_users_count = User.objects.count()
        
        # If there are already 5 or more users, use an existing superuser if available, otherwise regular user
        if existing_users_count >= 5:
            superusers = User.objects.filter(is_superuser=True)
            if superusers.exists():
                return random.choice(superusers)
            else:
                # Fall back to any existing user
                return random.choice(User.objects.all())
        
        # Otherwise, create a new superuser
        password = kwargs.pop('password', 'admin123')
        
        manager = cls._get_manager(model_class)
        user = manager.create_superuser(
            username=kwargs.get('username'),
            email=kwargs.get('email'),
            pf_number=kwargs.get('pf_number'),
            first_name=kwargs.get('first_name'),
            last_name=kwargs.get('last_name'),
            password=password,
            **{k: v for k, v in kwargs.items() if k not in ['username', 'email', 'pf_number', 'first_name', 'last_name', 'password']}
        )
        
        return user

# Rest of your factories remain the same but updated to use the new UserFactory
class AssetCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AssetCategory
    
    name = factory.Sequence(lambda n: f'Asset Category {n}')
    description = factory.Faker('sentence')
    created_by = factory.SubFactory(UserFactory)

    @factory.lazy_attribute
    def parent_category(self):
        if random.random() < 0.3 and AssetCategory.objects.exists():
            return random.choice(AssetCategory.objects.all())
        return None

class AssetTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AssetType
    
    name = factory.Sequence(lambda n: f'Asset Type {n}')
    # description = factory.Faker('sentence')
    category = factory.SubFactory(AssetCategoryFactory)
    specifications_template = factory.Dict({
        'default_specs': {
            'ram': '8GB',
            'storage': '256GB SSD',
            'processor': 'Intel Core i5'
        }
    })
    created_by = factory.SubFactory(UserFactory)

class ManufacturerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Manufacturer
    
    name = factory.Sequence(lambda n: f'Manufacturer {n}')
    contact_email = factory.LazyAttribute(lambda obj: f'contact@{obj.name.lower().replace(" ", "")}.com')
    support_phone = factory.LazyFunction(lambda: fake.numerify(text='+255-###-######'))  # Max 20 chars
    website = factory.LazyAttribute(lambda obj: f'www.{obj.name.lower().replace(" ", "")}.com')
    created_by = factory.SubFactory(UserFactory)

class SupplierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Supplier
    
    name = factory.Sequence(lambda n: f'Supplier {n}')
    contact_person = factory.Faker('name')
    email = factory.LazyAttribute(lambda obj: f'info@{obj.name.lower().replace(" ", "")}.com')
    phone = factory.LazyFunction(lambda: fake.numerify(text='+255-###-######'))  # Max 20 chars
    address = factory.Faker('address')
    created_by = factory.SubFactory(UserFactory)

class BuildingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Building
    
    name = factory.Sequence(lambda n: f'Building {n}')
    code = factory.Sequence(lambda n: f'B{n:02d}')
    address = factory.Faker('address')
    created_by = factory.SubFactory(UserFactory)

class FloorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Floor
    
    building = factory.SubFactory(BuildingFactory)
    number = factory.Sequence(lambda n: n + 1)
    name = factory.LazyAttribute(lambda obj: f'Floor {obj.number}')
    created_by = factory.SubFactory(UserFactory)

class LocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Location
    
    name = factory.Sequence(lambda n: f'Location {n}')
    building = factory.SubFactory(BuildingFactory)
    floor = factory.SubFactory(FloorFactory)
    room = factory.Sequence(lambda n: f'{random.randint(1, 10)}{n:02d}')
    address = factory.LazyAttribute(lambda obj: f'{obj.building.address}, Room {obj.room}')
    created_by = factory.SubFactory(UserFactory)

    @factory.lazy_attribute
    def parent(self):
        if random.random() < 0.2 and Location.objects.exists():
            return random.choice(Location.objects.all())
        return None
    
class SoftwareCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SoftwareCategory
    
    name = factory.Sequence(lambda n: f'Software Category {n}')
    description = factory.Faker('sentence')
    created_by = factory.SubFactory(UserFactory)

class SoftwareFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Software
    
    # Basic Information
    asset_tag = factory.LazyFunction(lambda: f'SW-{fake.unique.random_number(digits=4, fix_len=True)}')
    software_name = factory.Sequence(lambda n: f'Software {n}')
    version = factory.Faker('numerify', text='#.#.#')
    publisher = factory.Faker('company')
    software_type = factory.Iterator(['application', 'operating_system', 'utility', 'development_tool', 'database', 'security'])
    platform = factory.Iterator(['windows', 'linux', 'macos', 'web', 'cross_platform'])
    
    # Legacy field
    category = factory.SubFactory(SoftwareCategoryFactory)
    
    # Asset Management
    asset_type = factory.SubFactory(AssetTypeFactory)
    status = factory.Iterator(['active', 'inactive', 'operational', 'retired'])
    condition = factory.Iterator(['new', 'excellent', 'good', 'fair'])
    
    # License Information
    license_type = factory.Iterator(['perpetual', 'subscription', 'open_source', 'trial', 'enterprise', 'volume'])
    total_licenses = factory.LazyFunction(lambda: random.choice([1, 5, 10, 25, 50, 100]))
    used_licenses = factory.LazyAttribute(lambda obj: random.randint(0, obj.total_licenses))
    license_expiry = factory.LazyAttribute(lambda obj: fake.date_between(start_date='today', end_date='+2y') if obj.license_type in ['subscription', 'trial'] else None)
    
    # Financial Information
    purchase_cost = factory.Faker('random_number', digits=3, fix_len=True)
    purchase_date = factory.Faker('date_between', start_date='-2y', end_date='today')
    supplier = factory.SubFactory(SupplierFactory)
    
    # Assignment & Location
    custodian = factory.LazyAttribute(lambda obj: UserFactory() if random.random() < 0.6 else None)
    location = factory.LazyAttribute(lambda obj: LocationFactory() if random.random() < 0.7 else None)
    
    # Support & Documentation
    support_url = factory.LazyAttribute(lambda obj: f'https://support.{obj.publisher.lower().replace(" ", "")}.com' if random.random() < 0.5 else None)
    documentation_url = factory.LazyAttribute(lambda obj: f'https://docs.{obj.publisher.lower().replace(" ", "")}.com' if random.random() < 0.5 else None)
    
    created_by = factory.SubFactory(UserFactory)

class AssetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Asset
    
    asset_tag = factory.LazyFunction(lambda: f'ASSET-{fake.unique.random_number(digits=4, fix_len=True)}')
    serial_number = factory.LazyFunction(lambda: f'SN-{fake.unique.uuid4()[:8].upper()}')
    asset_type = factory.SubFactory(AssetTypeFactory)
    manufacturer = factory.SubFactory(ManufacturerFactory)
    model = factory.LazyAttribute(lambda obj: f'{obj.manufacturer.name} Model {random.randint(100, 999)}')
    purchase_date = factory.Faker('date_between', start_date='-3y', end_date='today')
    purchase_cost = factory.Faker('random_number', digits=4, fix_len=True)
    supplier = factory.SubFactory(SupplierFactory)
    status = factory.Iterator(['active', 'inactive', 'maintenance', 'retired'])
    condition = factory.Iterator(['excellent', 'good', 'fair', 'poor'])
    location = factory.SubFactory(LocationFactory)
    is_active = True
    last_audit_date = factory.LazyAttribute(lambda obj: fake.date_between(
        start_date=obj.purchase_date, 
        end_date='today'
    ))
    created_by = factory.SubFactory(UserFactory)

    @factory.lazy_attribute
    def custodian(self):
        if random.random() < 0.7:
            return UserFactory()
        return None

    @factory.lazy_attribute
    def warranty_expiry(self):
        if random.random() < 0.8:
            return fake.date_between(start_date='today', end_date='+2y')
        return None

    @factory.lazy_attribute
    def barcode(self):
        if random.random() < 0.5:
            return f'BC-{fake.uuid4()[:8].upper()}'
        return ''

    @factory.lazy_attribute
    def notes(self):
        if random.random() < 0.3:
            return fake.paragraph()
        return ''

class ComputerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Computer
    
    asset = factory.SubFactory(AssetFactory)
    hostname = factory.LazyAttribute(lambda obj: f'PC-{obj.asset.asset_tag}')
    fqdn = factory.LazyAttribute(lambda obj: f'{obj.hostname}.company.local')
    processor = factory.Iterator(['Intel Core i5', 'Intel Core i7', 'Intel Core i9', 'AMD Ryzen 5', 'AMD Ryzen 7'])
    cpu_cores = factory.Iterator([4, 6, 8, 12, 16])
    cpu_speed_ghz = factory.LazyFunction(lambda: round(random.uniform(2.0, 4.5), 1))
    cpu_architecture = factory.Iterator(['x64', 'x86'])
    ram_gb = factory.Iterator([8, 16, 32, 64])
    storage_type = factory.Iterator(['SSD', 'HDD', 'NVMe'])
    storage_gb = factory.Iterator([256, 512, 1024, 2048])
    disks = factory.LazyFunction(lambda: [{"type": "SSD", "size_gb": random.choice([256, 512, 1024])}])
    operating_system = factory.Iterator(['Windows 10', 'Windows 11', 'Ubuntu 22.04', 'macOS Monterey'])
    os_version = factory.Faker('numerify', text='#.#.#')
    mac_addresses = factory.LazyFunction(lambda: [fake.mac_address()])
    ip_addresses = factory.LazyFunction(lambda: [fake.ipv4()])
    management_ip = factory.LazyFunction(lambda: fake.ipv4())
    gpu = factory.Iterator(['Integrated', 'NVIDIA GTX 1660', 'AMD Radeon RX 580', 'NVIDIA RTX 3060'])
    virtual = False
    created_by = factory.SubFactory(UserFactory)

    @factory.lazy_attribute
    def bios_version(self):
        return f"{random.choice(['A', 'B', 'C'])}{random.randint(1, 10)}.{random.randint(0, 9)}"

class NetworkDeviceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NetworkDevice
    
    asset = factory.SubFactory(AssetFactory)
    device_type = factory.Iterator(['Switch', 'Router', 'Firewall', 'Access Point'])
    ip_address = factory.LazyFunction(lambda: fake.ipv4())
    mac_address = factory.LazyFunction(lambda: fake.mac_address())
    ports = factory.Iterator([8, 16, 24, 48])
    created_by = factory.SubFactory(UserFactory)

class PeripheralFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Peripheral
    
    asset = factory.SubFactory(AssetFactory)
    peripheral_type = factory.Iterator(['Monitor', 'Printer', 'Scanner', 'Keyboard', 'Mouse'])
    connection_type = factory.Iterator(['USB', 'HDMI', 'Wireless', 'Ethernet', 'Bluetooth'])
    created_by = factory.SubFactory(UserFactory)

class SoftwareInstallationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SoftwareInstallation
    
    # Core Relationships
    software = factory.SubFactory(SoftwareFactory)
    asset = factory.SubFactory(AssetFactory)
    
    # Installation Details
    installation_date = factory.LazyAttribute(lambda obj: fake.date_between(
        start_date=obj.asset.purchase_date,
        end_date='today'
    ) if obj.asset.purchase_date else fake.date_between(start_date='-2y', end_date='today'))
    installed_by = factory.SubFactory(UserFactory)
    installation_path = factory.LazyAttribute(lambda obj: f'C:\\Program Files\\{obj.software.software_name}' if random.random() < 0.7 else None)
    version_installed = factory.LazyAttribute(lambda obj: obj.software.version)
    
    # License Information
    license_key_used = factory.LazyFunction(lambda: fake.uuid4() if random.random() > 0.5 else '')
    
    # Status & Verification
    status = factory.Iterator(['active', 'inactive', 'pending', 'uninstalled'])
    is_compliant = factory.LazyFunction(lambda: random.choice([True, False]))
    
    # Assignment
    assigned_to = factory.LazyAttribute(lambda obj: obj.asset.custodian if obj.asset.custodian else UserFactory() if random.random() < 0.6 else None)
    
    created_by = factory.SubFactory(UserFactory)
    
    @factory.lazy_attribute
    def last_verified_date(self):
        if self.status == 'active' and random.random() < 0.4:
            return fake.date_between(start_date=self.installation_date, end_date='today')
        return None
    
    @factory.lazy_attribute
    def verified_by(self):
        if self.last_verified_date:
            return UserFactory()
        return None

class AssetAssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AssetAssignment
    
    asset = factory.SubFactory(AssetFactory)
    assigned_to = factory.SubFactory(UserFactory)
    assigned_date = factory.LazyAttribute(lambda obj: fake.date_between(
        start_date=obj.asset.purchase_date,
        end_date='today'
    ))
    condition_on_assignment = factory.LazyAttribute(lambda obj: obj.asset.condition)
    created_by = factory.SubFactory(UserFactory)

    @factory.lazy_attribute
    def return_date(self):
        if random.random() < 0.4:
            return fake.date_between(start_date='today', end_date='+1y')
        return None

class MaintenanceRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MaintenanceRecord
    
    asset = factory.SubFactory(AssetFactory)
    maintenance_type = factory.Iterator(['Preventive', 'Corrective', 'Emergency', 'Routine'])
    status = factory.Iterator(['scheduled', 'in_progress', 'completed', 'cancelled'])
    cost = factory.LazyFunction(lambda: random.randint(50, 1000))
    description = factory.LazyAttribute(lambda obj: f'{obj.maintenance_type} maintenance for {obj.asset.asset_tag}')
    technician = factory.Faker('name')
    created_by = factory.SubFactory(UserFactory)

    @factory.lazy_attribute
    def scheduled_date(self):
        from django.utils import timezone
        today = timezone.now().date()
        
        if self.status == 'completed':
            # For completed records, ensure scheduled_date is in the past
            return fake.date_between(start_date='-60d', end_date=today)
        else:
            # For other statuses, can be past or future
            return fake.date_between(start_date='-30d', end_date='+30d')

    @factory.lazy_attribute
    def completed_date(self):
        if self.status == 'completed':
            # Generate completed date between scheduled_date and today
            from django.utils import timezone
            today = timezone.now().date()
            return fake.date_between(start_date=self.scheduled_date, end_date=today)
        return None
    
class SupportTicketFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SupportTicket
    
    ticket_id = factory.LazyFunction(lambda: f'TKT-{timezone.now().year}{fake.unique.random_number(digits=4, fix_len=True)}')
    asset = factory.SubFactory(AssetFactory)
    issue_description = factory.Faker('paragraph')
    priority = factory.Iterator(['low', 'medium', 'high', 'critical'])
    status = factory.Iterator(['open', 'in_progress', 'resolved', 'closed'])
    created_by = factory.SubFactory(UserFactory)

    @factory.lazy_attribute
    def created_date(self):
        naive_date = fake.date_between(start_date='-60d', end_date='today')
        return timezone.make_aware(timezone.datetime.combine(naive_date, timezone.datetime.min.time()))
    
    @factory.lazy_attribute
    def assigned_technician(self):
        return UserFactory()

    @factory.lazy_attribute
    def resolved_date(self):
        if self.status in ['resolved', 'closed']:
            naive_date = fake.date_between(start_date=self.created_date.date(), end_date='today')
            return timezone.make_aware(timezone.datetime.combine(naive_date, timezone.datetime.min.time()))
        return None

class WarrantyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Warranty
    
    asset = factory.SubFactory(AssetFactory)
    start_date = factory.LazyAttribute(lambda obj: obj.asset.purchase_date)
    end_date = factory.LazyAttribute(lambda obj: fake.date_between(
        start_date=obj.start_date,
        end_date=obj.start_date + timedelta(days=1095)  # 3 years
    ))
    provider = factory.Iterator(['Dell Warranty', 'HP Care Pack', 'Lenovo Premier', 'Apple Care'])
    po_number = factory.Sequence(lambda n: f'PO-{fake.uuid4()[:8].upper()}')
    po_date = factory.LazyAttribute(lambda obj: obj.asset.purchase_date)
    po_amount = factory.LazyAttribute(lambda obj: round(obj.asset.purchase_cost * 0.1, 2))
    coverage_details = factory.LazyAttribute(lambda obj: f'Standard warranty for {obj.asset.model}')
    support_contact = factory.LazyAttribute(lambda obj: f'support@{obj.provider.split()[0].lower()}.com')
    created_by = factory.SubFactory(UserFactory)

class DisposalRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DisposalRecord
    
    asset = factory.SubFactory(AssetFactory)
    disposal_date = factory.LazyAttribute(lambda obj: fake.date_between(
        start_date=obj.asset.purchase_date,
        end_date='today'
    ))
    disposal_method = factory.Iterator(['recycled', 'sold', 'donated', 'destroyed'])
    disposal_reason = factory.LazyAttribute(lambda obj: f'End of life for {obj.asset.model}')
    disposal_value = factory.LazyAttribute(lambda obj: round(obj.asset.purchase_cost * random.uniform(0.05, 0.2), 2))
    approved_by = factory.SubFactory(UserFactory)
    created_by = factory.SubFactory(UserFactory)

class AssetCustodianHistoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AssetCustodianHistory
    
    asset = factory.SubFactory(AssetFactory)
    custodian = factory.SubFactory(UserFactory)
    assigned_date = factory.LazyAttribute(lambda obj: fake.date_between(
        start_date=obj.asset.purchase_date if obj.asset.purchase_date else '-2y',
        end_date='today'
    ))
    notes = factory.LazyAttribute(lambda obj: f'Asset {obj.asset.asset_tag} assigned to {obj.custodian.get_full_name()}')
    created_by = factory.SubFactory(UserFactory)

class AssetLocationHistoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AssetLocationHistory
    
    asset = factory.SubFactory(AssetFactory)
    location = factory.SubFactory(LocationFactory)
    moved_date = factory.LazyAttribute(lambda obj: fake.date_between(
        start_date=obj.asset.purchase_date if obj.asset.purchase_date else '-2y',
        end_date='today'
    ))
    notes = factory.LazyAttribute(lambda obj: f'Asset {obj.asset.asset_tag} moved to {obj.location.name}')
    created_by = factory.SubFactory(UserFactory)

class SoftwareLicenseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SoftwareLicense
    
    software = factory.SubFactory(SoftwareFactory)
    license_key = factory.LazyFunction(lambda: fake.uuid4().upper())
    status = factory.Iterator(['available', 'assigned', 'expired', 'revoked'])
    
    # Assignment
    assigned_to = factory.LazyAttribute(lambda obj: UserFactory() if obj.status == 'assigned' else None)
    assigned_date = factory.LazyAttribute(lambda obj: fake.date_between(start_date='-1y', end_date='today') if obj.status == 'assigned' else None)
    
    # Validity
    activation_date = factory.LazyAttribute(lambda obj: fake.date_between(start_date='-1y', end_date='today') if obj.status in ['assigned', 'expired'] else None)
    expiry_date = factory.LazyAttribute(lambda obj: fake.date_between(start_date='today', end_date='+2y') if obj.status in ['assigned', 'available'] else fake.date_between(start_date='-1y', end_date='today') if obj.status == 'expired' else None)
    
    notes = factory.LazyAttribute(lambda obj: f'License key for {obj.software.software_name}' if random.random() < 0.3 else '')
    created_by = factory.SubFactory(UserFactory)

class DepreciationPolicyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DepreciationPolicy
    
    asset_category = factory.SubFactory(AssetCategoryFactory)
    useful_life_years = factory.Iterator([3, 5, 7, 10])
    depreciation_rate = factory.LazyAttribute(lambda obj: round(100 / obj.useful_life_years, 2))
    method = factory.Iterator(['Straight-line', 'Reducing balance', 'Double declining balance', 'Sum of years digits'])
    created_by = factory.SubFactory(UserFactory)