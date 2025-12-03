from datetime import datetime
from django.db import transaction
from django.db.models import Q, Sum
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_analytical.models import PatientAttendance, Attendance, Clinic, PaymentMode
from microservices.mnh_analytical.serializers import (
    PatientAttendanceSerializer, PatientAttendanceListSerializer, PatientAttendanceDetailSerializer
)
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class PatientAttendanceView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = PatientAttendanceSerializer
    required_permissions = {
        "get": ["view_patientattendance"],
        "post": ["add_patientattendance", "change_patientattendance"],
        "put": ["change_patientattendance"],
        "patch": ["change_patientattendance"],
        "delete": ["delete_patientattendance"]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                patient_attendance = PatientAttendance.objects.filter(uid=uid, is_deleted=False).first()
                if not patient_attendance:
                    raise NotFound("Patient attendance not found")
                return CustomResponse.success(data=PatientAttendanceDetailSerializer(patient_attendance).data)

            search_query = request.GET.get('search', '').strip()
            attendance_uid = request.GET.get('attendance', '').strip()
            clinic_uid = request.GET.get('clinic', '').strip()
            payment_uid = request.GET.get('payment', '').strip()
            date_from = request.GET.get('date_from', '').strip()
            date_to = request.GET.get('date_to', '').strip()

            patient_attendances = PatientAttendance.objects.filter(is_deleted=False)

            if attendance_uid:
                patient_attendances = patient_attendances.filter(attendance__uid=attendance_uid)

            if clinic_uid:
                patient_attendances = patient_attendances.filter(clinic__uid=clinic_uid)

            if payment_uid:
                patient_attendances = patient_attendances.filter(payment__uid=payment_uid)

            if date_from:
                patient_attendances = patient_attendances.filter(attendance__date__gte=date_from)

            if date_to:
                patient_attendances = patient_attendances.filter(attendance__date__lte=date_to)

            if patient_attendances.exists():
                return CustomPagination.paginate(view_class=self, results=patient_attendances, request=request)

            return CustomResponse.errors(message="Patient attendances not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Patient Attendances: {str(e)}')

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
            return CustomResponse.server_error(message=f'Failed to Create Patient Attendance: {str(e)}')

    def put(self, request, uid):
        try:
            with transaction.atomic():
                try:
                    instance = PatientAttendance.objects.get(uid=uid, is_deleted=False)
                except PatientAttendance.DoesNotExist:
                    return CustomResponse.errors(message="Patient attendance not found")

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
            return CustomResponse.server_error(message=f'Failed to Update Patient Attendance: {str(e)}')

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                try:
                    instance = PatientAttendance.objects.get(uid=uid, is_deleted=False)
                except PatientAttendance.DoesNotExist:
                    return CustomResponse.errors(message="Patient attendance not found")

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
            return CustomResponse.server_error(message=f'Failed to Update Patient Attendance: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                patient_attendance = PatientAttendance.objects.filter(uid=uid, is_deleted=False).first()
                if not patient_attendance:
                    return CustomResponse.errors(message="Patient Attendance Not Found or Already Deleted")

                patient_attendance.is_deleted = True
                patient_attendance.deleted_at = datetime.now()
                patient_attendance.deleted_by = request.user
                patient_attendance.save()
                return CustomResponse.success(message='Patient attendance deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Patient Attendance")


class PatientAttendanceBulkCreateView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "post": ["add_patientattendance"]
    }

    def post(self, request):
        try:
            with transaction.atomic():
                attendance_uid = request.data.get('attendance')
                records = request.data.get('records', [])

                if not attendance_uid:
                    return CustomResponse.errors(message="Attendance UID is required")

                try:
                    attendance = Attendance.objects.get(uid=attendance_uid, is_deleted=False)
                except Attendance.DoesNotExist:
                    return CustomResponse.errors(message="Attendance not found")

                created_records = []
                errors = []

                for idx, record in enumerate(records):
                    try:
                        clinic = Clinic.objects.get(uid=record.get('clinic'), is_deleted=False)
                        payment = PaymentMode.objects.get(uid=record.get('payment'), is_deleted=False)

                        patient_attendance = PatientAttendance.objects.create(
                            attendance=attendance,
                            clinic=clinic,
                            payment=payment,
                            new_patients=record.get('new_patients', 0),
                            follow_up_patients=record.get('follow_up_patients', 0),
                            created_by=request.user,
                            updated_by=request.user
                        )
                        created_records.append(PatientAttendanceSerializer(patient_attendance).data)
                    except Clinic.DoesNotExist:
                        errors.append({'index': idx, 'error': 'Clinic not found'})
                    except PaymentMode.DoesNotExist:
                        errors.append({'index': idx, 'error': 'Payment mode not found'})
                    except Exception as e:
                        errors.append({'index': idx, 'error': str(e)})

                return CustomResponse.success(data={
                    'created': created_records,
                    'errors': errors,
                    'total_created': len(created_records),
                    'total_errors': len(errors)
                })

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Create Patient Attendances: {str(e)}')


class ClinicPatientVolumeView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_patientattendance"]
    }

    def get(self, request):
        try:
            date_from = request.GET.get('date_from', '').strip()
            date_to = request.GET.get('date_to', '').strip()
            clinic_uid = request.GET.get('clinic', '').strip()

            patient_attendances = PatientAttendance.objects.filter(is_deleted=False)

            if date_from:
                patient_attendances = patient_attendances.filter(attendance__date__gte=date_from)

            if date_to:
                patient_attendances = patient_attendances.filter(attendance__date__lte=date_to)

            if clinic_uid:
                patient_attendances = patient_attendances.filter(clinic__uid=clinic_uid)

            clinic_volumes = patient_attendances.values(
                'clinic__uid', 'clinic__name'
            ).annotate(
                total_patients=Sum('total_patients'),
                new_patients=Sum('new_patients'),
                follow_up_patients=Sum('follow_up_patients')
            ).order_by('-total_patients')

            data = [
                {
                    'clinic_uid': str(item['clinic__uid']),
                    'clinic_name': item['clinic__name'],
                    'total_patients': item['total_patients'] or 0,
                    'new_patients': item['new_patients'] or 0,
                    'follow_up_patients': item['follow_up_patients'] or 0
                }
                for item in clinic_volumes
            ]

            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Clinic Volumes: {str(e)}')
