"""
SPISM REST helpers: enforce custom auth.Permission codenames (auth.can_*_spism_*).

Every ``SpismProtectedAPIView`` must declare ``spism_perm_map`` for each HTTP verb it
handles (``GET``/``POST``/``PUT``/``DELETE``/``PATCH``; ``HEAD`` may reuse ``GET``), except
``SpismAuditLogListCreateView`` which uses ``SpismAuditLogConversationPermission`` instead.
``/api/performance-dashboard/*`` views in ``views.py`` and ``spism_endpoints.py`` use this layer.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView


def spism_has_any_perm(user, *codenames: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    # Prefer DB codenames from the same source as login / HasMethodPermission so SPISM
    # checks stay aligned with ``user.user_permissions`` in the API payload; then fall back
    # to Django's has_perm for backends that only populate permission caches there.
    codes: set[str] | None = None
    codes_lower: set[str] | None = None
    if hasattr(user, "get_permission_codes"):
        try:
            raw = user.get_permission_codes()
            codes = {str(x) for x in raw}
            codes_lower = {x.lower() for x in codes}
        except Exception:
            codes = None
            codes_lower = None
    for c in codenames:
        if not c:
            continue
        want = str(c)
        if codes is not None and (
            want in codes or (codes_lower is not None and want.lower() in codes_lower)
        ):
            return True
        if user.has_perm(f"auth.{want}") or user.has_perm(want):
            return True
    return False


# Group names (lowercase) that see all SPISM targets / objectives / activities.
_SPISM_TARGET_GLOBAL_ROLES = frozenset(
    {
        "admin",
        "spism_admin",
        "spism_approver",
        "spism_planning_officer",
        "spims_planning_officer",
        "spism_planning_office",
        "spims_planning_office",
    }
)

# Department implementation leads: only data for targets where they are responsible officer.
_SPISM_DEPT_HEAD_ROLES = frozenset(
    {
        "spism_dept_head",
        "spism_contributor",  # legacy Django group name
    }
)


def spism_dept_head_targets_scope_only(user) -> bool:
    """
    True when the user should be scoped to targets (and related rows) where they are the
    ``responsible_officer``. Planning officers, approvers, SPISM admins, and superusers are not scoped.
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return False
    names: set[str] = set()
    if hasattr(user, "get_groups"):
        try:
            names = {str(x).lower() for x in user.get_groups()}
        except Exception:
            names = set()
    else:
        names = {str(g.name).lower() for g in user.groups.all()}
    if names & _SPISM_TARGET_GLOBAL_ROLES:
        return False
    if names & _SPISM_DEPT_HEAD_ROLES:
        return True
    return False


class SpismAuditLogConversationPermission(BasePermission):
    """
    Full audit trail access via ``can_view_spism_audit_log``, or scoped access when the client
    passes ``entity_type`` + ``entity_id`` (objective / target / activity) for SPISM conversation
    threads so planning and approval users are not blocked by the global audit permission.
    """

    def has_permission(self, request, view):
        method = (getattr(request, "method", None) or "GET").upper()
        if method == "OPTIONS":
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if spism_has_any_perm(user, "can_view_spism_audit_log"):
            return True

        if method == "GET":
            et = (request.GET.get("entity_type") or "").strip().lower()
            eid_raw = (request.GET.get("entity_id") or "").strip()
        else:
            et = (request.data.get("entity_type") or "").strip().lower()
            eid_raw = (request.data.get("entity_id") or "").strip()

        if not et or not eid_raw:
            return False

        if method == "GET":
            if et == "objective":
                return spism_has_any_perm(user, "can_view_spism_objective")
            if et == "target":
                return spism_has_any_perm(user, "can_view_spism_target")
            if et == "activity":
                return spism_has_any_perm(user, "can_view_spism_activity")
            return False

        if method == "POST":
            if et == "objective":
                return spism_has_any_perm(
                    user,
                    "can_edit_spism_objective",
                    "can_approve_spism_planning",
                )
            if et == "target":
                return spism_has_any_perm(
                    user,
                    "can_edit_spism_target",
                    "can_approve_spism_planning",
                )
            if et == "activity":
                return spism_has_any_perm(
                    user,
                    "can_edit_spism_activity",
                    "can_approve_spism_planning",
                    "can_approve_spism_implementation",
                )
            return False

        return False


class SpismCodenamePermission(BasePermission):
    """
    Reads ``spism_perm_map`` on the view: HTTP method (uppercase) -> tuple of codenames.
    User must have **any** of those codenames for that method (OR semantics within the tuple).

    Fail-closed: ``GET``/``POST``/``PUT``/``PATCH``/``DELETE``/``HEAD`` must appear in the map
    (``HEAD`` may inherit ``GET`` when only ``GET`` is declared). Unlisted verbs other than
    ``OPTIONS`` default to deny. Empty permission tuples deny.
    """

    def has_permission(self, request, view):
        method = (getattr(request, "method", None) or "GET").upper()
        if method == "OPTIONS":
            return True
        perm_map = getattr(view, "spism_perm_map", None) or {}
        effective = method
        if method == "HEAD" and "HEAD" not in perm_map and "GET" in perm_map:
            effective = "GET"
        if effective not in perm_map:
            if method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
                return False
            return True
        codes = perm_map[effective]
        if not codes:
            return False
        return spism_has_any_perm(request.user, *codes)


class SpismProtectedAPIView(APIView):
    """
    Subclasses set ``spism_perm_map``: HTTP method (uppercase) -> tuple of codenames.
    Uses DRF permission checks so responses go through normal dispatch/finalize (no renderer errors).
    """

    permission_classes = [IsAuthenticated, SpismCodenamePermission]
    spism_perm_map: dict[str, tuple[str, ...]] = {}
    # Explicit JSON avoids empty renderer list / negotiation edge cases with some clients.
    renderer_classes = [JSONRenderer]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        # Django calls SimpleTemplateResponse.render() on DRF Response; that requires negotiation attrs.
        if isinstance(response, Response):
            if getattr(response, "accepted_renderer", None) is None:
                response.accepted_renderer = JSONRenderer()
                response.accepted_media_type = "application/json"
            if getattr(response, "renderer_context", None) is None:
                response.renderer_context = self.get_renderer_context()
        return response
