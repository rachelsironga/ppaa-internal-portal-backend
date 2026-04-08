from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, F, Q
from django.utils import timezone
from datetime import date, timedelta

from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission

from ..models import Report, FinancialYear
from ..serializers import ReportListSerializer
from .report import get_user_directory_info, is_admin_user


def get_current_financial_year():
    today = date.today()
    return (
        FinancialYear.objects.filter(
            is_deleted=False,
            start_date__lte=today,
            end_date__gte=today,
        ).first()
        or FinancialYear.objects.filter(is_current=True, is_deleted=False).first()
    )


class DashboardView(APIView):
    """API view for dashboard statistics"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_report"],
    }

    def get(self, request):
        """Get dashboard statistics"""
        try:
            today = date.today()
            
            # Base queryset
            queryset = Report.objects.filter(is_deleted=False)
            user_department_info = get_user_directory_info(request.user)
            is_admin = is_admin_user(request.user)

            if not is_admin and user_department_info and user_department_info.get("department"):
                queryset = queryset.filter(department=user_department_info["department"])

            # Apply filters
            financial_year_uid = request.query_params.get('financial_year_uid')
            selected_financial_year = None
            if financial_year_uid:
                selected_financial_year = FinancialYear.objects.filter(
                    uid=financial_year_uid,
                    is_deleted=False
                ).first()
                queryset = queryset.filter(financial_year__uid=financial_year_uid)
            else:
                current_fy = get_current_financial_year()
                if current_fy:
                    selected_financial_year = current_fy
                    queryset = queryset.filter(financial_year=current_fy)

            department_uid = request.query_params.get('department_uid') or request.query_params.get('directorate_uid')
            if department_uid:
                queryset = queryset.filter(department__uid=department_uid)

            scope = request.query_params.get('scope')
            if scope:
                queryset = queryset.filter(scope=scope)

            report_type_uid = request.query_params.get('report_type_uid')
            if report_type_uid:
                queryset = queryset.filter(report_type__uid=report_type_uid)

            # Status Summary
            status_summary = {
                'pending': queryset.filter(status='pending').count(),
                'in_progress': queryset.filter(status='in_progress').count(),
                'submitted': queryset.filter(status='submitted').count(),
            }

            # Deadline Summary (for non-submitted reports)
            active_reports = queryset.exclude(status='submitted')
            
            overdue_count = active_reports.filter(deadline_date__lt=today).count()
            due_today_count = active_reports.filter(deadline_date=today).count()
            due_soon_count = active_reports.filter(
                deadline_date__gt=today,
                deadline_date__lte=today + timedelta(days=3)
            ).count()
            on_track_count = active_reports.filter(
                deadline_date__gt=today + timedelta(days=3)
            ).count()
            completed_count = queryset.filter(status='submitted').count()

            deadline_summary = {
                'on_track': on_track_count,
                'due_soon': due_soon_count,
                'due_today': due_today_count,
                'overdue': overdue_count,
                'completed': completed_count,
            }

            # Reports by priority
            priority_summary = {
                'low': queryset.filter(priority='low').count(),
                'medium': queryset.filter(priority='medium').count(),
                'high': queryset.filter(priority='high').count(),
                'critical': queryset.filter(priority='critical').count(),
            }

            # Reports by scope
            scope_summary = {
                'internal': queryset.filter(scope='internal').count(),
                'external': queryset.filter(scope='external').count(),
            }

            # Submitted this month
            first_of_month = today.replace(day=1)
            submitted_this_month = queryset.filter(
                status='submitted',
                submission_date__gte=first_of_month
            ).count()

            # By report type
            by_report_type = list(
                queryset.filter(report_type__isnull=False)
                .values('report_type__uid', 'report_type__name', 'report_type__code')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            )

            # By category
            by_category = list(
                queryset.filter(category__isnull=False)
                .values('category__uid', 'category__name', 'category__color')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            )

            # By department (departmental performance)
            by_department = list(
                queryset.filter(department__isnull=False)
                .values('department__uid', 'department__code', 'department__name')
                .annotate(
                    total=Count('id'),
                    pending=Count('id', filter=Q(status='pending')),
                    in_progress=Count('id', filter=Q(status='in_progress')),
                    submitted=Count('id', filter=Q(status='submitted')),
                    submitted_this_month=Count(
                        'id',
                        filter=Q(
                            status='submitted',
                            submission_date__date__gte=first_of_month,
                            submission_date__date__lte=today,
                        )
                    ),
                )
                .order_by('-total')
            )

            # Recent submissions
            recent_submissions = ReportListSerializer(
                queryset.filter(status='submitted')
                .order_by('-submission_date')[:5],
                many=True,
                context={'request': request}
            ).data

            late_submitted_queryset = queryset.filter(
                status='submitted',
                submission_date__isnull=False,
                submission_date__date__gt=F('deadline_date'),
            )
            late_submissions_count = late_submitted_queryset.count()
            late_submissions = ReportListSerializer(
                late_submitted_queryset.order_by('-submission_date')[:10],
                many=True,
                context={'request': request}
            ).data

            # Upcoming deadlines
            upcoming_deadlines = ReportListSerializer(
                active_reports.filter(deadline_date__gte=today)
                .order_by('deadline_date')[:10],
                many=True,
                context={'request': request}
            ).data

            # Overdue reports
            overdue_reports = ReportListSerializer(
                active_reports.filter(deadline_date__lt=today)
                .order_by('deadline_date')[:10],
                many=True,
                context={'request': request}
            ).data

            # Monthly trend (last 6 months)
            monthly_trend = []
            for i in range(5, -1, -1):
                month_start = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
                if i > 0:
                    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                else:
                    month_end = today

                month_data = {
                    'month': month_start.strftime('%b %Y'),
                    'created': queryset.filter(
                        created_at__date__gte=month_start,
                        created_at__date__lte=month_end
                    ).count(),
                    'submitted': queryset.filter(
                        submission_date__date__gte=month_start,
                        submission_date__date__lte=month_end
                    ).count(),
                }
                monthly_trend.append(month_data)

            data = {
                'status_summary': status_summary,
                'deadline_summary': deadline_summary,
                'selected_financial_year': {
                    'uid': str(selected_financial_year.uid),
                    'name': selected_financial_year.name,
                    'start_date': selected_financial_year.start_date,
                    'end_date': selected_financial_year.end_date,
                } if selected_financial_year else None,
                'priority_summary': priority_summary,
                'scope_summary': scope_summary,
                'total_reports': queryset.count(),
                'overdue_count': overdue_count,
                'due_soon_count': due_soon_count,
                'due_today_count': due_today_count,
                'submitted_this_month': submitted_this_month,
                'late_submissions_count': late_submissions_count,
                'by_report_type': by_report_type,
                'by_category': by_category,
                'by_directory': by_department,
                'by_department': by_department,
                'recent_submissions': recent_submissions,
                'late_submissions': late_submissions,
                'upcoming_deadlines': upcoming_deadlines,
                'overdue_reports': overdue_reports,
                'monthly_trend': monthly_trend,
            }

            return CustomResponse.success(
                data=data,
                message="Dashboard statistics retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve dashboard statistics: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class DirectorateDashboardView(APIView):
    """API view for directorate-specific dashboard"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_report"],
    }

    def get(self, request, directorate_uid):
        """Get dashboard statistics for a specific directorate"""
        try:
            today = date.today()
            
            queryset = Report.objects.filter(
                is_deleted=False,
                directorate_uid=directorate_uid
            )

            # Apply financial year filter
            financial_year_uid = request.query_params.get('financial_year_uid')
            if financial_year_uid:
                queryset = queryset.filter(financial_year__uid=financial_year_uid)
            else:
                current_fy = get_current_financial_year()
                if current_fy:
                    queryset = queryset.filter(financial_year=current_fy)

            # Status Summary
            status_summary = {
                'pending': queryset.filter(status='pending').count(),
                'in_progress': queryset.filter(status='in_progress').count(),
                'submitted': queryset.filter(status='submitted').count(),
            }

            # Deadline Summary
            active_reports = queryset.exclude(status='submitted')
            
            deadline_summary = {
                'on_track': active_reports.filter(
                    deadline_date__gt=today + timedelta(days=3)
                ).count(),
                'due_soon': active_reports.filter(
                    deadline_date__gt=today,
                    deadline_date__lte=today + timedelta(days=3)
                ).count(),
                'due_today': active_reports.filter(deadline_date=today).count(),
                'overdue': active_reports.filter(deadline_date__lt=today).count(),
                'completed': queryset.filter(status='submitted').count(),
            }

            # Reports by unit
            by_unit = list(
                queryset.filter(unit_uid__isnull=False)
                .values('unit_uid')
                .annotate(
                    total=Count('id'),
                    pending=Count('id', filter=Q(status='pending')),
                    in_progress=Count('id', filter=Q(status='in_progress')),
                    submitted=Count('id', filter=Q(status='submitted')),
                    overdue=Count('id', filter=Q(
                        deadline_date__lt=today
                    ) & ~Q(status='submitted'))
                )
                .order_by('-total')
            )

            # Reports by type
            by_report_type = list(
                queryset.values('report_type__name', 'report_type__code')
                .annotate(count=Count('id'))
                .order_by('-count')
            )

            # Upcoming deadlines
            upcoming_deadlines = ReportListSerializer(
                active_reports.filter(deadline_date__gte=today)
                .order_by('deadline_date')[:10],
                many=True,
                context={'request': request}
            ).data

            # Overdue reports
            overdue_reports = ReportListSerializer(
                active_reports.filter(deadline_date__lt=today)
                .order_by('deadline_date'),
                many=True,
                context={'request': request}
            ).data

            data = {
                'directorate_uid': directorate_uid,
                'status_summary': status_summary,
                'deadline_summary': deadline_summary,
                'total_reports': queryset.count(),
                'by_unit': by_unit,
                'by_report_type': by_report_type,
                'upcoming_deadlines': upcoming_deadlines,
                'overdue_reports': overdue_reports,
            }

            return CustomResponse.success(
                data=data,
                message="Directorate dashboard statistics retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve directorate dashboard: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class DeadlineCalendarView(APIView):
    """API view for deadline calendar"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_report"],
    }

    def get(self, request):
        """Get reports organized by deadline for calendar view"""
        try:
            queryset = Report.objects.filter(
                is_deleted=False
            ).exclude(status='submitted')

            # Date range filter
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            if start_date:
                queryset = queryset.filter(deadline_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(deadline_date__lte=end_date)

            # Additional filters
            directorate_uid = request.query_params.get('directorate_uid')
            if directorate_uid:
                queryset = queryset.filter(directorate_uid=directorate_uid)

            financial_year_uid = request.query_params.get('financial_year_uid')
            if financial_year_uid:
                queryset = queryset.filter(financial_year__uid=financial_year_uid)

            # Group by deadline date
            calendar_data = {}
            for report in queryset.order_by('deadline_date'):
                date_str = report.deadline_date.isoformat()
                if date_str not in calendar_data:
                    calendar_data[date_str] = {
                        'date': date_str,
                        'reports': [],
                        'count': 0,
                        'has_overdue': False,
                    }
                
                report_data = ReportListSerializer(report, context={'request': request}).data
                calendar_data[date_str]['reports'].append(report_data)
                calendar_data[date_str]['count'] += 1
                
                if report.is_overdue:
                    calendar_data[date_str]['has_overdue'] = True

            return CustomResponse.success(
                data=list(calendar_data.values()),
                message="Calendar data retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve calendar data: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )
