from datetime import datetime

from django.db import transaction
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from api.serializers import ApprovalModuleLevelSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_model.models import ApprovalModuleLevel, ApprovalModule


class ApprovalModuleLevelView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ApprovalModuleLevelSerializer


    def get(self, request, uid=None):
        try:
            if uid:
                approval_module_level = ApprovalModuleLevel.objects.filter(uid=uid, is_deleted=False).first()
                if not approval_module_level:
                    raise NotFound("Approval Module Level not found") 
                return CustomResponse.success(data=ApprovalModuleLevelSerializer(approval_module_level).data)

            search_query = request.GET.get('search', '').strip()
            approval_module_levels = ApprovalModuleLevel.objects.filter(is_deleted=False)

            if search_query:
                approval_module_levels = approval_module_levels.filter(name__icontains=search_query)

            if approval_module_levels.exists():
                return CustomPagination.paginate(self=self, results=approval_module_levels, request=request)

            return CustomResponse.errors(message="Approval Module Level not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Approval Module Levels: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = ApprovalModuleLevel.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except ApprovalModuleLevel.DoesNotExist:
                        return CustomResponse.errors(message="Approval Module Level not found")

                sort_list = request.data.get('sort_list', None)
                module_uid = request.data.get('module_uid', None)
                if sort_list and module_uid:
                    module = ApprovalModule.objects.filter(uid=module_uid, is_deleted=False).first()
                    if not module:
                        CustomResponse.errors(message="Approval Module Level not found")

                    # get all levels under the selected module
                    levels = ApprovalModuleLevel.objects.filter(module=module, is_deleted=False).all()
                    if not levels:
                        return CustomResponse.errors(message="Approval Module Level not found")

                    # Create a mapping of uid to desired order
                    uid_to_order = {uid: index+1 for index, uid in enumerate(sort_list)}
                    # Prepare list for bulk update
                    levels_to_update = []
                    for level in levels:
                        level_uid_str = str(level.uid)
                        if level_uid_str in uid_to_order:
                            level.order = uid_to_order[level_uid_str]
                            levels_to_update.append(level)
                    try:
                        with transaction.atomic():
                            ApprovalModuleLevel.objects.bulk_update(levels_to_update, ['order'])
                        return CustomResponse.success(message="Positional Levels updated successfully")
                    except Exception as e:
                        return CustomResponse.errors(message=f"Failed to update: {str(e)}")
                else:
                    '''Handle create if no UID and sort_list or module_uid passed in request'''
                    serializer = self.serializer_class(data=request.data)


                # Validate and save
                if serializer.is_valid():
                    if uid and instance:
                        serializer.update(instance=instance, validated_data=serializer.validated_data)
                    else:
                        serializer.save(created_by=request.user.id, updated_by=request.user.id)
                    return CustomResponse.success(data=serializer.data)

                # Validation failed
                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            # Catch unexpected errors that occur in the entire process
            return CustomResponse.server_error(message=f'Failed to Change Approval Module Level: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Approval Module Level by UID """
                approval_module_level = ApprovalModuleLevel.objects.filter(uid=uid, is_deleted=False).first()
                if not approval_module_level:
                    return CustomResponse.errors(message="Approval Module Level Not Found or Deleted",)

                approval_module_level.is_deleted = True
                approval_module_level.deleted_at = datetime.now()
                approval_module_level.deleted_by = request.user.id
                approval_module_level.save()
                return CustomResponse.success(message='Approval Module Level deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Approval Module Level")
