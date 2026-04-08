from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from ppaa_portal.tasks import send_email_task
import logging

logger = logging.getLogger(__name__)


def send_custom_email(subject, to_email, template_name, context):
    """
    Try to send email via Celery task. If Celery is not available, fall back to synchronous sending.
    Does not raise on failure so callers can still return a safe response (e.g. forgot-password).
    """
    try:
        # Try to enqueue email send task via Celery
        return send_email_task.delay(subject, to_email, template_name, context)
    except Exception as e:
        # Celery not available or connection error - send synchronously as fallback
        logger.warning("Celery not available, sending email synchronously: %s", e)
        try:
            # Render HTML & fallback text
            html_content = render_to_string(template_name, context)
            text_content = context.get("text", "This email requires an HTML-compatible email client.")

            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
            if not from_email:
                logger.warning("DEFAULT_FROM_EMAIL not set; email may fail.")
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=[to_email],
            )
            email.attach_alternative(html_content, "text/html")
            # fail_silently=True so we don't crash when SMTP is misconfigured or unreachable
            sent = email.send(fail_silently=True)
            if sent:
                logger.info("Email sent synchronously to %s", to_email)
                return {"status": "sent", "method": "synchronous"}
            logger.error("SMTP send returned 0 (check EMAIL_* settings and SMTP server).")
            return {"status": "failed", "method": "synchronous", "reason": "send returned 0"}
        except Exception as sync_error:
            logger.exception("Failed to send email synchronously to %s: %s", to_email, sync_error)
            # Do not re-raise: allow callers (e.g. forgot-password) to return success and log only
            return {"status": "failed", "method": "synchronous", "reason": str(sync_error)}


import base64
from io import BytesIO
from openpyxl import load_workbook
import magic  #from python-magic
from django.core.exceptions import ValidationError

def base64_to_excel_file(base64_str, filename="uploaded.xlsx"):
    try:
        # Step 1: Split and decode
        if ';base64,' not in base64_str:
            raise ValidationError("Invalid Uploaded file format.")

        _, file_str = base64_str.split(';base64,')
        decoded_file = base64.b64decode(file_str, validate=True)

        # Step 2: Validate file size
        if len(decoded_file) > 5 * 1024 * 1024:  # 5 MB limit
            raise ValidationError("File too large. For The Usage of this Service, please contact the Admin.")

        # Step 3: Check MIME type (to prevent disguised executables)
        mime_type = magic.from_buffer(decoded_file, mime=True)
        if mime_type not in [
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        ]:
            raise ValidationError("Invalid file type. Please upload an Excel file with the correct extension (.xlsx) (xls).")

        # Step 4: Try to load with openpyxl (checks structure and catches malformed Excel files)
        file_io = BytesIO(decoded_file)
        file_io.name = filename
        load_workbook(file_io)

        # Reset file pointer
        file_io.seek(0)
        return file_io

    except (base64.binascii.Error, ValueError):
        raise ValidationError("Invalid Uploaded file format. Please upload an Excel file with the correct extension (.xlsx) (xls) and no spaces in the filename.")
    except Exception as e:
        print(f'Error processing Excel file: {e}')
        raise ValidationError(f"Error processing Excel file: {str(e)}")


import re

# Common words to ignore in acronym generation
STOPWORDS = {"the", "of", "an", "in", "a", "and"}

def generate_acronym(name):
    # Remove extra spaces and convert to uppercase
    name = re.sub(r'\s+', ' ', name.strip()).upper()

    # Split name into words, filter out stopwords
    words = [word for word in name.split() if word.lower() not in STOPWORDS]

    # Create an acronym by taking the first letter of each word
    acronym = ''.join(word[0] for word in words if word)

    return acronym