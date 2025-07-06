from datetime import datetime
from django.utils import timezone


from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from api.serializers import ApprovalModuleSerializer, ApprovalRequestStepSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.models import UserProfile
from mnh_model.models import ApprovalModule, ApprovalModuleLevel, ApprovalRequestStep


class ApproveModuleLevelStepView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ApprovalRequestStepSerializer

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data, context={'request': request})
                if not serializer.is_valid():
                    return CustomResponse.errors(
                        message="Validation Failed",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )

                validated = serializer.validated_data
                action = validated.get("action")
                approval_request = validated["approval_request"]
                approval_module_level = validated["approval_module_level"]
                user = request.user

                if approval_request.status in ("APPROVED", "REJECTED"):
                    return CustomResponse.errors(
                        message="You cannot perform any action: request is already closed.",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )

                # Default flags
                is_acting = False
                is_approved = False

                if action == "FORWARD":
                    # Check if user is authorized to approve
                    expected_level = ApprovalModuleLevel.objects.filter(
                        module=approval_request.module,
                        order=approval_request.current_state + 1
                    ).first()

                    if not expected_level:
                        return CustomResponse.errors(
                            message="Sorry. Currently Unable to Find Approving Position Please Try Again",
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )

                    # Does user match expected positional level?
                    user_position = user.get_position() if hasattr(user, "get_position") else None

                    if expected_level.level == user_position:
                        is_acting = False
                    else:
                        # Check if a user is acting for someone in this level
                        acting = UserProfile.objects.filter(
                            is_active=True,
                        ).exclude(id=user.id).filter(
                            acting_user__id=user.id
                        ).exists()
                        if not acting:
                            return CustomResponse.errors(
                                message="You are not allowed to perform this action.",
                                code=STATUS_CODES["VALIDATION_ERROR"],
                            )
                        is_acting = True

                    # Mark approved and advance state
                    is_approved = True
                    approval_request.current_state += 1

                    # If no more levels mark APPROVED
                    total_levels = ApprovalModuleLevel.objects.filter(
                        module=approval_request.module,
                        is_deleted=False
                    ).count()
                    if approval_request.current_state >= total_levels:
                        approval_request.status = "APPROVED"
                    else:
                        approval_request.status = "PENDING"

                elif action == "RETURN":
                    # Mark REJECTED
                    approval_request.status = "PENDING"
                    approval_request.current_state = approval_request.current_state - 1 if approval_request.current_state > 0 else 0
                    is_approved = False

                else:
                    return CustomResponse.errors(
                        message="Sorry We Unable to Identify your Action",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )

                # Save step
                step = ApprovalRequestStep.objects.create(
                    approval_request=approval_request,
                    approval_module_level=approval_module_level,
                    approved_by=user,
                    is_acting=is_acting,
                    is_approved=is_approved,
                    comment=validated.get("comment"),
                    created_by=user,
                    updated_by=user,
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                )

                approval_request.save()

                # Return success
                response_serializer = self.serializer_class(step)
                return CustomResponse.success(data=response_serializer.data)

        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to process approval action: {str(e)}"
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Approval Module by UID """
                approval_module = ApprovalModule.objects.filter(uid=uid, is_deleted=False).first()
                if not approval_module:
                    return CustomResponse.errors(message="Approval Module Not Found or Deleted",)

                approval_module.is_deleted = True
                approval_module.deleted_at = timezone.now()
                approval_module.deleted_by = request.user
                approval_module.save()
                return CustomResponse.success(message='Approval Module deleted successfully')

        except Exception as e:
            print(f'Failed to Delete Approval Module: {str(e)}')
            return CustomResponse.server_error(message="Something went wrong While Deleting Approval Module")
