from django.contrib import admin
from django.contrib import messages

from .models import (
    OxygenUsage,
    OxygenSupplier,
    OxygenVolume,
    OxygenLocation,
    LocationOxygenVolumes,
    OxygenReceiving,
    OxygenAllocation,
    PatientAgeGroup,
    LocationalOxygenUsage,
    OxygenUsagePatientAgeGroup, OxygenReceiveItem, OxygenAllocationItem,
)
from .service import verify_allocation, verify_receiving


class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'email_address', 'physical_address', 'contact', 'telephone', 'remarks')
    search_fields = ('name', 'email_address', 'contact')
    ordering = ('name',)
    exclude = ('created_at', 'deleted_at', 'is_deleted', 'deleted_by', 'updated_by', 'created_by')
admin.site.register(OxygenSupplier, SupplierAdmin)


class OxygenVolumeAdmin(admin.ModelAdmin):
    list_display = ('name', 'volume', 'created_at')
    search_fields = ('name', 'volume')
    ordering = ('-volume',)
    exclude = ('created_at', 'deleted_at', 'is_deleted', 'deleted_by', 'updated_by', 'created_by')
admin.site.register(OxygenVolume, OxygenVolumeAdmin)



class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'type', 'quantity', 'created_at')
    search_fields = ('name', 'code')
    list_filter = ('type',)
    ordering = ('name',)
    exclude = ('created_at', 'deleted_at', 'is_deleted', 'deleted_by', 'updated_by', 'created_by')
admin.site.register(OxygenLocation, LocationAdmin)

class LocationOxygenVolumeAdmin(admin.ModelAdmin):
    list_display = ('location', 'volume', 'quantity', 'created_at')
    search_fields = ('location__name', 'volume__name')
    ordering = ('quantity',)
    exclude = ('created_at', 'deleted_at', 'is_deleted', 'deleted_by', 'updated_by', 'created_by')
admin.site.register(LocationOxygenVolumes, LocationOxygenVolumeAdmin)


class OxygenReceiveItemInline(admin.TabularInline):
    model = OxygenReceiveItem
    extra = 1
    fields = ('volume', 'supplier', 'quantity', 'status', 'verify_date', 'verify_remarks', 'verify_by')
    readonly_fields = ('status', 'verify_date', 'verify_remarks', 'verify_by')
    can_delete = False  # optional: disallow deletes from inline

class OxygenReceivingAdmin(admin.ModelAdmin):
    list_display = ('location', 'status', 'receiving_number', 'date')
    search_fields = ('receiving_number', 'location__name')
    list_filter = ('status',)
    ordering = ('-created_at',)
    exclude = ('created_at', 'deleted_at', 'is_deleted', 'deleted_by', 'updated_by', 'created_by')

    actions = ['verify_receiving']
    inlines = [OxygenReceiveItemInline]

    def verify_receiving(self, request, queryset):
        for obj in queryset:
            try:
                verify_receiving(uid=obj.uid, user=request.user)
                self.message_user(request, f"Verified {obj}", level=messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f"Failed {obj}: {e}", level=messages.ERROR)

    verify_receiving.short_description = "Verify selected Receiving"
admin.site.register(OxygenReceiving, OxygenReceivingAdmin)


class OxygenAllocationItemInline(admin.TabularInline):
    model = OxygenAllocationItem
    extra = 1
    fields = ('volume', 'quantity', 'status', 'verify_date', 'verify_remarks', 'verify_by')
    readonly_fields = ('status', 'verify_date', 'verify_remarks', 'verify_by')
    can_delete = False  # optional: disallow deletes from inline

class OxygenAllocationAdmin(admin.ModelAdmin):
    list_display = ('date', 'location_from', 'location_to','status')
    search_fields = ('location_from__name', 'location_to__name')
    list_filter = ('status','location_from__name', 'location_to__name')
    ordering = ('-date',)
    exclude = ('created_at', 'deleted_at', 'is_deleted', 'deleted_by', 'updated_by', 'created_by')

    actions = ['verify_allocations']
    inlines = [OxygenAllocationItemInline]

    def verify_allocations(self, request, queryset):
        for obj in queryset:
            try:
                verify_allocation(uid=obj.uid, user=request.user)
                self.message_user(request, f"Verified {obj}", level=messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f"Failed {obj}: {e}", level=messages.ERROR)

    verify_allocations.short_description = "Verify selected allocations"
admin.site.register(OxygenAllocation, OxygenAllocationAdmin)

class PatientAgeGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_age', 'max_age', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)
    ordering = ('min_age',)
    exclude = ('created_at', 'deleted_at', 'is_deleted', 'deleted_by', 'updated_by', 'created_by')
admin.site.register(PatientAgeGroup, PatientAgeGroupAdmin)


class OxygenUsagePatientAgeGroupInline(admin.TabularInline):
    model = OxygenUsagePatientAgeGroup
    extra = 1  # Number of empty forms to show
    # readonly_fields = ('patient_age_group', 'oxygen', 'ventilator', 'cpap', 'remarks')
    can_delete = True
    show_change_link = True
    exclude = ('created_at', 'deleted_at', 'is_deleted', 'deleted_by', 'updated_by', 'created_by')

@admin.register(LocationalOxygenUsage)
class LocationalOxygenUsageAdmin(admin.ModelAdmin):
    list_display = ('location', 'date', 'status')
    inlines = [OxygenUsagePatientAgeGroupInline]
    search_fields = ('location__name',)
    list_filter = ('status',)
    ordering = ('-date',)
    exclude = ('created_at', 'deleted_at', 'is_deleted', 'deleted_by', 'updated_by', 'created_by')

class OxygenUsagePatientAgeGroupAdmin(admin.ModelAdmin):
    list_display = ('oxygen_usage', 'patient_age_group', 'oxygen', 'ventilator', 'cpap')
    search_fields = ('oxygen_usage__location__name', 'patient_age_group__name')
    ordering = ('created_at',)
    exclude = ('created_at', 'deleted_at', 'is_deleted', 'deleted_by', 'updated_by', 'created_by')
admin.site.register(OxygenUsagePatientAgeGroup, OxygenUsagePatientAgeGroupAdmin)
