#!/usr/bin/env python3
"""
Script to analyze Skill Lab Courses and generate HTML files.

This script:
1. Analyzes all 39 skill lab courses
2. Reads course structure (chapters, intro, worksheets, MCQs)
3. Generates a summary document
4. Converts chapter full content to HTML
5. Generates HTML files for course intro (non-logged-in view)
6. Creates download link structure for worksheets and MCQs
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

# Import convert_docx_to_html from same directory
from convert_docx_to_html import convert_docx_to_html


class CourseAnalyzer:
    def __init__(self, source_dir: str, output_dir: str):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.courses_data = []
        
    def sanitize_filename(self, name: str) -> str:
        """Convert course name to safe filename."""
        # Replace spaces and special chars with underscores
        safe = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in name)
        return safe.replace(' ', '_').strip('_')
    
    def analyze_course(self, course_path: Path) -> Dict:
        """Analyze a single course and return its structure."""
        course_name = course_path.name
        course_data = {
            'name': course_name,
            'safe_name': self.sanitize_filename(course_name),
            'path': str(course_path),
            'chapters': [],
            'course_intro': None,
            'index_file': None,
            'worksheets': [],
            'mcqs': [],
            'total_chapters': 0
        }
        
        # Find course intro file
        intro_patterns = ['course intro.docx', 'intro-course.docx', 'intro- course.docx']
        for pattern in intro_patterns:
            intro_file = course_path / pattern
            if intro_file.exists():
                course_data['course_intro'] = str(intro_file)
                break
        
        # Find index file
        index_file = course_path / 'index.docx'
        if index_file.exists():
            course_data['index_file'] = str(index_file)
        
        # Analyze chapters
        chapter_dirs = sorted([d for d in course_path.iterdir() 
                              if d.is_dir() and d.name.startswith('chapter')],
                             key=lambda x: self._extract_chapter_number(x.name))
        
        for chapter_dir in chapter_dirs:
            chapter_num = self._extract_chapter_number(chapter_dir.name)
            chapter_data = {
                'number': chapter_num,
                'name': chapter_dir.name,
                'full_content': None,
                'intro': None,
                'worksheet': None,
                'mcq': None
            }
            
            # Find chapter files - try multiple naming patterns
            chapter_file = None
            patterns = [
                f'chapter {chapter_num}.docx',
                f'chapter  {chapter_num}.docx',  # Double space
                f'CHAPTER {chapter_num}.docx',  # Uppercase
                f'Chapter {chapter_num}.docx',  # Title case
                f'{chapter_dir.name}.docx',
                f'Chapter{chapter_num}.docx',  # No space
                f'chapter{chapter_num}.docx',  # No space lowercase
            ]
            
            for pattern in patterns:
                test_file = chapter_dir / pattern
                if test_file.exists():
                    chapter_file = test_file
                    break
            
            if chapter_file and chapter_file.exists():
                chapter_data['full_content'] = str(chapter_file)
            
            # Find intro
            intro_file = chapter_dir / 'intro.docx'
            if intro_file.exists():
                chapter_data['intro'] = str(intro_file)
            
            # Find worksheet
            worksheet_file = chapter_dir / 'worksheet.docx'
            if not worksheet_file.exists():
                worksheet_file = chapter_dir / 'worksheets.docx'
            if worksheet_file.exists():
                chapter_data['worksheet'] = str(worksheet_file)
                course_data['worksheets'].append({
                    'chapter': chapter_num,
                    'path': str(worksheet_file)
                })
            
            # Find MCQ (check various naming patterns)
            mcq_patterns = ['mcq.docx', 'MCQ.docx', 'mcqs.docx', 'MCQs.docx']
            for pattern in mcq_patterns:
                mcq_file = chapter_dir / pattern
                if mcq_file.exists():
                    chapter_data['mcq'] = str(mcq_file)
                    course_data['mcqs'].append({
                        'chapter': chapter_num,
                        'path': str(mcq_file)
                    })
                    break
            
            course_data['chapters'].append(chapter_data)
        
        course_data['total_chapters'] = len(course_data['chapters'])
        return course_data
    
    def _extract_chapter_number(self, chapter_name: str) -> int:
        """Extract chapter number from directory name."""
        import re
        match = re.search(r'(\d+)', chapter_name)
        return int(match.group(1)) if match else 0
    
    def analyze_all_courses(self) -> List[Dict]:
        """Analyze all courses in the source directory."""
        print(f"Analyzing courses in: {self.source_dir}")
        
        # Get all course directories (exclude .docx files)
        course_dirs = [d for d in self.source_dir.iterdir() 
                      if d.is_dir() and not d.name.startswith('.')]
        
        print(f"Found {len(course_dirs)} course directories")
        
        for course_dir in sorted(course_dirs):
            print(f"\nAnalyzing: {course_dir.name}")
            try:
                course_data = self.analyze_course(course_dir)
                self.courses_data.append(course_data)
                print(f"  - Chapters: {course_data['total_chapters']}")
                print(f"  - Worksheets: {len(course_data['worksheets'])}")
                print(f"  - MCQs: {len(course_data['mcqs'])}")
            except Exception as e:
                print(f"  ERROR analyzing {course_dir.name}: {e}")
        
        return self.courses_data
    
    def generate_summary(self) -> str:
        """Generate a summary document of all courses."""
        summary_lines = [
            "# Skill Lab Courses Analysis Summary",
            "",
            f"**Total Courses:** {len(self.courses_data)}",
            f"**Analysis Date:** {Path(__file__).stat().st_mtime}",
            "",
            "---",
            ""
        ]
        
        # Overall statistics
        total_chapters = sum(c['total_chapters'] for c in self.courses_data)
        total_worksheets = sum(len(c['worksheets']) for c in self.courses_data)
        total_mcqs = sum(len(c['mcqs']) for c in self.courses_data)
        courses_with_intro = sum(1 for c in self.courses_data if c['course_intro'])
        
        summary_lines.extend([
            "## Overall Statistics",
            "",
            f"- Total Courses: {len(self.courses_data)}",
            f"- Total Chapters: {total_chapters}",
            f"- Total Worksheets: {total_worksheets}",
            f"- Total MCQs: {total_mcqs}",
            f"- Courses with Intro: {courses_with_intro}",
            "",
            "---",
            ""
        ])
        
        # Per-course details
        summary_lines.append("## Course Details")
        summary_lines.append("")
        
        for course in sorted(self.courses_data, key=lambda x: x['name']):
            summary_lines.extend([
                f"### {course['name']}",
                "",
                f"- **Safe Name:** `{course['safe_name']}`",
                f"- **Total Chapters:** {course['total_chapters']}",
                f"- **Course Intro:** {'✓' if course['course_intro'] else '✗'}",
                f"- **Index File:** {'✓' if course['index_file'] else '✗'}",
                f"- **Worksheets:** {len(course['worksheets'])}",
                f"- **MCQs:** {len(course['mcqs'])}",
                ""
            ])
            
            if course['chapters']:
                summary_lines.append("**Chapters:**")
                for ch in course['chapters']:
                    status = []
                    if ch['full_content']:
                        status.append("Content")
                    if ch['intro']:
                        status.append("Intro")
                    if ch['worksheet']:
                        status.append("Worksheet")
                    if ch['mcq']:
                        status.append("MCQ")
                    summary_lines.append(f"  - Chapter {ch['number']}: {', '.join(status)}")
                summary_lines.append("")
            
            summary_lines.append("---")
            summary_lines.append("")
        
        return "\n".join(summary_lines)
    
    def generate_course_html(self, course_data: Dict) -> bool:
        """Generate HTML files for a single course."""
        course_output_dir = self.output_dir / course_data['safe_name']
        course_output_dir.mkdir(parents=True, exist_ok=True)
        
        success = True
        
        # Generate course intro HTML (for non-logged-in users)
        if course_data['course_intro']:
            try:
                intro_html = convert_docx_to_html(Path(course_data['course_intro']))
                if intro_html:
                    intro_file = course_output_dir / 'intro.html'
                    with open(intro_file, 'w', encoding='utf-8') as f:
                        f.write(intro_html)
                    print(f"  ✓ Generated intro.html")
                else:
                    print(f"  ✗ Failed to convert intro")
                    success = False
            except Exception as e:
                print(f"  ✗ Error converting intro: {e}")
                success = False
        
        # Generate full course HTML (all chapters combined)
        full_course_html = []
        full_course_html.append("<!DOCTYPE html>")
        full_course_html.append("<html>")
        full_course_html.append("<head>")
        full_course_html.append("<meta charset='utf-8'>")
        full_course_html.append(f"<title>{course_data['name']}</title>")
        full_course_html.append("</head>")
        full_course_html.append("<body>")
        full_course_html.append(f"<h1>{course_data['name']}</h1>")
        
        # Process each chapter
        for chapter in sorted(course_data['chapters'], key=lambda x: x['number']):
            if not chapter['full_content']:
                continue
            
            try:
                chapter_html = convert_docx_to_html(Path(chapter['full_content']))
                if chapter_html:
                    # Extract body content (remove HTML wrapper)
                    import re
                    body_match = re.search(r'<body>(.*?)</body>', chapter_html, re.DOTALL | re.IGNORECASE)
                    if body_match:
                        chapter_body = body_match.group(1)
                        full_course_html.append(f"<div class='chapter' id='chapter-{chapter['number']}'>")
                        full_course_html.append(f"<h2>Chapter {chapter['number']}</h2>")
                        full_course_html.append(chapter_body)
                        full_course_html.append("</div>")
                        full_course_html.append("<hr>")
                    print(f"  ✓ Processed Chapter {chapter['number']}")
                else:
                    print(f"  ✗ Failed to convert Chapter {chapter['number']}")
                    success = False
            except Exception as e:
                print(f"  ✗ Error converting Chapter {chapter['number']}: {e}")
                success = False
        
        full_course_html.append("</body>")
        full_course_html.append("</html>")
        
        # Save full course HTML
        full_course_file = course_output_dir / 'full_course.html'
        with open(full_course_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(full_course_html))
        print(f"  ✓ Generated full_course.html")
        
        # Generate metadata JSON for download links
        metadata = {
            'course_name': course_data['name'],
            'safe_name': course_data['safe_name'],
            'total_chapters': course_data['total_chapters'],
            'worksheets': course_data['worksheets'],
            'mcqs': course_data['mcqs'],
            'chapters': [
                {
                    'number': ch['number'],
                    'has_worksheet': ch['worksheet'] is not None,
                    'has_mcq': ch['mcq'] is not None
                }
                for ch in course_data['chapters']
            ]
        }
        
        metadata_file = course_output_dir / 'metadata.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        print(f"  ✓ Generated metadata.json")
        
        return success
    
    def generate_all_html(self):
        """Generate HTML files for all courses."""
        print(f"\n{'='*60}")
        print("Generating HTML files...")
        print(f"{'='*60}\n")
        
        success_count = 0
        for course in self.courses_data:
            print(f"\nGenerating HTML for: {course['name']}")
            if self.generate_course_html(course):
                success_count += 1
        
        print(f"\n{'='*60}")
        print(f"Summary: {success_count}/{len(self.courses_data)} courses processed successfully")
        print(f"{'='*60}\n")
    
    def run(self):
        """Run the complete analysis and generation process."""
        print("="*60)
        print("Skill Lab Courses Analysis & HTML Generation")
        print("="*60)
        
        # Step 1: Analyze all courses
        self.analyze_all_courses()
        
        # Step 2: Generate summary
        print(f"\n{'='*60}")
        print("Generating summary...")
        print(f"{'='*60}\n")
        summary = self.generate_summary()
        summary_file = self.output_dir / 'COURSES_SUMMARY.md'
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(summary)
        print(f"Summary saved to: {summary_file}")
        
        # Step 3: Generate HTML files
        self.generate_all_html()
        
        # Step 4: Save JSON data
        json_file = self.output_dir / 'courses_data.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.courses_data, f, indent=2)
        print(f"\nCourse data JSON saved to: {json_file}")


def main():
    source_dir = "/home/itpc6/Public/share/content- Topteen/skill lab courses"
    output_dir = "/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/topteen_1.0/skilllabcourses_html"
    
    analyzer = CourseAnalyzer(source_dir, output_dir)
    analyzer.run()


if __name__ == "__main__":
    main()
