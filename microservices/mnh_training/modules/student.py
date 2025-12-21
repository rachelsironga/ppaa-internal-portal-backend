# student.py
import csv
import io
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from microservices.mnh_training.models import Student
from microservices.mnh_training.serializers import StudentSerializer, StudentListSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission

try:
    from mnh_auth.models import Country
except ImportError:
    Country = None


class StudentView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = StudentSerializer
    list_serializer_class = StudentListSerializer

    required_permissions = {
        "get": ["view_student"],
        "post": ["add_student", "change_student"],
        "put": ["change_student"],
        "patch": ["change_student"],
        "delete": ["delete_student"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                student = Student.objects.filter(uid=uid, is_deleted=False).first()
                if not student:
                    raise NotFound("Student not found")
                return CustomResponse.success(data=self.serializer_class(student).data)

            search_query = request.GET.get('search', '').strip()
            student_type = request.GET.get('type', '').strip()

            students = Student.objects.filter(is_deleted=False)

            if student_type:
                students = students.filter(type=student_type)

            if search_query:
                students = students.filter(
                    Q(first_name__icontains=search_query) |
                    Q(last_name__icontains=search_query) |
                    Q(email__icontains=search_query) |
                    Q(student_id__icontains=search_query) |
                    Q(primary_phone__icontains=search_query)
                )

            if students.exists():
                # Use list serializer for pagination
                serializer = self.list_serializer_class(
                    students,
                    many=True,
                    context={'request': request}
                )
                return CustomResponse.success(
                    data=serializer.data,
                    message="Success"
                )

            return CustomResponse.errors(message="Students not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Students: {str(e)}'
            )

    def post(self, request):
        try:
            # Check if this is an import request
            if 'file' in request.FILES:
                return self._import_students(request)
            
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = Student.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Student not found")

                    serializer = self.serializer_class(
                        instance,
                        data=request.data,
                        partial=True,
                        context={'request': request}
                    )
                else:
                    serializer = self.serializer_class(
                        data=request.data,
                        context={'request': request}
                    )

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Create/Update Student: {str(e)}'
            )
    
    def _import_students(self, request):
        """Handle CSV import of students"""
        try:
            file = request.FILES['file']
            
            if not file.name.endswith('.csv'):
                return CustomResponse.errors(message="Please upload a CSV file")
            
            decoded_file = file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            created_count = 0
            updated_count = 0
            errors = []
            
            with transaction.atomic():
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Clean and prepare row data
                        student_data = {
                            'first_name': row.get('first_name', '').strip(),
                            'middle_name': row.get('middle_name', '').strip() or None,
                            'last_name': row.get('last_name', '').strip(),
                            'email': row.get('email', '').strip().lower(),
                            'primary_phone': row.get('primary_phone', '').strip(),
                            'secondary_phone': row.get('secondary_phone', '').strip() or None,
                            'sex': row.get('sex', '').strip().upper(),
                            'student_id': row.get('student_id', '').strip(),
                            'id_type': row.get('id_type', '').strip().upper() or None,
                            'are_you_currently_studying': row.get('are_you_currently_studying', '').strip().lower() == 'true',
                        }
                        
                        # Handle nationality
                        nationality_name = row.get('nationality', '').strip()
                        if nationality_name and Country:
                            nationality = Country.objects.filter(
                                name__iexact=nationality_name,
                                is_deleted=False
                            ).first()
                            if nationality:
                                student_data['nationality'] = nationality
                        
                        # Check if student exists by email or student_id
                        existing_student = Student.objects.filter(
                            Q(email__iexact=student_data['email']) | 
                            Q(student_id=student_data['student_id']),
                            is_deleted=False
                        ).first()
                        
                        if existing_student:
                            # Update existing student
                            for key, value in student_data.items():
                                if value is not None:
                                    setattr(existing_student, key, value)
                            existing_student.updated_by = request.user
                            existing_student.save()
                            updated_count += 1
                        else:
                            # Create new student
                            student = Student(
                                **student_data,
                                created_by=request.user,
                                updated_by=request.user
                            )
                            student.save()
                            created_count += 1
                            
                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")
            
            message = f"Import complete. Created: {created_count}, Updated: {updated_count}"
            if errors:
                message += f", Errors: {len(errors)}"
                return CustomResponse.success(
                    message=message,
                    data={'created': created_count, 'updated': updated_count, 'errors': errors[:10]}
                )
            
            return CustomResponse.success(
                message=message,
                data={'created': created_count, 'updated': updated_count}
            )
            
        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to import students: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = Student.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Student not found")

                serializer = self.serializer_class(
                    instance,
                    data=request.data,
                    partial=True,
                    context={'request': request}
                )

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Update Student: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = Student.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Student not found")

                serializer = self.serializer_class(
                    instance,
                    data=request.data,
                    partial=True,
                    context={'request': request}
                )

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Partially Update Student: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                student = Student.objects.filter(uid=uid, is_deleted=False).first()
                if not student:
                    return CustomResponse.errors(message="Student Not Found or Already Deleted")

                student.is_deleted = True
                student.deleted_at = datetime.now()
                student.deleted_by = request.user
                student.save()

                return CustomResponse.success(message='Student deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting Student"
            )
