#!/usr/bin/env python3
"""
Upload processed Skill Lab Courses to database.
Reads HTML files and uploads to Django database with S3 integration for PDFs.
Combines HTMLs in order: intro, sections (h2), conclusion.
"""

import os
import sys
import re
from pathlib import Path
from typing import Optional, Dict, List
from bs4 import BeautifulSoup

# Django setup
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')

import django
django.setup()

from django.utils.text import slugify
from skilllab.models import (
    SkillLabCourse, SkillLabCourseChapter, SkillLabCourseActivity,
    SkillLabMCQ, SkillLabMCQQuestion, SkillLabMCQAnswer, SkillLabChapterSection
)
from core.utils import choices
from core.s3_utils import get_s3_upload_service
from django.core.files import File
import json


# Configuration - use project root so it works locally and on server
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "skilllabcourses_html"
S3_FOLDER = "skilllab_courses"  # Folder in S3 for PDFs


def get_course_category(course_name: str) -> int:
    """
    Determine course category based on course name.
    """
    name_lower = course_name.lower()
    
    if any(keyword in name_lower for keyword in ['class 7', 'class 8', 'career ready']):
        return choices.SkillLabCourseTypeChoice.after_10_class
    elif any(keyword in name_lower for keyword in ['class 12', 'after 12', 'soft skills', 'high school']):
        return choices.SkillLabCourseTypeChoice.after_12_class
    elif any(keyword in name_lower for keyword in ['college', 'graduate', 'post-graduate']):
        return choices.SkillLabCourseTypeChoice.after_college
    else:
        return choices.SkillLabCourseTypeChoice.BOTH


def read_html_file(html_path: Path) -> Optional[str]:
    """
    Read HTML file and return content as string.
    """
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"  Error reading {html_path}: {e}")
        return None


def extract_body_content(html_content: str) -> str:
    """
    Extract body content from HTML, or return as-is if no body tag.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    body = soup.find('body')
    if body:
        return ''.join(str(child) for child in body.children)
    return html_content


def extract_chapter_sections(chapter_dir: Path, chapter_num: int) -> List[Dict]:
    """
    Extract chapter content as sections.
    Supports: (1) <p>Section N: ...</p> and <p>Chapter Wrap-Up</p> patterns,
    (2) h2/h3 headings as fallback.
    Returns list of {'title': str, 'content': str} for each section.
    """
    sections = []
    
    # 1. Read intro as first section
    intro_html_path = chapter_dir / "intro.html"
    if intro_html_path.exists():
        intro_html = read_html_file(intro_html_path)
        if intro_html:
            intro_content = extract_body_content(intro_html)
            sections.append({'title': 'Introduction', 'content': intro_content})
    
    # 2. Read chapter HTML - try <p>Section N:</p> pattern first, then h2/h3
    chapter_html_path = chapter_dir / f"chapter{chapter_num}.html"
    if not chapter_html_path.exists():
        chapter_html_path = chapter_dir / f"chapter_{chapter_num}.html"
    if chapter_html_path.exists():
        chapter_html = read_html_file(chapter_html_path)
        if chapter_html:
            body_html = extract_body_content(chapter_html)
            chapter_sections = _split_chapter_by_section_patterns(body_html)
            if not chapter_sections:
                chapter_sections = _split_chapter_by_h2_h3(body_html)
            sections.extend(chapter_sections)
    
    return sections


def _split_chapter_by_h2_h3(body_html: str) -> List[Dict]:
    """Fallback: split by h2/h3 headings."""
    if not body_html or not body_html.strip():
        return []
    soup = BeautifulSoup(body_html, 'html.parser')
    body = soup.find('body') or soup
    parts = re.split(r'(?=<h[23][^>]*>)', str(body), flags=re.IGNORECASE)
    result = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part or len(part) < 10:
            continue
        title_match = re.search(r'<h[23][^>]*>([^<]+)</h[23]>', part, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else (f'Section {i + 1}' if i > 0 else 'Content')
        result.append({'title': title[:255], 'content': part})
    return result if result else [{'title': 'Content', 'content': body_html}]


def _split_chapter_by_section_patterns(body_html: str) -> List[Dict]:
    """
    Split chapter body HTML by <p>Section N:</p>, <p>Section N-</p>, or <p>Chapter Wrap-Up</p> patterns.
    Content uses <p> tags for section headers, not h2/h3.
    Supports: Section 1:, Section 1-, Section 1 -, Chapter Wrap-up, Chapter Wrap-Up, Chapter Wrap- up, etc.
    """
    if not body_html or not body_html.strip():
        return []
    
    # Split by: <p>Section 1:, <p>Section 1-, <p>Section 1 -, ... or <p>Chapter Wrap-Up (and variants)
    # Pattern matches position before these paragraph starts (case-insensitive)
    # Section N: or Section N- or Section N - ; Chapter Wrap-up/Wrap-Up/Wrap- up/Wrap Up
    split_pattern = re.compile(
        r'(?=<p[^>]*>\s*(?:Section\s+\d+\s*[-:]|Chapter\s+Wrap[- ]?[\s-]*[Uu]p\b))',
        re.IGNORECASE
    )
    parts = split_pattern.split(body_html)
    
    result = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part or len(part) < 10:
            continue
        
        # Extract title from first <p> tag - Section N: Title or Section N- Title or Chapter Wrap-Up
        title_match = re.search(
            r'<p[^>]*>\s*(?:Section\s+(\d+)\s*[-:]\s*([^<]+)|(Chapter\s+Wrap[- ]?[\s-]*[Uu]p[^<]*))',
            part, re.IGNORECASE | re.DOTALL
        )
        if title_match:
            if title_match.group(1):  # Section N
                title = f"Section {title_match.group(1)}: {title_match.group(2).strip()}"
            else:  # Chapter Wrap-Up
                title = title_match.group(3).strip() if title_match.group(3) else 'Chapter Wrap-Up'
            # Clean trailing colon/space from title
            title = re.sub(r'[:\s]+$', '', title)
        else:
            # First part might be chapter title (before Section 1) - skip
            if i == 0 and not re.search(r'Section\s+\d+\s*[-:]', part[:300], re.IGNORECASE):
                continue  # Skip chapter title block
            title = f'Section {len(result) + 1}'
        
        result.append({'title': title[:255], 'content': part})
    
    return result


def combine_chapter_html(chapter_dir: Path, chapter_num: int) -> Optional[str]:
    """
    Combine chapter HTML (legacy fallback). Uses extract_chapter_sections.
    """
    sections = extract_chapter_sections(chapter_dir, chapter_num)
    if not sections:
        return None
    return '\n\n'.join(
        f'<h2>{s["title"]}</h2>\n{s["content"]}' for s in sections
    )


def upload_pdf_to_s3(pdf_path: Path, course_name: str, chapter_num: int, file_type: str) -> Optional[str]:
    """
    Upload PDF file to S3 and return S3 URL.
    file_type: 'worksheet' or 'mcq'
    """
    if not pdf_path.exists():
        return None
    
    try:
        s3_service = get_s3_upload_service()
        if not s3_service.is_enabled():
            print(f"  Warning: S3 upload is disabled. Skipping PDF upload for {pdf_path.name}")
            return None
        
        # Create folder path
        folder_path = f"{S3_FOLDER}/{slugify(course_name)}/chapter_{chapter_num}"
        
        # Open file and upload
        with open(pdf_path, 'rb') as f:
            file_obj = File(f, name=pdf_path.name)
            result = s3_service.upload_file(
                file_obj=file_obj,
                folder_path=folder_path,
                file_name=pdf_path.name,
                description=f"{file_type.title()} for {course_name} - Chapter {chapter_num}",
                uploaded_by="skilllab_upload_script"
            )
            
            if result.get('success'):
                return result.get('s3_url')
            else:
                print(f"  Error uploading {pdf_path.name} to S3: {result.get('error')}")
                return None
                
    except Exception as e:
        print(f"  Error uploading {pdf_path.name} to S3: {e}")
        import traceback
        traceback.print_exc()
        return None


def process_course(course_dir: Path, dry_run: bool = False):
    """
    Process a single course and upload to database.
    Returns statistics dictionary with detailed information.
    """
    stats = {
        'course_name': course_dir.name,
        'course_id': None,
        'course_created': False,
        'course_updated': False,
        'chapters': [],
        'worksheets': [],
        'mcqs': [],
        'mcq_activities': [],
        'pdfs_uploaded': 0,
        'pdfs_failed': 0
    }
    
    course_name = course_dir.name
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Processing course: {course_name}")
    
    # Read course intro and index
    course_intro_html = None
    course_index_html = None
    
    intro_path = course_dir / "course_intro.html"
    if intro_path.exists():
        course_intro_html = read_html_file(intro_path)
        if course_intro_html:
            course_intro_html = extract_body_content(course_intro_html)
    
    index_path = course_dir / "course_index.html"
    if index_path.exists():
        course_index_html = read_html_file(index_path)
        if course_index_html:
            course_index_html = extract_body_content(course_index_html)
    
    # course_intro_html and course_index_html are stored in separate fields for tabs
    # Fallback description for SEO if intro is empty
    course_description = course_intro_html or f"Course: {course_name}"
    
    # Determine category
    category = get_course_category(course_name)
    
    # Create or update course
    course_slug = slugify(course_name)
    
    if dry_run:
        print(f"  Would create/update course: {course_name}")
        print(f"    Slug: {course_slug}")
        print(f"    Category: {category}")
        print(f"    Description length: {len(course_description)} chars")
    else:
        try:
            course, created = SkillLabCourse.objects.get_or_create(
                slug=course_slug,
                defaults={
                    'name': course_name,
                    'description': course_description,
                    'course_intro_html': course_intro_html or '',
                    'course_index_html': course_index_html or '',
                    'category': category,
                    'object_status': choices.ObjectStatus.ACTIVE,
                    'amount': 0,  # Free by default
                    'currency': choices.Currency.IND
                }
            )
            
            if not created:
                # Update existing course
                course.name = course_name
                course.description = course_description
                course.course_intro_html = course_intro_html or ''
                course.course_index_html = course_index_html or ''
                course.category = category
                course.object_status = choices.ObjectStatus.ACTIVE
                course.save()
                stats['course_id'] = course.id
                stats['course_updated'] = True
                print(f"  Updated existing course: {course_name} (ID: {course.id})")
            else:
                stats['course_id'] = course.id
                stats['course_created'] = True
                print(f"  Created new course: {course_name} (ID: {course.id})")
        except Exception as e:
            print(f"  Error creating/updating course: {e}")
            import traceback
            traceback.print_exc()
            return
    
    # Process chapters
    chapter_dirs = sorted(
        [d for d in course_dir.iterdir() if d.is_dir() and d.name.startswith("chapter_")],
        key=lambda x: int(re.search(r'\d+', x.name).group()) if re.search(r'\d+', x.name) else 0
    )
    
    for chapter_dir in chapter_dirs:
        chapter_num_match = re.search(r'\d+', chapter_dir.name)
        if not chapter_num_match:
            continue
        
        chapter_num = int(chapter_num_match.group())
        chapter_name = f"Chapter {chapter_num}"
        
        print(f"  Processing {chapter_name}...")
        
        # Extract chapter sections (split by h2/h3 during upload)
        chapter_sections = extract_chapter_sections(chapter_dir, chapter_num)
        
        if not chapter_sections:
            print(f"    Warning: No HTML content found for {chapter_name}")
            continue
        
        if dry_run:
            print(f"    Would create/update chapter: {chapter_name}")
            print(f"      Sections: {len(chapter_sections)}")
        else:
            try:
                # Create or update chapter (content kept as fallback for chapters with no sections)
                chapter, created = SkillLabCourseChapter.objects.get_or_create(
                    skilllab=course,
                    chapter_name=chapter_name,
                    defaults={
                        'content': '',  # Sections stored separately
                        'object_status': choices.ObjectStatus.ACTIVE
                    }
                )
                
                if not created:
                    chapter.object_status = choices.ObjectStatus.ACTIVE
                    chapter.save()
                
                # Delete existing sections and create new ones (re-upload replaces all)
                SkillLabChapterSection.objects.filter(chapter=chapter).delete()
                
                for order, sec in enumerate(chapter_sections):
                    if order == 0:
                        section_type = 'introduction'
                    else:
                        title_lower = (sec['title'] or '').lower()
                        if any(kw in title_lower for kw in ('wrap-up', 'wrap up', 'conclusion', 'summary', 'chapter wrap')):
                            section_type = 'chapter_wrap_up'
                        else:
                            section_type = 'section'
                    SkillLabChapterSection.objects.create(
                        chapter=chapter,
                        order=order,
                        section_type=section_type,
                        title=sec['title'],
                        content=sec['content']
                    )
                
                stats['chapters'].append({
                    'name': chapter_name,
                    'id': chapter.id,
                    'created': created,
                    'updated': not created,
                    'sections': len(chapter_sections)
                })
                print(f"    {'Created' if created else 'Updated'} chapter: {chapter_name} (ID: {chapter.id}, {len(chapter_sections)} sections)")
            except Exception as e:
                print(f"    Error creating/updating chapter: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Process worksheet
        worksheet_pdf_path = chapter_dir / f"worksheet{chapter_num}.pdf"
        if worksheet_pdf_path.exists():
            if dry_run:
                print(f"    Would upload worksheet PDF: {worksheet_pdf_path.name}")
            else:
                s3_url = upload_pdf_to_s3(worksheet_pdf_path, course_name, chapter_num, 'worksheet')
                if s3_url:
                    try:
                        activity_name = f"Worksheet - Chapter {chapter_num}"
                        activity, created = SkillLabCourseActivity.objects.get_or_create(
                            skilllab_chapter=chapter,
                            name=activity_name,
                            defaults={
                                'type': choices.SkillLabAcivityChoice.worksheet,
                                'content': f'<p>Download worksheet for {chapter_name}</p><p><a href="{s3_url}" target="_blank">Download Worksheet PDF</a></p>',
                                'object_status': choices.ObjectStatus.ACTIVE
                            }
                        )
                        
                        if not created:
                            # Update existing activity
                            activity.content = f'<p>Download worksheet for {chapter_name}</p><p><a href="{s3_url}" target="_blank">Download Worksheet PDF</a></p>'
                            activity.type = choices.SkillLabAcivityChoice.worksheet
                            activity.object_status = choices.ObjectStatus.ACTIVE
                            activity.save()
                            stats['worksheets'].append({
                                'chapter': chapter_name,
                                'activity_id': activity.id,
                                'created': False,
                                'updated': True,
                                's3_url': s3_url
                            })
                            print(f"    Updated existing worksheet activity (ID: {activity.id})")
                        else:
                            stats['worksheets'].append({
                                'chapter': chapter_name,
                                'activity_id': activity.id,
                                'created': True,
                                'updated': False,
                                's3_url': s3_url
                            })
                            print(f"    Created new worksheet activity (ID: {activity.id})")
                        
                        if s3_url:
                            stats['pdfs_uploaded'] += 1
                    except Exception as e:
                        print(f"    Error creating worksheet activity: {e}")
                        import traceback
                        traceback.print_exc()
        
        # Process MCQ
        mcq_pdf_path = chapter_dir / f"chapter{chapter_num}-mcq.pdf"
        mcq_json_path = chapter_dir / f"chapter{chapter_num}-mcq.json"
        
        if mcq_pdf_path.exists() or mcq_json_path.exists():
            if dry_run:
                if mcq_pdf_path.exists():
                    print(f"    Would upload MCQ PDF: {mcq_pdf_path.name}")
                if mcq_json_path.exists():
                    print(f"    Would import MCQ data from: {mcq_json_path.name}")
            else:
                # Upload PDF if exists
                s3_url = None
                if mcq_pdf_path.exists():
                    s3_url = upload_pdf_to_s3(mcq_pdf_path, course_name, chapter_num, 'mcq')
                
                # Import MCQ data from JSON if exists
                if mcq_json_path.exists():
                    try:
                        with open(mcq_json_path, 'r', encoding='utf-8') as f:
                            mcq_data = json.load(f)
                        
                        # Create or update MCQ (one MCQ per chapter)
                        mcq_title = mcq_data.get('title', f'MCQ - {chapter_name}')
                        mcq, created = SkillLabMCQ.objects.get_or_create(
                            skilllab_chapter=chapter,
                            defaults={
                                'title': mcq_title,
                                'description': f'<p>MCQ questions for {chapter_name}</p>',
                                'object_status': choices.ObjectStatus.ACTIVE
                            }
                        )
                        
                        if not created:
                            # Update existing MCQ
                            mcq.title = mcq_title
                            mcq.description = f'<p>MCQ questions for {chapter_name}</p>'
                            mcq.save()
                            stats['mcqs'].append({
                                'chapter': chapter_name,
                                'mcq_id': mcq.id,
                                'title': mcq_title,
                                'created': False,
                                'updated': True,
                                'questions_created': 0,
                                'questions_updated': 0,
                                'total_questions': 0
                            })
                            print(f"    Updated existing MCQ: {mcq_title} (ID: {mcq.id})")
                        else:
                            stats['mcqs'].append({
                                'chapter': chapter_name,
                                'mcq_id': mcq.id,
                                'title': mcq_title,
                                'created': True,
                                'updated': False,
                                'questions_created': 0,
                                'questions_updated': 0,
                                'total_questions': 0
                            })
                            print(f"    Created new MCQ: {mcq_title} (ID: {mcq.id})")
                        
                        # Import questions - use get_or_create to avoid duplicates
                        questions_data = mcq_data.get('questions', [])
                        total_questions = len(questions_data)
                        created_questions = 0
                        updated_questions = 0
                        
                        # Update MCQ stats
                        mcq_stat = next((m for m in stats['mcqs'] if m['mcq_id'] == mcq.id), None)
                        if mcq_stat:
                            mcq_stat['total_questions'] = total_questions
                        
                        for q_data in questions_data:
                            question_number = q_data.get('question_number', 0)
                            question_text = q_data.get('question_text', '')
                            
                            # Get or create question
                            question, q_created = SkillLabMCQQuestion.objects.get_or_create(
                                mcq=mcq,
                                question_number=question_number,
                                defaults={
                                    'question_text': question_text,
                                    'order': question_number,
                                    'object_status': choices.ObjectStatus.ACTIVE
                                }
                            )
                            
                            if not q_created:
                                # Update existing question
                                question.question_text = question_text
                                question.order = question_number
                                question.save()
                                updated_questions += 1
                            else:
                                created_questions += 1
                            
                            # Import answers - use get_or_create to avoid duplicates
                            options = q_data.get('options', [])
                            correct_answer = q_data.get('correct_answer', {})
                            correct_letter = correct_answer.get('letter', '') if correct_answer else ''
                            
                            for opt_idx, option in enumerate(options):
                                opt_letter = option.get('letter', '').upper()
                                opt_text = option.get('text', '')
                                is_correct = (opt_letter == correct_letter.upper())
                                
                                # Get or create answer
                                answer, a_created = SkillLabMCQAnswer.objects.get_or_create(
                                    question=question,
                                    answer_letter=opt_letter,
                                    defaults={
                                        'answer_text': opt_text,
                                        'is_correct': is_correct,
                                        'order': opt_idx,
                                        'object_status': choices.ObjectStatus.ACTIVE
                                    }
                                )
                                
                                if not a_created:
                                    # Update existing answer
                                    answer.answer_text = opt_text
                                    answer.is_correct = is_correct
                                    answer.order = opt_idx
                                    answer.save()
                        
                        # Update MCQ total questions count if available
                        if hasattr(mcq, 'total_questions'):
                            mcq.total_questions = total_questions
                            mcq.save()
                        
                        # Update MCQ stats with question counts
                        if mcq_stat:
                            mcq_stat['questions_created'] = created_questions
                            mcq_stat['questions_updated'] = updated_questions
                        
                        print(f"    MCQ Questions: {created_questions} created, {updated_questions} updated (Total: {total_questions})")
                        
                        if s3_url:
                            stats['pdfs_uploaded'] += 1
                        
                        # Also create activity for MCQ
                        activity_name = f"MCQ Test - Chapter {chapter_num}"
                        activity_content = f'<p>Take the MCQ test for {chapter_name}</p>'
                        if s3_url:
                            activity_content += f'<p><a href="{s3_url}" target="_blank">Download MCQ PDF</a></p>'
                        
                        activity, created = SkillLabCourseActivity.objects.get_or_create(
                            skilllab_chapter=chapter,
                            name=activity_name,
                            defaults={
                                'type': choices.SkillLabAcivityChoice.activity,
                                'content': activity_content,
                                'object_status': choices.ObjectStatus.ACTIVE
                            }
                        )
                        
                        if not created:
                            # Update existing activity
                            activity.content = activity_content
                            activity.type = choices.SkillLabAcivityChoice.activity
                            activity.object_status = choices.ObjectStatus.ACTIVE
                            activity.save()
                            stats['mcq_activities'].append({
                                'chapter': chapter_name,
                                'activity_id': activity.id,
                                'created': False,
                                'updated': True,
                                's3_url': s3_url
                            })
                            print(f"    Updated existing MCQ activity (ID: {activity.id})")
                        else:
                            stats['mcq_activities'].append({
                                'chapter': chapter_name,
                                'activity_id': activity.id,
                                'created': True,
                                'updated': False,
                                's3_url': s3_url
                            })
                            print(f"    Created new MCQ activity (ID: {activity.id})")
                        
                    except Exception as e:
                        print(f"    Error importing MCQ data: {e}")
                        import traceback
                        traceback.print_exc()
                elif mcq_pdf_path.exists() and s3_url:
                    # Only PDF available, create activity
                    try:
                        activity_name = f"MCQ - Chapter {chapter_num}"
                        activity, created = SkillLabCourseActivity.objects.get_or_create(
                            skilllab_chapter=chapter,
                            name=activity_name,
                            defaults={
                                'type': choices.SkillLabAcivityChoice.activity,
                                'content': f'<p>Download MCQ for {chapter_name}</p><p><a href="{s3_url}" target="_blank">Download MCQ PDF</a></p>',
                                'object_status': choices.ObjectStatus.ACTIVE
                            }
                        )
                        
                        if not created:
                            # Update existing activity
                            activity.content = f'<p>Download MCQ for {chapter_name}</p><p><a href="{s3_url}" target="_blank">Download MCQ PDF</a></p>'
                            activity.type = choices.SkillLabAcivityChoice.activity
                            activity.object_status = choices.ObjectStatus.ACTIVE
                            activity.save()
                            print(f"    Updated existing MCQ activity (ID: {activity.id})")
                        else:
                            print(f"    Created new MCQ activity (ID: {activity.id})")
                    except Exception as e:
                        print(f"    Error creating MCQ activity: {e}")
                        import traceback
                        traceback.print_exc()
    
    return stats


def main():
    """
    Main upload function.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Upload processed Skill Lab Courses to database')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without making them')
    parser.add_argument('--course', type=str, help='Process only specific course (by name)')
    args = parser.parse_args()
    
    if not PROCESSED_DIR.exists():
        print(f"Error: Processed directory not found: {PROCESSED_DIR}")
        sys.exit(1)
    
    print("=" * 60)
    print("Skill Lab Courses Database Upload Script")
    print("=" * 60)
    print(f"Processed directory: {PROCESSED_DIR}")
    print(f"Dry run: {args.dry_run}")
    print()
    
    # Get all course directories
    if args.course:
        course_dirs = [PROCESSED_DIR / args.course]
        if not course_dirs[0].exists():
            print(f"Error: Course directory not found: {course_dirs[0]}")
            sys.exit(1)
    else:
        course_dirs = [d for d in PROCESSED_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')]
        course_dirs.sort()
    
    print(f"Found {len(course_dirs)} courses to process\n")
    
    processed = 0
    errors = 0
    all_stats = []
    
    for course_dir in course_dirs:
        try:
            stats = process_course(course_dir, dry_run=args.dry_run)
            if stats:
                all_stats.append(stats)
            processed += 1
        except Exception as e:
            errors += 1
            print(f"\nError processing {course_dir.name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Display comprehensive summary
    print("\n" + "=" * 80)
    print("UPLOAD SUMMARY")
    print("=" * 80)
    print(f"Total Courses Processed: {processed}")
    print(f"Errors: {errors}")
    
    if all_stats and not args.dry_run:
        print("\n" + "-" * 80)
        print("DETAILED BREAKDOWN BY COURSE")
        print("-" * 80)
        
        total_chapters_created = 0
        total_chapters_updated = 0
        total_worksheets_created = 0
        total_worksheets_updated = 0
        total_mcqs_created = 0
        total_mcqs_updated = 0
        total_mcq_questions = 0
        total_mcq_activities_created = 0
        total_mcq_activities_updated = 0
        total_pdfs_uploaded = 0
        
        for stats in all_stats:
            course_name = stats.get('course_name', 'Unknown')
            course_id = stats.get('course_id')
            course_status = "CREATED" if stats.get('course_created') else "UPDATED" if stats.get('course_updated') else "N/A"
            
            print(f"\n📚 Course: {course_name}")
            print(f"   ID: {course_id} | Status: {course_status}")
            
            # Chapters
            chapters = stats.get('chapters', [])
            chapters_created = sum(1 for c in chapters if c.get('created'))
            chapters_updated = sum(1 for c in chapters if c.get('updated'))
            total_chapters_created += chapters_created
            total_chapters_updated += chapters_updated
            
            if chapters:
                print(f"   📖 Chapters: {len(chapters)} total ({chapters_created} created, {chapters_updated} updated)")
                for ch in chapters:
                    status = "CREATED" if ch.get('created') else "UPDATED"
                    print(f"      - {ch.get('name')} (ID: {ch.get('id')}) [{status}]")
            
            # Worksheets
            worksheets = stats.get('worksheets', [])
            worksheets_created = sum(1 for w in worksheets if w.get('created'))
            worksheets_updated = sum(1 for w in worksheets if w.get('updated'))
            total_worksheets_created += worksheets_created
            total_worksheets_updated += worksheets_updated
            
            if worksheets:
                print(f"   📝 Worksheets: {len(worksheets)} total ({worksheets_created} created, {worksheets_updated} updated)")
                for ws in worksheets:
                    status = "CREATED" if ws.get('created') else "UPDATED"
                    print(f"      - {ws.get('chapter')} (Activity ID: {ws.get('activity_id')}) [{status}]")
            
            # MCQs
            mcqs = stats.get('mcqs', [])
            mcqs_created = sum(1 for m in mcqs if m.get('created'))
            mcqs_updated = sum(1 for m in mcqs if m.get('updated'))
            total_mcqs_created += mcqs_created
            total_mcqs_updated += mcqs_updated
            
            if mcqs:
                print(f"   ❓ MCQs: {len(mcqs)} total ({mcqs_created} created, {mcqs_updated} updated)")
                for mcq in mcqs:
                    status = "CREATED" if mcq.get('created') else "UPDATED"
                    q_created = mcq.get('questions_created', 0)
                    q_updated = mcq.get('questions_updated', 0)
                    total_q = mcq.get('total_questions', 0)
                    total_mcq_questions += total_q
                    print(f"      - {mcq.get('title')} (ID: {mcq.get('mcq_id')}) [{status}]")
                    print(f"        Questions: {total_q} total ({q_created} created, {q_updated} updated)")
            
            # MCQ Activities
            mcq_activities = stats.get('mcq_activities', [])
            mcq_acts_created = sum(1 for a in mcq_activities if a.get('created'))
            mcq_acts_updated = sum(1 for a in mcq_activities if a.get('updated'))
            total_mcq_activities_created += mcq_acts_created
            total_mcq_activities_updated += mcq_acts_updated
            
            if mcq_activities:
                print(f"   🎯 MCQ Activities: {len(mcq_activities)} total ({mcq_acts_created} created, {mcq_acts_updated} updated)")
                for act in mcq_activities:
                    status = "CREATED" if act.get('created') else "UPDATED"
                    print(f"      - {act.get('chapter')} (Activity ID: {act.get('activity_id')}) [{status}]")
            
            # PDFs
            pdfs = stats.get('pdfs_uploaded', 0)
            total_pdfs_uploaded += pdfs
            if pdfs > 0:
                print(f"   📄 PDFs Uploaded: {pdfs}")
        
        # Overall totals
        print("\n" + "=" * 80)
        print("OVERALL TOTALS")
        print("=" * 80)
        print(f"Courses: {len(all_stats)} processed")
        print(f"Chapters: {total_chapters_created + total_chapters_updated} total ({total_chapters_created} created, {total_chapters_updated} updated)")
        print(f"Worksheets: {total_worksheets_created + total_worksheets_updated} total ({total_worksheets_created} created, {total_worksheets_updated} updated)")
        print(f"MCQs: {total_mcqs_created + total_mcqs_updated} total ({total_mcqs_created} created, {total_mcqs_updated} updated)")
        print(f"MCQ Questions: {total_mcq_questions} total")
        print(f"MCQ Activities: {total_mcq_activities_created + total_mcq_activities_updated} total ({total_mcq_activities_created} created, {total_mcq_activities_updated} updated)")
        print(f"PDFs Uploaded: {total_pdfs_uploaded}")
    
    if args.dry_run:
        print("\n" + "=" * 80)
        print("⚠️  This was a DRY RUN. No changes were made to the database.")
        print("=" * 80)
    
    print()


if __name__ == "__main__":
    main()
