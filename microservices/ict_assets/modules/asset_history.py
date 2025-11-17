# asset_history.py
from requests import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import Asset, AssetAssignment, AssetCustodianHistory, AssetLocationHistory, MaintenanceRecord, SoftwareInstallation, SupportTicket
from microservices.ict_assets.serializers import AssetCustodianHistorySerializer, AssetLocationHistorySerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse
from utils.permissions import HasMethodPermission


class AssetCustodianHistoryView(APIView):
    """View to retrieve custodian history for assets"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = AssetCustodianHistorySerializer
    required_permissions = {
        "get": ["view_assetcustodianhistory"]
    }

    def get(self, request, asset_uid=None):
        """
        Get custodian history.
        If asset_uid is provided, get history for that specific asset.
        Otherwise, get all history records.
        """
        try:
            if asset_uid:
                # Verify asset exists
                asset = Asset.objects.filter(uid=asset_uid, is_deleted=False).first()
                if not asset:
                    return CustomResponse.errors(message="Asset not found")
                
                history = AssetCustodianHistory.objects.filter(
                    asset=asset, 
                    is_deleted=False
                ).select_related('asset', 'custodian', 'created_by')
            else:
                history = AssetCustodianHistory.objects.filter(
                    is_deleted=False
                ).select_related('asset', 'custodian', 'created_by')
            
            if history.exists():
                return CustomPagination.paginate(
                    view_class=self, 
                    results=history, 
                    request=request
                )
            
            return CustomResponse.success(
                message="No custodian history found",
                data=[]
            )
            
        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to retrieve custodian history: {str(e)}'
            )


class AssetLocationHistoryView(APIView):
    """View to retrieve location history for assets"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = AssetLocationHistorySerializer
    required_permissions = {
        "get": ["view_assetlocationhistory"]
    }

    def get(self, request, asset_uid=None):
        """
        Get location history.
        If asset_uid is provided, get history for that specific asset.
        Otherwise, get all history records.
        """
        try:
            if asset_uid:
                # Verify asset exists
                asset = Asset.objects.filter(uid=asset_uid, is_deleted=False).first()
                if not asset:
                    return CustomResponse.errors(message="Asset not found")
                
                history = AssetLocationHistory.objects.filter(
                    asset=asset,
                    is_deleted=False
                ).select_related('asset', 'location', 'created_by')
            else:
                history = AssetLocationHistory.objects.filter(
                    is_deleted=False
                ).select_related('asset', 'location', 'created_by')
            
            if history.exists():
                return CustomPagination.paginate(
                    view_class=self,
                    results=history,
                    request=request
                )
            
            return CustomResponse.success(
                message="No location history found",
                data=[]
            )
            
        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to retrieve location history: {str(e)}'
            )


class AssetActivitiesAPIView(APIView):
    """Endpoint for recent system activities or specific asset activities"""
    
    def get(self, request, uid=None):
        try:
            limit = int(request.GET.get('limit', 10))
            
            activities = []
            
            if uid:
                # Get activities for a specific asset
                # Verify asset exists
                asset = Asset.objects.filter(uid=uid, is_deleted=False).first()
                if not asset:
                    return Response({
                        'error': 'Asset not found'
                    }, status=404)
                
                # Recent maintenance for specific asset
                recent_maintenance = MaintenanceRecord.objects.select_related(
                    'asset', 'updated_by'
                ).filter(asset__uid=uid).order_by('-updated_at')[:limit]
                
                for maintenance in recent_maintenance:
                    activities.append({
                        'activity_type': 'Maintenance',
                        'description': f"{maintenance.get_maintenance_type_display()} - {maintenance.description[:50]}...",
                        'asset_tag': maintenance.asset.asset_tag,
                        'asset_uid': maintenance.asset.uid,
                        'timestamp': maintenance.updated_at,
                        'user': maintenance.updated_by.get_full_name() if maintenance.updated_by else 'System',
                        'status': maintenance.status,
                        'id': maintenance.id
                    })
                
                # Recent assignments for specific asset
                recent_assignments = AssetAssignment.objects.select_related(
                    'asset', 'assigned_to', 'updated_by'
                ).filter(asset__uid=uid).order_by('-updated_at')[:limit]
                
                for assignment in recent_assignments:
                    activities.append({
                        'activity_type': 'Assignment',
                        'description': f"Assigned to {assignment.assigned_to.get_full_name()}",
                        'asset_tag': assignment.asset.asset_tag,
                        'asset_uid': assignment.asset.uid,
                        'timestamp': assignment.updated_at,
                        'user': assignment.updated_by.get_full_name() if assignment.updated_by else 'System',
                        'status': 'active' if not assignment.return_date else 'returned',
                        'id': assignment.id
                    })
                
                # Recent support tickets for specific asset
                recent_tickets = SupportTicket.objects.select_related(
                    'asset', 'assigned_technician'
                ).filter(asset__uid=uid).order_by('-created_date')[:limit]
                
                for ticket in recent_tickets:
                    activities.append({
                        'activity_type': 'Support',
                        'description': f"Ticket #{ticket.ticket_id} - {ticket.issue_description[:50]}...",
                        'asset_tag': ticket.asset.asset_tag,
                        'asset_uid': ticket.asset.uid,
                        'timestamp': ticket.created_date,
                        'user': ticket.assigned_technician.get_full_name() if ticket.assigned_technician else 'Unassigned',
                        'status': ticket.status,
                        'id': ticket.id
                    })
                
                # Recent software installations for specific asset
                recent_installations = SoftwareInstallation.objects.select_related(
                    'software', 'asset', 'installed_by'
                ).filter(asset__uid=uid).order_by('-created_at')[:limit]
                
                for installation in recent_installations:
                    activities.append({
                        'activity_type': 'Software',
                        'description': f"{installation.software.name} installed",
                        'asset_tag': installation.asset.asset_tag,
                        'asset_uid': installation.asset.uid,
                        'timestamp': installation.created_at,
                        'user': installation.installed_by.get_full_name() if installation.installed_by else 'System',
                        'status': 'installed',
                        'id': installation.id
                    })
                
            else:
                # Get general recent activities across all assets
                # Recent maintenance across all assets
                recent_maintenance = MaintenanceRecord.objects.select_related(
                    'asset', 'updated_by'
                ).order_by('-updated_at')[:limit]
                
                for maintenance in recent_maintenance:
                    activities.append({
                        'activity_type': 'Maintenance',
                        'description': f"{maintenance.get_maintenance_type_display()} - {maintenance.description[:50]}...",
                        'asset_tag': maintenance.asset.asset_tag,
                        'asset_uid': maintenance.asset.uid,
                        'timestamp': maintenance.updated_at,
                        'user': maintenance.updated_by.get_full_name() if maintenance.updated_by else 'System',
                        'status': maintenance.status,
                        'id': maintenance.id
                    })
                
                # Recent assignments across all assets
                recent_assignments = AssetAssignment.objects.select_related(
                    'asset', 'assigned_to', 'updated_by'
                ).order_by('-updated_at')[:limit]
                
                for assignment in recent_assignments:
                    activities.append({
                        'activity_type': 'Assignment',
                        'description': f"Assigned to {assignment.assigned_to.get_full_name()}",
                        'asset_tag': assignment.asset.asset_tag,
                        'asset_uid': assignment.asset.uid,
                        'timestamp': assignment.updated_at,
                        'user': assignment.updated_by.get_full_name() if assignment.updated_by else 'System',
                        'status': 'active' if not assignment.return_date else 'returned',
                        'id': assignment.id
                    })
                
                # Recent support tickets across all assets
                recent_tickets = SupportTicket.objects.select_related(
                    'asset', 'assigned_technician'
                ).order_by('-created_date')[:limit]
                
                for ticket in recent_tickets:
                    activities.append({
                        'activity_type': 'Support',
                        'description': f"Ticket #{ticket.ticket_id} - {ticket.issue_description[:50]}...",
                        'asset_tag': ticket.asset.asset_tag,
                        'asset_uid': ticket.asset.uid,
                        'timestamp': ticket.created_date,
                        'user': ticket.assigned_technician.get_full_name() if ticket.assigned_technician else 'Unassigned',
                        'status': ticket.status,
                        'id': ticket.id
                    })
                
                # Recent software installations across all assets
                recent_installations = SoftwareInstallation.objects.select_related(
                    'software', 'asset', 'installed_by'
                ).order_by('-created_at')[:limit]
                
                for installation in recent_installations:
                    activities.append({
                        'activity_type': 'Software',
                        'description': f"{installation.software.name} installed",
                        'asset_tag': installation.asset.asset_tag,
                        'asset_uid': installation.asset.uid,
                        'timestamp': installation.created_at,
                        'user': installation.installed_by.get_full_name() if installation.installed_by else 'System',
                        'status': 'installed',
                        'id': installation.id
                    })
            
            # Sort all activities by timestamp and limit
            sorted_activities = sorted(activities, key=lambda x: x['timestamp'], reverse=True)[:limit]
            
            # Return appropriate response based on whether it's for a specific asset or general
            if uid:
                return Response({
                    'asset_uid': uid,
                    'asset_tag': asset.asset_tag,
                    'activities': sorted_activities,
                    'total_activities': len(sorted_activities)
                })
            else:
                return Response({
                    'activities': sorted_activities,
                    'total_activities': len(sorted_activities)
                })
            
        except Exception as e:
            return Response({
                'error': 'Failed to load activities',
                'details': str(e)
            }, status=500)
        


