from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.models import User, UserProfile
from mnh_auth.serializers import UserSerializer


class UserView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                user = User.objects.filter(guid=uid, is_deleted=False).first()
                if not user:
                    raise NotFound("User not found")
                return CustomResponse.success(data=self.serializer_class(user).data)

            users = User.objects.filter(is_deleted=False)

            search_query = request.GET.get('search', '').strip()
            if search_query:
                users = users.filter(
                    Q(username__icontains=search_query) |
                    Q(email__icontains=search_query) |
                    Q(pf_number__icontains=search_query) |
                    Q(check_number__icontains=search_query) |
                    Q(first_name__icontains=search_query) |
                    Q(middle_name__icontains=search_query) |
                    Q(last_name__icontains=search_query) |
                    Q(phone_number__icontains=search_query) |
                    Q(alternative_contact__icontains=search_query)
                )

            if users.exists():
                context = {"is_auth_view": False}
                return CustomPagination.paginate(
                    view_class=self,
                    results=users,
                    request=request,
                    serializer_context=context
                )

            return CustomResponse.errors(message="User not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Users: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid')
                instance = None
                is_update = False

                if uid:
                    try:
                        instance = User.objects.get(uid=uid)
                    except User.DoesNotExist:
                        return CustomResponse.errors(message="User not found")

                    if instance.is_deleted:
                        return CustomResponse.errors(message="You can't update. User is already deleted")
                    if not instance.is_active:
                        return CustomResponse.errors(message="You can't update a disabled user")
                    is_update = True

                # Initialize serializer
                serializer = self.serializer_class(
                    instance=instance,
                    data=request.data,
                    partial=is_update
                )

                if not serializer.is_valid():
                    return CustomResponse.errors(
                        message="Validation failed, please try again",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )

                # Save with appropriate creator/updater
                user = serializer.save(
                    updated_by=request.user.id,
                    **({'created_by': request.user.id} if not is_update else {})
                )

                # Set password only on creation
                if not is_update:
                    last_name = serializer.validated_data.get('last_name') or 'password'
                    pf_number = serializer.validated_data.get('pf_number', '')
                    password = f"{last_name.upper()}@{pf_number}"
                    user.set_password(password)
                    user.save(update_fields=["password"])

                return CustomResponse.success(data=serializer.data)

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Change User: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                user = User.objects.filter(uid=uid,is_deleted=False).first()
                if not User:
                    return CustomResponse.errors(message="User Not Found or Already Deleted", )

                user.is_deleted = True
                user.deleted_at=timezone.datetime.now()
                user.deleted_by = request.user
                user.save()
                return CustomResponse.success(message='User deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting User")
