-- Add planned_value_label, planned_financial_year, planned_quarter to performance_activities
-- Run this on the performance_dashboard database if migration 0003 was not applied.
--
-- Preferred: from project root with venv active run:
--   python manage.py migrate ppaa_performance --database=performance_dashboard
--
-- If you run this SQL manually instead, then record the migration so Django skips it next time:
--   INSERT INTO django_migrations (app, name, applied) VALUES ('ppaa_performance', '0003_activity_planned_fields', NOW());

ALTER TABLE performance_activities
  ADD COLUMN IF NOT EXISTS planned_value_label VARCHAR(255) NULL;

ALTER TABLE performance_activities
  ADD COLUMN IF NOT EXISTS planned_financial_year VARCHAR(9) NULL;

ALTER TABLE performance_activities
  ADD COLUMN IF NOT EXISTS planned_quarter SMALLINT NULL;
