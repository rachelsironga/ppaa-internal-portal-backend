from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_analytical.models import Block
from microservices.mnh_analytical.serializers import BlockSerializer, BlockListSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class BlockView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = BlockSerializer
    required_permissions = {
        "get": ["view_block"],
        "post": ["add_block", "change_block"],
        "delete": ["delete_block"]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                block = Block.objects.filter(uid=uid, is_deleted=False).first()
                if not block:
                    raise NotFound("Block not found")
                return CustomResponse.success(data=BlockSerializer(block).data)

            search_query = request.GET.get('search', '').strip()
            location = request.GET.get('location', '').strip()
            blocks = Block.objects.filter(is_deleted=False)

            if search_query:
                blocks = blocks.filter(
                    Q(name__icontains=search_query) |
                    Q(code__icontains=search_query) |
                    Q(description__icontains=search_query)
                )

            if location:
                blocks = blocks.filter(location=location)

            if blocks.exists():
                return CustomPagination.paginate(view_class=self, results=blocks, request=request)

            return CustomResponse.errors(message="Blocks not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Blocks: {str(e)}')

    def post(self, request, uid=None):
        try:
            with transaction.atomic():
                uid = uid or request.data.get('uid', None)
                if uid:
                    try:
                        instance = Block.objects.get(uid=uid, is_deleted=False)
                        serializer = self.serializer_class(
                            instance, data=request.data, partial=True, context={'request': request}
                        )
                    except Block.DoesNotExist:
                        return CustomResponse.errors(message="Block not found")
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
            return CustomResponse.server_error(message=f'Failed to Save Block: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                block = Block.objects.filter(uid=uid, is_deleted=False).first()
                if not block:
                    return CustomResponse.errors(message="Block Not Found or Already Deleted")

                block.is_deleted = True
                block.deleted_at = datetime.now()
                block.deleted_by = request.user
                block.save()
                return CustomResponse.success(message='Block deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Block")
