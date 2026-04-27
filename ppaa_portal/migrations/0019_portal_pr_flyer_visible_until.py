from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ppaa_portal", "0018_portal_pr_flyer"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalprflyer",
            name="visible_until",
            field=models.DateTimeField(
                blank=True,
                help_text="If set, hidden from dashboards and public image URL after this time (server clock).",
                null=True,
            ),
        ),
    ]
