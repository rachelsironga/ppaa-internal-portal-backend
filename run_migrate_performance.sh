#!/bin/sh
# Run this from ppaa-internal-portal-backend directory to create Performance Dashboard tables.
# Performance tables live in ppaa_portal (migration 0007). Activate venv if needed, then run:
#   python manage.py migrate ppaa_portal

set -e
cd "$(dirname "$0")"

if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
  . venv/bin/activate
elif [ -d ".venv" ] && [ -f ".venv/bin/activate" ]; then
  . .venv/bin/activate
fi

if command -v python3 >/dev/null 2>&1; then
  python3 manage.py migrate ppaa_portal
else
  python manage.py migrate ppaa_portal
fi
echo "Done. performance_objectives and related tables should now exist."
