import base64
import csv
from io import StringIO
from uuid import uuid4

import numpy as np
import pandas as pd
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from api.utils import base64_to_excel_file
from ppaa_portal.response_codes import CustomResponse
from ppaa_auth.models import Department, User, PositionalLevel, UserProfile
from ppaa_auth.serializers import UserImportSerializer
from utils.permissions import HasMethodPermission


class BulkUserImportView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = UserImportSerializer
    required_permissions = {
        "post": ["import_users"],
    }

    REQUIRED_COLS = [
        "FIRST_NAME", "MIDDLE_NAME", "LAST_NAME", "USERNAME", "GENDER",
        "PHONE_NO", "EMAIL", "DESIGNATION", "CHECK_NO",
        "DIRECTORATE", "DEPARTMENT", "OFFICE_LOCATION",
    ]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.errors("Invalid request", serializer.errors)

        def safe_str(val):
            return str(val).strip() if val not in (None, "", np.nan) else ""

        try:
            with transaction.atomic():

                # ================= FILE & DATAFRAME =================
                file_obj = base64_to_excel_file(serializer.validated_data["file"])
                df = pd.read_excel(file_obj)
                df.columns = df.columns.str.upper().str.strip()
                df = df.replace({np.nan: None})

                missing_cols = [c for c in self.REQUIRED_COLS if c not in df.columns]
                if missing_cols:
                    return CustomResponse.errors(
                        "Missing required columns",
                        {"missing_columns": missing_cols}
                    )

                # ================= PRELOAD DB DATA =================
                departments = {
                    d.name.strip().lower(): d
                    for d in Department.objects.select_related("directory")
                }

                levels = {
                    l.name.strip().upper(): l
                    for l in PositionalLevel.objects.filter(is_active=True)
                }

                existing_usernames = set(
                    User.objects.values_list("username", flat=True)
                )

                users_to_create = []
                profiles_to_create = []
                failed_rows = []

                # ================= PROCESS ROWS =================
                for row in df.itertuples(index=False):
                    row_data = {col: safe_str(getattr(row, col)) for col in self.REQUIRED_COLS}

                    try:
                        # ---- REQUIRED FIELD CHECK ----
                        missing_fields = [k for k, v in row_data.items() if not v]
                        if missing_fields:
                            raise Exception(f"Missing required fields: {', '.join(missing_fields)}")

                        username = row_data["USERNAME"].lower()

                        if username in existing_usernames:
                            raise Exception("Username already exists")

                        dept = departments.get(row_data["DEPARTMENT"].lower())
                        if not dept:
                            raise Exception(f"Department '{row_data['DEPARTMENT']}' not found")

                        level = levels.get(row_data["DESIGNATION"].upper())
                        if not level:
                            raise Exception(f"Designation '{row_data['DESIGNATION']}' not found")

                        user = User(
                            guid=uuid4(),
                            username=username,
                            email=row_data["EMAIL"],
                            check_number=row_data["CHECK_NO"],
                            office_location=row_data["OFFICE_LOCATION"],
                            first_name=row_data["FIRST_NAME"].upper(),
                            middle_name=row_data["MIDDLE_NAME"].upper(),
                            last_name=row_data["LAST_NAME"].upper(),
                            sex=row_data["GENDER"],
                            phone_number=row_data["PHONE_NO"],
                            created_by=request.user.id,
                            updated_by=request.user.id,
                            created_at=timezone.now(),
                            updated_at=timezone.now(),
                            is_active=True,
                            status="NEW",
                        )
                        user.set_unusable_password()

                        users_to_create.append((user, dept, level))
                        existing_usernames.add(username)

                    except Exception as e:
                        row_data["ERROR_MESSAGE"] = str(e)
                        failed_rows.append(row_data)

                # ================= BULK CREATE USERS =================
                User.objects.bulk_create(
                    [u[0] for u in users_to_create],
                    batch_size=5000
                )

                created_users = {
                    u.username: u
                    for u in User.objects.filter(
                        username__in=[u[0].username for u in users_to_create]
                    )
                }

                # ================= BULK CREATE PROFILES =================
                for user, dept, level in users_to_create:
                    db_user = created_users.get(user.username)
                    if db_user:
                        profiles_to_create.append(
                            UserProfile(
                                uid=uuid4(),
                                user=db_user,
                                department=dept,
                                level=level,
                                is_active=True,
                                created_by=request.user,
                                updated_by=request.user,
                                created_at=timezone.now(),
                                updated_at=timezone.now(),
                            )
                        )

                UserProfile.objects.bulk_create(profiles_to_create, batch_size=5000)

                # ================= FAILED CSV =================
                csv_base64 = None
                if failed_rows:
                    buffer = StringIO()
                    writer = csv.DictWriter(
                        buffer,
                        fieldnames=self.REQUIRED_COLS + ["ERROR_MESSAGE"]
                    )
                    writer.writeheader()
                    writer.writerows(failed_rows)
                    csv_base64 = base64.b64encode(
                        buffer.getvalue().encode()
                    ).decode()

                return CustomResponse.success(
                    message=f"Import completed: {len(users_to_create)} success, {len(failed_rows)} failed.",
                    data={"failures_csv": csv_base64},
                )

        except Exception as e:
            return CustomResponse.errors(
                "Import failed",
                {"error": str(e)}
            )
