"""GET all permissions grouped by app + roles (for admin UI)."""

from collections import defaultdict

from django.apps import apps as django_apps
from django.contrib.auth.models import Group, Permission
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ppaa_portal.response_codes import CustomResponse
from utils.permissions import HasMethodPermission


def _app_verbose_name(app_label: str) -> str:
    try:
        return str(django_apps.get_app_config(app_label).verbose_name)
    except LookupError:
        return app_label


def _permission_payload(p: Permission) -> dict:
    ct = p.content_type
    return {
        "id": p.id,
        "name": p.name,
        "codename": p.codename,
        "model": ct.model if ct else None,
        "content_type_id": p.content_type_id,
        "app_label": ct.app_label if ct else None,
    }


class SystemPermissionsByAppView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "get": ["can_view_system_permission", "can_view_group"],
    }

    def get(self, request):
        perms_qs = Permission.objects.select_related("content_type").order_by(
            "content_type__app_label",
            "content_type__model",
            "codename",
        )
        by_app: dict[str, list] = defaultdict(list)
        for p in perms_qs:
            by_app[p.content_type.app_label].append(_permission_payload(p))

        apps_list = [
            {
                "app_label": label,
                "app_name": _app_verbose_name(label),
                "permission_count": len(items),
                "permissions": items,
            }
            for label, items in sorted(by_app.items(), key=lambda x: x[0].lower())
        ]

        roles_out = []
        for g in (
            Group.objects.prefetch_related("permissions__content_type")
            .all()
            .order_by("name")
        ):
            role_by_app: dict[str, list] = defaultdict(list)
            for p in g.permissions.all().order_by(
                "content_type__app_label",
                "content_type__model",
                "codename",
            ):
                role_by_app[p.content_type.app_label].append(_permission_payload(p))
            roles_out.append(
                {
                    "id": g.id,
                    "name": g.name,
                    "permissions_by_app": {
                        k: role_by_app[k]
                        for k in sorted(role_by_app.keys(), key=str.lower)
                    },
                }
            )

        return CustomResponse.success(data={"apps": apps_list, "roles": roles_out})
