from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_portal.pagination import CustomPagination
from utils.permissions import HasMethodPermission
from ppaa_auth.models import Department, UserProfile

# PPAA auth does not expose a separate Directory model; reuse Department.
Directory = Department

from ..serializers import DirectorySerializer, DepartmentSerializer


class DirectoryView(APIView):
    """API view for Directory (Directorate) management"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_report"],
    }
    serializer_class = DirectorySerializer

    def get(self, request, uid=None):
        """Get directory(s)"""
        try:
            if uid:
                directory = Directory.objects.filter(
                    uid=uid, is_deleted=False
                ).first()
                
                if not directory:
                    return CustomResponse.errors(
                        message="Directory not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                serializer = DirectorySerializer(directory)
                return CustomResponse.success(
                    data=serializer.data,
                    message="Directory retrieved successfully"
                )

            queryset = Directory.objects.filter(
                is_deleted=False, is_active=True
            ).order_by('name')

            search = request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) | Q(code__icontains=search)
                )

            if request.query_params.get('paginated', 'false').lower() == 'true':
                return CustomPagination.paginate(
                    view_class=self,
                    results=queryset,
                    request=request
                )

            serializer = DirectorySerializer(queryset, many=True)
            return CustomResponse.success(
                data=serializer.data,
                message="Directories retrieved successfully"
            )

        except Exception as e: 
            return CustomResponse.errors(
                message=f"Failed to retrieve Directories: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class DepartmentView(APIView):
    """API view for Department (Unit) management"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_report"],
    }
    serializer_class = DepartmentSerializer

    def get(self, request, uid=None, directory_uid=None):
        """Get department(s)"""
        try:
            if uid:
                department = Department.objects.filter(
                    uid=uid, is_deleted=False
                ).first()
                
                if not department:
                    return CustomResponse.errors(
                        message="Department not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                serializer = DepartmentSerializer(department)
                return CustomResponse.success(
                    data=serializer.data,
                    message="Department retrieved successfully"
                )

            queryset = Department.objects.filter(
                is_deleted=False, is_active=True
            ).order_by('name')

            # Filter by directory
            if directory_uid:
                queryset = queryset.filter(uid=directory_uid)

            search = request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) | Q(code__icontains=search)
                )

            if request.query_params.get('paginated', 'false').lower() == 'true':
                return CustomPagination.paginate(
                    view_class=self,
                    results=queryset,
                    request=request
                )

            serializer = DepartmentSerializer(queryset, many=True)
            return CustomResponse.success(
                data=serializer.data,
                message="Departments retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve Departments: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )


class UserProfileInfoView(APIView):
    """API view to get current user's profile info for report creation"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["view_report"],
    }

    def get(self, request):
        """Get current user's directory and department info"""
        try:
            user = request.user
            profile = UserProfile.objects.filter(
                user=user,
                is_active=True,
                is_deleted=False
            ).select_related('department', 'level').first()

            if not profile:
                return CustomResponse.errors(
                    message="No active profile found for this user",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            data = {
                'user': {
                    'uid': str(user.guid) if hasattr(user, 'guid') else str(user.id),
                    'full_name': user.get_full_name(),
                    'email': user.email,
                    'pf_number': getattr(user, 'pf_number', None),
                },
                'directory': {
                    'uid': str(profile.department.uid),
                    'name': profile.department.name,
                    'code': profile.department.code,
                } if profile.department else None,
                'department': {
                    'uid': str(profile.department.uid),
                    'name': profile.department.name,
                    'code': profile.department.code,
                } if profile.department else None,
                'level': {
                    'uid': str(profile.level.uid),
                    'name': profile.level.name,
                    'code': profile.level.code,
                } if profile.level else None,
                'is_active': profile.is_active,
            }

            return CustomResponse.success(
                data=data,
                message="User profile info retrieved successfully"
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve user profile info: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )
