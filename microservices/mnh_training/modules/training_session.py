# training_session.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_training.models import TrainingSession, TrainingBatch
from microservices.mnh_training.serializers import TrainingSessionSerializer, TrainingSessionListSerializer
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class TrainingSessionView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = TrainingSessionSerializer
    list_serializer_class = TrainingSessionListSerializer

    required_permissions = {
        "get": ["view_trainingsession"],
        "post": ["add_trainingsession", "change_trainingsession"],
        "put": ["change_trainingsession"],
        "patch": ["change_trainingsession"],
        "delete": ["delete_trainingsession"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                session = TrainingSession.objects.filter(uid=uid, is_deleted=False).first()
                if not session:
                    raise NotFound("Training session not found")
                return CustomResponse.success(data=self.serializer_class(session).data)

            batch_uid = request.GET.get('batch_uid', '').strip()
            status = request.GET.get('status', '').strip()
            from_date = request.GET.get('from_date', '').strip()
            to_date = request.GET.get('to_date', '').strip()

            sessions = TrainingSession.objects.filter(is_deleted=False)

            if batch_uid:
                sessions = sessions.filter(batch__uid=batch_uid)

            if status:
                sessions = sessions.filter(status=status)

            if from_date:
                sessions = sessions.filter(session_date__gte=from_date)

            if to_date:
                sessions = sessions.filter(session_date__lte=to_date)

            if sessions.exists():
                serializer = self.list_serializer_class(
                    sessions.order_by('-session_date', 'session_number'),
                    many=True,
                    context={'request': request}
                )
                return CustomResponse.success(data=serializer.data)

            return CustomResponse.errors(message="Training sessions not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Training Sessions: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = TrainingSession.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Training session not found")

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
                message=f'Failed to Create/Update Training Session: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = TrainingSession.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Training session not found")

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
                message=f'Failed to Update Training Session: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = TrainingSession.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Training session not found")

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
                message=f'Failed to Partially Update Training Session: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                session = TrainingSession.objects.filter(uid=uid, is_deleted=False).first()
                if not session:
                    return CustomResponse.errors(message="Training session not found or already deleted")

                session.is_deleted = True
                session.deleted_at = datetime.now()
                session.deleted_by = request.user
                session.save()

                return CustomResponse.success(message='Training session deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(
                message="Something went wrong while deleting training session"
            )
