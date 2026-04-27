from django.apps import AppConfig


class PPAAAuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ppaa_auth"

    def ready(self):
        import ppaa_auth.signals  # noqa: F401
