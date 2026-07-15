"""Short-TTL cache for admin-configured dashboard rule tables.

DashboardPointRule / DashboardTrophyDefinition / DashboardLevelBand are tiny
tables that change only through the admin but are read dozens of times per
student-dashboard render (point map, trophy filtering, level bands, applies-to
resolution). Cache them process-locally (works with any cache backend, incl.
the DummyCache used in DEBUG) plus the Django cache (Redis in production), and
invalidate on save/delete via signals wired in core/apps.py.
"""

import time

from django.core.cache import cache

_LOCAL = {}
_LOCAL_TTL = 30  # seconds; bounds cross-request staleness in dev/DummyCache
_CACHE_TTL = 600  # seconds; Redis TTL in production
_CACHE_PREFIX = 'dashcfg:v1:'
_KEYS = (
    'point_rules_active',
    'point_rule_applies_to',
    'trophy_rows',
    'level_bands',
)


def cached_config(key, builder):
    """Return builder() for `key`, memoized process-locally + in Django cache."""
    now = time.time()
    hit = _LOCAL.get(key)
    if hit is not None and (now - hit[1]) < _LOCAL_TTL:
        return hit[0]

    cache_key = _CACHE_PREFIX + key
    try:
        val = cache.get(cache_key)
    except Exception:
        val = None

    if val is None:
        val = builder()
        try:
            cache.set(cache_key, val, _CACHE_TTL)
        except Exception:
            pass

    _LOCAL[key] = (val, now)
    return val


def invalidate_dashboard_config_cache(*args, **kwargs):
    """Drop all cached dashboard config (called from admin-save signals)."""
    _LOCAL.clear()
    for key in _KEYS:
        try:
            cache.delete(_CACHE_PREFIX + key)
        except Exception:
            pass
