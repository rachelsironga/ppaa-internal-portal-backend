# Generated manually for Maoni workflow UI (department receipt date).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("maoni", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="maonisuggestion",
            name="department_received_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="When staff first opened the case (Submitted → Under handler review) for this department queue.",
                null=True,
            ),
        ),
    ]
