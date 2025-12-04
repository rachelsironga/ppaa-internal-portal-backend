class AnalyticalRouter:
    """
    Database router for mnh_analytical app.
    Routes mnh_analytical models to SQLite, everything else to default PostgreSQL.
    """
    
    route_app_labels = {'mnh_analytical'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'analytical'
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'analytical'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations between analytical and default databases."""
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Allow migrations to run for all apps on their respective databases.
        - mnh_analytical apps migrate only to 'analytical' db
        - All other apps migrate only to 'default' db
        """
        if app_label in self.route_app_labels:
            return db == 'analytical'
        if db == 'analytical':
            return False
        return None
