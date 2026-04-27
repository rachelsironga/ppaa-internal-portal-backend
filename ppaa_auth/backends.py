from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameModelBackend(ModelBackend):
    """Supports ``authenticate(..., username=...)`` and ``authenticate(..., email=...)``."""

    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        User = get_user_model()
        if password is None:
            return None
        if email:
            user = User.objects.filter(email__iexact=email).first()
            if user and user.check_password(password):
                return user if self.user_can_authenticate(user) else None
        if username:
            return super().authenticate(
                request, username=username, password=password, **kwargs
            )
        return None
