"""Shared CLI filters for vocational course HTML management commands."""
from __future__ import annotations

from core.models import VocationalCourse


def add_vocational_course_arguments(parser) -> None:
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes only; do not write to the database.",
    )
    parser.add_argument(
        "--course-id",
        type=int,
        default=None,
        help="Process a single vocational course by primary key.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Process course(s) whose name contains this string (case-insensitive).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of courses to process (after filters).",
    )


def vocational_course_queryset(options):
    qs = VocationalCourse.objects.all().order_by("id")
    course_id = options.get("course_id")
    name = options.get("name")
    limit = options.get("limit")
    if course_id:
        qs = qs.filter(pk=course_id)
    elif name:
        qs = qs.filter(name__icontains=name)
    if limit:
        qs = qs[:limit]
    return qs
