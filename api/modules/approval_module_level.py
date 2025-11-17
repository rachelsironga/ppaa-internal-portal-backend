from datetime import datetime

from django.db import transaction
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from api.serializers import ApprovalModuleLevelSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_model.models import ApprovalModuleLevel, ApprovalModule
from utils.permissions import HasMethodPermission



class ApprovalModuleLevelView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = ApprovalModuleLevelSerializer
    required_permissions = {
        "get": [
            "view_approvalmodulelevel"
        ],
        "post": [
            "add_approvalmodulelevel",
            "change_approvalmodulelevel",
        ],
        "delete": [
            "delete_approvalmodulelevel",
        ]
    }


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
                return CustomPagination.paginate(view_class=self, results=approval_module_levels, request=request)

            return CustomResponse.errors(message="Approval Module Level not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Approval Module Levels: {str(e)}', )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                sort_list = request.data.get('sort_list', None)
                module_uid = request.data.get('module_uid', None)

                # --- CASE 1: UPDATE existing level ---
                if uid:
                    try:
                        instance = ApprovalModuleLevel.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except ApprovalModuleLevel.DoesNotExist:
                        return CustomResponse.errors(message="Approval Module Level not found")

                # --- CASE 2: SORTING existing levels ---
                elif sort_list and module_uid:
                    module = ApprovalModule.objects.filter(uid=module_uid, is_deleted=False).first()
                    if not module:
                        return CustomResponse.errors(message="Approval Module not found")

                    levels = ApprovalModuleLevel.objects.filter(module=module, is_deleted=False).all()
                    if not levels:
                        return CustomResponse.errors(message="No levels found under this module")

                    uid_to_order = {uid: index + 1 for index, uid in enumerate(sort_list)}
                    levels_to_update = []
                    for level in levels:
                        level_uid_str = str(level.uid)
                        if level_uid_str in uid_to_order:
                            level.order = uid_to_order[level_uid_str]
                            levels_to_update.append(level)

                    ApprovalModuleLevel.objects.bulk_update(levels_to_update, ['order'])
                    return CustomResponse.success(message="Positional Levels updated successfully")

                # --- CASE 3: CREATE new level ---
                else:
                    serializer = self.serializer_class(data=request.data)

                    if serializer.is_valid():
                        module_uid = request.data.get('module_uid')
                        module = ApprovalModule.objects.filter(uid=module_uid, is_deleted=False).first()

                        if not module:
                            return CustomResponse.errors(message="Approval Module not found")

                        # ✅ Find next available order number for this module
                        last_level = (
                            ApprovalModuleLevel.objects
                            .filter(module=module, is_deleted=False)
                            .order_by('-order', '-created_at')
                            .first()
                        )
                        next_order = last_level.order + 1 if last_level else 1

                        # Save with the new order
                        serializer.save(
                            module=module,
                            order=next_order,
                            created_by=request.user,
                            updated_by=request.user
                        )

                        return CustomResponse.success(
                            message=f"Level created successfully (Order {next_order})",
                            data=serializer.data
                        )

                    # Validation failed
                    return CustomResponse.errors(
                        message="Validation Failed, Please Try Again",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Change Approval Module Level: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Approval Module Level by UID """
                approval_module_level = ApprovalModuleLevel.objects.filter(uid=uid, is_deleted=False).first()
                if not approval_module_level:
                    return CustomResponse.errors(message="Approval Module Level Not Found or Deleted",)

                approval_module_level.is_deleted = True
                approval_module_level.deleted_at = datetime.now()
                approval_module_level.deleted_by = request.user
                approval_module_level.save()
                return CustomResponse.success(message='Approval Module Level deleted successfully')

        except Exception as e:
            print(f'{str(e)}')
            return CustomResponse.server_error(message="Something went wrong While Deleting Approval Module Level")
