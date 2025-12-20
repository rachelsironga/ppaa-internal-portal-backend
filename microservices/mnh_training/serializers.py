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


class UUIDRelatedField(serializers.PrimaryKeyRelatedField):
    """Custom related field that handles UUID strings and converts them to model instance"""
    
    def to_internal_value(self, data):
        """Convert UUID string to model instance"""
        try:
            # If data is a UUID string, find the object by uid and return it
            if isinstance(data, str):
                obj = self.get_queryset().filter(uid=data).first()
                if obj:
                    return obj
            # Otherwise, treat it as pk directly (fallback to parent behavior)
            return super().to_internal_value(data)
        except Exception as e:
            self.fail(f'Invalid value: {str(e)}')
    
    def to_representation(self, value):
        """Convert pk to UUID string in response"""
        try:
            if value:
                obj = self.get_queryset().filter(pk=value).first()
                if obj:
                    return str(obj.uid)
            return None
        except Exception:
            return super().to_representation(value)


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


# Minimal Serializers for nested relationships (read-only)
class CountryMinimalSerializer(serializers.ModelSerializer):
    """Minimal country serializer for nested display"""
    class Meta:
        model = Country
        fields = ['uid', 'name', 'iso_code']


class AffiliationMinimalSerializer(serializers.ModelSerializer):
    """Minimal affiliation serializer for nested display"""
    class Meta:
        model = Affiliation
        fields = ['uid', 'name', 'type', 'level', 'course']


class StudentMinimalSerializer(serializers.ModelSerializer):
    """Minimal student serializer for nested display"""
    full_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = Student
        fields = ['uid', 'first_name', 'last_name', 'full_name', 'email', 'student_id']


class ApplicationMinimalSerializer(serializers.ModelSerializer):
    """Minimal application serializer for nested display"""
    student = StudentMinimalSerializer(read_only=True)
    reference_number = serializers.CharField(read_only=True)
    
    class Meta:
        model = Application
        fields = ['uid', 'application_number', 'reference_number', 'placement_type', 'from_date', 'to_date', 'student']


class SupervisorMinimalSerializer(serializers.ModelSerializer):
    """Minimal supervisor serializer for nested display"""
    class Meta:
        model = Supervisor
        fields = ['uid', 'user_guid', 'department_uid', 'description']


class InstitutionMinimalSerializer(serializers.ModelSerializer):
    """Minimal institution serializer for nested display"""
    class Meta:
        model = Institution
        fields = ['uid', 'name', 'institution_code', 'institution_type']


class MOUMinimalSerializer(serializers.ModelSerializer):
    """Minimal MOU serializer for nested display"""
    class Meta:
        model = MOU
        fields = ['uid', 'mou_number', 'start_date', 'end_date']


class DepartmentMinimalSerializer(serializers.ModelSerializer):
    """Minimal department serializer for nested display"""
    class Meta:
        model = Department
        fields = ['uid', 'name', 'code']


# Country Serializer
class CountrySerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    class Meta:
        model = Country
        fields = BaseModelSerializer.Meta.fields + ['name', 'code', 'is_active']


# Affiliation Serializer
class AffiliationSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    # For write operations - accept UUID strings
    country_uid = UUIDRelatedField(
        queryset=Country.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
        write_only=True,
        source='country'
    )
    application_uid = UUIDRelatedField(
        queryset=Application.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
        write_only=True,
        source='application'
    )
    # For read operations - return nested objects
    country = CountryMinimalSerializer(read_only=True)
    application = ApplicationMinimalSerializer(read_only=True)
    
    class Meta:
        model = Affiliation
        fields = BaseModelSerializer.Meta.fields + [
            'application', 'application_uid', 'type', 'name', 'level', 'year',
            'course', 'address', 'country', 'country_uid', 'is_active'
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
    full_name = serializers.CharField(read_only=True)
    # For write operations - accept UUID strings
    nationality_uid = UUIDRelatedField(
        queryset=Country.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
        write_only=True,
        source='nationality'
    )
    country_of_birth_uid = UUIDRelatedField(
        queryset=Country.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
        write_only=True,
        source='country_of_birth'
    )
    affiliation_uid = UUIDRelatedField(
        queryset=Affiliation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
        write_only=True,
        source='affiliation'
    )
    # For read operations - return nested objects
    nationality = CountryMinimalSerializer(read_only=True)
    country_of_birth = CountryMinimalSerializer(read_only=True)
    affiliation = AffiliationMinimalSerializer(read_only=True)
    
    class Meta:
        model = Student
        fields = BaseModelSerializer.Meta.fields + [
            'profile_picture', 'first_name', 'middle_name', 'last_name', 'full_name',
            'sex', 'primary_phone', 'secondary_phone', 'email', 'id_type', 'copy_of_id',
            'student_id', 'nationality', 'nationality_uid', 'country_of_birth',
            'country_of_birth_uid', 'affiliation', 'affiliation_uid', 'bio', 'are_you_currently_studying',
            'type', 'supporting_letter', 'is_active'
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
            'first_name', 'last_name', 'full_name', 'middle_name', 'email', 'student_id',
            'sex', 'primary_phone', 'secondary_phone', 'id_type', 'copy_of_id', 'bio',
            'type', 'is_active', 'nationality', 'country_of_birth', 'affiliation',
            'are_you_currently_studying', 'supporting_letter'
        ]


# Application Serializer
class ApplicationSerializer(SaveWithRequestUserMixin, BaseModelSerializer, DateValidationMixin):
    # For write operations - accept UUID strings
    student_uid = UUIDRelatedField(
        queryset=Student.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
        write_only=True,
        source='student'
    )
    user_uid = UUIDRelatedField(
        queryset=User.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
        write_only=True,
        source='user'
    )
    # For read operations - return nested objects
    student = StudentMinimalSerializer(read_only=True)
    user = serializers.SerializerMethodField(read_only=True)
    
    placement_type_display = serializers.CharField(source='get_placement_type_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    campus_display = serializers.CharField(source='get_campus_display', read_only=True)
    
    def get_user(self, obj):
        if obj.user:
            return {
                'uid': str(obj.user.guid),
                'full_name': obj.user.get_full_name(),
                'email': obj.user.email
            }
        return None
    
    class Meta:
        model = Application
        fields = BaseModelSerializer.Meta.fields + [
            'user', 'user_uid', 'student', 'student_uid', 'application_number',
            'departments', 'duration', 'from_date', 'to_date',
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
    # For write operations - accept UUID strings
    application_uid = UUIDRelatedField(
        queryset=Application.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
        write_only=True,
        source='application'
    )
    department_uid = serializers.CharField(
        required=False,
        allow_null=True,
        write_only=True,
        help_text="UID reference to Department from auth microservice"
    )
    supervisor_uid = UUIDRelatedField(
        queryset=Supervisor.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
        write_only=True,
        source='supervisor'
    )
    # For read operations - return nested objects
    application = ApplicationMinimalSerializer(read_only=True)
    supervisor = SupervisorMinimalSerializer(read_only=True)
    
    duration_days = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = DepartmentAllocation
        fields = BaseModelSerializer.Meta.fields + [
            'application', 'application_uid', 'department_uid',
            'supervisor', 'supervisor_uid', 'start_date', 'end_date',
            'duration_days', 'description', 'is_active'
        ]
    
    def validate(self, data):
        """Validate allocation dates"""
        return self.validate_dates('start_date', 'end_date', data)


# Supervisor Serializer
class SupervisorSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    class Meta:
        model = Supervisor
        fields = BaseModelSerializer.Meta.fields + [
            'user_guid', 'department_uid',
            'description', 'is_active'
        ]


# Supervisor List Serializer
class SupervisorListSerializer(SupervisorSerializer):
    """List serializer for supervisor display"""
    pass


# Institution Serializer
class InstitutionSerializer(SaveWithRequestUserMixin, BaseModelSerializer):
    # For write operations - accept UUID strings
    country_uid = UUIDRelatedField(
        queryset=Country.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
        write_only=True,
        source='country'
    )
    # For read operations - return nested object
    country = CountryMinimalSerializer(read_only=True)
    mou_count = serializers.SerializerMethodField()
    
    def get_mou_count(self, obj):
        return obj.mous.filter(is_deleted=False).count()
    
    class Meta:
        model = Institution
        fields = BaseModelSerializer.Meta.fields + [
            'institution_code', 'name', 'address', 'country', 'country_uid',
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
    # For write operations - accept UUID strings
    institution_uid = UUIDRelatedField(
        queryset=Institution.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
        write_only=True,
        source='institution'
    )
    # For read operations - return nested object
    institution = InstitutionMinimalSerializer(read_only=True)
    duration_display = serializers.CharField(read_only=True)
    expiration_status = serializers.SerializerMethodField()
    
    def get_expiration_status(self, obj):
        return obj.expiration_status()
    
    class Meta:
        model = MOU
        fields = BaseModelSerializer.Meta.fields + [
            'institution', 'institution_uid', 'mou_number', 'start_date', 'end_date',
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
    # For write operations - accept UUID strings
    mou_uid = UUIDRelatedField(
        queryset=MOU.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
        write_only=True,
        source='mou'
    )
    # For read operations - return nested object
    mou = MOUMinimalSerializer(read_only=True)
    
    department_names = serializers.SerializerMethodField()
    duration_display = serializers.CharField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    mou_number = serializers.SerializerMethodField()
    institution_name = serializers.SerializerMethodField()
    
    def get_department_names(self, obj):
        return list(obj.departments.values_list('name', flat=True))
    
    def get_mou_number(self, obj):
        return obj.mou.mou_number if obj.mou else None
    
    def get_institution_name(self, obj):
        return obj.mou.institution.name if obj.mou and obj.mou.institution else None
    
    class Meta:
        model = TrainingBatch
        fields = BaseModelSerializer.Meta.fields + [
            'batch_number', 'mou', 'mou_uid', 'mou_number', 'institution_name',
            'number_of_students', 'departments', 'department_names',
            'invoiced_amount', 'currency', 'training_start_date', 'training_end_date',
            'duration_display', 'application_letter', 'status', 'status_display',
            'notes', 'cancellation_reason', 'cancelled_by_guid',
            'cancelled_at', 'is_active'
        ]
        read_only_fields = ['batch_number', 'duration_display', 'mou_number', 'institution_name']
    
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

