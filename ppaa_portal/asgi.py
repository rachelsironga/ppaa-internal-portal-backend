"""
ASGI config for ppaa_portal project entrypoint.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ppaa_portal.settings")

application = get_asgi_application()
