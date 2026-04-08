#!/bin/sh
# Add missing planned_quarters column to performance_activities (performance_dashboard DB).
# Run from ppaa-internal-portal-backend with your venv activated:
#   ./run_add_planned_quarters.sh
# Or: source venv/bin/activate && python manage.py add_planned_quarters_column

set -e
cd "$(dirname "$0")"

if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
  . venv/bin/activate
elif [ -d ".venv" ] && [ -f ".venv/bin/activate" ]; then
  . .venv/bin/activate
fi

echo "Running migration to add planned_quarters column..."
if command -v python3 >/dev/null 2>&1; then
  python3 manage.py migrate ppaa_performance --database=performance_dashboard
else
  python manage.py migrate ppaa_performance --database=performance_dashboard
fi

# If migrate didn't add the column (e.g. migration already marked applied), run the command
if command -v python3 >/dev/null 2>&1; then
  python3 manage.py add_planned_quarters_column 2>/dev/null || true
else
  python manage.py add_planned_quarters_column 2>/dev/null || true
fi

echo "Done. Column planned_quarters should exist on performance_activities."
