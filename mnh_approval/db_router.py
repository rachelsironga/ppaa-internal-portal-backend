"""
Centralized database routers configuration.
All database routers are defined here.
"""

class BaseAppRouter:
    """
    Base database router for apps with dedicated databases.
    """
    route_app_labels = set()  # Override in subclasses
    database_name = ''        # Override in subclasses
    
    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.database_name
        return None  # Let other routers decide
    
    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.database_name
        return None
    
    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if both objects are in allowed databases.
        This prevents cross-database foreign keys which Django doesn't support.
        """
        allowed_dbs = ('default', self.database_name)
        
        if obj1._state.db in allowed_dbs and obj2._state.db in allowed_dbs:
            return True
        return None  # Let other routers decide
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Control where migrations run.
        """
        if app_label in self.route_app_labels:
            return db == self.database_name
        elif db == self.database_name:
            # No other apps should migrate to this database
            return False
        return None


# Concrete router implementations
class AnalyticalRouter(BaseAppRouter):
    route_app_labels = {'mnh_analytical'}
    database_name = 'analytical'
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # mnh_analytical uses managed=False models, so no migrations needed
        if db == 'analytical':
            return False
        if app_label == 'mnh_analytical':
            return False
        return None


class TrainingRouter(BaseAppRouter):
    route_app_labels = {'mnh_training'}
    database_name = 'training'
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # mnh_training migrations go to training database
        if app_label == 'mnh_training':
            return db == 'training'
        # Only Django core apps can migrate to training (for django_migrations table)
        if db == 'training':
            if app_label in ('contenttypes', 'sessions'):
                return True
            return False
        return None


class IctAssetRouter(BaseAppRouter):
    route_app_labels = {'ict_assets'}
    database_name = 'ict_assets'
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # ict_assets migrations go to ict_assets database
        if app_label == 'ict_assets':
            return db == 'ict_assets'
        # Only Django core apps can migrate to ict_assets (for django_migrations table)
        if db == 'ict_assets':
            if app_label in ('contenttypes', 'sessions'):
                return True
            return False
        return None


class DefaultRouter:
    """
    Default router as fallback.
    This should be the last router in the chain.
    """
    def db_for_read(self, model, **hints):
        return 'default'
    
    def db_for_write(self, model, **hints):
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        # Only decide for objects in default database
        if obj1._state.db == 'default' and obj2._state.db == 'default':
            return True
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Default database gets everything
        if db == 'default':
            return True
        # Other databases can have Django built-in apps and sessions
        if app_label in ('auth', 'contenttypes', 'sessions', 'admin', 'token_blacklist'):
            return True
        # Everything else goes to default
        return False


# Router instances
ROUTERS = [
    AnalyticalRouter(),
    TrainingRouter(),
    IctAssetRouter(),
    DefaultRouter(),
]