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
<<<<<<< HEAD
    
    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.database_name
        return None  # Let other routers decide
    
=======

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.database_name
        return None

>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.database_name
        return None
<<<<<<< HEAD
    
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
=======

    def allow_relation(self, obj1, obj2, **hints):
        allowed_dbs = ('default', self.database_name)
        if obj1._state.db in allowed_dbs and obj2._state.db in allowed_dbs:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.route_app_labels:
            return db == self.database_name
        elif db == self.database_name:
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
            return False
        return None


<<<<<<< HEAD
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
=======
class DefaultRouter:
    """Default router as fallback. Last in the chain."""
    # Apps that use a dedicated DB: never migrate these on 'default' (they run on their own DB only).
    DEDICATED_DB_APPS = frozenset({"ppaa_maoni", "ppaa_performance", "ppaa_reports"})

    def db_for_read(self, model, **hints):
        return 'default'

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        if obj1._state.db == 'default' and obj2._state.db == 'default':
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Never run dedicated-DB app migrations on default (they use maoni / performance_dashboard).
        if db == 'default' and app_label in self.DEDICATED_DB_APPS:
            return False
        if db == 'default':
            return True
        # performance_dashboard: SPISM uses same auth as portal (user ids only, no FK to auth_user)
        if db == 'performance_dashboard' and app_label in (
            'auth', 'contenttypes', 'sessions', 'admin', 'token_blacklist', 'ppaa_auth'
        ):
            return False
        return False


class MaoniRouter(BaseAppRouter):
    route_app_labels = {"ppaa_maoni"}
    database_name = "maoni"


# SPISM uses same auth as portal (user ids stored as IntegerField; no auth_user in performance_dashboard).
# So no shared apps needed on performance_dashboard.
SHARED_APPS_FOR_PERFORMANCE_DB = frozenset()


class PerformanceDashboardRouter(BaseAppRouter):
    """Performance Dashboard: dedicated DB (same pattern as Maoni)."""
    route_app_labels = {"ppaa_performance"}
    database_name = "performance_dashboard"

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db != self.database_name:
            return None
        if app_label in self.route_app_labels:
            return True
        # Let DefaultRouter decide for shared apps (auth_user etc.) so they run on this DB too
        if app_label in SHARED_APPS_FOR_PERFORMANCE_DB:
            return None
        return False


SHARED_APPS_FOR_REPORTS_DB = frozenset({
    "auth", "contenttypes", "sessions", "admin", "token_blacklist", "ppaa_auth"
})


class ReportsRouter(BaseAppRouter):
    """PPAA Reports / RMS: dedicated DB."""
    route_app_labels = {"ppaa_reports"}
    database_name = "ppaa_reports"

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db != self.database_name:
            return None
        if app_label in self.route_app_labels or app_label in SHARED_APPS_FOR_REPORTS_DB:
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
            return True
        return False


<<<<<<< HEAD
# Router instances
# Maoni (``maoni``) and SPISM (``ppaa_performance``) use ``default``: they FK to
# ``auth.User``; a separate DB alias would require ``auth_user`` there too.
ROUTERS = [
    RmsRouter(),
    DefaultRouter(),
]
=======
ROUTERS = [
    MaoniRouter(),
    PerformanceDashboardRouter(),
    ReportsRouter(),
    DefaultRouter(),
]
>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
