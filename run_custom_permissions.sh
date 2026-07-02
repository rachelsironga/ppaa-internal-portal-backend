#!/bin/sh
# Create internal-portal custom permissions and sync Django groups (staff, content_editor, ICT, etc.).
#
# Run from ppaa-internal-portal-backend with the stack up:
#   ./run_custom_permissions.sh
#
# To run ALL permission commands (portal + Maoni + RMS + SPISM):
#   ./run_all_permissions.sh
#
# Or directly:
#   docker compose exec backend python manage.py custom_permissions

set -e
cd "$(dirname "$0")"

docker compose exec backend python manage.py custom_permissions
