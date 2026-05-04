from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission

from ..models import ReportSetting
from ..serializers import ReportSettingSerializer


class ReportSettingView(APIView):
    """API view for Report Settings management"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_reportsetting"],
        "put": ["change_reportsetting"],
        "patch": ["change_reportsetting"],
    }

    def get(self, request):
        """Get report settings"""
        try:
            settings = ReportSetting.get_settings()
            serializer = ReportSettingSerializer(settings)
            return CustomResponse.success(
                data=serializer.data,
                message="Report Settings retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve Report Settings: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def put(self, request):
        """Update report settings"""
        try:
            settings = ReportSetting.get_settings()
            serializer = ReportSettingSerializer(
                settings, data=request.data, partial=True
            )
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            serializer.save(updated_by=request.user)
            return CustomResponse.success(
                data=serializer.data,
                message="Report Settings updated successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to update Report Settings: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )
