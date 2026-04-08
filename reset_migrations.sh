#!/bin/bash

# WARNING: This script will delete all migrations and drop all database tables
# Make sure you have a backup if you need to preserve data

echo "⚠️  WARNING: This will delete all migrations and database tables!"
echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
sleep 5

cd "$(dirname "$0")"

# Delete all migration files except __init__.py
echo "🗑️  Deleting migration files..."
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete

# Drop all tables from database
echo "🗑️  Dropping all database tables..."
python manage.py shell << EOF
from django.db import connection
cursor = connection.cursor()
cursor.execute("DROP SCHEMA public CASCADE;")
cursor.execute("CREATE SCHEMA public;")
cursor.execute("GRANT ALL ON SCHEMA public TO postgres;")
cursor.execute("GRANT ALL ON SCHEMA public TO public;")
EOF

# Recreate migrations
echo "📝 Creating new migrations..."
python manage.py makemigrations

echo "✅ Done! Run 'python manage.py migrate' to apply migrations."

