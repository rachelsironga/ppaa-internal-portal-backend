from django.db import migrations


class Migration(migrations.Migration):
    """
    Legacy MNH DBs may have closure_* columns on maoni_maonisuggestion.
    PPAA installs from 0001_initial never had closure_file_key — skip safely.
    """

    dependencies = [
        ("maoni", "0006_alter_maonisuggestion_status"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'maoni_maonisuggestion'
                      AND column_name = 'closure_file_key'
                ) THEN
                    ALTER TABLE public.maoni_maonisuggestion
                    ALTER COLUMN closure_file_key DROP NOT NULL;
                END IF;
            END $$;
            """,
            reverse_sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'maoni_maonisuggestion'
                      AND column_name = 'closure_file_key'
                ) THEN
                    ALTER TABLE public.maoni_maonisuggestion
                    ALTER COLUMN closure_file_key SET NOT NULL;
                END IF;
            END $$;
            """,
        ),
    ]

