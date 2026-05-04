# Generated manually — move contributor-visible workflow audit rows out of STAFF.

from django.db import migrations
from django.db.models import Q


def forwards(apps, schema_editor):
    MaoniSuggestionComment = apps.get_model("maoni", "MaoniSuggestionComment")
    prefixes = (
        "[CLOSED REJECTED]",
        "[CLOSED_REJECTED]",
        "[CLOSED APPROVED]",
        "[CLOSED_APPROVED]",
        "[HANDLER RESPONDED TO CONTRIBUTOR]",
        "[HANDLER_RESPONDED_TO_CONTRIBUTOR]",
        "[UNDER HANDLER REVIEW]",
        "[UNDER_HANDLER_REVIEW]",
    )
    q = Q()
    for p in prefixes:
        q |= Q(comment__istartswith=p)
    MaoniSuggestionComment.objects.filter(
        message_type="WORKFLOW",
        thread_scope="STAFF",
    ).filter(q).update(thread_scope="CONTRIBUTOR")


def backwards(apps, schema_editor):
    # Do not move rows back to STAFF; would hide already-visible history from contributors.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("maoni", "0011_maonisuggestioncomment_thread_scope"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
