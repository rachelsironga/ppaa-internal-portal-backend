from django.apps import AppConfig


class IctAssetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'microservices.ict_assets'
    
    def ready(self):
        import microservices.ict_assets.signals
