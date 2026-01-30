#!/usr/bin/env python3
"""
Management command to import Skill Lab Courses from generated HTML files.

This command:
1. Reads courses_data.json
2. Creates/updates SkillLabCourse records
3. Imports chapter content from full_course.html
4. Creates activities for worksheets and MCQs
"""

import os
import sys
import json
from pathlib import Path
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files import File
from skilllab.models import SkillLabCourse, SkillLabCourseChapter, SkillLabCourseActivity
from core.choices import ObjectStatus, SkillLabCourseTypeChoice, Currency, SkillLabAcivityChoice

# Import DOCX converter
try:
    from scripts.convert_docx_to_html import convert_docx_to_html
except ImportError:
    # Fallback if import fails
    def convert_docx_to_html(docx_path):
        return None


class Command(BaseCommand):
    help = 'Import Skill Lab Courses from generated HTML files'
    
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
            '--course-name',
            type=str,
            help='Import specific course by name',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually doing it',
        )
        parser.add_argument(
            '--skip-chapters',
            action='store_true',
            help='Skip chapter import',
        )
        parser.add_argument(
            '--skip-activities',
            action='store_true',
            help='Skip activities (worksheets/MCQs) import',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        course_name = options.get('course_name')
        skip_chapters = options.get('skip_chapters', False)
        skip_activities = options.get('skip_activities', False)
        
        # Load courses data
        base_path = Path(settings.BASE_DIR) / 'skilllabcourses_html'
        courses_data_path = base_path / 'courses_data.json'
        
        if not courses_data_path.exists():
            self.stdout.write(self.style.ERROR(f'Courses data file not found: {courses_data_path}'))
            return
        
        with open(courses_data_path, 'r', encoding='utf-8') as f:
            all_courses = json.load(f)
        
        # Filter by course name if specified
        if course_name:
            all_courses = [c for c in all_courses if course_name.lower() in c['name'].lower()]
            if not all_courses:
                self.stdout.write(self.style.ERROR(f'Course not found: {course_name}'))
                return
        
        self.stdout.write(f'Found {len(all_courses)} course(s) to import')
        self.stdout.write('=' * 80)
        
        success_count = 0
        error_count = 0
        
        for course_data in all_courses:
            try:
                self.stdout.write(f'\nProcessing: {course_data["name"]}')
                
                if dry_run:
                    self.stdout.write(f'  [DRY RUN] Would create/update course')
                    continue
                
                # Create or update course
                course = self.create_or_update_course(course_data, base_path)
                
                if not skip_chapters:
                    # Import chapters
                    chapters_count = self.import_chapters(course, course_data, base_path)
                    if chapters_count > 0:
                        self.stdout.write(f'  ✓ Processed {chapters_count} chapters')
                    else:
                        self.stdout.write(self.style.WARNING(f'  ⚠ No chapters imported'))
                
                if not skip_activities:
                    # Import activities
                    activities_count = self.import_activities(course, course_data)
                    if activities_count > 0:
                        self.stdout.write(f'  ✓ Processed {activities_count} activities')
                    else:
                        self.stdout.write(self.style.WARNING(f'  ⚠ No activities imported'))
                
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Successfully imported: {course.name}'))
                
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Error importing {course_data["name"]}: {str(e)}'))
                import traceback
                self.stdout.write(traceback.format_exc())
        
        # Summary
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('IMPORT SUMMARY')
        self.stdout.write('=' * 80)
        self.stdout.write(f'Success: {success_count}')
        self.stdout.write(f'Errors: {error_count}')
        self.stdout.write(f'Total: {len(all_courses)}')

    def create_or_update_course(self, course_data, base_path):
        """Create or update SkillLabCourse from course data"""
        course_name = course_data['name']
        safe_name = course_data['safe_name']
        
        # Try to find existing course - try multiple matching strategies
        course = None
        
        # Strategy 1: Exact name match
        course = SkillLabCourse.objects.filter(name=course_name).first()
        
        # Strategy 2: Case-insensitive match
        if not course:
            course = SkillLabCourse.objects.filter(name__iexact=course_name).first()
        
        # Strategy 3: Partial match (first 30 chars)
        if not course:
            course = SkillLabCourse.objects.filter(name__icontains=course_name[:30]).first()
        
        # Strategy 4: Reverse partial match (check if course name contains expected name)
        if not course:
            for db_course in SkillLabCourse.objects.all():
                if course_name[:30].lower() in db_course.name.lower() or db_course.name.lower() in course_name[:30].lower():
                    course = db_course
                    break
        
        # Strategy 5: Check by slug (in case name differs but slug matches)
        if not course:
            from django.utils.text import slugify
            expected_slug = slugify(course_name)
            course = SkillLabCourse.objects.filter(slug=expected_slug).first()
        
        # Strategy 6: Check for courses with question mark variations
        if not course:
            name_variations = [
                course_name + '?',
                course_name.replace('?', ''),
                course_name.replace('!', ''),
            ]
            for var_name in name_variations:
                course = SkillLabCourse.objects.filter(name__iexact=var_name).first()
                if course:
                    break
        
        # Load intro HTML
        intro_path = base_path / safe_name / 'intro.html'
        description = None
        
        if intro_path.exists():
            try:
                with open(intro_path, 'r', encoding='utf-8') as f:
                    html = f.read()
                
                # Extract body content
                soup = BeautifulSoup(html, 'html.parser')
                body = soup.find('body')
                if body:
                    # Clean HTML and handle encoding issues
                    description = str(body)
                    # Remove problematic characters that cause MySQL encoding issues
                    # Replace arrow characters and other special Unicode
                    description = description.replace('→', '->')
                    description = description.replace('←', '<-')
                    description = description.replace('⇒', '=>')
                    description = description.replace('⇐', '<=')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'    ⚠ Could not read intro.html: {e}'))
        
        # Determine category
        category = self.get_course_category(course_name)
        category_name = dict(SkillLabCourseTypeChoice.CHOICE).get(category, 'Unknown')
        
        if course:
            # Update existing course - update all fields
            updated_fields = []
            if course.name != course_name:
                course.name = course_name
                updated_fields.append('name')
            if description and course.description != description:
                course.description = description
                updated_fields.append('description')
            if course.object_status != ObjectStatus.ACTIVE:
                course.object_status = ObjectStatus.ACTIVE
                updated_fields.append('status')
            if course.category != category:
                course.category = category
                updated_fields.append('category')
            
            # Handle slug conflicts - regenerate if needed
            try:
                if updated_fields:
                    # Check if slug needs to be updated
                    from django.utils.text import slugify
                    expected_slug = slugify(course_name)
                    if course.slug != expected_slug:
                        # Check if expected slug is available
                        if not SkillLabCourse.objects.filter(slug=expected_slug).exclude(id=course.id).exists():
                            course.slug = expected_slug
                            updated_fields.append('slug')
                    course.save()
                    self.stdout.write(f'  → Updated existing course (ID: {course.id}, Category: {category_name}, Updated: {", ".join(updated_fields)})')
                else:
                    self.stdout.write(f'  → Course already up-to-date (ID: {course.id}, Category: {category_name})')
            except Exception as e:
                if 'slug' in str(e).lower() or 'duplicate' in str(e).lower():
                    # Regenerate slug to avoid conflicts
                    from django.utils.text import slugify
                    base_slug = slugify(course_name)
                    counter = 1
                    new_slug = f"{base_slug}-{counter}"
                    while SkillLabCourse.objects.filter(slug=new_slug).exclude(id=course.id).exists():
                        counter += 1
                        new_slug = f"{base_slug}-{counter}"
                    course.slug = new_slug
                    course.save()
                    self.stdout.write(f'  → Updated existing course (ID: {course.id}, Category: {category_name}, Fixed slug conflict)')
                else:
                    raise
        else:
            # Create new course
            try:
                # Pre-generate unique slug to avoid conflicts
                from django.utils.text import slugify
                base_slug = slugify(course_name)
                # Check if slug exists
                if SkillLabCourse.objects.filter(slug=base_slug).exists():
                    # Find existing course with same slug
                    existing = SkillLabCourse.objects.filter(slug=base_slug).first()
                    if existing:
                        # Update the existing course instead
                        course = existing
                        course.name = course_name
                        if description:
                            course.description = description
                        course.object_status = ObjectStatus.ACTIVE
                        course.category = category
                        course.save()
                        self.stdout.write(f'  → Updated existing course (ID: {course.id}, Category: {category_name}, Resolved slug conflict)')
                    else:
                        # Generate unique slug
                        counter = 1
                        new_slug = f"{base_slug}-{counter}"
                        while SkillLabCourse.objects.filter(slug=new_slug).exists():
                            counter += 1
                            new_slug = f"{base_slug}-{counter}"
                        course = SkillLabCourse.objects.create(
                            name=course_name,
                            description=description or '',
                            object_status=ObjectStatus.ACTIVE,
                            category=category,
                            amount=0,
                            currency=Currency.IND,
                            slug=new_slug
                        )
                        self.stdout.write(f'  → Created new course (ID: {course.id}, Category: {category_name}, Slug: {new_slug})')
                else:
                    # Pre-set slug to avoid auto-generation conflicts
                    from django.utils.text import slugify
                    base_slug = slugify(course_name)
                    # Check if slug exists
                    if SkillLabCourse.objects.filter(slug=base_slug).exists():
                        # Generate unique slug
                        counter = 1
                        new_slug = f"{base_slug}-{counter}"
                        while SkillLabCourse.objects.filter(slug=new_slug).exists():
                            counter += 1
                            new_slug = f"{base_slug}-{counter}"
                        base_slug = new_slug
                    
                    # Create course with explicit slug to avoid auto-generation conflicts
                    # Use raw SQL or set slug after creation to bypass SlugModel auto-generation
                    try:
                        course = SkillLabCourse.objects.create(
                            name=course_name,
                            description=description or '',
                            object_status=ObjectStatus.ACTIVE,
                            category=category,
                            amount=0,  # Default to free, can be updated later
                            currency=Currency.IND
                        )
                        # Update slug if it was auto-generated and conflicts
                        if course.slug != base_slug:
                            # Check if our desired slug is available
                            if not SkillLabCourse.objects.filter(slug=base_slug).exclude(id=course.id).exists():
                                course.slug = base_slug
                                course.save(update_fields=['slug'])
                        self.stdout.write(f'  → Created new course (ID: {course.id}, Category: {category_name})')
                    except Exception as create_error:
                        if 'slug' in str(create_error).lower() or 'duplicate' in str(create_error).lower():
                            # Slug conflict during creation - find existing and update
                            existing = SkillLabCourse.objects.filter(slug=base_slug).first()
                            if existing:
                                course = existing
                                course.name = course_name
                                if description:
                                    course.description = description
                                course.object_status = ObjectStatus.ACTIVE
                                course.category = category
                                course.save()
                                self.stdout.write(f'  → Updated existing course (ID: {course.id}, Category: {category_name}, Resolved slug conflict)')
                            else:
                                # Generate unique slug and retry
                                counter = 1
                                new_slug = f"{base_slug}-{counter}"
                                while SkillLabCourse.objects.filter(slug=new_slug).exists():
                                    counter += 1
                                    new_slug = f"{base_slug}-{counter}"
                                course = SkillLabCourse.objects.create(
                                    name=course_name,
                                    description=description or '',
                                    object_status=ObjectStatus.ACTIVE,
                                    category=category,
                                    amount=0,
                                    currency=Currency.IND,
                                    slug=new_slug
                                )
                                self.stdout.write(f'  → Created new course (ID: {course.id}, Category: {category_name}, Slug: {new_slug})')
                        else:
                            raise
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error creating course: {e}'))
                raise
        
        return course

    def import_chapters_from_source(self, course, course_data):
        """Import chapters directly from source DOCX files (fallback if HTML is empty)"""
        source_path = Path(course_data['path'])
        imported_count = 0
        
        # Get existing chapters
        existing_chapters = {ch.chapter_name: ch for ch in SkillLabCourseChapter.objects.filter(skilllab=course)}
        
        for chapter_info in course_data.get('chapters', []):
            if not chapter_info.get('full_content'):
                continue
            
            chapter_num = chapter_info['number']
            chapter_name = f"Chapter {chapter_num}"
            chapter_docx_path = Path(chapter_info['full_content'])
            
            if not chapter_docx_path.exists():
                continue
            
            try:
                # Convert DOCX to HTML
                chapter_html = convert_docx_to_html(chapter_docx_path)
                if not chapter_html:
                    continue
                
                # Extract body content
                soup = BeautifulSoup(chapter_html, 'html.parser')
                body = soup.find('body')
                if body:
                    chapter_content = str(body)
                else:
                    continue
                
                # Create or update chapter
                if chapter_name in existing_chapters:
                    chapter = existing_chapters[chapter_name]
                    if chapter.content != chapter_content:
                        chapter.content = chapter_content
                        chapter.save()
                else:
                    chapter = SkillLabCourseChapter.objects.create(
                        skilllab=course,
                        chapter_name=chapter_name,
                        content=chapter_content
                    )
                
                imported_count += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'    ⚠ Error importing chapter {chapter_num} from source: {e}'))
        
        return imported_count

    def import_chapters(self, course, course_data, base_path):
        """Import chapters from full_course.html"""
        safe_name = course_data['safe_name']
        full_course_path = base_path / safe_name / 'full_course.html'
        
        if not full_course_path.exists():
            self.stdout.write(self.style.WARNING(f'  ⚠ Full course HTML not found: {full_course_path}'))
            # Try importing from source DOCX files
            return self.import_chapters_from_source(course, course_data)
        
        # Read and parse HTML
        try:
            with open(full_course_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Error reading full_course.html: {e}'))
            return 0
        
        soup = BeautifulSoup(html_content, 'html.parser')
        chapter_divs = soup.find_all('div', class_='chapter')
        
        # Check if file actually has chapters (not just title)
        if not chapter_divs or len(chapter_divs) == 0:
            # Check if there's any meaningful content beyond just the title
            body = soup.find('body')
            if body:
                # Count non-empty elements
                content_elements = [elem for elem in body.children if hasattr(elem, 'text') and elem.text.strip()]
                if len(content_elements) <= 1:  # Only title
                    self.stdout.write(self.style.WARNING(f'  ⚠ Full course HTML appears empty (only title found), trying source files...'))
                    # Fallback to importing from source DOCX files
                    return self.import_chapters_from_source(course, course_data)
        
        imported_count = 0
        updated_count = 0
        created_count = 0
        
        # Get existing chapters for this course
        existing_chapters = {ch.chapter_name: ch for ch in SkillLabCourseChapter.objects.filter(skilllab=course)}
        
        for chapter_div in chapter_divs:
            chapter_id = chapter_div.get('id', '')
            
            # Extract chapter number
            import re
            match = re.search(r'chapter-(\d+)', chapter_id)
            if not match:
                continue
            
            chapter_num = match.group(1)
            chapter_name = f"Chapter {chapter_num}"
            
            # Extract content (remove the wrapper div)
            chapter_content = ''
            for child in chapter_div.children:
                if hasattr(child, 'name') and child.name == 'h2':
                    # Skip the h2 title as we'll use chapter_name
                    continue
                chapter_content += str(child)
            
            # Check if chapter exists
            if chapter_name in existing_chapters:
                # Update existing chapter
                chapter = existing_chapters[chapter_name]
                if chapter.content != chapter_content:
                    chapter.content = chapter_content
                    chapter.save()
                    updated_count += 1
                imported_count += 1
            else:
                # Create new chapter
                chapter = SkillLabCourseChapter.objects.create(
                    skilllab=course,
                    chapter_name=chapter_name,
                    content=chapter_content
                )
                created_count += 1
                imported_count += 1
        
        if created_count > 0 or updated_count > 0:
            self.stdout.write(f'    Chapters: {imported_count} total ({created_count} created, {updated_count} updated)')
        
        return imported_count

    def import_activities(self, course, course_data):
        """Import worksheets and MCQs as activities"""
        imported_count = 0
        created_count = 0
        updated_count = 0
        
        # Import worksheets
        for worksheet in course_data.get('worksheets', []):
            chapter_num = worksheet['chapter']
            worksheet_path = Path(worksheet['path'])
            
            if not worksheet_path.exists():
                self.stdout.write(self.style.WARNING(f'    ⚠ Worksheet file not found: {worksheet_path}'))
                continue
            
            # Find chapter
            chapter = SkillLabCourseChapter.objects.filter(
                skilllab=course,
                chapter_name__icontains=f"Chapter {chapter_num}"
            ).first()
            
            if not chapter:
                self.stdout.write(self.style.WARNING(f'    ⚠ Chapter {chapter_num} not found for worksheet'))
                continue
            
            # Create or update activity
            activity_name = f"Worksheet - Chapter {chapter_num}"
            activity, created = SkillLabCourseActivity.objects.get_or_create(
                skilllab_chapter=chapter,
                name=activity_name,
                defaults={
                    'type': SkillLabAcivityChoice.worksheet,  # Worksheet type (2)
                    'content': f'Download worksheet for Chapter {chapter_num}'
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
            
            # Update file if it doesn't exist or is different
            if not activity.downloadable_file or not activity.downloadable_file.name:
                try:
                    with open(worksheet_path, 'rb') as f:
                        activity.downloadable_file.save(
                            worksheet_path.name,
                            File(f),
                            save=True
                        )
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'    ⚠ Could not copy worksheet file: {e}'))
            
            imported_count += 1
        
        # Import MCQs (if any)
        for mcq in course_data.get('mcqs', []):
            chapter_num = mcq['chapter']
            mcq_path = Path(mcq['path'])
            
            if not mcq_path.exists():
                continue
            
            # Find chapter
            chapter = SkillLabCourseChapter.objects.filter(
                skilllab=course,
                chapter_name__icontains=f"Chapter {chapter_num}"
            ).first()
            
            if not chapter:
                continue
            
            # Create or update activity
            activity_name = f"MCQ - Chapter {chapter_num}"
            activity, created = SkillLabCourseActivity.objects.get_or_create(
                skilllab_chapter=chapter,
                name=activity_name,
                defaults={
                    'type': SkillLabAcivityChoice.activity,  # MCQ type (using activity as fallback)
                    'content': f'Download MCQ for Chapter {chapter_num}'
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
            
            # Update file if it doesn't exist
            if not activity.downloadable_file or not activity.downloadable_file.name:
                try:
                    with open(mcq_path, 'rb') as f:
                        activity.downloadable_file.save(
                            mcq_path.name,
                            File(f),
                            save=True
                        )
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'    ⚠ Could not copy MCQ file: {e}'))
            
            imported_count += 1
        
        if created_count > 0 or updated_count > 0:
            self.stdout.write(f'    Activities: {imported_count} total ({created_count} created, {updated_count} updated)')
        
        return imported_count
