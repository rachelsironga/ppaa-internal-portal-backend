"""Middleware for ppaa_performance app."""

_implementation_columns_ensured = False


def ensure_implementation_columns_middleware(get_response):
    """Add implementation_submitted_at/_by_id to performance_activities if missing (runs once per process)."""
    global _implementation_columns_ensured

    def middleware(request):
        global _implementation_columns_ensured
        if not _implementation_columns_ensured:
            _implementation_columns_ensured = True
            _ensure_implementation_columns()
        return get_response(request)

    return middleware


def _ensure_implementation_columns():
    from django.db import connections
    for db_alias in ("performance_dashboard", "default"):
        try:
            conn = connections[db_alias]
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'performance_activities'
                    AND column_name = 'implementation_submitted_at'
                    """
                )
                if cursor.fetchone() is not None:
                    continue
                cursor.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'performance_activities'
                    """
                )
                if cursor.fetchone() is None:
                    continue
                cursor.execute(
                    """
                    ALTER TABLE performance_activities
                    ADD COLUMN IF NOT EXISTS implementation_submitted_at TIMESTAMP WITH TIME ZONE NULL
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE performance_activities
                    ADD COLUMN IF NOT EXISTS implementation_submitted_by_id INTEGER NULL
                    """
                )
        except Exception:
            pass
