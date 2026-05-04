"""
Log authenticated mutating API requests to ``AuditLog`` for System Logs.

Aligned with Report Management audit style: real client IP, department from ``UserProfile``,
semantic HTTP method as ``action`` (not ``POST_200``), status in ``changes``.

Skips token refresh, login, and ``/api/system/*`` (explicit ``create_audit_log`` there).
"""

from django.utils.deprecation import MiddlewareMixin

from ppaa_portal.models import audit_department_for_user, portal_client_ip, record_audit_log
from ppaa_portal.portal_audit_utils import (
    extract_request_data_highlight,
    summarize_internal_portal_request,
)


class ApiActivityAuditMiddleware(MiddlewareMixin):
    """One row per POST/PUT/PATCH/DELETE under ``/api/`` for traceability."""

    SKIP_PREFIXES = (
        "/api/token",
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/password",
        "/api/auth/users",
        "/api/system/",
        "/api/internal-portal/audit-logs",
    )

    def process_response(self, request, response):
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return response
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return response
        path = request.path or ""
        if not path.startswith("/api/"):
            return response
        if any(path.startswith(p) for p in self.SKIP_PREFIXES):
            return response

        try:
            status_code = getattr(response, "status_code", None)
            method = request.method
            data_highlight = extract_request_data_highlight(request)
            human = summarize_internal_portal_request(method, path, data_highlight)
            # Human-first copy for System Logs (RMS-style); raw path kept only inside ``changes``.
            record_audit_log(
                user=user,
                action=method[:64],
                model_name="ApiActivity",
                object_id=path[:255],
                object_repr=(human.get("summary_title") or f"{method} {path}")[:255],
                changes={
                    "method": method,
                    "path": path,
                    "http_status": status_code,
                    "data_highlight": data_highlight or None,
                    **human,
                },
                ip_address=portal_client_ip(request) or None,
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:500],
                department=audit_department_for_user(user),
                created_by=user,
                updated_by=user,
            )
        except Exception:
            pass
        return response
