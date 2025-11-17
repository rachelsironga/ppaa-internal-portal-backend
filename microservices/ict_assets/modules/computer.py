# computer.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import Computer
from microservices.ict_assets.serializers import ComputerSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class ComputerView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = ComputerSerializer

    required_permissions = {
        "get": ["view_computer"],
        "post": ["add_computer", "change_computer"],
        "put": ["change_computer"],
        "patch": ["change_computer"],
        "delete": ["delete_computer"],
    }

    # -----------------------------
    # GET (List / Retrieve)
    # -----------------------------
    def get(self, request, uid=None):
        try:
            if uid:
                computer = Computer.objects.filter(uid=uid, is_deleted=False).first()
                if not computer:
                    raise NotFound("Computer not found")
                return CustomResponse.success(data=self.serializer_class(computer).data)

            search_query = request.GET.get('search', '').strip()
            asset_uid = request.GET.get('asset', '').strip()

            computers = Computer.objects.filter(is_deleted=False)

            if asset_uid:
                computers = computers.filter(asset__uid=asset_uid)

            if search_query:
                computers = computers.filter(
                    Q(asset__asset_tag__icontains=search_query) |
                    Q(hostname__icontains=search_query) |
                    Q(ip_addresses__icontains=search_query) |
                    Q(mac_addresses__icontains=search_query)
                )

            if computers.exists():
                return CustomPagination.paginate(
                    view_class=self, 
                    results=computers, 
                    request=request
                )

            return CustomResponse.errors(message="Computers not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Computers: {str(e)}'
            )

    # -----------------------------
    # POST (Create or Update)
    # -----------------------------
    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = Computer.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Computer not found")

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
                message=f'Failed to Change Computer: {str(e)}'
            )

    # -----------------------------
    # PUT (Strict Update)
    # -----------------------------
    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = Computer.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Computer not found")

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
                message=f'Failed to Update Computer: {str(e)}'
            )

    # -----------------------------
    # PATCH (Partial Update)
    # -----------------------------
    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = Computer.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Computer not found")

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
                message=f'Failed to Partially Update Computer: {str(e)}'
            )

    # -----------------------------
    # DELETE (Soft Delete)
    # -----------------------------
    def delete(self, request, uid):
        try:
            with transaction.atomic():
                computer = Computer.objects.filter(uid=uid, is_deleted=False).first()
                if not computer:
                    return CustomResponse.errors(message="Computer Not Found or Already Deleted")

                computer.is_deleted = True
                computer.deleted_at = datetime.now()
                computer.deleted_by = request.user
                computer.save()

                return CustomResponse.success(message='Computer deleted successfully')

        except Exception:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting Computer"
            )
