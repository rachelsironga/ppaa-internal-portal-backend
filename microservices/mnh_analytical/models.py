from django.utils import timezone
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from django.db import models

from django.contrib.auth import get_user_model
User = get_user_model()


class AnalyticalBaseModel(models.Model):
    """Base model for mnh_analytical app with cross-database FK support."""
    uid = models.UUIDField(default=None, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, related_name='created_%(class)s', on_delete=models.SET_NULL,
        null=True, blank=True, db_constraint=False, db_column='created_by_id'
    )
    updated_by = models.ForeignKey(
        User, related_name='updated_%(class)s', on_delete=models.SET_NULL,
        null=True, blank=True, db_constraint=False, db_column='updated_by_id'
    )
    deleted_by = models.ForeignKey(
        User, related_name='deleted_%(class)s', on_delete=models.SET_NULL,
        null=True, blank=True, db_constraint=False, db_column='deleted_by_id'
    )

    def save(self, *args, **kwargs):
        if not self.uid:
            import uuid
            self.uid = uuid.uuid4()
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


class Block(AnalyticalBaseModel):
    """Represents a physical block/building in the facility"""
    name = models.CharField(
        max_length=255,
        verbose_name=_('block name'),
        help_text=_('The name of the block/building')
    )
    code = models.CharField(
        max_length=50,
        unique=False,
        verbose_name=_('block code'),
        help_text=_('Short code identifier for the block')
    )
    location = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        choices=[
            ('Upanga', _('Upanga')),
            ('Mloganzila', _('Mloganzila')),
        ],
        default='Upanga',
        verbose_name=_('location'),
        help_text=_('Geographical location description of the block')
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('description'),
        help_text=_('Additional details about the block')
    )

    class Meta:
        db_table = 'analyticsApp_block'
        managed = False
        verbose_name = _('block')
        verbose_name_plural = _('blocks')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class AnalyticalDepartment(models.Model):
    """Represents a department in the facility (from remote DB)"""
    uid = models.UUIDField(default=None, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by_id = models.BigIntegerField(null=True, blank=True)
    updated_by_id = models.BigIntegerField(null=True, blank=True)
    deleted_by_id = models.BigIntegerField(null=True, blank=True)
    name = models.CharField(
        max_length=250,
        verbose_name=_('department name'),
        help_text=_('The name of the department')
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_('department code'),
        help_text=_('Short code identifier for the department')
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('description'),
        help_text=_('Additional details about the department')
    )

    class Meta:
        db_table = 'analyticsApp_department'
        managed = False
        verbose_name = _('department')
        verbose_name_plural = _('departments')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Clinic(AnalyticalBaseModel):
    """Represents a clinical unit within the facility"""
    block = models.ForeignKey(
        Block,
        related_name='clinics',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='block_id',
        verbose_name=_('block'),
        help_text=_('The physical block where this clinic is located')
    )
    department = models.ForeignKey(
        'microservices.mnh_analytical.models.AnalyticalDepartment',
        related_name='clinics',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_constraint=False,
        db_column='department_id',
        verbose_name=_('department'),
        help_text=_('The department this clinic belongs to')
    )
    name = models.CharField(
        max_length=250,
        verbose_name=_('clinic name'),
        help_text=_('The name of the clinic')
    )
    code = models.CharField(
        max_length=50,
        unique=False,
        verbose_name=_('clinic code'),
        help_text=_('Short code identifier for the clinic')
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('description'),
        help_text=_('Additional details about the clinic')
    )

    class Meta:
        db_table = 'analyticsApp_clinic'
        managed = False
        verbose_name = _('clinic')
        verbose_name_plural = _('clinics')
        unique_together = ('block', 'department', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"
    

    def get_patient_volume(self, start_date=None, end_date=None):
        """Get total patient volume for this clinic within a date range"""
        qs = PatientAttendance.objects.filter(clinic=self)
        if start_date:
            qs = qs.filter(attendance__date__gte=start_date)
        if end_date:
            qs = qs.filter(attendance__date__lte=end_date)
            
        result = qs.aggregate(
            total_patients=Sum('total_patients'),
            new_patients=Sum('new_patients'),
            follow_up_patients=Sum('follow_up_patients')
        )
        return result
    
    def get_growth_rate(self, period='monthly'):
        """Calculate growth/decline rate for this clinic"""
        from django.db.models.functions import ExtractMonth, ExtractYear
        from django.db.models import F, ExpressionWrapper, FloatField
        
        # Get current date and calculate previous period
        today = timezone.now().date()
        
        if period == 'monthly':
            # Compare with same month last year
            prev_period_start = today.replace(year=today.year-1, month=today.month, day=1)
            prev_period_end = prev_period_start.replace(day=28)  # Approximate
            current_period_start = today.replace(day=1)
            
            # Get data for both periods
            prev_data = self.get_patient_volume(prev_period_start, prev_period_end)
            current_data = self.get_patient_volume(current_period_start, today)
            
            prev_total = prev_data['total_patients'] or 0
            current_total = current_data['total_patients'] or 0
            
            if prev_total == 0:
                return float('inf') if current_total > 0 else 0.0
            
            return ((current_total - prev_total) / prev_total) * 100
        
        elif period == 'quarterly':
            # Similar logic for quarterly comparison
            pass
        # Add other periods as needed
        
    def get_comparison_with_peers(self):
        """Compare this clinic with others in the same department"""
        if not self.department:
            return None
            
        # Get all clinics in the same department
        peers = Clinic.objects.filter(department=self.department).exclude(id=self.id)
        
        # Get current month data for all
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        peer_data = []
        for peer in peers:
            data = peer.get_patient_volume(month_start, today)
            peer_data.append({
                'clinic': peer,
                'total_patients': data['total_patients'] or 0,
                'new_patients': data['new_patients'] or 0,
                'follow_up_patients': data['follow_up_patients'] or 0
            })
        
        # Sort by total patients (descending)
        peer_data.sort(key=lambda x: x['total_patients'], reverse=True)
        
        return peer_data


class PaymentMode(AnalyticalBaseModel):
    """Represents different payment modes available"""
    name = models.CharField(
        max_length=250,
        verbose_name=_('payment mode'),
        help_text=_('Name of the payment method')
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_('payment code'),
        help_text=_('Short code identifier for the payment method')
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('description'),
        help_text=_('Additional details about the payment method')
    )

    class Meta:
        db_table = 'analyticsApp_paymentmode'
        managed = False
        verbose_name = _('payment mode')
        verbose_name_plural = _('payment modes')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


# Method 2: Manager with default database
class AnalyticsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().using('analytical')



class Attendance(AnalyticalBaseModel):
    """Tracks daily attendance records for clinics"""
    def clinic_attendance_upload_path(instance, filename):
        year_month = instance.date.strftime('%Y_%m')
        return f'Attendance/{year_month}/{filename}'

    date = models.DateField(
        verbose_name=_('attendance date'),
        help_text=_('The date this attendance was recorded')
    )

    attendance_report = models.FileField(
        upload_to=clinic_attendance_upload_path,
        null=True,
        blank=True,
        verbose_name=_('attendance report'),
        help_text=_('Original uploaded attendance file (Excel or CSV)')
    )

    total_new_patients = models.PositiveIntegerField(
        default=0,
        verbose_name=_('total new patients'),
        help_text=_('Total number of new patients')
    )
    total_follow_up_patients = models.PositiveIntegerField(
        default=0,
        verbose_name=_('total follow-up patients'),
        help_text=_('Total number of follow-up patients')
    )
    grand_total_patients = models.PositiveIntegerField(
        default=0,
        verbose_name=_('grand total patients'),
        help_text=_('Grand total number of patients')
    )

     # Additional notes for the attendance record
    notes = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('notes'),
        help_text=_('Additional notes about this attendance record')
    )

    # Processing data
    processed_date = models.DateField(
        verbose_name=_('processed date'),
        help_text=_('The date this attendance was processed'),
        null=True,
        blank=True
    )
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='processed_%(class)ss',
        db_index=True,
        db_constraint=False,
        db_column='processed_by_id',
        verbose_name=_('processed by')
    )
    total_column = models.PositiveIntegerField(
        default=0,
        verbose_name=_('total excel colums')
    )
    success_colums = models.PositiveIntegerField(
        default=0,
        verbose_name=_('total success columns')
    )
    failed_colums = models.PositiveIntegerField(
        default=0,
        verbose_name=_('total failed colum')
    )

    objects = AnalyticsManager()

    class Meta:
        db_table = 'analyticsApp_attendance'
        managed = False
        verbose_name = _('attendance')
        verbose_name_plural = _('attendances')
        ordering = ['-date']

    def __str__(self):
        return _("{date}").format(
            date=self.date.strftime('%Y-%m-%d')
        )


class PatientAttendance(AnalyticalBaseModel):
    """Tracks daily attendance records for clinics"""

    attendance = models.ForeignKey(
        Attendance,
        related_name='attendances',
        on_delete=models.CASCADE,
        verbose_name=_('attendance'),
        help_text=_('The parent attendance record')
    )

    clinic = models.ForeignKey(
        Clinic,
        related_name='clinics',
        on_delete=models.CASCADE,
        verbose_name=_('clinic'),
        help_text=_('The parent attendance record')
    )

    payment = models.ForeignKey(
        PaymentMode,
        related_name='payments',
        on_delete=models.CASCADE,
        verbose_name=_('payment mode'),
        help_text=_('The parent attendance record')
    )
    
    new_patients = models.PositiveIntegerField(
        default=0,
        verbose_name=_('new patients'),
        help_text=_('Number of new patients')
    )
    follow_up_patients = models.PositiveIntegerField(
        default=0,
        verbose_name=_('follow-up patients'),
        help_text=_('Number of follow-up patients')
    )
    total_patients = models.PositiveIntegerField(
        default=0,
        verbose_name=_('total patients'),
        help_text=_('Number of patients')
    )

    class Meta:
        db_table = 'analyticsApp_patientattendance'
        managed = False
        verbose_name = _('patient attendance')
        verbose_name_plural = _('Patient attendances')
        ordering = ['-attendance__date']

    def save(self, *args, **kwargs):
        # Automatically calculate total before saving
        self.total_patients = self.new_patients + self.follow_up_patients
        super().save(*args, **kwargs)
        
        # Update parent Attendance totals
        self.update_attendance_totals()
    
    def delete(self, *args, **kwargs):
        attendance = self.attendance
        super().delete(*args, **kwargs)
        self.update_attendance_totals()
    
    def update_attendance_totals(self):
        attendance = self.attendance
        
        # Aggregate all related PatientAttendance records
        aggregates = PatientAttendance.objects.filter(attendance=attendance).aggregate(
            total_new=models.Sum('new_patients'),
            total_follow_up=models.Sum('follow_up_patients')
        )
        
        # Update the parent Attendance record
        attendance.total_new_patients = aggregates['total_new'] or 0
        attendance.total_follow_up_patients = aggregates['total_follow_up'] or 0
        attendance.grand_total_patients = (aggregates['total_new'] or 0) + (aggregates['total_follow_up'] or 0)
        attendance.save()


