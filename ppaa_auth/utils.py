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
