from rest_framework.fields import empty
from rest_framework.permissions import BasePermission, SAFE_METHODS

from mnh_approval.response_codes import CustomResponse


class HasMethodPermission(BasePermission):
    """
    Checks permissions defined in `required_permissions` dict on the view:
    {
        "get": ["perm1", "perm2"],
        "post": ["perm3"]
    }
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # return true if user is super_user
        if request.user.is_superuser:
            return True

        required_perms_map = getattr(view, "required_permissions", {})
        method = request.method.lower()
        required_perms = required_perms_map.get(method, [])

        if not required_perms:
            # If no permissions required for this method, allow
            return True

        user_permissions = request.user.get_permission_codes()

        # Require *all* permissions
        return all(perm in user_permissions for perm in required_perms)
