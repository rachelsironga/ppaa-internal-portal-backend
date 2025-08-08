import base64

import numpy as np
import pandas as pd
import csv
from io import BytesIO, StringIO
from uuid import uuid4
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.http import FileResponse
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

        try:
            with transaction.atomic():
                file_obj = base64_to_excel_file(serializer.validated_data['file'])
                df = pd.read_excel(file_obj)
                df = df.replace({np.nan: None})
                required_cols = [
                    "FIRSTNAME", "LAST_NAME", "LOGIN_ID", "USER_JOB_ROLE", "CHECK_NO",
                    "DIRECTORATE", "USER_DEPT", "OFFICE_LOCATION", "FILE_NO"
                ]
                if not all(col in df.columns for col in required_cols):
                    return CustomResponse.errors("Missing required columns", data=required_cols)


                df.columns = df.columns.str.upper().str.strip()


                # Cache departments for fast lookup
                department_map = {
                    dept.name.strip().lower(): dept for dept in Department.objects.select_related('directory').all()
                }

                # Cache existing pf_numbers
                existing_pf_numbers = set(User.objects.values_list("pf_number", flat=True))
                existing_usernames = set(User.objects.values_list("username", flat=True))

                # Cache Positional Levels
                positional_levels = {
                    lvl.name.strip().upper(): lvl for lvl in PositionalLevel.objects.filter(is_active=True)
                }

                user_objs = []
                user_profiles = []
                failed_rows = []
                index_number = 0
                for index, row in df.iterrows():
                    try:
                        index_number += 1
                        dept_name = str(row["USER_DEPT"]).strip()
                        dept = department_map.get(dept_name.lower())
                        if not dept:
                            raise Exception(f"Department '{dept_name}' not found")

                        username = str(row["LOGIN_ID"]).strip()
                        pf_number = str(row["FILE_NO"]).strip()


                        if username is None or username == '':
                            raise Exception("Login ID is required")
                        if pf_number is None or pf_number == '':
                            raise Exception("PF Number is required")

                        if username in existing_usernames:
                            raise Exception(f"Duplicate User with Login id : {username}")

                        if pf_number in existing_pf_numbers:
                            raise Exception(f"Duplicate User with PF number : {pf_number}")

                        job_role_code = str(row["USER_JOB_ROLE"]).strip().upper()
                        level = positional_levels.get(job_role_code)
                        if not level:
                            raise Exception(f"User Job role '{job_role_code}' not found in the System or Disabled")

                        user = User(
                            guid=uuid4(),
                            username=username,
                            email=f'{username}@mnh.or.tz',
                            pf_number=pf_number,
                            check_number=str(row["CHECK_NO"]).strip() if str(row["CHECK_NO"]).strip() else None,
                            office_location=str(row["OFFICE_LOCATION"]).strip(),
                            first_name=str(row["FIRSTNAME"]).strip(),
                            last_name=str(row["LAST_NAME"]).strip(),
                            sex=str(row["GENDER"]).strip() if str(row["GENDER"]).strip() else None,
                            phone_number=str(row["PHONE_NO"]).strip() if str(row["PHONE_NO"]).strip() else None,
                            middle_name="",
                            created_by=request.user.id,
                            updated_by=request.user.id,
                            created_at=timezone.now(),
                            updated_at=timezone.now(),
                            is_active=True
                        )
                        password = f"{user.last_name.upper()}@{pf_number}"
                        user.set_password(password)
                        # Save both for later profile creation
                        user_objs.append((user, level, dept))

                        # Track added emails and PFs
                        existing_usernames.add(username)
                        existing_pf_numbers.add(pf_number)

                    except Exception as e:
                        failed_rows.append({
                            "FIRSTNAME": row.get("FIRSTNAME"),
                            "LAST_NAME": row.get("LAST_NAME"),
                            "LOGIN_ID": row.get("LOGIN_ID"),
                            "FILE_NO": row.get("FILE_NO"),
                            "CHECK_NO": row.get("CHECK_NO"),
                            "USER_DEPT": row.get("USER_DEPT"),
                            "USER_JOB_ROLE": row.get("USER_JOB_ROLE"),
                            "DIRECTORATE": row.get("DIRECTORATE"),
                            "OFFICE_LOCATION": row.get("OFFICE_LOCATION"),
                            "ERROR_MESSAGE": str(e),
                        })

                # Separate user and level from saved tuples
                users = [item[0] for item in user_objs]
                User.objects.bulk_create(users, batch_size=1000)


                # Re-map email to User to safely link UserProfiles
                username_to_user = {user.username: user for user in User.objects.filter(username__in=[u.username for u in users])}

                for user, level, dept in user_objs:
                    db_user = username_to_user.get(user.username)
                    if db_user and dept and level:
                        user_profiles.append(UserProfile(
                            uid=uuid4(),
                            user=db_user,
                            department=dept,
                            directory=dept.directory,
                            level=level,
                            is_active=True,
                            created_by = request.user,
                            updated_by = request.user,
                            created_at = timezone.now(),
                            updated_at = timezone.now(),
                        ))

                UserProfile.objects.bulk_create(user_profiles, batch_size=1000)

                # Generate a failed report if needed
                csv_report = None
                if failed_rows:
                    csv_buffer = StringIO()
                    writer = csv.DictWriter(csv_buffer, fieldnames=[
                        "FIRSTNAME","LAST_NAME","LOGIN_ID","FILE_NO","CHECK_NO","USER_DEPT","USER_JOB_ROLE",
                        "DIRECTORATE", "OFFICE_LOCATION","ERROR_MESSAGE"
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
                    message=f"Import completed: {len(user_objs)} success, {len(failed_rows)} failed.",
                    data={"failures_csv": csv_base64 if csv_report else None}
                )

        except Exception as e:
            return CustomResponse.errors("Import failed", data={"error": str(e)})
