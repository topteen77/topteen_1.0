#!/usr/bin/env python3
"""
Management command to reset Skill Lab course progress for testing.

Deletes (HARD delete): SkillLabCourseProgressSummary, SkillLabCourseProgress,
SkillLabWorksheetProgress, SkillLabMCQAttempt, SkillLabCourseResume,
SkillLabUserHighlight, SkillLabUserNote, SkillLabUserBookmark.

IMPORTANT: These models inherit BaseModel which uses *soft delete*
(object_status=DELETED). A soft delete leaves the row in the table, so its
unique_together key (e.g. user+course) is still occupied and re-attempting the
course raises "Duplicate entry ... IntegrityError". This command therefore uses
hard_delete() to physically remove rows so the course can be started fresh.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from skilllab.models import (
    SkillLabCourse,
    SkillLabCourseProgress,
    SkillLabCourseProgressSummary,
    SkillLabWorksheetProgress,
    SkillLabMCQAttempt,
    SkillLabCourseResume,
    SkillLabUserHighlight,
    SkillLabUserNote,
    SkillLabUserBookmark,
)

User = get_user_model()


def _hard_delete(qs):
    """Physically remove rows. Falls back to model-level delete for non soft-delete qs."""
    if hasattr(qs, 'hard_delete'):
        return qs.hard_delete()
    return qs.delete()


class Command(BaseCommand):
    help = 'Reset Skill Lab course progress (worksheets, MCQs, progress summary, resume) for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Reset for specific user (email or username)',
        )
        parser.add_argument(
            '--course',
            type=str,
            help='Reset for specific course (slug)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually doing it',
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        user_filter = options.get('user')
        course_filter = options.get('course')
        dry_run = options.get('dry_run')
        skip_confirm = options.get('yes')

        user = None
        if user_filter:
            user = User.objects.filter(
                email=user_filter
            ).first() or User.objects.filter(username=user_filter).first()
            if not user:
                self.stdout.write(self.style.ERROR(f'User not found: {user_filter}'))
                return

        course = None
        if course_filter:
            course = SkillLabCourse.objects.filter(slug=course_filter).first()
            if not course:
                self.stdout.write(self.style.ERROR(f'Course not found: {course_filter}'))
                return

        # Use .complete() so soft-deleted rows are included too. A previous
        # admin/reset "delete" only soft-deleted rows, and those zombie rows
        # are exactly what keeps the unique key occupied and triggers the
        # IntegrityError, so they must be removed as well.
        qs_summary = SkillLabCourseProgressSummary.objects.complete()
        qs_progress = SkillLabCourseProgress.objects.complete()
        qs_worksheet = SkillLabWorksheetProgress.objects.complete()
        qs_mcq = SkillLabMCQAttempt.objects.complete()
        qs_resume = SkillLabCourseResume.objects.complete()
        qs_highlight = SkillLabUserHighlight.objects.complete()
        qs_note = SkillLabUserNote.objects.complete()
        qs_bookmark = SkillLabUserBookmark.objects.complete()

        if user:
            qs_summary = qs_summary.filter(user=user)
            qs_progress = qs_progress.filter(user=user)
            qs_worksheet = qs_worksheet.filter(user=user)
            qs_mcq = qs_mcq.filter(user=user)
            qs_resume = qs_resume.filter(user=user)
            qs_highlight = qs_highlight.filter(user=user)
            qs_note = qs_note.filter(user=user)
            qs_bookmark = qs_bookmark.filter(user=user)
        if course:
            qs_summary = qs_summary.filter(skilllab_course=course)
            qs_progress = qs_progress.filter(skilllab_course=course)
            qs_worksheet = qs_worksheet.filter(activity__skilllab_chapter__skilllab=course)
            qs_mcq = qs_mcq.filter(mcq__skilllab_chapter__skilllab=course)
            qs_resume = qs_resume.filter(skilllab_course=course)
            qs_highlight = qs_highlight.filter(skilllab_course=course)
            qs_note = qs_note.filter(skilllab_course=course)
            qs_bookmark = qs_bookmark.filter(skilllab_course=course)

        counts = {
            'SkillLabCourseProgressSummary': qs_summary.count(),
            'SkillLabCourseProgress': qs_progress.count(),
            'SkillLabWorksheetProgress': qs_worksheet.count(),
            'SkillLabMCQAttempt': qs_mcq.count(),
            'SkillLabCourseResume': qs_resume.count(),
            'SkillLabUserHighlight': qs_highlight.count(),
            'SkillLabUserNote': qs_note.count(),
            'SkillLabUserBookmark': qs_bookmark.count(),
        }

        self.stdout.write('Records to delete (including soft-deleted):')
        for name, count in counts.items():
            self.stdout.write(f'  {name}: {count}')
        self.stdout.write('-' * 60)

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes made.'))
            return

        if sum(counts.values()) == 0:
            self.stdout.write(self.style.WARNING('No records to delete.'))
            return

        if not skip_confirm:
            confirm = input('Proceed? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Cancelled.'))
                return

        _hard_delete(qs_summary)
        _hard_delete(qs_progress)
        _hard_delete(qs_worksheet)
        _hard_delete(qs_mcq)
        _hard_delete(qs_resume)
        _hard_delete(qs_highlight)
        _hard_delete(qs_note)
        _hard_delete(qs_bookmark)

        self.stdout.write(self.style.SUCCESS('Progress reset complete.'))
