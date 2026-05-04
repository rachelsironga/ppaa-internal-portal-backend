"""
Management command to send email reminders for reports with approaching deadlines and overdue reports.
Uses ReportType.before_reminder_days / after_reminder_days (or ReportSetting.default_reminder_days fallback).
Run daily via cron: python manage.py send_report_reminders
"""
import time
from datetime import date, timedelta

from django.conf import settings as django_settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from microservices.ppaa_reports.models import Report, ReportSetting
from api.utils import send_custom_email


def send_email_sync(subject, to_email, template_name, context):
    """Send email synchronously (fallback when Celery/Redis is unavailable). Retries once on connection errors."""
    html_content = render_to_string(template_name, context)
    text_content = context.get("text", "This email requires an HTML-compatible email client.")
    last_error = None
    for attempt in range(2):
        try:
            # Use a fresh connection each attempt so 587+TLS is applied (settings_prod forces Gmail 465 -> 587)
            connection = get_connection(fail_silently=False)
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                to=[to_email],
                connection=connection,
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)
            return
        except Exception as e:
            last_error = e
            if attempt == 0 and any(
                msg in str(e).lower()
                for msg in ("connection unexpectedly closed", "connection refused", "connection reset")
            ):
                time.sleep(2)
                continue
            raise
    if last_error:
        raise last_error


def get_reminder_config(report):
    """Get reminder config: (before_days, after_days) from report type or global settings."""
    settings = ReportSetting.get_settings()
    before_days = settings.default_reminder_days
    after_days = 0
    if report.report_type:
        if getattr(report.report_type, "before_reminder_days", None) is not None:
            before_days = report.report_type.before_reminder_days
        elif report.report_type.default_days_before_deadline and getattr(report.report_type, "reminder_timing", "before") == "before":
            before_days = report.report_type.default_days_before_deadline

        if getattr(report.report_type, "after_reminder_days", None) is not None:
            after_days = report.report_type.after_reminder_days
        elif report.report_type.default_days_before_deadline and getattr(report.report_type, "reminder_timing", "before") == "after":
            after_days = report.report_type.default_days_before_deadline

    return before_days, after_days


def get_recipient_emails(report):
    """Collect unique emails for assigned_to, created_by (report owner)."""
    emails = set()
    if report.assigned_to and report.assigned_to.email:
        emails.add(report.assigned_to.email.strip().lower())
    if report.created_by and report.created_by.email:
        emails.add(report.created_by.email.strip().lower())
    return list(emails)


def get_recipient_name(user):
    """Get display name for user."""
    if not user:
        return "User"
    parts = [user.first_name, user.middle_name, user.last_name]
    name = " ".join(p for p in parts if p).strip()
    return name or user.email or "User"


def build_urgency_text(days_remaining):
    """Human-readable urgency text."""
    if days_remaining < 0:
        return f"{abs(days_remaining)} day(s) ago (overdue)"
    if days_remaining == 0:
        return "today"
    if days_remaining == 1:
        return "tomorrow"
    return f"in {days_remaining} days"


class Command(BaseCommand):
    help = "Send email reminders for reports with deadlines approaching (based on report type reminder days)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List reports that would receive reminders without sending",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show why each report was skipped (overdue, outside window, no emails)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            metavar="N",
            help="Override reminder window: treat deadlines within N days as in-window (for testing). Default: use report type / settings.",
        )
        parser.add_argument(
            "--test",
            action="store_true",
            help="Test mode: include reports even if reminder already sent; do not set reminder_sent (so you can re-run to test email).",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        verbose = options.get("verbose", False)
        override_days = options.get("days")
        test_mode = options.get("test", False)
        today = date.today()

        # Check if email notifications are enabled
        rms_settings = ReportSetting.get_settings()
        if not rms_settings.enable_email_notifications:
            self.stdout.write(self.style.WARNING("Email notifications are disabled in Report Settings. Skipping."))
            return

        # Find reports: not submitted. Per-stage reminder flags are checked later.
        qs = Report.objects.filter(
            is_deleted=False,
            status__in=["pending", "in_progress"],
        )
        reports = list(qs.select_related(
            "report_type", "directory", "created_by", "assigned_to"
        ))

        if verbose:
            msg = f"Today: {today}. Found {len(reports)} report(s) pending/in_progress."
            if test_mode:
                msg += " (--test: including reports that already had reminder sent)"
            self.stdout.write(msg)

        sent_count = 0
        for report in reports:
            before_days, after_days = get_reminder_config(report)
            days_until = (report.deadline_date - today).days

            recipient_emails = get_recipient_emails(report)
            if not recipient_emails:
                if verbose:
                    self.stdout.write(self.style.WARNING(f"  Skip {report.reference_number}: no recipient emails (assignee or creator)."))
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Report {report.reference_number} has no recipient emails. Skipping.")
                    )
                continue

            # Build context for email template
            organization_name = rms_settings.organization_name or "PPAA"
            from django.conf import settings as django_settings
            frontend_base = getattr(django_settings, "FRONTEND_URL", None) or "https://connect.mnh.or.tz"
            reports_link = f"{frontend_base.rstrip('/')}/report-management/reports/{report.uid}"

            directory_name = report.directory.name if report.directory else ""

            reminder_events = []
            effective_before_days = override_days if override_days is not None else before_days
            effective_after_days = override_days if override_days is not None else after_days

            if (
                effective_before_days is not None
                and effective_before_days >= 0
                and days_until >= 0
                and days_until <= effective_before_days
                and (test_mode or not getattr(report, "before_reminder_sent", False))
            ):
                reminder_events.append({
                    "stage": "before",
                    "urgency_text": build_urgency_text(days_until),
                    "days_remaining": days_until,
                    "subject": f"Reminder: Report due {build_urgency_text(days_until)} – {report.reference_number} ({report.title})",
                    "body_text": f"Report {report.reference_number} ({report.title}) is due {build_urgency_text(days_until)}. Deadline: {report.deadline_date}. View at {reports_link}",
                })

            days_after = (today - report.deadline_date).days
            if (
                effective_after_days is not None
                and effective_after_days > 0
                and days_after > 0
                and days_after <= effective_after_days
                and (test_mode or not getattr(report, "after_reminder_sent", False))
            ):
                reminder_events.append({
                    "stage": "after",
                    "urgency_text": build_urgency_text(-days_after),
                    "days_remaining": -days_after,
                    "subject": f"Overdue: Report deadline reached – please submit {report.reference_number} ({report.title})",
                    "body_text": f"Report {report.reference_number} ({report.title}) deadline has been reached. Please submit your report. Deadline: {report.deadline_date}. View at {reports_link}",
                })

            if verbose and not reminder_events:
                self.stdout.write(
                    f"  Skip {report.reference_number}: outside reminder window or reminder already sent."
                )
                continue

            for event in reminder_events:
                base_context = {
                    "urgency_text": event["urgency_text"],
                    "report_title": report.title,
                    "reference_number": report.reference_number,
                    "report_type_name": report.report_type.name if report.report_type else "Report",
                    "deadline_date": report.deadline_date.strftime("%d %B %Y"),
                    "days_remaining": event["days_remaining"],
                    "directory_name": directory_name,
                    "priority": report.get_priority_display() if hasattr(report, "get_priority_display") else report.priority,
                    "reports_link": reports_link,
                    "organization_name": organization_name,
                    "year": today.year,
                    "text": event["body_text"],
                    "reminder_stage": event["stage"],
                }

                if dry_run:
                    self.stdout.write(
                        f"[DRY-RUN] Would send {event['stage']} reminder for {report.reference_number} to {recipient_emails}"
                    )
                    sent_count += 1
                    continue

                from django.contrib.auth import get_user_model
                User = get_user_model()
                for email in recipient_emails:
                    user = None
                    if report.assigned_to and report.assigned_to.email and report.assigned_to.email.strip().lower() == email:
                        user = report.assigned_to
                    elif report.created_by and report.created_by.email and report.created_by.email.strip().lower() == email:
                        user = report.created_by
                    else:
                        user = User.objects.filter(email__iexact=email).first()
                    recipient_name = get_recipient_name(user) if user else "User"
                    context = {**base_context, "recipient_name": recipient_name}

                    template_name = "emails/report_deadline_reminder.html"

                    try:
                        send_custom_email(
                            subject=event["subject"],
                            to_email=email,
                            template_name=template_name,
                            context=context,
                        )
                        self.stdout.write(self.style.SUCCESS(f"Queued {event['stage']} reminder to {email} for {report.reference_number}"))
                    except Exception:
                        try:
                            send_email_sync(event["subject"], email, template_name, context)
                            self.stdout.write(self.style.SUCCESS(f"Sent {event['stage']} reminder to {email} for {report.reference_number} (sync)"))
                        except Exception as sync_err:
                            self.stdout.write(self.style.ERROR(f"Failed to send email to {email}: {sync_err}"))

                if not test_mode:
                    now = timezone.now()
                    report.reminder_sent = True
                    report.reminder_sent_at = now
                    update_fields = ["reminder_sent", "reminder_sent_at", "updated_at"]
                    if event["stage"] == "before":
                        report.before_reminder_sent = True
                        report.before_reminder_sent_at = now
                        update_fields.extend(["before_reminder_sent", "before_reminder_sent_at"])
                    else:
                        report.after_reminder_sent = True
                        report.after_reminder_sent_at = now
                        update_fields.extend(["after_reminder_sent", "after_reminder_sent_at"])
                    report.save(update_fields=update_fields)
                sent_count += 1

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"[DRY-RUN] Would send {sent_count} reminder(s)"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Processed {sent_count} report(s) with reminders queued"))
            if test_mode and sent_count > 0:
                self.stdout.write(self.style.WARNING("(Test mode: reminder_sent was not updated so you can run --test again)"))

        if verbose and sent_count == 0 and reports:
            self.stdout.write("")
            self.stdout.write(
                "Tip: Use --days N to test with a wider window (e.g. --dry-run -v --days 365 to see all due reports)."
            )
