# training_attendance.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_training.models import TrainingAttendance, TrainingSession, Application
from microservices.mnh_training.serializers import TrainingAttendanceSerializer, TrainingAttendanceListSerializer
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class TrainingAttendanceView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = TrainingAttendanceSerializer
    list_serializer_class = TrainingAttendanceListSerializer

    required_permissions = {
        "get": ["view_trainingattendance"],
        "post": ["add_trainingattendance", "change_trainingattendance"],
        "put": ["change_trainingattendance"],
        "patch": ["change_trainingattendance"],
        "delete": ["delete_trainingattendance"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                attendance = TrainingAttendance.objects.filter(uid=uid, is_deleted=False).first()
                if not attendance:
                    raise NotFound("Training attendance record not found")
                return CustomResponse.success(data=self.serializer_class(attendance).data)

            session_uid = request.GET.get('session_uid', '').strip()
            application_uid = request.GET.get('application_uid', '').strip()
            status = request.GET.get('status', '').strip()

            attendances = TrainingAttendance.objects.filter(is_deleted=False)

            if session_uid:
                attendances = attendances.filter(session__uid=session_uid)

            if application_uid:
                attendances = attendances.filter(application__uid=application_uid)

            if status:
                attendances = attendances.filter(status=status)

            if attendances.exists():
                serializer = self.list_serializer_class(
                    attendances.order_by('session__session_date', 'application__student__last_name'),
                    many=True,
                    context={'request': request}
                )
                return CustomResponse.success(data=serializer.data)

            return CustomResponse.errors(message="Attendance records not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Attendance Records: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = TrainingAttendance.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Attendance record not found")

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
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Create/Update Attendance Record: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = TrainingAttendance.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Attendance record not found")

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
                message=f'Failed to Update Attendance Record: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = TrainingAttendance.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Attendance record not found")

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
                message=f'Failed to Partially Update Attendance Record: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                attendance = TrainingAttendance.objects.filter(uid=uid, is_deleted=False).first()
                if not attendance:
                    return CustomResponse.errors(message="Attendance record not found or already deleted")

                attendance.is_deleted = True
                attendance.deleted_at = datetime.now()
                attendance.deleted_by = request.user
                attendance.save()

                return CustomResponse.success(message='Attendance record deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(
                message="Something went wrong while deleting attendance record"
            )

    def bulk_mark_attendance(self, request):
        """Bulk mark attendance for a session"""
        try:
            with transaction.atomic():
                session_uid = request.data.get('session_uid')
                attendance_data = request.data.get('attendance_records', [])

                if not session_uid or not attendance_data:
                    return CustomResponse.errors(
                        message="session_uid and attendance_records are required"
                    )

                session = TrainingSession.objects.filter(uid=session_uid, is_deleted=False).first()
                if not session:
                    return CustomResponse.errors(message="Training session not found")

                created_count = 0
                for record in attendance_data:
                    application_uid = record.get('application_uid')
                    status = record.get('status')

                    if not application_uid or not status:
                        continue

                    attendance, created = TrainingAttendance.objects.get_or_create(
                        session=session,
                        application__uid=application_uid,
                        defaults={
                            'status': status,
                            'remarks': record.get('remarks', ''),
                            'created_by': request.user,
                        }
                    )
                    if not created:
                        attendance.status = status
                        attendance.remarks = record.get('remarks', '')
                        attendance.updated_by = request.user
                        attendance.save()
                    else:
                        created_count += 1

                return CustomResponse.success(
                    message=f"Attendance records processed ({created_count} created/updated)"
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Bulk Mark Attendance: {str(e)}'
            )
