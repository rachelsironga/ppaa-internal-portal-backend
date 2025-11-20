from django.db import transaction

from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from mnh_auth.serializers import UserSerializer, CheckUserNameSerializer, UpdateProfileSerializer, LoginSerializer, \
    NewUserLoginSerializer, PasswordResetSerializer
from django.contrib.auth import authenticate, login, logout
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mnh_auth.models import User
from mnh_auth.serializers import RegistrationSerializer, PasswordChangeSerializer
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
                        "username" : user.username,
                        "first_name" : user.first_name,
                        "last_name" : user.last_name,
                        "email" : user.email,
                        "status" : user.status,
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
                    user = authenticate(request, username=new_user.username, password=serializer.validated_data['password'])
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

class ResetPasswordView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission ]
    serializer_class = PasswordResetSerializer
    required_permissions = {
        "post": ["can_change_user_password"],
    }

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(context={'request': request}, data=request.data)
                # Validate and save
                if serializer.is_valid():
                    # request.user.set_password(serializer.validated_data['new_password'])
                    # request.user.save()
                    return CustomResponse.success(message="Successfully. an Email sent to User Email Account.")

                # Validation failed
                return CustomResponse.errors(
                    message="Incorrect User Details",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
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
    permission_classes = [IsAuthenticated, HasMethodPermission,]
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
            return CustomResponse.server_error(message=f'Unable to Update Profile ' )
