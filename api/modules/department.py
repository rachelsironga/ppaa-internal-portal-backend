from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.http import Http404
from oauthlib.openid.connect.core.exceptions import LoginRequired
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.utils import timezone
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from api.serializers import DepartmentSerializer, DepartmentImportSerializer
from api.utils import base64_to_excel_file, generate_acronym
from ppaa_portal.pagination import CustomPagination
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_auth.models import Department
from utils.permissions import HasMethodPermission
from ppaa_portal.models import AuditLog

import pandas as pd



class DepartmentView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = DepartmentSerializer
    required_permissions = {
        "get": [
              "view_department", "can_view_department","can_view_department_lookup"
            ],
        "post": [
            "add_department",
            "change_department",
        ],
        "delete": [
            "delete_department",
        ]
    }

    @swagger_auto_schema(
        operation_description="Retrieve a single department by UID or list all departments with optional search",
        manual_parameters=[
            openapi.Parameter('search', openapi.IN_QUERY, description="Search query for name or code", type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER, required=False),
            openapi.Parameter('page_size', openapi.IN_QUERY, description="Page size", type=openapi.TYPE_INTEGER, required=False),
        ],
        responses={
            200: openapi.Response('Success', DepartmentSerializer),
            404: openapi.Response('Department not found'),
            500: openapi.Response('Server error'),
        }
    )
    def get(self, request, uid=None):
        try:
            """ Retrieve a single Department by UID or list Departments with optional search """
            if uid:
                department = Department.objects.filter(uid=uid, is_deleted=False).first()
                if not department:
                    raise NotFound("Department not found")
                
                # Log view action
                try:
                    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
                    ip_address = request.META.get("REMOTE_ADDR")
                    user_agent = request.META.get("HTTP_USER_AGENT", "")[:500] if request.META.get("HTTP_USER_AGENT") else ""
                    dept = department
                    AuditLog.objects.create(
                        user=user,
                        action="VIEW",
                        model_name="Department",
                        object_id=department.uid,
                        object_repr=str(department)[:200],
                        ip_address=ip_address,
                        user_agent=user_agent,
                        department=dept,
                        created_by=user if user else None,
                        updated_by=user if user else None,
                    )
                except Exception:
                    pass
                
                serializer = DepartmentSerializer(department)
                return CustomResponse.success(data=serializer.data)

            search_query = request.GET.get('search', '').strip()
            departments = Department.objects.filter(is_deleted=False)

            if search_query:
                departments = departments.filter(
                    Q(name__icontains=search_query) | Q(code__icontains=search_query)
                )

            if departments.exists():
                return CustomPagination.paginate(view_class=self, results=departments, request=request)

            return CustomResponse.errors(message="Department not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Departments: {str(e)}', )

    @swagger_auto_schema(
        operation_description="Create a new department or update an existing one (if uid is provided in request body)",
        request_body=DepartmentSerializer,
        responses={
            200: openapi.Response('Success', DepartmentSerializer),
            400: openapi.Response('Validation error'),
            500: openapi.Response('Server error'),
        }
    )
    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)

                # Handle an Update case
                if uid:
                    try:
                        instance = Department.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except Department.DoesNotExist:
                        return CustomResponse.errors(message="Department not found")

                # Handle Create a case (when no uid)
                else:
                    serializer = self.serializer_class(data=request.data)

                # Validate and save
                if serializer.is_valid():
                    department = serializer.save(created_by=request.user, updated_by=request.user)
                    
                    # Log create/update action
                    try:
                        ip_address = request.META.get("REMOTE_ADDR")
                        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500] if request.META.get("HTTP_USER_AGENT") else ""
                        dept = department
                        action = "UPDATE" if uid else "CREATE"
                        AuditLog.objects.create(
                            user=request.user,
                            action=action,
                            model_name="Department",
                            object_id=department.uid,
                            object_repr=str(department)[:200],
                            changes={"data": serializer.data},
                            ip_address=ip_address,
                            user_agent=user_agent,
                            department=dept,
                            created_by=request.user,
                            updated_by=request.user,
                        )
                    except Exception:
                        pass
                    
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            # Catch unexpected errors that occur in the entire process
            return CustomResponse.server_error(message=f'Failed to Change Department: {str(e)}', )

    @swagger_auto_schema(
        operation_description="Soft delete a department by UID",
        manual_parameters=[
            openapi.Parameter('uid', openapi.IN_PATH, description="Department UID", type=openapi.TYPE_STRING, required=True),
        ],
        responses={
            200: openapi.Response('Department deleted successfully'),
            404: openapi.Response('Department not found'),
            500: openapi.Response('Server error'),
        }
    )
    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Department by UID """
                department = Department.objects.filter(uid=uid, is_deleted=False).first()
                if not department:
                    return CustomResponse.errors(message="Department Not Found or Deleted", )

                department.is_deleted = True
                department.deleted_at = timezone.datetime.now()
                department.deleted_by = request.user
                department.save()
                
                # Log delete action
                try:
                    ip_address = request.META.get("REMOTE_ADDR")
                    user_agent = request.META.get("HTTP_USER_AGENT", "")[:500] if request.META.get("HTTP_USER_AGENT") else ""
                    dept = department
                    AuditLog.objects.create(
                        user=request.user,
                        action="DELETE",
                        model_name="Department",
                        object_id=department.uid,
                        object_repr=str(department)[:200],
                        ip_address=ip_address,
                        user_agent=user_agent,
                        department=dept,
                        created_by=request.user,
                        updated_by=request.user,
                    )
                except Exception:
                    pass
                
                return CustomResponse.success(message='Department deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Department")

class UploadDepartmentExcelView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission, ]
    serializer_class = DepartmentImportSerializer
    required_permissions = {
        "post": [
            "import_department",
        ],
    }


    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.errors(message="Invalid request", data=serializer.errors)

        try:
            with transaction.atomic():
                # Step 1: Decode Excel file
                file_obj = base64_to_excel_file(serializer.validated_data['file'])

                # Step 2: Read Excel into DataFrame
                df = pd.read_excel(file_obj)

                required_cols = ["DEPARTMENT", "OFFICE_LOCATION"]
                if not all(col in df.columns for col in required_cols):
                    return CustomResponse.errors(message="Missing required columns", data=required_cols)

                failed_rows, success_count = [], 0

                # Step 3: Iterate rows and import
                for _, row in df.iterrows():
                    try:
                        dept_name = str(row["DEPARTMENT"]).strip()
                        office_location = str(row["OFFICE_LOCATION"]).strip()

                        if not dept_name or not office_location:
                            raise ValueError("Department or Office Location is missing")

                        dept_code = generate_acronym(dept_name)

                        # Create/get Directory
                        directory = Directory.objects.filter(
                            Q(name__iexact=dir_name) | Q(code__iexact=dir_code)
                        ).first()

                        if not directory:
                            directory = Directory.objects.create(name=dir_name, code=dir_code)

                        # Check for existing department
                        if Department.objects.filter(name__iexact=dept_name, directory=directory).exists():
                            failed_rows.append({
                                "department": dept_name,
                                "directory": dir_name,
                                "reason": f"Already exists as a department in this directory: {directory.name}"
                            })
                            continue

                        # Create department
                        department = Department.objects.create(
                            name=dept_name,
                            code=dept_code,
                            directory=directory,
                            created_by=request.user,
                            updated_by=request.user
                        )
                        
                        # Create audit log for bulk import
                        try:
                            ip_address = request.META.get("REMOTE_ADDR")
                            user_agent = request.META.get("HTTP_USER_AGENT", "")[:500] if request.META.get("HTTP_USER_AGENT") else ""
                            AuditLog.objects.create(
                                user=request.user,
                                action="CREATE",
                                model_name="Department",
                                object_id=department.uid,
                                object_repr=str(department)[:200],
                                changes={"source": "Bulk Import", "data": {"name": dept_name, "code": dept_code}},
                                ip_address=ip_address,
                                user_agent=user_agent,
                                department=department,
                                created_by=request.user,
                                updated_by=request.user,
                            )
                        except Exception:
                            pass
                        
                        success_count += 1

                    except Exception as e:
                        failed_rows.append({
                            "department": row.get("DEPARTMENT", "Unknown"),
                            "office_location": row.get("OFFICE_LOCATION", "Unknown"),
                            "reason": str(e)
                        })

                return CustomResponse.success(
                    data={
                        "successfully_created": success_count,
                        "failed": failed_rows
                    })

        except Exception as e:
            return CustomResponse.server_error(message=f"Import failed: {str(e)}")
