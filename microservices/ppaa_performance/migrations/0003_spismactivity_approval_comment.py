# Generated manually — persist planning return comments on activities.

from django.db import migrations, models


def backfill_return_comments_from_audit(apps, schema_editor):
    Activity = apps.get_model("micro_ppaa_performance", "SpismActivity")
    Log = apps.get_model("micro_ppaa_performance", "SpismPerformanceAuditLog")
    for act in Activity.objects.filter(status="RETURNED").iterator():
        if (act.approval_comment or "").strip():
            continue
        hit = (
            Log.objects.filter(
                entity_type="activity",
                entity_uid=act.uid,
                action__iexact="RETURN",
            )
            .exclude(comment="")
            .order_by("-created_at")
            .first()
        )
        if hit and hit.comment:
            Activity.objects.filter(pk=act.pk).update(approval_comment=hit.comment[:20000])


class Migration(migrations.Migration):

    dependencies = [
        ("micro_ppaa_performance", "0002_spism_core"),
    ]

    operations = [
        migrations.AddField(
            model_name="spismactivity",
            name="approval_comment",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.RunPython(backfill_return_comments_from_audit, migrations.RunPython.noop),
    ]
