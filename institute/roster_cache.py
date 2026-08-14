"""Short-TTL cache for institute student roster test-result payloads."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from django.core.cache import caches

ROSTER_RESULT_CACHE_TTL = 90
ROSTER_RESULT_CACHE_VERSION = "v1"
ROSTER_CACHE_ALIAS = "roster"


def _roster_cache():
    try:
        return caches[ROSTER_CACHE_ALIAS]
    except Exception:
        from django.core.cache import cache

        return cache


def roster_result_cache_key(user_id: int) -> str:
    return f"inst:roster:result:{ROSTER_RESULT_CACHE_VERSION}:{int(user_id)}"


def get_cached_roster_result(user_id: int) -> Optional[dict]:
    try:
        cached = _roster_cache().get(roster_result_cache_key(user_id))
    except Exception:
        return None
    if isinstance(cached, dict) and "test_status" in cached:
        return cached
    return None


def set_cached_roster_result(user_id: int, payload: dict, ttl: int = ROSTER_RESULT_CACHE_TTL) -> None:
    if not isinstance(payload, dict) or "test_status" not in payload:
        return
    try:
        _roster_cache().set(roster_result_cache_key(user_id), payload, int(ttl))
    except Exception:
        pass


def set_many_cached_roster_results(
    payloads: Dict[int, dict], ttl: int = ROSTER_RESULT_CACHE_TTL
) -> None:
    mapping = {}
    for uid, payload in (payloads or {}).items():
        if not isinstance(payload, dict) or "test_status" not in payload:
            continue
        try:
            mapping[roster_result_cache_key(int(uid))] = payload
        except (TypeError, ValueError):
            continue
    if not mapping:
        return
    try:
        _roster_cache().set_many(mapping, int(ttl))
    except Exception:
        for key, payload in mapping.items():
            try:
                _roster_cache().set(key, payload, int(ttl))
            except Exception:
                pass


def invalidate_roster_result_cache(user_ids: Iterable[int]) -> None:
    keys = []
    for uid in user_ids or []:
        try:
            keys.append(roster_result_cache_key(int(uid)))
        except (TypeError, ValueError):
            continue
    if not keys:
        return
    c = _roster_cache()
    try:
        c.delete_many(keys)
    except Exception:
        for key in keys:
            try:
                c.delete(key)
            except Exception:
                pass


def merge_cached_roster_results(
    user_ids: Iterable[int],
) -> Dict[int, dict]:
    """Return {user_id: payload} for ids that have a valid cache entry."""
    out: Dict[int, Any] = {}
    id_list = []
    for uid in user_ids or []:
        try:
            id_list.append(int(uid))
        except (TypeError, ValueError):
            continue
    if not id_list:
        return out
    keys = [roster_result_cache_key(iid) for iid in id_list]
    try:
        bulk = _roster_cache().get_many(keys) or {}
    except Exception:
        bulk = {}
    if bulk:
        key_to_uid = dict(zip(keys, id_list))
        for key, cached in bulk.items():
            if isinstance(cached, dict) and "test_status" in cached:
                out[key_to_uid[key]] = cached
        return out
    # Fallback: per-key get (DummyCache / backends without get_many).
    for iid in id_list:
        cached = get_cached_roster_result(iid)
        if cached is not None:
            out[iid] = cached
    return out
