#!/usr/bin/env python3
"""
Management command to check if Skill Lab Courses data is fully uploaded.

This command:
1. Compares database courses with expected courses from courses_data.json
2. Checks if chapters are imported
3. Checks if activities (worksheets/MCQs) are imported
4. Shows missing data and statistics
"""

import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from skilllab.models import SkillLabCourse, SkillLabCourseChapter, SkillLabCourseActivity
from core.choices import ObjectStatus


class Command(BaseCommand):
    help = 'Check if Skill Lab Courses data is fully uploaded'

    def handle(self, *args, **options):
        # Load expected courses data
        base_path = Path(settings.BASE_DIR) / 'skilllabcourses_html'
        courses_data_path = base_path / 'courses_data.json'
        
        if not courses_data_path.exists():
            self.stdout.write(self.style.ERROR(f'Courses data file not found: {courses_data_path}'))
            return
        
        with open(courses_data_path, 'r', encoding='utf-8') as f:
            expected_courses = json.load(f)
        
        self.stdout.write('=' * 80)
        self.stdout.write('SKILL LAB COURSES - UPLOAD STATUS CHECK')
        self.stdout.write('=' * 80)
        self.stdout.write()
        
        # Get all courses from database
        db_courses = SkillLabCourse.objects.complete()
        db_courses_dict = {course.name: course for course in db_courses}
        
        # Statistics
        expected_count = len(expected_courses)
        db_count = db_courses.count()
        active_count = SkillLabCourse.objects.filter(object_status=ObjectStatus.ACTIVE).count()
        inactive_count = SkillLabCourse.objects.filter(object_status=ObjectStatus.INACTIVE).count()
        
        self.stdout.write(f'Expected Courses: {expected_count}')
        self.stdout.write(f'Database Courses: {db_count}')
        self.stdout.write(f'  - Active: {active_count}')
        self.stdout.write(f'  - Inactive: {inactive_count}')
        self.stdout.write(f'  - Deleted: {db_count - active_count - inactive_count}')
        self.stdout.write()
        
        # Check each expected course
        found_courses = []
        missing_courses = []
        courses_with_issues = []
        
        total_expected_chapters = 0
        total_db_chapters = 0
        total_expected_worksheets = 0
        total_db_activities = 0
        
        for expected_course in expected_courses:
            course_name = expected_course['name']
            expected_chapters = expected_course['total_chapters']
            expected_worksheets = len(expected_course.get('worksheets', []))
            expected_mcqs = len(expected_course.get('mcqs', []))
            
            total_expected_chapters += expected_chapters
            total_expected_worksheets += expected_worksheets
            
            db_course = db_courses_dict.get(course_name)
            
            if not db_course:
                # Try partial match
                for db_c in db_courses:
                    if course_name[:30].lower() in db_c.name.lower() or db_c.name.lower() in course_name[:30].lower():
                        db_course = db_c
                        break
            
            if db_course:
                found_courses.append({
                    'expected': expected_course,
                    'db': db_course
                })
                
                # Check chapters
                db_chapters = SkillLabCourseChapter.objects.filter(skilllab=db_course).count()
                total_db_chapters += db_chapters
                
                # Check activities
                db_activities = SkillLabCourseActivity.objects.filter(
                    skilllab_chapter__skilllab=db_course
                ).count()
                total_db_activities += db_activities
                
                issues = []
                if db_chapters != expected_chapters:
                    issues.append(f'Chapters: {db_chapters}/{expected_chapters}')
                if db_activities < expected_worksheets:
                    issues.append(f'Activities: {db_activities}/{expected_worksheets} worksheets')
                if db_course.object_status != ObjectStatus.ACTIVE:
                    issues.append(f'Status: {dict(ObjectStatus.CHOICES).get(db_course.object_status)}')
                if not db_course.description or len(db_course.description) < 100:
                    issues.append('Missing/Short description')
                
                if issues:
                    courses_with_issues.append({
                        'course': db_course,
                        'expected': expected_course,
                        'issues': issues,
                        'db_chapters': db_chapters,
                        'db_activities': db_activities
                    })
            else:
                missing_courses.append(expected_course)
        
        # Summary
        self.stdout.write('=' * 80)
        self.stdout.write('SUMMARY')
        self.stdout.write('=' * 80)
        self.stdout.write(f'Courses Found: {len(found_courses)}/{expected_count}')
        self.stdout.write(f'Courses Missing: {len(missing_courses)}')
        self.stdout.write(f'Courses with Issues: {len(courses_with_issues)}')
        self.stdout.write()
        self.stdout.write(f'Chapters: {total_db_chapters}/{total_expected_chapters} ({total_db_chapters/total_expected_chapters*100:.1f}%)')
        self.stdout.write(f'Activities: {total_db_activities}/{total_expected_worksheets} ({total_db_activities/total_expected_worksheets*100:.1f}% if all worksheets)')
        self.stdout.write()
        
        # Missing courses
        if missing_courses:
            self.stdout.write(self.style.ERROR('MISSING COURSES:'))
            self.stdout.write('-' * 80)
            for course in missing_courses:
                self.stdout.write(f'  ✗ {course["name"]}')
                self.stdout.write(f'    Expected: {course["total_chapters"]} chapters, {len(course.get("worksheets", []))} worksheets')
            self.stdout.write()
        
        # Courses with issues
        if courses_with_issues:
            self.stdout.write(self.style.WARNING('COURSES WITH ISSUES:'))
            self.stdout.write('-' * 80)
            for item in courses_with_issues:
                course = item['course']
                expected = item['expected']
                self.stdout.write(f'  ⚠ {course.name} (ID: {course.id})')
                for issue in item['issues']:
                    self.stdout.write(f'     - {issue}')
                self.stdout.write(f'     DB: {item["db_chapters"]} chapters, {item["db_activities"]} activities')
                self.stdout.write(f'     Expected: {expected["total_chapters"]} chapters, {len(expected.get("worksheets", []))} worksheets')
                self.stdout.write()
        
        # Successfully uploaded courses
        success_count = len(found_courses) - len(courses_with_issues)
        if success_count > 0:
            self.stdout.write(self.style.SUCCESS(f'FULLY UPLOADED COURSES: {success_count}'))
            self.stdout.write('-' * 80)
            for item in found_courses:
                if item not in [c['course'] for c in courses_with_issues]:
                    course = item['db']
                    expected = item['expected']
                    db_chapters = SkillLabCourseChapter.objects.filter(skilllab=course).count()
                    db_activities = SkillLabCourseActivity.objects.filter(
                        skilllab_chapter__skilllab=course
                    ).count()
                    self.stdout.write(f'  ✓ {course.name}')
                    self.stdout.write(f'    Chapters: {db_chapters}/{expected["total_chapters"]}, Activities: {db_activities}/{len(expected.get("worksheets", []))}')
        
        # Overall status
        self.stdout.write()
        self.stdout.write('=' * 80)
        if len(missing_courses) == 0 and len(courses_with_issues) == 0:
            self.stdout.write(self.style.SUCCESS('✅ ALL COURSES FULLY UPLOADED!'))
        elif len(missing_courses) == 0:
            self.stdout.write(self.style.WARNING('⚠️  All courses found, but some have issues'))
        else:
            self.stdout.write(self.style.ERROR('❌ INCOMPLETE UPLOAD - Missing courses or data'))
        self.stdout.write('=' * 80)
