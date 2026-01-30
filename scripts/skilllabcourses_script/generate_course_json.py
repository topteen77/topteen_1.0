#!/usr/bin/env python3
"""
Generate JSON file for a single course for manual verification.
Extracts course structure with chapters divided into sections (h2 headings).
"""

import os
import sys
import re
import json
from pathlib import Path
from typing import Optional, Dict, List
from bs4 import BeautifulSoup

# Configuration
PROCESSED_DIR = Path("/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/topteen_1.0/skilllabcourses_html")
OUTPUT_JSON_DIR = Path("/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/topteen_1.0/scripts/skilllabcourses_script/course_json")


def read_html_file(html_path: Path) -> Optional[str]:
    """Read HTML file and return content as string."""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"  Error reading {html_path}: {e}")
        return None


def extract_body_content(html_content: str) -> str:
    """Extract body content from HTML, or return as-is if no body tag."""
    soup = BeautifulSoup(html_content, 'html.parser')
    body = soup.find('body')
    if body:
        return ''.join(str(child) for child in body.children)
    return html_content


def extract_sections_from_chapter(chapter_html: str) -> List[Dict]:
    """
    Extract sections (h2 headings) from chapter HTML.
    Returns list of sections with heading and content.
    """
    soup = BeautifulSoup(chapter_html, 'html.parser')
    body = soup.find('body')
    if not body:
        body = soup
    
    sections = []
    current_section = []
    current_heading = None
    current_heading_text = None
    
    # Get all elements in document order
    all_elements = body.find_all(['h1', 'h2', 'p', 'ul', 'ol', 'table', 'div', 'h3', 'h4', 'h5', 'h6'])
    
    for element in all_elements:
        # Skip if element is nested inside another element we've already processed
        parent = element.parent
        if parent and parent.name in ['p', 'li', 'td', 'th', 'div', 'ul', 'ol']:
            if parent in all_elements:
                continue
        
        if element.name == 'h1':
            # Skip chapter heading (h1)
            continue
        elif element.name == 'h2':
            # Save previous section if exists
            if current_heading_text and current_section:
                sections.append({
                    'heading': current_heading_text,
                    'heading_html': str(current_heading),
                    'content': '\n'.join(str(e) for e in current_section),
                    'content_html': ''.join(str(e) for e in current_section)
                })
            # Start new section
            current_heading = element
            current_heading_text = element.get_text(strip=True)
            current_section = []
        else:
            # Add to current section (including content before first h2)
            if current_heading_text or not sections:
                current_section.append(element)
    
    # Add last section
    if current_heading_text and current_section:
        sections.append({
            'heading': current_heading_text,
            'heading_html': str(current_heading),
            'content': '\n'.join(str(e) for e in current_section),
            'content_html': ''.join(str(e) for e in current_section)
        })
    elif current_section and not sections:
        # Content before first h2 (intro content)
        sections.append({
            'heading': 'Introduction',
            'heading_html': '<h2>Introduction</h2>',
            'content': '\n'.join(str(e) for e in current_section),
            'content_html': ''.join(str(e) for e in current_section)
        })
    
    return sections


def process_course_for_json(course_dir: Path) -> Optional[Dict]:
    """
    Process a single course and generate JSON structure.
    """
    course_name = course_dir.name
    print(f"Processing course: {course_name}")
    
    # Read course intro and index
    course_intro_html = None
    course_index_html = None
    
    # Try multiple possible file names for intro
    intro_paths = [
        course_dir / "course_intro.html",
        course_dir / "intro-course.html",  # Alternative naming
    ]
    
    for intro_path in intro_paths:
        if intro_path.exists():
            course_intro_html = read_html_file(intro_path)
            if course_intro_html:
                course_intro_html = extract_body_content(course_intro_html)
                if course_intro_html and course_intro_html.strip():
                    print(f"  Found course intro: {intro_path.name} ({len(course_intro_html)} chars)")
                    break
            course_intro_html = None  # Reset if empty
    
    if not course_intro_html:
        print(f"  Warning: Course intro HTML not found or empty")
    
    # Try multiple possible file names for index
    index_paths = [
        course_dir / "course_index.html",
        course_dir / "index.html",  # Alternative naming
    ]
    
    for index_path in index_paths:
        if index_path.exists():
            course_index_html = read_html_file(index_path)
            if course_index_html:
                course_index_html = extract_body_content(course_index_html)
                if course_index_html and course_index_html.strip():
                    print(f"  Found course index: {index_path.name} ({len(course_index_html)} chars)")
                    break
            course_index_html = None  # Reset if empty
    
    if not course_index_html:
        print(f"  Warning: Course index HTML not found or empty")
    
    # Combine intro and index for description
    course_description = ""
    if course_intro_html:
        course_description += course_intro_html
    if course_index_html:
        if course_description:
            course_description += "\n\n"
        course_description += course_index_html
    
    if not course_description:
        course_description = f"Course: {course_name}"
    
    # Process chapters
    chapter_dirs = sorted(
        [d for d in course_dir.iterdir() if d.is_dir() and d.name.startswith("chapter_")],
        key=lambda x: int(re.search(r'\d+', x.name).group()) if re.search(r'\d+', x.name) else 0
    )
    
    chapters = []
    
    for chapter_dir in chapter_dirs:
        chapter_num_match = re.search(r'\d+', chapter_dir.name)
        if not chapter_num_match:
            continue
        
        chapter_num = int(chapter_num_match.group())
        
        # Try to extract actual chapter name from chapter HTML (h1 heading)
        chapter_name = f"Chapter {chapter_num}"  # Default
        chapter_html_path = chapter_dir / f"chapter{chapter_num}.html"
        if chapter_html_path.exists():
            chapter_html = read_html_file(chapter_html_path)
            if chapter_html:
                soup = BeautifulSoup(chapter_html, 'html.parser')
                h1 = soup.find('h1')
                if h1:
                    h1_text = h1.get_text(strip=True)
                    if h1_text and h1_text.startswith('Chapter'):
                        chapter_name = h1_text
                        print(f"  Found chapter name from HTML: {chapter_name}")
        
        print(f"  Processing {chapter_name}...")
        
        # Read intro
        intro_html = None
        intro_path = chapter_dir / "intro.html"
        if intro_path.exists():
            intro_html = read_html_file(intro_path)
            if intro_html:
                intro_html = extract_body_content(intro_html)
        
        # Read chapter HTML and extract sections
        chapter_html_path = chapter_dir / f"chapter{chapter_num}.html"
        sections = []
        
        if chapter_html_path.exists():
            chapter_html = read_html_file(chapter_html_path)
            if chapter_html:
                sections = extract_sections_from_chapter(chapter_html)
                print(f"    Found {len(sections)} sections")
        
        # Check for worksheet
        worksheet_pdf_path = chapter_dir / f"worksheet{chapter_num}.pdf"
        has_worksheet = worksheet_pdf_path.exists()
        
        # Check for MCQ
        mcq_json_path = chapter_dir / f"chapter{chapter_num}-mcq.json"
        mcq_data = None
        if mcq_json_path.exists():
            try:
                with open(mcq_json_path, 'r', encoding='utf-8') as f:
                    mcq_data = json.load(f)
            except Exception as e:
                print(f"    Warning: Could not read MCQ JSON: {e}")
        
        chapter_info = {
            'chapter_number': chapter_num,
            'chapter_name': chapter_name,
            'intro_html': intro_html,
            'sections': sections,
            'has_worksheet': has_worksheet,
            'worksheet_pdf': str(worksheet_pdf_path) if has_worksheet else None,
            'has_mcq': mcq_data is not None,
            'mcq_data': mcq_data
        }
        
        chapters.append(chapter_info)
    
    course_data = {
        'course_name': course_name,
        'course_description': course_description,
        'course_intro_html': course_intro_html,
        'course_index_html': course_index_html,
        'total_chapters': len(chapters),
        'chapters': chapters
    }
    
    return course_data


def main():
    """Main function to generate course JSON."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate JSON file for course verification')
    parser.add_argument('--course', type=str, help='Course name to process (required if --all not used)')
    parser.add_argument('--all', action='store_true', help='Process all courses')
    args = parser.parse_args()
    
    if not PROCESSED_DIR.exists():
        print(f"Error: Processed directory not found: {PROCESSED_DIR}")
        sys.exit(1)
    
    OUTPUT_JSON_DIR.mkdir(parents=True, exist_ok=True)
    
    # Determine which courses to process
    if args.all:
        # Get all course directories
        course_dirs = [d for d in PROCESSED_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')]
        if not course_dirs:
            print(f"Error: No course directories found in {PROCESSED_DIR}")
            sys.exit(1)
        course_dirs.sort()
        print("=" * 80)
        print("Course JSON Generator for Manual Verification - ALL COURSES")
        print("=" * 80)
        print(f"Found {len(course_dirs)} courses to process")
        print(f"Output directory: {OUTPUT_JSON_DIR}")
        print()
    else:
        if not args.course:
            parser.error("Either --course or --all must be specified")
        course_dirs = [PROCESSED_DIR / args.course]
        if not course_dirs[0].exists():
            print(f"Error: Course directory not found: {course_dirs[0]}")
            sys.exit(1)
        print("=" * 80)
        print("Course JSON Generator for Manual Verification")
        print("=" * 80)
        print(f"Course: {args.course}")
        print(f"Output directory: {OUTPUT_JSON_DIR}")
        print()
    
    # Process courses
    successful = []
    failed = []
    total_courses = len(course_dirs)
    
    for idx, course_dir in enumerate(course_dirs, 1):
        course_name = course_dir.name
        print(f"\n[{idx}/{total_courses}] Processing course: {course_name}")
        print("-" * 80)
        
        try:
            course_data = process_course_for_json(course_dir)
            
            if not course_data:
                print(f"  ✗ Error: Could not process course")
                failed.append(course_name)
                continue
            
            # Save JSON
            json_filename = f"{course_name.replace(' ', '_').replace('/', '_')}.json"
            json_path = OUTPUT_JSON_DIR / json_filename
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(course_data, f, indent=2, ensure_ascii=False)
            
            # Count sections
            total_sections = sum(len(ch.get('sections', [])) for ch in course_data['chapters'])
            
            print(f"  ✓ JSON saved: {json_path}")
            print(f"    Chapters: {course_data['total_chapters']}, Sections: {total_sections}")
            
            successful.append({
                'name': course_name,
                'json_file': json_filename,
                'chapters': course_data['total_chapters'],
                'sections': total_sections
            })
            
        except Exception as e:
            print(f"  ✗ Error processing {course_name}: {e}")
            import traceback
            traceback.print_exc()
            failed.append(course_name)
    
    # Summary
    print("\n" + "=" * 80)
    print("JSON GENERATION SUMMARY")
    print("=" * 80)
    print(f"Total courses: {total_courses}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    
    if successful:
        print("\n✓ Successfully generated JSON files:")
        for course in successful:
            print(f"  - {course['name']}")
            print(f"    File: {course['json_file']}")
            print(f"    Chapters: {course['chapters']}, Sections: {course['sections']}")
    
    if failed:
        print("\n✗ Failed courses:")
        for course_name in failed:
            print(f"  - {course_name}")
    
    print(f"\nAll JSON files saved to: {OUTPUT_JSON_DIR}")
    print()


if __name__ == "__main__":
    main()
