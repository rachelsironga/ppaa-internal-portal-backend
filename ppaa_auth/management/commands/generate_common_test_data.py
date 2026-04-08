# generate_common_test_data.py
from django.core.management.base import BaseCommand
from django.db import IntegrityError
import factory
from ppaa_auth.models import User, Directory, Department, PositionalLevel, UserProfile
from django.contrib.auth import get_user_model

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'testuser{n}')
    email = factory.Sequence(lambda n: f'testuser{n}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    status = 'ACTIVE'
    account_type = 'LONG_TERM'

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop('password', 'testpass123')
        obj = model_class(*args, **kwargs)
        obj.set_password(password)
        obj.save()
        return obj


class DirectoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Directory

    name = factory.Sequence(lambda n: f'Directory{n}')
    code = factory.Sequence(lambda n: f'DIR{n:03d}')


class DepartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Department

    name = factory.Sequence(lambda n: f'Department{n}')
    code = factory.Sequence(lambda n: f'DEPT{n:03d}')
    directory = factory.SubFactory(DirectoryFactory)


class PositionalLevelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PositionalLevel

    name = factory.Sequence(lambda n: f'Level{n}')
    code = factory.Sequence(lambda n: f'LEV{n:03d}')


class UserProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserProfile

    user = factory.SubFactory(UserFactory)
    level = factory.SubFactory(PositionalLevelFactory)
    directory = factory.SubFactory(DirectoryFactory)
    department = factory.SubFactory(DepartmentFactory)


class Command(BaseCommand):
    help = 'Generate test data for auth app using Factory Boy'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=10,
            help='Number of users to create'
        )
        parser.add_argument(
            '--directories',
            type=int,
            default=3,
            help='Number of directories to create'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data first'
        )

    def handle(self, *args, **options):
        # Check if users >= 10, if so, skip population
        existing_users = User.objects.filter(username__startswith='testuser').count()
        if existing_users >= 10:
            self.stdout.write(self.style.WARNING(f'Found {existing_users} existing test users. Skipping data generation.'))
            return

        if options['clear']:
            self.clear_data()

        self.stdout.write('Generating test data with Factory Boy...')

        # Create positional levels
        levels = []
        try:
            levels = [
                PositionalLevelFactory.create(name='Supervisor', code='SUP'),
                PositionalLevelFactory.create(name='Manager', code='MGR'),
                PositionalLevelFactory.create(name='Director', code='DIR'),
            ]
            self.stdout.write(f'Created {len(levels)} positional levels')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Positional level creation skipped: {str(e)[:50]}'))

        # Create directories
        directories = []
        try:
            directories = DirectoryFactory.create_batch(options['directories'])
            self.stdout.write(f'Created {len(directories)} directories')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Directory creation skipped: {str(e)[:50]}'))

        # Create departments
        departments = []
        try:
            for directory in directories:
                for i in range(2):
                    dept = DepartmentFactory.create(directory=directory)
                    departments.append(dept)
            self.stdout.write(f'Created {len(departments)} departments')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Department creation skipped: {str(e)[:50]}'))

        # Create users
        users = []
        try:
            users = UserFactory.create_batch(options['users'])
            self.stdout.write(f'Created {len(users)} users')
        except IntegrityError as e:
            self.stdout.write(self.style.WARNING(f'User creation failed: {str(e)[:50]}'))

        # Create user profiles
        user_profiles = []
        try:
            for user in users:
                if levels and directories:
                    profile = UserProfileFactory.create(
                        user=user,
                        level=levels[0],
                        directory=directories[0]
                    )
                    user_profiles.append(profile)
            self.stdout.write(f'Created {len(user_profiles)} user profiles')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'User profile creation skipped: {str(e)[:50]}'))

        self.stdout.write(self.style.SUCCESS('Test data generation completed!'))

    def clear_data(self):
        self.stdout.write('Clearing existing test data...')

        models = [
            UserProfile, Department, Directory, PositionalLevel
        ]

        for model in models:
            count, _ = model.objects.all().delete()
            self.stdout.write(f'Deleted {count} {model.__name__} records')

        try:
            user_count, _ = User.objects.filter(username__startswith='testuser').delete()
            self.stdout.write(f'Deleted {user_count} test users')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not delete test users: {str(e)[:50]}'))
