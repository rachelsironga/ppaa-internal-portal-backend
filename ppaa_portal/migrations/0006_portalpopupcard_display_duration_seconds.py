from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ppaa_portal", "0005_portalpopupcard_gratitude_message"),
    ]

    operations = [
        # Remove legacy/unused column that isn't in the form/model.
        # This fixes NOT NULL insert failures when the column exists in DB.
        migrations.RunSQL(
            sql=(
                "ALTER TABLE portal_popup_cards "
                "DROP COLUMN IF EXISTS display_duration_seconds;"
            ),
            reverse_sql=(
                "ALTER TABLE portal_popup_cards "
                "ADD COLUMN IF NOT EXISTS display_duration_seconds INTEGER;"
            ),
        ),
    ]

