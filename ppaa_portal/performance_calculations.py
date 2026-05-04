"""
SRS Performance Calculation Engine.
Activity → Target (operational + KPI) → Objective → Institution.
All calculations use approved records only; internal precision 4 decimals, display 2.
"""
from decimal import Decimal
from django.db.models import Sum, Count

from ppaa_performance.models import Objective, Target, Activity, QuarterlyData, KPIActual


def _round_display(val):
    if val is None:
        return None
    return round(Decimal(str(val)), 2)


def activity_achievement_index(activity, financial_year=None, quarter=None):
    """
    AI_i = (Actual_i / Planned_i) * 100.
    Uses QuarterlyData for the activity; if not found returns None.
    """
    if not activity.planned_value or activity.planned_value <= 0:
        return None
    qs = QuarterlyData.objects.filter(activity=activity, is_deleted=False)
    if financial_year:
        qs = qs.filter(financial_year=financial_year)
    if quarter is not None:
        qs = qs.filter(quarter=quarter)
    agg = qs.aggregate(total_actual=Sum("actual_value"))
    total_actual = agg.get("total_actual") or Decimal("0")
    pct = (total_actual / activity.planned_value) * 100
    return min(Decimal("100"), pct)


def target_operational_score(target, financial_year=None):
    """
    TI (operational) = sum(WAC_i) where WAC_i = AI_i * (ActivityWeight_i / 100).
    Only approved activities; uses quarterly computed_ai_percent where available.
    """
    activities = Activity.objects.filter(target=target, is_deleted=False, status="APPROVED")
    total = Decimal("0")
    for act in activities:
        qs = QuarterlyData.objects.filter(
            activity=act, is_deleted=False
        )
        if financial_year:
            qs = qs.filter(financial_year=financial_year)
        recs = list(qs)
        if not recs:
            continue
        ai_sum = sum((r.computed_ai_percent or Decimal("0")) for r in recs)
        ai_avg = ai_sum / len(recs) if recs else Decimal("0")
        wac = ai_avg * (act.weight / 100)
        total += wac
    return _round_display(total)


def target_kpi_score(target, financial_year=None, quarter=None):
    """
    KPI % from KPIActual; direction already applied in computed_kpi_percent.
    Returns average if multiple periods.
    """
    qs = KPIActual.objects.filter(target=target)
    if financial_year:
        qs = qs.filter(financial_year=financial_year)
    if quarter is not None:
        qs = qs.filter(quarter=quarter)
    recs = list(qs)
    if not recs:
        return None
    avg = sum((r.computed_kpi_percent or Decimal("0")) for r in recs) / len(recs)
    return _round_display(avg)


def objective_score(objective, financial_year=None):
    """
    OI = sum(TI_j * TargetWeight_j / 100) for approved targets.
    TI = target operational score.
    """
    targets = Target.objects.filter(objective=objective, is_deleted=False, status="APPROVED")
    total = Decimal("0")
    for t in targets:
        ti = target_operational_score(t, financial_year) or Decimal("0")
        total += ti * (t.weight / 100)
    return _round_display(total)


def institutional_performance(financial_year):
    """
    IP = sum(OI_k * ObjectiveWeight_k / 100) for approved objectives in the FY.
    """
    objectives = Objective.objects.filter(
        is_deleted=False, status="APPROVED", financial_year=financial_year
    )
    total = Decimal("0")
    for obj in objectives:
        oi = objective_score(obj, financial_year) or Decimal("0")
        total += oi * (obj.weight / 100)
    return _round_display(total)


def get_quarterly_trend(financial_year):
    """
    Aggregate by quarter for the given FY: average AI% across all quarterly data.
    Returns list of { quarter, label, value } for charts.
    """
    from django.db.models import Avg
    qs = (
        QuarterlyData.objects.filter(
            financial_year=financial_year, is_deleted=False
        )
        .values("quarter")
        .annotate(avg_ai=Avg("computed_ai_percent"))
    )
    labels = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    return [
        {"quarter": r["quarter"], "label": labels.get(r["quarter"], f"Q{r['quarter']}"), "value": _round_display(r["avg_ai"]) or 0}
        for r in qs.order_by("quarter")
    ]


def status_counts(model_class, filters=None):
    """Return count per status for given model (Objective, Target, Activity)."""
    qs = model_class.objects.filter(is_deleted=False)
    if filters:
        qs = qs.filter(**filters)
    return list(qs.values("status").annotate(count=Count("id")))
