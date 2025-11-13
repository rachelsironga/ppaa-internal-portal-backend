# support_ticket.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import SupportTicket
from microservices.ict_assets.serializers import SupportTicketSerializer, SupportTicketDetailSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class SupportTicketView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = SupportTicketSerializer
    required_permissions = {
        "get": [
            "view_supportticket"
        ],
        "post": [
            "add_supportticket",
            "change_supportticket",
        ],
        "delete": [
            "delete_supportticket",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                support_ticket = SupportTicket.objects.filter(uid=uid, is_deleted=False).first()
                if not support_ticket:
                    raise NotFound("Support Ticket not found")
                return CustomResponse.success(data=SupportTicketDetailSerializer(support_ticket).data)

            search_query = request.GET.get('search', '').strip()
            asset_uid = request.GET.get('asset', '').strip()
            priority = request.GET.get('priority', '').strip()
            status = request.GET.get('status', '').strip()
            assigned_technician_uid = request.GET.get('assigned_technician', '').strip()
            
            support_tickets = SupportTicket.objects.filter(is_deleted=False)

            if asset_uid:
                support_tickets = support_tickets.filter(asset__uid=asset_uid)

            if priority:
                support_tickets = support_tickets.filter(priority=priority)

            if status:
                support_tickets = support_tickets.filter(status=status)

            if assigned_technician_uid:
                support_tickets = support_tickets.filter(assigned_technician__uid=assigned_technician_uid)

            if search_query:
                support_tickets = support_tickets.filter(
                    Q(ticket_id__icontains=search_query) | 
                    Q(asset__asset_tag__icontains=search_query) |
                    Q(issue_description__icontains=search_query) |
                    Q(resolution_notes__icontains=search_query)
                )

            if support_tickets.exists():
                return CustomPagination.paginate(view_class=self, results=support_tickets, request=request)

            return CustomResponse.errors(message="Support Tickets not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Support Tickets: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = SupportTicket.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except SupportTicket.DoesNotExist:
                        return CustomResponse.errors(message="Support Ticket not found")
                else:
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
            return CustomResponse.server_error(message=f'Failed to Change Support Ticket: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                support_ticket = SupportTicket.objects.filter(uid=uid, is_deleted=False).first()
                if not support_ticket:
                    return CustomResponse.errors(message="Support Ticket Not Found or Already Deleted")

                support_ticket.is_deleted = True
                support_ticket.deleted_at = datetime.now()
                support_ticket.deleted_by = request.user
                support_ticket.save()
                return CustomResponse.success(message='Support Ticket deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Support Ticket")
        


        