# dashboard_summary.py
from datetime import datetime
from django.db.models import Count, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ict_assets.models import Asset, MaintenanceRecord, SupportTicket
from mnh_approval.response_codes import CustomResponse
from utils.permissions import HasMethodPermission


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": [
            "view_asset", "view_maintenancerecord", "view_supportticket"
        ]
    }

    def get(self, request):
        try:
            # Asset statistics
            total_assets = Asset.objects.filter(is_deleted=False).count()
            active_assets = Asset.objects.filter(is_deleted=False, is_active=True).count()
            
            asset_status_counts = Asset.objects.filter(is_deleted=False).values(
                'status'
            ).annotate(count=Count('id'))
            
            asset_condition_counts = Asset.objects.filter(is_deleted=False).values(
                'condition'
            ).annotate(count=Count('id'))

            # Maintenance statistics
            pending_maintenance = MaintenanceRecord.objects.filter(
                is_deleted=False, 
                status='pending'
            ).count()
            
            overdue_maintenance = MaintenanceRecord.objects.filter(
                is_deleted=False,
                status='scheduled',
                scheduled_date__lt=datetime.now().date()
            ).count()

            # Support ticket statistics
            open_tickets = SupportTicket.objects.filter(
                is_deleted=False,
                status__in=['open', 'in_progress']
            ).count()
            
            high_priority_tickets = SupportTicket.objects.filter(
                is_deleted=False,
                priority='high',
                status__in=['open', 'in_progress']
            ).count()

            summary_data = {
                'assets': {
                    'total': total_assets,
                    'active': active_assets,
                    'by_status': list(asset_status_counts),
                    'by_condition': list(asset_condition_counts),
                },
                'maintenance': {
                    'pending': pending_maintenance,
                    'overdue': overdue_maintenance,
                },
                'support': {
                    'open_tickets': open_tickets,
                    'high_priority_tickets': high_priority_tickets,
                }
            }

            return CustomResponse.success(data=summary_data)

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to load dashboard summary: {str(e)}')
        
        