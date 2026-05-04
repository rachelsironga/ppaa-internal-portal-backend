from django.db import migrations, models


def forwards_set_workflow_staff(apps, schema_editor):
    MaoniSuggestionComment = apps.get_model("maoni", "MaoniSuggestionComment")
    MaoniSuggestionComment.objects.filter(message_type="WORKFLOW").update(thread_scope="STAFF")


class Migration(migrations.Migration):

    dependencies = [
        ("maoni", "0010_maonisuggestioncomment_message_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="maonisuggestioncomment",
            name="thread_scope",
            field=models.CharField(
                choices=[
                    ("CONTRIBUTOR", "Contributor-visible thread"),
                    ("STAFF", "Staff-only (handler & institutional reviewer)"),
                ],
                db_index=True,
                default="CONTRIBUTOR",
                max_length=20,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(forwards_set_workflow_staff, migrations.RunPython.noop),
    ]
