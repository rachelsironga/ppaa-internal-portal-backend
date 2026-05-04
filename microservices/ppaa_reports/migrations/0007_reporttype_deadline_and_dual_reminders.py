from django.db import migrations, models


def seed_report_type_reminder_fields(apps, schema_editor):
    ReportType = apps.get_model("ppaa_reports", "ReportType")
    for report_type in ReportType.objects.all():
        old_days = getattr(report_type, "default_days_before_deadline", 7) or 0
        old_timing = getattr(report_type, "reminder_timing", "before") or "before"

        report_type.submission_deadline_days = getattr(report_type, "submission_deadline_days", 0) or 0
        report_type.before_reminder_days = old_days if old_timing == "before" else 0
        report_type.after_reminder_days = old_days if old_timing == "after" else 0
        report_type.save(
            update_fields=[
                "submission_deadline_days",
                "before_reminder_days",
                "after_reminder_days",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("ppaa_reports", "0006_add_reporttype_reminder_timing"),
    ]

    operations = [
        migrations.AddField(
            model_name="reporttype",
            name="submission_deadline_days",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Number of days after the selected reporting period ends before submission is due",
            ),
        ),
        migrations.AddField(
            model_name="reporttype",
            name="before_reminder_days",
            field=models.PositiveIntegerField(
                default=7,
                help_text="Send approaching-deadline reminder this many days before the computed deadline",
            ),
        ),
        migrations.AddField(
            model_name="reporttype",
            name="after_reminder_days",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Send overdue reminder this many days after the computed deadline",
            ),
        ),
        migrations.AddField(
            model_name="report",
            name="before_reminder_sent",
            field=models.BooleanField(
                default=False,
                help_text="Whether the before-deadline reminder has been sent",
            ),
        ),
        migrations.AddField(
            model_name="report",
            name="before_reminder_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="report",
            name="after_reminder_sent",
            field=models.BooleanField(
                default=False,
                help_text="Whether the overdue reminder has been sent",
            ),
        ),
        migrations.AddField(
            model_name="report",
            name="after_reminder_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(seed_report_type_reminder_fields, migrations.RunPython.noop),
    ]
