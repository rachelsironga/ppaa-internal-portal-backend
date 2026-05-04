from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("ppaa_reports", "0007_reporttype_deadline_and_dual_reminders"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reportaudittrail",
            name="report",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="audit_trail",
                to="ppaa_reports.report",
            ),
        ),
        migrations.AddField(
            model_name="reportaudittrail",
            name="entity_name",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="reportaudittrail",
            name="entity_type",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="reportaudittrail",
            name="entity_uid",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
