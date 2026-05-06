import secrets

import numpy as np
import pandas as pd
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

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

class BulkUserImportView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = UserImportSerializer
    required_permissions = {"post": ["import_users"]}

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
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
                                level=level,
                                is_active=True,
                                created_by=request.user,
                                updated_by=request.user,
                            )
                        created += 1
                    except Exception as exc:
                        failed.append({"row": row_num, "error": str(exc)})

                return CustomResponse.success(
                    data={"created": created, "failed": failed},
                    message="Import completed",
                )
        except Exception as exc:
            return CustomResponse.server_error(message=str(exc))
