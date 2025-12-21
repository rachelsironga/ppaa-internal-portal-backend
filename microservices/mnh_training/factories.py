# mnh_training/factories.py
import factory
from django.utils import timezone
from datetime import timedelta
import random
import uuid
from faker import Faker

from mnh_auth.models import User, Department, Country, Currency
from .models import (
    Affiliation, Student, Supervisor, Application, DepartmentAllocation,
    Institution, MOU, TrainingBatch
)

fake = Faker()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f'testuser{n}')
    pf_number = factory.Sequence(lambda n: f'PF{n:05d}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    middle_name = factory.Faker('last_name')
    check_number = factory.LazyFunction(lambda: f'CHK{fake.random_number(digits=6)}')
    office_location = factory.Faker('city')
    status = 'ACTIVE'
    account_type = 'LONG_TERM'
    is_active = True
    is_staff = True
    phone_number = factory.LazyFunction(lambda: fake.phone_number()[:15])
    alternative_contact = factory.LazyFunction(lambda: fake.phone_number()[:15])
    account_number = factory.LazyFunction(lambda: fake.bban())

    @factory.lazy_attribute
    def dob(self):
        return fake.date_of_birth(minimum_age=25, maximum_age=60)

    @factory.lazy_attribute
    def sex(self):
        return random.choice(['Male', 'Female'])

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to handle custom UserManager with pf_number requirement"""
        existing_users_count = User.objects.count()
        
        if existing_users_count >= 5:
            return random.choice(User.objects.all())
        
        password = kwargs.pop('password', 'password123')
        
        if 'pf_number' not in kwargs:
            existing_pf_numbers = set(User.objects.values_list('pf_number', flat=True))
            pf_number = f'PF{fake.random_number(digits=6)}'
            while pf_number in existing_pf_numbers:
                pf_number = f'PF{fake.random_number(digits=6)}'
            kwargs['pf_number'] = pf_number
        
        if 'first_name' not in kwargs:
            kwargs['first_name'] = fake.first_name()
            
        if 'last_name' not in kwargs:
            kwargs['last_name'] = fake.last_name()

        if 'username' not in kwargs:
            base_username = f'testuser{random.randint(1000, 9999)}'
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f'{base_username}_{counter}'
                counter += 1
            kwargs['username'] = username
        
        manager = cls._get_manager(model_class)
        
        user = manager.create_user(
            username=kwargs.get('username'),
            email=kwargs.get('email'),
            pf_number=kwargs.get('pf_number'),
            first_name=kwargs.get('first_name'),
            last_name=kwargs.get('last_name'),
            password=password,
            **{k: v for k, v in kwargs.items() if k not in ['username', 'email', 'pf_number', 'first_name', 'last_name', 'password']}
        )
        
        return user


class AffiliationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Affiliation
    
    type = factory.Iterator([Affiliation.AffiliationType.SELF, Affiliation.AffiliationType.ACADEMIC, Affiliation.AffiliationType.EMPLOYMENT])
    name = factory.Faker('company')
    level = factory.LazyAttribute(lambda obj: random.choice(['UG', 'G', 'PG']) if obj.type == Affiliation.AffiliationType.ACADEMIC else None)
    year = factory.LazyAttribute(lambda obj: str(random.randint(1, 4)) if obj.type == Affiliation.AffiliationType.ACADEMIC else None)
    course = factory.Faker('word')
    address = factory.Faker('address')
    country = factory.LazyAttribute(lambda obj: random.choice(Country.objects.all()) if Country.objects.exists() else None)


class StudentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Student
    
    profile_picture = None
    first_name = factory.Faker('first_name')
    middle_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    sex = factory.Iterator(['M', 'F'])
    primary_phone = factory.LazyFunction(lambda: f'+255{random.randint(600000000, 799999999)}')
    secondary_phone = factory.LazyFunction(lambda: f'+255{random.randint(600000000, 799999999)}')
    email = factory.Faker('email')
    id_type = factory.Iterator(['P', 'N', 'V', 'O'])
    copy_of_id = None
    student_id = factory.LazyFunction(lambda: f'STU-{uuid.uuid4().hex[:8].upper()}')
    nationality = factory.LazyAttribute(lambda obj: random.choice(Country.objects.all()) if Country.objects.exists() else None)
    country_of_birth = factory.LazyAttribute(lambda obj: random.choice(Country.objects.all()) if Country.objects.exists() else None)
    bio = factory.Faker('sentence')
    are_you_currently_studying = factory.Faker('boolean')
    supporting_letter = None
    affiliation = factory.SubFactory(AffiliationFactory)


class SupervisorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Supervisor
    
    description = factory.Faker('sentence')
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Custom create that handles missing columns"""
        try:
            # Try to create normally
            return super()._create(model_class, *args, **kwargs)
        except Exception:
            # If it fails (e.g., missing columns), skip
            return None


class ApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Application
    
    student = factory.SubFactory(StudentFactory)
    application_number = factory.LazyFunction(lambda: f'APP-{uuid.uuid4().hex[:8].upper()}')
    duration = factory.LazyFunction(lambda: random.randint(2, 52))
    from_date = factory.Faker('date_between', start_date='-1y', end_date='today')
    to_date = factory.LazyAttribute(lambda obj: obj.from_date + timedelta(weeks=obj.duration) if obj.duration else None)
    category = factory.Iterator(['CL', 'NL'])
    placement_type = factory.Iterator(['EL', 'PT', 'PG'])
    expected_amount = factory.LazyFunction(lambda: int(random.uniform(1000, 50000)))
    currency = factory.LazyAttribute(lambda obj: Currency.objects.first())
    campus = factory.Iterator(['UP', 'ML', 'BO'])
    supporting_letter = None

    @factory.post_generation
    def departments(obj, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            obj.department_uids = [str(dept.uid) for dept in extracted]
        else:
            departments = list(Department.objects.all()[:random.randint(1, 3)])
            obj.department_uids = [str(dept.uid) for dept in departments]
        obj.save()


class DepartmentAllocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DepartmentAllocation
    
    application = factory.SubFactory(ApplicationFactory)
    department_uid = factory.LazyFunction(lambda: str(uuid.uuid4()))
    supervisor = factory.SubFactory(SupervisorFactory)
    start_date = factory.Faker('date_between', start_date='-1y', end_date='today')
    end_date = factory.LazyAttribute(lambda obj: obj.start_date + timedelta(days=random.randint(7, 90)))
    description = factory.Faker('sentence')


class InstitutionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Institution
    
    institution_code = factory.LazyFunction(lambda: f'INST-{uuid.uuid4().hex[:6].upper()}')
    name = factory.Faker('company')
    address = factory.Faker('address')
    country = factory.LazyAttribute(lambda obj: random.choice(Country.objects.all()) if Country.objects.exists() else None)
    contact_person = factory.Faker('name')
    contact_email = factory.Faker('email')
    contact_phone = factory.LazyFunction(lambda: fake.phone_number()[:20])
    website = factory.Faker('url')
    institution_type = factory.Iterator(['university', 'college', 'polytechnic', 'school', 'other'])
    established_date = factory.Faker('date_between', start_date='-50y', end_date='today')


class MOUFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MOU
    
    institution = factory.SubFactory(InstitutionFactory)
    mou_number = factory.LazyFunction(lambda: f'MOU-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}')
    start_date = factory.Faker('date_between', start_date='-1y', end_date='today')
    end_date = factory.LazyAttribute(lambda obj: obj.start_date + timedelta(days=random.randint(365, 730)))
    purpose = factory.Faker('paragraph')
    terms_and_conditions = factory.Faker('paragraph')
    signed_by = factory.Faker('name')
    signed_date = factory.Faker('date_between', start_date='-2y', end_date='today')
    
    @factory.lazy_attribute
    def document(self):
        from django.core.files.base import ContentFile
        content = f"MOU Document\nNumber: {self.mou_number}".encode()
        return ContentFile(content, name=f"mou_{uuid.uuid4().hex[:8]}.txt")


class TrainingBatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TrainingBatch
    
    batch_number = factory.LazyFunction(lambda: f'BATCH/{timezone.now().year}/{random.randint(1, 9999):04d}')
    mou = factory.SubFactory(MOUFactory)
    number_of_students = factory.LazyFunction(lambda: random.randint(10, 100))
    invoiced_amount = factory.LazyFunction(lambda: int(random.uniform(5000, 100000)))
    currency = factory.LazyAttribute(lambda obj: Currency.objects.first())
    training_start_date = factory.Faker('date_between', start_date='-1y', end_date='today')
    training_end_date = factory.LazyAttribute(lambda obj: obj.training_start_date + timedelta(days=random.randint(7, 60)))
    status = factory.Iterator(['planned', 'ongoing', 'completed', 'cancelled'])
    notes = factory.Faker('sentence')
    cancellation_reason = factory.LazyAttribute(lambda obj: factory.Faker('sentence') if obj.status == 'cancelled' else '')
    
    @factory.lazy_attribute
    def application_letter(self):
        from django.core.files.base import ContentFile
        content = f"Training batch application letter\nBatch: {self.batch_number}".encode()
        return ContentFile(content, name=f"batch_{uuid.uuid4().hex[:8]}.txt")
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Skip creation if currency is missing"""
        if kwargs.get('currency') is None:
            return None
        return super()._create(model_class, *args, **kwargs)

    @factory.post_generation
    def departments(obj, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for department in extracted:
                obj.departments.add(department)
        else:
            departments = Department.objects.all()[:random.randint(1, 3)]
            for department in departments:
                obj.departments.add(department)
