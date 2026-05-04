<<<<<<< HEAD
from rest_framework import status
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["guid"] = str(getattr(user, "guid", ""))
        token["username"] = user.get_username()
        return token

    @classmethod
    def get_tokens_for_user(cls, request):
        user = request.user
        if not user.is_authenticated:
            return {"status": status.HTTP_401_UNAUTHORIZED, "data": {}}
        refresh = cls.get_token(user)
        return {
            "status": status.HTTP_200_OK,
            "data": {
                "refresh_token": str(refresh),
                "access_token": str(refresh.access_token),
            },
        }


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
=======
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from datetime import timedelta

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_tokens_for_user(cls,request,message = 'User login in Success'):
        refresh = RefreshToken.for_user(request.user)
        access_token = refresh.access_token
        token_type = 'Web App Token'
        if 'App-Type' in request.headers:
            if request.headers['App-Type'] == 'mobile':
                access_token.set_exp(lifetime=timedelta(days=183))
                token_type = 'Mobile App Token'
        return {
            'status':status.HTTP_200_OK,
            'message': message,
            'data' : {
                'token_type' : token_type,
                'refresh_token': str(refresh),
                'access_token' : str(access_token),
                'guid' : request.user.guid,
                'username' : request.user.username,
            }
            
        }
    


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
