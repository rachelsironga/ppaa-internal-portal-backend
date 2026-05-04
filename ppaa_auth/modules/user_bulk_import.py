<<<<<<< HEAD
import secrets
=======
import base64
import csv
from io import StringIO
from uuid import uuid4
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92

import numpy as np
import pandas as pd
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

<<<<<<< HEAD
from api.utils import base64_to_excel_file, generate_acronym
from ppaa_auth.models import Department, PositionalLevel, User, UserProfile
from ppaa_auth.serializers import UserImportSerializer
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission

REQUIRED_COLUMNS = [
    "FIRST_NAME",
    "MIDDLE_NAME",
    "LAST_NAME",
    "USERNAME",
    "GENDER",
    "PHONE_NO",
    "EMAIL",
    "DESIGNATION",
    "CHECK_NO",
    "DIRECTORATE",
    "DEPARTMENT",
    "OFFICE_LOCATION",
]

=======
from api.utils import base64_to_excel_file
from ppaa_portal.response_codes import CustomResponse
from ppaa_auth.models import Department, User, PositionalLevel, UserProfile
from ppaa_auth.serializers import UserImportSerializer
from utils.permissions import HasMethodPermission

>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92

class BulkUserImportView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = UserImportSerializer
<<<<<<< HEAD
    required_permissions = {"post": ["import_users"]}
=======
    required_permissions = {
        "post": ["import_users"],
    }

    REQUIRED_COLS = [
        "FIRST_NAME", "MIDDLE_NAME", "LAST_NAME", "USERNAME", "GENDER",
        "PHONE_NO", "EMAIL", "DESIGNATION", "CHECK_NO",
        "DIRECTORATE", "DEPARTMENT", "OFFICE_LOCATION",
    ]
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
<<<<<<< HEAD
            return CustomResponse.errors(
                message="Invalid request",
                data=serializer.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        try:
            with transaction.atomic():
                file_obj = base64_to_excel_file(serializer.validated_data["file"])
                df = pd.read_excel(file_obj)
                df = df.replace({np.nan: None})
                df.columns = df.columns.str.upper().str.strip()
                missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
                if missing:
                    return CustomResponse.errors(
                        message="Missing required columns",
                        data=missing,
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )

                created = 0
                failed = []

                for index, row in df.iterrows():
                    row_num = int(index) + 2
                    try:
                        username = (row["USERNAME"] or "").strip()
                        email = (row["EMAIL"] or "").strip()
                        if not username or not email:
                            raise ValueError("USERNAME and EMAIL are required")

                        if User.objects.filter(username__iexact=username).exists():
                            raise ValueError(f"Duplicate username: {username}")
                        if User.objects.filter(email__iexact=email).exists():
                            raise ValueError(f"Duplicate email: {email}")

                        department_name = (row["DEPARTMENT"] or "").strip()
                        designation = (row["DESIGNATION"] or "").strip()

                        department = None
                        if department_name:
                            department = Department.objects.filter(
                                name__iexact=department_name,
                                is_deleted=False,
                            ).first()
                            if not department:
                                dcode = generate_acronym(department_name)[:100]
                                department = Department.objects.create(
                                    name=department_name,
                                    code=dcode or "DEPT",
                                    created_by=request.user,
                                    updated_by=request.user,
                                )

                        level = None
                        if designation:
                            level = PositionalLevel.objects.filter(
                                name__iexact=designation, is_deleted=False
                            ).first()
                            if not level:
                                level = PositionalLevel.objects.create(
                                    name=designation,
                                    code=designation.replace(" ", "_").lower()[:100],
                                    created_by=request.user,
                                    updated_by=request.user,
                                )

                        password = secrets.token_urlsafe(16)
                        user = User.objects.create_user(
                            username=username,
                            email=email,
                            password=password,
                            first_name=(row["FIRST_NAME"] or "").strip() or "",
                            last_name=(row["LAST_NAME"] or "").strip() or "",
                            middle_name=(row["MIDDLE_NAME"] or "").strip() or "",
                            check_number=(row["CHECK_NO"] or "").strip() or "",
                            phone_number=(row["PHONE_NO"] or "").strip() or "",
                            office_location=(row["OFFICE_LOCATION"] or "").strip() or "",
                            sex=(row["GENDER"] or "").strip() or "",
                            created_by=request.user,
                            updated_by=request.user,
                        )

                        if department or level:
                            UserProfile.objects.create(
                                user=user,
                                department=department,
=======
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
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
                                level=level,
                                is_active=True,
                                created_by=request.user,
                                updated_by=request.user,
                                created_at=timezone.now(),
                                updated_at=timezone.now(),
                            )
<<<<<<< HEAD
                        created += 1
                    except Exception as exc:
                        failed.append({"row": row_num, "error": str(exc)})

                return CustomResponse.success(
                    data={"created": created, "failed": failed},
                    message="Import completed",
                )
        except Exception as exc:
            return CustomResponse.server_error(message=str(exc))
=======
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
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
