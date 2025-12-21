# generate_training_test_data.py
from django.core.management.base import BaseCommand
from django.db import IntegrityError
import factory
from microservices.mnh_training.factories import *
from microservices.mnh_training.models import (
    Affiliation, Student, Supervisor, Application, DepartmentAllocation,
    Institution, MOU, TrainingBatch
)

from django.contrib.auth import get_user_model
User = get_user_model()

class Command(BaseCommand):
    help = 'Generate test data using Factory Boy'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=10,
            help='Number of users to create'
        )
        parser.add_argument(
            '--programs',
            type=int,
            default=5,
            help='Number of training programs to create'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data first'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.clear_data()

        self.stdout.write('Generating test data with Factory Boy...')
        
        # Create or get existing users
        users = []
        existing_users = list(User.objects.filter(username__startswith='testuser'))
        
        if len(existing_users) >= options['users']:
            users = existing_users[:options['users']]
            self.stdout.write(f'Using {len(users)} existing users')
        else:
            users = existing_users
            needed = options['users'] - len(existing_users)
            for i in range(needed):
                try:
                    users.append(UserFactory.create())
                except IntegrityError:
                    self.stdout.write(self.style.WARNING(f'User creation failed, skipping...'))
            self.stdout.write(f'Created {len(users) - len(existing_users)} new users, using {len(existing_users)} existing users')

        # Create affiliations
        affiliations = AffiliationFactory.create_batch(5)
        self.stdout.write(f'Created {len(affiliations)} affiliations')

        # Create students
        students = StudentFactory.create_batch(options['users'])
        self.stdout.write(f'Created {len(students)} students')

        # Create supervisors
        supervisors = []
        try:
            supervisors = [s for s in SupervisorFactory.create_batch(5) if s is not None]
            self.stdout.write(f'Created {len(supervisors)} supervisors')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Supervisor creation skipped: {str(e)[:50]}'))

        # Create applications
        applications = []
        for student in students[:options['programs']]:
            try:
                app = ApplicationFactory.create(student=student)
                applications.append(app)
            except IntegrityError:
                pass
        self.stdout.write(f'Created {len(applications)} applications')

        # Create department allocations
        allocations = []
        for application in applications:
            try:
                allocation = DepartmentAllocationFactory.create(
                    application=application,
                    supervisor=supervisors[0] if supervisors else None
                )
                allocations.append(allocation)
            except IntegrityError:
                pass
        self.stdout.write(f'Created {len(allocations)} department allocations')

        # Create institutions
        institutions = InstitutionFactory.create_batch(3)
        self.stdout.write(f'Created {len(institutions)} institutions')

        # Create MOUs
        mous = []
        for institution in institutions:
            try:
                mou = MOUFactory.create(institution=institution)
                mous.append(mou)
            except IntegrityError:
                pass
        self.stdout.write(f'Created {len(mous)} MOUs')

        # Create training batches (skipped if no Currency data exists)
        batches = []
        try:
            from mnh_auth.models import Currency
            if not Currency.objects.exists():
                self.stdout.write(self.style.WARNING('Skipping training batches: No Currency data found'))
            else:
                for mou in mous:
                    try:
                        batch = TrainingBatchFactory.create(mou=mou)
                        if batch:
                            batches.append(batch)
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'Training batch error: {str(e)[:40]}'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Training batch creation skipped: {str(e)[:40]}'))
        self.stdout.write(f'Created {len(batches)} training batches')

        self.stdout.write(self.style.SUCCESS('Test data generation completed!'))

    def clear_data(self):
        self.stdout.write('Clearing existing test data...')
        
        models = [
            TrainingBatch, MOU, Institution, DepartmentAllocation,
            Application, Supervisor, Student, Affiliation
        ]
        
        for model in models:
            count, _ = model.objects.all().delete()
            self.stdout.write(f'Deleted {count} {model.__name__} records')
        
        try:
            user_count, _ = User.objects.filter(username__startswith='testuser').delete()
            self.stdout.write(f'Deleted {user_count} test users')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not delete test users: {str(e)[:50]}'))
