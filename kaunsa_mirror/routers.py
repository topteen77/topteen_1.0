"""
Route kaunsa_mirror app models to the `kaunsa_mirror` database alias only.
Requires KAUNSA_PG_ENABLED=True and DATABASES['kaunsa_mirror'] in settings.
"""


class KaunsaMirrorRouter:
    app_label = 'kaunsa_mirror'

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self.app_label:
            return 'kaunsa_mirror'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == self.app_label:
            return 'kaunsa_mirror'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if (
            obj1._meta.app_label == self.app_label
            or obj2._meta.app_label == self.app_label
        ):
            return obj1._meta.app_label == obj2._meta.app_label == self.app_label
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == self.app_label:
            return db == 'kaunsa_mirror'
        if db == 'kaunsa_mirror':
            return False
        return None
