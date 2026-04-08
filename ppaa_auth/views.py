import random
import string

from django.db import transaction
from django.utils import timezone

from api.utils import send_custom_email
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_auth.serializers import UserSerializer, CheckUserNameSerializer, UpdateProfileSerializer, LoginSerializer, \
    NewUserLoginSerializer, PasswordResetSerializer, PasswordNewChangeSerializer, ForgotPasswordSerializer
from django.contrib.auth import authenticate, login, logout
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from ppaa_auth.models import User, Department
from ppaa_auth.serializers import RegistrationSerializer, PasswordChangeSerializer, DepartmentSerializer
from ppaa_auth.utils import MyTokenObtainPairSerializer
from utils.permissions import HasMethodPermission
from ppaa_portal.models import AuditLog


class RegistrationView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegistrationSerializer

    def post(self, request):
        try:
            with transaction.atomic():
                reg_serializer = self.serializer_class(data=request.data)

                if reg_serializer.is_valid():
                    if User.objects.filter(username=request.data['username']).exists():
                        return Response(
                            {'status': status.HTTP_208_ALREADY_REPORTED, 'message': {"email": "email already exist"},
                             'data': []},
                            status=status.HTTP_208_ALREADY_REPORTED)

                    reg_user = reg_serializer.save()

                    # Extract account details
                    account_name = request.data.get('account_name', reg_user.email)
                    account_type = request.data.get('account_type', 'individual')

                    email = request.data['email']
                    password = request.data['password']
                    user = authenticate(request, email=email, password=password)
                    if user is not None:
                        login(request, user)
                        auth_data = MyTokenObtainPairSerializer.get_tokens_for_user(request)
                        login_serializer = RegistrationSerializer(user)
                        return Response({**auth_data,
                                         'user': login_serializer.data},
                                        status=status.HTTP_200_OK
                                        )
                    else:
                        raise Exception("Can not login user. Registration Failed")
                else:
                    return Response({'status': status.HTTP_401_UNAUTHORIZED, 'message': reg_serializer.errors},
                                    status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': "ppaa_auth failed", 'error': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        login_serializer = self.serializer_class(data=request.data)
        if not login_serializer.is_valid():
            return CustomResponse.errors(
                message="Please Provide Valid Credentials",
                data=login_serializer.errors,
                code=STATUS_CODES['VALIDATION_ERROR']
            )

        username = request.data['username']
        password = request.data['password']

        try:
            # Check if user exists
            user = User.objects.filter(username=username).first()
            if not user:
                return CustomResponse.unauthorized(
                    message="Sorry Username not Exist",
                    data=request.data,
                )

            # Handle NEW user login
            if user.status == "NEW":
                # Create payload for user Identification message
                return CustomResponse.errors(
                    message="First-time login. Please change your password.",
                    code=STATUS_CODES['NEW_USER'],
                    data={
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "email": user.email,
                        "status": user.status,
                    }
                )

            # Normal login for existing users
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                auth_data = MyTokenObtainPairSerializer.get_tokens_for_user(request)
                if auth_data['status'] != status.HTTP_200_OK:
                    logout(request)
                    return CustomResponse.errors(
                        message="Unable to authenticate. Please provide valid credentials",
                    )
                
                # Log login action
                try:
                    ip_address = request.META.get("REMOTE_ADDR")
                    user_agent = request.META.get("HTTP_USER_AGENT", "")[:500] if request.META.get("HTTP_USER_AGENT") else ""
                    department = None
                    try:
                        if hasattr(user, "get_position") and callable(user.get_position):
                            position = user.get_position() or {}
                            dept_uid = position.get("department_uid")
                            if dept_uid:
                                department = Department.objects.filter(uid=dept_uid, is_deleted=False).first()
                    except Exception:
                        department = None
                    
                    AuditLog.objects.create(
                        user=user,
                        action="LOGIN",
                        model_name="User",
                        object_id=user.guid,
                        object_repr=str(user)[:200],
                        ip_address=ip_address,
                        user_agent=user_agent,
                        department=department,
                        created_by=user,
                        updated_by=user,
                    )
                except Exception:
                    pass  # Never interrupt login flow
                
                return CustomResponse.success(
                    data={**auth_data['data'], 'user': UserSerializer(user).data},
                    message="Successfully Logged In",
                )

            return CustomResponse.unauthorized(
                message='Incorrect username or password',
                data=request.data,
            )

        except Exception as e:
            return CustomResponse.server_error(
                message=f"Login failed: {str(e)}"
            )


class LoginNewUser(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = NewUserLoginSerializer

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data)

                if serializer.is_valid():
                    new_user = serializer.save()
                    user = authenticate(request, username=new_user.username,
                                        password=serializer.validated_data['password'])
                    if user is not None:
                        login(request, user)
                        auth_data = MyTokenObtainPairSerializer.get_tokens_for_user(request)
                        if auth_data['status'] != status.HTTP_200_OK:
                            logout(request)
                            return CustomResponse.errors(
                                message="Unable to authenticate. Please provide valid Details",
                            )
                        return CustomResponse.success(
                            data={**auth_data['data'], 'user': UserSerializer(user).data},
                            message="Successfully Logged In",
                        )
                else:
                    return CustomResponse.errors(
                        message="Validation Failed",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Login failed: {str(e)}"
            )


class LogoutView(APIView):
    def post(self, request):
        # Log logout action before logging out
        try:
            user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
            if user:
                ip_address = request.META.get("REMOTE_ADDR")
                user_agent = request.META.get("HTTP_USER_AGENT", "")[:500] if request.META.get("HTTP_USER_AGENT") else ""
                department = None
                try:
                    if hasattr(user, "get_position") and callable(user.get_position):
                        position = user.get_position() or {}
                        dept_uid = position.get("department_uid")
                        if dept_uid:
                            department = Department.objects.filter(uid=dept_uid, is_deleted=False).first()
                except Exception:
                    department = None
                
                AuditLog.objects.create(
                    user=user,
                    action="LOGOUT",
                    model_name="User",
                    object_id=user.guid,
                    object_repr=str(user)[:200],
                    ip_address=ip_address,
                    user_agent=user_agent,
                    department=department,
                    created_by=user,
                    updated_by=user,
                )
        except Exception:
            pass  # Never interrupt logout flow
        
        logout(request)
        return Response({'msg': 'Successfully Logged out'}, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission, ]
    serializer_class = PasswordChangeSerializer
    required_permissions = {
        "post": ["can_change_own_password"],
    }

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(context={'request': request}, data=request.data)
                # Validate and save
                if serializer.is_valid():
                    request.user.set_password(serializer.validated_data['new_password'])
                    request.user.save()
                    
                    # Log password change action
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
                            action="UPDATE",
                            model_name="User",
                            object_id=request.user.guid,
                            object_repr=str(request.user)[:200],
                            changes={"action": "Password changed"},
                            ip_address=ip_address,
                            user_agent=user_agent,
                            department=department,
                            created_by=request.user,
                            updated_by=request.user,
                        )
                    except Exception:
                        pass
                    
                    return CustomResponse.success(data=UserSerializer(request.user).data)

                # Validation failed
                return CustomResponse.errors(
                    message="Incorrect Current Password",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to Change Change Password: {str(e)}"
            )


class AdminChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission, ]
    serializer_class = PasswordNewChangeSerializer
    required_permissions = {
        "post": ["can_change_user_password"],
    }

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(context={'request': request}, data=request.data)
                # Validate and save
                if serializer.is_valid():
                    user = serializer.validated_data['user']
                    user.set_password(serializer.validated_data['new_password'])
                    user.save()
                    
                    # Log admin password change action
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
                            action="UPDATE",
                            model_name="User",
                            object_id=user.guid,
                            object_repr=str(user)[:200],
                            changes={"action": f"Password changed by admin {request.user.username}"},
                            ip_address=ip_address,
                            user_agent=user_agent,
                            department=department,
                            created_by=request.user,
                            updated_by=request.user,
                        )
                    except Exception:
                        pass
                    
                    return CustomResponse.success(data=UserSerializer(request.user).data)

                # Validation failed
                return CustomResponse.errors(
                    message="validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to Change Change Password: {str(e)}"
            )

class ResetPasswordView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "post": ["can_change_user_password"],
    }

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                if uid is None:
                    return CustomResponse.errors(
                        message="Incorrect User Details",
                        data=None,
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )
                user_data = User.objects.filter(guid=uid, is_deleted=False).first()
                if user_data is None:
                    return CustomResponse.errors(
                        message="Incorrect User",
                        data=None,
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )

                password = generate_password()
                user_data.set_password(password)
                user_data.save(update_fields=["password"])

                # Log password reset action
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
                        action="UPDATE",
                        model_name="User",
                        object_id=user_data.guid,
                        object_repr=str(user_data)[:200],
                        changes={"action": f"Password reset by admin {request.user.username}"},
                        ip_address=ip_address,
                        user_agent=user_agent,
                        department=department,
                        created_by=request.user,
                        updated_by=request.user,
                    )
                except Exception:
                    pass

                data = {
                    "fullname": f'{user_data.first_name} {user_data.last_name}',
                    "username": user_data.username,
                    "password": password,
                    "year": timezone.now().year,
                    "login_link": "http://192.168.10.166:8091/auth/login"
                }

                print(f"----------------->{user_data.email}")

                send_custom_email(to_email=f"{user_data.email}", template_name="emails/reset_email.html",
                                  subject="Password Reset Email", context=data)
                return CustomResponse.success(message="Successfully. an Email sent to User Email Account.")

        except Exception as e:

            print(f"{e}")
            return CustomResponse.server_error(
                message=f"Failed to Change Change Password: {str(e)}"
            )


class ForgotPasswordView(APIView):
    """Allow users to request password reset via email (unauthenticated)"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            serializer = ForgotPasswordSerializer(data=request.data)
            if not serializer.is_valid():
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            email = serializer.validated_data['email']
            user = User.objects.filter(email=email, is_deleted=False).first()

            if not user:
                # Don't reveal if user exists or not for security
                return CustomResponse.success(
                    message="If an account exists with this email, a password reset link has been sent."
                )

            # Generate new password
            password = generate_password()
            user.set_password(password)
            user.save(update_fields=["password"])

            # Prepare email context (login_link must point to frontend app, not backend)
            frontend_url = getattr(settings, "FRONTEND_URL", "http://127.0.0.1:3000").rstrip("/")
            data = {
                "fullname": f'{user.first_name} {user.last_name}',
                "username": user.username,
                "password": password,
                "year": timezone.now().year,
                "login_link": f"{frontend_url}/auth/login",
            }

            # Send password reset email (does not raise; returns dict with status)
            result = send_custom_email(
                subject="Password Reset Email",
                to_email=user.email,
                template_name="emails/reset_email.html",
                context=data,
            )
            if isinstance(result, dict) and result.get("status") == "failed":
                import logging
                logging.getLogger(__name__).warning(
                    "Password reset email could not be sent to %s: %s. Check Celery/SMTP and EMAIL_* settings.",
                    user.email,
                    result.get("reason", "unknown"),
                )
            # Always return same success message (no email enumeration)
            return CustomResponse.success(
                message="If an account exists with this email, a password reset email has been sent."
            )

        except Exception as e:
            print(f"Forgot password error: {e}")
            return CustomResponse.server_error(
                message="Failed to process password reset request. Please try again later."
            )


class CheckUserExistence(APIView):
    def get(self, request):
        serializer = CheckUserNameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        check = User.objects.filter(user_auth=request.data['username']).first()
        if check:
            return Response({'status': status.HTTP_200_OK, 'message': 'User Exist'},
                            status=status.HTTP_200_OK)
        else:
            return Response({'status': status.HTTP_404_NOT_FOUND, 'message': 'User Not Exist'},
                            status=status.HTTP_404_NOT_FOUND)


class UpdateMyProfileView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission, ]
    serializer_class = UpdateProfileSerializer

    def put(self, request):
        try:
            with (transaction.atomic()):
                serializer_instance = self.serializer_class(request.user, data=request.data)
                if serializer_instance.is_valid():
                    old_data = UserSerializer(request.user, context={'request': request}).data
                    serializer_instance.save(updated_by=request.user)
                    
                    # Log profile update action
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
                            action="UPDATE",
                            model_name="User",
                            object_id=request.user.guid,
                            object_repr=str(request.user)[:200],
                            changes={
                                "before": old_data,
                                "after": serializer_instance.validated_data,
                            },
                            ip_address=ip_address,
                            user_agent=user_agent,
                            department=department,
                            created_by=request.user,
                            updated_by=request.user,
                        )
                    except Exception:
                        pass
                    
                    # Return Updated User
                    user_serializer = UserSerializer(request.user, context={'request': request})
                    return CustomResponse.success(data=user_serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer_instance.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            print(f"Fail to Update Profile {e}")
            return CustomResponse.server_error(message=f'Unable to Update Profile ')


def generate_password(length=8):
    characters = (
            string.ascii_uppercase +
            string.ascii_lowercase +
            string.digits +
            "@#$%&*?"
    )
    return ''.join(random.choice(characters) for _ in range(length))


class DepartmentView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = DepartmentSerializer
    required_permissions = {
        "get": ["view_department", "can_view_department_lookup"],
        "post": ["add_department"],
        "put": ["change_department"],
        "delete": ["delete_department"],
    }

    def get(self, request, uid=None):
        """Get all departments or a specific department by uid"""
        try:
            if uid:
                department = Department.objects.filter(uid=uid, is_deleted=False).first()
                if not department:
                    return CustomResponse.errors(
                        message="Department not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                serializer = self.serializer_class(department)
                return CustomResponse.success(
                    message="Department retrieved successfully",
                    data=serializer.data
                )
            else:
                departments = Department.objects.filter(is_deleted=False).order_by('name')
                serializer = self.serializer_class(departments, many=True)
                return CustomResponse.success(
                    message="Departments retrieved successfully",
                    data=serializer.data
                )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to retrieve departments: {str(e)}"
            )

    def post(self, request):
        """Create a new department"""
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    department = serializer.save(
                        created_by=request.user,
                        updated_by=request.user
                    )
                    return CustomResponse.success(
                        message="Department created successfully",
                        data=DepartmentSerializer(department).data,
                        code=STATUS_CODES.get("CREATED", 201)
                    )
                else:
                    return CustomResponse.errors(
                        message="Validation failed",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to create department: {str(e)}"
            )

    def put(self, request, uid=None):
        """Update an existing department"""
        try:
            with transaction.atomic():
                if not uid:
                    return CustomResponse.errors(
                        message="Department uid is required",
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )

                department = Department.objects.filter(uid=uid, is_deleted=False).first()
                if not department:
                    return CustomResponse.errors(
                        message="Department not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )

                serializer = self.serializer_class(department, data=request.data, partial=True)
                if serializer.is_valid():
                    department = serializer.save(updated_by=request.user)
                    return CustomResponse.success(
                        message="Department updated successfully",
                        data=DepartmentSerializer(department).data
                    )
                else:
                    return CustomResponse.errors(
                        message="Validation failed",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to update department: {str(e)}"
            )

    def delete(self, request, uid=None):
        """Soft delete a department"""
        try:
            with transaction.atomic():
                if not uid:
                    return CustomResponse.errors(
                        message="Department uid is required",
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )

                department = Department.objects.filter(uid=uid, is_deleted=False).first()
                if not department:
                    return CustomResponse.errors(
                        message="Department not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )

                # Soft delete
                department.is_deleted = True
                department.deleted_by = request.user
                department.deleted_at = timezone.now()
                department.save()

                return CustomResponse.success(
                    message="Department deleted successfully"
                )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to delete department: {str(e)}"
            )

