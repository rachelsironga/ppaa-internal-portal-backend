from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ppaa_auth", "0004_remove_user_dob"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="description",
            field=models.TextField(blank=True, null=True),
        ),
    ]

