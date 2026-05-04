#!/bin/bash
# Create all project databases so they appear in pgAdmin.
# Run from backend root: ./create_all_project_dbs.sh
# Then in pgAdmin: connect to your server and refresh Databases – you'll see all three.

set -e
cd "$(dirname "$0")"

strip_quotes() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

# Load from .env
if [ -f .env ]; then
  while IFS= read -r line; do
    case "$line" in
      POSTGRES_DB_NAME=*) export "${line%%#*}";;
      POSTGRES_DB_USER=*) export "${line%%#*}";;
      POSTGRES_DB_PWD=*) export "${line%%#*}";;
      POSTGRES_DB_HOST=*) export "${line%%#*}";;
      POSTGRES_DB_PORT=*) export "${line%%#*}";;
      MAONI_DB_NAME=*) export "${line%%#*}";;
      PERFORMANCE_DASHBOARD_DB_NAME=*) export "${line%%#*}";;
      REPORTS_DB_NAME=*) export "${line%%#*}";;
    esac
  done < .env
fi

DB_USER=$(strip_quotes "${POSTGRES_DB_USER:-postgres}")
DB_PWD=$(strip_quotes "${POSTGRES_DB_PWD:-}")
DB_HOST=$(strip_quotes "${POSTGRES_DB_HOST:-localhost}")
DB_PORT=$(strip_quotes "${POSTGRES_DB_PORT:-5432}")

# All three project databases (same as settings.py)
MAIN_DB=$(strip_quotes "${POSTGRES_DB_NAME:-ppaa_portal_db}")
MAONI_DB=$(strip_quotes "${MAONI_DB_NAME:-maoni_db}")
PERF_DB=$(strip_quotes "${PERFORMANCE_DASHBOARD_DB_NAME:-performance_dashboard_db}")
REPORTS_DB=$(strip_quotes "${REPORTS_DB_NAME:-ppaa_reports}")

export PGPASSWORD="$DB_PWD"

create_if_missing() {
  local name="$1"
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = '$name'" | grep -q 1 \
    || psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE \"$name\";"
  echo "  $name"
}

echo "Creating project databases at $DB_HOST:$DB_PORT (user: $DB_USER)..."
create_if_missing "$MAIN_DB"
create_if_missing "$MAONI_DB"
create_if_missing "$PERF_DB"
create_if_missing "$REPORTS_DB"
echo "Done. Open pgAdmin, connect to this server, refresh 'Databases' – you should see: $MAIN_DB, $MAONI_DB, $PERF_DB, $REPORTS_DB"
