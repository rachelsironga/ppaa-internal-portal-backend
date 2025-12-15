# mnh_training/serializers.py
from rest_framework import serializers
from django.db import transaction
from django.contrib.auth import get_user_model

from mnh_auth.serializers import UserSerializer
from mnh_auth.models import Department
try:
    from mnh_auth.models import Country
except ImportError:
    Country = None

from .models import (
    Affiliation, Student, Application, DepartmentAllocation,
    Supervisor, Institution, MOU, TrainingBatch
)

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
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    updated_by = serializers.PrimaryKeyRelatedField(read_only=True)
    deleted_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    # User details for read operations
    created_by_details = serializers.SerializerMethodField()
    updated_by_details = serializers.SerializerMethodField()
    
    def get_user_details(self, user):
        """Helper method to get user details"""
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
        return self.get_user_details(obj.created_by)
    
    def get_updated_by_details(self, obj):
        return self.get_user_details(obj.updated_by)


class BaseModelSerializer(AuditMixin, DynamicFieldsModelSerializer):
    """Base serializer with common functionality for all models"""
    uid = serializers.UUIDField(read_only=True)
    is_deleted = serializers.BooleanField(read_only=True)
    
    class Meta:
        fields = [
            'uid', 'created_at', 'updated_at', 'deleted_at', 'is_deleted', 
            'created_by', 'updated_by', 'deleted_by',
            'created_by_details', 'updated_by_details'
        ]


class RelatedFieldMixin:
    """Mixin for common related field patterns"""
    
    @staticmethod
    def get_related_name(source, read_only=True):
        """Helper to create related name fields"""
        return serializers.CharField(source=f'{source}.name', read_only=read_only)
    
    @staticmethod
    def get_user_full_name(source, read_only=True):
        """Helper to get user's full name"""
        return serializers.SerializerMethodField(read_only=read_only)


class SaveWithRequestUserMixin:
    """Mixin to handle setting created_by/updated_by from request user"""
    
    def save(self, **kwargs):
        """Set created_by/updated_by from request user"""
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        
        if user and user.is_authenticated:
            if self.instance is None:
                kwargs['created_by'] = user
            kwargs['updated_by'] = user
        
        return super().save(**kwargs)


class DateValidationMixin:
    """Mixin for common date validation patterns"""
    
    @staticmethod
    def validate_dates(start_field, end_field, data):
        """Validate that end date is after start date"""
        start_date = data.get(start_field)
        end_date = data.get(end_field)
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({
                end_field: f'{end_field} must be after {start_field}'
            })
        return data


# Country Serializer
class CountrySerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    class Meta:
        model = Country
        fields = BaseModelSerializer.Meta.fields + ['name', 'code', 'is_active']


# Affiliation Serializer
class AffiliationSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    country_name = RelatedFieldMixin.get_related_name('country')
    application_number = serializers.CharField(source='application.application_number', read_only=True)
    
    class Meta:
        model = Affiliation
        fields = BaseModelSerializer.Meta.fields + [
            'application', 'application_number', 'type', 'name', 'level', 'year',
            'course', 'address', 'country', 'country_name', 'is_active'
        ]
    
    def validate(self, data):
        """Validate affiliation data"""
        affiliation_type = data.get('type')
        level = data.get('level')
        
        # If type is ACADEMIC, level must be provided
        if affiliation_type == Affiliation.AffiliationType.ACADEMIC and not level:
            raise serializers.ValidationError({
                'level': 'Level is required for Academic affiliations'
            })
        
        return data


# Student Serializer
class StudentSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    full_name = serializers.CharField(source='full_name', read_only=True)
    nationality_name = RelatedFieldMixin.get_related_name('nationality')
    country_of_birth_name = RelatedFieldMixin.get_related_name('country_of_birth')
    affiliation_details = serializers.SerializerMethodField()
    
    def get_affiliation_details(self, obj):
        if obj.affiliation:
            return {
                'uid': str(obj.affiliation.uid),
                'name': obj.affiliation.name,
                'type': obj.affiliation.get_type_display()
            }
        return None
    
    class Meta:
        model = Student
        fields = BaseModelSerializer.Meta.fields + [
            'profile_picture', 'first_name', 'middle_name', 'last_name', 'full_name',
            'sex', 'primary_phone', 'secondary_phone', 'email', 'id_type', 'copy_of_id',
            'student_id', 'nationality', 'nationality_name', 'country_of_birth',
            'country_of_birth_name', 'bio', 'are_you_currently_studying',
            'type', 'supporting_letter', 'affiliation', 'affiliation_details', 'is_active'
        ]
        read_only_fields = ['type', 'full_name']
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        instance = self.instance
        qs = Student.objects.filter(email__iexact=value, is_deleted=False)
        if instance:
            qs = qs.exclude(uid=instance.uid)
        if qs.exists():
            raise serializers.ValidationError("A student with this email already exists.")
        return value
    
    def validate_primary_phone(self, value):
        """Validate phone uniqueness"""
        instance = self.instance
        qs = Student.objects.filter(primary_phone=value, is_deleted=False)
        if instance:
            qs = qs.exclude(uid=instance.uid)
        if qs.exists():
            raise serializers.ValidationError("A student with this phone already exists.")
        return value


class StudentListSerializer(StudentSerializer):
    """Lightweight student serializer for list endpoints"""
    affiliation_details = None
    
    class Meta:
        model = Student
        fields = BaseModelSerializer.Meta.fields + [
            'first_name', 'last_name', 'full_name', 'email', 'student_id',
            'sex', 'primary_phone', 'type', 'is_active'
        ]


# Application Serializer
class ApplicationSerializer(SaveWithRequestUserMixin, BaseModelSerializer, DateValidationMixin):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    department_names = serializers.CharField(read_only=True)
    placement_type_display = serializers.CharField(source='get_placement_type_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    campus_display = serializers.CharField(source='get_campus_display', read_only=True)
    
    class Meta:
        model = Application
        fields = BaseModelSerializer.Meta.fields + [
            'user', 'student', 'student_name', 'application_number',
            'departments', 'department_names', 'duration', 'from_date', 'to_date',
            'category', 'category_display', 'placement_type', 'placement_type_display',
            'expected_amount', 'currency', 'campus', 'campus_display',
            'supporting_letter', 'is_active'
        ]
    
    def validate(self, data):
        """Validate application data"""
        # Check date consistency
        data = self.validate_dates('from_date', 'to_date', data)
        
        # Validate either student or user is provided
        if not data.get('student') and not data.get('user'):
            raise serializers.ValidationError(
                'Either student or user must be provided'
            )
        
        return data


class ApplicationListSerializer(ApplicationSerializer):
    """Lightweight application serializer for list endpoints"""
    class Meta:
        model = Application
        fields = BaseModelSerializer.Meta.fields + [
            'student', 'student_name', 'application_number', 'placement_type',
            'placement_type_display', 'from_date', 'to_date', 'is_active'
        ]


# Department Allocation Serializer
class DepartmentAllocationSerializer(SaveWithRequestUserMixin, BaseModelSerializer, DateValidationMixin):
    department_name = RelatedFieldMixin.get_related_name('department')
    application_number = serializers.CharField(source='application.application_number', read_only=True)
    supervisor_name = serializers.SerializerMethodField()
    duration_days = serializers.IntegerField(read_only=True)
    
    def get_supervisor_name(self, obj):
        if obj.supervisor:
            return str(obj.supervisor.user)
        return None
    
    class Meta:
        model = DepartmentAllocation
        fields = BaseModelSerializer.Meta.fields + [
            'application', 'application_number', 'department', 'department_name',
            'supervisor', 'supervisor_name', 'start_date', 'end_date',
            'duration_days', 'description', 'is_active'
        ]
    
    def validate(self, data):
        """Validate allocation dates"""
        return self.validate_dates('start_date', 'end_date', data)


# Supervisor Serializer
class SupervisorSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    department_name = RelatedFieldMixin.get_related_name('department')
    
    class Meta:
        model = Supervisor
        fields = BaseModelSerializer.Meta.fields + [
            'user', 'user_name', 'department', 'department_name',
            'description', 'is_active'
        ]


# Institution Serializer
class InstitutionSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    country_name = RelatedFieldMixin.get_related_name('country')
    mou_count = serializers.SerializerMethodField()
    
    def get_mou_count(self, obj):
        return obj.mous.filter(is_deleted=False).count()
    
    class Meta:
        model = Institution
        fields = BaseModelSerializer.Meta.fields + [
            'institution_code', 'name', 'address', 'country', 'country_name',
            'contact_person', 'contact_email', 'contact_phone', 'website',
            'institution_type', 'established_date', 'mou_count', 'is_active'
        ]
    
    def validate(self, data):
        """Validate institution data"""
        instance = self.instance
        
        # Validate unique institution_code
        if data.get('institution_code'):
            qs = Institution.objects.filter(
                institution_code=data['institution_code'],
                is_deleted=False
            )
            if instance:
                qs = qs.exclude(uid=instance.uid)
            if qs.exists():
                raise serializers.ValidationError({
                    'institution_code': 'This code already exists'
                })
        
        return data


class InstitutionListSerializer(InstitutionSerializer):
    """Lightweight institution serializer for list endpoints"""
    class Meta:
        model = Institution
        fields = BaseModelSerializer.Meta.fields + [
            'institution_code', 'name', 'institution_type', 'mou_count', 'is_active'
        ]


# MOU Serializer
class MOUSerializer(SaveWithRequestUserMixin, BaseModelSerializer, DateValidationMixin):
    institution_name = RelatedFieldMixin.get_related_name('institution')
    duration_display = serializers.CharField(read_only=True)
    expiration_status = serializers.SerializerMethodField()
    
    def get_expiration_status(self, obj):
        return obj.expiration_status()
    
    class Meta:
        model = MOU
        fields = BaseModelSerializer.Meta.fields + [
            'institution', 'institution_name', 'mou_number', 'start_date', 'end_date',
            'purpose', 'terms_and_conditions', 'signed_by', 'signed_date',
            'document', 'duration_display', 'expiration_status', 'is_active'
        ]
    
    def validate(self, data):
        """Validate MOU data"""
        return self.validate_dates('start_date', 'end_date', data)


class MOUListSerializer(MOUSerializer):
    """Lightweight MOU serializer for list endpoints"""
    class Meta:
        model = MOU
        fields = BaseModelSerializer.Meta.fields + [
            'institution', 'institution_name', 'mou_number', 'start_date', 'end_date',
            'expiration_status', 'is_active'
        ]


# Training Batch Serializer
class TrainingBatchSerializer(SaveWithRequestUserMixin, BaseModelSerializer, DateValidationMixin):
    mou_number = serializers.CharField(source='mou.mou_number', read_only=True)
    institution_name = serializers.CharField(source='mou.institution.name', read_only=True)
    department_names = serializers.SerializerMethodField()
    duration_display = serializers.CharField(read_only=True)
    cancelled_by_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    def get_department_names(self, obj):
        return list(obj.departments.values_list('name', flat=True))
    
    def get_cancelled_by_name(self, obj):
        if obj.cancelled_by:
            return f"{obj.cancelled_by.first_name} {obj.cancelled_by.last_name}"
        return None
    
    class Meta:
        model = TrainingBatch
        fields = BaseModelSerializer.Meta.fields + [
            'batch_number', 'mou', 'mou_number', 'institution_name',
            'number_of_students', 'departments', 'department_names',
            'invoiced_amount', 'currency', 'training_start_date', 'training_end_date',
            'duration_display', 'application_letter', 'status', 'status_display',
            'notes', 'cancellation_reason', 'cancelled_by', 'cancelled_by_name',
            'cancelled_at', 'is_active'
        ]
        read_only_fields = ['batch_number', 'duration_display']
    
    def validate(self, data):
        """Validate training batch data"""
        return self.validate_dates('training_start_date', 'training_end_date', data)


class TrainingBatchListSerializer(TrainingBatchSerializer):
    """Lightweight training batch serializer for list endpoints"""
    class Meta:
        model = TrainingBatch
        fields = BaseModelSerializer.Meta.fields + [
            'batch_number', 'mou_number', 'institution_name',
            'training_start_date', 'training_end_date',
            'status', 'status_display', 'is_active'
        ]


# Detail Serializers with nested relationships
class AffiliationDetailSerializer(AffiliationSerializer):
    country = CountrySerializer(read_only=True)


class StudentDetailSerializer(StudentSerializer):
    nationality = CountrySerializer(read_only=True)
    country_of_birth = CountrySerializer(read_only=True)
    affiliation = AffiliationSerializer(read_only=True)


class ApplicationDetailSerializer(ApplicationSerializer):
    student = StudentListSerializer(read_only=True)
    departments = serializers.SerializerMethodField()
    
    def get_departments(self, obj):
        deps = obj.departments.all()
        return [{'id': d.id, 'name': d.name} for d in deps]


class DepartmentAllocationDetailSerializer(DepartmentAllocationSerializer):
    application = ApplicationListSerializer(read_only=True)
    supervisor = SupervisorSerializer(read_only=True)


class MOUDetailSerializer(MOUSerializer):
    institution = InstitutionListSerializer(read_only=True)


class TrainingBatchDetailSerializer(TrainingBatchSerializer):
    mou = MOUListSerializer(read_only=True)


# Bulk and Search Serializers
class StudentBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk student updates"""
    student_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    are_you_currently_studying = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)


class ApplicationSearchSerializer(serializers.Serializer):
    """Serializer for application search functionality"""
    query = serializers.CharField(required=False)
    placement_type = serializers.ChoiceField(
        choices=Application.PlacementType.choices,
        required=False
    )
    category = serializers.ChoiceField(
        choices=Application.Category.choices,
        required=False
    )
    status = serializers.CharField(required=False)
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)

