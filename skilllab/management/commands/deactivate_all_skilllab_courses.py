#!/usr/bin/env python3
"""
Management command to deactivate all existing Skill Lab Courses.
Sets object_status to INACTIVE for all courses.
"""

from django.core.management.base import BaseCommand
from skilllab.models import SkillLabCourse
from core.choices import ObjectStatus


class Command(BaseCommand):
    help = 'Deactivate all existing Skill Lab Courses'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deactivated without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Get all active courses
        courses = SkillLabCourse.objects.filter(object_status=ObjectStatus.ACTIVE)
        total_count = courses.count()
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING('No active courses found to deactivate.'))
            return
        
        self.stdout.write(f'Found {total_count} active course(s) to deactivate:')
        self.stdout.write('-' * 80)
        
        for course in courses:
            self.stdout.write(f'  • {course.name} (ID: {course.id}, Slug: {course.slug})')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes made.'))
            return
        
        # Confirm
        self.stdout.write(self.style.WARNING(f'\nThis will deactivate {total_count} course(s).'))
        confirm = input('Are you sure you want to continue? (yes/no): ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('Operation cancelled.'))
            return
        
        # Deactivate all courses
        updated = courses.update(object_status=ObjectStatus.INACTIVE)
        
        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully deactivated {updated} course(s).'))
        
        # Show summary
        active_count = SkillLabCourse.objects.filter(object_status=ObjectStatus.ACTIVE).count()
        inactive_count = SkillLabCourse.objects.filter(object_status=ObjectStatus.INACTIVE).count()
        deleted_count = SkillLabCourse.objects.filter(object_status=ObjectStatus.DELETED).count()
        
        self.stdout.write('\nCurrent Status:')
        self.stdout.write(f'  Active: {active_count}')
        self.stdout.write(f'  Inactive: {inactive_count}')
        self.stdout.write(f'  Deleted: {deleted_count}')
