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
    barcode = models.CharField(max_length=128, blank=True)  # optional barcode string (nullable true)
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
        ('ssd', 'SSD'),
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
        ('load_balancer', 'Load Balancer'),
        ('gateway', 'Gateway'),
        ('modem', 'Modem'),
        ('hub', 'Hub'),
        ('bridge', 'Bridge'),
        ('other', 'Other'),
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
        ('keyboard', 'Keyboard'),
        ('mouse', 'Mouse'),
        ('monitor', 'Monitor'),
        ('speaker', 'Speaker'),
        ('webcam', 'Webcam'),
        ('headset', 'Headset'),
        ('microphone', 'Microphone'),
        ('other', 'Other'),
    ]

    CONNECTION_TYPES = [
        ('usb', 'USB'),
        ('bluetooth', 'Bluetooth'),
        ('wireless', 'Wireless'),
        ('hdmi', 'HDMI'),
        ('vga', 'VGA'),
        ('ps2', 'PS/2'),
        ('ethernet', 'Ethernet'),
        ('other', 'Other'),
    ]

    asset = models.OneToOneField(Asset, on_delete=models.CASCADE)
    peripheral_type = models.CharField(max_length=20, choices=PERIPHERAL_TYPES)
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPES)

    def save(self, *args, **kwargs):
        # Normalize fields before saving
        if self.peripheral_type:
            self.peripheral_type = self.peripheral_type.strip().lower()
        if self.connection_type:
            self.connection_type = self.connection_type.strip().lower()
        super().save(*args, **kwargs)


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
        ('trial', 'Trial'),
        ('enterprise', 'Enterprise'),
        ('volume', 'Volume License'),
        ('freeware', 'Freeware'),
        ('site_license', 'Site License'),
        ('oem', 'OEM'),
        ('concurrent', 'Concurrent'),
        ('other', 'Other'),
    ]

    SOFTWARE_TYPES = [
        ('application', 'Application'),
        ('operating_system', 'Operating System'),
        ('utility', 'Utility'),
        ('development_tool', 'Development Tool'),
        ('database', 'Database'),
        ('security', 'Security'),
        ('office_suite', 'Office Suite'),
        ('graphics_design', 'Graphics/Design'),
        ('server_software', 'Server Software'),
        ('virtualization', 'Virtualization'),
        ('backup', 'Backup Software'),
        ('antivirus', 'Antivirus'),
        ('productivity', 'Productivity'),
        ('other', 'Other'),
    ]

    PLATFORM_CHOICES = [
        ('windows', 'Windows'),
        ('linux', 'Linux'),
        ('macos', 'macOS'),
        ('web', 'Web-based'),
        ('cross_platform', 'Cross-platform'),
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('trial', 'Trial'),
        ('expired', 'Expired'),
        ('deprecated', 'Deprecated'),
        ('operational', 'Operational'),
        ('retired', 'Retired'),
        ('disposed', 'Disposed'),
        ('other', 'Other'),
    ]

    CONDITION_CHOICES = [
        ('new', 'New'),
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]

    # Basic Information
    asset_tag = models.CharField(max_length=50, unique=True, default='AUTO')
    software_name = models.CharField(max_length=100, default='Unknown')
    version = models.CharField(max_length=50, default='1.0')
    publisher = models.CharField(max_length=100, default='Unknown')
    software_type = models.CharField(max_length=50, choices=SOFTWARE_TYPES, null=True, blank=True)
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES, null=True, blank=True)
    
    # Legacy field - consider mapping to software_type
    category = models.ForeignKey('SoftwareCategory', on_delete=models.CASCADE, null=True, blank=True)
    
    # Asset Management
    asset_type = models.ForeignKey('AssetType', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, null=True, blank=True)
    photo = models.TextField(max_length=200, null=True, blank=True)  # a file path
    
    # License Information
    license_type = models.CharField(max_length=20, choices=LICENSE_TYPES)
    license_key = models.CharField(max_length=255, null=True, blank=True)
    total_licenses = models.IntegerField(default=1)
    used_licenses = models.IntegerField(default=0)
    license_expiry = models.DateField(null=True, blank=True)  # Renamed from expiration_date
    
    # Financial Information
    purchase_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Renamed from cost
    purchase_date = models.DateField(null=True, blank=True)
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    
    # Assignment & Location
    custodian = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='software_assets')
    location = models.ForeignKey('Location', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Technical Details
    system_requirements = models.TextField(null=True, blank=True)
    installation_path = models.CharField(max_length=255, null=True, blank=True)
    
    # Support & Documentation
    support_url = models.URLField(max_length=500, null=True, blank=True)
    documentation_url = models.URLField(max_length=500, null=True, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    last_audit_date = models.DateField(null=True, blank=True)
    
    # Timestamps (inherited from BaseModel if it exists, otherwise add these)
    # created_at = models.DateTimeField(auto_now_add=True)
    # updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'software_assets'
        verbose_name = 'Software Asset'
        verbose_name_plural = 'Software Assets'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.asset_tag} - {self.software_name} v{self.version}"
    
    @property
    def available_licenses(self):
        """Calculate available licenses dynamically"""
        return max(0, self.total_licenses - self.used_licenses)
    
    @property
    def custodian_name(self):
        """Get custodian full name"""
        return self.custodian.get_full_name() if self.custodian else None
    
    @property
    def location_name(self):
        """Get location name"""
        return self.location.name if self.location else None
    
    @property
    def supplier_name(self):
        """Get supplier name"""
        return self.supplier.name if self.supplier else None
    
    @property
    def asset_type_name(self):
        """Get asset type name"""
        return self.asset_type.name if self.asset_type else None


class SoftwareInstallation(BaseModel):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending Installation'),
        ('failed', 'Installation Failed'),
        ('uninstalled', 'Uninstalled'),
    ]

    # Core Relationships
    software = models.ForeignKey(Software, on_delete=models.CASCADE, related_name='installations')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='software_installations')
    
    # Installation Details
    installation_date = models.DateField(null=True, blank=True)  # Renamed from installed_date
    installed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='software_installations')
    installation_path = models.CharField(max_length=500, null=True, blank=True)
    version_installed = models.CharField(max_length=50, null=True, blank=True)  # Track version at installation
    
    # License Information
    license_key_used = models.CharField(max_length=255, blank=True)  # Renamed from license_key
    license_assigned = models.ForeignKey('SoftwareLicense', on_delete=models.SET_NULL, null=True, blank=True)  # Optional: track specific license
    
    # Status & Verification
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    last_verified_date = models.DateField(null=True, blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_installations')
    
    # Uninstallation Details
    uninstall_date = models.DateField(null=True, blank=True)
    uninstalled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='uninstalled_software')
    uninstall_reason = models.TextField(null=True, blank=True)
    
    # Assignment
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_software')
    # department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)  # Commented out - Department model doesn't exist
    
    # Additional Information
    installation_notes = models.TextField(blank=True)
    configuration_notes = models.TextField(blank=True)
    
    # Compliance & Audit
    is_compliant = models.BooleanField(default=True)
    compliance_notes = models.TextField(blank=True)
    
    # Timestamps (inherited from BaseModel if it exists)
    # created_at = models.DateTimeField(auto_now_add=True)
    # updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'software_installations'
        verbose_name = 'Software Installation'
        verbose_name_plural = 'Software Installations'
        ordering = ['-installation_date']
        unique_together = [['software', 'asset']]  # Prevent duplicate installations on same asset
    
    def __str__(self):
        return f"{self.software.software_name} on {self.asset.asset_tag}"
    
    @property
    def software_name(self):
        """Get software name"""
        return self.software.software_name if self.software else None
    
    @property
    def asset_tag(self):
        """Get asset tag"""
        return self.asset.asset_tag if self.asset else None
    
    @property
    def asset_name(self):
        """Get asset name/description"""
        return self.asset.name if hasattr(self.asset, 'name') else self.asset.asset_tag
    
    @property
    def installed_by_name(self):
        """Get installer name"""
        return self.installed_by.get_full_name() if self.installed_by else None
    
    @property
    def assigned_to_name(self):
        """Get assigned user name"""
        return self.assigned_to.get_full_name() if self.assigned_to else None
    
    @property
    def is_active(self):
        """Check if installation is currently active"""
        return self.status == 'active'
    
    def save(self, *args, **kwargs):
        """Override save to update software license usage"""
        is_new = self.pk is None
        old_status = None
        
        if not is_new:
            old_instance = SoftwareInstallation.objects.get(pk=self.pk)
            old_status = old_instance.status
        
        super().save(*args, **kwargs)
        
        # Update software used_licenses count
        if is_new and self.status == 'active':
            self.software.used_licenses += 1
            self.software.save()
        elif old_status and old_status != self.status:
            if old_status == 'active' and self.status != 'active':
                # Deactivated - decrease used licenses
                self.software.used_licenses = max(0, self.software.used_licenses - 1)
                self.software.save()
            elif old_status != 'active' and self.status == 'active':
                # Activated - increase used licenses
                self.software.used_licenses += 1
                self.software.save()
    
    def delete(self, *args, **kwargs):
        """Override delete to update software license usage"""
        if self.status == 'active':
            self.software.used_licenses = max(0, self.software.used_licenses - 1)
            self.software.save()
        super().delete(*args, **kwargs)

class SoftwareLicense(BaseModel):
    """Individual license keys for software with multiple licenses"""
    
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    ]
    
    software = models.ForeignKey(Software, on_delete=models.CASCADE, related_name='licenses')
    license_key = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    
    # Assignment
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_date = models.DateField(null=True, blank=True)
    
    # Validity
    activation_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Tracking
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'software_licenses'
        verbose_name = 'Software License'
        verbose_name_plural = 'Software Licenses'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.software.software_name} - {self.license_key[:10]}..."
    
    @property
    def is_available(self):
        return self.status == 'available'
    
    @property
    def is_expired(self):
        from datetime import date
        return self.expiry_date and self.expiry_date < date.today()


# locations models
class Building(BaseModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)  # block code if needed
    address = models.TextField(blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name


class Floor(BaseModel):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="floors")
    number = models.IntegerField(null=True, blank=True)  # use integer for floor level
    name = models.CharField(max_length=50, blank=True)
    floor_number = models.CharField(max_length=20, blank=True)  # flexible floor number like "G", "B1", etc.
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['building', 'number'],
                name='unique_building_number',
                condition=models.Q(number__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['building', 'floor_number'],
                name='unique_building_floor_number',
                condition=models.Q(floor_number__isnull=False) & ~models.Q(floor_number='')
            )
        ]

    def __str__(self):
        floor_display = self.name or f"Floor {self.number}" if self.number else self.floor_number
        return f"{self.building.name} - {floor_display}"


class Location(BaseModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)  # location code
    address = models.TextField(blank=True)
    description = models.TextField(blank=True)
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
    STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    

    asset = models.OneToOneField(Asset, on_delete=models.CASCADE)
    disposal_date = models.DateField()
    disposal_method = models.CharField(max_length=20, choices=DISPOSAL_METHODS)
    disposal_reason = models.TextField()
    disposal_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='approved_disposals')
    rejected_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='rejected_disposals')
    rejection_reason = models.TextField(blank=True, null=True)
    decision_date = models.DateField(null=True, blank=True)  # date when decision was made

# Disposal Audit trail

class DisposalAuditTrail(BaseModel):
    disposal_record = models.ForeignKey(
        DisposalRecord, 
        on_delete=models.CASCADE, 
        related_name='audit_trail'
    )

    action = models.CharField(
        max_length=100
    )  # e.g., "Created", "Approved", "Rejected", "Resubmitted"

    performed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='disposal_actions'
    )

    action_date = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp of when the action was performed"
    )

    comments = models.TextField(
        blank=True,
        help_text="Optional remarks or notes about the action"
    )

    class Meta:
        verbose_name = "Disposal Audit Trail"
        verbose_name_plural = "Disposal Audit Trails"
        ordering = ['-action_date']


class DisposalConversation(BaseModel):

    MESSAGE_TYPE = [
        ('comment', 'Comment'),
        ('clarification', 'Clarification'),
        ('decision', 'Decision Note'),
    ]

    disposal_record = models.ForeignKey(
        DisposalRecord,
        on_delete=models.CASCADE,
        related_name='conversations'
    )

    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    message = models.TextField()

    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPE,
        default='comment'
    )

    is_internal = models.BooleanField(
        default=False,
        help_text="If true, only approvers can see this"
    )


    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender} ({self.message_type}) - {self.message[:50]}"


# configuration models
class DepreciationPolicy(BaseModel):
    asset_category = models.ForeignKey(AssetCategory, on_delete=models.CASCADE)
    useful_life_years = models.IntegerField()
    depreciation_rate = models.DecimalField(max_digits=5, decimal_places=2)
    method = models.CharField(max_length=50)


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




