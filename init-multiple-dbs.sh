#!/bin/bash
set -e

# Function to create database if it doesn't exist
create_database() {
  local db_name="$1"
  echo "Creating database: $db_name"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE $db_name'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db_name')\gexec
EOSQL
}

# Create both databases
create_database "mnh_approval_db"
create_database "analytics_db"

# Grant privileges
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
  GRANT ALL PRIVILEGES ON DATABASE mnh_approval_db TO $POSTGRES_USER;
  GRANT ALL PRIVILEGES ON DATABASE analytics_db TO $POSTGRES_USER;
EOSQL