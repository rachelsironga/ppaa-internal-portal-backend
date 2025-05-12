from datetime import datetime

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from api.serializers import ApprovalRequestSerializer, REQUEST_TYPE_SERIALIZER_IMPORTS, get_serializer_class
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_model.models import ApprovalRequest, ApprovalModule


class ApprovalRequestView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ApprovalRequestSerializer


    def get(self, request, uid=None):
        try:
            if uid:
                approval_request = ApprovalRequest.objects.filter(uid=uid, is_deleted=False).first()
                if not approval_request:
                    raise NotFound("Approval Request not found")

                # Get related instance dynamically based on type
                try:
                    related_attr = approval_request.type.lower()
                    related_instance = getattr(approval_request, related_attr, None)
                except AttributeError:
                    related_instance = None

                # Attach it dynamically for serializer
                setattr(approval_request, 'request_details', related_instance)

                return CustomResponse.success(data=ApprovalRequestSerializer(approval_request).data)


            search_query = request.GET.get('search', '').strip()
            approval_request = ApprovalRequest.objects.filter(is_deleted=False)

            if search_query:
                approval_request = approval_request.filter(name__icontains=search_query)

            if approval_request.exists():
                return CustomPagination.paginate(self=self, results=approval_request, request=request)

            return CustomResponse.errors(message="Approval Request not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Approval Requests: {str(e)}', )

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

                # 2. Handle base serializer
                base_serializer = self.serializer_class(
                    instance, data=request.data, partial=bool(instance)
                )

                # 3. Validate request type and load child serializer
                request_type = request.data.get('type')
                request_data = request.data.get('request_data', {})
                if base_serializer.is_valid():
                    if instance:
                        instance = base_serializer.update(instance, base_serializer.validated_data)
                    else:
                        instance = base_serializer.save(created_by=request.user, updated_by=request.user)

                    # 4. Save child serializer (specific request model)
                    request_data['approval_request'] = instance.id

                    try:
                        serializer_class = get_serializer_class(request_type)
                    except ImproperlyConfigured:
                        return CustomResponse.errors(
                            message=f"Request type '{request_type}' not supported",
                            data=base_serializer.errors,
                            code=STATUS_CODES['VALIDATION_ERROR']
                        )

                    child_serializer = serializer_class(data=request_data)
                    if child_serializer.is_valid(raise_exception=True):
                        print(child_serializer.validated_data)
                        child_serializer.save()
                    else:
                        return CustomResponse.errors(
                            message="Validation Failed",
                            data=child_serializer.errors,
                            code=STATUS_CODES["VALIDATION_ERROR"]
                        )

                    return CustomResponse.success(data=base_serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed",
                    data=base_serializer.errors,
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
