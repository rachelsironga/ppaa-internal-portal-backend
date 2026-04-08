# Generated migration for planned_quarters on Activity

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ppaa_performance", "0005_alter_activity_planned_value_alter_activity_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="activity",
            name="planned_quarters",
            field=models.JSONField(blank=True, default=list, help_text="Quarters when activity will be conducted, e.g. [1,2,3,4] for all quarters"),
        ),
    ]
