import os
import uuid
from functools import partial
from datetime import datetime
from django.utils import timezone
from django.db import models
from datetime import date
from django.core.validators import RegexValidator, FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from mnh_auth.models import BaseModel, Department, Currency
try:
    from mnh_auth.models import Country
except ImportError:
    Country = None


User = get_user_model()


def year_based_upload_path(instance, filename, prefix):
    """Generic secure file upload path with year-based organization"""
    ext = os.path.splitext(filename)[1]
    filename = f"{prefix}_{instance.pk or 'new'}{ext}"
    return f"{prefix}/{timezone.now().year}/{filename}"




# models = [
#     TrainingCertificate, TrainingAssessment, TrainingAttendance,
#     TrainingSession, TrainingMaterial, TrainingModule, TrainingBatch,
#     TrainingProgram, TrainingInstructor, TrainingVenue, TrainingCategory
#     TrainingBatch, MOU, Institution, DepartmentAllocation,
#     Application, Supervisor, Student, Affiliation
# ]
    

class Affiliation(BaseModel):
    class AffiliationType(models.TextChoices):
        SELF = 'SELF', 'Self'
        ACADEMIC = 'ACADEMIC', 'Academic Institution'
        EMPLOYMENT = 'EMPLOYMENT', 'Workplace / Company'

    class AcademicLevel(models.TextChoices):
        UNDERGRADUATE = 'UG', 'Undergraduate'
        GRADUATE = 'G', 'Graduate'
        POSTGRADUATE = 'PG', 'Postgraduate'
    
    application = models.ForeignKey(
        'Application',
        on_delete=models.PROTECT,  
        related_name='affiliation',
        null=True,
        blank=True,
        db_index=True
    )
    type = models.CharField(
        max_length=20,
        choices=AffiliationType.choices,
        default=AffiliationType.SELF,
        db_index=True
    )
    name = models.CharField(
        max_length=200,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^[\w\s\-\.\'&]+$',
                message='Name contains invalid characters'
            )
        ]
    )
    level = models.CharField(
        max_length=2,
        choices=AcademicLevel.choices,
        blank=True,
        null=True,
        db_index=True,
        help_text='Applicable if type is Academic'
    )
    year = models.CharField(
        max_length=1,
        blank=True,
        null=True,
        db_index=True,
        help_text='Current year of study'
    )
    course = models.CharField(
        max_length=200,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^[\w\s\-\.\']+$',
                message='Course name contains invalid characters'
            )
        ]
    )
    address = models.TextField(
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^[\w\s\-\.\,\']+$',
                message='Address contains invalid characters'
            )
        ]
    )
    country = models.ForeignKey(
        'mnh_auth.Country',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_index=True
    )
   
    def __str__(self):
        return f"{self.name or 'N/A'} - ({self.country})"    
    
    class Meta:
        verbose_name = 'Affiliation'
        verbose_name_plural = 'Affiliations'
        ordering = ['name']
        indexes = [
            models.Index(fields=['type', 'name']),
            models.Index(fields=['is_deleted']),
        ]

class Student(BaseModel):
    """Model for registered students with full validation and dynamic ID handling."""

    # ========= CHOICES ===========
    class SexChoices(models.TextChoices):
        MALE = 'M', 'Male'
        FEMALE = 'F', 'Female'

    class Type(models.TextChoices):
        LOCAL = 'LC', 'Local'
        FOREIGN = 'FR', 'Foreign'

    class IdType(models.TextChoices):
        PASSPORT = 'P', 'Passport'
        NIDA = 'N', 'National ID'
        VOTER = 'V', 'Voter ID'
        OTHER = 'O', 'Other'

    # ========= UPLOAD PATHS ===========
    def profile_upload_path(instance, filename):
        ext = os.path.splitext(filename)[1]
        return f'students/profile/{instance.last_name}_{instance.pk}{ext}'

    def id_upload_path(instance, filename):
        ext = os.path.splitext(filename)[1]
        return f'students/ids/{instance.id_type}/{instance.pk}{ext}'
    
    # ========= PERSONAL INFO ===========
    profile_picture = models.FileField(
        upload_to=profile_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['gif', 'jpg', 'jpeg', 'png'])],
        null=True, blank=True,
        help_text=('Upload a profile photo (jpg, png, gif)')
    )

    first_name = models.CharField(
        max_length=50,
        validators=[RegexValidator(r'^[a-zA-Z\- ]+$',('Only letters, spaces and hyphens allowed'))]
    )

    middle_name = models.CharField(
        max_length=50,
        blank=True, null=True,
        validators=[RegexValidator(r'^[a-zA-Z\- ]*$',('Only letters, spaces and hyphens allowed'))]
    )

    last_name = models.CharField(
        max_length=50,
        validators=[RegexValidator(r'^[a-zA-Z\- ]+$',('Only letters, spaces and hyphens allowed'))]
    )

    sex = models.CharField(max_length=1, choices=SexChoices.choices, db_index=True)

    # ========= CONTACT ===========
    primary_phone = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+?[0-9]{8,15}$',('Enter valid phone (e.g. +255123456789)'))]
    )

    secondary_phone = models.CharField(
        max_length=20, blank=True, null=True,
        validators=[RegexValidator(r'^\+?[0-9]{8,15}$',('Enter valid phone (e.g. +255123456789)'))]
    )

    email = models.EmailField(
        max_length=255,
        validators=[RegexValidator(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',('Enter valid email'))]
    )

    # ========= IDENTIFICATION ===========
    id_type = models.CharField(max_length=1, choices=IdType.choices, null=True, blank=True, db_index=True)

    copy_of_id = models.FileField(
        upload_to=id_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        null=True, blank=True,
        help_text=('Upload ID document (pdf, jpg, png)')
    )

    student_id = models.CharField(max_length=255, db_index=True)

    # ========= NATIONALITY ===========
    nationality = models.ForeignKey(
        Country, 
        on_delete=models.PROTECT, null=True, blank=True,
        related_name='students', db_index=True
    )

    country_of_birth = models.ForeignKey(
        Country, on_delete=models.PROTECT, null=True, blank=True,
        related_name='born_students', db_index=True
    )

    # ========= OTHER DETAILS ===========
    bio = models.TextField(
        blank=True, null=True,
        validators=[RegexValidator(r'^[\w\s\-.,!?()]*$',('Bio contains invalid characters'))]
    )

    are_you_currently_studying = models.BooleanField(default=False)

    # ========= SYSTEM FIELDS ===========
    type = models.CharField(max_length=2, choices=Type.choices, editable=False, db_index=True)

    supporting_letter = models.FileField(
        upload_to=partial(year_based_upload_path, prefix='supporting_letters'),
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])],
        help_text=('PDF or Word document (max 5MB)')
    )
    affiliation = models.ForeignKey(
        'Affiliation',
        on_delete=models.PROTECT,  
        related_name='student_application',
        null=True,
        blank=True,
        db_index=True
    )

    class Meta:
        ordering = ['last_name', 'first_name']
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['is_deleted', 'type']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['email'], name='unique_student_email', condition=models.Q(is_deleted=False)),
            models.UniqueConstraint(fields=['primary_phone'], name='unique_student_phone', condition=models.Q(is_deleted=False)),
        ]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return ' '.join(filter(None, [self.first_name, self.middle_name, self.last_name]))

    def is_tanzanian(self):
        return hasattr(self, '_is_tanzanian') and self._is_tanzanian

    def clean(self):
        """Validate and normalize data before saving."""
        super().clean()

        # Normalize phone numbers
        for field in ['primary_phone', 'secondary_phone']:
            value = getattr(self, field, '')
            if value:
                setattr(self, field, ''.join(c for c in value if c.isdigit() or c == '+'))

        # Set type based on nationality
        if self.nationality:
            self._is_tanzanian = self.nationality.name.lower() == 'tanzania'
            self.type = self.Type.LOCAL if self._is_tanzanian else self.Type.FOREIGN

        # Validate ID size
        if self.copy_of_id and self.copy_of_id.size > 5 * 1024 * 1024:
            raise ValidationError('ID document too large (max 5MB)')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Supervisor(BaseModel):    
    user_guid = models.CharField(max_length=36, help_text="GUID reference to User from auth microservice")
    department_uid = models.CharField(max_length=36, help_text="UID reference to Department from auth microservice")

    description = models.TextField(max_length=500, blank=True, null=True)    
    
    class Meta:
        verbose_name = "Supervisor"
        verbose_name_plural = "Supervisors"
        
    def clean(self):
        """Validate business rules and data consistency"""
        super().clean()

    def __str__(self):
        return f"Supervisor {self.user_guid}"
    
    @property
    def get_supervisor(self):
        return self.user_guid


class Application(BaseModel):
    class PlacementType(models.TextChoices):
        ELECTIVE = 'EL', 'Elective'
        PRACTICAL_TRAINING = 'PT', 'Practical Training'
        POSTGRADUATE = 'PG', 'Postgraduate'
    
    class Campus(models.TextChoices):
        UPANGA = 'UP', 'Upanga'
        MLOGANZILA = 'ML', 'Mloganzila'
        BOTH = 'BO', 'Both'
        
    class Category(models.TextChoices):
        CLINICAL = 'CL', 'Clinical'  # Shortened for efficiency
        NON_CLINICAL = 'NL', 'Non-clinical'
     
    student = models.ForeignKey(
        'Student',
        on_delete=models.PROTECT,  
        related_name='applications',
        null=True,
        blank=True,
        db_index=True
    )
    application_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[A-Z0-9\-]+$',
                message=('Application number can only contain letters, numbers and hyphens')
            )
        ]
    )
    department_uids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of department UIDs from auth microservice"
    )
    duration = models.PositiveIntegerField(
        default=0,
        blank=True,
        null=True,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(52)
        ],
        help_text=("Duration in weeks (2-52)")
    )
    from_date = models.DateField(db_index=True)
    to_date = models.DateField(null=True, blank=True, db_index=True)
    category = models.CharField(
        max_length=2,
        choices=Category.choices,
        db_index=True
    )    
    placement_type = models.CharField(
        max_length=2,
        choices=PlacementType.choices,
        verbose_name=("Placement Type"),
        db_index=True
    )
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.ForeignKey(
        Currency, 
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    campus = models.CharField(
        max_length=2,
        choices=Campus.choices,
        db_index=True
    )
    supporting_letter = models.FileField(
        upload_to=partial(year_based_upload_path, prefix='supporting_letters'),
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])],
        help_text=('PDF or Word document (max 5MB)')
    )
    
    def __str__(self):
        return (f"{self.application_number} - "
                f"{self.get_placement_type_display()} "
                f"({self.from_date} to {self.to_date})")

    def clean(self):
        """Validate date consistency"""
        if self.from_date and self.to_date:
            if self.from_date > self.to_date:
                raise ValidationError('End date must be after start date')
            
            # Auto-calculate duration if not set
            if not self.duration:
                self.duration = (self.to_date - self.from_date).days // 7
                
        elif self.duration and self.from_date:
            # Auto-calculate end date if duration is provided
            self.to_date = self.from_date + timezone.timedelta(weeks=self.duration)
        
        # Ensure application number follows a pattern if provided
        if self.application_number and not self.application_number.startswith('APP-'):
            self.application_number = f"APP-{self.application_number}"

        # Validating supporting document
        if self.supporting_letter and self.supporting_letter.size > 5 * 1024 * 1024:
            raise ValidationError('Supporting letter too large (max 5MB)')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def department_names(self):
        """Return list of department UIDs (names should be resolved by frontend)"""
        return self.department_uids if self.department_uids else []
    
    class Meta:
        verbose_name = 'Application'
        verbose_name_plural = 'Applications'
        ordering = ['-from_date', 'student__last_name']
        indexes = [
            models.Index(fields=['from_date', 'to_date']),
            models.Index(fields=['category', 'placement_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['application_number'],
                name='unique_application_number',
                condition=models.Q(is_deleted=False)
            )
        ]


class DepartmentAllocation(BaseModel):
    application = models.ForeignKey(Application, on_delete=models.PROTECT)
    department_uid = models.CharField(max_length=36, help_text="UID reference to Department from auth microservice")
    supervisor = models.ForeignKey(Supervisor, on_delete=models.PROTECT, blank=True, null=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(max_length=500, blank=True, null=True)    
    
    class Meta:
        verbose_name = "Department Allocation"
        verbose_name_plural = "Department Allocations"
        
    def clean(self):
        """Validate business rules and data consistency"""
        super().clean()

        # Date validation
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': "End date cannot be before start date."
            })

        # Overlapping date validation
        if self.start_date and self.end_date:
            overlapping_allocations = DepartmentAllocation.objects.filter(
                application=self.application,
                department_uid=self.department_uid,
                start_date__lte=self.end_date,
                end_date__gte=self.start_date,
                is_deleted=False,  # Optional: exclude soft-deleted
            ).exclude(pk=self.pk)  # Exclude current instance during updates

            if overlapping_allocations.exists():
                raise ValidationError(
                    "This department already has an allocation for the selected date range."
                )

    def __str__(self):
        return f"{self.department_uid} Allocation"
    
    @property
    def duration_days(self):
        """Calculate actual duration in days"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return None


class Institution(BaseModel):
    institution_code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        help_text="Auto-generated if left blank"
    )
    name = models.CharField(max_length=200)
    address = models.TextField()
    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,  
        related_name='institution',
        null=True,
        blank=True,
        db_index=True
    )  
    contact_person = models.CharField(max_length=100)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    website = models.URLField(blank=True, null=True)
    institution_type = models.CharField(max_length=50, choices=[
        ('university', 'University'),
        ('college', 'College'),
        ('polytechnic', 'Polytechnic'),
        ('school', 'School'),
        ('other', 'Other')
    ])
    established_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class MOU(BaseModel):
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='mous')
    mou_number = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    purpose = models.TextField()
    terms_and_conditions = models.TextField()
    signed_by = models.CharField(max_length=100)
    signed_date = models.DateField()
    document = models.FileField(upload_to='mou_documents/')

    def __str__(self):
        return f"MOU {self.mou_number} - {self.start_date} to {self.end_date}"

    def save(self, *args, **kwargs):
        if not self.mou_number:
            last_mou = MOU.objects.order_by('-id').first()
            last_id = last_mou.id if last_mou else 0
            self.mou_number = f"MOU-{timezone.now().year}-{last_id + 1:04d}"
        super().save(*args, **kwargs)
    
    def expiration_status(self):
        """
        Returns the status of the MOU based on current date and end date.
        Possible return values:
        - 'active' (more than 30 days until expiration)
        - 'expiring_soon' (between 0-30 days until expiration)
        - 'expired' (end date has passed)
        """
        today = timezone.now().date()
        days_remaining = (self.end_date - today).days
        
        if days_remaining < 0:
            return 'expired'
        elif days_remaining <= 30:
            return 'expiring_soon'
        else:
            return 'active'

    @property
    def duration(self):
        """Returns the duration of the training in days"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1  # +1 to include both start and end dates
        return 0

    @property
    def duration_display(self):
        """Returns a human-readable duration string"""
        days = self.duration
        if days == 0:
            return "N/A"
        elif days == 1:
            return "1 day"
        elif days < 7:
            return f"{days} days"
        else:
            weeks = days // 7
            remaining_days = days % 7
            if remaining_days == 0:
                return f"{weeks} week{'s' if weeks > 1 else ''}"
            else:
                return f"{weeks} week{'s' if weeks > 1 else ''} and {remaining_days} day{'s' if remaining_days > 1 else ''}"

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'MOU'
        verbose_name_plural = 'MOUs'


def application_letter_upload_path(instance, filename):
    # Generate unique filename for application letters
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('training_batches/application_letters/', filename)


class TrainingBatch(BaseModel):
    batch_number = models.CharField(max_length=50, unique=True, editable=False)
    mou = models.ForeignKey(MOU, on_delete=models.PROTECT, related_name='training_batches')
    number_of_students = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    departments = models.ManyToManyField(
        Department,
        related_name='training_batch'
    )
    invoiced_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.ForeignKey(
        Currency,  # Use string if Currency model is declared elsewhere
        on_delete=models.CASCADE
    )
    training_start_date = models.DateField()
    training_end_date = models.DateField()
    application_letter = models.FileField(upload_to=application_letter_upload_path)
    status = models.CharField(max_length=20, choices=[
        ('planned', 'Planned'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='planned')
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_by_guid = models.CharField(
        max_length=36,
        null=True,
        blank=True,
        help_text="GUID reference to User from auth microservice who cancelled this batch",
        db_index=True  
    )
    cancelled_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    
    def __str__(self):
        return f"Batch {self.batch_number} - {self.training_start_date} to {self.training_end_date}"

    @property
    def duration(self):
        """Returns the duration of the training in days"""
        if self.training_start_date and self.training_end_date:
            return (self.training_end_date - self.training_start_date).days + 1  # +1 to include both start and end dates
        return 0

    @property
    def duration_display(self):
        """Returns a human-readable duration string"""
        days = self.duration
        if days == 0:
            return "N/A"
        elif days == 1:
            return "1 day"
        elif days < 7:
            return f"{days} days"
        else:
            weeks = days // 7
            remaining_days = days % 7
            if remaining_days == 0:
                return f"{weeks} week{'s' if weeks > 1 else ''}"
            else:
                return f"{weeks} week{'s' if weeks > 1 else ''} and {remaining_days} day{'s' if remaining_days > 1 else ''}"

    def save(self, *args, **kwargs):

        if not self.batch_number:
            current_year = self.training_start_date.year if self.training_start_date else datetime.now().year
            
            # Find the last batch for this year
            last_batch_for_year = TrainingBatch.objects.filter(
                batch_number__startswith=f"BATCH/{current_year}/"
            ).order_by('-batch_number').first()
            
            if last_batch_for_year:
                try:
                    last_number = int(last_batch_for_year.batch_number.split('/')[-1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1
            else:
                new_number = 1
                
            self.batch_number = f"BATCH/{current_year}/{new_number:04d}"
        
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-training_start_date']
        verbose_name_plural = 'Training Batches'


class TrainingSetting(BaseModel):
    """
    Global training configuration settings for number/ID generation,
    training schedules, and certificate management.
    """
    
    class Duration(models.TextChoices):
        WEEKS = 'W', 'Weeks'
        MONTHS = 'M', 'Months'
        DAYS = 'D', 'Days'
    
    # ========= STUDENT ID/NUMBER SETTINGS ===========
    student_id_format = models.CharField(
        max_length=100,
        default='STD-{YYYY}-{NNNN}',
        help_text='Format pattern for student ID (e.g., STD-{YYYY}-{NNNN}, {YYYY} = year, {NNNN} = sequential)'
    )
    student_id_prefix = models.CharField(
        max_length=10,
        default='STD',
        help_text='Prefix for student ID'
    )
    student_id_increment_counter = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Current counter for student ID generation'
    )
    reset_student_counter_yearly = models.BooleanField(
        default=True,
        help_text='Reset student ID counter at the beginning of each year'
    )
    
    # ========= APPLICATION REFERENCE NUMBER SETTINGS ===========
    application_ref_format = models.CharField(
        max_length=100,
        default='APP-{YYYY}-{NNNN}',
        help_text='Format pattern for application reference (e.g., APP-{YYYY}-{NNNN})'
    )
    application_ref_prefix = models.CharField(
        max_length=10,
        default='APP',
        help_text='Prefix for application reference number'
    )
    application_ref_counter = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Current counter for application reference generation'
    )
    reset_application_counter_yearly = models.BooleanField(
        default=True,
        help_text='Reset application counter at the beginning of each year'
    )
    
    # ========= CERTIFICATE NUMBER SETTINGS ===========
    certificate_number_format = models.CharField(
        max_length=100,
        default='CERT-{YYYY}-{NNNN}',
        help_text='Format pattern for certificate number (e.g., CERT-{YYYY}-{NNNN})'
    )
    certificate_number_prefix = models.CharField(
        max_length=10,
        default='CERT',
        help_text='Prefix for certificate number'
    )
    certificate_counter = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Current counter for certificate generation'
    )
    reset_certificate_counter_yearly = models.BooleanField(
        default=True,
        help_text='Reset certificate counter at the beginning of each year'
    )
    
    # ========= TRAINING SCHEDULE SETTINGS ===========
    training_hours_per_week = models.PositiveIntegerField(
        default=40,
        validators=[MinValueValidator(1), MaxValueValidator(168)],
        help_text='Standard training hours per week'
    )
    training_days_per_week = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(7)],
        help_text='Standard number of training days per week'
    )
    standard_training_duration = models.PositiveIntegerField(
        default=12,
        validators=[MinValueValidator(1)],
        help_text='Standard training duration (value)'
    )
    standard_training_duration_unit = models.CharField(
        max_length=1,
        choices=Duration.choices,
        default='W',
        help_text='Unit for standard training duration'
    )
    
    # ========= SPECIAL DEPARTMENT SETTINGS ===========
    # JSONField to store special department configurations
    special_departments = models.JSONField(
        default=dict,
        blank=True,
        help_text='Special department configurations with custom training hours/duration (format: {dept_uid: {hours_per_week: int, duration_value: int, duration_unit: str, special_requirements: str}})'
    )
    
    # ========= DEPARTMENT ALLOCATION SETTINGS ===========
    min_training_days = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Minimum number of days per department allocation'
    )
    max_training_days = models.PositiveIntegerField(
        default=365,
        validators=[MinValueValidator(1)],
        help_text='Maximum number of days per department allocation'
    )
    allow_overlapping_departments = models.BooleanField(
        default=False,
        help_text='Allow training in multiple departments simultaneously'
    )
    
    # ========= GENERAL SETTINGS ===========
    organization_name = models.CharField(
        max_length=255,
        default='MNH Training Center',
        help_text='Organization name for certificates and official documents'
    )
    certificate_validity_years = models.PositiveIntegerField(
        default=0,
        help_text='Certificate validity period in years (0 = indefinite)'
    )
    minimum_attendance_percentage = models.PositiveIntegerField(
        default=80,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Minimum attendance percentage required to receive certificate'
    )
    require_supervisor_approval = models.BooleanField(
        default=True,
        help_text='Require supervisor approval before training completion'
    )
    
    # ========= NOTIFICATION SETTINGS ===========
    days_before_training_reminder = models.PositiveIntegerField(
        default=7,
        help_text='Send reminder notification N days before training starts'
    )
    notify_on_completion = models.BooleanField(
        default=True,
        help_text='Send notification when training is completed'
    )
    
    # ========= SYSTEM METADATA ===========
    last_modified_by_guid = models.CharField(
        max_length=36,
        null=True,
        blank=True,
        help_text='GUID of user who last modified these settings'
    )
    last_modified_at = models.DateTimeField(
        auto_now=True,
        help_text='Timestamp of last modification'
    )
    
    class Meta:
        verbose_name = 'Training Setting'
        verbose_name_plural = 'Training Settings'
    
    def __str__(self):
        return f"Training Settings - {self.organization_name}"
    
    def save(self, *args, **kwargs):
        """Ensure only one instance of TrainingSetting exists"""
        if not self.pk and TrainingSetting.objects.exists():
            # Update existing instead of creating new
            existing = TrainingSetting.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the single TrainingSetting instance"""
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
    
    def get_special_department_config(self, department_uid):
        """Get special configuration for a specific department"""
        return self.special_departments.get(department_uid, None)
    
    def set_special_department_config(self, department_uid, config):
        """Set special configuration for a specific department"""
        if not isinstance(self.special_departments, dict):
            self.special_departments = {}
        self.special_departments[department_uid] = config
        self.save()
    
    def remove_special_department_config(self, department_uid):
        """Remove special configuration for a specific department"""
        if isinstance(self.special_departments, dict) and department_uid in self.special_departments:
            del self.special_departments[department_uid]
            self.save()


class TrainingSession(BaseModel):
    """Model for individual training sessions"""
    
    class SessionStatus(models.TextChoices):
        SCHEDULED = 'SC', 'Scheduled'
        ONGOING = 'ON', 'Ongoing'
        COMPLETED = 'CP', 'Completed'
        CANCELLED = 'CN', 'Cancelled'
    
    batch = models.ForeignKey(
        TrainingBatch,
        on_delete=models.PROTECT,
        related_name='training_sessions',
        db_index=True
    )
    department_allocation = models.ForeignKey(
        DepartmentAllocation,
        on_delete=models.PROTECT,
        related_name='training_sessions',
        null=True,
        blank=True,
        db_index=True
    )
    supervisor_uid = models.CharField(
        max_length=36,
        help_text="UID reference to Supervisor"
    )
    session_number = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Session sequence number within batch"
    )
    session_date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=255, blank=True)
    topic = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    expected_attendees = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Expected number of attendees"
    )
    status = models.CharField(
        max_length=2,
        choices=SessionStatus.choices,
        default=SessionStatus.SCHEDULED,
        db_index=True
    )
    materials_provided = models.FileField(
        upload_to=partial(year_based_upload_path, prefix='training_materials'),
        null=True,
        blank=True,
        help_text="Training materials/handouts"
    )
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-session_date', 'session_number']
        verbose_name = 'Training Session'
        verbose_name_plural = 'Training Sessions'
        indexes = [
            models.Index(fields=['batch', 'session_date']),
            models.Index(fields=['status', 'session_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['batch', 'session_number'],
                name='unique_batch_session_number'
            )
        ]
    
    def __str__(self):
        return f"Session {self.session_number} - {self.batch.batch_number} ({self.session_date})"
    
    def clean(self):
        """Validate session data"""
        super().clean()
        
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError({
                    'end_time': 'End time must be after start time'
                })
    
    @property
    def duration_minutes(self):
        """Calculate session duration in minutes"""
        if self.start_time and self.end_time:
            from datetime import datetime as dt, timedelta
            start = dt.combine(date.today(), self.start_time)
            end = dt.combine(date.today(), self.end_time)
            return int((end - start).total_seconds() / 60)
        return 0
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class TrainingAttendance(BaseModel):
    """Model for tracking training attendance"""
    
    class AttendanceStatus(models.TextChoices):
        PRESENT = 'P', 'Present'
        ABSENT = 'A', 'Absent'
        LATE = 'L', 'Late'
        EXCUSED = 'E', 'Excused Absence'
    
    session = models.ForeignKey(
        TrainingSession,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        db_index=True
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.PROTECT,
        related_name='training_attendance',
        db_index=True
    )
    status = models.CharField(
        max_length=1,
        choices=AttendanceStatus.choices,
        db_index=True
    )
    arrival_time = models.TimeField(null=True, blank=True)
    departure_time = models.TimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    
    class Meta:
        ordering = ['session', 'application__student__last_name']
        verbose_name = 'Training Attendance'
        verbose_name_plural = 'Training Attendances'
        indexes = [
            models.Index(fields=['session', 'status']),
            models.Index(fields=['application', 'session']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'application'],
                name='unique_session_application_attendance'
            )
        ]
    
    def __str__(self):
        return f"{self.application.student.full_name} - {self.session.session_date} ({self.get_status_display()})"
    
    @property
    def attendance_percentage(self):
        """Calculate attendance for this application across all sessions"""
        total_sessions = TrainingSession.objects.filter(
            batch=self.session.batch,
            status__in=[TrainingSession.SessionStatus.COMPLETED, TrainingSession.SessionStatus.ONGOING]
        ).count()
        
        if total_sessions == 0:
            return 0
        
        present_sessions = TrainingAttendance.objects.filter(
            application=self.application,
            session__batch=self.session.batch,
            status__in=[self.AttendanceStatus.PRESENT, self.AttendanceStatus.LATE]
        ).count()
        
        return round((present_sessions / total_sessions) * 100, 2)


class TrainingAssessment(BaseModel):
    """Model for training assessments/evaluations"""
    
    class AssessmentType(models.TextChoices):
        PRE_TRAINING = 'PRE', 'Pre-Training Assessment'
        MID_TRAINING = 'MID', 'Mid-Training Assessment'
        POST_TRAINING = 'PST', 'Post-Training Assessment'
        PRACTICAL = 'PRC', 'Practical Assessment'
        WRITTEN = 'WRT', 'Written Assessment'
    
    batch = models.ForeignKey(
        TrainingBatch,
        on_delete=models.PROTECT,
        related_name='assessments',
        db_index=True
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.PROTECT,
        related_name='training_assessments',
        db_index=True
    )
    assessment_type = models.CharField(
        max_length=3,
        choices=AssessmentType.choices,
        db_index=True
    )
    assessment_date = models.DateField()
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Score out of 100"
    )
    total_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100,
        validators=[MinValueValidator(1)],
        help_text="Total possible score"
    )
    graded_by_guid = models.CharField(
        max_length=36,
        help_text="UID reference to grader"
    )
    feedback = models.TextField(blank=True)
    assessment_file = models.FileField(
        upload_to=partial(year_based_upload_path, prefix='assessments'),
        null=True,
        blank=True,
        help_text="Assessment document/answer sheet"
    )
    
    class Meta:
        ordering = ['-assessment_date', 'application']
        verbose_name = 'Training Assessment'
        verbose_name_plural = 'Training Assessments'
        indexes = [
            models.Index(fields=['batch', 'assessment_type']),
            models.Index(fields=['application', 'assessment_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['batch', 'application', 'assessment_type'],
                name='unique_batch_application_assessment_type'
            )
        ]
    
    def __str__(self):
        return f"{self.application.student.full_name} - {self.get_assessment_type_display()} ({self.score}/{self.total_score})"
    
    @property
    def percentage_score(self):
        """Calculate percentage score"""
        if self.total_score == 0:
            return 0
        return round((self.score / self.total_score) * 100, 2)
    
    @property
    def is_pass(self):
        """Determine if assessment is passed (70% threshold)"""
        return self.percentage_score >= 70


class TrainingCertificate(BaseModel):
    """Model for training certificates issued to participants"""
    
    class CertificateStatus(models.TextChoices):
        DRAFT = 'DR', 'Draft'
        PENDING = 'PD', 'Pending Issue'
        ISSUED = 'IS', 'Issued'
        REVOKED = 'RV', 'Revoked'
    
    batch = models.ForeignKey(
        TrainingBatch,
        on_delete=models.PROTECT,
        related_name='certificates',
        db_index=True
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.PROTECT,
        related_name='training_certificates',
        db_index=True
    )
    certificate_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True
    )
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=2,
        choices=CertificateStatus.choices,
        default=CertificateStatus.DRAFT,
        db_index=True
    )
    attendance_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Final attendance percentage"
    )
    final_assessment_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Final assessment score"
    )
    issued_by_guid = models.CharField(
        max_length=36,
        null=True,
        blank=True,
        help_text="UID reference to issuer"
    )
    revoked_by_guid = models.CharField(
        max_length=36,
        null=True,
        blank=True,
        help_text="UID reference to revoker"
    )
    revocation_reason = models.TextField(blank=True)
    certificate_file = models.FileField(
        upload_to=partial(year_based_upload_path, prefix='certificates'),
        null=True,
        blank=True,
        help_text="Certificate PDF document"
    )
    remarks = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-issue_date', 'application']
        verbose_name = 'Training Certificate'
        verbose_name_plural = 'Training Certificates'
        indexes = [
            models.Index(fields=['batch', 'status']),
            models.Index(fields=['application', 'status']),
            models.Index(fields=['certificate_number']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['batch', 'application'],
                name='unique_batch_application_certificate'
            )
        ]
    
    def __str__(self):
        return f"Cert {self.certificate_number} - {self.application.student.full_name}"
    
    def save(self, *args, **kwargs):
        """Generate certificate number if not set"""
        if not self.certificate_number:
            settings = TrainingSetting.get_settings()
            self.certificate_number = f"{settings.certificate_number_prefix}-{timezone.now().year}-{settings.certificate_counter:04d}"
            settings.certificate_counter += 1
            settings.save()
        
        super().save(*args, **kwargs)
    
    @property
    def is_valid(self):
        """Check if certificate is valid and not expired"""
        if self.status != self.CertificateStatus.ISSUED:
            return False
        
        if self.expiry_date:
            return self.expiry_date >= timezone.now().date()
        return True