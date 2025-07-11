from datetime import datetime

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from api.serializers import ApprovalRequestSerializer, REQUEST_TYPE_SERIALIZER_IMPORTS, get_serializer_class, \
    ApprovalRequestStepSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_model.models import ApprovalRequest, ApprovalModule
from utils.permissions import HasMethodPermission


class ApprovalRequestView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = ApprovalRequestSerializer
    required_permissions = {
        "get": ["view_approvalrequest"],
    }


    def get(self, request, uid=None):
        try:
            if uid:
                approval_request = ApprovalRequest.objects.filter(uid=uid, is_deleted=False).first()
                if not approval_request:
                    raise NotFound("Approval Request not found")

                serializer = ApprovalRequestSerializer(
                    approval_request,
                    context={'request': request, 'show_full_user': True,'approval_request_uid': approval_request.uid}
                )
                return CustomResponse.success(data=serializer.data)

            search_query = request.GET.get('search', '').strip()
            approval_request = ApprovalRequest.objects.filter(is_deleted=False)

            if search_query:
                approval_request = approval_request.filter(name__icontains=search_query)

            if approval_request.exists():
                return CustomPagination.paginate(view_class=self, results=approval_request, request=request)

            return CustomResponse.errors(message="Approval Request not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Approval Requests: {str(e)}', )

    def post(self, request):
        # try:
        with transaction.atomic():
            uid = request.data.get('uid')
            instance = None

            # 1. Check if it's an update operation
            if uid:
                try:
                    instance = ApprovalRequest.objects.get(uid=uid)
                except ApprovalRequest.DoesNotExist:
                    return CustomResponse.errors(message="Approval Request not found")

            serializer = self.serializer_class(instance, data=request.data, partial=True)

            # Validate and save
            if serializer.is_valid():
                serializer.save(created_by=request.user, updated_by=request.user)
                return CustomResponse.success(data=serializer.data)

            # Validation failed
            return CustomResponse.errors(
                message="Validation Failed",
                data=serializer.errors,
                code=STATUS_CODES["VALIDATION_ERROR"]
            )

        # except Exception as e:
        #     return CustomResponse.server_error(
        #         message=f"Failed to Change Approval Request: {str(e)}"
        #     )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Approval Request by UID """
                approval_request = ApprovalRequest.objects.filter(uid=uid, is_deleted=False).first()
                if not approval_request:
                    return CustomResponse.errors(message="Approval Request Not Found or Deleted",)

                approval_request.is_deleted = True
                approval_request.deleted_at = datetime.now()
                approval_request.deleted_by = request.user.id
                approval_request.save()
                return CustomResponse.success(message='Approval Request deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Approval Request")
