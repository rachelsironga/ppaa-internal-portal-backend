from datetime import datetime
from django.utils import timezone

from django.db import transaction
from django.db.models import Q, Max
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from api.serializers import ApprovalModuleSerializer, ApprovalRequestStepSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.models import UserProfile
from mnh_model.models import ApprovalModule, ApprovalModuleLevel, ApprovalRequestStep, ApprovalRequest
from utils.permissions import HasMethodPermission



class ApproveModuleLevelStepView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = ApprovalRequestStepSerializer

    def get(self, request, request_uid):
        try:
            if request_uid:
                request_steps = ApprovalRequestStep.objects.filter(is_deleted=False,
                                                                   approval_request__uid=request_uid).order_by(
                    'action_count')
                if request_steps.exists():
                    return CustomPagination.paginate(view_class=self, results=request_steps, request=request)

            return CustomResponse.errors(message="Please Specify Request to view Approval History", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Departments: {str(e)}', )

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
                    approval_request.status = "PENDING" if approval_request.current_state > 0 else 'REJECTED'
                    approval_request.current_state = approval_request.current_state - 1 if approval_request.current_state > 0 else 0
                    is_approved = False

                else:
                    return CustomResponse.errors(
                        message="Sorry We Unable to Identify your Action",
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )

                # Deactivate any previous active steps for this module level
                ApprovalRequestStep.objects.filter(
                    approval_request=approval_request,
                    approval_module_level=approval_module_level,
                    is_active=True
                ).update(is_active=False)

                # Get the max action count to increment
                previous_steps = ApprovalRequestStep.objects.filter(
                    approval_request=approval_request,
                    approval_module_level=approval_module_level
                )
                max_count = previous_steps.aggregate(Max("action_count"))["action_count__max"] or 0
                new_action_count = max_count + 1

                # Save step
                step = ApprovalRequestStep.objects.create(
                    approval_request=approval_request,
                    approval_module_level=approval_module_level,
                    approved_by=user,
                    is_acting=is_acting,
                    is_approved=is_approved,
                    action_count=new_action_count,
                    is_active=True,
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
