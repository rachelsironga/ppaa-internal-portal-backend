
from django.db import models
from django.db.models import Q
import uuid
from polymorphic.models import PolymorphicModel

from mnh_auth.models import BaseModel
from mnh_model.models import User


class PolymorphicBaseModel(PolymorphicModel):
    id = models.BigAutoField(primary_key=True)
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateField(blank=True, null=True)
    updated_at = models.DateField(blank=True, null=True)
    deleted_at = models.DateField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, related_name='created_%(class)s', on_delete=models.SET_NULL, null=True,
                                   blank=True)
    updated_by = models.ForeignKey(User, related_name='updated_%(class)s', on_delete=models.SET_NULL, null=True,
                                   blank=True)
    deleted_by = models.ForeignKey(User, related_name='deleted_%(class)s', on_delete=models.SET_NULL, null=True,
                                   blank=True)

    class Meta:
        abstract = True


class OxygenUsage(BaseModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'o2_mng_oxygen_usages'
        constraints = [
            models.UniqueConstraint(fields=['name', 'code'], condition=Q(deleted_at=None),
                                    name='unique_active_oxygen_usage')
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class OxygenSupplier(BaseModel):
    name = models.CharField(max_length=100)
    email_address = models.CharField(max_length=100)
    physical_address = models.CharField(max_length=100)
    contact = models.CharField(max_length=15)
    telephone = models.CharField(max_length=15)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'o2_mng_suppliers'
        ordering = ('name',)

    def __str__(self):
        return f"{self.name}"


class OxygenVolume(BaseModel):
    name = models.CharField(max_length=100)
    volume = models.CharField(max_length=5)

    class Meta:
        db_table = 'o2_mng_oxygen_volume'
        ordering = ('-volume',)

    def __str__(self):
        return f"{self.name}"


class OxygenLocation(BaseModel):
    OXYGEN_TYPE_CHOICES = [
        ('STORE', 'Store'),
        ('WARD', 'Ward'),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=15, unique=True)
    type = models.CharField(max_length=10, choices=OXYGEN_TYPE_CHOICES)
    quantity = models.IntegerField(default=0)

    class Meta:
        db_table = 'o2_mng_location'
        ordering = ('name',)

    def update_quantity(self):
        """Updates the location's total quantity based on its oxygen volumes"""
        total_quantity = LocationOxygenVolumes.objects.filter(
            location=self,
            is_deleted=False
        ).aggregate(total=models.Sum('quantity'))['total'] or 0
        self.quantity = total_quantity
        self.save()

    def __str__(self):
        return f"{self.name}"


class LocationOxygenVolumes(BaseModel):
    location = models.ForeignKey('oxygen_managements.OxygenLocation', on_delete=models.CASCADE, related_name='location')
    volume = models.ForeignKey(OxygenVolume, on_delete=models.CASCADE, related_name='location_volume')
    quantity = models.IntegerField()

    class Meta:
        db_table = 'o2_mng_location_oxygen_volumes'
        unique_together = ('location', 'volume')
        ordering = ['quantity']

    def __str__(self):
        return f"{self.location.code} ({self.volume.volume})"

    def save(self, *args, **kwargs):
        # Save the volume record first
        super().save(*args, **kwargs)

        # Update the parent Location's total quantity
        self.update_location_quantity()

    def delete(self, *args, **kwargs):
        # Get location before deletion
        location = self.location
        super().delete(*args, **kwargs)

        # Update location quantity using aggregation
        total_quantity = LocationOxygenVolumes.objects.filter(
            location=location,
            is_deleted=False
        ).aggregate(total=models.Sum('quantity'))['total'] or 0
        location.quantity = total_quantity
        location.save()

    def update_location_quantity(self):
        # Sum all quantities from related volumes
        total_quantity = LocationOxygenVolumes.objects.filter(
            location=self.location,
            is_deleted=False
        ).aggregate(total=models.Sum('quantity'))['total'] or 0

        # Update the Location's quantity
        self.location.quantity = total_quantity
        self.location.save()


class OxygenReceiving(BaseModel):
    RECEIVING_CHOICES = [
        ('NEW', 'new'),
        ('VERIFIED', 'Verified'),
        ('PARTIAL_VERIFIED', 'Partial Verified'),
        ('REJECTED', 'Rejected')
    ]
    location = models.ForeignKey('oxygen_managements.OxygenLocation', on_delete=models.CASCADE, related_name='receiving_location')
    quantity = models.IntegerField(default=0)
    status = models.CharField(max_length=30, choices=RECEIVING_CHOICES, default='NEW')
    receiving_number = models.CharField(max_length=20)
    date = models.DateTimeField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'o2_mng_oxygen_receiving'
        ordering = ['-date']

    def __str__(self):
        return f" {self.location.code} [{self.date.day}/{self.date.month}/{self.date.year}] "


class OxygenReceiveItem(BaseModel):
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    ]

    receiving = models.ForeignKey('OxygenReceiving', on_delete=models.CASCADE, related_name='receive_items')
    volume = models.ForeignKey('OxygenVolume', on_delete=models.CASCADE, related_name='receive_item_volume')
    supplier = models.ForeignKey('oxygen_managements.OxygenSupplier', on_delete=models.CASCADE, related_name='receive_item_supplier')
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    verify_date = models.DateTimeField(blank=True, null=True)
    verify_remarks = models.TextField(blank=True, null=True)
    verify_by = models.ForeignKey(User, related_name='verified_%(class)s', on_delete=models.SET_NULL, null=True,
                                  blank=True)

    class Meta:
        db_table = 'o2_mng_oxygen_receive_item'
        unique_together = ('receiving', 'volume', 'supplier')
        ordering = ['volume']

    def __str__(self):
        return f"{self.receiving} ( {self.volume.volume} ) "


class OxygenAllocation(BaseModel):
    RECEIVING_CHOICES = [
        ('NEW', 'New'),
        ('VERIFIED', 'Verified'),
        ('PARTIAL_VERIFIED', 'Partial Verified'),
        ('REJECTED', 'Rejected')
    ]
    location_from = models.ForeignKey(OxygenLocation, on_delete=models.CASCADE, related_name='location_from')
    location_to = models.ForeignKey(OxygenLocation, on_delete=models.CASCADE, related_name='location_to')
    date = models.DateTimeField(blank=False, null=False)
    quantity = models.IntegerField(default=0)
    status = models.CharField(max_length=50, choices=RECEIVING_CHOICES, default='NEW')
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'o2_mng_oxygen_allocation'
        ordering = ['-date']

    def __str__(self):
        return f" {self.location_from.code} -> {self.location_to.code} [{self.date.day}/{self.date.month}/{self.date.year}]"


class OxygenAllocationItem(BaseModel):
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    ]

    allocation = models.ForeignKey('oxygen_managements.OxygenAllocation', on_delete=models.CASCADE, related_name='allocation_items')
    volume = models.ForeignKey('OxygenVolume', on_delete=models.CASCADE, related_name='allocation_item_volume')
    quantity = models.IntegerField(default=0)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='NEW')
    verify_date = models.DateTimeField(blank=True, null=True)
    verify_remarks = models.TextField(blank=True, null=True)
    verify_by = models.ForeignKey(User, related_name='verified_%(class)s', on_delete=models.SET_NULL, null=True,
                                  blank=True)

    class Meta:
        db_table = 'o2_mng_allocation_item'
        unique_together = ('allocation', 'volume')
        ordering = ['volume']

    def __str__(self):
        return f"{self.allocation} ( {self.volume.volume} ) "


class PatientAgeGroup(BaseModel):
    name = models.CharField(max_length=50, unique=True)
    min_age = models.IntegerField()
    max_age = models.IntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'o2_mng__patient_age_groups'
        unique_together = ('min_age', 'max_age')
        ordering = ('min_age', 'max_age',)

    def __str__(self):
        return f"{self.name} ({self.min_age} - {self.max_age})"


class LocationalOxygenUsage(BaseModel):
    USAGE_CHOICES = [
        ('NEW', 'new'),
        ('VERIFIED', 'Verified'),
    ]
    location = models.ForeignKey('oxygen_managements.OxygenLocation', on_delete=models.CASCADE, related_name='location_oxygen_usages')
    date = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=USAGE_CHOICES, default='NEW')
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'o2_mng_locational_oxygen_usage'
        ordering = ['-date']

    def __str__(self):
        return f"{self.id} | {self.location.code}  [{self.date.day}/{self.date.month}/{self.date.year}] "


class OxygenUsagePatientAgeGroup(BaseModel):
    oxygen_usage = models.ForeignKey(LocationalOxygenUsage, on_delete=models.CASCADE, related_name='patient_age_groups')
    patient_age_group = models.ForeignKey(PatientAgeGroup, on_delete=models.CASCADE, related_name='oxygen_usages')
    oxygen = models.IntegerField()
    ventilator = models.IntegerField()
    cpap = models.IntegerField()
    remarks = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'o2_mng_oxygen_usage_patient_age_groups'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.id} | {self.oxygen_usage.location.code} - {self.patient_age_group.name}  [{self.oxygen_usage.date.day}/{self.oxygen_usage.date.month}/{self.oxygen_usage.date.year}] "