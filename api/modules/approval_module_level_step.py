from datetime import datetime
from django.utils import timezone

from django.db import transaction
from django.db.models import Q, Max
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from api.serializers import ApprovalModuleSerializer, ApprovalRequestStepSerializer, UserProfileSerializer, \
    ApprovalRequestSerializer, ApprovalRequestCustomiseSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.models import UserProfile, User
from mnh_model.models import ApprovalModule, ApprovalModuleLevel, ApprovalRequestStep, ApprovalRequest, \
    ApprovalRequestHandler
from utils.permissions import HasMethodPermission



class ApproveModuleLevelStepView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = ApprovalRequestStepSerializer
    required_permissions = {
        "get": [
            "can_view_approval_request_step"
        ],
        "post": [
            "can_approve_request",
        ],
    }

    def get(self, request, request_uid):
        try:
            if request_uid:
                request_steps = ApprovalRequestStep.objects.filter(is_deleted=False,
                                                                   approval_request__uid=request_uid).order_by(
                    'created_at')
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
                        expected_level = ApprovalModuleLevel.objects.filter(
                            module=approval_request.module,
                        ).query
                        return CustomResponse.errors(
                            message=f"Sorry. Currently Unable to Find Approving Position Please Try Again ",
                            code=STATUS_CODES["VALIDATION_ERROR"],
                        )

                    # Does user match expected positional level?
                    user_position = user.get_position() if hasattr(user, "get_position") else None

                    if expected_level.level.uid == user_position['level_uid'] and expected_level.department.uid == user_position['department_uid'] :
                        is_acting = False
                    else:
                        # Check if a user is acting for someone in this level
                        acting = UserProfile.objects.filter(
                            is_active=True,
                            acting_user__id=user.id,
                            level=expected_level.level,
                            department=expected_level.department,
                            is_deleted=False
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

                # approval_request.save()
                approval_request.updated_by = user  # Only update the updater
                approval_request.save(update_fields=['status', 'current_state', 'updated_by'])

                if approval_request.status == "APPROVED" or approval_request.status == "REJECTED":
                    handler_user_uid = validated.get("handler_user")
                    if handler_user_uid:
                        handler_user = User.objects.filter(guid=str(handler_user_uid)).first()
                        if not handler_user:
                            return CustomResponse.errors(
                                message="Sorry. We are unable to find the user you are Assign as handler",
                                code=STATUS_CODES["VALIDATION_ERROR"],
                            )

                        approval_request_handler = ApprovalRequestHandler()
                        approval_request_handler.approval_request = approval_request
                        approval_request_handler.handler = handler_user
                        approval_request_handler.created_by = user
                        approval_request_handler.updated_by = user
                        approval_request_handler.created_at = timezone.now()
                        approval_request_handler.updated_at = timezone.now()
                        approval_request_handler.comment = validated.get("comment"),
                        approval_request_handler.save()

                # Return success
                response_serializer = self.serializer_class(step)
                return CustomResponse.success(data=response_serializer.data)

        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to process approval action: {str(e)}"
            )


class ApproveModuleLevelActingUser(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = UserProfileSerializer
    required_permissions = {
        "get": [
            "can_view_approval_request_step",
            "view_department_lookup",
            "view_request_step",
        ],
    }

    def get(self, request):
        try:
            level_uid = request.GET.get('level', "").strip()
            department_uid = request.GET.get('department', "").strip()

            if level_uid != "" and department_uid != "":
                user = request.user
                user_position = user.get_position() if hasattr(user, "get_position") else None
                # Check if a user is acting for someone in this level
                acting = UserProfile.objects.filter(
                    is_active=True,
                    acting_user__id=user.id,
                    level__uid=level_uid,
                    department__uid=department_uid,
                    is_deleted=False
                ).first()
                if acting:
                    return CustomResponse.success(data=UserProfileSerializer(acting).data)

            return CustomResponse.errors(
                message="Your not Acting a Position in This Department",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Departments: {str(e)}', )


class ApprovalRequestCustomise(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = ApprovalRequestCustomiseSerializer
    required_permissions = {
        "post": [
            "can_approve_request",
        ],
    }

    def post(self, request, request_uid):
        try:
            with transaction.atomic():
                if request_uid == "":
                    return CustomResponse.errors(message="Unable to Retrieve Approval Request", code=STATUS_CODES["VALIDATION_ERROR"])
                try:
                    instance = ApprovalRequest.objects.get(uid=request_uid)
                except ApprovalRequest.DoesNotExist:
                    return CustomResponse.errors(message="Approval Request not found")

                serializer = self.serializer_class(instance, data=request.data, partial=True)

                # Validate and save
                if serializer.is_valid():
                    serializer.save(created_by=request.user, updated_by=request.user)
                    return CustomResponse.success(data=ApprovalRequestSerializer(instance).data)

                # Validation failed
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to Change Approval Request: {str(e)}"
            )

