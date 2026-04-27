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
        # Dedicated (non-default) DBs: only their app may migrate there.
        if self.database_name != "default" and db == self.database_name:
            return False
        return None


# Concrete router implementations

class RmsRouter(BaseAppRouter):
    """
    Reserved for app label ``rms`` if introduced. RMS tables currently live under
    ``ppaa_portal`` on the default DB; the alias matches DATABASES['reports_management_db'].
    """
    route_app_labels = {'rms'}
    database_name = 'reports_management_db'


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
        # Only ``default`` hosts the main project schema (incl. auth for User FKs).
        # Secondary DBs are handled by dedicated routers above; do not duplicate
        # contrib apps onto every alias (that breaks migrate and FK targets).
        if db == "default":
            return True
        return False


# Router instances
# Maoni (``maoni``) and SPISM (``ppaa_performance``) use ``default``: they FK to
# ``auth.User``; a separate DB alias would require ``auth_user`` there too.
ROUTERS = [
    RmsRouter(),
    DefaultRouter(),
]