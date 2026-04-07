"""
Rules for counselor course completion and certificate eligibility.

- Video is required only if the part has a video URL (same idea as PDF / case
  studies: opening PDFs or case study PDFs is never a completion gate).
- Quizzes are required only if the part has quizzes attached.
- A part with no video and no quizzes (e.g. case-study-only or PDF-only shell)
  does not block course completion or certificate.
"""
import json

from .models import CounselorCourse, Part, QuizResults, VideoProgress


def _part_needs_video(part) -> bool:
    return bool((getattr(part, "video_url", None) or "").strip())


def _part_needs_quiz(part) -> bool:
    return part.quizzes.exists()


def part_counts_toward_completion(part) -> bool:
    """True if this part has at least one gated requirement (video and/or quiz)."""
    return _part_needs_video(part) or _part_needs_quiz(part)


def is_course_fully_completed(user) -> bool:
    """
    True when every part that has a video has completed video, and every part
    that has quizzes has completed quizzes. PDF notes and case studies never
    add requirements.
    """
    course = CounselorCourse.objects.first()

    if not course:
        return False

    all_parts = list(
        Part.objects.filter(chapter__course=course).prefetch_related("quizzes")
    )

    if not all_parts:
        return False

    contributing = [p for p in all_parts if part_counts_toward_completion(p)]
    if not contributing:
        # Course exists but only "shell" parts (no video, no quiz) — nothing to gate certificate.
        return True

    part_ids_with_video = [p.id for p in contributing if _part_needs_video(p)]
    completed_video_ids = set()
    if part_ids_with_video:
        video_progress = VideoProgress.objects.filter(
            user=user,
            video_id__in=[f"video-{part_id}" for part_id in part_ids_with_video],
            completed=True,
        )
        completed_video_ids = {
            int(progress.video_id.split("-")[1]) for progress in video_progress
        }

    try:
        quiz_result = QuizResults.objects.get(user=user)
        if isinstance(quiz_result.scores, str):
            scores = json.loads(quiz_result.scores) if quiz_result.scores else []
        elif isinstance(quiz_result.scores, list):
            scores = quiz_result.scores
        else:
            scores = []
    except QuizResults.DoesNotExist:
        scores = []

    parts_with_quizzes = {p.id for p in contributing if _part_needs_quiz(p)}

    completed_quiz_parts = set()
    for score in scores:
        part_id = score.get("part_id")
        if part_id is not None and part_id != "":
            try:
                completed_quiz_parts.add(int(part_id))
            except (TypeError, ValueError):
                completed_quiz_parts.add(part_id)

    for p in contributing:
        pid = p.id
        if _part_needs_video(p):
            if pid not in completed_video_ids:
                return False
        if _part_needs_quiz(p):
            if pid not in completed_quiz_parts:
                return False

    return True
