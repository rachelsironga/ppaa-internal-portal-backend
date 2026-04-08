from django.utils.deprecation import MiddlewareMixin
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.models import AnonymousUser

class TokenAuthMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Skip authentication for admin or public paths
        if request.path.startswith('/admin/') or request.path.startswith('/public/'):
            return

        auth = TokenAuthentication()
        try:
            user, _ = auth.authenticate(request)
            request.user = user
        except AuthenticationFailed:
            request.user = AnonymousUser()
