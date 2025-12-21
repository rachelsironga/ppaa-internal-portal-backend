# Generated migration for Supervisor model field changes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mnh_training', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='supervisor',
            name='user',
        ),
        migrations.RemoveField(
            model_name='supervisor',
            name='department',
        ),
        migrations.AddField(
            model_name='supervisor',
            name='user_guid',
            field=models.CharField(max_length=36, help_text='GUID reference to User from auth microservice'),
        ),
        migrations.AddField(
            model_name='supervisor',
            name='department_uid',
            field=models.CharField(max_length=36, help_text='UID reference to Department from auth microservice'),
        ),
    ]
