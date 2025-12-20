import os
import uuid
from functools import partial
from datetime import datetime
from django.utils import timezone
from django.db import models
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
    departments = models.ManyToManyField(
        Department,
        related_name='applications',
        db_table='application_departments'  # Explicit join table name
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
        """Optimized department names listing"""
        return ', '.join(self.departments.values_list('name', flat=True))
    
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


