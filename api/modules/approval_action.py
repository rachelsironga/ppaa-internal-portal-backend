from datetime import datetime

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from api.serializers import ApprovalActionSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_model.models import ApprovalAction

class ApprovalActionView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ApprovalActionSerializer


    def get(self, request, uid=None):
        try:
            if uid:
                approval_action = ApprovalAction.objects.filter(uid=uid, is_deleted=False).first()
                if not approval_action:
                    raise NotFound("Approval Action not found")
                return CustomResponse.success(data=ApprovalActionSerializer(approval_action).data)

            search_query = request.GET.get('search', '').strip()
            approval_actions = ApprovalAction.objects.filter(is_deleted=False)

            if search_query:
                approval_actions = approval_actions.filter(
                    Q(name__icontains=search_query) | Q(code__icontains=search_query)
                )

            if approval_actions.exists():
                return CustomPagination.paginate(view_class=self, results=approval_actions, request=request)

            return CustomResponse.errors(message="Approval Action not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Approval Actions: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = ApprovalAction.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except ApprovalAction.DoesNotExist:
                        return CustomResponse.errors(message="Approval Action not found")

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
            return CustomResponse.server_error(message=f'Failed to Change Approval Action: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Approval Action by UID """
                approval_action = ApprovalAction.objects.filter(uid=uid, is_deleted=False).first()
                if not approval_action:
                    return CustomResponse.errors(message="Approval Action Not Found or Deleted",)

                approval_action.is_deleted = True
                approval_action.deleted_at = datetime.now()
                approval_action.deleted_by = request.user.id
                approval_action.save()
                return CustomResponse.success(message='Approval Action deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Approval Action")
