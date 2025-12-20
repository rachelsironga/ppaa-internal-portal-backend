# Generated migration for DepartmentAllocation and TrainingBatch field changes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mnh_training', '0002_supervisor_guid_uid_fields'),
    ]

    operations = [
        # DepartmentAllocation changes
        migrations.RemoveField(
            model_name='departmentallocation',
            name='department',
        ),
        migrations.AddField(
            model_name='departmentallocation',
            name='department_uid',
            field=models.CharField(default='', max_length=36, help_text='UID reference to Department from auth microservice'),
            preserve_default=False,
        ),
        
        # TrainingBatch changes
        migrations.RemoveField(
            model_name='trainingbatch',
            name='cancelled_by',
        ),
        migrations.AddField(
            model_name='trainingbatch',
            name='cancelled_by_guid',
            field=models.CharField(
                max_length=36,
                null=True,
                blank=True,
                help_text='GUID reference to User from auth microservice who cancelled this batch',
                db_index=True
            ),
        ),
    ]
