import logging
from collections import defaultdict

from django.db.models import Count, OuterRef, Subquery
from django.utils import timezone
from django.utils.html import strip_tags
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.maoni.models import (
    MaoniCategory,
    MaoniSuggestion,
    MaoniSuggestionComment,
    MaoniWorkflowSettings,
)
from microservices.maoni.serializers import (
    MaoniCategorySerializer,
    MaoniSuggestionBriefSerializer,
    MaoniWorkflowSettingsSerializer,
    MaoniSuggestionWriteSerializer,
)
from ppaa_portal.response_codes import STATUS_CODES, CustomResponse

logger = logging.getLogger(__name__)

# Portal + dedicated Maoni groups (names lowercased like the frontend).
# Legacy "HR" and old reviewer names remain accepted until users are on Maoni_Reviewer (or Maoni_Admin).
_PRIVILEGED_GROUP_SLUGS = frozenset(
    {
        "hr",
        "admin",
        "maoni_handler",
        "maoni_reviewer",
        "maoni_reviewe",
        "ppaa_maoni_reviewer",
        "maoni_admin",
    }
)
_REVIEWER_GROUP_SLUGS = frozenset({"admin", "maoni_admin"})
_HANDLER_GROUP_SLUGS = frozenset(
    {
        "maoni_reviewer",
        "maoni_handler",
        "maoni_reviewe",
        "ppaa_maoni_reviewer",
    }
)
# ES / institutional reviewers (Return-to-handler from escalated). Not department queue.
_SLUGS_INSTITUTIONAL_REVIEWER = frozenset(
    {"maoni_reviewer", "ppaa_maoni_reviewer", "maoni_reviewe", "hr"}
)
# Department queue: Django group ``Maoni_Handler`` → normalized ``maoni_handler`` only.
_SLUGS_DEPARTMENT_HANDLER = frozenset({"maoni_handler"})
# Custom Maoni codenames are stored on auth.Permission's content type → auth.<codename>
_MAONI_REVIEWER_PERMS = (
    "auth.can_review_maoni_suggestion",
    "auth.can_reply_maoni_suggestion",
)
_PERM_VIEW_MAONI = "auth.can_view_maoni"
_PERM_VIEW_DASHBOARD = "auth.can_view_maoni_dashboard"
_PERM_ADD = "auth.can_add_maoni_suggestion"
_PERM_CHANGE = "auth.can_change_maoni_suggestion"
_PERM_HANDLE = "auth.can_handle_maoni_suggestion"
_PERM_PICKUP_DEPARTMENT = "auth.can_pickup_maoni_suggestion"
_PERM_PICKUP_REVIEWER = "auth.can_reviewer_pickup_maoni_suggestion"
_PERM_HANDLER_RESPOND_CONTRIBUTOR = "auth.can_handler_respond_to_maoni_contributor"
_PERM_HANDLER_RESPOND_REVIEWER = "auth.can_handler_respond_to_maoni_reviewer"
_PERM_RESUME_FROM_RETURNED = "auth.can_resume_maoni_from_returned"
_PERM_RESUME_AFTER_REVIEWER_RESPONSE = "auth.can_resume_maoni_after_reviewer_response"
_PERM_RESUME_AFTER_CONTRIBUTOR = "auth.can_resume_maoni_after_contributor"
_PERM_ESCALATE = "auth.can_escalate_maoni_suggestion"
_PERM_RETURN = "auth.can_return_maoni_suggestion"
_PERM_CLOSE = "auth.can_close_maoni_suggestion"
_PERM_REVIEW = "auth.can_review_maoni_suggestion"
_PERM_REPLY = "auth.can_reply_maoni_suggestion"
_PERM_PRINT = "auth.can_print_maoni_suggestion"
_PERM_VIEW_ESCALATION_DAYS = "auth.can_view_maoni_escalation_days"
_PERM_ADD_ESCALATION_DAYS = "auth.can_add_maoni_escalation_days"
_PERM_DELETE_ESCALATION_DAYS = "auth.can_delete_maoni_escalation_days"

# Granular handler workflow perms; legacy ``can_handle_maoni_suggestion`` implies all of these.
_GRANULAR_HANDLER_WORKFLOW_PERMS = frozenset(
    {
        _PERM_PICKUP_DEPARTMENT,
        _PERM_HANDLER_RESPOND_CONTRIBUTOR,
        _PERM_HANDLER_RESPOND_REVIEWER,
        _PERM_RESUME_FROM_RETURNED,
        _PERM_RESUME_AFTER_REVIEWER_RESPONSE,
        _PERM_RESUME_AFTER_CONTRIBUTOR,
        _PERM_ESCALATE,
        _PERM_CLOSE,
    }
)

# Posting in the staff / contributor thread: explicit reply/review or any workflow-listed handler perm.
_STAFF_THREAD_POST_EXTRA_PERMS = frozenset(_GRANULAR_HANDLER_WORKFLOW_PERMS)

_LEGACY_STATUS_MAP = {
    "PENDING_REVIEW": MaoniSuggestion.Status.UNDER_HANDLER_REVIEW,
    "UNDER_CONSIDERATION": MaoniSuggestion.Status.ESCALATED_TO_REVIEWER,
    "APPROVED": MaoniSuggestion.Status.CLOSED_APPROVED,
    "IMPLEMENTED": MaoniSuggestion.Status.CLOSED_APPROVED,
    "REJECTED": MaoniSuggestion.Status.CLOSED_REJECTED,
}

_CLOSED_STATES = {
    MaoniSuggestion.Status.CLOSED_APPROVED,
    MaoniSuggestion.Status.CLOSED_REJECTED,
}


def _normalize_status(value):
    raw = str(value or "").upper()
    if raw in _LEGACY_STATUS_MAP:
        return _LEGACY_STATUS_MAP[raw]
    return raw


def _role_slugs(user):
    if not user or not user.is_authenticated:
        return set()
    names = user.groups.values_list("name", flat=True)
    return {str(n).lower().strip() for n in names}


def _is_reviewer(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return bool(_role_slugs(user) & _REVIEWER_GROUP_SLUGS)


def _is_handler(user):
    if not user or not user.is_authenticated:
        return False
    if _is_reviewer(user):
        return True
    return bool(_role_slugs(user) & _HANDLER_GROUP_SLUGS)


def _is_privileged(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    names = user.groups.values_list("name", flat=True)
    lowered = {str(n).lower() for n in names}
    if lowered & _PRIVILEGED_GROUP_SLUGS:
        return True
    # Users granted reviewer permissions without a matching group name
    return any(user.has_perm(p) for p in _MAONI_REVIEWER_PERMS)


def _has_perm(user, perm_codename):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.has_perm(perm_codename)


def _build_maoni_transition_perm_map():
    """Each allowed (role, current, next) status edge maps to one auth permission codename."""
    S = MaoniSuggestion.Status
    h, r = "handler", "reviewer"
    return {
        (h, S.SUBMITTED, S.UNDER_HANDLER_REVIEW): _PERM_PICKUP_DEPARTMENT,
        (h, S.UNDER_HANDLER_REVIEW, S.ESCALATED_TO_REVIEWER): _PERM_ESCALATE,
        (h, S.UNDER_HANDLER_REVIEW, S.HANDLER_RESPONDED_TO_CONTRIBUTOR): _PERM_HANDLER_RESPOND_CONTRIBUTOR,
        (h, S.UNDER_HANDLER_REVIEW, S.CLOSED_APPROVED): _PERM_CLOSE,
        (h, S.UNDER_HANDLER_REVIEW, S.CLOSED_REJECTED): _PERM_CLOSE,
        (h, S.ESCALATED_TO_REVIEWER, S.CLOSED_APPROVED): _PERM_CLOSE,
        (h, S.ESCALATED_TO_REVIEWER, S.CLOSED_REJECTED): _PERM_CLOSE,
        (h, S.RETURNED_TO_HANDLER, S.UNDER_HANDLER_REVIEW): _PERM_RESUME_FROM_RETURNED,
        (h, S.RETURNED_TO_HANDLER, S.HANDLER_RESPONDED_TO_REVIEWER): _PERM_HANDLER_RESPOND_REVIEWER,
        (h, S.RETURNED_TO_HANDLER, S.HANDLER_RESPONDED_TO_CONTRIBUTOR): _PERM_HANDLER_RESPOND_CONTRIBUTOR,
        (h, S.RETURNED_TO_HANDLER, S.CLOSED_APPROVED): _PERM_CLOSE,
        (h, S.RETURNED_TO_HANDLER, S.CLOSED_REJECTED): _PERM_CLOSE,
        (h, S.HANDLER_RESPONDED_TO_REVIEWER, S.UNDER_HANDLER_REVIEW): _PERM_RESUME_AFTER_REVIEWER_RESPONSE,
        (h, S.HANDLER_RESPONDED_TO_REVIEWER, S.ESCALATED_TO_REVIEWER): _PERM_ESCALATE,
        (h, S.HANDLER_RESPONDED_TO_REVIEWER, S.CLOSED_APPROVED): _PERM_CLOSE,
        (h, S.HANDLER_RESPONDED_TO_REVIEWER, S.CLOSED_REJECTED): _PERM_CLOSE,
        (h, S.HANDLER_RESPONDED_TO_CONTRIBUTOR, S.UNDER_HANDLER_REVIEW): _PERM_RESUME_AFTER_CONTRIBUTOR,
        (h, S.HANDLER_RESPONDED_TO_CONTRIBUTOR, S.CLOSED_APPROVED): _PERM_CLOSE,
        (h, S.HANDLER_RESPONDED_TO_CONTRIBUTOR, S.CLOSED_REJECTED): _PERM_CLOSE,
        (r, S.SUBMITTED, S.UNDER_HANDLER_REVIEW): _PERM_PICKUP_REVIEWER,
        (r, S.ESCALATED_TO_REVIEWER, S.RETURNED_TO_HANDLER): _PERM_RETURN,
        (r, S.HANDLER_RESPONDED_TO_REVIEWER, S.RETURNED_TO_HANDLER): _PERM_RETURN,
    }


_MAONI_TRANSITION_PERM_MAP = _build_maoni_transition_perm_map()


def _maoni_transition_perm_granted(user, role_kind, required_perm):
    """True if user holds ``required_perm`` or a legacy umbrella that covers it."""
    if not required_perm:
        return False
    if _has_perm(user, required_perm):
        return True
    if role_kind == "handler" and required_perm in _GRANULAR_HANDLER_WORKFLOW_PERMS:
        return _has_perm(user, _PERM_HANDLE)
    if role_kind == "reviewer" and required_perm == _PERM_PICKUP_REVIEWER:
        return _has_perm(user, _PERM_REVIEW)
    return False


def _required_perm_for_transition(role_kind, current_status, next_status):
    cur = _normalize_status(current_status)
    nxt = _normalize_status(next_status)
    if role_kind == "contributor":
        if nxt == MaoniSuggestion.Status.SUBMITTED:
            return _PERM_ADD
        return _PERM_CHANGE
    return _MAONI_TRANSITION_PERM_MAP.get((role_kind, cur, nxt))


def _display_name(user):
    if not user:
        return None
    fn = (user.get_full_name() or "").strip()
    return fn or getattr(user, "username", None) or str(user.pk)


def _infer_comment_message_type(body: str) -> str:
    """Classify comment text for MaoniSuggestionComment.message_type (DB NOT NULL)."""
    s = (body or "").strip().upper()
    if s.startswith("[CLARIFICATION"):
        return MaoniSuggestionComment.MessageType.CLARIFICATION
    if s.startswith("[") and "]" in s[:200]:
        return MaoniSuggestionComment.MessageType.WORKFLOW
    return MaoniSuggestionComment.MessageType.GENERAL


def _workflow_status_tag_from_body(body: str) -> str:
    """Parse `[STATUS TAG] …` workflow comments; return normalized status string or ''."""
    s = (body or "").strip()
    if not s.startswith("["):
        return ""
    end = s.find("]")
    if end < 1:
        return ""
    inner = s[1:end].strip().upper().replace(" ", "_")
    return _normalize_status(inner) if inner else ""


def _thread_scope_for_workflow_body(body: str) -> str:
    """
    Bracketed workflow notes are WORKFLOW message_type; only staff-internal transitions
    stay in STAFF. Outcomes and contributor-facing moves go to CONTRIBUTOR so the
    submitter sees reject/approve reasons and official handler replies.
    """
    tag = _workflow_status_tag_from_body(body)
    if tag in (
        MaoniSuggestion.Status.CLOSED_APPROVED,
        MaoniSuggestion.Status.CLOSED_REJECTED,
        MaoniSuggestion.Status.HANDLER_RESPONDED_TO_CONTRIBUTOR,
        MaoniSuggestion.Status.UNDER_HANDLER_REVIEW,
    ):
        return MaoniSuggestionComment.ThreadScope.CONTRIBUTOR
    return MaoniSuggestionComment.ThreadScope.STAFF


def _can_access_suggestion(request_user, suggestion):
    if _is_privileged(request_user):
        return True
    if suggestion.submitted_by_id and suggestion.submitted_by_id == request_user.id:
        return True
    return False


_latest_thread_comment = (
    MaoniSuggestionComment.objects.filter(suggestion_id=OuterRef("pk"))
    .order_by("-created_at", "-id")
)


def _annotate_suggestion_qs(qs):
    return qs.select_related("category", "submitted_by").annotate(
        comment_count=Count("comments"),
        last_comment_at=Subquery(_latest_thread_comment.values("created_at")[:1]),
        last_comment_by_id=Subquery(_latest_thread_comment.values("commented_by_id")[:1]),
    )


def _is_allowed_transition(role_kind, current_status, next_status):
    # Contributor can only move draft to submitted (or save draft again).
    allowed = {
        "contributor": {
            MaoniSuggestion.Status.DRAFT: {
                MaoniSuggestion.Status.DRAFT,
                MaoniSuggestion.Status.SUBMITTED,
            },
        },
        "handler": {
            MaoniSuggestion.Status.SUBMITTED: {MaoniSuggestion.Status.UNDER_HANDLER_REVIEW},
            MaoniSuggestion.Status.UNDER_HANDLER_REVIEW: {
                MaoniSuggestion.Status.ESCALATED_TO_REVIEWER,
                MaoniSuggestion.Status.HANDLER_RESPONDED_TO_CONTRIBUTOR,
                MaoniSuggestion.Status.CLOSED_APPROVED,
                MaoniSuggestion.Status.CLOSED_REJECTED,
            },
            # Department may close while with ES if ES is silent; no forced "resume" before close.
            MaoniSuggestion.Status.ESCALATED_TO_REVIEWER: {
                MaoniSuggestion.Status.CLOSED_APPROVED,
                MaoniSuggestion.Status.CLOSED_REJECTED,
            },
            MaoniSuggestion.Status.RETURNED_TO_HANDLER: {
                MaoniSuggestion.Status.UNDER_HANDLER_REVIEW,
                MaoniSuggestion.Status.HANDLER_RESPONDED_TO_REVIEWER,
                MaoniSuggestion.Status.HANDLER_RESPONDED_TO_CONTRIBUTOR,
                MaoniSuggestion.Status.CLOSED_APPROVED,
                MaoniSuggestion.Status.CLOSED_REJECTED,
            },
            MaoniSuggestion.Status.HANDLER_RESPONDED_TO_REVIEWER: {
                MaoniSuggestion.Status.UNDER_HANDLER_REVIEW,
                MaoniSuggestion.Status.ESCALATED_TO_REVIEWER,
                MaoniSuggestion.Status.CLOSED_APPROVED,
                MaoniSuggestion.Status.CLOSED_REJECTED,
            },
            MaoniSuggestion.Status.HANDLER_RESPONDED_TO_CONTRIBUTOR: {
                MaoniSuggestion.Status.UNDER_HANDLER_REVIEW,
                MaoniSuggestion.Status.CLOSED_APPROVED,
                MaoniSuggestion.Status.CLOSED_REJECTED,
            },
        },
        "reviewer": {
            MaoniSuggestion.Status.SUBMITTED: {
                MaoniSuggestion.Status.UNDER_HANDLER_REVIEW,
            },
            # Institutional reviewer returns work to the department handler; closing is handler-only.
            MaoniSuggestion.Status.ESCALATED_TO_REVIEWER: {
                MaoniSuggestion.Status.RETURNED_TO_HANDLER,
            },
            MaoniSuggestion.Status.HANDLER_RESPONDED_TO_REVIEWER: {
                MaoniSuggestion.Status.RETURNED_TO_HANDLER,
            },
            MaoniSuggestion.Status.RETURNED_TO_HANDLER: set(),
        },
    }
    return next_status in allowed.get(role_kind, {}).get(current_status, set())


def _role_kind_for(user, suggestion):
    """Reviewer vs handler affects allowed status transitions (reviewers do not close cases)."""
    if user and user.is_authenticated:
        if user.is_superuser:
            return "handler"
        slugs = _role_slugs(user)
        if slugs & {"maoni_admin", "admin"}:
            return "handler"
        # Department handlers first so dual maoni_handler + maoni_reviewer users keep queue actions.
        if slugs & _SLUGS_DEPARTMENT_HANDLER:
            return "handler"
        # maoni_reviewer-only (and legacy ES groups) were only in _HANDLER_GROUP_SLUGS, so they were
        # classified as "handler" and could not RETURN_TO_HANDLER from ESCALATED_TO_REVIEWER.
        if slugs & _SLUGS_INSTITUTIONAL_REVIEWER:
            return "reviewer"
    if _is_reviewer(user):
        return "reviewer"
    if _is_handler(user):
        return "handler"
    if suggestion.submitted_by_id and suggestion.submitted_by_id == user.id:
        return "contributor"
    return "none"


def _norm_maoni_uid(value):
    """Compare department / entity UUIDs case-insensitively (with or without hyphens)."""
    if value is None:
        return ""
    return str(value).strip().lower().replace("-", "")


def _user_profile_department_uid(user):
    """Active profile department UID for Maoni routing (optional)."""
    if not user or not user.is_authenticated:
        return None
    try:
        from ppaa_auth.models import UserProfile

        prof = (
            UserProfile.objects.select_related("department")
            .filter(user_id=user.id, is_active=True, is_deleted=False)
            .first()
        )
        if prof and prof.department_id and prof.department:
            uid = getattr(prof.department, "uid", None)
            if uid is not None:
                return str(uid)
    except Exception:
        logger.debug("Could not resolve user department for Maoni", exc_info=True)
    return None


def _pickup_staff_submitted_to_under_review(user, suggestion):
    """
    First staff engagement with a SUBMITTED suggestion → UNDER_HANDLER_REVIEW (in progress).

    Used on GET (open detail) and when staff posts an official reply, so status still moves
    forward if GET was skipped (cached page, older client) or the user is classified as
    reviewer (e.g. superuser / maoni_admin) rather than handler.
    """
    if not user or not user.is_authenticated:
        return False
    current_status = _normalize_status(suggestion.status)
    if current_status != MaoniSuggestion.Status.SUBMITTED:
        return False
    if not suggestion.submitted_by_id or suggestion.submitted_by_id == user.id:
        return False
    role_kind = _role_kind_for(user, suggestion)
    if role_kind not in ("handler", "reviewer"):
        return False
    if role_kind == "handler" and not (
        _maoni_transition_perm_granted(user, "handler", _PERM_PICKUP_DEPARTMENT)
        or _has_perm(user, _PERM_REPLY)
    ):
        return False
    if role_kind == "reviewer" and not (
        _maoni_transition_perm_granted(user, "reviewer", _PERM_PICKUP_REVIEWER)
        or _has_perm(user, _PERM_HANDLE)
    ):
        return False
    if not _is_allowed_transition(
        role_kind,
        MaoniSuggestion.Status.SUBMITTED,
        MaoniSuggestion.Status.UNDER_HANDLER_REVIEW,
    ):
        return False
    sugg_dept = _norm_maoni_uid(suggestion.department_uid)
    user_dept = _norm_maoni_uid(_user_profile_department_uid(user))
    # Reviewers: require department match when both are set (PPAA-wide role). Handlers may pick
    # up even when UIDs disagree — mismatch blocked too many real cases (profile vs suggestion).
    if role_kind == "reviewer" and sugg_dept and user_dept and sugg_dept != user_dept:
        return False

    updated = MaoniSuggestion.objects.filter(
        pk=suggestion.pk,
        status=MaoniSuggestion.Status.SUBMITTED,
    ).update(
        status=MaoniSuggestion.Status.UNDER_HANDLER_REVIEW,
        updated_at=timezone.now(),
    )
    return bool(updated)


def _can_see_staff_internal_thread(user, suggestion):
    """Handler / reviewer / privileged users see the staff-only escalation channel."""
    if not user or not user.is_authenticated:
        return False
    if _is_privileged(user):
        return True
    return _role_kind_for(user, suggestion) in ("handler", "reviewer")


def _build_comment_nodes(suggestion, thread_scope_value):
    rows = list(
        suggestion.comments.select_related("commented_by").order_by("created_at")
    )
    rows = [
        c
        for c in rows
        if getattr(c, "thread_scope", MaoniSuggestionComment.ThreadScope.CONTRIBUTOR)
        == thread_scope_value
    ]
    by_parent = defaultdict(list)
    for c in rows:
        by_parent[c.parent_id].append(c)

    def node(c):
        return {
            "uid": str(c.uid),
            "comment": c.comment,
            "commented_by_name": _display_name(c.commented_by) or "Anonymous",
            "is_hr_reply": c.is_hr_reply,
            "message_type": getattr(c, "message_type", None) or "GENERAL",
            "thread_scope": getattr(c, "thread_scope", None)
            or MaoniSuggestionComment.ThreadScope.CONTRIBUTOR,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "replies": [node(ch) for ch in by_parent[c.id]],
        }

    return [node(c) for c in by_parent[None]]


def _staff_internal_comment_list(suggestion):
    """Flat chronological staff-only messages (workflow + internal notes)."""
    rows = (
        suggestion.comments.select_related("commented_by")
        .filter(thread_scope=MaoniSuggestionComment.ThreadScope.STAFF)
        .order_by("created_at", "id")
    )
    return [
        {
            "uid": str(c.uid),
            "comment": c.comment,
            "commented_by_name": _display_name(c.commented_by) or "Anonymous",
            "is_hr_reply": c.is_hr_reply,
            "message_type": getattr(c, "message_type", None) or "GENERAL",
            "thread_scope": MaoniSuggestionComment.ThreadScope.STAFF,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in rows
    ]


def _flatten_comments(tree, out):
    for c in tree:
        replies = c.get("replies") or []
        out.append(
            {
                "uid": c["uid"],
                "comment": c["comment"],
                "commented_by_name": c["commented_by_name"],
                "is_hr_reply": c["is_hr_reply"],
                "message_type": c.get("message_type") or "GENERAL",
                "created_at": c["created_at"],
            }
        )
        _flatten_comments(replies, out)


def _detail_payload(obj, user):
    data = MaoniSuggestionBriefSerializer(obj).data
    data["comments"] = _build_comment_nodes(
        obj, MaoniSuggestionComment.ThreadScope.CONTRIBUTOR
    )
    if user is not None and _can_see_staff_internal_thread(user, obj):
        data["staff_internal_comments"] = _staff_internal_comment_list(obj)
    return data


def _print_payload(obj, user):
    data = _detail_payload(obj, user)
    flat = []
    _flatten_comments(data.get("comments") or [], flat)
    for row in data.get("staff_internal_comments") or []:
        flat.append(
            {
                "uid": row["uid"],
                "comment": row["comment"],
                "commented_by_name": row["commented_by_name"],
                "is_hr_reply": row["is_hr_reply"],
                "message_type": row.get("message_type") or "GENERAL",
                "created_at": row["created_at"],
            }
        )
    flat.sort(key=lambda r: (r.get("created_at") or "", r.get("uid") or ""))
    data["all_comments"] = flat
    return data


def _get_maoni_settings():
    inst = MaoniWorkflowSettings.objects.order_by("-updated_at").first()
    if inst:
        return inst
    return MaoniWorkflowSettings.objects.create(escalation_days=3)


class MaoniCategoriesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, _PERM_VIEW_MAONI):
            return CustomResponse.forbidden()
        rows = MaoniCategory.objects.filter(is_active=True).order_by("name")
        return CustomResponse.success(data=MaoniCategorySerializer(rows, many=True).data)


class MaoniSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Read-only workflow settings (e.g. escalation days for UI). Any Maoni participant may
        # GET; escalation *editing* stays behind _PERM_VIEW_ESCALATION_DAYS / ADD / DELETE on put/delete.
        if not _has_perm(request.user, _PERM_VIEW_MAONI):
            return CustomResponse.forbidden()
        inst = _get_maoni_settings()
        return CustomResponse.success(data=MaoniWorkflowSettingsSerializer(inst).data)

    def put(self, request):
        if not _has_perm(request.user, _PERM_ADD_ESCALATION_DAYS):
            return CustomResponse.forbidden()
        inst = _get_maoni_settings()
        ser = MaoniWorkflowSettingsSerializer(inst, data=request.data, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message=str(ser.errors),
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        inst = ser.save()
        return CustomResponse.success(
            data=MaoniWorkflowSettingsSerializer(inst).data,
            message="Maoni settings updated",
        )

    def delete(self, request):
        if not _has_perm(request.user, _PERM_DELETE_ESCALATION_DAYS):
            return CustomResponse.forbidden()
        inst = _get_maoni_settings()
        inst.escalation_days = 3
        inst.save(update_fields=["escalation_days", "updated_at"])
        return CustomResponse.success(
            data=MaoniWorkflowSettingsSerializer(inst).data,
            message="Maoni escalation days reset to default",
        )


class MaoniSuggestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, _PERM_VIEW_MAONI):
            return CustomResponse.forbidden()
        try:
            page = max(1, int(request.query_params.get("page") or 1))
            page_size = min(500, max(1, int(request.query_params.get("page_size") or 10)))
        except (TypeError, ValueError):
            page, page_size = 1, 10

        qs = _annotate_suggestion_qs(MaoniSuggestion.objects.all())
        only_mine = str(request.query_params.get("only_mine") or "").lower() in (
            "1",
            "true",
            "yes",
        )
        # Non-privileged users always see only their submissions.
        # Privileged users (reviewers / admins) see all by default (e.g. dashboard) but can pass
        # only_mine=1 for the personal "My Maoni" page at /ppaa-maoni.
        if not _is_privileged(request.user):
            qs = qs.filter(submitted_by=request.user)
        elif only_mine:
            qs = qs.filter(submitted_by=request.user)
        else:
            # Handler/reviewer/admin boards should not include private drafts by other users.
            qs = qs.exclude(status=MaoniSuggestion.Status.DRAFT)
        qs = qs.order_by("-created_at")
        total = qs.count()
        start = (page - 1) * page_size
        rows = qs[start : start + page_size]
        return CustomResponse.success(
            data=MaoniSuggestionBriefSerializer(rows, many=True).data,
            pagination={"total": total, "page": page, "page_size": page_size},
        )

    def post(self, request):
        if not _has_perm(request.user, _PERM_ADD):
            return CustomResponse.forbidden()
        ser = MaoniSuggestionWriteSerializer(data=request.data)
        if not ser.is_valid():
            return CustomResponse.errors(
                message=str(ser.errors),
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        v = ser.validated_data
        status_val = (v.get("status") or MaoniSuggestion.Status.DRAFT).upper()
        inst = MaoniSuggestion(
            title=v["title"],
            description=v.get("description") or "",
            priority=v.get("priority") or MaoniSuggestion.Priority.MEDIUM,
            status=status_val,
            category=v.get("category"),
            department_uid=v.get("department_uid") or None,
            submitted_by=request.user,
        )
        if status_val == MaoniSuggestion.Status.SUBMITTED:
            inst.submitted_at = timezone.now()
        inst.save()
        obj = _annotate_suggestion_qs(MaoniSuggestion.objects.filter(pk=inst.pk)).first()
        return CustomResponse.success(
            data=MaoniSuggestionBriefSerializer(obj).data,
            message="Suggestion saved",
        )


class MaoniSuggestionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, uid):
        return (
            _annotate_suggestion_qs(MaoniSuggestion.objects.filter(uid=uid)).first()
        )

    def get(self, request, uid):
        obj = self.get_object(uid)
        if not obj:
            return CustomResponse.errors(
                message="Suggestion not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        if not _can_access_suggestion(request.user, obj):
            return CustomResponse.forbidden()

        if _pickup_staff_submitted_to_under_review(request.user, obj):
            obj = self.get_object(uid)

        return CustomResponse.success(data=_detail_payload(obj, request.user))

    def put(self, request, uid):
        obj = MaoniSuggestion.objects.filter(uid=uid).first()
        if not obj:
            return CustomResponse.errors(
                message="Suggestion not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        if not _can_access_suggestion(request.user, obj):
            return CustomResponse.forbidden()
        role_kind = _role_kind_for(request.user, obj)
        if role_kind == "none":
            return CustomResponse.forbidden()

        incoming_status = request.data.get("status")
        next_status = _normalize_status(incoming_status) if incoming_status is not None else None
        current_status = _normalize_status(obj.status)

        editable_content_fields = {"title", "description", "priority", "category", "department_uid"}
        requested_fields = {k for k in request.data.keys() if k in editable_content_fields}

        if role_kind == "contributor":
            # Contributors can only edit their own drafts and submit draft -> submitted.
            if current_status != MaoniSuggestion.Status.DRAFT:
                return CustomResponse.errors(
                    message="Contributors can only edit draft suggestions.",
                    code=STATUS_CODES["FORBIDDEN"],
                )
            if requested_fields and any(True for _ in requested_fields):
                pass
            if next_status is None:
                next_status = current_status
            if not _is_allowed_transition(role_kind, current_status, next_status):
                return CustomResponse.errors(
                    message="Invalid contributor status transition.",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            required = _required_perm_for_transition(
                role_kind, current_status, next_status
            )
            if not required:
                return CustomResponse.errors(
                    message="This workflow transition is not mapped to a permission.",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            if not _maoni_transition_perm_granted(request.user, role_kind, required):
                return CustomResponse.forbidden()
        else:
            # Handler/reviewer updates are workflow-only; no content edits.
            if requested_fields:
                return CustomResponse.errors(
                    message="Only contributors can edit suggestion content.",
                    code=STATUS_CODES["FORBIDDEN"],
                )
            if next_status is None:
                return CustomResponse.errors(
                    message="Status is required for workflow actions.",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            if not _is_allowed_transition(role_kind, current_status, next_status):
                return CustomResponse.errors(
                    message="Invalid workflow status transition for your role.",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            required = _required_perm_for_transition(
                role_kind, current_status, next_status
            )
            if not required:
                return CustomResponse.errors(
                    message="This workflow transition is not mapped to a permission.",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            if not _maoni_transition_perm_granted(request.user, role_kind, required):
                return CustomResponse.forbidden()

        payload = dict(request.data)
        payload["status"] = next_status or current_status
        ser = MaoniSuggestionWriteSerializer(obj, data=payload, partial=True)
        if not ser.is_valid():
            return CustomResponse.errors(
                message=str(ser.errors),
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        prev_status = obj.status
        inst = ser.save()
        if (
            inst.status == MaoniSuggestion.Status.SUBMITTED
            and prev_status != MaoniSuggestion.Status.SUBMITTED
        ):
            inst.submitted_at = timezone.now()
            inst.save(update_fields=["submitted_at", "updated_at"])
        elif inst.status != MaoniSuggestion.Status.SUBMITTED and not inst.submitted_at:
            pass
        obj = self.get_object(uid)
        return CustomResponse.success(
            data=_detail_payload(obj, request.user),
            message="Suggestion updated",
        )


class MaoniSuggestionReplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uid):
        try:
            suggestion = MaoniSuggestion.objects.get(uid=uid)
        except MaoniSuggestion.DoesNotExist:
            return CustomResponse.errors(
                message="Suggestion not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        if not _can_access_suggestion(request.user, suggestion):
            return CustomResponse.forbidden()
        role_kind = _role_kind_for(request.user, suggestion)
        status_now = _normalize_status(suggestion.status)
        if status_now in _CLOSED_STATES:
            return CustomResponse.errors(
                message="This suggestion is already closed.",
                code=STATUS_CODES["FORBIDDEN"],
            )
        if role_kind == "contributor" and status_now == MaoniSuggestion.Status.HANDLER_RESPONDED_TO_CONTRIBUTOR:
            return CustomResponse.errors(
                message="Clarification is closed after handler direct response.",
                code=STATUS_CODES["FORBIDDEN"],
            )

        def _can_post_staff_reply():
            if (
                _has_perm(request.user, _PERM_REPLY)
                or _has_perm(request.user, _PERM_REVIEW)
                or _has_perm(request.user, _PERM_HANDLE)
            ):
                return True
            return any(
                _has_perm(request.user, p) for p in _STAFF_THREAD_POST_EXTRA_PERMS
            )

        is_official_reply = False
        if role_kind in {"handler", "reviewer"}:
            if not _can_post_staff_reply():
                return CustomResponse.forbidden(
                    message="You need Maoni reply, review, or handle permission to post this message.",
                )
            is_official_reply = True
        elif role_kind == "contributor":
            if not _has_perm(request.user, _PERM_ADD):
                return CustomResponse.forbidden()
        elif role_kind == "none" and _is_privileged(request.user):
            if not _can_post_staff_reply():
                return CustomResponse.forbidden(
                    message="You need Maoni reply, review, or handle permission to post this message.",
                )
            is_official_reply = True
        else:
            return CustomResponse.forbidden()

        body = (request.data.get("comment") or "").strip()
        if not body:
            return CustomResponse.errors(
                message="Comment is required",
                code=STATUS_CODES["VALIDATION_ERROR"],
            )

        parent = None
        parent_uid = request.data.get("parent_comment_uid")
        if parent_uid:
            parent = MaoniSuggestionComment.objects.filter(
                uid=parent_uid,
                suggestion=suggestion,
            ).first()
            if not parent:
                return CustomResponse.errors(
                    message="Parent comment not found",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        msg_type = _infer_comment_message_type(body)
        ts_raw = request.data.get("thread_scope")
        if isinstance(ts_raw, str):
            ts_raw = ts_raw.strip().upper()
        else:
            ts_raw = None
        if ts_raw not in (None, "", "CONTRIBUTOR", "STAFF"):
            ts_raw = "CONTRIBUTOR"
        thread_scope = (
            MaoniSuggestionComment.ThreadScope.STAFF
            if ts_raw == "STAFF"
            else MaoniSuggestionComment.ThreadScope.CONTRIBUTOR
        )
        if msg_type == MaoniSuggestionComment.MessageType.WORKFLOW:
            thread_scope = _thread_scope_for_workflow_body(body)
        if role_kind == "contributor":
            thread_scope = MaoniSuggestionComment.ThreadScope.CONTRIBUTOR
        if parent:
            pscope = getattr(parent, "thread_scope", None) or MaoniSuggestionComment.ThreadScope.CONTRIBUTOR
            if (
                pscope == MaoniSuggestionComment.ThreadScope.STAFF
                and thread_scope == MaoniSuggestionComment.ThreadScope.CONTRIBUTOR
            ):
                return CustomResponse.errors(
                    message="Public replies cannot be threaded under an internal-only message.",
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )
            if pscope == MaoniSuggestionComment.ThreadScope.STAFF:
                thread_scope = MaoniSuggestionComment.ThreadScope.STAFF

        MaoniSuggestionComment.objects.create(
            suggestion=suggestion,
            parent=parent,
            commented_by=request.user,
            is_hr_reply=is_official_reply,
            message_type=msg_type,
            thread_scope=thread_scope,
            comment=body,
        )
        # Bump parent row so lists / “new activity” clients can detect updates.
        MaoniSuggestion.objects.filter(pk=suggestion.pk).update(updated_at=timezone.now())

        if is_official_reply:
            _pickup_staff_submitted_to_under_review(request.user, suggestion)
            suggestion.refresh_from_db()

        if (
            is_official_reply
            and thread_scope == MaoniSuggestionComment.ThreadScope.CONTRIBUTOR
            and suggestion.submitted_by_id
            and suggestion.submitted_by_id != request.user.id
        ):
            submitter = suggestion.submitted_by
            to_email = (getattr(submitter, "email", None) or "").strip()
            if to_email:
                try:
                    from api.utils import send_custom_email

                    from django.conf import settings as dj_settings

                    base = getattr(dj_settings, "FRONTEND_URL", None)
                    path = f"/ppaa-maoni/suggestions/{suggestion.uid}"
                    detail_url = f"{base.rstrip('/')}{path}" if base else path
                    send_custom_email(
                        subject=f"New message on your Maoni suggestion: {(suggestion.title or '')[:72]}",
                        to_email=to_email,
                        template_name="emails/maoni_new_reply.html",
                        context={
                            "contributor_name": _display_name(submitter) or "there",
                            "staff_name": _display_name(request.user) or "Maoni team",
                            "suggestion_title": suggestion.title or "Your suggestion",
                            "preview": (strip_tags(body) or body)[:400],
                            "detail_url": detail_url,
                        },
                    )
                except Exception:
                    logger.exception("Maoni new-reply email to submitter skipped")

        obj = (
            _annotate_suggestion_qs(MaoniSuggestion.objects.filter(uid=uid)).first()
        )
        return CustomResponse.success(
            data=_detail_payload(obj, request.user),
            message="Reply sent",
        )


class MaoniSuggestionPrintView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, uid):
        if not _is_privileged(request.user):
            return CustomResponse.forbidden()
        if not (_has_perm(request.user, _PERM_PRINT) or _has_perm(request.user, _PERM_VIEW_DASHBOARD)):
            return CustomResponse.forbidden()
        obj = (
            _annotate_suggestion_qs(MaoniSuggestion.objects.filter(uid=uid)).first()
        )
        if not obj:
            return CustomResponse.errors(
                message="Suggestion not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        return CustomResponse.success(data=_print_payload(obj, request.user))
