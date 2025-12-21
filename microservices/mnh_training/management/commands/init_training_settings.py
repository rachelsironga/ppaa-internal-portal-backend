from django.core.management.base import BaseCommand
from microservices.mnh_training.models import TrainingSetting


class Command(BaseCommand):
    help = 'Initialize or reset training settings to defaults'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset existing settings to defaults'
        )

    def handle(self, *args, **options):
        reset = options.get('reset', False)

        try:
            if reset:
                # Delete existing if reset flag is set
                TrainingSetting.objects.all().delete()
                self.stdout.write(self.style.WARNING('Deleted existing training settings'))

            # Get or create
            settings, created = TrainingSetting.objects.get_or_create(
                pk=1,
                defaults={
                    'student_id_format': 'STD-{YYYY}-{NNNN}',
                    'student_id_prefix': 'STD',
                    'student_id_increment_counter': 1,
                    'reset_student_counter_yearly': True,
                    'application_ref_format': 'APP-{YYYY}-{NNNN}',
                    'application_ref_prefix': 'APP',
                    'application_ref_counter': 1,
                    'reset_application_counter_yearly': True,
                    'certificate_number_format': 'CERT-{YYYY}-{NNNN}',
                    'certificate_number_prefix': 'CERT',
                    'certificate_counter': 1,
                    'reset_certificate_counter_yearly': True,
                    'training_hours_per_week': 40,
                    'training_days_per_week': 5,
                    'standard_training_duration': 12,
                    'standard_training_duration_unit': 'W',
                    'special_departments': {},
                    'min_training_days': 1,
                    'max_training_days': 365,
                    'allow_overlapping_departments': False,
                    'organization_name': 'MNH Training Center',
                    'certificate_validity_years': 0,
                    'minimum_attendance_percentage': 80,
                    'require_supervisor_approval': True,
                    'days_before_training_reminder': 7,
                    'notify_on_completion': True,
                }
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS('Training settings created successfully with default values')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('Training settings already exist')
                )

            # Display current settings
            self.stdout.write(self.style.SUCCESS('\nCurrent Training Settings:'))
            self.stdout.write(f'Organization Name: {settings.organization_name}')
            self.stdout.write(f'Training Hours Per Week: {settings.training_hours_per_week}')
            self.stdout.write(f'Training Days Per Week: {settings.training_days_per_week}')
            self.stdout.write(f'Standard Training Duration: {settings.standard_training_duration} {settings.get_standard_training_duration_unit_display()}')
            self.stdout.write(f'Student ID Format: {settings.student_id_format}')
            self.stdout.write(f'Application Ref Format: {settings.application_ref_format}')
            self.stdout.write(f'Certificate Number Format: {settings.certificate_number_format}')
            self.stdout.write(f'Minimum Attendance: {settings.minimum_attendance_percentage}%')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error initializing training settings: {str(e)}')
            )
