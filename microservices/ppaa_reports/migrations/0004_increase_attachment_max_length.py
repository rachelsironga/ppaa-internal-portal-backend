# Generated manually - increase attachment max_length for MinIO paths

import django.core.validators
from django.db import migrations, models

import microservices.ppaa_reports.models


class Migration(migrations.Migration):

    dependencies = [
        ('ppaa_reports', '0003_update_report_directory_relations'),
    ]

    operations = [
        migrations.AlterField(
            model_name='report',
            name='attachment',
            field=models.FileField(
                blank=True,
                help_text='Report document attachment',
                max_length=500,
                null=True,
                upload_to=microservices.ppaa_reports.models.report_attachment_path,
                validators=[
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip']
                    )
                ],
            ),
        ),
    ]
