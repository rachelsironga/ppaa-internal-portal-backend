# student.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_training.models import Student
from microservices.mnh_training.serializers import StudentSerializer, StudentListSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class StudentView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
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

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = Student.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Student not found")

                serializer = self.serializer_class(
                    instance,
                    data=request.data,
                    partial=False,
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
