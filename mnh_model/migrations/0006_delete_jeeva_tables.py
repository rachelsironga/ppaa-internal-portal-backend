from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('mnh_model', '0005_alter_daterange_options_approvalrequest_date_range_and_more'),  # update this to your last migration
    ]

    operations = [
        migrations.RunSQL("DROP TABLE IF EXISTS mnh_model_jeevapermission CASCADE;"),
        migrations.RunSQL("DROP TABLE IF EXISTS mnh_model_jeevarole CASCADE;"),
    ]
