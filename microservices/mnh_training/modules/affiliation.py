# affiliation.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_training.models import Affiliation
from microservices.mnh_training.serializers import AffiliationSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class AffiliationView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = AffiliationSerializer

    required_permissions = {
        "get": ["view_affiliation"],
        "post": ["add_affiliation", "change_affiliation"],
        "delete": ["delete_affiliation"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                affiliation = Affiliation.objects.filter(uid=uid, is_deleted=False).first()
                if not affiliation:
                    raise NotFound("Affiliation not found")
                return CustomResponse.success(data=self.serializer_class(affiliation).data)

            search_query = request.GET.get('search', '').strip()
            affiliation_type = request.GET.get('type', '').strip()

            affiliations = Affiliation.objects.filter(is_deleted=False)

            if affiliation_type:
                affiliations = affiliations.filter(type=affiliation_type)

            if search_query:
                affiliations = affiliations.filter(
                    Q(name__icontains=search_query) |
                    Q(course__icontains=search_query) |
                    Q(country__name__icontains=search_query)
                )

            if affiliations.exists():
                return CustomPagination.paginate(
                    view_class=self,
                    results=affiliations,
                    request=request
                )

            return CustomResponse.errors(message="Affiliations not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Affiliations: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = Affiliation.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Affiliation not found")

                    serializer = self.serializer_class(
                        instance,
                        data=request.data,
                        partial=True,
                        context={'request': request}
                    )
                else:
                    serializer = self.serializer_class(
                        data=request.data,
                        context={'request': request}
                    )

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Create/Update Affiliation: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                affiliation = Affiliation.objects.filter(uid=uid, is_deleted=False).first()
                if not affiliation:
                    return CustomResponse.errors(message="Affiliation Not Found or Already Deleted")

                affiliation.is_deleted = True
                affiliation.deleted_at = datetime.now()
                affiliation.deleted_by = request.user
                affiliation.save()

                return CustomResponse.success(message='Affiliation deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting Affiliation"
            )
