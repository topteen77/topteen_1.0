import re
from urllib.parse import urlencode

from django.urls import reverse

from core import choices
from core.choices import ReasoningArea
from core.models import VocationalCourseReasoningMapping


def normalize_reasoning_area_code(area):
    """Map test score keys or labels to a ReasoningArea code (e.g. VERBAL)."""
    if not area:
        return None
    code = str(area).strip().upper()
    if ReasoningArea.is_valid(code):
        return code
    token = re.split(r'[\s_]+', code)[0] if code else ''
    if ReasoningArea.is_valid(token):
        return token
    return None


def vocational_level_tab_for_user(user):
    """
    Return vocational catalog tab slug for the student's class: after-10 or after-12.
    Class 11–12 → after-12; class 10 and below → after-10.
    """
    if not user or not getattr(user, 'is_authenticated', False) or not user.is_authenticated:
        return 'after-10'
    try:
        from institute.models import StudentManagement

        student_management = (
            StudentManagement.objects.filter(student=user)
            .select_related('class_and_section')
            .first()
        )
        if student_management and student_management.class_and_section:
            class_name = student_management.class_and_section.class_and_section or ''
            numbers = re.findall(r'\d+', class_name)
            if numbers and int(numbers[0]) >= 11:
                return 'after-12'
            return 'after-10'
    except Exception:
        pass
    try:
        profile = getattr(user, 'user_profile', None)
        if profile and profile.grade:
            grade_val = str(profile.grade).strip()
            if grade_val in ('12', '11'):
                return 'after-12'
            return 'after-10'
    except Exception:
        pass
    return 'after-10'


def build_vocational_courses_filter_url(reasoning_area, user=None):
    """URL to vocational courses list filtered by reasoning area and student class tab."""
    code = normalize_reasoning_area_code(reasoning_area)
    if not code:
        return reverse('core:vocational_courses')
    tab = vocational_level_tab_for_user(user) if user else 'after-10'
    qs = urlencode({'tab': tab, 'reasoning_area': code})
    return f"{reverse('core:vocational_courses')}?{qs}"


def vocational_category_ids_for_level(level_tab):
    """Category PKs under an After 10 / After 12 root (includes subcategories)."""
    if level_tab not in ('after-10', 'after-12'):
        return []
    from core.models import VocationalCourseCategory

    root = VocationalCourseCategory.objects.filter(
        slug=level_tab,
        parent__isnull=True,
        object_status=choices.ObjectStatus.ACTIVE,
    ).first()
    if not root:
        return []
    collected = {root.id}
    frontier = [root.id]
    while frontier:
        child_ids = list(
            VocationalCourseCategory.objects.filter(
                parent_id__in=frontier,
                object_status=choices.ObjectStatus.ACTIVE,
            ).values_list('id', flat=True)
        )
        new_ids = [pk for pk in child_ids if pk not in collected]
        collected.update(new_ids)
        frontier = new_ids
    return list(collected)


def course_ids_for_reasoning_area(reasoning_area, level_tab=None):
    """Active vocational course PKs mapped to this reasoning area, optionally scoped to After 10/12."""
    code = normalize_reasoning_area_code(reasoning_area)
    if not code:
        return []
    qs = VocationalCourseReasoningMapping.objects.filter(
        reasoning_area=code,
        object_status=choices.ObjectStatus.ACTIVE,
        vocational_course__object_status=choices.ObjectStatus.ACTIVE,
    )
    if level_tab in ('after-10', 'after-12'):
        category_ids = vocational_category_ids_for_level(level_tab)
        if category_ids:
            qs = qs.filter(vocational_course__category_id__in=category_ids)
        else:
            return []
    return list(
        qs.order_by('priority', 'vocational_course__name').values_list(
            'vocational_course_id', flat=True
        )
    )


def below_area_vocational_urls(below_areas, user=None):
    """Map each below-area key to a filtered vocational courses listing URL."""
    if not below_areas or not isinstance(below_areas, list):
        return {}
    urls = {}
    for area in below_areas:
        code = normalize_reasoning_area_code(area)
        if not code:
            continue
        key = str(area).strip().upper()
        urls[key] = build_vocational_courses_filter_url(code, user=user)
        urls[area] = urls[key]
    return urls


def vocational_cards_for_below_areas(below_areas, user=None):
    """
    Return one vocational course card per below-average reasoning area (in test order).
    Each card includes reasoning_area metadata and a link to all courses for that area.
    """
    if not below_areas or not isinstance(below_areas, list):
        return []

    cards = []
    for area in below_areas:
        code = normalize_reasoning_area_code(area)
        if not code:
            continue
        mapping = (
            VocationalCourseReasoningMapping.objects.filter(
                reasoning_area=code,
                object_status=choices.ObjectStatus.ACTIVE,
                vocational_course__object_status=choices.ObjectStatus.ACTIVE,
            )
            .select_related('vocational_course', 'vocational_course__category')
            .order_by('priority', 'vocational_course__name')
            .first()
        )
        if not mapping:
            continue
        course = mapping.vocational_course
        cards.append({
            'label': course.name,
            'course': course,
            'reasoning_area': code,
            'reasoning_area_label': ReasoningArea.label(code),
            'reasoning_area_courses_url': build_vocational_courses_filter_url(code, user=user),
            'reasoning_area_course_count': len(
                course_ids_for_reasoning_area(
                    code, vocational_level_tab_for_user(user) if user else 'after-10'
                )
            ),
        })
    return cards
