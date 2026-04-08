from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_portal.pagination import CustomPagination
from utils.permissions import HasMethodPermission

from ..models import ReportAuditTrail, Report


class SystemAuditTrailSerializer(serializers.ModelSerializer):
    """Serializer for system-wide audit trail with report details"""
    performed_by_name = serializers.SerializerMethodField()
    performed_by_email = serializers.SerializerMethodField()
    report_title = serializers.CharField(source='report.title', read_only=True)
    report_reference = serializers.CharField(source='report.reference_number', read_only=True)
    report_uid = serializers.UUIDField(source='report.uid', read_only=True)
    entity_type = serializers.CharField(read_only=True)
    entity_uid = serializers.UUIDField(read_only=True)
    entity_name = serializers.CharField(read_only=True)
    directory_name = serializers.CharField(source='report.department.name', read_only=True, default=None)
    directory_code = serializers.CharField(source='report.department.code', read_only=True, default=None)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = ReportAuditTrail
        fields = [
            'uid', 'action', 'action_display', 'old_value', 'new_value',
            'comments', 'ip_address', 'user_agent', 'created_at',
            'performed_by_name', 'performed_by_email',
            'report_uid', 'report_title', 'report_reference',
            'entity_type', 'entity_uid', 'entity_name',
            'directory_name', 'directory_code',
        ]

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.email
        return 'System'

    def get_performed_by_email(self, obj):
        if obj.performed_by:
            return obj.performed_by.email
        return None


class SystemAuditTrailView(APIView):
    """API view for system-wide audit trail - all report actions"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_system_audit"],
    }
    serializer_class = SystemAuditTrailSerializer

    def get(self, request):
        """Get all audit trail entries with filtering options"""
        try:
            queryset = ReportAuditTrail.objects.filter(
                is_deleted=False
            ).select_related(
                'report', 'report__department', 'performed_by'
            ).order_by('-created_at')

            # Filter by action type
            action = request.query_params.get('action')
            if action:
                queryset = queryset.filter(action=action)

            # Filter by user
            user_uid = request.query_params.get('user_uid')
            if user_uid:
                queryset = queryset.filter(performed_by__guid=user_uid)

            # Filter by report
            report_uid = request.query_params.get('report_uid')
            if report_uid:
                queryset = queryset.filter(report__uid=report_uid)

            department_uid = (
                request.query_params.get('department_uid')
                or request.query_params.get('directory_uid')
            )
            if department_uid:
                queryset = queryset.filter(report__department__uid=department_uid)

            # Filter by date range
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)

            # Quick date filters
            date_filter = request.query_params.get('date_filter')
            today = timezone.now().date()
            if date_filter == 'today':
                queryset = queryset.filter(created_at__date=today)
            elif date_filter == 'yesterday':
                queryset = queryset.filter(created_at__date=today - timedelta(days=1))
            elif date_filter == 'week':
                queryset = queryset.filter(created_at__date__gte=today - timedelta(days=7))
            elif date_filter == 'month':
                queryset = queryset.filter(created_at__date__gte=today - timedelta(days=30))

            # Search
            search = request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(report__title__icontains=search) |
                    Q(report__reference_number__icontains=search) |
                    Q(new_value__icontains=search) |
                    Q(old_value__icontains=search) |
                    Q(comments__icontains=search) |
                    Q(performed_by__first_name__icontains=search) |
                    Q(performed_by__last_name__icontains=search) |
                    Q(performed_by__email__icontains=search)
                )

            # Always paginate for audit trails
            return CustomPagination.paginate(
                view_class=self,
                results=queryset,
                request=request
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve audit trail: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class AuditTrailStatsView(APIView):
    """API view for audit trail statistics"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_system_audit"],
    }

    def get(self, request):
        """Get audit trail statistics"""
        try:
            today = timezone.now().date()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)

            base_queryset = ReportAuditTrail.objects.filter(is_deleted=False)

            # Stats by action type
            action_stats = {}
            for action, label in ReportAuditTrail.ACTION_CHOICES:
                action_stats[action] = {
                    'label': label,
                    'today': base_queryset.filter(action=action, created_at__date=today).count(),
                    'week': base_queryset.filter(action=action, created_at__date__gte=week_ago).count(),
                    'month': base_queryset.filter(action=action, created_at__date__gte=month_ago).count(),
                    'total': base_queryset.filter(action=action).count(),
                }

            # Overall stats
            overall_stats = {
                'today': base_queryset.filter(created_at__date=today).count(),
                'yesterday': base_queryset.filter(created_at__date=today - timedelta(days=1)).count(),
                'week': base_queryset.filter(created_at__date__gte=week_ago).count(),
                'month': base_queryset.filter(created_at__date__gte=month_ago).count(),
                'total': base_queryset.count(),
            }

            # Recent activities (last 10)
            recent = base_queryset.select_related(
                'report', 'performed_by'
            ).order_by('-created_at')[:10]
            recent_data = SystemAuditTrailSerializer(recent, many=True).data

            # Most active users (this week)
            from django.db.models import Count
            active_users = base_queryset.filter(
                created_at__date__gte=week_ago,
                performed_by__isnull=False
            ).values(
                'performed_by__email',
                'performed_by__first_name',
                'performed_by__last_name'
            ).annotate(
                action_count=Count('id')
            ).order_by('-action_count')[:5]

            data = {
                'overall': overall_stats,
                'by_action': action_stats,
                'recent_activities': recent_data,
                'most_active_users': list(active_users),
            }

            return CustomResponse.success(
                data=data,
                message="Audit trail statistics retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve audit trail statistics: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )
