"""Skill Lab course certificate issuance (separate from counselor certifications)."""

from django.utils import timezone

from skilllab.models import (
    SkillLabCourseProgress,
    SkillLabCourseProgressSummary,
    SkillLabCourseResume,
    SkillLabCertification,
)


def is_skilllab_course_completed(user, skilllab_course):
    """Return True when the user has completed every chapter in the course."""
    if SkillLabCertification.objects.filter(user=user, skilllab_course=skilllab_course).exists():
        return True
    chapters = list(skilllab_course.skilllabcoursechapter.order_by('created'))
    if not chapters:
        summary = SkillLabCourseProgressSummary.objects.filter(
            user=user, skilllab_course=skilllab_course
        ).first()
        return bool(summary and (summary.progress_percentage or 0) >= 100)
    completed_ids = set(
        SkillLabCourseProgress.objects.filter(
            user=user,
            skilllab_course=skilllab_course,
            chapter__isnull=False,
            completed=True,
        ).values_list('chapter_id', flat=True)
    )
    return all(ch.id in completed_ids for ch in chapters)


def mark_skilllab_course_complete(user, skilllab_course):
    """Mark all chapters and progress summary as complete for the user."""
    from skilllab.views import upsert_active, update_skilllab_course_progress_summary

    now = timezone.now()
    chapters = list(skilllab_course.skilllabcoursechapter.order_by('created'))

    for chapter in chapters:
        upsert_active(
            SkillLabCourseProgress,
            user=user,
            skilllab_course=skilllab_course,
            chapter=chapter,
            defaults={'completed': True, 'completed_at': now},
        )

    try:
        update_skilllab_course_progress_summary(user, skilllab_course)
    except Exception:
        pass

    summary = SkillLabCourseProgressSummary.objects.filter(
        user=user, skilllab_course=skilllab_course
    ).first()
    total = (summary.total_sections_count if summary else 0) or 0

    upsert_active(
        SkillLabCourseProgressSummary,
        user=user,
        skilllab_course=skilllab_course,
        defaults={
            'progress_percentage': 100,
            'completed_sections_count': total,
            'total_sections_count': total,
        },
    )

    if total > 0:
        upsert_active(
            SkillLabCourseResume,
            user=user,
            skilllab_course=skilllab_course,
            defaults={'last_section_index': total - 1},
        )


def _skilllab_certificate_code(certification_id):
    return f"TPTSL{certification_id:04d}"


def ensure_skilllab_certificate_code(certification):
    """Assign a stable serial number from the certification record id."""
    if certification.certificate_code:
        return certification
    certification.certificate_code = _skilllab_certificate_code(certification.id)
    certification.save(update_fields=['certificate_code'])
    return certification


def issue_skilllab_certificate_if_eligible(user, skilllab_course):
    """
    Issue a Skill Lab certificate when all chapters are complete.
    Marks the course as fully complete when a certificate is issued.
    Returns the certification instance or None if not eligible.
    """
    if not is_skilllab_course_completed(user, skilllab_course):
        return None

    certification = SkillLabCertification.objects.filter(
        user=user, skilllab_course=skilllab_course
    ).first()
    if not certification:
        certification = SkillLabCertification.objects.create(
            user=user,
            skilllab_course=skilllab_course,
        )
        ensure_skilllab_certificate_code(certification)
    else:
        ensure_skilllab_certificate_code(certification)

    mark_skilllab_course_complete(user, skilllab_course)
    return certification
