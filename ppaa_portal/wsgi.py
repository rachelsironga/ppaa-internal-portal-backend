"""
<<<<<<< HEAD
WSGI config for ppaa_portal project entrypoint.

It exposes the WSGI callable as a module-level variable named ``application``.
=======
<<<<<<<< HEAD:.venv/lib/python3.12/site-packages/tutorial/wsgi.py
WSGI config for tutorial project.
========
WSGI config for ppaa_portal project.
>>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92:ppaa_portal/wsgi.py

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
"""

import os

from django.core.wsgi import get_wsgi_application

<<<<<<< HEAD
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ppaa_portal.settings")
=======
<<<<<<<< HEAD:.venv/lib/python3.12/site-packages/tutorial/wsgi.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tutorial.settings')
========
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ppaa_portal.settings')
>>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92:ppaa_portal/wsgi.py
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92

application = get_wsgi_application()
