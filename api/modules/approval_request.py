from datetime import datetime
from django.db import transaction
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db.models import Q, Exists, OuterRef
from api.serializers import ApprovalRequestSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.models import UserProfile
from mnh_model.models import ApprovalRequest, ApprovalModuleLevel
from utils.permissions import HasMethodPermission


class ApprovalRequestView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = ApprovalRequestSerializer
    required_permissions = {
        "get": ["can_view_approval_request","can_view_approval_module_lookup"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                approval_request = ApprovalRequest.objects.filter(
                    uid=uid, is_deleted=False
                ).select_related('module', 'department', 'created_by').first()

                if not approval_request:
                    raise NotFound("Approval Request not found")

                serializer = self.serializer_class(
                    approval_request,
                    context={
                        'request': request,
                        'show_full_user': True,
                        'approval_request_uid': approval_request.uid
                    }
                )
                return CustomResponse.success(data=serializer.data)

            search_query = (request.GET.get('search') or '').strip()
            raw_filters = (request.GET.get('filters') or '').strip()
            filters = [f.strip().upper() for f in raw_filters.split(',') if f.strip()] if raw_filters else []

            # normalize ALL behavior (if ALL + others -> drop ALL, keep others)
            if "ALL" in filters and len(filters) > 1:
                filters = [f for f in filters if f != "ALL"]

            # Base queryset: requests where user is involved via module-level match.
            # Do NOT include creator yet; we handle "MY_REQUEST" explicitly below.
            qs = get_user_related_requests(request, include_created=True)

            # Status filters
            valid_statuses = {"NEW", "PENDING", "APPROVED", "REJECTED"}
            selected_statuses = [s for s in filters if s in valid_statuses]
            if selected_statuses:
                qs = qs.filter(status__in=selected_statuses)

            # "MY_REQUEST" filter (only my own created)
            if "MY_REQUEST" in filters:
                qs = ApprovalRequest.objects.filter(
                    is_deleted=False, created_by=request.user
                ).select_related('module', 'department', 'created_by')

                # keep any status filters the user selected
                if selected_statuses:
                    qs = qs.filter(status__in=selected_statuses)

            # Search by title (case-insensitive)
            if search_query:
                qs = qs.filter(title__icontains=search_query)

            # If you need to additionally allow "creator OR matching-level" regardless of MY_REQUEST:
            # qs = get_user_related_requests(profile, include_created=True)

            if qs.exists():
                return CustomPagination.paginate(view_class=self, results=qs, request=request)

            return CustomResponse.errors(message="Approval Request not found", data=[])

        except Exception as e:
            # Helpful console output while keeping client-friendly message
            print("Exception while listing approval requests:", repr(e))
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Approval Requests: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')
                instance = None

                # 1. Check if it's an update operation
                if uid:
                    try:
                        instance = ApprovalRequest.objects.get(uid=uid)
                    except ApprovalRequest.DoesNotExist:
                        return CustomResponse.errors(message="Approval Request not found")

                serializer = self.serializer_class(instance, data=request.data, partial=True)

                # Validate and save
                if serializer.is_valid():
                    serializer.save(created_by=request.user, updated_by=request.user)
                    return CustomResponse.success(data=serializer.data)

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

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Approval Request by UID """
                approval_request = ApprovalRequest.objects.filter(uid=uid, is_deleted=False).first()
                if not approval_request:
                    return CustomResponse.errors(message="Approval Request Not Found or Deleted",)

                approval_request.is_deleted = True
                approval_request.deleted_at = datetime.now()
                approval_request.deleted_by = request.user.id
                approval_request.save()
                return CustomResponse.success(message='Approval Request deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Approval Request")

# ---------- Helper: very fast (EXISTS), no duplicates, minimal queries ----------
def get_user_related_requests(request, include_created=False):
    """
    Return ApprovalRequest for which there EXISTS at least one ApprovalModuleLevel
    on the request's module matching the user's level + department.

    If include_created=True, OR include requests created by this user.
    """
    # current active profile (robust if multiple profiles exist)
    profile = (
        UserProfile.objects
        .select_related('level', 'department')
        .filter(user=request.user, is_active=True)
        .order_by('-created_at')
        .first()
    )

    if not profile or not profile.level_id or not profile.department_id:
        return (
            ApprovalRequest.objects
            .filter(is_deleted=False, created_by=request.user)
            .select_related('module', 'department', 'created_by')
        )

    # Subquery: Does this request's module have a module-level matching the user?
    matching_levels = ApprovalModuleLevel.objects.filter(
        is_active=True,
        module_id=OuterRef('module_id'),
        level_id=profile.level_id,
        department_id=profile.department_id,
    )

    qs = (
        ApprovalRequest.objects
        .filter(is_deleted=False)
        .annotate(_has_match=Exists(matching_levels))
        .select_related('module', 'department', 'created_by')
    )

    if include_created:
        # user is involved if (has matching level/department) OR (is creator)
        qs = qs.filter(Q(_has_match=True) | Q(created_by=profile.user))
    else:
        qs = qs.filter(_has_match=True)

    return qs
