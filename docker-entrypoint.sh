#!/bin/sh
set -e
# Run app as non-root (UID 1000). When started as root (default), fix named-volume
# ownership for static/media then drop privileges — avoids Celery/Gunicorn root warnings.
if [ "$(id -u)" = "0" ]; then
  chown -R app:app /app/static /app/media 2>/dev/null || true
  # Maoni & SPISM share ``default`` with ``auth`` (User FKs). Secondary aliases are unused for those apps.
  if [ "$1" = "gunicorn" ]; then
    gosu app python manage.py migrate --noinput --fake-initial
  fi
  exec gosu app "$@"
fi
if [ "$1" = "gunicorn" ]; then
  python manage.py migrate --noinput --fake-initial
fi
exec "$@"
