"""Shared payload for the trending-exams widget and public API."""

from django.utils.html import strip_tags

from core import choices
from core.models import EntranceTestPrepExam, TrendingExam


def exam_widget_summary(exam, override=""):
    text = (override or "").strip()
    if not text:
        payload = exam.content_json if isinstance(exam.content_json, dict) else {}
        for key in ("overview", "description", "about"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                text = value
                break
    if not text:
        text = exam.content_html or ""
    text = " ".join(strip_tags(text).split())
    if len(text) > 220:
        text = text[:217].rsplit(" ", 1)[0].rstrip(".,;:") + "..."
    return text


def trending_exam_queryset():
    return (
        TrendingExam.objects.select_related("exam", "exam__category", "exam__category__parent")
        .filter(exam__object_status=choices.ObjectStatus.ACTIVE)
        .order_by("position", "id")
    )


def serialize_trending_exam(row, site_url):
    exam = row.exam
    category = exam.category
    level = category.parent if category and category.parent_id else None
    path = exam_public_path(exam)
    image_path = ""
    if exam.image:
        try:
            image_path = exam.image.url
        except ValueError:
            image_path = ""
    origin = (site_url or "").rstrip("/")
    return {
        "id": exam.id,
        "name": exam.name,
        "slug": exam.slug,
        "summary": exam_widget_summary(exam, row.summary),
        "position": row.position,
        "category": category.name if category else "",
        "level": level.name if level else "",
        "url": origin + path if origin else path,
        "image_url": (origin + image_path) if origin and image_path else image_path,
    }


def exam_public_path(exam):
    from django.urls import reverse

    return reverse("core:entrance_test_prep_exam_detail", kwargs={"slug": exam.slug})


def search_exams_for_trending(query, limit=20):
    qs = EntranceTestPrepExam.objects.select_related("category", "category__parent").order_by("name")
    term = (query or "").strip()
    if term:
        qs = qs.filter(name__icontains=term)
    marked = set(TrendingExam.objects.values_list("exam_id", flat=True))
    results = []
    for exam in qs[: limit * 3]:
        if exam.id in marked:
            continue
        category = exam.category
        level = category.parent if category and category.parent_id else None
        results.append({
            "id": exam.id,
            "name": exam.name,
            "category": category.name if category else "",
            "level": level.name if level else "",
        })
        if len(results) >= limit:
            break
    return results


def renumber_trending_positions():
    rows = list(TrendingExam.objects.order_by("position", "id"))
    for index, row in enumerate(rows, start=1):
        if row.position != index:
            row.position = index
            row.save(update_fields=["position"])
