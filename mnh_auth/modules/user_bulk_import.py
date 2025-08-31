import base64

import numpy as np
import pandas as pd
import csv
from io import  StringIO
from uuid import uuid4

from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from api.utils import base64_to_excel_file
from mnh_approval.response_codes import CustomResponse
from mnh_auth.models import Department, User, PositionalLevel, UserProfile
from mnh_auth.serializers import UserImportSerializer
from utils.permissions import HasMethodPermission


class BulkUserImportView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission, ]
    serializer_class = UserImportSerializer
    required_permissions = {
        "post": [
            "import_users",
        ],
    }

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.errors("Invalid request", data=serializer.errors)

        # Helper to safely convert any value to string
        def safe_str(val):
            if val is None:
                return ""
            return str(val).strip()

        try:
            with transaction.atomic():
                # Convert uploaded base64 file to Excel
                file_obj = base64_to_excel_file(serializer.validated_data['file'])
                df = pd.read_excel(file_obj)
                df = df.replace({np.nan: None})

                required_cols = [
                    "FIRSTNAME", "LAST_NAME", "LOGIN_ID", "USER_JOB_ROLE", "CHECK_NO",
                    "DIRECTORATE", "USER_DEPT", "OFFICE_LOCATION", "FILE_NO", "PHONE_NO", "GENDER"
                ]
                if not all(col in df.columns for col in required_cols):
                    return CustomResponse.errors(
                        "Missing required columns", data=required_cols
                    )

                df.columns = df.columns.str.upper().str.strip()

                # Cache departments, usernames, PF numbers, and positional levels
                department_map = {d.name.strip().lower(): d for d in
                                  Department.objects.select_related('directory').all()}
                existing_pf_numbers = set(User.objects.values_list("pf_number", flat=True))
                existing_usernames = set(User.objects.values_list("username", flat=True))
                positional_levels = {lvl.name.strip().upper(): lvl for lvl in
                                     PositionalLevel.objects.filter(is_active=True)}

                users = []
                user_profiles = []
                failed_rows = []

                # Iterate rows efficiently
                for row in df.itertuples(index=False):
                    try:
                        dept_name = safe_str(row.USER_DEPT)
                        dept = department_map.get(dept_name.lower())
                        if not dept:
                            raise Exception(f"Department '{dept_name}' not found")

                        username = safe_str(row.LOGIN_ID)
                        pf_number = safe_str(row.FILE_NO)

                        if not username:
                            raise Exception("Login ID is required")
                        if not pf_number:
                            raise Exception("PF Number is required")

                        if username in existing_usernames:
                            raise Exception(f"Duplicate User with Login ID: {username}")
                        if pf_number in existing_pf_numbers:
                            raise Exception(f"Duplicate User with PF number: {pf_number}")

                        job_role_code = safe_str(row.USER_JOB_ROLE).upper()
                        level = positional_levels.get(job_role_code)
                        if not level:
                            raise Exception(f"User Job role '{job_role_code}' not found or disabled")

                        user = User(
                            guid=uuid4(),
                            username=str(username).lower(),
                            email=f"{username}@mnh.or.tz",
                            pf_number=pf_number,
                            check_number=safe_str(row.CHECK_NO) or None,
                            office_location=safe_str(row.OFFICE_LOCATION),
                            first_name=safe_str(row.FIRSTNAME).upper(),
                            last_name=safe_str(row.LAST_NAME).upper(),
                            sex=safe_str(row.GENDER) or None,
                            phone_number=safe_str(row.PHONE_NO) or None,
                            created_by=request.user.id,
                            updated_by=request.user.id,
                            created_at=timezone.now(),
                            updated_at=timezone.now(),
                            is_active=True,
                            password=None,  # No password generated
                            status="NEW"  # Mark as NEW for first-time login
                        )
                        user.set_unusable_password()  # <-- This sets a special value, satisfies NOT NULL
                        users.append((user, level, dept))
                        existing_usernames.add(username)
                        existing_pf_numbers.add(pf_number)

                    except Exception as e:
                        failed_rows.append({
                            "FIRSTNAME": safe_str(getattr(row, "FIRSTNAME", "")),
                            "LAST_NAME": safe_str(getattr(row, "LAST_NAME", "")),
                            "LOGIN_ID": safe_str(getattr(row, "LOGIN_ID", "")),
                            "FILE_NO": safe_str(getattr(row, "FILE_NO", "")),
                            "CHECK_NO": safe_str(getattr(row, "CHECK_NO", "")),
                            "USER_DEPT": safe_str(getattr(row, "USER_DEPT", "")),
                            "USER_JOB_ROLE": safe_str(getattr(row, "USER_JOB_ROLE", "")),
                            "DIRECTORATE": safe_str(getattr(row, "DIRECTORATE", "")),
                            "PHONE_NO": safe_str(getattr(row, "PHONE_NO", "")),
                            "GENDER": safe_str(getattr(row, "GENDER", "")),
                            "OFFICE_LOCATION": safe_str(getattr(row, "OFFICE_LOCATION", "")),
                            "ERROR_MESSAGE": str(e),
                        })


                # Bulk create users
                User.objects.bulk_create([u[0] for u in users], batch_size=5000)

                # Map usernames to saved users
                username_to_user = {u.username: u for u in
                                    User.objects.filter(username__in=[u[0].username for u in users])}

                # Bulk create UserProfiles
                for user, level, dept in users:
                    db_user = username_to_user.get(user.username)
                    if db_user:
                        user_profiles.append(UserProfile(
                            uid=uuid4(),
                            user=db_user,
                            department=dept,
                            directory=dept.directory,
                            level=level,
                            is_active=True,
                            created_by=request.user,
                            updated_by=request.user,
                            created_at=timezone.now(),
                            updated_at=timezone.now(),
                        ))

                UserProfile.objects.bulk_create(user_profiles, batch_size=5000)

                # Prepare failed rows CSV
                csv_base64 = None
                if failed_rows:
                    csv_buffer = StringIO()
                    writer = csv.DictWriter(csv_buffer, fieldnames=[
                        "FIRSTNAME", "LAST_NAME", "LOGIN_ID", "FILE_NO", "CHECK_NO",
                        "USER_DEPT", "USER_JOB_ROLE", "DIRECTORATE", "OFFICE_LOCATION",
                        "PHONE_NO", "GENDER", "ERROR_MESSAGE"
                    ])
                    writer.writeheader()
                    writer.writerows(failed_rows)
                    csv_content = csv_buffer.getvalue().encode("utf-8")
                    csv_base64 = base64.b64encode(csv_content).decode("utf-8")

                return CustomResponse.success(
                    message=f"Import completed: {len(users)} success, {len(failed_rows)} failed.",
                    data={"failures_csv": csv_base64}
                )

        except Exception as e:
            print(e)
            return CustomResponse.errors("Import failed", data={"error": str(e)})
