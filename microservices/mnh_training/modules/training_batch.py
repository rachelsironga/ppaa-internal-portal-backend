# training_batch.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_training.models import TrainingBatch
from microservices.mnh_training.serializers import TrainingBatchSerializer, TrainingBatchListSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class TrainingBatchView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = TrainingBatchSerializer
    list_serializer_class = TrainingBatchListSerializer

    required_permissions = {
        "get": ["view_trainingbatch"],
        "post": ["add_trainingbatch", "change_trainingbatch"],
        "put": ["change_trainingbatch"],
        "patch": ["change_trainingbatch"],
        "delete": ["delete_trainingbatch"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                batch = TrainingBatch.objects.filter(uid=uid, is_deleted=False).first()
                if not batch:
                    raise NotFound("Training Batch not found")
                return CustomResponse.success(data=self.serializer_class(batch).data)

            search_query = request.GET.get('search', '').strip()
            status_filter = request.GET.get('status', '').strip()
            from_date = request.GET.get('from_date', '').strip()
            to_date = request.GET.get('to_date', '').strip()

            batches = TrainingBatch.objects.filter(is_deleted=False)

            if status_filter:
                batches = batches.filter(status=status_filter)

            if from_date:
                batches = batches.filter(training_start_date__gte=from_date)

            if to_date:
                batches = batches.filter(training_end_date__lte=to_date)

            if search_query:
                batches = batches.filter(
                    Q(batch_number__icontains=search_query) |
                    Q(mou__mou_number__icontains=search_query) |
                    Q(mou__institution__name__icontains=search_query)
                )

            if batches.exists():
                return CustomPagination.paginate(
                    view_class=self,
                    results=batches,
                    request=request,
                    serializer=self.list_serializer_class
                )

            return CustomResponse.errors(message="Training Batches not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Training Batches: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = TrainingBatch.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Training Batch not found")

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
                message=f'Failed to Create/Update Training Batch: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = TrainingBatch.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Training Batch not found")

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
                message=f'Failed to Update Training Batch: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = TrainingBatch.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Training Batch not found")

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
                message=f'Failed to Partially Update Training Batch: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                batch = TrainingBatch.objects.filter(uid=uid, is_deleted=False).first()
                if not batch:
                    return CustomResponse.errors(message="Training Batch Not Found or Already Deleted")

                batch.is_deleted = True
                batch.deleted_at = datetime.now()
                batch.deleted_by = request.user
                batch.save()

                return CustomResponse.success(message='Training Batch deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting Training Batch"
            )
