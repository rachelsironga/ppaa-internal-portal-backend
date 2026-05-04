"""
Send RMS report deadline reminders (before / after) to the correct recipient email.

Recipient rules:
- ``scope`` external: primary = stakeholder email; if missing, fallback to report creator.
- ``scope`` internal (default): report creator (``created_by``) email.

Run daily via Celery (``rms_send_report_reminders``) or ``manage.py send_rms_reminders``.
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

from django.utils import timezone
from django.utils.formats import date_format

from api.utils import send_custom_email
from ppaa_portal.models import RmsReport, record_audit_log

logger = logging.getLogger(__name__)


def _recipient_display_name(report: RmsReport) -> str:
    u = report.created_by
    if not u:
        return ""
    first = (getattr(u, "first_name", None) or "").strip()
    last = (getattr(u, "last_name", None) or "").strip()
    name = f"{first} {last}".strip()
    return name or (getattr(u, "email", None) or "")


def rms_report_reminder_recipient_email(report: RmsReport) -> str | None:
    """
    Email address that should receive deadline reminders for this report.
    """
    scope = (report.scope or "").strip().lower()
    if scope == "external":
        st = report.stakeholder
        if st and (st.email or "").strip():
            return st.email.strip()
    user = report.created_by
    if user and (getattr(user, "email", None) or "").strip():
        return user.email.strip()
    return None


def _portal_report_url(report: RmsReport) -> str:
    base = (os.environ.get("PORTAL_PUBLIC_URL") or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}/report-management/reports/{report.uid}"


def _should_send_before(report: RmsReport, today: date) -> bool:
    rt = report.report_type
    n = int(rt.before_reminder_days or 0)
    if n <= 0 or not report.deadline_date:
        return False
    if report.reminder_before_sent_at:
        return False
    dl = report.deadline_date
    if today > dl:
        return False
    first_day = dl - timedelta(days=n)
    return today >= first_day


def _should_send_after(report: RmsReport, today: date) -> bool:
    rt = report.report_type
    n = int(rt.after_reminder_days or 0)
    if n <= 0 or not report.deadline_date:
        return False
    if report.reminder_after_sent_at:
        return False
    dl = report.deadline_date
    first_day = dl + timedelta(days=n)
    return today >= first_day


def _report_status_blocks_reminders(report: RmsReport) -> bool:
    return (report.status or "").strip().lower() == "submitted"


def run_rms_report_reminders(
    today: date | None = None,
) -> dict[str, Any]:
    """
    Evaluate all active reports and queue reminder emails. Idempotent per report
    and reminder type via ``reminder_before_sent_at`` / ``reminder_after_sent_at``.
    """
    tz_today = today or timezone.localdate()
    qs = (
        RmsReport.objects.filter(is_deleted=False, deadline_date__isnull=False)
        .select_related("report_type", "stakeholder", "created_by")
        .order_by("pk")
    )

    stats = {
        "date": str(tz_today),
        "before_sent": 0,
        "after_sent": 0,
        "skipped_no_email": 0,
        "skipped_submitted": 0,
        "errors": 0,
    }

    for report in qs:
        if _report_status_blocks_reminders(report):
            stats["skipped_submitted"] += 1
            continue

        to_email = rms_report_reminder_recipient_email(report)
        if not to_email:
            stats["skipped_no_email"] += 1
            logger.warning(
                "RMS reminder skipped (no recipient email) report_uid=%s ref=%s",
                report.uid,
                report.reference_number,
            )
            continue

        if _should_send_before(report, tz_today):
            _send_one_reminder(report, to_email, "before", tz_today, stats)
        if _should_send_after(report, tz_today):
            _send_one_reminder(report, to_email, "after", tz_today, stats)

    return stats


def _send_one_reminder(
    report: RmsReport,
    to_email: str,
    kind: str,
    today: date,
    stats: dict[str, Any],
) -> None:
    assert kind in ("before", "after")
    field = (
        "reminder_before_sent_at"
        if kind == "before"
        else "reminder_after_sent_at"
    )
    if getattr(report, field):
        return

    rt = report.report_type
    dl = report.deadline_date
    assert dl is not None
    recipient_name = _recipient_display_name(report) or "Colleague"
    recipient_name_caps = recipient_name.upper()
    deadline_str = date_format(dl, format="d F Y")
    before_days = int(rt.before_reminder_days or 0)
    after_days = int(rt.after_reminder_days or 0)
    report_url = _portal_report_url(report)
    ref = report.reference_number
    title = report.title

    after_issued_tail = ""
    if kind == "before":
        text_body = (
            f"Dear {recipient_name_caps},\n\n"
            "This notice serves to inform you that the following report is approaching "
            f"its submission deadline, based on the configured {before_days}-day reminder period.\n\n"
            f"Reference: {ref}\n"
            f"Title: {title}\n"
            f"Deadline: {deadline_str}\n\n"
            "Please ensure timely submission of the report by the stated deadline.\n\n"
            "If you have already submitted the report, kindly disregard this message.\n\n"
            "Best regards,\n"
            "RMS Notification System"
        )
    else:
        after_issued_tail = (
            "this follow-up reminder is issued 1 day after the deadline."
            if after_days == 1
            else f"this follow-up reminder is issued {after_days} days after the deadline."
        )
        text_body = (
            f"Dear {recipient_name_caps},\n\n"
            "This is to inform you that the report listed below has passed its submission "
            f"deadline and remains outstanding. As per the report type configuration, {after_issued_tail}\n\n"
            f"Reference: {ref}\n"
            f"Title: {title}\n"
            f"Deadline: {deadline_str}\n\n"
            "You are receiving this notification because you are listed as the responsible "
            "contact for this report in the RMS.\n\n"
            "Kindly arrange for the report to be submitted as soon as possible to ensure "
            "compliance with reporting requirements.\n\n"
            "If you have already completed the submission, please disregard this message.\n\n"
            "Best regards,\n"
            "RMS Notification System"
        )
    copy_year = timezone.now().year
    text_footer = (
        f"\n\n---\nCopyright (C) {copy_year} Public Procurement Appeal Authority. "
        "All Rights Reserved. Designed by the Department of Information Technology. "
        "Content Managed by Public Procurement Appeal Authority."
    )
    if report_url:
        text_body = f"{text_body}\n\n{report_url}"
    text_body = f"{text_body}{text_footer}"

    ctx = {
        "recipient_name": recipient_name,
        "recipient_name_caps": recipient_name_caps,
        "report_title": title,
        "reference_number": ref,
        "deadline_date": deadline_str,
        "reminder_kind": kind,
        "before_days": before_days,
        "after_days": after_days,
        "after_issued_tail": after_issued_tail,
        "report_url": report_url,
        "year": timezone.now().year,
        "text": text_body,
    }
    if kind == "before":
        subject = "APPROACHING DEADLINE NOTICE: REPORT SUBMISSION REMINDER."
    else:
        subject = "OVERDUE NOTICE: REPORT SUBMISSION PAST DEADLINE."
    subject = subject.upper()
    try:
        send_custom_email(
            subject,
            to_email,
            "emails/rms_report_reminder.html",
            ctx,
        )
        now = timezone.now()
        RmsReport.objects.filter(pk=report.pk).update(**{field: now})
        setattr(report, field, now)
        stats["before_sent" if kind == "before" else "after_sent"] += 1
        record_audit_log(
            user=report.created_by,
            action="reminder_sent",
            model_name="RmsReport",
            object_id=str(report.uid),
            object_repr=(report.title or "")[:255],
            changes={
                "reminder_kind": kind,
                "to_email": to_email,
                "comments": f"RMS {kind} deadline reminder emailed",
            },
            ip_address=None,
            user_agent="rms_reminders",
            department=None,
            created_by=report.created_by,
            updated_by=report.created_by,
        )
    except Exception as exc:
        stats["errors"] += 1
        logger.exception(
            "RMS reminder send failed report_uid=%s kind=%s: %s",
            report.uid,
            kind,
            exc,
        )
