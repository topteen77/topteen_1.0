#!/usr/bin/env python3
"""
Management command to update categories for existing Skill Lab Courses.

This command:
1. Finds all existing SkillLabCourse records
2. Determines appropriate category based on course name
3. Updates the category field
"""

from django.core.management.base import BaseCommand
from skilllab.models import SkillLabCourse
from core.choices import SkillLabCourseTypeChoice, ObjectStatus


class Command(BaseCommand):
    help = 'Update categories for existing Skill Lab Courses'

    def get_course_category(self, course_name):
        """Determine course category based on course name"""
        course_name_lower = course_name.lower()
        
        # Courses for class 7 and 8 (before 10th)
        if 'class 7' in course_name_lower or 'class 8' in course_name_lower:
            return SkillLabCourseTypeChoice.after_10_class
        
        # Courses specifically for high schoolers (after 10th or 12th)
        if any(keyword in course_name_lower for keyword in [
            'highschool', 'high school', 'highschooler', 'teen', 'teens', 'teenager', 'teenagers',
            'for students', 'student'
        ]):
            return SkillLabCourseTypeChoice.BOTH
        
        # Courses that could be for both high school and college
        if any(keyword in course_name_lower for keyword in [
            'career ready', 'career planning', 'soft skills', 'after highschool',
            'interview skills', 'networking', 'personal branding', 'entrepreneurship',
            'leadership', 'public speaking', 'communication', 'time-management',
            'productivity', 'study techniques', 'goal setting', 'emotional intelligence',
            'adaptability', 'resilience', 'self-advocacy', 'confidence'
        ]):
            return SkillLabCourseTypeChoice.BOTH
        
        # Technology/AI courses - typically for after 12th
        if any(keyword in course_name_lower for keyword in [
            'ai', 'coding', 'app development', 'cyber security', 'digital safety',
            'data literacy', 'analytics', 'stem', 'digital literacy'
        ]):
            return SkillLabCourseTypeChoice.after_12_class
        
        # Default to BOTH (most versatile)
        return SkillLabCourseTypeChoice.BOTH

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually doing it',
        )
        parser.add_argument(
            '--course-id',
            type=int,
            help='Update specific course by ID',
        )
        parser.add_argument(
            '--status',
            type=str,
            choices=['active', 'inactive', 'all'],
            default='all',
            help='Filter by object_status (active, inactive, or all)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        course_id = options.get('course_id')
        status_filter = options.get('status', 'all')
        
        # Get courses based on filters
        if course_id:
            courses = SkillLabCourse.objects.filter(id=course_id)
            if not courses.exists():
                self.stdout.write(self.style.ERROR(f'Course with ID {course_id} not found.'))
                return
        else:
            courses = SkillLabCourse.objects.complete()  # Get all including deleted
            
            # Filter by status
            if status_filter == 'active':
                courses = courses.filter(object_status=ObjectStatus.ACTIVE)
            elif status_filter == 'inactive':
                courses = courses.filter(object_status=ObjectStatus.INACTIVE)
            # 'all' means no additional filter
        
        total_count = courses.count()
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING('No courses found to update.'))
            return
        
        self.stdout.write(f'Found {total_count} course(s) to process')
        self.stdout.write('=' * 80)
        
        category_map = dict(SkillLabCourseTypeChoice.CHOICE)
        updated_count = 0
        unchanged_count = 0
        error_count = 0
        
        category_stats = {
            SkillLabCourseTypeChoice.after_10_class: 0,
            SkillLabCourseTypeChoice.after_12_class: 0,
            SkillLabCourseTypeChoice.BOTH: 0,
            SkillLabCourseTypeChoice.after_college: 0,
        }
        
        for course in courses:
            try:
                # Get current category
                current_category = course.category
                current_category_name = category_map.get(current_category, 'Unknown')
                
                # Determine new category
                new_category = self.get_course_category(course.name)
                new_category_name = category_map.get(new_category, 'Unknown')
                
                if current_category == new_category:
                    unchanged_count += 1
                    if not dry_run:
                        self.stdout.write(f'  ✓ {course.name[:60]:<60} → {new_category_name} (unchanged)')
                    else:
                        self.stdout.write(f'  [DRY RUN] {course.name[:60]:<60} → {new_category_name} (unchanged)')
                else:
                    updated_count += 1
                    category_stats[new_category] += 1
                    
                    if dry_run:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  [DRY RUN] {course.name[:60]:<60} → {current_category_name} → {new_category_name}'
                            )
                        )
                    else:
                        course.category = new_category
                        course.save(update_fields=['category'])
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✓ {course.name[:60]:<60} → {current_category_name} → {new_category_name}'
                            )
                        )
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error updating {course.name}: {str(e)}')
                )
        
        # Summary
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('UPDATE SUMMARY')
        self.stdout.write('=' * 80)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes made'))
            self.stdout.write(f'Would update: {updated_count}')
            self.stdout.write(f'Would remain unchanged: {unchanged_count}')
        else:
            self.stdout.write(f'Updated: {updated_count}')
            self.stdout.write(f'Unchanged: {unchanged_count}')
        
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {error_count}'))
        
        self.stdout.write('\nCategory Distribution:')
        for cat_id, count in category_stats.items():
            if count > 0:
                cat_name = category_map.get(cat_id, 'Unknown')
                self.stdout.write(f'  {cat_name}: {count}')
