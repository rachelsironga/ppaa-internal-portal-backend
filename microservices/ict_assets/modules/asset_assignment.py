# asset_assignment.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import AssetAssignment
from microservices.ict_assets.serializers import AssetAssignmentSerializer, AssetAssignmentDetailSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class AssetAssignmentView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = AssetAssignmentSerializer
    required_permissions = {
        "get": [
            "view_assetassignment"
        ],
        "post": [
            "add_assetassignment",
            "change_assetassignment",
        ],
        "delete": [
            "delete_assetassignment",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                assignment = AssetAssignment.objects.filter(uid=uid, is_deleted=False).first()
                if not assignment:
                    raise NotFound("Asset Assignment not found")
                return CustomResponse.success(data=AssetAssignmentDetailSerializer(assignment).data)

            search_query = request.GET.get('search', '').strip()
            asset_uid = request.GET.get('asset', '').strip()
            assigned_to_uid = request.GET.get('assigned_to', '').strip()
            status = request.GET.get('status', '').strip()
            
            assignments = AssetAssignment.objects.filter(is_deleted=False)

            if asset_uid:
                assignments = assignments.filter(asset__uid=asset_uid)

            if assigned_to_uid:
                assignments = assignments.filter(assigned_to__uid=assigned_to_uid)

            if status:
                assignments = assignments.filter(status=status)

            if search_query:
                assignments = assignments.filter(
                    Q(asset__asset_tag__icontains=search_query) | 
                    Q(assigned_to__first_name__icontains=search_query) |
                    Q(assigned_to__last_name__icontains=search_query) |
                    Q(notes__icontains=search_query)
                )

            if assignments.exists():
                return CustomPagination.paginate(view_class=self, results=assignments, request=request)

            return CustomResponse.errors(message="Asset Assignments not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Asset Assignments: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = AssetAssignment.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                    except AssetAssignment.DoesNotExist:
                        return CustomResponse.errors(message="Asset Assignment not found")
                else:
                    serializer = self.serializer_class(data=request.data, context={'request': request})

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Change Asset Assignment: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                assignment = AssetAssignment.objects.filter(uid=uid, is_deleted=False).first()
                if not assignment:
                    return CustomResponse.errors(message="Asset Assignment Not Found or Already Deleted")

                assignment.is_deleted = True
                assignment.deleted_at = datetime.now()
                assignment.deleted_by = request.user
                assignment.save()
                return CustomResponse.success(message='Asset Assignment deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Asset Assignment")
        


        