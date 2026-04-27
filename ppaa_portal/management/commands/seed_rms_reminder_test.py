"""
Create sample RMS reports so `send_rms_reminders` has something to email.

Creates one report due soon (before-deadline window) and one past due (after window),
both internal scope → email goes to the creator's address.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ppaa_auth.models import User
from ppaa_portal.models import RmsReport, RmsReportType
from ppaa_portal.rms_reminders import run_rms_report_reminders


class Command(BaseCommand):
    help = (
        "Insert two RMS test reports (before + after reminder windows) for the "
        "given user, then optionally run send_rms_reminders."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            default="",
            help="Creator email (must match an existing user). Default: first active user with an email.",
        )
        parser.add_argument(
            "--send",
            action="store_true",
            help="Run reminder job immediately after seeding (same as manage.py send_rms_reminders).",
        )

    def handle(self, *args, **options):
        email = (options["email"] or "").strip()
        if email:
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if not user:
                raise CommandError(f"No active user with email: {email}")
        else:
            user = (
                User.objects.filter(is_active=True)
                .exclude(email__isnull=True)
                .exclude(email="")
                .first()
            )
            if not user:
                raise CommandError(
                    "No active user with an email. Create a user or pass --email you@example.com"
                )

        today = timezone.localdate()
        suffix = uuid.uuid4().hex[:8].upper()
        type_code = f"T{suffix}"[:20]

        report_type, _ = RmsReportType.objects.get_or_create(
            code=type_code,
            defaults={
                "name": f"Reminder test type {suffix}",
                "frequency": "custom",
                "description": "Seeded for RMS reminder email testing; safe to delete.",
                "before_reminder_days": 7,
                "after_reminder_days": 3,
                "requires_attachment": False,
                "is_active": True,
                "is_deleted": False,
                "created_by": user,
            },
        )
        # If reused from partial state, ensure reminder windows are set
        if report_type.before_reminder_days < 1:
            report_type.before_reminder_days = 7
        if report_type.after_reminder_days < 1:
            report_type.after_reminder_days = 3
        report_type.save(
            update_fields=["before_reminder_days", "after_reminder_days"]
        )

        fy_uid = uuid.uuid4()

        # Before: deadline a few days ahead; window started 7 days before deadline
        dl_before = today + timedelta(days=3)
        ref_before = f"TEST-B-{suffix}"
        r_before, created_b = RmsReport.objects.get_or_create(
            reference_number=ref_before,
            defaults={
                "title": "RMS reminder test — before deadline",
                "report_type": report_type,
                "financial_year_uid": fy_uid,
                "scope": "internal",
                "status": "draft",
                "deadline_date": dl_before,
                "created_by": user,
                "reminder_before_sent_at": None,
                "reminder_after_sent_at": None,
            },
        )
        if not created_b:
            r_before.deadline_date = dl_before
            r_before.reminder_before_sent_at = None
            r_before.reminder_after_sent_at = None
            r_before.status = "draft"
            r_before.is_deleted = False
            r_before.save(
                update_fields=[
                    "deadline_date",
                    "reminder_before_sent_at",
                    "reminder_after_sent_at",
                    "status",
                    "is_deleted",
                ]
            )

        # After: deadline far enough in the past that today >= deadline + after_days
        dl_after = today - timedelta(days=5)
        ref_after = f"TEST-A-{suffix}"
        r_after, created_a = RmsReport.objects.get_or_create(
            reference_number=ref_after,
            defaults={
                "title": "RMS reminder test — overdue follow-up",
                "report_type": report_type,
                "financial_year_uid": uuid.uuid4(),
                "scope": "internal",
                "status": "draft",
                "deadline_date": dl_after,
                "created_by": user,
                "reminder_before_sent_at": None,
                "reminder_after_sent_at": None,
            },
        )
        if not created_a:
            r_after.deadline_date = dl_after
            r_after.reminder_before_sent_at = None
            r_after.reminder_after_sent_at = None
            r_after.status = "draft"
            r_after.is_deleted = False
            r_after.save(
                update_fields=[
                    "deadline_date",
                    "reminder_before_sent_at",
                    "reminder_after_sent_at",
                    "status",
                    "is_deleted",
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded RMS test reports for {user.email}\n"
                f"  Before window: ref={ref_before} deadline={dl_before} (today={today})\n"
                f"  After window:  ref={ref_after} deadline={dl_after}\n"
                f"  Report type code={type_code} (before_days=7, after_days=3)"
            )
        )

        if options["send"]:
            stats = run_rms_report_reminders()
            self.stdout.write(self.style.SUCCESS(f"Reminders run: {stats}"))
