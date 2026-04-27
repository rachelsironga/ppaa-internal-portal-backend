"""
RMS (Report Management System) access helpers and DRF permission.

Roles (Django groups, case-insensitive in checks):
- RMS_SYS_ADMIN — full RMS Django perms; financial-year maintenance; global audit; setup CRUD.
- RMS_REPORT_MANAGER — institution-wide scope; full report workflow + catalog reads; no
  stakeholder/type/category mutations; FY maintenance and global audit APIs sys-admin /
  portal-admin only.
- RMS_DEPT_REPORTER — own-department reports and department dashboard only.
"""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView

User = get_user_model()


def rms_group_names_lower(user) -> set[str]:
    if not user or not user.is_authenticated:
        return set()
    return {str(n).lower() for n in user.groups.values_list("name", flat=True)}


def rms_is_portal_admin_group(user) -> bool:
    return "admin" in rms_group_names_lower(user)


def rms_is_sys_admin_group(user) -> bool:
    g = rms_group_names_lower(user)
    return "rms_sys_admin" in g or rms_is_portal_admin_group(user)


def rms_institution_scope(user) -> bool:
    """User may see and act on reports across all departments."""
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    g = rms_group_names_lower(user)
    return "rms_sys_admin" in g or "rms_report_manager" in g or rms_is_portal_admin_group(
        user
    )


def rms_reporter_department_id(user) -> int | None:
    from ppaa_auth.models import UserProfile

    if not user or not user.is_authenticated:
        return None
    prof = (
        UserProfile.objects.filter(
            user=user, is_active=True, is_deleted=False
        )
        .order_by("-updated_at")
        .first()
    )
    return prof.department_id if prof and prof.department_id else None


def rms_reporter_department_uid(user) -> uuid.UUID | None:
    from ppaa_auth.models import UserProfile

    if not user or not user.is_authenticated:
        return None
    prof = (
        UserProfile.objects.filter(
            user=user, is_active=True, is_deleted=False
        )
        .select_related("department")
        .order_by("-updated_at")
        .first()
    )
    if not prof or not prof.department_id:
        return None
    return prof.department.uid


def rms_apply_report_queryset_scope(user, qs):
    """Restrict a RmsReport queryset to the user's department when not in institution scope."""
    if not user or not user.is_authenticated:
        return qs.none()
    if getattr(user, "is_superuser", False) or rms_institution_scope(user):
        return qs
    did = rms_reporter_department_id(user)
    if not did:
        return qs.none()
    return qs.filter(department_id=did)


def rms_user_can_access_report(user, report) -> bool:
    if not user or not user.is_authenticated or not report:
        return False
    if getattr(user, "is_superuser", False) or rms_institution_scope(user):
        return True
    did = rms_reporter_department_id(user)
    return bool(did and report.department_id == did)


def rms_user_can_access_directorate_dashboard(user, department_uid: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False) or rms_institution_scope(user):
        return True
    try:
        target = uuid.UUID(str(department_uid).strip())
    except (ValueError, TypeError):
        return False
    own = rms_reporter_department_uid(user)
    return bool(own and own == target)


def rms_financial_setup_allowed(user) -> bool:
    """Create/update/delete SPISM financial years bridged under RMS URLs."""
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    return rms_is_sys_admin_group(user)


class RmsPermission(BasePermission):
    """
    Class-level permission using Django model permission codenames.

    On each view set either:
    - rms_perm_map: e.g. {"GET": ("view_rmsreport",), "POST": ("add_rmsreport",)}
    - rms_requires_sys_admin: True for FY maintenance and global RMS audit (RMS_SYS_ADMIN / admin / superuser)
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True

        if getattr(view, "rms_requires_sys_admin", False):
            return rms_financial_setup_allowed(user)

        method = (request.method or "GET").upper()
        if method == "OPTIONS":
            return True

        pmap = getattr(view, "rms_perm_map", None) or {}
        needed = pmap.get(method)
        if needed is None and method == "PATCH":
            needed = pmap.get("PUT")
        if needed is None and method == "HEAD":
            needed = pmap.get("GET")
        if not needed:
            return False

        codes = set(user.get_permission_codes())
        return any(p in codes for p in needed)


class RmsProtectedAPIView(APIView):
    """Base for RMS HTTP endpoints: session/JWT auth + `RmsPermission` (codename map on subclass)."""

    permission_classes = [IsAuthenticated, RmsPermission]
