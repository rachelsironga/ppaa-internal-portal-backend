# Add missing gratitude_message column to portal_popup_cards (raw SQL so it applies even if table already existed)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ppaa_portal', '0004_portalpopupcard'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE portal_popup_cards ADD COLUMN IF NOT EXISTS gratitude_message TEXT;",
            reverse_sql="ALTER TABLE portal_popup_cards DROP COLUMN IF EXISTS gratitude_message;",
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='portalpopupcard',
                    name='gratitude_message',
                    field=models.TextField(blank=True, null=True),
                ),
            ],
        ),
    ]
