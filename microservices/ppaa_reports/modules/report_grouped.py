from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser
from django.db.models import Q
from datetime import date
import hashlib

from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_portal.pagination import CustomPagination
from utils.permissions import HasMethodPermission

from ..models import Report, FinancialYear
from ..serializers import ReportListSerializer
from .report import get_user_directory_info, is_admin_user


def _period_group_key(report: Report) -> str:
    """
    Stable group key for periodic reports so they appear as one item in list.
    Excludes financial_period so Q1-Q4 / H1-H2 collapse together.
    """
    parts = [
        str(getattr(report.report_type, "uid", "")),
        str(getattr(report.financial_year, "uid", "")),
        str(getattr(report.directory, "uid", "")),
        str(getattr(report.department, "uid", "")) if report.department_id else "",
        str(getattr(report.category, "uid", "")) if report.category_id else "",
        str(getattr(report.stakeholder, "uid", "")) if report.stakeholder_id else "",
        (report.other_stakeholder_name or "").strip().lower(),
        (report.scope or "").strip().lower(),
        (report.title or "").strip().lower(),
    ]
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


class ReportGroupedView(APIView):
    """
    Group quarterly (Q1-Q4) and biannual (H1-H2) reports into a single list item.
    Other reports are returned as-is.
    """
    permission_classes = [IsAuthenticated, HasMethodPermission]
    parser_classes = [JSONParser]
    serializer_class = ReportListSerializer
    required_permissions = {"get": ["view_report"]}

    def get(self, request):
        try:
            user_dir_info = get_user_directory_info(request.user)
            is_admin = is_admin_user(request.user)

            queryset = Report.objects.filter(is_deleted=False).select_related(
                "report_type", "category", "stakeholder", "financial_year", "financial_period",
                "directory", "department"
            )

            if not is_admin and user_dir_info and user_dir_info.get("department"):
                queryset = queryset.filter(department=user_dir_info["department"])

            # Apply same filters as ReportView (subset used by list page)
            status = request.query_params.get("status")
            if status:
                queryset = queryset.filter(status__in=status.split(",") if "," in status else [status])

            priority = request.query_params.get("priority")
            if priority:
                queryset = queryset.filter(priority__in=priority.split(",") if "," in priority else [priority])

            scope = request.query_params.get("scope")
            if scope:
                queryset = queryset.filter(scope__in=scope.split(",") if "," in scope else [scope])

            financial_year_uid = request.query_params.get("financial_year_uid")
            if financial_year_uid:
                uids = [u.strip() for u in financial_year_uid.split(",") if u.strip()]
                queryset = queryset.filter(financial_year__uid__in=uids)
            else:
                # Default All Reports to the current financial year based on today's date.
                today = date.today()
                current_fy = FinancialYear.objects.filter(
                    is_deleted=False,
                    start_date__lte=today,
                    end_date__gte=today,
                ).order_by("-start_date").first()

                if not current_fy:
                    current_fy = FinancialYear.objects.filter(
                        is_deleted=False,
                        is_current=True,
                    ).order_by("-start_date").first()

                if not current_fy:
                    current_fy = FinancialYear.objects.filter(
                        is_deleted=False
                    ).order_by("-start_date").first()

                if current_fy:
                    queryset = queryset.filter(financial_year=current_fy)

            report_type_uid = request.query_params.get("report_type_uid")
            if report_type_uid:
                uids = [u.strip() for u in report_type_uid.split(",") if u.strip()]
                queryset = queryset.filter(report_type__uid__in=uids)

            category_uid = request.query_params.get("category_uid")
            if category_uid:
                queryset = queryset.filter(category__uid=category_uid)

            department_uid = (
                request.query_params.get("department_uid")
                or request.query_params.get("directory_uid")
                or request.query_params.get("directorate_uid")
            )
            if department_uid:
                queryset = queryset.filter(department__uid=department_uid)

            stakeholder_uid = request.query_params.get("stakeholder_uid")
            if stakeholder_uid:
                queryset = queryset.filter(stakeholder__uid=stakeholder_uid)

            deadline_state = request.query_params.get("deadline_state")
            if deadline_state:
                today = date.today()
                if deadline_state == "overdue":
                    queryset = queryset.filter(deadline_date__lt=today).exclude(status="submitted")
                elif deadline_state == "due_today":
                    queryset = queryset.filter(deadline_date=today).exclude(status="submitted")

            search = request.query_params.get("search")
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(reference_number__icontains=search) |
                    Q(description__icontains=search)
                )

            ordering = request.query_params.get("ordering", "-deadline_date")
            queryset = queryset.order_by(ordering)

            reports = list(queryset)

            grouped = []
            groups = {}
            group_counts = {}

            for r in reports:
                freq = getattr(r.report_type, "frequency", None)
                is_grouped_periodic = freq in ("quarterly", "biannual")
                if not is_grouped_periodic:
                    grouped.append(r)
                    continue

                key = _period_group_key(r)
                current_counts = group_counts.setdefault(
                    key,
                    {"done": 0, "pending": 0, "total": 0}
                )
                current_counts["total"] += 1
                if r.status == "submitted":
                    current_counts["done"] += 1
                else:
                    current_counts["pending"] += 1

                if key not in groups:
                    groups[key] = r
                    # Attach extra info used by frontend detail page
                    setattr(r, "_quarter_group_key", key)
                    grouped.append(r)

            for r in grouped:
                key = getattr(r, "_quarter_group_key", None)
                if not key:
                    continue
                counts = group_counts.get(key, {})
                setattr(r, "period_done_count", counts.get("done", 0))
                setattr(r, "period_pending_count", counts.get("pending", 0))
                setattr(r, "period_total_count", counts.get("total", 0))

            return CustomPagination.paginate(
                view_class=self,
                results=grouped,
                request=request,
                serializer_context={"request": request},
            )

        except Exception as e:
            return CustomResponse.errors(
                message=f"Failed to retrieve Reports: {str(e)}",
                code=STATUS_CODES["SERVER_ERROR"]
            )

