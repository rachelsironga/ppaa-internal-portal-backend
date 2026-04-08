from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from api.serializers import PositionalLevelSerializer
from ppaa_portal.pagination import CustomPagination
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_auth.models import PositionalLevel, Department
from utils.permissions import HasMethodPermission
from ppaa_portal.models import AuditLog


class PositionalLevelView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission,]
    serializer_class = PositionalLevelSerializer
    required_permissions = {
        "get": [
            "can_view_department",  # Using department permission for now, can be changed later
        ],
        "post": [
            "can_add_department",
        ],
        "delete": [
            "can_delete_department",
        ]
    }

    def get(self, request, uid=None):
        try:
            """ Retrieve a single PositionalLevel by UID or list PositionalLevels with optional search """
            if uid:
                level = PositionalLevel.objects.filter(uid=uid, is_deleted=False).first()
                if not level:
                    raise NotFound("Positional Level not found")
                
                # Log view action
                try:
                    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
                    ip_address = request.META.get("REMOTE_ADDR")
                    user_agent = request.META.get("HTTP_USER_AGENT", "")[:500] if request.META.get("HTTP_USER_AGENT") else ""
                    department = None
                    try:
                        if user and hasattr(user, "get_position") and callable(user.get_position):
                            position = user.get_position() or {}
                            dept_uid = position.get("department_uid")
                            if dept_uid:
                                department = Department.objects.filter(uid=dept_uid, is_deleted=False).first()
                    except Exception:
                        department = None
                    
                    AuditLog.objects.create(
                        user=user,
                        action="VIEW",
                        model_name="PositionalLevel",
                        object_id=level.uid,
                        object_repr=str(level)[:200],
                        ip_address=ip_address,
                        user_agent=user_agent,
                        department=department,
                        created_by=user if user else None,
                        updated_by=user if user else None,
                    )
                except Exception:
                    pass
                
                serializer = PositionalLevelSerializer(level)
                return CustomResponse.success(data=serializer.data)

            search_query = request.GET.get('search', '').strip()
            is_active = request.GET.get('is_active', None)
            
            levels = PositionalLevel.objects.filter(is_deleted=False)

            # Filter by is_active if provided
            if is_active is not None:
                is_active_bool = is_active.lower() == 'true' if isinstance(is_active, str) else bool(is_active)
                levels = levels.filter(is_active=is_active_bool)

            if search_query:
                levels = levels.filter(
                    Q(name__icontains=search_query) | Q(code__icontains=search_query)
                )

            if levels.exists():
                return CustomPagination.paginate(view_class=self, results=levels, request=request)

            return CustomResponse.errors(message="Positional Level not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Positional Levels: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)

                # Handle an Update case
                if uid:
                    try:
                        instance = PositionalLevel.objects.get(uid=uid)
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except PositionalLevel.DoesNotExist:
                        return CustomResponse.errors(message="Positional Level not found")
                else:
                    serializer = self.serializer_class(data=request.data)

                if serializer.is_valid():
                    if uid:
                        level = serializer.save(updated_by=request.user)
                        action = "UPDATE"
                    else:
                        level = serializer.save(created_by=request.user, updated_by=request.user)
                        action = "CREATE"
                    
                    # Log create/update action
                    try:
                        ip_address = request.META.get("REMOTE_ADDR")
                        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500] if request.META.get("HTTP_USER_AGENT") else ""
                        department = None
                        try:
                            if hasattr(request.user, "get_position") and callable(request.user.get_position):
                                position = request.user.get_position() or {}
                                dept_uid = position.get("department_uid")
                                if dept_uid:
                                    department = Department.objects.filter(uid=dept_uid, is_deleted=False).first()
                        except Exception:
                            department = None
                        
                        AuditLog.objects.create(
                            user=request.user,
                            action=action,
                            model_name="PositionalLevel",
                            object_id=level.uid,
                            object_repr=str(level)[:200],
                            changes={"data": serializer.data},
                            ip_address=ip_address,
                            user_agent=user_agent,
                            department=department,
                            created_by=request.user.id,
                            updated_by=request.user.id,
                        )
                    except Exception:
                        pass
                    
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Save Positional Level: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                level = PositionalLevel.objects.filter(uid=uid, is_deleted=False).first()
                if not level:
                    return CustomResponse.errors(message="Positional Level Not Found or Already Deleted", )

                level.is_deleted = True
                level.deleted_at = datetime.now()
                level.deleted_by = request.user
                level.save()
                
                # Log delete action
                try:
                    ip_address = request.META.get("REMOTE_ADDR")
                    user_agent = request.META.get("HTTP_USER_AGENT", "")[:500] if request.META.get("HTTP_USER_AGENT") else ""
                    department = None
                    try:
                        if hasattr(request.user, "get_position") and callable(request.user.get_position):
                            position = request.user.get_position() or {}
                            dept_uid = position.get("department_uid")
                            if dept_uid:
                                department = Department.objects.filter(uid=dept_uid, is_deleted=False).first()
                    except Exception:
                        department = None
                    
                    AuditLog.objects.create(
                        user=request.user,
                        action="DELETE",
                        model_name="PositionalLevel",
                        object_id=level.uid,
                        object_repr=str(level)[:200],
                        ip_address=ip_address,
                        user_agent=user_agent,
                        department=department,
                        created_by=request.user.id,
                        updated_by=request.user.id,
                    )
                except Exception:
                    pass
                
                return CustomResponse.success(message='Positional Level deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to Delete Positional Level: {str(e)}")

