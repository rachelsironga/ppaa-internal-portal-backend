from datetime import datetime

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from api.serializers import ApprovalModuleSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_model.models import ApprovalModule, ApprovalModuleLevel


class ApprovalModuleView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ApprovalModuleSerializer


    def get(self, request, uid=None):
        try:
            if uid:
                approval_module = ApprovalModule.objects.filter(uid=uid, is_deleted=False).first()
                if not approval_module:
                    raise NotFound("Approval Module not found")
                return CustomResponse.success(data=ApprovalModuleSerializer(approval_module).data)

            search_query = request.GET.get('search', '').strip()
            approval_modules = ApprovalModule.objects.filter(is_deleted=False)

            if search_query:
                approval_modules = approval_modules.filter(
                    Q(name__icontains=search_query) | Q(description__icontains=search_query)
                )

            if approval_modules.exists():
                return CustomPagination.paginate(view_class=self, results=approval_modules, request=request)

            return CustomResponse.errors(message="Approval Module not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Approval Modules: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = ApprovalModule.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except ApprovalModule.DoesNotExist:
                        return CustomResponse.errors(message="Approval Module not found")

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
            return CustomResponse.server_error(message=f'Failed to Change Approval Module: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Approval Module by UID """
                approval_module = ApprovalModule.objects.filter(uid=uid, is_deleted=False).first()
                if not approval_module:
                    return CustomResponse.errors(message="Approval Module Not Found or Deleted",)

                approval_module.is_deleted = True
                approval_module.deleted_at = datetime.now()
                approval_module.deleted_by = request.user.id
                approval_module.save()
                return CustomResponse.success(message='Approval Module deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Approval Module")
