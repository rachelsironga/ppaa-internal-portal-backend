from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Block, Department, Clinic, PaymentMode, Attendance, PatientAttendance

User = get_user_model()


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        super().__init__(*args, **kwargs)

        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class AuditMixin(serializers.ModelSerializer):
    """Mixin for audit fields with standardized formatting"""
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    created_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    updated_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    deleted_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    
    created_by_details = serializers.SerializerMethodField()
    updated_by_details = serializers.SerializerMethodField()
    
    def get_user_details(self, user):
        if not user:
            return None
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
    
    def get_created_by_details(self, obj):
        try:
            return self.get_user_details(obj.created_by)
        except User.DoesNotExist:
            return {'id': obj.created_by_id} if obj.created_by_id else None
    
    def get_updated_by_details(self, obj):
        try:
            return self.get_user_details(obj.updated_by)
        except User.DoesNotExist:
            return {'id': obj.updated_by_id} if obj.updated_by_id else None


class BaseModelSerializer(AuditMixin, DynamicFieldsModelSerializer):
    """Base serializer with common functionality for all models"""
    uid = serializers.UUIDField(read_only=True)
    is_deleted = serializers.BooleanField(read_only=True)
    
    class Meta:
        fields = [
            'uid', 'created_at', 'updated_at', 'deleted_at', 'is_deleted', 
            'created_by_id', 'updated_by_id', 'deleted_by_id',
            'created_by_details', 'updated_by_details'
        ]


class SaveWithRequestUserMixin:
    """Mixin to handle setting created_by/updated_by from request user"""
    
    def save(self, **kwargs):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        
        if user and user.is_authenticated:
            if self.instance is None:
                kwargs['created_by'] = user
            kwargs['updated_by'] = user
        
        return super().save(**kwargs)


class RelatedFieldMixin:
    """Mixin for common related field patterns"""
    
    @staticmethod
    def get_related_name(source, read_only=True):
        return serializers.CharField(source=f'{source}.name', read_only=read_only)
    
    @staticmethod
    def get_user_full_name(source, read_only=True):
        return serializers.SerializerMethodField(read_only=read_only)


# =====================
# Block Serializers
# =====================
class BlockSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    class Meta:
        model = Block
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'code', 'location', 'description', 'is_active'
        ]

    def validate_code(self, value):
        instance = getattr(self, 'instance', None)
        qs = Block.objects.filter(code__iexact=value)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A block with this code already exists.')
        return value


class BlockListSerializer(BaseModelSerializer):
    class Meta:
        model = Block
        fields = ['uid', 'name', 'code', 'location', 'is_active']


# =====================
# Clinic Serializers
# =====================
class ClinicSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    block_id = serializers.IntegerField(read_only=True, allow_null=True)
    department_id = serializers.IntegerField(read_only=True, allow_null=True)
    block_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    block_details = serializers.SerializerMethodField()
    department_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Clinic
        fields = BaseModelSerializer.Meta.fields + [
            'block_id', 'block_name', 'block_details',
            'department_id', 'department_name', 'department_details',
            'name', 'code', 'description', 'is_active'
        ]
    
    def get_block_name(self, obj):
        try:
            if obj.block:
                return obj.block.name
        except Block.DoesNotExist:
            pass
        return None
    
    def get_department_name(self, obj):
        try:
            if obj.department:
                return obj.department.name
        except Department.DoesNotExist:
            pass
        return None
    
    def get_block_details(self, obj):
        try:
            if obj.block:
                return {
                    'uid': str(obj.block.uid),
                    'name': obj.block.name,
                    'code': obj.block.code
                }
        except Block.DoesNotExist:
            return {'id': obj.block_id} if obj.block_id else None
        return None
    
    def get_department_details(self, obj):
        try:
            if obj.department:
                return {
                    'uid': str(obj.department.uid),
                    'name': obj.department.name,
                    'code': obj.department.code
                }
        except Department.DoesNotExist:
            return {'id': obj.department_id} if obj.department_id else None
        return None
    
    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        if 'block' in data and data['block']:
            try:
                block = Block.objects.get(uid=data['block'])
                data['block'] = block.id
            except Block.DoesNotExist:
                raise serializers.ValidationError({'block': 'Block not found with the provided UID'})
        elif 'block' in data and data['block'] == '':
            data['block'] = None
        
        if 'department' in data and data['department']:
            try:
                department = Department.objects.using('default').get(uid=data['department'])
                data['department'] = department.id
            except Department.DoesNotExist:
                raise serializers.ValidationError({'department': 'Department not found with the provided UID'})
        elif 'department' in data and data['department'] == '':
            data['department'] = None
            
        return super().to_internal_value(data)


class ClinicListSerializer(BaseModelSerializer):
    block_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Clinic
        fields = ['uid', 'name', 'code', 'block_name', 'department_name', 'is_active']
    
    def get_block_name(self, obj):
        try:
            if obj.block:
                return obj.block.name
        except Block.DoesNotExist:
            pass
        return None
    
    def get_department_name(self, obj):
        try:
            if obj.department:
                return obj.department.name
        except Department.DoesNotExist:
            pass
        return None


class ClinicDetailSerializer(ClinicSerializer):
    block = BlockListSerializer(read_only=True)
    
    class Meta(ClinicSerializer.Meta):
        pass


# =====================
# PaymentMode Serializers
# =====================
class PaymentModeSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    class Meta:
        model = PaymentMode
        fields = BaseModelSerializer.Meta.fields + [
            'name', 'code', 'description', 'is_active'
        ]

    def validate_code(self, value):
        instance = getattr(self, 'instance', None)
        qs = PaymentMode.objects.filter(code__iexact=value)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A payment mode with this code already exists.')
        return value


class PaymentModeListSerializer(BaseModelSerializer):
    class Meta:
        model = PaymentMode
        fields = ['uid', 'name', 'code', 'is_active']


# =====================
# Attendance Serializers
# =====================
class AttendanceSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    processed_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    processed_by_name = serializers.SerializerMethodField()
    processed_by_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Attendance
        fields = BaseModelSerializer.Meta.fields + [
            'date', 'attendance_report',
            'total_new_patients', 'total_follow_up_patients', 'grand_total_patients',
            'notes', 'processed_date', 'processed_by_id', 'processed_by_name', 'processed_by_details',
            'total_column', 'success_colums', 'failed_colums', 'is_active'
        ]
    
    def get_processed_by_name(self, obj):
        try:
            if obj.processed_by:
                return f"{obj.processed_by.first_name} {obj.processed_by.last_name}"
        except User.DoesNotExist:
            return None
        return None
    
    def get_processed_by_details(self, obj):
        try:
            if obj.processed_by:
                return {
                    'id': obj.processed_by.id,
                    'guid': str(obj.processed_by.guid),
                    'username': obj.processed_by.username,
                    'email': obj.processed_by.email,
                    'full_name': obj.processed_by.get_full_name()
                }
        except User.DoesNotExist:
            return {'id': obj.processed_by_id} if obj.processed_by_id else None
        return None
    
    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        if 'processed_by' in data and data['processed_by']:
            try:
                user = User.objects.using('default').get(guid=data['processed_by'])
                data['processed_by'] = user.id
            except User.DoesNotExist:
                raise serializers.ValidationError({'processed_by': 'User not found with the provided GUID'})
        elif 'processed_by' in data and data['processed_by'] == '':
            data['processed_by'] = None
        
        if 'processed_date' in data and data['processed_date'] == '':
            data['processed_date'] = None
            
        return super().to_internal_value(data)


class AttendanceListSerializer(BaseModelSerializer):
    class Meta:
        model = Attendance
        fields = [
            'uid', 'date', 'total_new_patients', 'total_follow_up_patients',
            'grand_total_patients', 'processed_date', 'is_active'
        ]


class AttendanceDetailSerializer(AttendanceSerializer):
    patient_attendances = serializers.SerializerMethodField()
    
    class Meta(AttendanceSerializer.Meta):
        fields = AttendanceSerializer.Meta.fields + ['patient_attendances']
    
    def get_patient_attendances(self, obj):
        patient_attendances = PatientAttendance.objects.filter(attendance=obj)
        return PatientAttendanceListSerializer(patient_attendances, many=True).data


# =====================
# PatientAttendance Serializers
# =====================
class PatientAttendanceSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    attendance_date = serializers.DateField(source='attendance.date', read_only=True)
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    payment_name = serializers.CharField(source='payment.name', read_only=True)
    clinic_details = serializers.SerializerMethodField()
    payment_details = serializers.SerializerMethodField()
    
    class Meta:
        model = PatientAttendance
        fields = BaseModelSerializer.Meta.fields + [
            'attendance', 'attendance_date',
            'clinic', 'clinic_name', 'clinic_details',
            'payment', 'payment_name', 'payment_details',
            'new_patients', 'follow_up_patients', 'total_patients', 'is_active'
        ]
    
    def get_clinic_details(self, obj):
        if obj.clinic:
            return {
                'uid': str(obj.clinic.uid),
                'name': obj.clinic.name,
                'code': obj.clinic.code
            }
        return None
    
    def get_payment_details(self, obj):
        if obj.payment:
            return {
                'uid': str(obj.payment.uid),
                'name': obj.payment.name,
                'code': obj.payment.code
            }
        return None
    
    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        if 'attendance' in data and data['attendance']:
            try:
                attendance = Attendance.objects.get(uid=data['attendance'])
                data['attendance'] = attendance.id
            except Attendance.DoesNotExist:
                raise serializers.ValidationError({'attendance': 'Attendance not found with the provided UID'})
        
        if 'clinic' in data and data['clinic']:
            try:
                clinic = Clinic.objects.get(uid=data['clinic'])
                data['clinic'] = clinic.id
            except Clinic.DoesNotExist:
                raise serializers.ValidationError({'clinic': 'Clinic not found with the provided UID'})
        
        if 'payment' in data and data['payment']:
            try:
                payment = PaymentMode.objects.get(uid=data['payment'])
                data['payment'] = payment.id
            except PaymentMode.DoesNotExist:
                raise serializers.ValidationError({'payment': 'Payment mode not found with the provided UID'})
            
        return super().to_internal_value(data)
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.attendance:
            representation['attendance'] = str(instance.attendance.uid)
        if instance.clinic:
            representation['clinic'] = str(instance.clinic.uid)
        if instance.payment:
            representation['payment'] = str(instance.payment.uid)
        return representation


class PatientAttendanceListSerializer(BaseModelSerializer):
    attendance_date = serializers.DateField(source='attendance.date', read_only=True)
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    payment_name = serializers.CharField(source='payment.name', read_only=True)
    
    class Meta:
        model = PatientAttendance
        fields = [
            'uid', 'attendance_date', 'clinic_name', 'payment_name',
            'new_patients', 'follow_up_patients', 'total_patients'
        ]


class PatientAttendanceDetailSerializer(PatientAttendanceSerializer):
    attendance = AttendanceListSerializer(read_only=True)
    clinic = ClinicListSerializer(read_only=True)
    payment = PaymentModeListSerializer(read_only=True)
    
    class Meta(PatientAttendanceSerializer.Meta):
        pass


# =====================
# Bulk/Search Serializers
# =====================
class PatientAttendanceBulkCreateSerializer(serializers.Serializer):
    """Serializer for bulk creating patient attendance records"""
    attendance = serializers.UUIDField()
    records = serializers.ListField(
        child=serializers.DictField(),
        min_length=1
    )
    
    def validate_attendance(self, value):
        try:
            Attendance.objects.get(uid=value)
        except Attendance.DoesNotExist:
            raise serializers.ValidationError('Attendance not found with the provided UID')
        return value


class AttendanceSummarySerializer(serializers.Serializer):
    """Serializer for attendance summary/dashboard"""
    total_attendances = serializers.IntegerField()
    total_new_patients = serializers.IntegerField()
    total_follow_up_patients = serializers.IntegerField()
    grand_total_patients = serializers.IntegerField()
    date_range_start = serializers.DateField()
    date_range_end = serializers.DateField()


class ClinicPatientVolumeSerializer(serializers.Serializer):
    """Serializer for clinic patient volume analytics"""
    clinic_uid = serializers.UUIDField()
    clinic_name = serializers.CharField()
    total_patients = serializers.IntegerField()
    new_patients = serializers.IntegerField()
    follow_up_patients = serializers.IntegerField()
    growth_rate = serializers.FloatField(allow_null=True)
