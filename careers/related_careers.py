"""Resolve related careers for detail pages and APIs."""

from django.db.models import Q

from core import choices


def get_related_careers(career, *, limit=6, published_only=True):
    """
    Return a queryset of related careers for display.

    Priority:
    1. Manually assigned ``related_careers`` (admin)
    2. Careers sharing courses
    3. Careers in the same career cluster(s)

    Avoids multiple ``.exists()`` round-trips; uses id lists / prefetch cache when available.
    """
    from .models import Career

    published = choices.PublishStatus.PUBLISHED

    manual_qs = career.related_careers.all().order_by("name")
    if published_only:
        manual_qs = manual_qs.filter(publish_status=published)
    manual_ids = list(manual_qs.values_list("id", flat=True)[:limit])
    if manual_ids:
        return Career.objects.filter(id__in=manual_ids).order_by("name")

    course_ids = list(career.courses.values_list("id", flat=True)[:80])
    # Uses prefetch cache when career_cluster was prefetched on the career instance.
    cluster_ids = [c.id for c in career.career_cluster.all()][:40]

    if not course_ids and not cluster_ids:
        return Career.objects.none()

    qs = Career.objects.filter(publish_status=published).exclude(id=career.id)
    if course_ids and cluster_ids:
        qs = qs.filter(Q(courses__id__in=course_ids) | Q(career_cluster__id__in=cluster_ids))
    elif course_ids:
        qs = qs.filter(courses__id__in=course_ids)
    else:
        qs = qs.filter(career_cluster__id__in=cluster_ids)

    return qs.distinct().order_by("name")[:limit]
