"""
Centralized multi-DB routing.

Aliases must match ``ppaa_portal.db_config.build_databases``:
  - default
  - maoni_db
  - performance_dashboard_db
  - reports_management_db
"""


class BaseAppRouter:
    """Route a set of app labels to one dedicated database alias."""

    route_app_labels = frozenset()
    database_name = ""

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.database_name
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.database_name
        return None

    def allow_relation(self, obj1, obj2, **hints):
        allowed_dbs = {"default", self.database_name}
        if obj1._state.db in allowed_dbs and obj2._state.db in allowed_dbs:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.route_app_labels:
            return db == self.database_name
        if db == self.database_name:
            return False
        return None


class MaoniRouter(BaseAppRouter):
    route_app_labels = frozenset({"maoni", "ppaa_maoni"})
    database_name = "maoni_db"


class PerformanceDashboardRouter(BaseAppRouter):
    route_app_labels = frozenset({"ppaa_performance"})
    database_name = "performance_dashboard_db"


class ReportsManagementRouter(BaseAppRouter):
    # Keep legacy label too in case older RMS modules still use it.
    route_app_labels = frozenset({"reports_management", "rms_reports", "ppaa_reports"})
    database_name = "reports_management_db"


class DefaultRouter:
    """Fallback router; keep non-dedicated apps on default DB."""

    DEDICATED_DB_APPS = frozenset(
        {
            "maoni",
            "ppaa_maoni",
            "ppaa_performance",
            "reports_management",
            "rms_reports",
            "ppaa_reports",
        }
    )

    def db_for_read(self, model, **hints):
        return "default"

    def db_for_write(self, model, **hints):
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        if obj1._state.db == "default" and obj2._state.db == "default":
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == "default":
            return app_label not in self.DEDICATED_DB_APPS
        return False


ROUTERS = [
    MaoniRouter(),
    PerformanceDashboardRouter(),
    ReportsManagementRouter(),
    DefaultRouter(),
]
