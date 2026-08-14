"""Invalidate careers page caches when careers/clusters change."""
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from careers.page_cache import invalidate_careers_caches


def _bump(**kwargs):
    try:
        invalidate_careers_caches()
    except Exception:
        pass


@receiver(post_save, sender="careers.Career")
@receiver(post_delete, sender="careers.Career")
@receiver(post_save, sender="careers.CareerCluster")
@receiver(post_delete, sender="careers.CareerCluster")
def careers_cache_invalidate_on_save(sender, **kwargs):
    _bump()


@receiver(m2m_changed, sender="careers.Career_career_cluster")
def careers_cache_invalidate_on_cluster_m2m(sender, **kwargs):
    if kwargs.get("action") in (
        "post_add",
        "post_remove",
        "post_clear",
    ):
        _bump()
