import datetime

from django.db import transaction
from django.db.migrations import serializer
from django.db.transaction import atomic
from drf_yasg.utils import swagger_auto_schema
from rest_framework_simplejwt.authentication import JWTAuthentication

from mnh_auth.serializers import UserSerializer, CheckUserNameSerializer, UpdateProfileSerializer, LoginSerializer
from django.contrib.auth import authenticate, login, logout
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mnh_auth.models import User, AccountSetup
from mnh_auth.serializers import RegistrationSerializer, PasswordChangeSerializer
from mnh_auth.utils import MyTokenObtainPairSerializer


class RegistrationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            with transaction.atomic():
                reg_serializer = RegistrationSerializer(data=request.data)

                if reg_serializer.is_valid():
                    print(f"--------------{request.data}-------------")
                    if User.objects.filter(email=request.data['email']).exists():
                        return Response(
                            {'status': status.HTTP_208_ALREADY_REPORTED, 'message': {"email": "email already exist"},
                             'data': []},
                            status=status.HTTP_208_ALREADY_REPORTED)


                    reg_user = reg_serializer.save()

                    # Extract account details
                    account_name = request.data.get('account_name',reg_user.email)
                    account_type = request.data.get('account_type', 'individual')

                    # Create AccountSetup
                    AccountSetup.objects.create(
                        user=reg_user,
                        name=account_name,
                        contact_person_name=reg_user.get_full_name(),
                        phone_number=reg_user.phone_number,
                        user_address=reg_user.email,
                        post_address='',
                        account_type=account_type
                    )

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

    def post(self, request):
        login_serializer = LoginSerializer(data=request.data)
        if not login_serializer.is_valid():
            return Response({'status': status.HTTP_401_UNAUTHORIZED, 'message': login_serializer.errors},
                            status=status.HTTP_401_UNAUTHORIZED)

        print(f"--------------{request.data['email']}-------------")
        print(f"--login_serializer------------{login_serializer}-------------")

        email = request.data['email']
        password = request.data['password']
        print("---------email---------",email)
        print("---------password---------",password)

        # return Response({'data': email}, status=status.HTTP_200_OK)
        user = authenticate(request, email=email, password=password)
        print("---------user---------",user)
        if user is not None:
            login(request, user)
            auth_data = MyTokenObtainPairSerializer.get_tokens_for_user(request)
            auth_serializer = RegistrationSerializer(user)
            return Response({**auth_data, 'user': auth_serializer.data}, status=status.HTTP_200_OK)
        return Response({'status': status.HTTP_401_UNAUTHORIZED, 'message': 'Incorrect email or password', },
                        status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({'msg': 'Successfully Logged out'}, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, ]

    def post(self, request):
        serializer = PasswordChangeSerializer(context={'request': request}, data=request.data)
        serializer.is_valid(raise_exception=True)  # Another way to write is as in Line 17
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response({'status': status.HTTP_200_OK, 'data': str(request.user), 'message': 'Password Changes'},
                        status=status.HTTP_200_OK)

class UserView(APIView):
    permission_classes = [IsAuthenticated, ]

    def get(self, request):
        serializer = UserSerializer(request.user, context={'request': request})
        return Response({'status': status.HTTP_200_OK, 'data': serializer.data}, status=status.HTTP_200_OK)


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
    permission_classes = [IsAuthenticated, ]
    serializer_class = UpdateProfileSerializer

    def put(self, request):
        serializer = self.serializer_class(request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'status': status.HTTP_200_OK, 'message': 'User information updated'},
                        status=status.HTTP_200_OK)