#!/bin/sh
# Run every permission setup command (portal, Maoni, RMS, SPISM).
#
# From ppaa-internal-portal-backend with the stack up:
#   ./run_all_permissions.sh
#
# Or directly:
#   docker compose exec backend python manage.py sync_all_permissions

set -e
cd "$(dirname "$0")"

docker compose exec backend python manage.py sync_all_permissions
