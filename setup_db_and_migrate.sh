#!/bin/bash
# Create PostgreSQL database (if missing) and run Django migrations.
# Use from backend root. For Docker Postgres, use host localhost and port 5433.

set -e
cd "$(dirname "$0")"

# Load only POSTGRES_* from .env (avoids errors from other .env lines)
if [ -f .env ]; then
  while IFS= read -r line; do
    case "$line" in
      POSTGRES_DB_NAME=*) export "${line%%#*}";;
      POSTGRES_DB_USER=*) export "${line%%#*}";;
      POSTGRES_DB_PWD=*) export "${line%%#*}";;
      POSTGRES_DB_HOST=*) export "${line%%#*}";;
      POSTGRES_DB_PORT=*) export "${line%%#*}";;
    esac
  done < .env
fi

# Strip optional double quotes from env vars
strip_quotes() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

# Database connection (defaults match docker-compose)
DB_NAME=$(strip_quotes "${POSTGRES_DB_NAME:-ppaa_portal_db}")
DB_USER=$(strip_quotes "${POSTGRES_DB_USER:-postgres}")
DB_PWD=$(strip_quotes "${POSTGRES_DB_PWD:-P@ssw0rd}")
DB_HOST=$(strip_quotes "${POSTGRES_DB_HOST:-localhost}")
DB_PORT=$(strip_quotes "${POSTGRES_DB_PORT:-5433}")

export PGPASSWORD="$DB_PWD"

echo "Using DB: $DB_NAME @ $DB_HOST:$DB_PORT (user: $DB_USER)"

# 1) Create database if it doesn't exist (connect to 'postgres' to run CREATE DATABASE)
echo "Ensuring database '$DB_NAME' exists..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 \
  || psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME;"
echo "Database OK."

# 2) Run migrations
echo "Running Django migrations..."
if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
  . venv/bin/activate
elif [ -d ".venv" ] && [ -f ".venv/bin/activate" ]; then
  . .venv/bin/activate
fi

MIGRATE_OK=0
if command -v python3 >/dev/null 2>&1; then
  python3 manage.py migrate && MIGRATE_OK=1
else
  python manage.py migrate && MIGRATE_OK=1
fi

echo ""
if [ "$MIGRATE_OK" = "1" ]; then
  echo "Done. All migrations applied."
else
  echo "Migrations could not run (activate venv first). Run manually:"
  echo "  source venv/bin/activate   # or your venv path"
  echo "  python manage.py migrate"
  echo ""
fi
echo "--- pgAdmin: connect to see database and tables ---"
echo "  1. Open pgAdmin, right-click Servers → Register → Server"
echo "  2. General tab: Name = PPAA Portal (any name)"
echo "  3. Connection tab:"
echo "       Host = $DB_HOST"
echo "       Port = $DB_PORT"
echo "       Username = $DB_USER"
echo "       Password = (your POSTGRES_DB_PWD from .env)"
echo "  4. Save. Then in the tree: Servers → PPAA Portal → Databases → $DB_NAME"
echo "  5. Expand: $DB_NAME → Schemas → public → Tables"
echo "     You should see performance_objectives, performance_targets, etc. after running migrations."
echo "---"
