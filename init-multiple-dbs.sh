#!/bin/bash
set -e

# Create database if it doesn't exist (POSTGRES_DB=ppaa_portal_db is already created by the image)
create_database() {
  local db_name="$1"
  echo "Creating database: $db_name"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = '$db_name'" | grep -q 1 \
    || psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $db_name;"
}

<<<<<<< HEAD
# Create both databases
create_database "ppaa_internal_portal"
create_database "performance_dashboard_db"
create_database "maoni_db"
create_database "reports_management_db"

# Grant privileges
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
  GRANT ALL PRIVILEGES ON DATABASE ppaa_internal_portal TO $POSTGRES_USER;
  GRANT ALL PRIVILEGES ON DATABASE performance_dashboard_db TO $POSTGRES_USER;
  GRANT ALL PRIVILEGES ON DATABASE maoni_db TO $POSTGRES_USER;
  GRANT ALL PRIVILEGES ON DATABASE reports_management_db TO $POSTGRES_USER;
=======
# Maoni Microservice Database (ppaa_portal_db already exists from POSTGRES_DB)
create_database "maoni_db"
# Performance Dashboard (same pattern as Maoni – dedicated DB)
create_database "performance_dashboard_db"
# PPAA Reports dedicated database
create_database "ppaa_reports"

# Grant privileges
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d postgres <<-EOSQL
  GRANT ALL PRIVILEGES ON DATABASE ppaa_portal_db TO $POSTGRES_USER;
  GRANT ALL PRIVILEGES ON DATABASE maoni_db TO $POSTGRES_USER;
  GRANT ALL PRIVILEGES ON DATABASE performance_dashboard_db TO $POSTGRES_USER;
  GRANT ALL PRIVILEGES ON DATABASE ppaa_reports TO $POSTGRES_USER;
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
EOSQL