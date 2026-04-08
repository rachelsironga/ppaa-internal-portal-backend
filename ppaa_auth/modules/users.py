import pandas as pd
from django.db import transaction, models
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from sqlparse.engine.grouping import group

from api.utils import base64_to_excel_file, generate_acronym
from ppaa_portal.pagination import CustomPagination
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_auth.models import User, UserProfile
from ppaa_auth.serializers import UserSerializer, FileUploadSerializer, UserImportSerializer
from utils.minio_storage import MinioStorage
from utils.permissions import HasMethodPermission



class UserView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = UserSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                user = User.objects.filter(guid=uid, is_deleted=False).first()
                if not user:
                    raise NotFound("User not found")
                return CustomResponse.success(data=self.serializer_class(user).data)

            users = User.objects.filter(is_deleted=False)

            group_id = request.GET.get('group_id', '').strip()
            if group_id:
                users = users.filter(groups__id=group_id)

            search_query = request.GET.get('search', '').strip()
            if search_query:
                # Search only user fields first
                user_search = Q(
                    Q(username__icontains=search_query) |
                    Q(email__icontains=search_query) |
                    Q(check_number__icontains=search_query) |
                    Q(first_name__icontains=search_query) |
                    Q(middle_name__icontains=search_query) |
                    Q(last_name__icontains=search_query) |
                    Q(phone_number__icontains=search_query) |
                    Q(alternative_contact__icontains=search_query) |
                    Q(status__icontains=search_query)
                )

                # Search profile fields separately
                # NOTE: `user_profiles` comes from UserProfile.user related_name='user_profiles'
                profile_search = (
                    Q(user_profiles__is_active=True, user_profiles__is_deleted=False)
                    & (
                        Q(user_profiles__level__name__icontains=search_query)
                        | Q(user_profiles__department__name__icontains=search_query)
                    )
                )

                users = users.filter(user_search | profile_search).distinct()

            # Add annotations for display only
            users = users.annotate(
                current_level_name=models.Subquery(
                    UserProfile.objects.filter(
                        user=models.OuterRef('pk'),
                        is_active=True,
                        is_deleted=False
                    ).values('level__name')[:1]
                ),
                current_department_name=models.Subquery(
                    UserProfile.objects.filter(
                        user=models.OuterRef('pk'),
                        is_active=True,
                        is_deleted=False
                    ).values('department__name')[:1]
                )
         
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
            print(f"Fail to Retrieve Users {e}")
            return CustomResponse.server_error(message=f'Failed to Retrieve Users: {str(e)}', )

    def post(self, request):
        try:
            with transaction.atomic():
                # Accept both user_guid and guid (frontend may send either); treat empty string as missing
                raw_guid = request.data.get("user_guid") or request.data.get("guid")
                user_guid = (raw_guid or "").strip() or None
                instance = None
                is_update = False

                # ----------- Determine Update or Create -----------
                if user_guid:
                    print("-------------user_guid------------", user_guid)
                    try:
                        instance = User.objects.get(guid=user_guid)
                    except User.DoesNotExist:
                        return CustomResponse.errors(message="User not found")

                    if instance.is_deleted:
                        return CustomResponse.errors(message="User already deleted")

                    if not instance.is_active:
                        return CustomResponse.errors(message="Cannot update disabled user")

                    is_update = True

                # ----------- Prepare Data Before Validation -----------
                data = request.data.copy()

                # Uppercase formatting
                if "first_name" in data:
                    data["first_name"] = data["first_name"].strip().upper()

                if "middle_name" in data:
                    m = data.get("middle_name")
                    data["middle_name"] = m.strip().upper() if m else ""

                if "last_name" in data:
                    data["last_name"] = data["last_name"].strip().upper()

                # Set username for creation
                if not is_update:
                    if "first_name" in data and "last_name" in data:
                        data["username"] = f"{data['first_name']}.{data['last_name']}".lower()

                    data["status"] = "NEW"
                    data["created_by"] = request.user.id

                data["updated_by"] = request.user.id

                # ----------- Serializer -----------
                serializer = UserSerializer(
                    instance=instance,
                    data=data,
                    partial=is_update,
                    context={"request": request}
                )

                if not serializer.is_valid():
                    return CustomResponse.errors(
                        message="Validation failed",
                        data=serializer.errors
                    )
                user = serializer.save()
                # ----------- Set password on creation -----------
                print(is_update)
                if not is_update:
                    password = data.get("check_number", "")
                    user.set_password(password)
                    user.save(update_fields=["password"])

                # Create audit log for user create/update
                try:
                    from ppaa_portal.views import create_audit_log
                    action = "CREATE" if not is_update else "UPDATE"
                    create_audit_log(
                        request=request,
                        action=action,
                        model_name="User",
                        obj=user,
                        changes=serializer.data if is_update else None
                    )
                except Exception:
                    # Don't fail the request if audit log creation fails
                    pass

                return CustomResponse.success(data=serializer.data)

        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to Change User: {str(e)}")

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                user = User.objects.filter(uid=uid, is_deleted=False).first()
                if not User:
                    return CustomResponse.errors(message="User Not Found or Already Deleted", )

                user.is_deleted = True
                user.deleted_at = timezone.datetime.now()
                user.deleted_by = request.user
                user.save()
                
                # Create audit log for user deletion
                try:
                    from ppaa_portal.views import create_audit_log
                    create_audit_log(
                        request=request,
                        action="DELETE",
                        model_name="User",
                        obj=user,
                        changes={"deleted_by": request.user.username}
                    )
                except Exception:
                    # Don't fail the request if audit log creation fails
                    pass
                
                return CustomResponse.success(message='User deleted successfully')

        except SystemError as e:
            print(f'Failed to Perform Action: {str(e)}')
            return CustomResponse.server_error(message="Something went wrong While Deleting User")

class UserPhotoUpload(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = FileUploadSerializer

    def post(self, request):
        try:
            with (transaction.atomic()):
                serializer = self.serializer_class(
                    instance=None,
                    data=request.data,
                    partial=False
                )

                if not serializer.is_valid():
                    return CustomResponse.errors(
                        message="Validation failed, please try again"
                            if request.data.get('uid', None)
                            else "You can't update. You must Specify User to Update Photo",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )

                try:
                    instance = User.objects.get(guid=serializer.validated_data.get('uid'))
                    if instance.is_deleted:
                        return CustomResponse.errors(message="You can't update. Deleted User")
                except User.DoesNotExist:
                    return CustomResponse.errors(message="You can't update. You must Specify User to Update Photo")

                photo_base64 = serializer.validated_data.get('based64_file', '')
                minio = MinioStorage()
                file_name = instance.guid
                photo_url = minio.upload_base64_file(
                    photo_base64,
                    folder="user_photos",
                    file_name=file_name,
                    old_file_path=instance.photo
                )
                instance.photo = photo_url
                # User.updated_by is an IntegerField in ppaa_auth.models.User
                instance.updated_by = request.user.id
                instance.updated_at = timezone.now()
                instance.save(update_fields=["photo",'updated_by','updated_at'])
                
                # Create audit log for photo upload
                try:
                    from ppaa_portal.views import create_audit_log
                    create_audit_log(
                        request=request,
                        action="UPDATE",
                        model_name="UserPhoto",
                        obj=instance,
                        changes={"photo_updated": True, "photo_url": photo_url}
                    )
                except Exception:
                    # Don't fail the request if audit log creation fails
                    pass
                
                user_serializer = UserSerializer(instance)
                return CustomResponse.success(data=user_serializer.data)

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Change User Photo: {str(e)}', )

class UserSignatureUpload(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = FileUploadSerializer

    def post(self, request):
        try:
            with (transaction.atomic()):
                serializer = self.serializer_class(
                    instance=None,
                    data=request.data,
                    partial=False
                )

                if not serializer.is_valid():
                    return CustomResponse.errors(
                        message="Validation failed, please try again"
                            if request.data.get('uid', None)
                            else "You can't update. You must Specify User to Update Photo",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )

                try:
                    instance = User.objects.get(guid=serializer.validated_data.get('uid'))
                    if instance.is_deleted:
                        return CustomResponse.errors(message="You can't update. Deleted User")
                except User.DoesNotExist:
                    return CustomResponse.errors(message="You can't update. You must Specify User to Update Signature")

                file_base64 = serializer.validated_data.get('based64_file', '')
                minio = MinioStorage()
                file_name = instance.guid
                file_url = minio.upload_base64_file(
                    file_base64,
                    folder="user_signatures",
                    file_name=file_name,
                    old_file_path=instance.signature
                )
                instance.signature = file_url
                # User.updated_by is an IntegerField in ppaa_auth.models.User
                instance.updated_by = request.user.id
                instance.updated_at = timezone.now()
                instance.save(update_fields=["signature",'updated_by','updated_at'])
                
                # Create audit log for signature upload
                try:
                    from ppaa_portal.views import create_audit_log
                    create_audit_log(
                        request=request,
                        action="UPDATE",
                        model_name="UserSignature",
                        obj=instance,
                        changes={"signature_updated": True, "signature_url": file_url}
                    )
                except Exception:
                    # Don't fail the request if audit log creation fails
                    pass
                
                user_serializer = UserSerializer(instance)
                return CustomResponse.success(data=user_serializer.data)

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Change User signature: {str(e)}', )