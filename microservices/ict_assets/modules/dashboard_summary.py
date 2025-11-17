# microservices/ict_assets/modules/dashboard_summary.py
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from datetime import timedelta
from django.db import models
from ..models import *



# class DashboardAPIView(APIView):
#     """Main dashboard endpoint with all metrics"""
    
#     def get(self, request):
#         try:
#             # Calculate all metrics in single database hits (optimized)
#             total_assets = Asset.objects.filter(is_active=True).count()
            
#             # FIXED: Add order_by to the aggregated queryset
#             status_counts = Asset.objects.filter(is_active=True).values(
#                 'status'
#             ).annotate(count=Count('id')).order_by('status')
            
#             # Convert status_counts to a dictionary for easier access
#             status_dict = {item['status']: item['count'] for item in status_counts}
            
#             # Asset type counts
#             computer_count = Computer.objects.filter(asset__is_active=True).count()
#             network_count = NetworkDevice.objects.filter(asset__is_active=True).count()
#             peripheral_count = Peripheral.objects.filter(asset__is_active=True).count()
            
#             # Cost calculations
#             cost_stats = Asset.objects.filter(
#                 is_active=True, 
#                 purchase_cost__isnull=False
#             ).aggregate(
#                 total_value=Sum('purchase_cost'),
#                 avg_cost=Avg('purchase_cost')
#             )
            
#             # Maintenance metrics
#             pending_maintenance = MaintenanceRecord.objects.filter(
#                 status__in=['scheduled', 'in_progress']
#             ).count()
            
#             open_tickets = SupportTicket.objects.filter(
#                 status__in=['open', 'in_progress']
#             ).count()
            
#             # Warranty alerts (expiring in next 30 days)
#             thirty_days_later = timezone.now().date() + timedelta(days=30)
#             expiring_warranties = Asset.objects.filter(
#                 is_active=True,
#                 warranty_expiry__range=[timezone.now().date(), thirty_days_later]
#             ).count()
            
#             summary_data = {
#                 'total_assets': total_assets,
#                 'operational_assets': status_dict.get('operational', 0),
#                 'assets_in_repair': status_dict.get('in_repair', 0),
#                 'retired_assets': status_dict.get('retired', 0),
#                 'lost_assets': status_dict.get('lost', 0),
#                 'disposed_assets': status_dict.get('disposed', 0),
#                 'total_computers': computer_count,
#                 'total_network_devices': network_count,
#                 'total_peripherals': peripheral_count,
#                 'total_asset_value': cost_stats['total_value'] or 0,
#                 'average_asset_cost': cost_stats['avg_cost'] or 0,
#                 'pending_maintenance': pending_maintenance,
#                 'open_tickets': open_tickets,
#                 'expiring_warranties': expiring_warranties,
#             }
            
#             # Status distribution for charts
#             status_distribution = []
#             for status, count in status_dict.items():
#                 status_distribution.append({
#                     'status': dict(Asset.ASSET_STATUS).get(status, status.title()),
#                     'count': count,
#                     'percentage': round((count / total_assets) * 100, 2) if total_assets > 0 else 0
#                 })
            
#             # Category distribution - FIXED: Add order_by
#             category_distribution = Asset.objects.filter(
#                 is_active=True
#             ).values(
#                 'asset_type__category__name'
#             ).annotate(
#                 count=Count('id'),
#                 total_value=Sum('purchase_cost')
#             ).order_by('-count')
            
#             category_data = []
#             for item in category_distribution:
#                 category_data.append({
#                     'category': item['asset_type__category__name'] or 'Uncategorized',
#                     'count': item['count'],
#                     'total_value': item['total_value'] or 0
#                 })
            
#             return Response({
#                 'summary': summary_data,
#                 'status_distribution': status_distribution,
#                 'category_distribution': category_data,
#                 'recent_activities': self.get_recent_activities()
#             })
            
#         except Exception as e:
#             # Log the error for debugging
#             print(f"Dashboard API Error: {str(e)}")
#             return Response({
#                 'error': 'Failed to load dashboard data',
#                 'details': str(e)
#             }, status=500)

class DashboardAPIView(APIView):
    """Main dashboard endpoint with all metrics"""
    
    def get(self, request):
        try:
            # Calculate all metrics in single database hits (optimized)
            total_assets = Asset.objects.filter(is_active=True).count()
            
            # FIXED: Add order_by to the aggregated queryset
            status_counts = Asset.objects.filter(is_active=True).values(
                'status'
            ).annotate(count=Count('id')).order_by('status')  # Added order_by
            
            # Convert status_counts to a dictionary for easier access
            status_dict = {item['status']: item['count'] for item in status_counts}
            
            # Asset type counts
            computer_count = Computer.objects.filter(asset__is_active=True).count()
            network_count = NetworkDevice.objects.filter(asset__is_active=True).count()
            peripheral_count = Peripheral.objects.filter(asset__is_active=True).count()
            
            # Cost calculations
            cost_stats = Asset.objects.filter(
                is_active=True, 
                purchase_cost__isnull=False
            ).aggregate(
                total_value=Sum('purchase_cost'),
                avg_cost=Avg('purchase_cost')
            )
            
            # Maintenance metrics
            pending_maintenance = MaintenanceRecord.objects.filter(
                status__in=['scheduled', 'in_progress']
            ).count()
            
            open_tickets = SupportTicket.objects.filter(
                status__in=['open', 'in_progress']
            ).count()
            
            # Warranty alerts (expiring in next 30 days)
            thirty_days_later = timezone.now().date() + timedelta(days=30)
            expiring_warranties = Asset.objects.filter(
                is_active=True,
                warranty_expiry__range=[timezone.now().date(), thirty_days_later]
            ).count()
            
            summary_data = {
                'total_assets': total_assets,
                'operational_assets': status_dict.get('operational', 0),
                'assets_in_repair': status_dict.get('in_repair', 0),
                'retired_assets': status_dict.get('retired', 0),
                'lost_assets': status_dict.get('lost', 0),
                'disposed_assets': status_dict.get('disposed', 0),
                'total_computers': computer_count,
                'total_network_devices': network_count,
                'total_peripherals': peripheral_count,
                'total_asset_value': cost_stats['total_value'] or 0,
                'average_asset_cost': cost_stats['avg_cost'] or 0,
                'pending_maintenance': pending_maintenance,
                'open_tickets': open_tickets,
                'expiring_warranties': expiring_warranties,
            }
            
            # Status distribution for charts
            status_distribution = []
            for status, count in status_dict.items():
                status_distribution.append({
                    'status': dict(Asset.ASSET_STATUS).get(status, status.title()),
                    'count': count,
                    'percentage': round((count / total_assets) * 100, 2) if total_assets > 0 else 0
                })
            
            # Category distribution - FIXED: Add order_by
            category_distribution = Asset.objects.filter(
                is_active=True
            ).values(
                'asset_type__category__name'
            ).annotate(
                count=Count('id'),
                total_value=Sum('purchase_cost')
            ).order_by('-count')  # Added order_by
            
            category_data = []
            for item in category_distribution:
                category_data.append({
                    'category': item['asset_type__category__name'] or 'Uncategorized',
                    'count': item['count'],
                    'total_value': item['total_value'] or 0
                })
            
            return Response({
                'summary': summary_data,
                'status_distribution': status_distribution,
                'category_distribution': category_data,
                'recent_activities': self.get_recent_activities()
            })
            
        except Exception as e:
            # Log the error for debugging
            print(f"Dashboard API Error: {str(e)}")
            return Response({
                'error': 'Failed to load dashboard data',
                'details': str(e)
            }, status=500)
    
    def get_recent_activities(self):
        """Get recent system activities"""
        activities = []
        
        # Recent maintenance - FIXED: Add order_by
        recent_maintenance = MaintenanceRecord.objects.select_related('asset').order_by('-updated_at')[:5]
        for maintenance in recent_maintenance:
            activities.append({
                'activity_type': 'Maintenance',
                'description': f"{maintenance.get_maintenance_type_display()} - {maintenance.description[:50]}...",
                'asset_tag': maintenance.asset.asset_tag,
                'timestamp': maintenance.updated_at,
                'user': maintenance.updated_by.get_full_name() if maintenance.updated_by else 'System'
            })
        
        # Recent assignments - FIXED: Add order_by
        recent_assignments = AssetAssignment.objects.select_related('asset', 'assigned_to').order_by('-updated_at')[:5]
        for assignment in recent_assignments:
            activities.append({
                'activity_type': 'Assignment',
                'description': f"Assigned to {assignment.assigned_to.get_full_name()}",
                'asset_tag': assignment.asset.asset_tag,
                'timestamp': assignment.updated_at,
                'user': assignment.updated_by.get_full_name() if assignment.updated_by else 'System'
            })
        
        # Add support tickets
        recent_tickets = SupportTicket.objects.select_related('asset').order_by('-created_date')[:5]
        for ticket in recent_tickets:
            activities.append({
                'activity_type': 'Support',
                'description': f"Ticket #{ticket.ticket_id} - {ticket.issue_description[:50]}...",
                'asset_tag': ticket.asset.asset_tag,
                'timestamp': ticket.created_date,
                'user': ticket.assigned_technician.get_full_name() if ticket.assigned_technician else 'Unassigned'
            })
        
        return sorted(activities, key=lambda x: x['timestamp'], reverse=True)[:10]
    
class StatusDistributionAPIView(APIView):
    """Endpoint for asset status distribution data"""
    
    def get(self, request):
        try:
            total_assets = Asset.objects.filter(is_active=True).count()
            
            status_counts = Asset.objects.filter(is_active=True).values(
                'status'
            ).annotate(count=Count('id')).order_by('status')
            
            status_distribution = []
            for item in status_counts:
                status_distribution.append({
                    'status': dict(Asset.ASSET_STATUS).get(item['status'], item['status'].title()),
                    'count': item['count'],
                    'percentage': round((item['count'] / total_assets) * 100, 2) if total_assets > 0 else 0
                })
            
            return Response(status_distribution)
            
        except Exception as e:
            return Response({
                'error': 'Failed to load status distribution',
                'details': str(e)
            }, status=500)

class MaintenanceMetricsAPIView(APIView):
    """Endpoint for maintenance performance metrics"""
    
    def get(self, request):
        try:
            # Current month range
            today = timezone.now().date()
            first_day_of_month = today.replace(day=1)
            next_month = today.replace(day=28) + timedelta(days=4)
            last_day_of_month = next_month - timedelta(days=next_month.day)
            
            # Maintenance metrics
            completed_this_month = MaintenanceRecord.objects.filter(
                status='completed',
                completed_date__range=[first_day_of_month, last_day_of_month]
            ).count()
            
            scheduled_next_month = MaintenanceRecord.objects.filter(
                status='scheduled',
                scheduled_date__range=[first_day_of_month, last_day_of_month]
            ).count()
            
            # Average completion time (in days)
            completed_maintenance = MaintenanceRecord.objects.filter(
                status='completed',
                completed_date__isnull=False
            ).annotate(
                completion_time=F('completed_date') - F('scheduled_date')
            ).aggregate(
                avg_completion=Avg('completion_time')
            )
            
            avg_completion_days = 0
            if completed_maintenance['avg_completion']:
                avg_completion_days = completed_maintenance['avg_completion'].days
            
            # Year-to-date maintenance cost
            first_day_of_year = today.replace(month=1, day=1)
            maintenance_cost_ytd = MaintenanceRecord.objects.filter(
                completed_date__range=[first_day_of_year, today],
                cost__isnull=False
            ).aggregate(total_cost=Sum('cost'))['total_cost'] or 0
            
            metrics_data = {
                'completed_this_month': completed_this_month,
                'scheduled_next_month': scheduled_next_month,
                'average_completion_time': avg_completion_days,
                'maintenance_cost_ytd': float(maintenance_cost_ytd),
                'maintenance_backlog': MaintenanceRecord.objects.filter(
                    status__in=['scheduled', 'in_progress']
                ).count(),
                'critical_maintenance': MaintenanceRecord.objects.filter(
                    status='scheduled',
                    scheduled_date__lt=today  # Overdue maintenance
                ).count()
            }
            
            return Response(metrics_data)
            
        except Exception as e:
            return Response({
                'error': 'Failed to load maintenance metrics',
                'details': str(e)
            }, status=500)

class RecentActivitiesAPIView(APIView):
    """Endpoint for recent system activities"""
    
    def get(self, request):
        try:
            limit = int(request.GET.get('limit', 10))
            
            activities = []
            
            # Recent maintenance
            recent_maintenance = MaintenanceRecord.objects.select_related(
                'asset', 'updated_by'
            ).order_by('-updated_at')[:limit]
            
            for maintenance in recent_maintenance:
                activities.append({
                    'activity_type': 'Maintenance',
                    'description': f"{maintenance.get_maintenance_type_display()} - {maintenance.description[:50]}...",
                    'asset_tag': maintenance.asset.asset_tag,
                    'timestamp': maintenance.updated_at,
                    'user': maintenance.updated_by.get_full_name() if maintenance.updated_by else 'System',
                    'status': maintenance.status
                })
            
            # Recent assignments
            recent_assignments = AssetAssignment.objects.select_related(
                'asset', 'assigned_to', 'updated_by'
            ).order_by('-updated_at')[:limit]
            
            for assignment in recent_assignments:
                activities.append({
                    'activity_type': 'Assignment',
                    'description': f"Assigned to {assignment.assigned_to.get_full_name()}",
                    'asset_tag': assignment.asset.asset_tag,
                    'timestamp': assignment.updated_at,
                    'user': assignment.updated_by.get_full_name() if assignment.updated_by else 'System',
                    'status': 'active' if not assignment.return_date else 'returned'
                })
            
            # Recent support tickets
            recent_tickets = SupportTicket.objects.select_related(
                'asset', 'assigned_technician'
            ).order_by('-created_date')[:limit]
            
            for ticket in recent_tickets:
                activities.append({
                    'activity_type': 'Support',
                    'description': f"Ticket #{ticket.ticket_id} - {ticket.issue_description[:50]}...",
                    'asset_tag': ticket.asset.asset_tag,
                    'timestamp': ticket.created_date,
                    'user': ticket.assigned_technician.get_full_name() if ticket.assigned_technician else 'Unassigned',
                    'status': ticket.status
                })
            
            # Recent software installations
            recent_installations = SoftwareInstallation.objects.select_related(
                'software', 'asset', 'installed_by'
            ).order_by('-created_at')[:limit]
            
            for installation in recent_installations:
                activities.append({
                    'activity_type': 'Software',
                    'description': f"{installation.software.name} installed",
                    'asset_tag': installation.asset.asset_tag,
                    'timestamp': installation.created_at,
                    'user': installation.installed_by.get_full_name() if installation.installed_by else 'System',
                    'status': 'installed'
                })
            
            # Sort all activities by timestamp and limit
            sorted_activities = sorted(activities, key=lambda x: x['timestamp'], reverse=True)[:limit]
            
            return Response(sorted_activities)
            
        except Exception as e:
            return Response({
                'error': 'Failed to load recent activities',
                'details': str(e)
            }, status=500)

class AssetTypeBreakdownAPIView(APIView):
    """Endpoint for asset type breakdown"""
    
    def get(self, request):
        try:
            # Asset type breakdown
            asset_type_breakdown = Asset.objects.filter(
                is_active=True
            ).values(
                'asset_type__name'
            ).annotate(
                count=Count('id'),
                total_value=Sum('purchase_cost'),
                operational_count=Count('id', filter=Q(status='operational')),
                in_repair_count=Count('id', filter=Q(status='in_repair'))
            ).order_by('-count')
            
            breakdown_data = []
            for item in asset_type_breakdown:
                breakdown_data.append({
                    'asset_type': item['asset_type__name'] or 'Unknown',
                    'count': item['count'],
                    'total_value': item['total_value'] or 0,
                    'operational_count': item['operational_count'],
                    'in_repair_count': item['in_repair_count'],
                    'operational_percentage': round((item['operational_count'] / item['count']) * 100, 2) if item['count'] > 0 else 0
                })
            
            # Hardware type breakdown
            hardware_data = {
                'computers': Computer.objects.filter(asset__is_active=True).count(),
                'network_devices': NetworkDevice.objects.filter(asset__is_active=True).count(),
                'peripherals': Peripheral.objects.filter(asset__is_active=True).count(),
                'total_hardware': Computer.objects.filter(asset__is_active=True).count() +
                                 NetworkDevice.objects.filter(asset__is_active=True).count() +
                                 Peripheral.objects.filter(asset__is_active=True).count()
            }
            
            return Response({
                'asset_types': breakdown_data,
                'hardware_types': hardware_data
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to load asset type breakdown',
                'details': str(e)
            }, status=500)

class WarrantyAlertsAPIView(APIView):
    """Endpoint for warranty alerts and expirations"""
    
    def get(self, request):
        try:
            today = timezone.now().date()
            
            # Warranty alerts by time frame
            warranty_alerts = {
                'expired': Asset.objects.filter(
                    is_active=True,
                    warranty_expiry__lt=today
                ).count(),
                
                'expiring_7_days': Asset.objects.filter(
                    is_active=True,
                    warranty_expiry__range=[today, today + timedelta(days=7)]
                ).count(),
                
                'expiring_30_days': Asset.objects.filter(
                    is_active=True,
                    warranty_expiry__range=[today + timedelta(days=8), today + timedelta(days=30)]
                ).count(),
                
                'expiring_90_days': Asset.objects.filter(
                    is_active=True,
                    warranty_expiry__range=[today + timedelta(days=31), today + timedelta(days=90)]
                ).count(),
                
                'no_warranty': Asset.objects.filter(
                    is_active=True,
                    warranty_expiry__isnull=True
                ).count()
            }
            
            # Detailed expiring assets
            expiring_soon = Asset.objects.filter(
                is_active=True,
                warranty_expiry__range=[today, today + timedelta(days=30)]
            ).select_related('asset_type', 'manufacturer').order_by('warranty_expiry')[:10]
            
            expiring_assets = []
            for asset in expiring_soon:
                days_until_expiry = (asset.warranty_expiry - today).days
                expiring_assets.append({
                    'asset_tag': asset.asset_tag,
                    'asset_type': asset.asset_type.name,
                    'manufacturer': asset.manufacturer.name if asset.manufacturer else 'Unknown',
                    'warranty_expiry': asset.warranty_expiry,
                    'days_until_expiry': days_until_expiry,
                    'status': 'expired' if days_until_expiry < 0 else 'expiring_soon'
                })
            
            return Response({
                'alerts_summary': warranty_alerts,
                'expiring_assets': expiring_assets,
                'total_assets_with_warranty': Asset.objects.filter(
                    is_active=True,
                    warranty_expiry__isnull=False
                ).count()
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to load warranty alerts',
                'details': str(e)
            }, status=500)

class FilteredDashboardAPIView(APIView):
    """Endpoint for filtered dashboard data"""
    
    def get(self, request):
        try:
            filters = request.GET.dict()
            
            # Build base queryset
            assets = Asset.objects.filter(is_active=True)
            
            # Apply filters
            if filters.get('asset_type'):
                assets = assets.filter(asset_type_id=filters['asset_type'])
            
            if filters.get('status'):
                assets = assets.filter(status=filters['status'])
            
            if filters.get('location'):
                assets = assets.filter(location_id=filters['location'])
            
            if filters.get('manufacturer'):
                assets = assets.filter(manufacturer_id=filters['manufacturer'])
            
            if filters.get('date_from') and filters.get('date_to'):
                date_from = filters['date_from']
                date_to = filters['date_to']
                assets = assets.filter(
                    purchase_date__range=[date_from, date_to]
                )
            
            # Calculate filtered metrics
            filtered_data = {
                'total_assets': assets.count(),
                'total_value': assets.aggregate(
                    total_value=Sum('purchase_cost')
                )['total_value'] or 0,
                'operational_assets': assets.filter(status='operational').count(),
                'assets_in_repair': assets.filter(status='in_repair').count(),
                'average_cost': assets.aggregate(
                    avg_cost=Avg('purchase_cost')
                )['avg_cost'] or 0
            }
            
            return Response(filtered_data)
            
        except Exception as e:
            return Response({
                'error': 'Failed to load filtered dashboard data',
                'details': str(e)
            }, status=500)
        




        