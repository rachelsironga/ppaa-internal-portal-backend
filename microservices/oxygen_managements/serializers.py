from rest_framework import serializers
from django.db import transaction
from .models import (OxygenUsage, OxygenLocation, LocationOxygenVolumes, OxygenReceiving, OxygenAllocation,
                     OxygenVolume, OxygenSupplier, PatientAgeGroup, LocationalOxygenUsage,
                     OxygenUsagePatientAgeGroup, OxygenReceiveItem, OxygenAllocationItem)


# OxygenVolumeSerializerClass 
class OxygenVolumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OxygenVolume
        fields = ['uid', 'name', 'volume', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at']
        
    def validate(self, data):
        name = data.get('name')
        volume = data.get('volume')
        uid = self.instance.uid if self.instance else None
        existing = OxygenVolume.objects.filter(name=name, volume=volume, deleted_at=None)
        if existing.exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("An Oxygen Volume entry with the same name and code already exists.")
        return data 

# OxygenUsageSerializerClass
class OxygenUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OxygenUsage
        fields = ['uid', 'name', 'code', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
            'deleted_by': {'read_only': True},
        }

    def validate(self, data):
        name = data.get('name')
        code = data.get('code')
        uid = self.instance.uid if self.instance else None
        existing = OxygenUsage.objects.filter(name=name, code=code, deleted_at=None)
        if existing.exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("An Oxygen Usage entry with the same name and code already exists.")
        return data

# SupplierSerializerClass
class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = OxygenSupplier
        fields = ['uid', 'name', 'email_address', 'physical_address', 'contact','telephone','remarks', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at']
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True}, 
            'deleted_by': {'read_only': True},
        }

# LocationOxygenSerializer
class LocationOxygenSerializer(serializers.ModelSerializer):
    volumes = serializers.SerializerMethodField(read_only=True)
    # usages = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OxygenLocation
        fields = ['uid', 'name', 'code', 'type', 'quantity', 'volumes', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at']

    def get_volumes(self, obj):
        location_uid = self.context.get('location_uid') if hasattr(self, 'context') and self.context else None
        with_volumes = self.context.get('with_volumes', False) if hasattr(self, 'context') and self.context else None


        if location_uid or with_volumes:
            if with_volumes:
                location_uid = obj.uid
            # Get all volume records for this location
            location_volumes = LocationOxygenVolumes.objects.filter(
                location__uid=location_uid,
                location=obj,
                is_deleted=False
            ).select_related('volume')
            
            # Prepare the response data
            volumes_data = []
            for lv in location_volumes:
                volumes_data.append({
                    'volume_uid': lv.volume.uid,
                    'volume_name': lv.volume.name,
                    'volume_value': lv.volume.volume,
                    'quantity': lv.quantity
                })
            
            return volumes_data
        return []


    def validate(self, data):
        name = data.get('name')
        code = data.get('code')
        uid = self.instance.uid if self.instance else None
        existing = OxygenLocation.objects.filter(name=name, code=code, deleted_at=None)
        if existing.exists():
            if existing.exclude(uid=uid).exists():
                raise serializers.ValidationError("An Oxygen Location entry with the same name and code already exists.")
        return data



# LocationOxygenVolumesSerializerClass
class LocationOxygenVolumeSerializer(serializers.ModelSerializer):
    location_uid = serializers.UUIDField(write_only=True)
    volume_uid = serializers.UUIDField(write_only=True)

    location = LocationOxygenSerializer(read_only=True)
    volume = OxygenVolumeSerializer(read_only=True)


    class Meta:
        model = LocationOxygenVolumes
        fields = ['uid', 'location_uid','location', 'volume_uid', 'volume', 'quantity', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'location_uid', 'volume_uid', 'created_at', 'updated_at']

    def validate(self, data):
        """
        Ensure that volume_uid and location_uid exist in the database.
        """
        location_uid = data.get('location_uid')
        volume_uid = data.get('volume_uid')
        try:
            data['location'] = OxygenLocation.objects.get(uid=location_uid, is_deleted=False)
        except OxygenLocation.DoesNotExist:
            raise serializers.ValidationError({"location_uid": "Invalid Location, not found or deleted"})

        try:
            data['volume'] = OxygenVolume.objects.get(uid=volume_uid, is_deleted=False)
        except OxygenVolume.DoesNotExist:
            raise serializers.ValidationError({"volume_uid": "Invalid Volume, not found or deleted"})
        return data

    def create(self, validated_data):
        validated_data.pop('location_uid')
        validated_data.pop('volume_uid')
        return LocationOxygenVolumes.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        validated_data.pop('location_uid')
        validated_data.pop('volume_uid')
        return super().update(instance, validated_data)


class OxygenReceiveItemInputSerializer(serializers.Serializer):
    volume_uid = serializers.UUIDField(write_only=True)
    supplier_uid = serializers.UUIDField(write_only=True)
    quantity = serializers.IntegerField()

    def validate(self, data):
        volume_uid = data.get('volume_uid')
        supplier_uid = data.get('supplier_uid')

        # Validate volume
        try:
            volume = OxygenVolume.objects.get(uid=volume_uid, is_deleted=False)
            data['volume'] = volume
        except OxygenVolume.DoesNotExist:
            raise serializers.ValidationError({"volume_uid": f"Volume {volume_uid} not found or deleted"})

        # Validate supplier
        try:
            supplier = OxygenSupplier.objects.get(uid=supplier_uid, is_deleted=False)
            data['supplier'] = supplier
        except OxygenSupplier.DoesNotExist:
            raise serializers.ValidationError({"supplier_uid": f"Supplier {supplier_uid} not found or deleted"})

        return data

# user for view only isn't used for insert
class OxygenReceiveItemSerializer(serializers.ModelSerializer):
    volume = OxygenVolumeSerializer(read_only=True)
    supplier = SupplierSerializer(read_only=True)

    verify_by = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OxygenReceiveItem
        fields = [
            'uid','volume','supplier', 'quantity','status','verify_date','verify_by',
        ]
        read_only_fields = ['uid', 'status', 'verify_date', 'verify_by']

    def get_verify_by(self, obj):
        if obj.verify_by:
            user = obj.verify_by
            if user:
                return {
                    'uid': user.guid,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
        return None

    def validate(self, data):
        """
        Ensure that volume_uid and location_uid exist in the database.
        """
        volume_uid = data.get('volume_uid')
        supplier_uid = data.get('supplier_uid')

        try:
            data['volume'] = OxygenVolume.objects.get(uid=volume_uid, is_deleted=False)
        except OxygenVolume.DoesNotExist:
            raise serializers.ValidationError({"volume_uid": "Invalid Volume, not found or deleted"})

        try:
            data['supplier'] = OxygenSupplier.objects.get(uid=supplier_uid, is_deleted=False)
        except OxygenSupplier.DoesNotExist:
            raise serializers.ValidationError({"supplier_uid": "Invalid Supplier, not found or deleted"})

        return data

# OxygenReceivingSerializer
class OxygenReceivingSerializer(serializers.ModelSerializer):
    location_uid = serializers.UUIDField(write_only=True)
    date = serializers.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "iso-8601"]
    )
    receive_details = OxygenReceiveItemSerializer(source='receive_items',read_only=True, many=True)

    receive_items = OxygenReceiveItemInputSerializer(write_only=True, many=True)
    received_by = serializers.SerializerMethodField(read_only=True)


    location = LocationOxygenSerializer(read_only=True)

    class Meta:
        model = OxygenReceiving
        fields = [
            'uid', 'location', 'receive_items','receive_details',  'status',
            'receiving_number', 'remarks', 'created_at', 'updated_at',
            'location_uid', 'date','quantity','received_by'
        ]
        read_only_fields = ['uid', 'created_at', 'status', 'updated_at']

    def get_received_by(self, obj):
        if obj.created_by:
                return {
                    'uid': obj.created_by.guid,
                    'name': f'{obj.created_by.first_name} {obj.created_by.last_name}',
                }
        return None

    def validate(self, data):
        """
        Ensure that volume_uid and location_uid exist in the database.
        """
        location_uid = data.get('location_uid')
        try:
            data['location'] = OxygenLocation.objects.get(uid=location_uid, is_deleted=False)
        except OxygenLocation.DoesNotExist:
            raise serializers.ValidationError({"location_uid": "Invalid Location, not found or deleted"})


        return data

    def create(self, validated_data):
        receive_items_data = validated_data.pop('receive_items', [])
        validated_data.pop('location_uid', None)
        # Compute total quantity from receiver items
        total_quantity = sum(item.get('quantity', 0) for item in receive_items_data)
        validated_data['quantity'] = total_quantity
        instance = OxygenReceiving.objects.create(**validated_data)

        # Create each item individually
        for item in receive_items_data:
            OxygenReceiveItem.objects.create(
                receiving=instance,
                volume=item['volume'],
                supplier = item['supplier'],
                quantity=item['quantity'],
                created_by=instance.created_by,
                updated_by=instance.updated_by,
            )
            print()
        return instance

    def update(self, instance, validated_data):
        validated_data.pop('location_uid', None)
        validated_data.pop('receive_items', None)  # Prevent updating receive items here
        return super().update(instance, validated_data)

class OxygenReceivingVerifySerializer(serializers.Serializer):
    item_uids=serializers.ListField(write_only=True,min_length=1)

    class Meta:
        model = OxygenReceiving
        fields = ['remarks','status', 'item_uids']

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)




class OxygenAllocationItemInputSerializer(serializers.Serializer):
    volume_uid = serializers.UUIDField(write_only=True)
    quantity = serializers.IntegerField(min_value=1)

    def validate(self, data):
        volume_uid = data.get('volume_uid')

        # Validate volume
        try:
            volume = OxygenVolume.objects.get(uid=volume_uid, is_deleted=False)
            data['volume'] = volume
        except OxygenVolume.DoesNotExist:
            raise serializers.ValidationError({"volume_uid": f"Volume {volume_uid} not found or deleted"})

        return data

# user for view only isn't used for insert
class OxygenAllocationItemSerializer(serializers.ModelSerializer):
    volume = OxygenVolumeSerializer(read_only=True)
    verify_by = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OxygenAllocationItem
        fields = [
            'uid','volume', 'quantity','status','verify_date','verify_by',
        ]
        read_only_fields = ['uid', 'status', 'verify_date', 'verify_by']

    def get_verify_by(self, obj):
        if obj.verify_by:
            user = obj.verify_by
            if user:
                return {
                    'uid': user.guid,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
        return None

# OxygenAllocationSerializer
class OxygenAllocationSerializer(serializers.ModelSerializer):
    location_from_uid = serializers.UUIDField(write_only=True)
    location_to_uid = serializers.UUIDField(write_only=True)
    date = serializers.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "iso-8601"]
    )
    allocation_details = OxygenAllocationItemSerializer(source='allocation_items',read_only=True, many=True)

    allocation_items = OxygenAllocationItemInputSerializer(write_only=True, many=True)
    allocated_by = serializers.SerializerMethodField(read_only=True)

    location_from = LocationOxygenSerializer(read_only=True)
    location_to = LocationOxygenSerializer(read_only=True)
    class Meta:
        model = OxygenAllocation
        fields = [
            'uid', 'location_from', 'location_to', 'allocation_items','allocation_details',  'status','remarks',
            'created_at', 'updated_at', 'location_from_uid', 'location_to_uid','date','quantity', 'allocated_by'
        ]
        read_only_fields = ['uid', 'created_at', 'status', 'updated_at']


    def get_allocated_by(self, obj):
        if obj.created_by:
                return {
                    'uid': obj.created_by.guid,
                    'name': f'{obj.created_by.first_name} {obj.created_by.last_name}',
                }
        return None

    def validate(self, data):
        location_from_uid = data.get('location_from_uid')
        location_to_uid = data.get('location_to_uid')

        if str(location_from_uid) == str(location_to_uid):
            raise serializers.ValidationError({"location_to_uid": "You Can not Allocate to Same Location"})

        try:
            data['location_from'] = OxygenLocation.objects.get(uid=location_from_uid, is_deleted=False)
        except OxygenLocation.DoesNotExist:
            raise serializers.ValidationError({"location_from_uid": "Invalid Location, not found or deleted"})

        try:
            data['location_to'] = OxygenLocation.objects.get(uid=location_to_uid, is_deleted=False)
        except OxygenLocation.DoesNotExist:
            raise serializers.ValidationError({"location_to_uid": "Invalid Location, not found or deleted"})

        return data

    def create(self, validated_data):
        receive_items_data = validated_data.pop('allocation_items', [])
        validated_data.pop('location_from_uid', None)
        validated_data.pop('location_to_uid', None)

        # Compute total quantity from receiver items
        total_quantity = sum(item.get('quantity', 0) for item in receive_items_data)
        validated_data['quantity'] = total_quantity
        instance = OxygenAllocation.objects.create(**validated_data)

        # Create each item individually
        for item in receive_items_data:
            OxygenAllocationItem.objects.create(
                allocation=instance,
                volume=item['volume'],
                quantity=item['quantity'],
                created_by=instance.created_by,
                updated_by=instance.updated_by,
            )
        return instance

    def update(self, instance, validated_data):
        validated_data.pop('location_from_uid', None)
        validated_data.pop('location_to_uid', None)
        validated_data.pop('allocation_items', None)
        return super().update(instance, validated_data)

class OxygenAllocationVerifySerializer(serializers.Serializer):
    item_uids=serializers.ListField(write_only=True,min_length=1)

    class Meta:
        model = OxygenAllocation
        fields = ['remarks','status', 'item_uids']

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

class PatientAgeGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientAgeGroup
        fields = ['uid', 'name', 'min_age','max_age','is_active', 'created_at', 'updated_at']
        read_only_fields = ['uid', 'created_at', 'updated_at']


class UsageItemsSerializer(serializers.Serializer):
    patient_age_group_uid = serializers.UUIDField(write_only=True)
    patient_age_group = PatientAgeGroupSerializer(read_only=True)
    oxygen = serializers.IntegerField(required=False, default=0)
    ventilator = serializers.IntegerField(required=False, default=0)
    cpap = serializers.IntegerField(required=False, default=0)
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)


    class Meta:
        model = OxygenUsagePatientAgeGroup
        fields = [
            'uid', 'oxygen', 'cpap', 'remarks', 'created_at', 'updated_at',
            'patient_age_group', 'patient_age_group_uid'
        ]
        read_only_fields = ['uid','oxygen_usage','patient_age_group', 'created_at', 'updated_at']


    def create(self, validated_data):
        validated_data.pop('patient_age_group_uid')
        return OxygenUsagePatientAgeGroup.objects.create(**validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('patient_age_group_uid')
        return super().update(instance, validated_data)

class LocationalOxygenUsageSerializer(serializers.ModelSerializer):
    location_uid = serializers.UUIDField(write_only=True)
    date = serializers.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "iso-8601"]
    )
    used_by = serializers.SerializerMethodField()

    location = LocationOxygenSerializer(read_only=True)
    patient_age_groups = UsageItemsSerializer(many=True, required=True)

    class Meta:
        model = LocationalOxygenUsage
        fields = [
            'uid', 'location', 'date', 'remarks', 'status', 'created_at',
            'used_by','updated_at','location_uid','patient_age_groups',
        ]
        read_only_fields = ['uid', 'created_at', 'status', 'updated_at']

    def get_used_by(self, obj):
        if obj.created_by:
                return {
                    'uid': obj.created_by.guid,
                    'name': f'{obj.created_by.first_name} {obj.created_by.last_name}',
                }
        return None


    @transaction.atomic
    def create(self, validated_data):
        patient_age_groups_data = validated_data.pop('patient_age_groups', [])
        location_uid = validated_data.pop('location_uid')


        try:
            location = OxygenLocation.objects.get(uid=location_uid, is_deleted=False)
        except OxygenLocation.DoesNotExist:
            raise serializers.ValidationError({"location_uid": "Invalid location UID. or Deleted"})

        validated_data['location'] = location
        usage = LocationalOxygenUsage.objects.create(**validated_data)

        # Prepare a list of instances to bulk_create
        age_group_instances = []

        for patient_age_group_data in patient_age_groups_data:
            patient_age_group_uid = patient_age_group_data.pop('patient_age_group_uid', None)

            if not patient_age_group_uid:
                raise serializers.ValidationError({"patient_age_groups": "Please specify a patient age groups"})
            try:
                patient_age_group = PatientAgeGroup.objects.get(uid=patient_age_group_uid, is_active=True)
            except PatientAgeGroup.DoesNotExist:
                raise serializers.ValidationError(
                    {"patient_age_groups": f"Invalid patient age group UID: {patient_age_group_uid}"})

            instance = OxygenUsagePatientAgeGroup(
                oxygen_usage=usage,
                patient_age_group=patient_age_group,
                **patient_age_group_data
            )
            age_group_instances.append(instance)

        if age_group_instances:

            OxygenUsagePatientAgeGroup.objects.bulk_create(age_group_instances)

        return usage

    def update(self, instance, validated_data):
        validated_data.pop('location_uid', None)
        validated_data.pop('patient_age_groups', None)  # Do not handle nested update here
        return super().update(instance, validated_data)


class OxygenUsagePatientAgeGroupSerializer(serializers.Serializer):
    patient_age_group_uid = serializers.UUIDField()
    oxygen_usage_uid = serializers.UUIDField()

    oxygen_usage = LocationalOxygenUsageSerializer(read_only=True)
    patient_age_group = PatientAgeGroupSerializer(read_only=True)

    class Meta:
        model = OxygenUsagePatientAgeGroup
        fields = [
            'uid', 'oxygen', 'cpap', 'remarks', 'created_at', 'updated_at',
            'patient_age_group', 'patient_age_group_uid', 'oxygen_usage', 'oxygen_usage_uid'
        ]
        read_only_fields = ['uid', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data.pop('patient_age_group_uid')
        validated_data.pop('oxygen_usage_uid')
        return OxygenUsagePatientAgeGroup.objects.create(**validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('patient_age_group_uid')
        validated_data.pop('oxygen_usage_uid')
        return super().update(instance, validated_data)


class UsageReportSerializer(serializers.Serializer):
    date = serializers.DateTimeField(
        format="%d-%m-%Y %H:%M",
        input_formats=["%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M"]
    )
    location = LocationOxygenSerializer(read_only=True)
    patient_age_groups = UsageItemsSerializer(many=True, required=True)
    report_file = serializers.CharField(read_only=True, required=False)
