#!/usr/bin/env python3
"""
Management command to reset Skill Lab course progress for testing.
Deletes: SkillLabCourseProgressSummary, SkillLabWorksheetProgress, SkillLabMCQAttempt, SkillLabCourseResume.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from skilllab.models import (
    SkillLabCourse,
    SkillLabCourseProgressSummary,
    SkillLabWorksheetProgress,
    SkillLabMCQAttempt,
    SkillLabCourseResume,
)

User = get_user_model()


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

        qs_summary = SkillLabCourseProgressSummary.objects.all()
        qs_worksheet = SkillLabWorksheetProgress.objects.all()
        qs_mcq = SkillLabMCQAttempt.objects.all()
        qs_resume = SkillLabCourseResume.objects.all()

        if user:
            qs_summary = qs_summary.filter(user=user)
            qs_worksheet = qs_worksheet.filter(user=user)
            qs_mcq = qs_mcq.filter(user=user)
            qs_resume = qs_resume.filter(user=user)
        if course:
            qs_summary = qs_summary.filter(skilllab_course=course)
            qs_worksheet = qs_worksheet.filter(activity__skilllab_chapter__skilllab=course)
            qs_mcq = qs_mcq.filter(mcq__skilllab_chapter__skilllab=course)
            qs_resume = qs_resume.filter(skilllab_course=course)

        c_summary = qs_summary.count()
        c_worksheet = qs_worksheet.count()
        c_mcq = qs_mcq.count()
        c_resume = qs_resume.count()

        self.stdout.write('Records to delete:')
        self.stdout.write(f'  SkillLabCourseProgressSummary: {c_summary}')
        self.stdout.write(f'  SkillLabWorksheetProgress: {c_worksheet}')
        self.stdout.write(f'  SkillLabMCQAttempt: {c_mcq}')
        self.stdout.write(f'  SkillLabCourseResume: {c_resume}')
        self.stdout.write('-' * 60)

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes made.'))
            return

        if c_summary + c_worksheet + c_mcq + c_resume == 0:
            self.stdout.write(self.style.WARNING('No records to delete.'))
            return

        if not skip_confirm:
            confirm = input('Proceed? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Cancelled.'))
                return

        qs_summary.delete()
        qs_worksheet.delete()
        qs_mcq.delete()
        qs_resume.delete()

        self.stdout.write(self.style.SUCCESS('Progress reset complete.'))
