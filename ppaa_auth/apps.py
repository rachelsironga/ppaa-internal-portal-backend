from django.apps import AppConfig


<<<<<<< HEAD
class PPAAAuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ppaa_auth"

    def ready(self):
        import ppaa_auth.signals  # noqa: F401
=======
<<<<<<<< HEAD:.venv/lib/python3.12/site-packages/tutorial/quickstart/apps.py
class QuickstartConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'quickstart'
========
class PPAAAuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ppaa_auth'

>>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92:ppaa_auth/apps.py
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
