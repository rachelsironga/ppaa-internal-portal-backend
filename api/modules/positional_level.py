import base64
import csv
from datetime import datetime
from io import BytesIO, StringIO
from uuid import uuid4

import numpy as np
import pandas as pd
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from api.serializers import PositionalLevelSerializer
from api.utils import base64_to_excel_file
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.models import Department, User, PositionalLevel, UserProfile
from mnh_auth.serializers import UserImportSerializer
from utils.permissions import HasMethodPermission



class PositionalLevelView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = PositionalLevelSerializer
    required_permissions = {
        "get": [
            "view_positionallevel"
        ],
        "post": [
            "add_positionallevel",
            "change_positionallevel",
        ],
        "delete": [
            "delete_positionallevel",
        ]
    }

    def get(self, request, uid=None):
        try:
            """ Retrieve a single Positional Level by UID or list Positional Levels with optional search """
            if uid:
                positional_level = PositionalLevel.objects.filter(uid=uid, is_deleted=False).first()
                if not positional_level:
                    raise NotFound("Positional Level not found")
                return CustomResponse.success(data=PositionalLevelSerializer(positional_level).data)

            search_query = request.GET.get('search', '').strip()
            positional_levels = PositionalLevel.objects.filter(is_deleted=False)

            if search_query:
                positional_levels = positional_levels.filter(
                    Q(name__icontains=search_query) | Q(code__icontains=search_query)
                )

            if positional_levels.exists():
                return CustomPagination.paginate(view_class=self, results=positional_levels, request=request)

            return CustomResponse.errors(message="Positional Level not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Positional Levels: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)

                # Handle Update case
                if uid:
                    try:
                        instance = PositionalLevel.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except PositionalLevel.DoesNotExist:
                        return CustomResponse.errors(message="Positional Level not found")

                # Handle Create case (when no uid)
                else:
                    serializer = self.serializer_class(data=request.data)

                # Validate and save
                if serializer.is_valid():
                    serializer.save(created_by=request.user, updated_by=request.user)
                    return CustomResponse.success(data=serializer.data)

                # Validation failed
                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            # Catch unexpected errors that occur in the entire process
            return CustomResponse.server_error(message=f'Failed to Change Positional Level: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Positional Level by UID """
                positional_level = PositionalLevel.objects.filter(uid=uid, is_deleted=False).first()
                if not positional_level:
                    return CustomResponse.errors(message="Positional Level Not Found or Deleted",)

                positional_level.is_deleted = True
                positional_level.deleted_at = datetime.now()
                positional_level.deleted_by = request.user
                positional_level.save()
                return CustomResponse.success(message='Positional Level deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Positional Level")

class BulkDesignationImportView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission, ]
    serializer_class = UserImportSerializer
    required_permissions = {
        "post": [
            "import_designations",
        ],
    }

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.errors("Invalid request", data=serializer.errors)

        try:
            with transaction.atomic():
                file_obj = base64_to_excel_file(serializer.validated_data['file'])
                df = pd.read_excel(file_obj)
                df = df.replace({np.nan: None})
                required_cols = [
                    "DESIGNATIONS"
                ]
                if not all(col in df.columns for col in required_cols):
                    return CustomResponse.errors("Missing required columns", data=required_cols)


                df.columns = df.columns.str.upper().str.strip()

                # Cache designations for fast lookup
                designation_map = {
                    lvl.name.strip().lower(): lvl for lvl in PositionalLevel.objects.filter(is_active=True).all()
                }

                designation_objs = []
                failed_rows = []
                index_number = 0
                for index, row in df.iterrows():
                    try:
                        index_number += 1
                        position = str(row["DESIGNATIONS"]).strip().lower()
                        if position is None or position == '':
                            raise Exception("DESIGNATIONS Column is required")

                        if position in designation_map:
                            raise Exception(f"Duplicate Designations with name : {position}")

                        position_code = position.replace(" ", "_")
                        # Add to map so duplicates in the same file are caught
                        designation_map[position] = None

                        designation_objs.append(PositionalLevel(
                            name=position,
                            code=position_code,
                            is_active=True,
                            created_by=request.user,
                            updated_by=request.user,
                            created_at=timezone.now(),
                            updated_at=timezone.now(),
                        ))

                    except Exception as e:
                        failed_rows.append({
                            "DESIGNATIONS": row.get("DESIGNATIONS"),
                            "ERROR_MESSAGE": str(e),
                        })

                PositionalLevel.objects.bulk_create(designation_objs, batch_size=1000)

                # Generate a failed report if needed
                csv_report = None
                if failed_rows:
                    csv_buffer = StringIO()
                    writer = csv.DictWriter(csv_buffer, fieldnames=[
                        "DESIGNATIONS","ERROR_MESSAGE"
                    ])
                    writer.writeheader()
                    writer.writerows(failed_rows)
                    # Get CSV content
                    csv_content = csv_buffer.getvalue().encode("utf-8")
                    # Save as Django ContentFile
                    csv_report = ContentFile(csv_content, name="failed_users.csv")
                    # Convert to Base64
                    csv_base64 = base64.b64encode(csv_content).decode("utf-8")

                return CustomResponse.success(
                    message=f"Import completed: {len(designation_objs)} success, {len(failed_rows)} failed.",
                    data={"failures_csv": csv_base64 if csv_report else None}
                )

        except Exception as e:
            return CustomResponse.errors("Import failed", data={"error": str(e)})
