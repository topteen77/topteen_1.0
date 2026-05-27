"""Resolve related careers for detail pages and APIs."""

from core import choices


def get_related_careers(career, *, limit=6, published_only=True):
    """
    Return a queryset of related careers for display.

    Priority:
    1. Manually assigned ``related_careers`` (admin)
    2. Careers sharing courses
    3. Careers in the same career cluster(s)
    """
    from .models import Career

    manual_qs = career.related_careers.all().order_by('name')
    if published_only:
        manual_qs = manual_qs.filter(publish_status=choices.PublishStatus.PUBLISHED)
    if manual_qs.exists():
        return manual_qs[:limit]

    related = Career.objects.none()
    if career.courses.exists():
        related = Career.objects.filter(
            courses__in=career.courses.all(),
            publish_status=choices.PublishStatus.PUBLISHED,
        ).exclude(id=career.id).distinct()

    if career.career_cluster.exists():
        cluster_careers = Career.objects.filter(
            career_cluster__in=career.career_cluster.all(),
            publish_status=choices.PublishStatus.PUBLISHED,
        ).exclude(id=career.id).distinct()
        if related.exists():
            return (related | cluster_careers).distinct()[:limit]
        return cluster_careers[:limit]

    if related.exists():
        return related[:limit]
    return related
