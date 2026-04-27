from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ppaa_portal", "0019_portal_pr_flyer_visible_until"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalprflyer",
            name="video_url",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional YouTube or Instagram URL when the item is video-only or has a linked clip.",
                max_length=2048,
            ),
        ),
    ]
