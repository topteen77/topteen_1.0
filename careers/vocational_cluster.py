"""Vocational career cluster (career library track) used for aptitude reasoning mappings."""

from django.conf import settings
from django.urls import reverse

DEFAULT_VOCATIONAL_CAREER_CLUSTER_ID = 27


def vocational_career_cluster_id():
    return int(getattr(settings, 'VOCATIONAL_CAREER_CLUSTER_ID', DEFAULT_VOCATIONAL_CAREER_CLUSTER_ID))


def get_vocational_career_cluster():
    from careers.models import CareerCluster
    from core import choices

    return CareerCluster.objects.filter(
        id=vocational_career_cluster_id(),
        object_status=choices.ObjectStatus.ACTIVE,
    ).first()


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
