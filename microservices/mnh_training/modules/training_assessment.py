# training_assessment.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_training.models import TrainingAssessment
from microservices.mnh_training.serializers import TrainingAssessmentSerializer, TrainingAssessmentListSerializer
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class TrainingAssessmentView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = TrainingAssessmentSerializer
    list_serializer_class = TrainingAssessmentListSerializer

    required_permissions = {
        "get": ["view_trainingassessment"],
        "post": ["add_trainingassessment", "change_trainingassessment"],
        "put": ["change_trainingassessment"],
        "patch": ["change_trainingassessment"],
        "delete": ["delete_trainingassessment"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                assessment = TrainingAssessment.objects.filter(uid=uid, is_deleted=False).first()
                if not assessment:
                    raise NotFound("Training assessment not found")
                return CustomResponse.success(data=self.serializer_class(assessment).data)

            batch_uid = request.GET.get('batch_uid', '').strip()
            application_uid = request.GET.get('application_uid', '').strip()
            assessment_type = request.GET.get('assessment_type', '').strip()

            assessments = TrainingAssessment.objects.filter(is_deleted=False)

            if batch_uid:
                assessments = assessments.filter(batch__uid=batch_uid)

            if application_uid:
                assessments = assessments.filter(application__uid=application_uid)

            if assessment_type:
                assessments = assessments.filter(assessment_type=assessment_type)

            if assessments.exists():
                serializer = self.list_serializer_class(
                    assessments.order_by('-assessment_date'),
                    many=True,
                    context={'request': request}
                )
                return CustomResponse.success(data=serializer.data)

            return CustomResponse.errors(message="Assessments not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Assessments: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = TrainingAssessment.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Assessment not found")

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
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Create/Update Assessment: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = TrainingAssessment.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Assessment not found")

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
                message=f'Failed to Update Assessment: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = TrainingAssessment.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Assessment not found")

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
                message=f'Failed to Partially Update Assessment: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                assessment = TrainingAssessment.objects.filter(uid=uid, is_deleted=False).first()
                if not assessment:
                    return CustomResponse.errors(message="Assessment not found or already deleted")

                assessment.is_deleted = True
                assessment.deleted_at = datetime.now()
                assessment.deleted_by = request.user
                assessment.save()

                return CustomResponse.success(message='Assessment deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(
                message="Something went wrong while deleting assessment"
            )
