# ict_assets/models.py
from django.db import models
from mnh_auth.models import BaseModel
from django.contrib.auth import get_user_model
User = get_user_model()

class AssetCategory(BaseModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent_category = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)


class AssetType(BaseModel):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(AssetCategory, on_delete=models.CASCADE)
    specifications_template = models.JSONField(default=dict)  # For dynamic fields


class Manufacturer(BaseModel):
    name = models.CharField(max_length=100)
    contact_email = models.EmailField(blank=True)
    support_phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)


class Supplier(BaseModel):
    name = models.CharField(max_length=100)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)


class Asset(BaseModel):
    ASSET_STATUS = [
        ('operational', 'Operational'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('in_repair', 'In Repair'),
        ('under_maintenance', 'Under Maintenance'),
        ('in_storage', 'In Storage'),
        ('reserved', 'Reserved'),
        ('retired', 'Retired'),
        ('lost', 'Lost'),
        ('disposed', 'Disposed'),
    ]

    CONDITION_CHOICES = [
        ('new', 'New'),
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]

    asset_tag = models.CharField(max_length=50, unique=True)
    barcode = models.CharField(max_length=128, blank=True)  # optional barcode string
    serial_number = models.CharField(max_length=100, null=True, blank=True, unique=True)
    asset_type = models.ForeignKey(AssetType, on_delete=models.CASCADE)
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.SET_NULL, null=True, blank=True)
    model = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=ASSET_STATUS, default='operational')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, blank=True)
    location = models.ForeignKey('Location', on_delete=models.SET_NULL, null=True, blank=True)
    custodian = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assets')
    warranty_expiry = models.DateField(null=True, blank=True)  # convenience copy; canonical Warranty model exists below
    photo = models.TextField(max_length=200, null=True, blank=True)  # a file path

    is_active = models.BooleanField(default=True)  # soft-active flag
    last_audit_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['asset_tag']),
            models.Index(fields=['serial_number']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.asset_tag} ({self.asset_type.name})"


class AssetCustodianHistory(BaseModel):
    """Tracks the history of asset custodian changes"""
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='custodian_history')
    custodian = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='asset_custodian_history')
    assigned_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-assigned_date']
        verbose_name_plural = "Asset Custodian Histories"
    
    def __str__(self):
        custodian_name = f"{self.custodian.get_full_name()}" if self.custodian else "Unassigned"
        return f"{self.asset.asset_tag} - {custodian_name} ({self.assigned_date.strftime('%Y-%m-%d')})"


class AssetLocationHistory(BaseModel):
    """Tracks the history of asset location changes"""
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='location_history')
    location = models.ForeignKey('Location', on_delete=models.SET_NULL, null=True, blank=True, related_name='asset_location_history')
    moved_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-moved_date']
        verbose_name_plural = "Asset Location Histories"
    
    def __str__(self):
        location_name = self.location.name if self.location else "No Location"
        return f"{self.asset.asset_tag} - {location_name} ({self.moved_date.strftime('%Y-%m-%d')})"


# Hardware Specific Models
class Computer(BaseModel):
    STORAGE_TYPES = [
        ('hdd', 'HDD'),
        ('SSD', 'SSD'),
        ('nvme', 'NVMe'),
        ('hybrid', 'Hybrid (SSHD)'),
        ('external', 'External'),
        ('nas', 'Network Attached Storage'),
    ]

    CPU_ARCH_CHOICES = [
        ('x86', 'x86 (32-bit)'),
        ('x86_64', 'x86_64 (64-bit)'),
        ('arm', 'ARM (32-bit)'),
        ('arm64', 'ARM64'),
        ('powerpc', 'PowerPC'),
        ('riscv', 'RISC-V'),
        ('other', 'Other'),
    ]

    asset = models.OneToOneField(Asset, on_delete=models.CASCADE)
    hostname = models.CharField(max_length=100, blank=True)          # device host name
    fqdn = models.CharField(max_length=255, blank=True)             # fully qualified domain name
    processor = models.CharField(max_length=200, blank=True)
    cpu_cores = models.PositiveIntegerField(null=True, blank=True)
    cpu_speed_ghz = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    cpu_architecture = models.CharField(max_length=20, choices=CPU_ARCH_CHOICES, blank=True)

    ram_gb = models.PositiveIntegerField(null=True, blank=True)
    storage_type = models.CharField(max_length=20, choices=STORAGE_TYPES, default='ssd')
    storage_gb = models.PositiveIntegerField(null=True, blank=True)
    disks = models.JSONField(default=list, blank=True)  # list of disks: [{"type":"nvme","size_gb":512,"model":"..."}]

    operating_system = models.CharField(max_length=150, blank=True)
    os_version = models.CharField(max_length=100, blank=True)

    # networking - allow multiple MAC/IP entries
    mac_addresses = models.JSONField(default=list, blank=True)  # e.g. ["00:11:22:33:44:55"]
    ip_addresses = models.JSONField(default=list, blank=True)   # e.g. ["10.0.0.5", "192.168.1.5"]
    management_ip = models.GenericIPAddressField(null=True, blank=True)

    gpu = models.CharField(max_length=200, blank=True)
    virtual = models.BooleanField(default=False)                 # is virtual machine
    virtualization_host = models.CharField(max_length=200, blank=True)  # host if VM

    bios_version = models.CharField(max_length=100, blank=True)
    firmware_version = models.CharField(max_length=100, blank=True)

    asset_tag_backup = models.CharField(max_length=50, blank=True)  # optional local copy if needed
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['hostname']),
            models.Index(fields=['virtual']),
        ]

    def __str__(self):
        return self.hostname or str(self.asset)


class NetworkDevice(BaseModel):
    DEVICE_TYPES = [
        ('router', 'Router'),
        ('switch', 'Switch'),
        ('firewall', 'Firewall'),
        ('access_point', 'Access Point'),
    ]

    asset = models.OneToOneField(Asset, on_delete=models.CASCADE)
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    mac_address = models.CharField(max_length=17, blank=True)
    ports = models.IntegerField(default=0)


class Peripheral(BaseModel):
    PERIPHERAL_TYPES = [
        ('printer', 'Printer'),
        ('scanner', 'Scanner'),
        ('monitor', 'Monitor'),
        ('keyboard', 'Keyboard'),
        ('mouse', 'Mouse'),
    ]

    CONNECTION_TYPES = [
        ('usb', 'USB'),
        ('utp', 'UTP'),
        ('bluetooth', 'BLUETOOTH'),
        ('wi-fi', 'Wi-FI'),
    ]

    asset = models.OneToOneField(Asset, on_delete=models.CASCADE)
    peripheral_type = models.CharField(max_length=20, choices=PERIPHERAL_TYPES)
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPES)


# software models
class SoftwareCategory(BaseModel):
    """
    Represents a category used to classify software assets.

    This model groups software into high-level categories (for example,
    "Productivity", "Security", "Development") to simplify filtering, reporting,
    and policy application across the ICT asset inventory.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)


class Software(BaseModel):
    LICENSE_TYPES = [
        ('perpetual', 'Perpetual'),
        ('subscription', 'Subscription'),
        ('open_source', 'Open Source'),
    ]

    name = models.CharField(max_length=100)
    version = models.CharField(max_length=50)
    publisher = models.CharField(max_length=100)
    category = models.ForeignKey(SoftwareCategory, on_delete=models.CASCADE)
    license_type = models.CharField(max_length=20, choices=LICENSE_TYPES)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_date = models.DateField()
    expiration_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)


class SoftwareInstallation(BaseModel):
    software = models.ForeignKey(Software, on_delete=models.CASCADE)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    installed_date = models.DateField()
    license_key = models.CharField(max_length=255, blank=True)
    installed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)


# locations models
class Building(BaseModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)  # block code if needed
    address = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name


class Floor(BaseModel):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="floors")
    number = models.IntegerField()  # use integer for floor level
    name = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ("building", "number")

    def __str__(self):
        return f"{self.building.name} - Floor {self.number}"


class Location(BaseModel):
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    building = models.ForeignKey(Building, on_delete=models.SET_NULL, null=True, blank=True)
    floor = models.ForeignKey(Floor, on_delete=models.SET_NULL, null=True, blank=True)
    room = models.CharField(max_length=50, blank=True)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True)  # optional nesting

    def __str__(self):
        parts = [self.name]
        if self.room:
            parts.append(self.room)
        if self.floor:
            parts.append(f"Floor {self.floor.number}")
        if self.building:
            parts.append(self.building.name)
        return " / ".join(parts)


class AssetAssignment(BaseModel):
    CONDITION_ON_ASSIGNMENT_CHOICES = [
        ('new', 'New'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('fixed', 'Fixed'),
    ]

    asset = models.OneToOneField(Asset, on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE)
    assigned_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    condition_on_assignment = models.CharField(
        max_length=20,
        choices=CONDITION_ON_ASSIGNMENT_CHOICES,
        default='good',
        blank=True,
    )
    notes = models.TextField(blank=True)


# maintenance models
class MaintenanceRecord(BaseModel):
    MAINTENANCE_STATUS = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    MAINTENANCE_TYPE_CHOICES = [
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('calibration', 'Calibration'),
        ('inspection', 'Inspection'),
        ('upgrade', 'Upgrade'),
        ('repair', 'Repair'),
        ('cleaning', 'Cleaning'),
    ]

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    maintenance_type = models.CharField(max_length=30, choices=MAINTENANCE_TYPE_CHOICES, default='corrective')
    scheduled_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=MAINTENANCE_STATUS, default='scheduled')
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    description = models.TextField()
    technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_records')
    notes = models.TextField(blank=True)


class SupportTicket(BaseModel):
    TICKET_STATUS = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    ticket_id = models.CharField(max_length=20, unique=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    issue_description = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    status = models.CharField(max_length=20, choices=TICKET_STATUS, default='open')
    created_date = models.DateTimeField(auto_now_add=True)
    resolved_date = models.DateTimeField(null=True, blank=True)
    assigned_technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    resolution_notes = models.TextField(blank=True)


# procurement and Disposal models
class DisposalRecord(BaseModel):
    DISPOSAL_METHODS = [
        ('recycled', 'Recycled'),
        ('sold', 'Sold'),
        ('donated', 'Donated'),
        ('destroyed', 'Destroyed'),
    ]

    asset = models.OneToOneField(Asset, on_delete=models.CASCADE)
    disposal_date = models.DateField()
    disposal_method = models.CharField(max_length=20, choices=DISPOSAL_METHODS)
    disposal_reason = models.TextField()
    disposal_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.CASCADE)
    notes = models.TextField(blank=True)


# configuration models
class DepreciationPolicy(BaseModel):
    asset_category = models.ForeignKey(AssetCategory, on_delete=models.CASCADE)
    useful_life_years = models.IntegerField()
    depreciation_rate = models.DecimalField(max_digits=5, decimal_places=2)
    method = models.CharField(max_length=50)  # Straight-line, Reducing balance, etc.


class Warranty(BaseModel):
    PROVIDER_CHOICES = [
        ('vendor', 'Vendor'),
        ('manufacturer', 'Manufacturer'),
        ('other', 'Other'),
    ]

    asset = models.OneToOneField(Asset, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default='manufacturer')

    # Procurement / TOR details
    po_number = models.CharField(max_length=100, blank=True)
    po_date = models.DateField(null=True, blank=True)
    po_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    procurement_notes = models.TextField(blank=True)
    contract_file = models.FileField(upload_to="contracts/", null=True, blank=True)

    coverage_details = models.TextField(blank=True)
    support_contact = models.TextField(blank=True)




