-- Run this script in pgAdmin on your performance_dashboard database
-- (the same DB that has performance_objectives, performance_targets, etc.)
-- This creates the Financial Year table if the Django migration hasn't been run.

-- Create sequence for primary key
CREATE SEQUENCE IF NOT EXISTS ppaa_performance_financialyear_id_seq;

-- Create table (matches ppaa_performance.migrations.0002_financialyear)
CREATE TABLE IF NOT EXISTS performance_financial_years (
    id BIGINT NOT NULL DEFAULT nextval('ppaa_performance_financialyear_id_seq'::regclass) PRIMARY KEY,
    uid UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NULL,
    updated_at TIMESTAMP WITH TIME ZONE NULL,
    deleted_at TIMESTAMP WITH TIME ZONE NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id INTEGER NULL,
    updated_by_id INTEGER NULL,
    deleted_by_id INTEGER NULL,
    name VARCHAR(9) NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL
);

-- Own the sequence by the table (optional, for consistency with Django)
ALTER SEQUENCE ppaa_performance_financialyear_id_seq OWNED BY performance_financial_years.id;

-- So Django's migrate recognizes this table, record the migration as applied (optional):
-- Only do this if you are NOT going to run "python manage.py migrate --database=performance_dashboard" later.
-- INSERT INTO django_migrations (app, name, applied) VALUES ('ppaa_performance', '0002_financialyear', NOW())
-- ON CONFLICT DO NOTHING;

COMMENT ON TABLE performance_financial_years IS 'Financial years for Setup & Configuration. Format: YYYY/YYYY e.g. 2025/2026';
