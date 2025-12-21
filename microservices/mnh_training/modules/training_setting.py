# training_setting.py
from datetime import datetime
from django.db import transaction
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from microservices.mnh_training.models import TrainingSetting
from microservices.mnh_training.serializers import TrainingSettingSerializer
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class TrainingSettingView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = TrainingSettingSerializer

    required_permissions = {
        "get": ["view_trainingsetting"],
        "post": ["change_trainingsetting"],
        "put": ["change_trainingsetting"],
        "patch": ["change_trainingsetting"],
    }

    def get(self, request):
        """Get current training settings"""
        try:
            settings = TrainingSetting.get_settings()
            serializer = self.serializer_class(settings, context={'request': request})
            return CustomResponse.success(data=serializer.data)
        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Training Settings: {str(e)}'
            )

    def post(self, request):
        """Create or update training settings"""
        try:
            with transaction.atomic():
                # Get or create the singleton instance
                settings = TrainingSetting.get_settings()

                serializer = self.serializer_class(
                    settings,
                    data=request.data,
                    partial=True,
                    context={'request': request}
                )

                if serializer.is_valid():
                    serializer.save(last_modified_by_guid=request.user.id)
                    return CustomResponse.success(
                        data=serializer.data,
                        message="Training settings updated successfully"
                    )

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Update Training Settings: {str(e)}'
            )

    def put(self, request):
        """Fully update training settings"""
        try:
            with transaction.atomic():
                settings = TrainingSetting.get_settings()

                serializer = self.serializer_class(
                    settings,
                    data=request.data,
                    partial=False,
                    context={'request': request}
                )

                if serializer.is_valid():
                    serializer.save(last_modified_by_guid=request.user.id)
                    return CustomResponse.success(
                        data=serializer.data,
                        message="Training settings updated successfully"
                    )

                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Update Training Settings: {str(e)}'
            )

    def patch(self, request):
        """Partially update training settings"""
        try:
            with transaction.atomic():
                settings = TrainingSetting.get_settings()

                serializer = self.serializer_class(
                    settings,
                    data=request.data,
                    partial=True,
                    context={'request': request}
                )

                if serializer.is_valid():
                    serializer.save(last_modified_by_guid=request.user.id)
                    return CustomResponse.success(
                        data=serializer.data,
                        message="Training settings updated successfully"
                    )

                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Partially Update Training Settings: {str(e)}'
            )

    def set_special_department_config(self, request):
        """Set special configuration for a specific department"""
        try:
            with transaction.atomic():
                settings = TrainingSetting.get_settings()
                department_uid = request.data.get('department_uid')
                config = request.data.get('config')

                if not department_uid or not config:
                    return CustomResponse.errors(
                        message="department_uid and config are required"
                    )

                settings.set_special_department_config(department_uid, config)
                serializer = self.serializer_class(settings, context={'request': request})
                return CustomResponse.success(
                    data=serializer.data,
                    message="Special department configuration set successfully"
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Set Special Department Config: {str(e)}'
            )

    def remove_special_department_config(self, request):
        """Remove special configuration for a specific department"""
        try:
            with transaction.atomic():
                settings = TrainingSetting.get_settings()
                department_uid = request.data.get('department_uid')

                if not department_uid:
                    return CustomResponse.errors(
                        message="department_uid is required"
                    )

                settings.remove_special_department_config(department_uid)
                serializer = self.serializer_class(settings, context={'request': request})
                return CustomResponse.success(
                    data=serializer.data,
                    message="Special department configuration removed successfully"
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Remove Special Department Config: {str(e)}'
            )

    def get_special_department_config(self, request, department_uid):
        """Get special configuration for a specific department"""
        try:
            settings = TrainingSetting.get_settings()
            config = settings.get_special_department_config(department_uid)

            if not config:
                return CustomResponse.errors(
                    message=f"No special configuration found for department {department_uid}"
                )

            return CustomResponse.success(
                data=config,
                message="Special department configuration retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Special Department Config: {str(e)}'
            )
