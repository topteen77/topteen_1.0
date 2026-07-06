from typing import List, Dict, Any, Iterable

from django.conf import settings
from django.db.models import Count, Q as DjangoQ

from .models import MasterClass


def _footer_career_clusters():
    """Same clusters as careers page grid: active, with at least one published career, ordered by name. Used by Django templates. Links use /careers/cluster/<slug>-<id>/."""
    try:
        from careers.models import CareerCluster
        clusters_qs = CareerCluster.objects.filter(
            career_clusters__publish_status=1,
            object_status=1,
        ).distinct().annotate(
            career_count=Count('career_clusters', filter=DjangoQ(career_clusters__publish_status=1), distinct=True)
        ).filter(career_count__gt=0).order_by('name')
        return [{'id': c.id, 'name': c.name or '', 'slug': c.slug or ''} for c in clusters_qs]
    except Exception:
        return []


def allow_search_engine_index_processor(request):
    """
    Django context processor: indexing follows core.seo_indexing rules (production + optional demo QA).
    Injects allow_search_engine_index (bool) for templates.
    """
    from core.seo_indexing import resolve_allow_search_engine_index

    return {
        "allow_search_engine_index": resolve_allow_search_engine_index(request),
        "footer_career_clusters": _footer_career_clusters(),
    }


def _fallback_master_classes(min_value: int = 6, max_value: int = 12) -> List[Dict[str, Any]]:
    """Return a default list of class options when DB is empty or unavailable."""
    return [{"value": v, "label": f"Class {v}"} for v in range(max_value, min_value - 1, -1)]


def _fetch_master_classes(min_value: int = 6, max_value: int = 12) -> Iterable:
    """
    Internal helper that returns an iterable of master class rows.
    Returns queryset when possible, otherwise a fallback list of dicts.
    Uses fallback when DB returns no rows so the class dropdown always has options.
    """
    try:
        qs = MasterClass.get_active_master_classes(min_value=min_value, max_value=max_value)
        # When called from templates we prefer a list of dicts for predictable iteration
        if hasattr(qs, "values"):
            result = list(qs.values("value", "label"))
        else:
            result = list(qs)
        # Ensure dropdown always has options; use fallback when table is empty or all inactive
        if not result:
            return _fallback_master_classes(min_value=min_value, max_value=max_value)
        return result
    except Exception:
        # Fallback when DB/migrations not ready
        return _fallback_master_classes(min_value=min_value, max_value=max_value)


def master_classes_processor(request):
    """
    Django context processor for DjangoTemplates backend.
    Injects 'MASTER_CLASSES' into template context as a list of {'value','label'} dicts.
    """
    master_list = list(_fetch_master_classes())
    extra = None
    try:
        user = getattr(request, "user", None)
        profile = getattr(user, "user_profile", None) if user and user.is_authenticated else None
        grade_val = None
        if profile:
            grade_val = getattr(profile, "grade", None)
        # If grade exists and is not in master list, expose it so templates can render it
        if grade_val is not None and grade_val != "" and not any(str(m.get("value")) == str(grade_val) for m in master_list):
            extra = {"value": grade_val, "label": f"Class {grade_val}"}
    except Exception:
        extra = None
    return {"MASTER_CLASSES": master_list, "EXTRA_GRADE_OPTION": extra}


def master_classes(request=None):
    """
    Callable helper usable from Jinja environment (global).
    Call without arguments to get list of {'value','label'}.
    """
    return _fetch_master_classes()

