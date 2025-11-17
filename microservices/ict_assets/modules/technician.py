# technician.py
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse
from utils.permissions import HasMethodPermission
from django.contrib.auth import get_user_model

from microservices.ict_assets.serializers import TechnicianSerializer

User = get_user_model()


class TechnicianListView(APIView):
    """View for listing and searching technicians"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = TechnicianSerializer
    required_permissions = {
        "get": ["view_technician"]
    }

    def get(self, request, guid=None):
        try:
            if guid:
                technician = User.objects.filter(guid=guid, is_deleted=False).first()
                if not technician:
                    raise NotFound("Technician not found")
                return CustomResponse.success(data=TechnicianSerializer(technician).data)

            search_query = request.GET.get('search', '').strip()

            technicians = User.objects.filter(is_deleted=False)

            # Multi-field search
            if search_query:
                technicians = technicians.filter(
                    Q(username__icontains=search_query) |
                    Q(email__icontains=search_query) |
                    Q(pf_number__icontains=search_query) |
                    Q(first_name__icontains=search_query) |
                    Q(middle_name__icontains=search_query) |
                    Q(last_name__icontains=search_query) |
                    Q(phone_number__icontains=search_query)
                ).order_by('first_name')

            if technicians.exists():
                return CustomPagination.paginate(view_class=self, results=technicians, request=request)

            return CustomResponse.success(message="No technicians found", data=[])
            
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to retrieve technicians: {str(e)}')
