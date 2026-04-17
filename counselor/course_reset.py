"""
Admin/support: reset a user's Careers Counsellor Course progress to a fresh state.

- **soft**: save a JSON snapshot to CounselorCourseAttemptBackup, then delete progress rows.
- **hard**: delete progress rows with no backup.

Does not delete Payment / invoices.
"""
from django.db import transaction

from counselor.models import (
    CounselorCertification,
    CounselorCourse,
    CounselorCourseAttemptBackup,
    Notes,
    Part,
    QuizResults,
    VideoProgress,
)


def _build_snapshot(user, course, part_ids, video_keys):
    """Collect current counselor-course data for a soft-reset backup."""
    vp_qs = VideoProgress.objects.filter(user=user, video_id__in=video_keys)
    video_progress = list(
        vp_qs.values("id", "video_id", "progress", "completed", "duration")
    )
    notes = []
    if part_ids:
        notes = list(
            Notes.objects.filter(user=user, part_id__in=part_ids).values(
                "id",
                "part_id",
                "content",
                "video_timestamp",
                "video_end_timestamp",
                "updated_at",
            )
        )
    quiz_row = QuizResults.objects.filter(user=user).first()
    quiz_results = None
    if quiz_row:
        quiz_results = {
            "scores": quiz_row.scores,
            "modified": quiz_row.modified.isoformat() if quiz_row.modified else None,
        }
    certifications = list(
        CounselorCertification.objects.filter(user=user).values(
            "id", "certificate_code", "grade", "created_at"
        )
    )
    return {
        "course_id": course.id,
        "video_progress": video_progress,
        "notes": notes,
        "quiz_results": quiz_results,
        "certifications": certifications,
    }


def reset_counselor_course_data_for_user(user, mode="hard", actor=None):
    """
    Delete all counselor-course learning data for ``user``.

    mode:
      - ``soft``: write CounselorCourseAttemptBackup snapshot, then delete rows.
      - ``hard``: delete rows only (no backup).

    ``actor`` is the admin user performing the action (stored on soft backup).

    Returns a dict: ok, message, counts, mode, backup_id (if soft).
    """
    if user is None:
        return {"ok": False, "message": "No user.", "counts": {}, "mode": mode}

    mode = (mode or "hard").lower()
    if mode not in ("soft", "hard"):
        mode = "hard"

    course = CounselorCourse.objects.order_by("id").first()
    if not course:
        return {
            "ok": False,
            "message": "No CounselorCourse is configured.",
            "counts": {},
            "mode": mode,
        }

    part_ids = list(
        Part.objects.filter(chapter__course=course).values_list("id", flat=True)
    )
    video_keys = [f"video-{pid}" for pid in part_ids]
    counts = {}
    backup_id = None

    with transaction.atomic():
        if mode == "soft":
            snap = _build_snapshot(user, course, part_ids, video_keys)
            backup = CounselorCourseAttemptBackup.objects.create(
                user=user,
                snapshot=snap,
                created_by=actor,
            )
            backup_id = backup.id

        if video_keys:
            _n, _ = VideoProgress.objects.filter(
                user=user, video_id__in=video_keys
            ).delete()
            counts["video_progress"] = _n
        else:
            counts["video_progress"] = 0

        if part_ids:
            _n, _ = Notes.objects.filter(user=user, part_id__in=part_ids).delete()
            counts["notes"] = _n
        else:
            counts["notes"] = 0

        _n, _ = QuizResults.objects.filter(user=user).delete()
        counts["quiz_results"] = _n

        _n, _ = CounselorCertification.objects.filter(user=user).delete()
        counts["certifications"] = _n

    msg = "Counselor course progress cleared for this user."
    if mode == "soft":
        msg += f" Backup id={backup_id} (recover from Counselor course attempt backups)."

    out = {
        "ok": True,
        "message": msg,
        "counts": counts,
        "mode": mode,
    }
    if backup_id is not None:
        out["backup_id"] = backup_id
    return out


def restore_counselor_course_from_backup(backup, actor=None):
    """
    Restore counselor course progress from a soft-reset ``CounselorCourseAttemptBackup``.

    Replaces current counselor-course progress for ``backup.user`` with the snapshot
    (clears existing video progress / notes / quiz / cert for this course scope, then applies backup).

    Returns dict: ok, message, counts.
    """
    if backup is None:
        return {"ok": False, "message": "No backup.", "counts": {}}

    user = backup.user
    snap = backup.snapshot or {}
    if not isinstance(snap, dict):
        return {"ok": False, "message": "Invalid snapshot.", "counts": {}}

    course = CounselorCourse.objects.order_by("id").first()
    if not course:
        return {"ok": False, "message": "No CounselorCourse is configured.", "counts": {}}

    part_ids = list(
        Part.objects.filter(chapter__course=course).values_list("id", flat=True)
    )
    part_id_set = set(part_ids)
    video_keys = [f"video-{pid}" for pid in part_ids]
    video_key_set = set(video_keys)

    counts = {
        "video_progress": 0,
        "notes": 0,
        "quiz_results": 0,
        "certifications": 0,
    }

    snap_course = snap.get("course_id")
    if snap_course and snap_course != course.id:
        # Course record changed; still restore overlapping parts only
        pass

    with transaction.atomic():
        # Clear current counselor-scope data for this user
        if video_keys:
            VideoProgress.objects.filter(user=user, video_id__in=video_keys).delete()
        if part_ids:
            Notes.objects.filter(user=user, part_id__in=part_ids).delete()
        QuizResults.objects.filter(user=user).delete()
        CounselorCertification.objects.filter(user=user).delete()

        for row in snap.get("video_progress") or []:
            vid = row.get("video_id")
            if not vid or vid not in video_key_set:
                continue
            VideoProgress.objects.create(
                user=user,
                video_id=vid,
                progress=int(row.get("progress") or 0),
                completed=bool(row.get("completed")),
                duration=row.get("duration"),
            )
            counts["video_progress"] += 1

        for row in snap.get("notes") or []:
            pid = row.get("part_id")
            if pid not in part_id_set:
                continue
            Notes.objects.create(
                user=user,
                part_id=pid,
                content=row.get("content") or "",
                video_timestamp=row.get("video_timestamp"),
                video_end_timestamp=row.get("video_end_timestamp"),
            )
            counts["notes"] += 1

        qr = snap.get("quiz_results")
        if qr and isinstance(qr, dict) and "scores" in qr:
            QuizResults.objects.create(user=user, scores=qr["scores"])
            counts["quiz_results"] = 1

        for row in snap.get("certifications") or []:
            CounselorCertification.objects.create(
                user=user,
                certificate_code=row.get("certificate_code") or "",
                grade=row.get("grade") or "",
            )
            counts["certifications"] += 1

    return {
        "ok": True,
        "message": f"Restored backup #{backup.pk} for user {user_id_display(user)}.",
        "counts": counts,
        "backup_id": backup.pk,
    }


def user_id_display(user):
    try:
        return user.email or str(user.pk)
    except Exception:
        return "?"
