from django.apps import AppConfig


class PpaaPerformanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "microservices.ppaa_performance"
    verbose_name = "SPISM / Performance dashboard"
    # Avoid clashing with the `ppaa_performance` app label.
    label = "micro_ppaa_performance"
