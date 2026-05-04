-- Create maoni_db database for ppaa_maoni microservice
-- Run this in pgAdmin Query Tool or psql

-- Create database if it doesn't exist
SELECT 'CREATE DATABASE maoni_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'maoni_db')\gexec

-- Grant privileges to your user (replace 'Raquel' with your PostgreSQL username if different)
GRANT ALL PRIVILEGES ON DATABASE maoni_db TO Raquel;

-- Connect to the new database and grant schema privileges
\c maoni_db

-- Grant privileges on public schema
GRANT ALL PRIVILEGES ON SCHEMA public TO Raquel;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO Raquel;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO Raquel;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO Raquel;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO Raquel;
