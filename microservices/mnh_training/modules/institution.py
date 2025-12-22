# institution.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_training.models import Institution
from microservices.mnh_training.serializers import InstitutionSerializer, InstitutionListSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class InstitutionView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = InstitutionSerializer
    list_serializer_class = InstitutionListSerializer

    required_permissions = {
        "get": ["view_institution"],
        "post": ["add_institution", "change_institution"],
        "put": ["change_institution"],
        "patch": ["change_institution"],
        "delete": ["delete_institution"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                institution = Institution.objects.filter(uid=uid, is_deleted=False).first()
                if not institution:
                    raise NotFound("Institution not found")
                return CustomResponse.success(data=self.serializer_class(institution).data)

            search_query = request.GET.get('search', '').strip()
            institution_type = request.GET.get('institution_type', '').strip()

            institutions = Institution.objects.filter(is_deleted=False)

            if institution_type:
                institutions = institutions.filter(institution_type=institution_type)

            if search_query:
                institutions = institutions.filter(
                    Q(name__icontains=search_query) |
                    Q(institution_code__icontains=search_query) |
                    Q(contact_person__icontains=search_query) |
                    Q(contact_email__icontains=search_query)
                )

            if institutions.exists():
                # Use list serializer for list view
                serializer = self.list_serializer_class(
                    institutions,
                    many=True,
                    context={'request': request}
                )
                return CustomResponse.success(
                    data=serializer.data,
                    message="Success"
                )

            return CustomResponse.errors(message="Institutions not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Institutions: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = Institution.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Institution not found")

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
                message=f'Failed to Create/Update Institution: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = Institution.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Institution not found")

                serializer = self.serializer_class(
                    instance,
                    data=request.data,
                    partial=False,
                    context={'request': request}
                )

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Update Institution: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = Institution.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Institution not found")

                serializer = self.serializer_class(
                    instance,
                    data=request.data,
                    partial=True,
                    context={'request': request}
                )

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Partially Update Institution: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                institution = Institution.objects.filter(uid=uid, is_deleted=False).first()
                if not institution:
                    return CustomResponse.errors(message="Institution Not Found or Already Deleted")

                institution.is_deleted = True
                institution.deleted_at = datetime.now()
                institution.deleted_by = request.user
                institution.save()

                return CustomResponse.success(message='Institution deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting Institution"
            )
