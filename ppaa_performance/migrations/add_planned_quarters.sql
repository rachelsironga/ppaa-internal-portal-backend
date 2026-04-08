-- Add planned_quarters to performance_activities (list of quarters e.g. [1,2,3,4])
-- Run this on the performance_dashboard database if migration 0007 was not applied.
--
-- In pgAdmin: connect to the performance_dashboard database and run this script.
--
-- Preferred: from project root with venv active run:
--   python manage.py migrate ppaa_performance --database=performance_dashboard
--
-- If you run this SQL manually instead, then record the migration so Django skips it:
--   INSERT INTO django_migrations (app, name, applied) VALUES ('ppaa_performance', '0007_activity_planned_quarters', NOW());

ALTER TABLE performance_activities
  ADD COLUMN IF NOT EXISTS planned_quarters JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN performance_activities.planned_quarters IS 'Quarters when activity will be conducted, e.g. [1,2,3,4] for all quarters';
