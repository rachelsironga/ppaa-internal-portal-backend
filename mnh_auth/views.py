import random
import string

from django.db import transaction
from django.utils import timezone

from api.utils import send_custom_email
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.serializers import UserSerializer, CheckUserNameSerializer, UpdateProfileSerializer, LoginSerializer, \
    NewUserLoginSerializer, PasswordResetSerializer, PasswordNewChangeSerializer, CountrySerializer, CurrencySerializer
from django.contrib.auth import authenticate, login, logout
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mnh_auth.models import User, Country, Currency, Department, Directory
from mnh_auth.serializers import RegistrationSerializer, PasswordChangeSerializer, DepartmentSerializer, DirectorySerializer
from mnh_auth.utils import MyTokenObtainPairSerializer
from utils.permissions import HasMethodPermission


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
            return Response({'status': status.HTTP_400_BAD_REQUEST, 'message': "mnh_auth failed", 'error': str(e)},
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
                if password != user.pf_number:
                    return CustomResponse.errors(
                        message="For first-time login, password must be your PF-number",
                        code=STATUS_CODES['VALIDATION_ERROR']
                    )
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
                    serializer_instance.save(updated_by=request.user)
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


class CountriesView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = CountrySerializer
    required_permissions = {
        "get": ["view_country"],
        "post": ["add_country"],
        "put": ["change_country"],
        "delete": ["delete_country"],
    }

    def get(self, request, uid=None):
        """Get all countries or a specific country by uid"""
        try:
            if uid:
                country = Country.objects.filter(uid=uid, is_deleted=False).first()
                if not country:
                    return CustomResponse.error(
                        message="Country not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                serializer = self.serializer_class(country)
                return CustomResponse.success(
                    message="Country retrieved successfully",
                    data=serializer.data
                )
            else:
                countries = Country.objects.filter(is_deleted=False).order_by('name')
                serializer = self.serializer_class(countries, many=True)
                return CustomResponse.success(
                    message="Countries retrieved successfully",
                    data=serializer.data
                )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to retrieve countries: {str(e)}"
            )

    def post(self, request):
        """Create a new country"""
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    country = serializer.save(
                        created_by=request.user,
                        updated_by=request.user
                    )
                    return CustomResponse.success(
                        message="Country created successfully",
                        data=CountrySerializer(country).data,
                        code=STATUS_CODES.get("CREATED", 201)
                    )
                else:
                    return CustomResponse.error(
                        message="Validation failed",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to create country: {str(e)}"
            )

    def put(self, request, uid=None):
        """Update an existing country"""
        try:
            with transaction.atomic():
                if not uid:
                    return CustomResponse.error(
                        message="Country uid is required",
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )

                country = Country.objects.filter(uid=uid, is_deleted=False).first()
                if not country:
                    return CustomResponse.error(
                        message="Country not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )

                serializer = self.serializer_class(country, data=request.data, partial=True)
                if serializer.is_valid():
                    country = serializer.save(updated_by=request.user)
                    return CustomResponse.success(
                        message="Country updated successfully",
                        data=CountrySerializer(country).data
                    )
                else:
                    return CustomResponse.error(
                        message="Validation failed",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to update country: {str(e)}"
            )

    def delete(self, request, uid=None):
        """Soft delete a country"""
        try:
            with transaction.atomic():
                if not uid:
                    return CustomResponse.error(
                        message="Country uid is required",
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )

                country = Country.objects.filter(uid=uid, is_deleted=False).first()
                if not country:
                    return CustomResponse.error(
                        message="Country not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )

                # Soft delete
                country.is_deleted = True
                country.deleted_by = request.user
                country.deleted_at = timezone.now()
                country.save()

                return CustomResponse.success(
                    message="Country deleted successfully"
                )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to delete country: {str(e)}"
            )

class CurrenciesView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = CurrencySerializer
    required_permissions = {
        "get": ["view_currency"],
        "post": ["add_currency"],
        "put": ["change_currency"],
        "delete": ["delete_currency"],
    }

    def get(self, request, uid=None):
        """Get all currencies or a specific currency by uid"""
        try:
            if uid:
                currency = Currency.objects.filter(uid=uid, is_deleted=False).first()
                if not currency:
                    return CustomResponse.error(
                        message="Currency not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                serializer = self.serializer_class(currency)
                return CustomResponse.success(
                    message="Currency retrieved successfully",
                    data=serializer.data
                )
            else:
                currencies = Currency.objects.filter(is_deleted=False).order_by('name')
                serializer = self.serializer_class(currencies, many=True)
                return CustomResponse.success(
                    message="Currencies retrieved successfully",
                    data=serializer.data
                )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to retrieve currencies: {str(e)}"
            )

    def post(self, request):
        """Create a new currency"""
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    currency = serializer.save(
                        created_by=request.user,
                        updated_by=request.user
                    )
                    return CustomResponse.success(
                        message="Currency created successfully",
                        data=CurrencySerializer(currency).data,
                        code=STATUS_CODES.get("CREATED", 201)
                    )
                else:
                    return CustomResponse.error(
                        message="Validation failed",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to create currency: {str(e)}"
            )

    def put(self, request, uid=None):
        """Update an existing currency"""
        try:
            with transaction.atomic():
                if not uid:
                    return CustomResponse.error(
                        message="Currency uid is required",
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )

                currency = Currency.objects.filter(uid=uid, is_deleted=False).first()
                if not currency:
                    return CustomResponse.error(
                        message="Currency not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )

                serializer = self.serializer_class(currency, data=request.data, partial=True)
                if serializer.is_valid():
                    currency = serializer.save(updated_by=request.user)
                    return CustomResponse.success(
                        message="Currency updated successfully",
                        data=CurrencySerializer(currency).data
                    )
                else:
                    return CustomResponse.error(
                        message="Validation failed",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to update currency: {str(e)}"
            )

    def delete(self, request, uid=None):
        """Soft delete a currency"""
        try:
            with transaction.atomic():
                if not uid:
                    return CustomResponse.error(
                        message="Currency uid is required",
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )

                currency = Currency.objects.filter(uid=uid, is_deleted=False).first()
                if not currency:
                    return CustomResponse.error(
                        message="Currency not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )

                # Soft delete
                currency.is_deleted = True
                currency.deleted_by = request.user
                currency.deleted_at = timezone.now()
                currency.save()

                return CustomResponse.success(
                    message="Currency deleted successfully"
                )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to delete currency: {str(e)}"
            )

class DirectoryView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = DirectorySerializer
    required_permissions = {
        "get": ["view_directory"],
        "post": ["add_directory"],
        "put": ["change_directory"],
        "delete": ["delete_directory"],
    }

    def get(self, request, uid=None):
        """Get all directories or a specific directory by uid"""
        try:
            if uid:
                directory = Directory.objects.filter(uid=uid, is_deleted=False).first()
                if not directory:
                    return CustomResponse.errors(
                        message="Directory not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )
                serializer = self.serializer_class(directory)
                return CustomResponse.success(
                    message="Directory retrieved successfully",
                    data=serializer.data
                )
            else:
                directories = Directory.objects.filter(is_deleted=False).order_by('name')
                serializer = self.serializer_class(directories, many=True)
                return CustomResponse.success(
                    message="Directories retrieved successfully",
                    data=serializer.data
                )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to retrieve directories: {str(e)}"
            )

    def post(self, request):
        """Create a new directory"""
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    directory = serializer.save(
                        created_by=request.user,
                        updated_by=request.user
                    )
                    return CustomResponse.success(
                        message="Directory created successfully",
                        data=DirectorySerializer(directory).data,
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
                message=f"Failed to create directory: {str(e)}"
            )

    def put(self, request, uid=None):
        """Update an existing directory"""
        try:
            with transaction.atomic():
                if not uid:
                    return CustomResponse.errors(
                        message="Directory uid is required",
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )

                directory = Directory.objects.filter(uid=uid, is_deleted=False).first()
                if not directory:
                    return CustomResponse.errors(
                        message="Directory not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )

                serializer = self.serializer_class(directory, data=request.data, partial=True)
                if serializer.is_valid():
                    directory = serializer.save(updated_by=request.user)
                    return CustomResponse.success(
                        message="Directory updated successfully",
                        data=DirectorySerializer(directory).data
                    )
                else:
                    return CustomResponse.errors(
                        message="Validation failed",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to update directory: {str(e)}"
            )

    def delete(self, request, uid=None):
        """Soft delete a directory"""
        try:
            with transaction.atomic():
                if not uid:
                    return CustomResponse.errors(
                        message="Directory uid is required",
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )

                directory = Directory.objects.filter(uid=uid, is_deleted=False).first()
                if not directory:
                    return CustomResponse.errors(
                        message="Directory not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )

                # Soft delete
                directory.is_deleted = True
                directory.deleted_by = request.user
                directory.deleted_at = timezone.now()
                directory.save()

                return CustomResponse.success(
                    message="Directory deleted successfully"
                )
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to delete directory: {str(e)}"
            )

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
                # Optional: filter by directory if provided
                directory_uid = request.query_params.get('directory_uid')
                query = Department.objects.filter(is_deleted=False).select_related('directory')

                if directory_uid:
                    query = query.filter(directory__uid=directory_uid)

                departments = query.order_by('name')
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
                    # Validate directory exists
                    directory_uid = request.data.get('directory')
                    if not directory_uid:
                        return CustomResponse.errors(
                            message="Directory is required",
                            code=STATUS_CODES["VALIDATION_ERROR"]
                        )

                    directory = Directory.objects.filter(uid=directory_uid, is_deleted=False).first()
                    if not directory:
                        return CustomResponse.errors(
                            message="Directory not found",
                            code=STATUS_CODES["DATA_NOT_FOUND"]
                        )

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

