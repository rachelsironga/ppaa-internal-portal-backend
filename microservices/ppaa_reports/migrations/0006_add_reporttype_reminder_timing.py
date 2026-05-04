from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ppaa_reports', '0005_add_comment_mentions_and_read_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='reporttype',
            name='reminder_timing',
            field=models.CharField(
                max_length=10,
                choices=[('before', 'Before deadline'), ('after', 'After deadline')],
                default='before',
                help_text='Whether reminders are sent before or after the deadline',
            ),
        ),
    ]

