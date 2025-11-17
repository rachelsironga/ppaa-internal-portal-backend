# custodian.py
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission
from django.contrib.auth import get_user_model

from microservices.ict_assets.serializers import CustodianSerializer

User = get_user_model()


class CustodianListView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = CustodianSerializer
    required_permissions = {
        "get": [
            "view_custodian"
        ],
        "post": [
            "add_custodian",
            "change_custodian",
        ],
        "delete": [
            "delete_custodian",
        ]
    }

    def get(self, request, guid=None):
        try:
            if guid:
                custodian = User.objects.filter(guid=guid, is_deleted=False).first()
                if not custodian:
                    raise NotFound("Custodian not found")
                return CustomResponse.success(data=CustodianSerializer(custodian).data)

            search_query = request.GET.get('search', '').strip()

            custodians = User.objects.filter(is_deleted=False)

             # 🔍 Multi-field search_query
            if search_query:
                custodians = custodians.filter(
                    Q(username__icontains=search_query) |
                    Q(email__icontains=search_query) |
                    Q(pf_number__icontains=search_query) |
                    Q(first_name__icontains=search_query) |
                    Q(middle_name__icontains=search_query) |
                    Q(last_name__icontains=search_query) |
                    Q(phone_number__icontains=search_query)
                ).order_by('first_name')

            if custodians.exists():
                return CustomPagination.paginate(view_class=self, results=custodians, request=request)

            return CustomResponse.errors(message="Custodian not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Custodian: {str(e)}')
        

