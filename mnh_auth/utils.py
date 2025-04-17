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
            }
            
        }
    


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer