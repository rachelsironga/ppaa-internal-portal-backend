-- Add implementation submission columns to performance_activities.
-- Run this on the performance_dashboard database if migration 0004 was not applied.
--
-- Option 1 (Django):
--   python manage.py migrate ppaa_performance --database=performance_dashboard
--
-- Option 2 (psql / pgAdmin): connect to performance_dashboard_db and run this file.

ALTER TABLE performance_activities
  ADD COLUMN IF NOT EXISTS implementation_submitted_at TIMESTAMP WITH TIME ZONE NULL;

ALTER TABLE performance_activities
  ADD COLUMN IF NOT EXISTS implementation_submitted_by_id INTEGER NULL;

COMMENT ON COLUMN performance_activities.implementation_submitted_at IS
  'When officer submitted implementation (quarterly data/documents) as complete';
