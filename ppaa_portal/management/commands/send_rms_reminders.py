from django.core.management.base import BaseCommand

from ppaa_portal.rms_reminders import run_rms_report_reminders


class Command(BaseCommand):
    help = (
        "Send RMS report deadline reminders (before/after) to stakeholder or creator email. "
        "Schedule daily via cron or Celery Beat."
    )

    def handle(self, *args, **options):
        stats = run_rms_report_reminders()
        self.stdout.write(self.style.SUCCESS(str(stats)))
