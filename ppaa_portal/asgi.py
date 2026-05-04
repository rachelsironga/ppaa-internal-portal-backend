"""
<<<<<<< HEAD
ASGI config for ppaa_portal project entrypoint.
=======
<<<<<<<< HEAD:.venv/lib/python3.12/site-packages/tutorial/asgi.py
ASGI config for tutorial project.
========
ASGI config for ppaa_portal project.
>>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92:ppaa_portal/asgi.py

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
"""

import os

from django.core.asgi import get_asgi_application

<<<<<<< HEAD
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ppaa_portal.settings")
=======
<<<<<<<< HEAD:.venv/lib/python3.12/site-packages/tutorial/asgi.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tutorial.settings')
========
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ppaa_portal.settings')
>>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92:ppaa_portal/asgi.py
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92

application = get_asgi_application()
