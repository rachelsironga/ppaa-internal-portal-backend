from datetime import datetime

from celery import shared_task
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
import redis
import json
import logging

logger = logging.getLogger(__name__)

# Redis client for recording sent emails
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_email_task(self, subject, to_email, template_name, context):
    """
    Celery task: render and send email, then record result to Redis list 'sent_emails'.
    Retries on exception.
    """
    try:
        # Render HTML & fallback text
        html_content = render_to_string(template_name, context)
        text_content = context.get("text", "This email requires an HTML-compatible email client.")

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        email.attach_alternative(html_content, "text/html")

        # send (this will use EMAIL_* settings from Django)
        email.send(fail_silently=False)

        # success record
        record = {
            "timestamp": datetime.now().isoformat() + "Z",
            "to": to_email,
            "subject": subject,
            "template": template_name,
            "context": context,
            "status": "sent",
        }
        redis_client.rpush("sent_emails", json.dumps(record))
        return {"status": "sent", "record": record}

    except Exception as exc:
        # record failure too (best-effort)
        try:
            record = {
                "timestamp": datetime.now().isoformat() + "Z",
                "to": to_email,
                "subject": subject,
                "template": template_name,
                "context": context,
                "status": "failed",
                "error": str(exc),
            }
            redis_client.rpush("sent_emails", json.dumps(record))
        except Exception as inner:
            logger.exception("Failed to write failure record to Redis: %s", inner)

        # Retry with exponential backoff via Celery retry
        raise self.retry(exc=exc)
