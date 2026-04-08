from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone

from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_portal.pagination import CustomPagination
from utils.permissions import HasMethodPermission

from ..models import FinancialYear, FinancialPeriod
from ..serializers import FinancialYearSerializer, FinancialPeriodSerializer
from .report import create_audit_trail


class FinancialYearView(APIView):
    """API view for Financial Year management"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = FinancialYearSerializer
    required_permissions = {
        "get": ["view_financialyear"],
        "post": ["add_financialyear"],
        "put": ["change_financialyear"],
        "patch": ["change_financialyear"],
        "delete": ["delete_financialyear"],
    }

    def get(self, request, uid=None):
        """Get financial year(s)"""
        try:
            if uid:
                financial_year = FinancialYear.objects.filter(
                    uid=uid, is_deleted=False
                ).first()
                if not financial_year:
                    return CustomResponse.errors(
                        message="Financial Year not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                serializer = FinancialYearSerializer(financial_year)
                return CustomResponse.success(
                    data=serializer.data,
                    message="Financial Year retrieved successfully"
                )

            queryset = FinancialYear.objects.filter(is_deleted=False)

            # Filters
            is_current = request.query_params.get('is_current')
            if is_current:
                queryset = queryset.filter(is_current=is_current.lower() == 'true')

            is_active = request.query_params.get('is_active')
            if is_active:
                queryset = queryset.filter(is_active=is_active.lower() == 'true')

            search = request.query_params.get('search')
            if search:
                queryset = queryset.filter(name__icontains=search)

            queryset = queryset.order_by('-start_date')

            if request.query_params.get('paginated', 'false').lower() == 'true':
                return CustomPagination.paginate(
                    view_class=self,
                    results=queryset,
                    request=request
                )

            serializer = FinancialYearSerializer(queryset, many=True)
            return CustomResponse.success(
                data=serializer.data,
                message="Financial Years retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve Financial Years: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def post(self, request):
        """Create a new financial year"""
        try:
            serializer = FinancialYearSerializer(data=request.data)
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            financial_year = serializer.save(created_by=request.user, updated_by=request.user)
            create_audit_trail(
                report=None,
                action="created",
                user=request.user,
                new_value=financial_year.name,
                request=request,
                entity_type="Financial Year",
                entity_uid=financial_year.uid,
                entity_name=financial_year.name,
            )
            return CustomResponse.success(
                data=serializer.data,
                message="Financial Year created successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to create Financial Year: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def put(self, request, uid):
        """Update a financial year"""
        try:
            financial_year = FinancialYear.objects.filter(
                uid=uid, is_deleted=False
            ).first()
            if not financial_year:
                return CustomResponse.errors(
                    message="Financial Year not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            serializer = FinancialYearSerializer(
                financial_year, data=request.data, partial=True
            )
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            old_value = financial_year.name
            financial_year = serializer.save(updated_by=request.user)
            create_audit_trail(
                report=None,
                action="updated",
                user=request.user,
                old_value=old_value,
                new_value=financial_year.name,
                request=request,
                entity_type="Financial Year",
                entity_uid=financial_year.uid,
                entity_name=financial_year.name,
            )
            return CustomResponse.success(
                data=serializer.data,
                message="Financial Year updated successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to update Financial Year: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def delete(self, request, uid):
        """Soft delete a financial year"""
        try:
            financial_year = FinancialYear.objects.filter(
                uid=uid, is_deleted=False
            ).first()
            if not financial_year:
                return CustomResponse.errors(
                    message="Financial Year not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            # Check if financial year is in use
            if financial_year.reports.filter(is_deleted=False).exists():
                return CustomResponse.errors(
                    message="Cannot delete Financial Year with associated reports",
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            old_value = financial_year.name
            financial_year.is_deleted = True
            financial_year.deleted_at = timezone.now()
            financial_year.deleted_by = request.user
            financial_year.save()
            create_audit_trail(
                report=None,
                action="deleted",
                user=request.user,
                old_value=old_value,
                request=request,
                entity_type="Financial Year",
                entity_uid=financial_year.uid,
                entity_name=financial_year.name,
            )

            return CustomResponse.success(
                message="Financial Year deleted successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to delete Financial Year: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class FinancialPeriodView(APIView):
    """API view for Financial Period management (Quarters/Months)"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_financialyear"],
        "post": ["add_financialyear"],
        "put": ["change_financialyear"],
        "patch": ["change_financialyear"],
        "delete": ["delete_financialyear"],
    }

    def get(self, request, financial_year_uid=None, uid=None):
        """Get financial periods - optionally filtered by financial year"""
        try:
            if uid:
                period = FinancialPeriod.objects.filter(
                    uid=uid, is_deleted=False
                ).first()
                if not period:
                    return CustomResponse.errors(
                        message="Financial Period not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                serializer = FinancialPeriodSerializer(period)
                return CustomResponse.success(
                    data=serializer.data,
                    message="Financial Period retrieved successfully"
                )

            queryset = FinancialPeriod.objects.filter(is_deleted=False)

            # Filter by financial year
            if financial_year_uid:
                queryset = queryset.filter(financial_year__uid=financial_year_uid)
            
            # Get quarters from query params if present
            fy_uid = request.query_params.get('financial_year_uid')
            if fy_uid:
                queryset = queryset.filter(financial_year__uid=fy_uid)

            # Filter by period type
            period_type = request.query_params.get('period_type')
            if period_type:
                # Ensure biannual periods exist for requested FY (handles older FY records)
                target_fy_uid = financial_year_uid or fy_uid
                if period_type == 'biannual' and target_fy_uid:
                    fy = FinancialYear.objects.filter(uid=target_fy_uid, is_deleted=False).first()
                    if fy:
                        try:
                            fy._create_biannual_periods()
                        except Exception:
                            pass
                queryset = queryset.filter(period_type=period_type)

            is_active = request.query_params.get('is_active')
            if is_active:
                queryset = queryset.filter(is_active=is_active.lower() == 'true')

            queryset = queryset.order_by('financial_year', 'period_type', 'period_number')

            serializer = FinancialPeriodSerializer(queryset, many=True)
            return CustomResponse.success(
                data=serializer.data,
                message="Financial Periods retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve Financial Periods: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def post(self, request, financial_year_uid=None):
        """Create a new financial period"""
        try:
            data = request.data.copy()
            
            # If financial_year_uid in URL, use it
            if financial_year_uid:
                fy = FinancialYear.objects.filter(
                    uid=financial_year_uid, is_deleted=False
                ).first()
                if not fy:
                    return CustomResponse.errors(
                        message="Financial Year not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                data['financial_year'] = fy.id
            
            serializer = FinancialPeriodSerializer(data=data)
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            serializer.save(created_by=request.user, updated_by=request.user)
            return CustomResponse.success(
                data=serializer.data,
                message="Financial Period created successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to create Financial Period: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def put(self, request, uid):
        """Update a financial period"""
        try:
            period = FinancialPeriod.objects.filter(
                uid=uid, is_deleted=False
            ).first()
            if not period:
                return CustomResponse.errors(
                    message="Financial Period not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            serializer = FinancialPeriodSerializer(
                period, data=request.data, partial=True
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
                message="Financial Period updated successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to update Financial Period: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

    @transaction.atomic
    def delete(self, request, uid):
        """Soft delete a financial period"""
        try:
            period = FinancialPeriod.objects.filter(
                uid=uid, is_deleted=False
            ).first()
            if not period:
                return CustomResponse.errors(
                    message="Financial Period not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            # Check if period is in use
            if period.reports.filter(is_deleted=False).exists():
                return CustomResponse.errors(
                    message="Cannot delete Financial Period with associated reports",
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            period.is_deleted = True
            period.deleted_at = timezone.now()
            period.deleted_by = request.user
            period.save()

            return CustomResponse.success(
                message="Financial Period deleted successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to delete Financial Period: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )
