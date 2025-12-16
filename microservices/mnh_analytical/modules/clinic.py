import base64
import csv
from datetime import datetime
from io import StringIO
from uuid import uuid4

import numpy as np
import pandas as pd
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from api.utils import base64_to_excel_file
from microservices.mnh_analytical.models import Clinic, Block
from microservices.mnh_analytical.serializers import (
    ClinicSerializer, ClinicListSerializer, ClinicDetailSerializer
)
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.models import Department, Directory
from utils.permissions import HasMethodPermission


class ClinicView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = ClinicSerializer
    required_permissions = {
        "get": ["view_clinic"],
        "post": ["add_clinic", "change_clinic"],
        "put": ["change_clinic"],
        "patch": ["change_clinic"],
        "delete": ["delete_clinic"]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                clinic = Clinic.objects.filter(uid=uid, is_deleted=False).first()
                if not clinic:
                    raise NotFound("Clinic not found")
                return CustomResponse.success(data=ClinicDetailSerializer(clinic).data)

            search_query = request.GET.get('search', '').strip()
            block_uid = request.GET.get('block', '').strip()
            department_uid = request.GET.get('department', '').strip()
            clinics = Clinic.objects.filter(is_deleted=False)

            if search_query:
                clinics = clinics.filter(
                    Q(name__icontains=search_query) |
                    Q(code__icontains=search_query) |
                    Q(description__icontains=search_query)
                )

            if block_uid:
                clinics = clinics.filter(block__uid=block_uid)

            if department_uid:
                clinics = clinics.filter(department_uid=department_uid)

            if clinics.exists():
                return CustomPagination.paginate(view_class=self, results=clinics, request=request)

            return CustomResponse.errors(message="Clinics not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Clinics: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data, context={'request': request})

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Create Clinic: {str(e)}')

    def put(self, request, uid):
        try:
            with transaction.atomic():
                try:
                    instance = Clinic.objects.get(uid=uid, is_deleted=False)
                except Clinic.DoesNotExist:
                    return CustomResponse.errors(message="Clinic not found")

                serializer = self.serializer_class(instance, data=request.data, context={'request': request})

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Update Clinic: {str(e)}')

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                try:
                    instance = Clinic.objects.get(uid=uid, is_deleted=False)
                except Clinic.DoesNotExist:
                    return CustomResponse.errors(message="Clinic not found")

                serializer = self.serializer_class(
                    instance, data=request.data, partial=True, context={'request': request}
                )

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Update Clinic: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                clinic = Clinic.objects.filter(uid=uid, is_deleted=False).first()
                if not clinic:
                    return CustomResponse.errors(message="Clinic Not Found or Already Deleted")

                clinic.is_deleted = True
                clinic.deleted_at = datetime.now()
                clinic.deleted_by = request.user
                clinic.save()
                return CustomResponse.success(message='Clinic deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Clinic")


class ClinicImportSerializer(serializers.Serializer):
    file = serializers.CharField(required=True)


class BulkClinicImportView(APIView):
    """Bulk import clinics from Excel file"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = ClinicImportSerializer
    required_permissions = {
        "post": ["import_clinics"],
    }

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.errors("Invalid request", data=serializer.errors)

        def safe_str(val):
            if val is None or pd.isna(val):
                return ""
            return str(val).strip()

        try:
            with transaction.atomic():
                file_obj = base64_to_excel_file(serializer.validated_data['file'])
                df = pd.read_excel(file_obj)
                df = df.replace({np.nan: None})

                required_cols = ["name", "code"]
                if not all(col in df.columns for col in required_cols):
                    return CustomResponse.errors(
                        "Missing required columns. Required: name, code. Optional: block, department, description",
                        data=required_cols
                    )

                df.columns = df.columns.str.lower().str.strip()

                block_map = {b.code.strip().upper(): b for b in Block.objects.filter(is_deleted=False)}
                block_name_map = {b.name.strip().upper(): b for b in Block.objects.filter(is_deleted=False)}
                
                dept_map = {d.name.strip().upper(): d for d in Department.objects.using('default').filter(is_deleted=False)}
                dept_code_map = {d.code.strip().upper(): d for d in Department.objects.using('default').filter(is_deleted=False)}
                
                existing_clinics = set(
                    Clinic.objects.filter(is_deleted=False).values_list('name', 'code')
                )

                clinics_to_create = []
                failed_rows = []
                success_count = 0

                for _, row in df.iterrows():
                    try:
                        name = safe_str(row.get('name', ''))
                        code = safe_str(row.get('code', ''))
                        block_val = safe_str(row.get('block', ''))
                        dept_val = safe_str(row.get('department', ''))
                        description = safe_str(row.get('description', ''))

                        if not name:
                            raise Exception("Clinic name is required")
                        if not code:
                            raise Exception("Clinic code is required")

                        if (name, code) in existing_clinics:
                            raise Exception(f"Clinic with name '{name}' and code '{code}' already exists")

                        block = None
                        if block_val:
                            block = block_map.get(block_val.upper()) or block_name_map.get(block_val.upper())
                            if not block:
                                block = Block.objects.create(
                                    uid=uuid4(),
                                    name=block_val,
                                    code=block_val.upper().replace(' ', '_'),
                                    is_active=True,
                                    created_by=request.user,
                                    updated_by=request.user,
                                )
                                block_map[block.code.upper()] = block
                                block_name_map[block.name.upper()] = block

                        department = None
                        if dept_val:
                            department = dept_map.get(dept_val.upper()) or dept_code_map.get(dept_val.upper())
                            if not department:
                                default_directory = Directory.objects.using('default').filter(
                                    is_deleted=False
                                ).first()
                                if not default_directory:
                                    default_directory = Directory.objects.using('default').create(
                                        uid=uuid4(),
                                        name="Default Directory",
                                        code="DEFAULT",
                                        description="Auto-created directory for imported departments",
                                        created_by=request.user,
                                        updated_by=request.user,
                                    )
                                department = Department.objects.using('default').create(
                                    uid=uuid4(),
                                    name=dept_val,
                                    code=dept_val.upper().replace(' ', '_'),
                                    directory=default_directory,
                                    is_active=True,
                                    created_by=request.user,
                                    updated_by=request.user,
                                )
                                dept_map[department.name.upper()] = department
                                dept_code_map[department.code.upper()] = department

                        clinic = Clinic(
                            uid=uuid4(),
                            name=name,
                            code=code,
                            block=block,
                            department=department,
                            description=description or None,
                            is_active=True,
                            created_by=request.user,
                            updated_by=request.user,
                        )
                        clinics_to_create.append(clinic)
                        existing_clinics.add((name, code))
                        success_count += 1

                    except Exception as e:
                        failed_rows.append({
                            "name": safe_str(row.get('name', '')),
                            "code": safe_str(row.get('code', '')),
                            "block": safe_str(row.get('block', '')),
                            "department": safe_str(row.get('department', '')),
                            "description": safe_str(row.get('description', '')),
                            "error": str(e),
                        })

                Clinic.objects.bulk_create(clinics_to_create, batch_size=500)

                csv_base64 = None
                if failed_rows:
                    csv_buffer = StringIO()
                    writer = csv.DictWriter(csv_buffer, fieldnames=[
                        "name", "code", "block", "department", "description", "error"
                    ])
                    writer.writeheader()
                    writer.writerows(failed_rows)
                    csv_content = csv_buffer.getvalue().encode("utf-8")
                    csv_base64 = base64.b64encode(csv_content).decode("utf-8")

                return CustomResponse.success(
                    message=f"Import completed: {success_count} success, {len(failed_rows)} failed.",
                    data={
                        "successfully_created": success_count,
                        "failed_count": len(failed_rows),
                        "failures_csv": csv_base64
                    }
                )

        except Exception as e:
            return CustomResponse.server_error(message=f"Import failed: {str(e)}")
