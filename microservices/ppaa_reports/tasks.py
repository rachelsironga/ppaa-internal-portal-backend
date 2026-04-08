"""
Celery tasks for Report Management System.
"""
from celery import shared_task
from django.core.management import call_command


@shared_task
def send_report_deadline_reminders():
    """
    Send email reminders for reports with approaching deadlines.
    Intended to run daily via Celery Beat.
    """
    call_command("send_report_reminders")
