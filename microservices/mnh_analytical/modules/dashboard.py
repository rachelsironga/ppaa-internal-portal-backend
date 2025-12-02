from datetime import datetime, timedelta
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncMonth, TruncWeek, TruncDay
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_analytical.models import (
    Block, Clinic, PaymentMode, Attendance, PatientAttendance
)
from mnh_approval.response_codes import CustomResponse
from utils.permissions import HasMethodPermission


class AnalyticalDashboardView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_attendance"]
    }

    def get(self, request):
        try:
            today = datetime.now().date()
            month_start = today.replace(day=1)
            year_start = today.replace(month=1, day=1)

            total_blocks = Block.objects.filter(is_deleted=False).count()
            total_clinics = Clinic.objects.filter(is_deleted=False).count()
            total_payment_modes = PaymentMode.objects.filter(is_deleted=False).count()

            monthly_stats = Attendance.objects.filter(
                is_deleted=False,
                date__gte=month_start,
                date__lte=today
            ).aggregate(
                total_new_patients=Sum('total_new_patients'),
                total_follow_up_patients=Sum('total_follow_up_patients'),
                grand_total_patients=Sum('grand_total_patients'),
                attendance_count=Count('id')
            )

            yearly_stats = Attendance.objects.filter(
                is_deleted=False,
                date__gte=year_start,
                date__lte=today
            ).aggregate(
                total_new_patients=Sum('total_new_patients'),
                total_follow_up_patients=Sum('total_follow_up_patients'),
                grand_total_patients=Sum('grand_total_patients'),
                attendance_count=Count('id')
            )

            data = {
                'overview': {
                    'total_blocks': total_blocks,
                    'total_clinics': total_clinics,
                    'total_payment_modes': total_payment_modes
                },
                'monthly_summary': {
                    'period': f'{month_start.strftime("%B %Y")}',
                    'total_new_patients': monthly_stats['total_new_patients'] or 0,
                    'total_follow_up_patients': monthly_stats['total_follow_up_patients'] or 0,
                    'grand_total_patients': monthly_stats['grand_total_patients'] or 0,
                    'attendance_count': monthly_stats['attendance_count'] or 0
                },
                'yearly_summary': {
                    'year': today.year,
                    'total_new_patients': yearly_stats['total_new_patients'] or 0,
                    'total_follow_up_patients': yearly_stats['total_follow_up_patients'] or 0,
                    'grand_total_patients': yearly_stats['grand_total_patients'] or 0,
                    'attendance_count': yearly_stats['attendance_count'] or 0
                }
            }

            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Dashboard: {str(e)}')


class PatientTrendView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_attendance"]
    }

    def get(self, request):
        try:
            period = request.GET.get('period', 'monthly').strip()
            date_from = request.GET.get('date_from', '').strip()
            date_to = request.GET.get('date_to', '').strip()

            attendances = Attendance.objects.filter(is_deleted=False)

            if date_from:
                attendances = attendances.filter(date__gte=date_from)
            else:
                today = datetime.now().date()
                attendances = attendances.filter(date__gte=today.replace(month=1, day=1))

            if date_to:
                attendances = attendances.filter(date__lte=date_to)

            if period == 'daily':
                trend_data = attendances.annotate(
                    period=TruncDay('date')
                ).values('period').annotate(
                    total_new_patients=Sum('total_new_patients'),
                    total_follow_up_patients=Sum('total_follow_up_patients'),
                    grand_total_patients=Sum('grand_total_patients')
                ).order_by('period')
            elif period == 'weekly':
                trend_data = attendances.annotate(
                    period=TruncWeek('date')
                ).values('period').annotate(
                    total_new_patients=Sum('total_new_patients'),
                    total_follow_up_patients=Sum('total_follow_up_patients'),
                    grand_total_patients=Sum('grand_total_patients')
                ).order_by('period')
            else:
                trend_data = attendances.annotate(
                    period=TruncMonth('date')
                ).values('period').annotate(
                    total_new_patients=Sum('total_new_patients'),
                    total_follow_up_patients=Sum('total_follow_up_patients'),
                    grand_total_patients=Sum('grand_total_patients')
                ).order_by('period')

            data = [
                {
                    'period': item['period'].strftime('%Y-%m-%d') if item['period'] else None,
                    'total_new_patients': item['total_new_patients'] or 0,
                    'total_follow_up_patients': item['total_follow_up_patients'] or 0,
                    'grand_total_patients': item['grand_total_patients'] or 0
                }
                for item in trend_data
            ]

            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Trends: {str(e)}')


class PaymentModeDistributionView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_patientattendance"]
    }

    def get(self, request):
        try:
            date_from = request.GET.get('date_from', '').strip()
            date_to = request.GET.get('date_to', '').strip()

            patient_attendances = PatientAttendance.objects.filter(is_deleted=False)

            if date_from:
                patient_attendances = patient_attendances.filter(attendance__date__gte=date_from)

            if date_to:
                patient_attendances = patient_attendances.filter(attendance__date__lte=date_to)

            distribution = patient_attendances.values(
                'payment__uid', 'payment__name', 'payment__code'
            ).annotate(
                total_patients=Sum('total_patients'),
                new_patients=Sum('new_patients'),
                follow_up_patients=Sum('follow_up_patients'),
                record_count=Count('id')
            ).order_by('-total_patients')

            total = sum(item['total_patients'] or 0 for item in distribution)

            data = [
                {
                    'payment_uid': str(item['payment__uid']),
                    'payment_name': item['payment__name'],
                    'payment_code': item['payment__code'],
                    'total_patients': item['total_patients'] or 0,
                    'new_patients': item['new_patients'] or 0,
                    'follow_up_patients': item['follow_up_patients'] or 0,
                    'percentage': round((item['total_patients'] or 0) / total * 100, 2) if total > 0 else 0
                }
                for item in distribution
            ]

            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Distribution: {str(e)}')


class BlockClinicDistributionView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_clinic"]
    }

    def get(self, request):
        try:
            blocks = Block.objects.filter(is_deleted=False)

            data = []
            for block in blocks:
                clinics = Clinic.objects.filter(block=block, is_deleted=False)
                clinic_list = [
                    {
                        'uid': str(clinic.uid),
                        'name': clinic.name,
                        'code': clinic.code
                    }
                    for clinic in clinics
                ]
                data.append({
                    'block_uid': str(block.uid),
                    'block_name': block.name,
                    'block_code': block.code,
                    'location': block.location,
                    'clinic_count': clinics.count(),
                    'clinics': clinic_list
                })

            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Distribution: {str(e)}')


class ClinicGrowthTrendsView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_patientattendance"]
    }

    def get(self, request):
        try:
            current_month = request.GET.get('current_month', '').strip()
            previous_month = request.GET.get('previous_month', '').strip()

            if not current_month:
                today = datetime.now().date()
                current_month = today.strftime('%Y-%m')
            if not previous_month:
                today = datetime.now().date()
                prev_date = today.replace(day=1) - timedelta(days=1)
                previous_month = prev_date.strftime('%Y-%m')

            current_year, current_m = map(int, current_month.split('-'))
            previous_year, previous_m = map(int, previous_month.split('-'))

            clinics = Clinic.objects.filter(is_deleted=False)

            data = []
            for clinic in clinics:
                current_patients = PatientAttendance.objects.filter(
                    clinic=clinic,
                    is_deleted=False,
                    attendance__date__year=current_year,
                    attendance__date__month=current_m
                ).aggregate(total=Sum('total_patients'))['total'] or 0

                previous_patients = PatientAttendance.objects.filter(
                    clinic=clinic,
                    is_deleted=False,
                    attendance__date__year=previous_year,
                    attendance__date__month=previous_m
                ).aggregate(total=Sum('total_patients'))['total'] or 0

                if current_patients > 0 or previous_patients > 0:
                    data.append({
                        'clinic_uid': str(clinic.uid),
                        'clinic_name': clinic.name,
                        'clinic_code': clinic.code,
                        'current_month_patients': current_patients,
                        'previous_month_patients': previous_patients
                    })

            data.sort(key=lambda x: abs(x['current_month_patients'] - x['previous_month_patients']), reverse=True)

            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Growth Trends: {str(e)}')


class DepartmentClinicComparisonView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_patientattendance"]
    }

    def get(self, request):
        try:
            date_from = request.GET.get('date_from', '').strip()
            date_to = request.GET.get('date_to', '').strip()

            from mnh_auth.models import Department
            departments = Department.objects.filter(is_deleted=False)

            data = []
            for dept in departments:
                clinics = Clinic.objects.filter(department=dept, is_deleted=False)
                clinic_count = clinics.count()

                if clinic_count == 0:
                    continue

                patient_qs = PatientAttendance.objects.filter(
                    clinic__in=clinics,
                    is_deleted=False
                )

                if date_from:
                    patient_qs = patient_qs.filter(attendance__date__gte=date_from)
                if date_to:
                    patient_qs = patient_qs.filter(attendance__date__lte=date_to)

                stats = patient_qs.aggregate(
                    total_patients=Sum('total_patients'),
                    new_patients=Sum('new_patients'),
                    follow_up_patients=Sum('follow_up_patients')
                )

                data.append({
                    'department_uid': str(dept.uid),
                    'department_name': dept.name,
                    'total_clinics': clinic_count,
                    'total_patients': stats['total_patients'] or 0,
                    'new_patients': stats['new_patients'] or 0,
                    'follow_up_patients': stats['follow_up_patients'] or 0
                })

            data.sort(key=lambda x: x['total_patients'], reverse=True)

            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Department Comparison: {str(e)}')
