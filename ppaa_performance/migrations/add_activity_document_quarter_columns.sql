-- Add quarter and financial_year to performance_activity_documents
-- Run this on the performance_dashboard database if migration 0008 was not applied.
--
-- In pgAdmin: connect to the performance_dashboard database and run this script.
--
-- Preferred: from project root with venv active run:
--   python manage.py migrate ppaa_performance --database=performance_dashboard
--
-- If you run this SQL manually instead, record the migration so Django skips it:
--   INSERT INTO django_migrations (app, name, applied) VALUES ('ppaa_performance', '0008_activitydocument_quarter_financial_year', NOW());

ALTER TABLE performance_activity_documents
  ADD COLUMN IF NOT EXISTS quarter SMALLINT NULL;

ALTER TABLE performance_activity_documents
  ADD COLUMN IF NOT EXISTS financial_year VARCHAR(9) NULL;

COMMENT ON COLUMN performance_activity_documents.quarter IS 'Quarter this document relates to (1-4)';
COMMENT ON COLUMN performance_activity_documents.financial_year IS 'Financial year this document relates to (e.g. 2024/2025)';
