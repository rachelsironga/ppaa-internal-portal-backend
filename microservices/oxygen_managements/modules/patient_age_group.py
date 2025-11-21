from datetime import datetime

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from microservices.oxygen_managements.models import PatientAgeGroup
from microservices.oxygen_managements.serializers import PatientAgeGroupSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES


class PatientAgeGroupView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PatientAgeGroupSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                patient_age_group = PatientAgeGroup.objects.filter(uid=uid, is_deleted=False).first()
                if not patient_age_group:
                    raise NotFound("Patient Age Group not found")
                return CustomResponse.success(data=PatientAgeGroupSerializer(patient_age_group).data)

            search_query = request.GET.get('search', '').strip()
            patient_age_groups = PatientAgeGroup.objects.filter(is_deleted=False)

            if search_query:
                patient_age_groups = patient_age_groups.filter(
                    Q(name__icontains=search_query) | Q(code__icontains=search_query)
                )

            if patient_age_groups.exists():
                return CustomPagination.paginate(view_class=self, results=patient_age_groups, request=request)

            return CustomResponse.errors(message="Patient Age Group not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Patient Age Groups: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = PatientAgeGroup.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except PatientAgeGroup.DoesNotExist:
                        return CustomResponse.errors(message="Patient Age Group not found")

                # Handle Create case (when no uid)
                else:
                    serializer = self.serializer_class(data=request.data)

                # Validate and save
                if serializer.is_valid():
                    serializer.save(created_by=request.user, updated_by=request.user)
                    return CustomResponse.success(data=serializer.data)

                # Validation failed
                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            # Catch unexpected errors that occur in the entire process
            return CustomResponse.server_error(message=f'Failed to Change Patient Age Group: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Patient Age Group by UID """
                patient_age_group = PatientAgeGroup.objects.filter(uid=uid, is_deleted=False).first()
                if not patient_age_group:
                    return CustomResponse.errors(message="Patient Age Group Not Found or Deleted",)

                patient_age_group.is_deleted = True
                patient_age_group.deleted_at = datetime.now()
                patient_age_group.deleted_by = request.user.id
                patient_age_group.save()
                return CustomResponse.success(message='Patient Age Group deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Patient Age Group")
