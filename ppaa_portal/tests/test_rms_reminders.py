"""Tests for RMS before/after deadline reminder emails."""

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

from django.core import mail
from django.test import TestCase, override_settings

from ppaa_auth.models import User
from ppaa_portal.models import (
    AuditLog,
    RmsReport,
    RmsReportType,
    RmsStakeholder,
)
from ppaa_portal.rms_reminders import (
    rms_report_reminder_recipient_email,
    run_rms_report_reminders,
)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class RmsReminderEmailTests(TestCase):
    databases = {"default"}

    def setUp(self):
        mail.outbox.clear()
        # Email task logs to Redis for auditing; tests do not require Redis.
        p = patch("ppaa_portal.tasks.redis_client", MagicMock())
        p.start()
        self.addCleanup(p.stop)

    def _create_user(self, username, email):
        return User.objects.create_user(
            username=username,
            email=email,
            password="testpass123",
            first_name="Test",
            last_name="User",
        )

    def _create_report_type(self, before_days=7, after_days=3):
        return RmsReportType.objects.create(
            name="Quarterly Test Type",
            code=f"QT{uuid.uuid4().hex[:6]}",
            frequency="quarterly",
            before_reminder_days=before_days,
            after_reminder_days=after_days,
        )

    def _create_report(self, owner, rt, deadline, **extra):
        fy = uuid.uuid4()
        return RmsReport.objects.create(
            reference_number=f"TST-{uuid.uuid4().hex[:8]}",
            title="Compliance report for testing reminders",
            report_type=rt,
            financial_year_uid=fy,
            financial_period_uid="",
            financial_period_uids=[],
            scope=extra.get("scope", "internal"),
            status=extra.get("status", "in_progress"),
            deadline_date=deadline,
            created_by=owner,
            updated_by=owner,
            stakeholder=extra.get("stakeholder"),
        )

    def test_before_reminder_sends_email_to_creator_and_sets_timestamp(self):
        owner = self._create_user("rms_before", "creator.before@example.com")
        rt = self._create_report_type(before_days=7, after_days=0)
        deadline = date(2026, 6, 30)
        # Window starts 2026-06-23; pick a day inside window before deadline
        today = date(2026, 6, 25)
        report = self._create_report(owner, rt, deadline)

        stats = run_rms_report_reminders(today=today)

        self.assertEqual(stats["before_sent"], 1)
        self.assertEqual(stats["after_sent"], 0)
        self.assertEqual(stats["errors"], 0)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn("creator.before@example.com", msg.to)
        self.assertIn("approaching", msg.subject.lower())
        self.assertIn("PPAA RMS", msg.subject)

        report.refresh_from_db()
        self.assertIsNotNone(report.reminder_before_sent_at)
        self.assertIsNone(report.reminder_after_sent_at)

        log = AuditLog.objects.filter(
            action="reminder_sent",
            object_id=str(report.uid),
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.changes.get("reminder_kind"), "before")

    def test_after_reminder_sends_email_and_sets_timestamp(self):
        owner = self._create_user("rms_after", "creator.after@example.com")
        rt = self._create_report_type(before_days=0, after_days=2)
        deadline = date(2026, 6, 10)
        today = date(2026, 6, 13)
        report = self._create_report(owner, rt, deadline)

        stats = run_rms_report_reminders(today=today)

        self.assertEqual(stats["before_sent"], 0)
        self.assertEqual(stats["after_sent"], 1)
        self.assertEqual(stats["errors"], 0)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn("creator.after@example.com", msg.to)
        self.assertIn("overdue", msg.subject.lower())

        report.refresh_from_db()
        self.assertIsNone(report.reminder_before_sent_at)
        self.assertIsNotNone(report.reminder_after_sent_at)

        log = AuditLog.objects.filter(
            action="reminder_sent",
            object_id=str(report.uid),
        ).first()
        self.assertEqual(log.changes.get("reminder_kind"), "after")

    def test_both_before_and_after_on_separate_runs(self):
        """Same report can receive before email first, then after email later."""
        owner = self._create_user("rms_both", "creator.both@example.com")
        rt = self._create_report_type(before_days=5, after_days=1)
        deadline = date(2026, 7, 15)
        report = self._create_report(owner, rt, deadline)

        # Day inside before window (deadline - 5 = July 10)
        stats1 = run_rms_report_reminders(today=date(2026, 7, 12))
        self.assertEqual(stats1["before_sent"], 1)
        self.assertEqual(stats1["after_sent"], 0)
        self.assertEqual(len(mail.outbox), 1)

        mail.outbox.clear()

        # After deadline + 1 day
        stats2 = run_rms_report_reminders(today=date(2026, 7, 17))
        self.assertEqual(stats2["before_sent"], 0)
        self.assertEqual(stats2["after_sent"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("overdue", mail.outbox[0].subject.lower())

        report.refresh_from_db()
        self.assertIsNotNone(report.reminder_before_sent_at)
        self.assertIsNotNone(report.reminder_after_sent_at)

    def test_skips_submitted_report(self):
        owner = self._create_user("rms_done", "done@example.com")
        rt = self._create_report_type(before_days=7, after_days=3)
        report = self._create_report(
            owner,
            rt,
            date(2026, 8, 1),
            status="submitted",
        )

        stats = run_rms_report_reminders(today=date(2026, 7, 28))
        self.assertEqual(stats["skipped_submitted"], 1)
        self.assertEqual(stats["before_sent"], 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_external_scope_uses_stakeholder_email(self):
        owner = self._create_user("rms_int", "internal@example.com")
        stakeholder = RmsStakeholder.objects.create(
            name="Ext Org",
            organization_type="ngo",
            email="stakeholder@external.org",
        )
        rt = self._create_report_type(before_days=3, after_days=0)
        deadline = date(2026, 9, 10)
        report = self._create_report(
            owner,
            rt,
            deadline,
            scope="external",
            stakeholder=stakeholder,
        )

        self.assertEqual(
            rms_report_reminder_recipient_email(report),
            "stakeholder@external.org",
        )

        # First day of before window: deadline - 3 = Sept 7
        stats = run_rms_report_reminders(today=date(2026, 9, 8))
        self.assertEqual(stats["before_sent"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("stakeholder@external.org", mail.outbox[0].to)
