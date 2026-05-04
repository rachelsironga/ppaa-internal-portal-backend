"""
SPISM performance reports: aggregates quarterly implementation that has been submitted
(SUBMITTED / PENDING / APPROVED in implementation_quarters_state, or legacy full submit).
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.utils import timezone

from .models import (
    SpismActivity,
    SpismKpiActual,
    SpismObjective,
    SpismQuarterlyData,
    SpismTarget,
)


def _terminal_impl_statuses():
    return frozenset({"SUBMITTED", "PENDING", "APPROVED"})


def _entry_terminal(entry) -> bool:
    return isinstance(entry, dict) and str(entry.get("status") or "").upper() in _terminal_impl_statuses()


def quarter_implementation_submitted(activity: SpismActivity, quarter: int) -> bool:
    """
    True when this quarter's implementation is submitted for review or approved
    (counts toward institutional / quarterly reports).
    """
    st = activity.implementation_quarters_state or {}
    if not isinstance(st, dict):
        st = {}
    sk = str(int(quarter))

    e = st.get(sk)
    if e is not None and _entry_terminal(e):
        return True

    all_e = st.get("all")
    if all_e is not None and _entry_terminal(all_e):
        return True

    if activity.implementation_submitted_at:
        if not st:
            return True
        if all_e is not None and _entry_terminal(all_e):
            return True
        has_q = any(k in st for k in ("1", "2", "3", "4"))
        if not has_q and all_e is None:
            return True

    return False


def activity_achievement_index_percent(activity: SpismActivity, actual: Decimal | None) -> float | None:
    """AI % = actual / planned * 100 when planned is set and positive."""
    if actual is None:
        return None
    planned = activity.planned_value
    if planned is None or planned <= 0:
        return None
    try:
        return float((Decimal(actual) / planned) * Decimal(100))
    except Exception:
        return None


def _collect_submitted_quarterly_ai(financial_year: str) -> list[tuple[int, float, SpismActivity]]:
    """
    Returns list of (quarter, ai_percent, activity) for rows that count as submitted implementation.
    """
    fy = (financial_year or "").strip()
    if not fy:
        return []

    qs = (
        SpismQuarterlyData.objects.filter(is_deleted=False, financial_year=fy)
        .select_related("activity", "activity__target", "activity__target__objective")
        .filter(
            activity__is_deleted=False,
            activity__status=SpismActivity.Status.APPROVED,
            activity__target__is_deleted=False,
            activity__target__status=SpismTarget.Status.APPROVED,
            activity__target__objective__is_deleted=False,
            activity__target__objective__status=SpismObjective.Status.APPROVED,
            activity__target__objective__financial_year=fy,
        )
    )

    out: list[tuple[int, float, SpismActivity]] = []
    for row in qs:
        act = row.activity
        q = int(row.quarter)
        if not quarter_implementation_submitted(act, q):
            continue
        pct = activity_achievement_index_percent(act, row.actual_value)
        if pct is None:
            continue
        out.append((q, pct, act))
    return out


def build_quarterly_report(financial_year: str) -> dict[str, Any]:
    rows = _collect_submitted_quarterly_ai(financial_year)
    by_q: dict[int, list[float]] = defaultdict(list)
    all_pct: list[float] = []
    for q, pct, _act in rows:
        by_q[q].append(pct)
        all_pct.append(pct)

    quarterly_trend = []
    for q in (1, 2, 3, 4):
        vals = by_q.get(q, [])
        if vals:
            quarterly_trend.append(
                {
                    "quarter": q,
                    "label": f"Q{q}",
                    "value": round(sum(vals) / len(vals), 2),
                }
            )

    inst = round(sum(all_pct) / len(all_pct), 2) if all_pct else None

    return {
        "financial_year": financial_year,
        "generated_at": timezone.now().isoformat(),
        "institutional_performance": inst,
        "quarterly_trend": quarterly_trend,
        "summary": {
            "institutional_performance": inst,
            "quarters_reported": len([q for q in (1, 2, 3, 4) if by_q.get(q)]),
            "submitted_quarter_rows": len(rows),
        },
    }


def _weighted_avg(pairs: list[tuple[float, float]]) -> float | None:
    """pairs: (weight, value)."""
    if not pairs:
        return None
    tw = sum(w for w, _ in pairs if w and w > 0)
    if tw <= 0:
        return sum(v for _, v in pairs) / len(pairs)
    return sum(w * v for w, v in pairs if w and w > 0) / tw


def build_annual_report(financial_year: str) -> dict[str, Any]:
    fy = (financial_year or "").strip()
    rows = _collect_submitted_quarterly_ai(fy)
    by_objective: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for _q, pct, act in rows:
        ouid = str(act.target.objective_id)
        w = float(act.weight or 0) or 1.0
        by_objective[ouid].append((w, pct))

    objectives_out = []
    obj_qs = SpismObjective.objects.filter(
        is_deleted=False, financial_year=fy, status=SpismObjective.Status.APPROVED
    ).order_by("title")
    for o in obj_qs:
        pairs = by_objective.get(str(o.id), [])
        score = _weighted_avg(pairs)
        objectives_out.append(
            {
                "uid": str(o.uid),
                "title": o.title,
                "weight": float(o.weight),
                "score": round(score, 2) if score is not None else None,
            }
        )

    all_scores = [s["score"] for s in objectives_out if s["score"] is not None]
    inst = round(sum(all_scores) / len(all_scores), 2) if all_scores else None

    return {
        "financial_year": fy,
        "generated_at": timezone.now().isoformat(),
        "objectives": objectives_out,
        "summary": {
            "institutional_performance": inst,
            "objective_count": len(objectives_out),
        },
    }


def build_objective_report(financial_year: str) -> dict[str, Any]:
    fy = (financial_year or "").strip()
    rows = _collect_submitted_quarterly_ai(fy)
    by_target: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for _q, pct, act in rows:
        tuid = str(act.target_id)
        w = float(act.weight or 0) or 1.0
        by_target[tuid].append((w, pct))

    objectives_out = []
    total_targets = 0
    obj_qs = (
        SpismObjective.objects.filter(is_deleted=False, financial_year=fy, status=SpismObjective.Status.APPROVED)
        .prefetch_related("targets")
        .order_by("title")
    )
    for o in obj_qs:
        targets_out = []
        obj_pairs: list[tuple[float, float]] = []
        for t in o.targets.filter(is_deleted=False, status=SpismTarget.Status.APPROVED):
            total_targets += 1
            pairs = by_target.get(str(t.id), [])
            op_score = _weighted_avg(pairs)
            kpi_row = SpismKpiActual.objects.filter(
                target_id=t.id, financial_year=fy, is_deleted=False
            ).first()
            kpi_score = None
            if kpi_row and kpi_row.computed_kpi_percent is not None:
                kpi_score = float(kpi_row.computed_kpi_percent)
            targets_out.append(
                {
                    "uid": str(t.uid),
                    "title": t.title,
                    "weight": float(t.weight),
                    "operational_score": round(op_score, 2) if op_score is not None else None,
                    "kpi_score": round(kpi_score, 2) if kpi_score is not None else None,
                }
            )
            if op_score is not None:
                obj_pairs.append((float(t.weight or 0) or 1.0, op_score))

        o_score = _weighted_avg(obj_pairs)
        objectives_out.append(
            {
                "uid": str(o.uid),
                "title": o.title,
                "weight": float(o.weight),
                "score": round(o_score, 2) if o_score is not None else None,
                "targets": targets_out,
            }
        )

    return {
        "financial_year": fy,
        "generated_at": timezone.now().isoformat(),
        "objectives": objectives_out,
        "summary": {
            "objective_count": len(objectives_out),
            "target_count": total_targets,
        },
    }


def build_kpi_report(financial_year: str) -> dict[str, Any]:
    fy = (financial_year or "").strip()
    kpi_targets = []
    qs = (
        SpismKpiActual.objects.filter(is_deleted=False, financial_year=fy)
        .select_related("target", "target__objective")
        .filter(
            target__is_deleted=False,
            target__status=SpismTarget.Status.APPROVED,
            target__objective__is_deleted=False,
            target__objective__status=SpismObjective.Status.APPROVED,
            target__objective__financial_year=fy,
        )
    )
    scores = []
    for row in qs:
        t = row.target
        pct = row.computed_kpi_percent
        if pct is None:
            continue
        pv = float(pct)
        scores.append(pv)
        kpi_targets.append(
            {
                "uid": str(t.uid),
                "title": t.title,
                "objective_title": t.objective.title,
                "kpi_name": t.kpi_name or "—",
                "kpi_planned_value": float(t.kpi_planned_value) if t.kpi_planned_value is not None else None,
                "kpi_score": round(pv, 2),
            }
        )

    avg_kpi = round(sum(scores) / len(scores), 2) if scores else None

    return {
        "financial_year": fy,
        "generated_at": timezone.now().isoformat(),
        "kpi_targets": kpi_targets,
        "summary": {
            "target_count": len(kpi_targets),
            "average_kpi_score": avg_kpi,
        },
    }


def build_report(report_type: str, financial_year: str) -> dict[str, Any]:
    rt = (report_type or "quarterly").lower()
    if rt == "quarterly":
        return build_quarterly_report(financial_year)
    if rt == "annual":
        return build_annual_report(financial_year)
    if rt == "objective":
        return build_objective_report(financial_year)
    if rt == "kpi":
        return build_kpi_report(financial_year)
    return {
        "financial_year": financial_year,
        "generated_at": timezone.now().isoformat(),
        "report_type": rt,
        "summary": {},
    }
