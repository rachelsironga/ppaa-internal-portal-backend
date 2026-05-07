from datetime import datetime, timedelta
import json
import logging
import smtplib

import redis
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)

# Redis client for recording sent emails
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

def send_email_sync(subject, to_email, template_name, context):
    """
    Render and send one email via Django's mail backend.
    Redis audit is best-effort so SMTP success is not rolled back if Redis is down.
    """
    html_content = render_to_string(template_name, context)
    text_content = context.get(
        "text", "This email requires an HTML-compatible email client."
    )

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)

    record = {
        "timestamp": datetime.now().isoformat() + "Z",
        "to": to_email,
        "subject": subject,
        "template": template_name,
        "context": context,
        "status": "sent",
    }
    try:
        redis_client.rpush("sent_emails", json.dumps(record))
    except Exception as inner:
        logger.warning("Failed to write success record to Redis: %s", inner)
    return {"status": "sent", "record": record}


def _append_email_audit(status, subject, to_email, template_name, context, error=None):
    record = {
        "timestamp": datetime.now().isoformat() + "Z",
        "to": to_email,
        "subject": subject,
        "template": template_name,
        "context": context,
        "status": status,
    }
    if error is not None:
        record["error"] = error
    try:
        redis_client.rpush("sent_emails", json.dumps(record))
    except Exception as inner:
        logger.warning("Failed to write email audit to Redis: %s", inner)
@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_email_task(self, subject, to_email, template_name, context):
    """
    Celery task: render and send email, then record result to Redis list 'sent_emails'.

    SMTP authentication failures are not retried (credentials will not self-heal).
    Other errors retry up to max_retries.
    """
    try:
        return send_email_sync(subject, to_email, template_name, context)
    except smtplib.SMTPAuthenticationError as exc:
        logger.error(
            "SMTP authentication failed (535). Use a valid app password for Gmail, "
            "or set EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend in dev: %s",
            exc,
        )
        _append_email_audit(
            "failed_smtp_auth",
            subject,
            to_email,
            template_name,
            context,
            error=str(exc),
        )
        return {
            "status": "failed_smtp_auth",
            "error": str(exc),
            "hint": "Fix EMAIL_HOST_USER / EMAIL_HOST_PASSWORD or use console email backend.",
        }
    except Exception as exc:
        _append_email_audit(
            "failed",
            subject,
            to_email,
            template_name,
            context,
            error=str(exc),
        )
        raise self.retry(exc=exc) from exc


@shared_task
def rms_send_report_reminders():
    """Daily job: email before/after deadline reminders for RMS reports."""
    from ppaa_portal.rms_reminders import run_rms_report_reminders

    return run_rms_report_reminders()


@shared_task
def maoni_auto_escalate_overdue_suggestions():
    """
    Auto-escalate overdue handler-stage suggestions to reviewer based on
    configured Maoni escalation_days.
    """
    from microservices.maoni.models import MaoniSuggestion, MaoniWorkflowSettings

    settings_row = MaoniWorkflowSettings.objects.order_by("-updated_at").first()
    escalation_days = (
        int(settings_row.escalation_days)
        if settings_row and settings_row.escalation_days
        else 3
    )
    escalation_days = max(1, escalation_days)

    cutoff = timezone.now() - timedelta(days=escalation_days)
    handler_stage_statuses = [
        MaoniSuggestion.Status.UNDER_HANDLER_REVIEW,
        MaoniSuggestion.Status.HANDLER_RESPONDED_TO_REVIEWER,
    ]

    qs = MaoniSuggestion.objects.filter(
        status__in=handler_stage_statuses,
        updated_at__lt=cutoff,
    )
    affected = qs.update(status=MaoniSuggestion.Status.ESCALATED_TO_REVIEWER)

    logger.info(
        "Maoni auto-escalation run complete: affected=%s, escalation_days=%s",
        affected,
        escalation_days,
    )
    return {
        "affected": affected,
        "escalation_days": escalation_days,
        "cutoff": cutoff.isoformat(),
    }
