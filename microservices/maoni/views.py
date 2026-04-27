from collections import defaultdict

from django.db.models import Count
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.maoni.models import MaoniCategory, MaoniSuggestion, MaoniSuggestionComment
from microservices.maoni.serializers import (
    MaoniCategorySerializer,
    MaoniSuggestionBriefSerializer,
    MaoniSuggestionWriteSerializer,
)
from ppaa_portal.response_codes import STATUS_CODES, CustomResponse


# Portal + dedicated Maoni groups (names lowercased like the frontend).
# Legacy "HR" remains accepted until users are on PPAA_Maoni_Reviewer (or Maoni_Admin).
_PRIVILEGED_GROUP_SLUGS = frozenset(
    {
        "hr",
        "admin",
        "ppaa_maoni_reviewer",
        "maoni_admin",
    }
)
# Custom Maoni codenames are stored on auth.Permission's content type → auth.<codename>
_MAONI_REVIEWER_PERMS = (
    "auth.can_review_maoni_suggestion",
    "auth.can_reply_maoni_suggestion",
)


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


def _display_name(user):
    if not user:
        return None
    fn = (user.get_full_name() or "").strip()
    return fn or getattr(user, "username", None) or str(user.pk)


def _can_access_suggestion(request_user, suggestion):
    if _is_privileged(request_user):
        return True
    if suggestion.submitted_by_id and suggestion.submitted_by_id == request_user.id:
        return True
    return False


def _annotate_suggestion_qs(qs):
    return qs.select_related("category", "submitted_by").annotate(comment_count=Count("comments"))


def _build_comment_nodes(suggestion):
    rows = list(
        suggestion.comments.select_related("commented_by").order_by("created_at")
    )
    by_parent = defaultdict(list)
    for c in rows:
        by_parent[c.parent_id].append(c)

    def node(c):
        return {
            "uid": str(c.uid),
            "comment": c.comment,
            "commented_by_name": _display_name(c.commented_by) or "Anonymous",
            "is_hr_reply": c.is_hr_reply,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "replies": [node(ch) for ch in by_parent[c.id]],
        }

    return [node(c) for c in by_parent[None]]


def _flatten_comments(tree, out):
    for c in tree:
        replies = c.get("replies") or []
        out.append(
            {
                "uid": c["uid"],
                "comment": c["comment"],
                "commented_by_name": c["commented_by_name"],
                "is_hr_reply": c["is_hr_reply"],
                "created_at": c["created_at"],
            }
        )
        _flatten_comments(replies, out)


def _detail_payload(obj):
    data = MaoniSuggestionBriefSerializer(obj).data
    tree = _build_comment_nodes(obj)
    data["comments"] = tree
    return data


def _print_payload(obj):
    data = _detail_payload(obj)
    flat = []
    _flatten_comments(data.get("comments") or [], flat)
    data["all_comments"] = flat
    return data


class MaoniCategoriesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = MaoniCategory.objects.filter(is_active=True).order_by("name")
        return CustomResponse.success(data=MaoniCategorySerializer(rows, many=True).data)


class MaoniSuggestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
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
        qs = qs.order_by("-created_at")
        total = qs.count()
        start = (page - 1) * page_size
        rows = qs[start : start + page_size]
        return CustomResponse.success(
            data=MaoniSuggestionBriefSerializer(rows, many=True).data,
            pagination={"total": total, "page": page, "page_size": page_size},
        )

    def post(self, request):
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
        return CustomResponse.success(data=_detail_payload(obj))

    def put(self, request, uid):
        obj = MaoniSuggestion.objects.filter(uid=uid).first()
        if not obj:
            return CustomResponse.errors(
                message="Suggestion not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        if not _can_access_suggestion(request.user, obj):
            return CustomResponse.forbidden()
        ser = MaoniSuggestionWriteSerializer(obj, data=request.data, partial=True)
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
            data=_detail_payload(obj),
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

        MaoniSuggestionComment.objects.create(
            suggestion=suggestion,
            parent=parent,
            commented_by=request.user,
            is_hr_reply=_is_privileged(request.user),
            comment=body,
        )
        obj = (
            _annotate_suggestion_qs(MaoniSuggestion.objects.filter(uid=uid)).first()
        )
        return CustomResponse.success(
            data=_detail_payload(obj),
            message="Reply sent",
        )


class MaoniSuggestionPrintView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, uid):
        if not _is_privileged(request.user):
            return CustomResponse.forbidden()
        obj = (
            _annotate_suggestion_qs(MaoniSuggestion.objects.filter(uid=uid)).first()
        )
        if not obj:
            return CustomResponse.errors(
                message="Suggestion not found",
                code=STATUS_CODES["DATA_NOT_FOUND"],
            )
        return CustomResponse.success(data=_print_payload(obj))
