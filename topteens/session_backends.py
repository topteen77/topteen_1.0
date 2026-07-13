"""
Cached DB sessions that reject Redis orphans missing from the database.

Django's cached_db backend can load a session from Redis after the DB row was
deleted (logout elsewhere, clearsessions, manual cleanup). With
SESSION_SAVE_EVERY_REQUEST / analytics writing the session, save() then raises
UpdateError and SessionMiddleware turns that into SessionInterrupted (HTTP 400).
"""
from django.contrib.sessions.backends.cached_db import SessionStore as CachedDBStore
from django.contrib.sessions.backends.db import SessionStore as DBStore


class SessionStore(CachedDBStore):
    def load(self):
        try:
            data = self._cache.get(self.cache_key)
        except Exception:
            # Some backends raise on invalid keys; reset like upstream cached_db.
            data = None

        if data is not None:
            session_key = self.session_key
            # Prefer DB truth: cache-only orphans cause SessionInterrupted on save.
            if session_key and not DBStore.exists(self, session_key):
                self._cache.delete(self.cache_key_prefix + session_key)
                self._session_key = None
                return {}
            return data

        s = self._get_session_from_db()
        if s:
            data = self.decode(s.session_data)
            self._cache.set(
                self.cache_key, data, self.get_expiry_age(expiry=s.expire_date)
            )
            return data
        return {}
