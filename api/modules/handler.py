from datetime import datetime

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from yaml import serialize

from api.serializers import  RequestHandlerSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_model.models import ApprovalRequestHandler, ApprovalRequestHandler
from utils.permissions import HasMethodPermission


class RequestHandler(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = RequestHandlerSerializer
    required_permissions = {
        "get": ["can_view_request_handling"],
        "post": ["can_perform_request_handling", "can_view_request_handling"],
        "delete": ["can_perform_request_handling"],
    }

    def get_queryset(self, request, uid=None):
        """Build queryset based on user and filters"""
        qs = ApprovalRequestHandler.objects.filter(is_deleted=False)

        if uid:
            return qs.filter(uid=uid).first()

        # Superusers and admins see all, others see their own
        if not (request.user.is_superuser or "admin" in request.user.get_groups()):
            qs = qs.filter(handler=request.user)

        # Apply search filter
        search_query = request.GET.get("search", "").strip()
        if search_query:
            qs = qs.filter(
                Q(approval_request__title__icontains=search_query)  # icontains is better for search
            )

        # Apply status filters
        raw_filters = (request.GET.get("filters") or "").strip()
        filters = [f.strip().upper() for f in raw_filters.split(",") if f.strip()]
        if "ALL" in filters and len(filters) > 1:
            filters = ["PENDING", "DONE", "POSTPONED"]

        if filters:
            qs = qs.filter(status__in=filters)

        return qs

    def get(self, request, uid=None):
        try:
            serializer = self.serializer_class()
            # Case 1: single record by UID
            if uid:
                handlers = self.get_queryset(request, uid)
                if not handlers:
                    raise NotFound("Approval Request Handler not found")
                return CustomResponse.success(
                    data=ApprovalRequestHandler(handlers).data
                )

            # Case 2: list with filters/pagination
            queryset = self.get_queryset(request)
            if not queryset.exists():
                return CustomResponse.errors(
                    message="Approval Request Handler not found", data=[]
                )

            return CustomPagination.paginate(
                view_class=self, results=queryset, request=request
            )

        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to Retrieve Approval Request Handlers: {str(e)}"
            )


    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = ApprovalRequestHandler.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except ApprovalRequestHandler.DoesNotExist:
                        return CustomResponse.errors(message="Approval Request Handler not found")

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
            return CustomResponse.server_error(message=f'Failed to Change Approval Request Handler: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Approval Request Handler by UID """
                approval_request_handler = ApprovalRequestHandler.objects.filter(uid=uid, is_deleted=False).first()
                if not approval_request_handler:
                    return CustomResponse.errors(message="Approval Request Handler Not Found or Deleted",)

                approval_request_handler.is_deleted = True
                approval_request_handler.deleted_at = datetime.now()
                approval_request_handler.deleted_by = request.user.id
                approval_request_handler.save()
                return CustomResponse.success(message='Approval Request Handler deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Approval Request Handler")
