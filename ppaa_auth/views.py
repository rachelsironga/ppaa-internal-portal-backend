import random
import secrets
import string
from datetime import datetime

from django.conf import settings as django_settings
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import DepartmentSerializer
from api.utils import send_custom_email
from ppaa_auth.models import Department, User
from ppaa_auth.serializers import (
    ForgotPasswordSerializer,
    LoginSerializer,
    NewUserLoginSerializer,
    PasswordChangeSerializer,
    PasswordNewChangeSerializer,
    UpdateProfileSerializer,
    RegistrationSerializer,
    UserSerializer,
)
from ppaa_auth.utils import MyTokenObtainPairSerializer
from ppaa_portal.models import audit_department_for_user, portal_client_ip, record_audit_log
from ppaa_portal.pagination import CustomPagination
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


def generate_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def _new_user_initial_secret_valid(user: User, raw: str) -> bool:
    """True if ``raw`` matches the user's current password or check number (first-time login)."""
    candidate = (raw or "").strip()
    if not candidate:
        return False
    if user.check_password(candidate):
        return True
    check = (user.check_number or "").strip()
    if not check:
        return False
    if len(candidate) != len(check):
        return False
    return secrets.compare_digest(candidate, check)


class RegistrationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = RegistrationSerializer

    def post(self, request):
        try:
            with transaction.atomic():
                reg_serializer = self.serializer_class(data=request.data)
                if not reg_serializer.is_valid():
                    return Response(
                        {
                            "status": status.HTTP_401_UNAUTHORIZED,
                            "message": "Please Provide Valid Credentials",
                            "data": reg_serializer.errors,
                        },
                        status=status.HTTP_401_UNAUTHORIZED,
                    )

                if User.objects.filter(
                    username__iexact=request.data.get("username", "")
                ).exists():
                    return Response(
                        {"status": status.HTTP_208_ALREADY_REPORTED, "message": "email already exist", "data": []},
                        status=status.HTTP_208_ALREADY_REPORTED,
                    )

                reg_user = reg_serializer.save()

                email = request.data.get("email")
                password = request.data.get("password")
                user = authenticate(request, email=email, password=password)
                if user is None:
                    raise Exception("Can not login user. Registration Failed")
                login(
                    request,
                    user,
                    backend=getattr(user, "backend", None)
                    or django_settings.AUTHENTICATION_BACKENDS[0],
                )
                auth_data = MyTokenObtainPairSerializer.get_tokens_for_user(request)
                login_serializer = RegistrationSerializer(user)
                body = {**auth_data, "user": login_serializer.data}
                return Response(body, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {
                    "status": status.HTTP_400_BAD_REQUEST,
                    "message": "ppaa_auth failed",
                    "error": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = LoginSerializer

    def post(self, request):
        try:
            login_serializer = self.serializer_class(data=request.data)
            if not login_serializer.is_valid():
                return CustomResponse.errors(
                    message="Please Provide Valid Credentials",
                    data=login_serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

            username = request.data["username"]
            password = request.data["password"]
            user = User.objects.filter(username__iexact=username).first()
            if not user:
                return CustomResponse.unauthorized(
                    message="Sorry Username not Exist", data=request.data
                )

            if user.status == User.AccountStatus.NEW:
                if not _new_user_initial_secret_valid(user, password):
                    return CustomResponse.unauthorized(
                        message="Incorrect username or check number",
                        data=request.data,
                    )
                return CustomResponse.errors(
                    message="First-time login. Please change your password.",
                    code=STATUS_CODES["NEW_USER"],
                    data={
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "email": user.email,
                        "status": user.status,
                    },
                )

            user = authenticate(request, username=username, password=password)
            if user is None:
                return CustomResponse.unauthorized(
                    message="Incorrect username or password", data=request.data
                )

            login(request, user)
            auth_data = MyTokenObtainPairSerializer.get_tokens_for_user(request)
            if auth_data.get("status") != status.HTTP_200_OK:
                logout(request)
                return CustomResponse.errors(
                    message="Unable to authenticate. Please provide valid credentials"
                )

            ua = request.META.get("HTTP_USER_AGENT") or ""
            if len(ua) > 500:
                ua = ua[:500]
            department = audit_department_for_user(user)

            record_audit_log(
                user=user,
                action="LOGIN",
                model_name="User",
                object_id=str(user.guid),
                object_repr=str(user)[:200],
                ip_address=portal_client_ip(request) or None,
                user_agent=ua,
                department=department,
                created_by=user,
                updated_by=user,
            )

            merged = {
                **auth_data.get("data", {}),
                "user": UserSerializer(user).data,
            }
            return CustomResponse.success(data=merged, message="Successfully Logged In")
        except Exception as e:
            return CustomResponse.server_error(message=f"Login failed: {e!s}")


class LoginNewUser(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = NewUserLoginSerializer

    def post(self, request):
        ser = self.serializer_class(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        username = ser.validated_data["username"]
        new_password = ser.validated_data["new_password"]
        initial_password = ser.validated_data["initial_password"]
        email = ser.validated_data["email"]
        phone_number = (ser.validated_data.get("phone_number") or "").strip()

        user = User.objects.filter(
            username__iexact=username,
            status=User.AccountStatus.NEW,
            is_deleted=False,
        ).first()
        if not user:
            return CustomResponse.errors(
                message="User not found or account is already activated",
                data=None,
                code=STATUS_CODES["UNAUTHORIZED"],
            )
        if not _new_user_initial_secret_valid(user, initial_password):
            return CustomResponse.errors(
                message="Incorrect check number or verification password",
                data=None,
                code=STATUS_CODES["UNAUTHORIZED"],
            )

        user.set_password(new_password)
        user.status = User.AccountStatus.ACTIVE
        user.email = User.objects.normalize_email(email)
        user.phone_number = phone_number
        user.save(
            update_fields=["password", "status", "email", "phone_number", "updated_at"]
        )
        login(
            request,
            user,
            backend=django_settings.AUTHENTICATION_BACKENDS[0],
        )
        auth_data = MyTokenObtainPairSerializer.get_tokens_for_user(request)
        merged = {**auth_data.get("data", {}), "user": UserSerializer(user).data}
        return CustomResponse.success(data=merged, message="Password updated")


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return CustomResponse.success(message="Logged out")


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = PasswordChangeSerializer
    required_permissions = {"post": ["can_change_own_password"]}

    def post(self, request):
        ser = self.serializer_class(
            data=request.data, context={"request": request}
        )
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        request.user.set_password(ser.validated_data["new_password"])
        request.user.save(update_fields=["password", "updated_at"])
        return CustomResponse.success(message="Password changed")


class AdminChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = PasswordNewChangeSerializer
    required_permissions = {"post": ["can_change_user_password"]}

    def post(self, request):
        ser = self.serializer_class(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        uid = ser.validated_data["uid"]
        user = User.objects.filter(guid=uid, is_deleted=False).first()
        if not user:
            return CustomResponse.errors(message="User not found", data=None)
        user.set_password(ser.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        return CustomResponse.success(message="Password updated")


class ResetPasswordView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {"post": ["can_change_user_password"]}

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get("uid")
                if not uid:
                    return CustomResponse.errors(
                        message="Incorrect User Details",
                        data=None,
                        code=STATUS_CODES["VALIDATION_ERROR"],
                    )
                user_data = User.objects.filter(
                    guid=uid, is_deleted=False
                ).first()
                if not user_data:
                    return CustomResponse.errors(
                        message="Incorrect User",
                        data=None,
                        code=STATUS_CODES["DATA_NOT_FOUND"],
                    )
                password = generate_password()
                user_data.set_password(password)
                user_data.save(update_fields=["password", "updated_at"])

                ip_address = request.META.get("REMOTE_ADDR")
                ua = request.META.get("HTTP_USER_AGENT") or ""
                if len(ua) > 500:
                    ua = ua[:500]
                department = None
                try:
                    if hasattr(request.user, "get_position") and callable(
                        request.user.get_position
                    ):
                        pos = request.user.get_position() or {}
                        du = pos.get("department_uid")
                        if du:
                            department = Department.objects.filter(
                                uid=du, is_deleted=False
                            ).first()
                except Exception:
                    department = None

                record_audit_log(
                    user=request.user,
                    action="UPDATE",
                    model_name="User",
                    object_id=str(user_data.guid),
                    object_repr=str(user_data)[:200],
                    changes={
                        "action": f"Password reset by admin {request.user.username}"
                    },
                    ip_address=ip_address,
                    user_agent=ua,
                    department=department,
                    created_by=request.user,
                    updated_by=request.user,
                )

                login_link = "/"
                if hasattr(request, "build_absolute_uri"):
                    try:
                        login_link = request.build_absolute_uri("/")[:200]
                    except Exception:
                        pass
                ctx = {
                    "fullname": f"{user_data.first_name} {user_data.last_name}".strip(),
                    "username": user_data.username,
                    "password": password,
                    "year": datetime.now().year,
                    "login_link": login_link,
                }
                send_custom_email(
                    "Password Reset Email",
                    user_data.email,
                    "emails/reset_email.html",
                    ctx,
                )
                return CustomResponse.success(
                    message="Successfully. an Email sent to User Email Account."
                )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to Change Change Password: {e!s}"
            )


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        ser = ForgotPasswordSerializer(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message="Validation failed",
                data=ser.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        email = ser.validated_data["email"]
        user = User.objects.filter(email__iexact=email, is_deleted=False).first()
        if not user:
            return CustomResponse.errors(message="Unknown email", data=None)
        password = generate_password()
        user.set_password(password)
        user.save(update_fields=["password", "updated_at"])
        ctx = {
            "fullname": f"{user.first_name} {user.last_name}".strip(),
            "username": user.username,
            "password": password,
            "year": datetime.now().year,
            "login_link": "/",
        }
        try:
            send_custom_email(
                "Password Reset Email",
                user.email,
                "emails/reset_email.html",
                ctx,
            )
        except Exception as e:
            return CustomResponse.server_error(message=str(e))
        return CustomResponse.success(
            message="If the email exists, a reset message has been sent."
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


class DepartmentView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = DepartmentSerializer
    required_permissions = {
        "get": [
            "can_add_department",
            "can_view_department",
            "can_view_department_lookup",
        ],
        "post": [
            "add_department",
            "can_add_department",
            "can_delete_department",
        ],
        "delete": [
            "can_add_department",
            "can_delete_department",
        ],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                department = Department.objects.filter(uid=uid, is_deleted=False).first()
                if not department:
                    raise NotFound("Department not found")
                return CustomResponse.success(data=DepartmentSerializer(department).data)

            search_query = request.GET.get("search", "").strip()
            departments = Department.objects.filter(is_deleted=False)
            if search_query:
                departments = departments.filter(
                    Q(name__icontains=search_query)
                    | Q(code__icontains=search_query)
                )
            if departments.exists():
                return CustomPagination.paginate(
                    view_class=self, results=departments, request=request
                )
            return CustomResponse.errors(message="Department not found", data=[])
        except NotFound as e:
            return CustomResponse.errors(message=str(e), data=None)
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to Retrieve Departments: {e!s}"
            )

    def post(self, request):
        try:
            with transaction.atomic():
                puid = request.data.get("uid", None)
                if puid:
                    try:
                        instance = Department.objects.get(uid=puid)
                        serializer = self.serializer_class(
                            instance, data=request.data, partial=True
                        )
                    except Department.DoesNotExist:
                        return CustomResponse.errors(message="Department not found")
                else:
                    serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    serializer.save(
                        created_by=request.user, updated_by=request.user
                    )
                    return CustomResponse.success(data=serializer.data)
                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to Change Department: {e!s}"
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                department = Department.objects.filter(
                    uid=uid, is_deleted=False
                ).first()
                if not department:
                    return CustomResponse.errors(
                        message="Department Not Found or Deleted",
                    )
                department.is_deleted = True
                department.deleted_at = datetime.now()
                department.deleted_by = request.user
                department.save()
                return CustomResponse.success(
                    message="Department deleted successfully"
                )
        except Exception:
            return CustomResponse.server_error(
                message="Something went wrong While Deleting Department"
            )
