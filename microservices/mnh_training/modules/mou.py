# mou.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_training.models import MOU
from microservices.mnh_training.serializers import MOUSerializer, MOUListSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class MOUView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = MOUSerializer
    list_serializer_class = MOUListSerializer

    required_permissions = {
        "get": ["view_mou"],
        "post": ["add_mou", "change_mou"],
        "put": ["change_mou"],
        "patch": ["change_mou"],
        "delete": ["delete_mou"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                mou = MOU.objects.filter(uid=uid, is_deleted=False).first()
                if not mou:
                    raise NotFound("MOU not found")
                return CustomResponse.success(data=self.serializer_class(mou).data)

            search_query = request.GET.get('search', '').strip()
            status_filter = request.GET.get('status', '').strip()

            mous = MOU.objects.filter(is_deleted=False)

            if search_query:
                mous = mous.filter(
                    Q(mou_number__icontains=search_query) |
                    Q(institution__name__icontains=search_query) |
                    Q(purpose__icontains=search_query)
                )

            # Filter by expiration status
            if status_filter:
                if status_filter == 'active':
                    mous = [m for m in mous if m.expiration_status() == 'active']
                elif status_filter == 'expiring_soon':
                    mous = [m for m in mous if m.expiration_status() == 'expiring_soon']
                elif status_filter == 'expired':
                    mous = [m for m in mous if m.expiration_status() == 'expired']

            if isinstance(mous, list):
                # If filtered as list, convert to queryset-like result
                mou_ids = [m.id for m in mous]
                mous = MOU.objects.filter(id__in=mou_ids, is_deleted=False)

            if mous.exists() if hasattr(mous, 'exists') else mous:
               serializer = self.list_serializer_class(
                   mous,
                   many=True,
                   context={'request': request}
               )
               return CustomResponse.success(
                   data=serializer.data,
                   message="Success"
               )

            return CustomResponse.errors(message="MOUs not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve MOUs: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = MOU.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="MOU not found")

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
                message=f'Failed to Create/Update MOU: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = MOU.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="MOU not found")

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
                message=f'Failed to Update MOU: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = MOU.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="MOU not found")

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
                message=f'Failed to Partially Update MOU: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                mou = MOU.objects.filter(uid=uid, is_deleted=False).first()
                if not mou:
                    return CustomResponse.errors(message="MOU Not Found or Already Deleted")

                mou.is_deleted = True
                mou.deleted_at = datetime.now()
                mou.deleted_by = request.user
                mou.save()

                return CustomResponse.success(message='MOU deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting MOU"
            )
