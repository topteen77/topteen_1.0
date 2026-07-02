"""Vocational career cluster (career library track) used for aptitude reasoning mappings."""

import time

from django.conf import settings
from django.urls import reverse

DEFAULT_VOCATIONAL_CAREER_CLUSTER_ID = 27

# The cluster is a fixed, config-driven row that is looked up hundreds of times
# while building a single report (once per career/reasoning-area link). Memoize it
# with a short TTL so a report build issues one query instead of hundreds, while
# still picking up admin changes within a few minutes.
_CLUSTER_CACHE_TTL_SECONDS = 300
_cluster_cache = {"value": None, "ts": 0.0}


def vocational_career_cluster_id():
    return int(getattr(settings, 'VOCATIONAL_CAREER_CLUSTER_ID', DEFAULT_VOCATIONAL_CAREER_CLUSTER_ID))


def clear_vocational_career_cluster_cache():
    _cluster_cache["value"] = None
    _cluster_cache["ts"] = 0.0


def get_vocational_career_cluster():
    from careers.models import CareerCluster
    from core import choices

    now = time.monotonic()
    if _cluster_cache["value"] is not None and (now - _cluster_cache["ts"]) < _CLUSTER_CACHE_TTL_SECONDS:
        return _cluster_cache["value"]

    cluster = CareerCluster.objects.filter(
        id=vocational_career_cluster_id(),
        object_status=choices.ObjectStatus.ACTIVE,
    ).first()
    if cluster is not None:
        _cluster_cache["value"] = cluster
        _cluster_cache["ts"] = now
    return cluster


def vocational_career_cluster_url():
    cluster = get_vocational_career_cluster()
    if not cluster:
        return reverse('careers:career')
    return reverse('careers:career_cluster', args=[cluster.slug, cluster.id])


def build_vocational_cluster_reasoning_url(reasoning_area):
    from urllib.parse import urlencode

    from app.vocational_recommendations import normalize_reasoning_area_code

    cluster = get_vocational_career_cluster()
    if not cluster:
        return reverse('careers:career')
    code = normalize_reasoning_area_code(reasoning_area)
    base = reverse('careers:career_cluster', args=[cluster.slug, cluster.id])
    params = {'mapped': '1'}
    if code:
        params['reasoning_area'] = code
    return f"{base}?{urlencode(params)}"


def build_vocational_cluster_mapped_url():
    """Vocational cluster page limited to careers with an active reasoning mapping."""
    cluster = get_vocational_career_cluster()
    if not cluster:
        return reverse('careers:career')
    base = reverse('careers:career_cluster', args=[cluster.slug, cluster.id])
    return f"{base}?mapped=1"
