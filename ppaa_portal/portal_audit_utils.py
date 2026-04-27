"""
Internal Portal audit trail helpers (System Logs UI, aligned with RMS Audit Trail).

Normalizes legacy ``POST_200``-style actions and maps ``action_key`` filters for list/stats.
Maps API paths to human-readable titles (no raw endpoints in the UI).
"""
from __future__ import annotations

import json
import re
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from ppaa_portal.models import AuditLog

_LEGACY_HTTP = re.compile(r"^(POST|PUT|PATCH|DELETE)_(\d{3})$", re.I)
_UUID_SEG = re.compile(
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)


def normalize_api_path(path: str) -> str:
    """Strip query string, trailing slash, replace UUID segments for matching."""
    p = (path or "").split("?")[0].rstrip("/")
    return _UUID_SEG.sub("/{id}", p)


def extract_request_data_highlight(request) -> str:
    """Best-effort short label from JSON body (name/title/etc.) for audit subtitle."""
    try:
        body = getattr(request, "body", None) or b""
        if not body or len(body) > 65536:
            return ""
        data = json.loads(body.decode("utf-8"))
        if not isinstance(data, dict):
            return ""
        for key in (
            "name",
            "title",
            "subject",
            "label",
            "username",
            "email",
            "heading",
        ):
            val = data.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()[:240]
        return ""
    except Exception:
        return ""


def _verb_to_semantic(method: str) -> str:
    m = (method or "").upper()
    if m == "POST":
        return "created"
    if m in ("PUT", "PATCH"):
        return "updated"
    if m == "DELETE":
        return "deleted"
    return "updated"


def _verb_to_badge(method: str) -> str:
    m = (method or "").upper()
    if m == "POST":
        return "Created"
    if m in ("PUT", "PATCH"):
        return "Updated"
    if m == "DELETE":
        return "Deleted"
    return "Saved"


def summarize_internal_portal_request(
    method: str,
    path: str,
    data_highlight: str = "",
) -> dict:
    """
    Build RMS-style human copy for Internal Portal (and other /api) mutating calls.

    Returns flat keys stored on ``AuditLog.changes`` for ApiActivity rows.
    """
    m = (method or "GET").upper()
    norm = normalize_api_path(path or "")
    semantic = _verb_to_semantic(m)
    badge = _verb_to_badge(m)
    highlight = (data_highlight or "").strip()

    # (pattern, resource_name, phrases by method for POST/PUT/PATCH/DELETE)
    routes: list[tuple[re.Pattern[str], str, dict[str, str]]] = [
        (
            re.compile(r"^/api/internal-portal/departments$"),
            "Department",
            {
                "POST": "Added a new department",
                "PUT": "Updated department details",
                "PATCH": "Updated department details",
                "DELETE": "Removed a department",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/departments/\{id\}$"),
            "Department",
            {
                "POST": "Saved department",
                "PUT": "Updated department details",
                "PATCH": "Updated department details",
                "DELETE": "Removed a department",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/positional-levels$"),
            "Position / designation",
            {
                "POST": "Added a position or designation",
                "PUT": "Updated position details",
                "PATCH": "Updated position details",
                "DELETE": "Removed a position or designation",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/positional-levels/\{id\}$"),
            "Position / designation",
            {
                "PUT": "Updated position details",
                "PATCH": "Updated position details",
                "DELETE": "Removed a position or designation",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/documents$"),
            "Document",
            {
                "POST": "Added a document",
                "PUT": "Updated document details",
                "PATCH": "Updated document details",
                "DELETE": "Removed a document",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/documents/\{id\}$"),
            "Document",
            {
                "PUT": "Updated document details",
                "PATCH": "Updated document details",
                "DELETE": "Removed a document",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/document-categories$"),
            "Document category",
            {
                "POST": "Added a document category",
                "PUT": "Updated category",
                "PATCH": "Updated category",
                "DELETE": "Removed a category",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/document-categories/\{id\}$"),
            "Document category",
            {
                "PUT": "Updated category",
                "PATCH": "Updated category",
                "DELETE": "Removed a category",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/events$"),
            "Event",
            {
                "POST": "Added an event",
                "PUT": "Updated event details",
                "PATCH": "Updated event details",
                "DELETE": "Removed an event",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/events/\{id\}$"),
            "Event",
            {
                "PUT": "Updated event details",
                "PATCH": "Updated event details",
                "DELETE": "Removed an event",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/announcements$"),
            "Announcement",
            {
                "POST": "Added an announcement",
                "PUT": "Updated announcement",
                "PATCH": "Updated announcement",
                "DELETE": "Removed an announcement",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/announcements/\{id\}$"),
            "Announcement",
            {
                "PUT": "Updated announcement",
                "PATCH": "Updated announcement",
                "DELETE": "Removed an announcement",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/faqs$"),
            "FAQ",
            {
                "POST": "Added an FAQ",
                "PUT": "Updated FAQ",
                "PATCH": "Updated FAQ",
                "DELETE": "Removed an FAQ",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/faqs/\{id\}$"),
            "FAQ",
            {
                "PUT": "Updated FAQ",
                "PATCH": "Updated FAQ",
                "DELETE": "Removed an FAQ",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/todos$"),
            "To-do",
            {
                "POST": "Added a to-do",
                "PUT": "Updated to-do",
                "PATCH": "Updated to-do",
                "DELETE": "Removed a to-do",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/todos/\{id\}$"),
            "To-do",
            {
                "PUT": "Updated to-do",
                "PATCH": "Updated to-do",
                "DELETE": "Removed a to-do",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/quick-links$"),
            "Quick link",
            {
                "POST": "Added a quick link",
                "PUT": "Updated quick link",
                "PATCH": "Updated quick link",
                "DELETE": "Removed a quick link",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/quick-links/\{id\}$"),
            "Quick link",
            {
                "PUT": "Updated quick link",
                "PATCH": "Updated quick link",
                "DELETE": "Removed a quick link",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/quick-links/\{id\}/click$"),
            "Quick link",
            {"POST": "Recorded quick link click"},
        ),
        (
            re.compile(r"^/api/internal-portal/popup-cards$"),
            "Popup card",
            {
                "POST": "Added a popup card",
                "PUT": "Updated popup card",
                "PATCH": "Updated popup card",
                "DELETE": "Removed a popup card",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/popup-cards/\{id\}$"),
            "Popup card",
            {
                "PUT": "Updated popup card",
                "PATCH": "Updated popup card",
                "DELETE": "Removed a popup card",
            },
        ),
        (
            re.compile(r"^/api/internal-portal/dashboard-summary$"),
            "Dashboard",
            {"POST": "Refreshed dashboard summary"},
        ),
    ]

    title = None
    resource_label = "Internal Portal"
    for rx, res_name, phrases in routes:
        if rx.match(norm):
            resource_label = res_name
            title = phrases.get(m) or phrases.get("POST") or f"{badge} {res_name.lower()}"
            break

    if title is None:
        tail = norm.replace("/api/internal-portal/", "").replace("/api/", "") or "request"
        parts = [p for p in tail.split("/") if p and p != "{id}"]
        area = parts[0].replace("-", " ").title() if parts else "Portal"
        title = f"{badge} · {area}"
        resource_label = area

    subtitle = f"Internal Portal · {resource_label}"
    if highlight:
        subtitle = f"“{highlight}” · {resource_label}"

    return {
        "semantic_action_key": semantic,
        "summary_badge": badge,
        "summary_title": title,
        "summary_subtitle": subtitle,
        "resource_label": resource_label,
        "data_highlight": highlight or None,
    }


def merge_api_activity_changes(obj: AuditLog) -> dict:
    """Recompute summary for old rows missing ``summary_title``."""
    ch = obj.changes if isinstance(obj.changes, dict) else {}
    if ch.get("summary_title"):
        return ch
    method = (ch.get("method") or "").strip().upper()
    if not method:
        verb, _ = parse_legacy_http_action(obj.action)
        method = verb or "POST"
    path = (ch.get("path") or obj.object_id or "").strip()
    highlight = ""
    if isinstance(ch.get("data_highlight"), str):
        highlight = ch["data_highlight"]
    extra = summarize_internal_portal_request(method, path, highlight)
    merged = {**ch, **extra}
    return merged


def parse_legacy_http_action(action: str) -> tuple[str | None, str | None]:
    m = _LEGACY_HTTP.match((action or "").strip())
    if not m:
        return None, None
    return m.group(1).upper(), m.group(2)


def audit_action_key(obj: AuditLog) -> str:
    """Stable key for tabs / stats — matches domain actions (``created``/``updated``/…)."""
    if (obj.model_name or "") == "ApiActivity":
        ch = merge_api_activity_changes(obj)
        sk = ch.get("semantic_action_key")
        if sk:
            return str(sk).lower()
        method = (ch.get("method") or "").strip().upper()
        if not method:
            verb, _ = parse_legacy_http_action(obj.action)
            method = verb or "POST"
        return _verb_to_semantic(method)
    verb, _code = parse_legacy_http_action(obj.action)
    if verb:
        return _verb_to_semantic(verb)
    return (obj.action or "unknown").lower()


def audit_action_label(obj: AuditLog) -> str:
    """Primary badge text (RMS-style: Created / Updated / …)."""
    if (obj.model_name or "") == "ApiActivity":
        ch = merge_api_activity_changes(obj)
        badge = ch.get("summary_badge")
        if badge:
            return str(badge)
        method = (ch.get("method") or "").strip().upper()
        if not method:
            verb, _ = parse_legacy_http_action(obj.action)
            method = verb or "POST"
        return _verb_to_badge(method)
    verb, code = parse_legacy_http_action(obj.action)
    if verb and code:
        return _verb_to_badge(verb)
    labels = {
        "CREATE": "Created",
        "UPDATE": "Updated",
        "DELETE": "Deleted",
        "VIEW": "View",
        "DOWNLOAD": "Download",
        "LOGIN": "Login",
        "LOGOUT": "Logout",
    }
    a = (obj.action or "").strip().upper()
    return labels.get(a, (obj.action or "—")[:64])


def audit_activity_title(obj: AuditLog) -> str:
    if (obj.model_name or "") == "ApiActivity":
        ch = merge_api_activity_changes(obj)
        t = ch.get("summary_title")
        if t:
            return str(t)[:500]
    if obj.object_repr and str(obj.object_repr).strip():
        return str(obj.object_repr).strip()[:500]
    if obj.object_id and str(obj.object_id).strip():
        return str(obj.object_id).strip()[:500]
    return "—"


def audit_activity_subtitle(obj: AuditLog) -> str:
    if (obj.model_name or "") == "ApiActivity":
        ch = merge_api_activity_changes(obj)
        sub = ch.get("summary_subtitle")
        if sub:
            st = ch.get("http_status")
            try:
                code = int(st) if st is not None else None
            except (TypeError, ValueError):
                code = None
            extra = ""
            if code is not None and code >= 400:
                extra = f" · HTTP {code}"
            return (str(sub)[:500] + extra).strip()
    ch = obj.changes if isinstance(obj.changes, dict) else {}
    if (obj.model_name or "") == "User" and ch.get("summary"):
        return str(ch["summary"])[:500]
    if (obj.model_name or "") == "UserProfile" and ch.get("summary"):
        return str(ch["summary"])[:500]
    parts = []
    if obj.model_name and obj.model_name != "ApiActivity":
        parts.append(obj.model_name)
    return " · ".join(parts) if parts else "—"


def audit_resource_label(obj: AuditLog) -> str:
    if (obj.model_name or "") == "ApiActivity":
        ch = merge_api_activity_changes(obj)
        rl = ch.get("resource_label")
        if rl:
            return str(rl)
    if (obj.model_name or "") == "User":
        return "User management"
    if (obj.model_name or "") == "UserProfile":
        return "Position / assignment"
    return obj.model_name or "—"


def audit_http_status(obj: AuditLog) -> int | None:
    ch = obj.changes if isinstance(obj.changes, dict) else {}
    st = ch.get("http_status")
    if st is None:
        _, code = parse_legacy_http_action(obj.action)
        if code:
            try:
                return int(code)
            except ValueError:
                pass
        return None
    try:
        return int(st)
    except (TypeError, ValueError):
        return None


def date_filter_q(request) -> Q:
    df = (request.GET.get("date_filter") or "").strip().lower()
    if not df:
        return Q()
    now = timezone.now()
    today = timezone.localdate()
    if df == "today":
        return Q(created_at__date=today)
    if df == "yesterday":
        return Q(created_at__date=today - timedelta(days=1))
    if df in ("week", "last_7_days"):
        return Q(created_at__gte=now - timedelta(days=7))
    if df in ("month", "last_30_days"):
        return Q(created_at__gte=now - timedelta(days=30))
    return Q()


def action_key_filter_q(action_key: str) -> Q | None:
    """
    Return ``Q`` for ``action_key`` from the SPA, or ``None`` if ``all`` / empty.

    ``created`` / ``updated`` / ``deleted`` include both domain ``AuditLog`` rows and
    ``ApiActivity`` HTTP traffic (aligned with RMS-style wording).
    """
    if not action_key:
        return None
    k = action_key.strip().lower()
    if k in ("", "all"):
        return None
    api_created = Q(model_name="ApiActivity") & (
        Q(changes__semantic_action_key="created")
        | Q(action__iexact="POST")
        | Q(action__iregex=r"^POST_\d{3}$")
    )
    api_updated = Q(model_name="ApiActivity") & (
        Q(changes__semantic_action_key="updated")
        | Q(action__iexact="PUT")
        | Q(action__iexact="PATCH")
        | Q(action__iregex=r"^PUT_\d{3}$")
        | Q(action__iregex=r"^PATCH_\d{3}$")
    )
    api_deleted = Q(model_name="ApiActivity") & (
        Q(changes__semantic_action_key="deleted")
        | Q(action__iexact="DELETE")
        | Q(action__iregex=r"^DELETE_\d{3}$")
    )
    if k == "created":
        return Q(action__iexact="CREATE") | api_created
    if k == "updated":
        return Q(action__iexact="UPDATE") | api_updated
    if k == "deleted":
        return Q(action__iexact="DELETE") | api_deleted
    if k == "view":
        return Q(action__iexact="VIEW")
    if k == "download":
        return Q(action__iexact="DOWNLOAD")
    if k == "login":
        return Q(action__iexact="LOGIN")
    if k == "logout":
        return Q(action__iexact="LOGOUT")
    if k == "submitted":
        return Q(action__iexact="SUBMIT") | Q(action__icontains="submit")
    # Legacy tabs that targeted raw HTTP verbs only
    if k == "http_post":
        return api_created
    if k == "http_put":
        return Q(model_name="ApiActivity") & (
            Q(action__iexact="PUT") | Q(action__iregex=r"^PUT_\d{3}$")
        )
    if k == "http_patch":
        return Q(model_name="ApiActivity") & (
            Q(action__iexact="PATCH") | Q(action__iregex=r"^PATCH_\d{3}$")
        )
    if k == "http_delete":
        return api_deleted
    return Q(action__iexact=action_key)


def stats_payload() -> dict:
    base = AuditLog.objects.all()
    now = timezone.now()
    today = timezone.localdate()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    overall = {
        "today": base.filter(created_at__date=today).count(),
        "week": base.filter(created_at__gte=week_ago).count(),
        "month": base.filter(created_at__gte=month_ago).count(),
        "total": base.count(),
    }
    by_action: dict = {}
    buckets = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("deleted", "Deleted"),
        ("view", "View"),
        ("login", "Login"),
        ("logout", "Logout"),
        ("download", "Download"),
    ]
    for key, label in buckets:
        qf = action_key_filter_q(key)
        by_action[key] = {
            "label": label,
            "total": base.filter(qf).count() if qf is not None else 0,
        }
    top_raw = (
        base.filter(created_at__gte=week_ago, user_id__isnull=False)
        .values("user__first_name", "user__last_name", "user__email")
        .annotate(action_count=Count("id"))
        .order_by("-action_count")[:10]
    )
    most_active_users = [
        {
            "first_name": r.get("user__first_name") or "",
            "last_name": r.get("user__last_name") or "",
            "email": r.get("user__email") or "",
            "action_count": r["action_count"],
        }
        for r in top_raw
    ]
    return {
        "overall": overall,
        "by_action": by_action,
        "most_active_users": most_active_users,
    }
