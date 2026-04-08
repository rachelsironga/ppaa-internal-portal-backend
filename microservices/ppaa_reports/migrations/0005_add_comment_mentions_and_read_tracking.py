# Generated manually for comment mentions_directory and ReportCommentRead

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ppaa_reports', '0004_increase_attachment_max_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='reportcomment',
            name='mentions_directory',
            field=models.BooleanField(
                default=False,
                help_text="When True, ED/RMS_REPORT_MANAGER is directing this message to the report's directory"
            ),
        ),
        migrations.CreateModel(
            name='ReportCommentRead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_read_at', models.DateTimeField(help_text="When the user last viewed this report's comments")),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comment_reads', to='ppaa_reports.report')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='report_comment_reads', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'ppaa_reports_comment_read',
                'verbose_name': 'Report Comment Read',
                'verbose_name_plural': 'Report Comment Reads',
                'unique_together': {('report', 'user')},
            },
        ),
    ]
