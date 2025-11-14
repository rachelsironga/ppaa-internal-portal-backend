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
        # Extract password if provided
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
    support_phone = factory.Faker('phone_number')
    website = factory.LazyAttribute(lambda obj: f'www.{obj.name.lower().replace(" ", "")}.com')
    created_by = factory.SubFactory(UserFactory)

class SupplierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Supplier
    
    name = factory.Sequence(lambda n: f'Supplier {n}')
    contact_person = factory.Faker('name')
    email = factory.LazyAttribute(lambda obj: f'info@{obj.name.lower().replace(" ", "")}.com')
    phone = factory.Faker('phone_number')
    address = factory.Faker('address')
    created_by = factory.SubFactory(UserFactory)

# class BuildingFactory(factory.django.DjangoModelFactory):
#     class Meta:
#         model = Building
    
#     name = factory.Sequence(lambda n: f'Building {n}')
#     code = factory.Sequence(lambda n: f'B{n:02d}')
#     address = factory.Faker('address')
#     created_by = factory.SubFactory(UserFactory)

# class FloorFactory(factory.django.DjangoModelFactory):
#     class Meta:
#         model = Floor
    
#     building = factory.SubFactory(BuildingFactory)
#     number = factory.Sequence(lambda n: n + 1)
#     name = factory.LazyAttribute(lambda obj: f'Floor {obj.number}')
#     created_by = factory.SubFactory(UserFactory)

# class LocationFactory(factory.django.DjangoModelFactory):
#     class Meta:
#         model = Location
    
#     name = factory.Sequence(lambda n: f'Location {n}')
#     building = factory.SubFactory(BuildingFactory)
#     floor = factory.SubFactory(FloorFactory)
#     room = factory.Sequence(lambda n: f'{random.randint(1, 10)}{n:02d}')
#     address = factory.LazyAttribute(lambda obj: f'{obj.building.address}, Room {obj.room}')
#     created_by = factory.SubFactory(UserFactory)

#     @factory.lazy_attribute
#     def parent(self):
#         if random.random() < 0.2 and Location.objects.exists():
#             return random.choice(Location.objects.all())
#         return None

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
    
    name = factory.Sequence(lambda n: f'Software {n}')
    version = factory.Faker('numerify', text='#.#.#')
    publisher = factory.Faker('company')
    category = factory.SubFactory(SoftwareCategoryFactory)
    license_type = factory.Iterator(['Volume', 'Subscription', 'Free', 'Open Source'])
    cost = factory.Faker('random_number', digits=3, fix_len=True)
    purchase_date = factory.Faker('date_between', start_date='-2y', end_date='today')
    expiration_date = factory.LazyAttribute(lambda obj: obj.purchase_date + timedelta(days=365))
    created_by = factory.SubFactory(UserFactory)

class AssetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Asset
    
    asset_tag = factory.Sequence(lambda n: f'ASSET-{1000 + n:04d}')
    serial_number = factory.Sequence(lambda n: f'SN-{fake.uuid4()[:8].upper()}')
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
    
    software = factory.SubFactory(SoftwareFactory)
    asset = factory.SubFactory(AssetFactory)
    installed_date = factory.LazyAttribute(lambda obj: fake.date_between(
        start_date=obj.asset.purchase_date,
        end_date='today'
    ))
    license_key = factory.LazyFunction(lambda: fake.uuid4() if random.random() > 0.5 else '')
    installed_by = factory.SubFactory(UserFactory)
    created_by = factory.SubFactory(UserFactory)

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
    
    ticket_id = factory.Sequence(lambda n: f'TKT-{timezone.now().year}{n+1:04d}')
    asset = factory.SubFactory(AssetFactory)
    issue_description = factory.Faker('paragraph')
    priority = factory.Iterator(['low', 'medium', 'high', 'critical'])
    status = factory.Iterator(['open', 'in_progress', 'resolved', 'closed'])
    created_date = factory.Faker('date_between', start_date='-60d', end_date='today')
    assigned_technician = factory.SubFactory(UserFactory)
    created_by = factory.SubFactory(UserFactory)

    @factory.lazy_attribute
    def resolved_date(self):
        if self.status in ['resolved', 'closed']:
            return fake.date_between(start_date=self.created_date, end_date='today')
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
    disposal_method = factory.Iterator(['recycled', 'sold', 'donated', 'destroyed', 'trade_in'])
    disposal_reason = factory.LazyAttribute(lambda obj: f'End of life for {obj.asset.model}')
    disposal_value = factory.LazyAttribute(lambda obj: round(obj.asset.purchase_cost * random.uniform(0.05, 0.2), 2))
    approved_by = factory.SubFactory(UserFactory)
    created_by = factory.SubFactory(UserFactory)