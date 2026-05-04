from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("maoni", "0007_relax_legacy_closure_file_key_not_null"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            DECLARE
                col record;
            BEGIN
                FOR col IN
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'maoni_maonisuggestion'
                      AND column_name LIKE 'closure_%'
                      AND is_nullable = 'NO'
                LOOP
                    EXECUTE format(
                        'ALTER TABLE public.maoni_maonisuggestion ALTER COLUMN %I DROP NOT NULL',
                        col.column_name
                    );
                END LOOP;
            END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

