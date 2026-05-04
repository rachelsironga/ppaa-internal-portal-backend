from decimal import Decimal

from django.db.models import Q

from ppaa_portal.response_codes import CustomResponse


def paginated_queryset(qs, request, serializer_class, context_extra=None):
    ctx = {"request": request}
    if context_extra:
        ctx.update(context_extra)
    paginated = str(request.GET.get("paginated", "")).lower() == "true"
    if not paginated:
        ser = serializer_class(qs, many=True, context=ctx)
        return CustomResponse.success(data=ser.data)
    page = max(int(request.GET.get("page", 1) or 1), 1)
    page_size = min(max(int(request.GET.get("page_size", 10) or 10), 1), 500)
    total = qs.count()
    start = (page - 1) * page_size
    chunk = qs[start : start + page_size]
    ser = serializer_class(chunk, many=True, context=ctx)
    return CustomResponse.success(
        data=ser.data,
        pagination={"page": page, "page_size": page_size, "total": total},
    )


def apply_search_filter(qs, request, *field_names):
    q = (request.GET.get("search") or "").strip()
    if not q:
        return qs
    cond = Q()
    for f in field_names:
        cond |= Q(**{f"{f}__icontains": q})
    return qs.filter(cond)


def parse_filters_param(request):
    raw = (request.GET.get("filters") or "").strip()
    if not raw or raw.upper() == "ALL":
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def to_decimal(val, default=None):
    if val is None or val == "":
        return default
    try:
        return Decimal(str(val))
    except Exception:
        return default
