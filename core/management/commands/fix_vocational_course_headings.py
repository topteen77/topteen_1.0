from __future__ import annotations

import json
import re
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import VocationalCourse


# Fixed accordion headings
FIXED_HEADINGS = [
    'Overview',
    'Eligibility & Admission',
    'Duration & Structure',
    'Curriculum Highlights',
    'Skills Required',
    'Pros & Cons',
    'Internship & Industry Collaborations',
    'Certification & Accreditation',
    'Learning Outcomes',
    'Career Growth & Prospects',
    'Employment Sectors & Employers',
    'Conclusion'
]

# Keyword mapping for better matching
KEYWORD_MAP = {
    'overview': ['overview', 'introduction', 'intro', 'about', 'summary', 'description', 'general', 'brief'],
    'eligibility_admission': ['eligibility', 'admission', 'admit', 'entry', 'requirement', 'qualification', 'criteria'],
    'duration_structure': ['duration', 'structure', 'length', 'period', 'time', 'year', 'semester', 'term'],
    'curriculum_highlights': ['curriculum', 'syllabus', 'course', 'subject', 'module', 'highlight', 'content', 'study'],
    'skills_required': ['skill', 'ability', 'competence', 'proficiency', 'capability', 'talent'],
    'pros_cons': ['pros', 'cons', 'advantage', 'disadvantage', 'benefit', 'drawback', 'merit', 'demerit', 'strength', 'weakness'],
    'internship_industry_collaborations': ['internship', 'industry', 'collaboration', 'training', 'practical', 'exposure', 'attachment', 'placement'],
    'certification_accreditation': ['certification', 'accreditation', 'certificate', 'accredit', 'license', 'credential', 'diploma'],
    'learning_outcomes': ['learning', 'outcome', 'result', 'achievement', 'objective', 'goal', 'target'],
    'career_growth_prospects': ['career', 'growth', 'prospect', 'opportunity', 'advancement', 'progress', 'future', 'scope'],
    'employment_sectors_employers': ['employment', 'sector', 'employer', 'recruiter', 'company', 'organization', 'job', 'work'],
    'conclusion': ['conclusion', 'summary', 'final', 'overall', 'wrap', 'end']
}


def normalize_text(text):
    """Normalize text for comparison - handles 'and' vs '&', removes punctuation"""
    if not text:
        return ''
    # Convert to lowercase and normalize 'and' to '&' for comparison
    normalized = text.lower().strip()
    # Replace 'and' with '&' for better matching
    normalized = re.sub(r'\s+and\s+', ' & ', normalized)
    normalized = re.sub(r'\s+&\s+', ' & ', normalized)
    # Remove all non-alphanumeric except spaces and &
    normalized = re.sub(r'[^a-z0-9\s&]', '', normalized)
    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def match_heading_to_section(heading_text):
    """Match a heading text to one of the fixed sections"""
    if not heading_text or len(heading_text.strip()) < 5:
        return None
    
    # Remove trailing colons and normalize
    heading_text = heading_text.rstrip(':').strip()
    normalized_heading = normalize_text(heading_text)
    heading_word_count = len(normalized_heading.split())
    
    best_match = None
    best_score = 0
    
    # First try exact or partial match with fixed headings
    for fixed_heading in FIXED_HEADINGS:
        normalized_fixed = normalize_text(fixed_heading)
        fixed_word_count = len(normalized_fixed.split())
        key = re.sub(r'[^a-z0-9]+', '_', fixed_heading.lower())
        
        # Exact match after normalization
        if normalized_heading == normalized_fixed:
            return key
        
        # Prevent single-word headings from matching multi-word fixed headings
        # (e.g., "Pros" should not match "Pros & Cons")
        if heading_word_count == 1 and fixed_word_count > 1:
            # Only allow if the single word is the first word of the fixed heading
            fixed_first_word = normalized_fixed.split()[0]
            if normalized_heading == fixed_first_word:
                # This is a sub-heading, don't match
                continue
        
        # Check if one contains the other (for partial matches)
        # But require at least 75% similarity to avoid matching sub-headings
        if normalized_heading in normalized_fixed or normalized_fixed in normalized_heading:
            # Calculate similarity score
            shorter = min(len(normalized_heading), len(normalized_fixed))
            longer = max(len(normalized_heading), len(normalized_fixed))
            score = (shorter / longer) * 100
            # Require at least 75% match to avoid sub-headings
            if score >= 75 and score > best_score:
                best_match = key
                best_score = score
        
        # Also check word-by-word matching for better accuracy
        heading_words = set(normalized_heading.split())
        fixed_words = set(normalized_fixed.split())
        if heading_words and fixed_words:
            # Calculate Jaccard similarity (intersection over union)
            intersection = len(heading_words & fixed_words)
            union = len(heading_words | fixed_words)
            if union > 0:
                jaccard_score = (intersection / union) * 100
                # Check if heading contains all key words from fixed heading
                # (e.g., "Employment Sectors and Examples of Employers" contains "Employment", "Sectors", "Employers")
                key_words_match = len(fixed_words & heading_words)
                key_words_ratio = key_words_match / len(fixed_words) if fixed_words else 0
                
                # If heading contains most key words from fixed heading, it's a match
                if key_words_ratio >= 0.7:  # At least 70% of fixed heading words are present
                    score = key_words_ratio * 100
                    if score > best_score:
                        best_match = key
                        best_score = score
                # Also check Jaccard similarity with word count consideration
                word_count_ratio = min(heading_word_count, fixed_word_count) / max(heading_word_count, fixed_word_count)
                if jaccard_score >= 60 and word_count_ratio >= 0.5 and jaccard_score > best_score:
                    best_match = key
                    best_score = jaccard_score
    
    # If no good match found, try keyword matching (but be very strict)
    if best_score < 65:
        for key, keywords in KEYWORD_MAP.items():
            matched_keywords = []
            for keyword in keywords:
                # Only match if keyword is a significant part of the heading
                if keyword in normalized_heading and len(keyword) >= 4:
                    matched_keywords.append(keyword)
            
            if matched_keywords:
                # For single-word headings, don't match multi-word sections
                if heading_word_count == 1:
                    # Skip single-word matches to multi-word sections
                    continue
                
                # Calculate score based on matched keywords
                total_keyword_length = sum(len(kw) for kw in matched_keywords)
                heading_length = len(normalized_heading)
                
                # Multi-word heading - require at least 60% keyword coverage
                score = (total_keyword_length / heading_length) * 70
                
                if score > best_score:
                    best_match = key
                    best_score = score
    
    # Require at least 60% match to avoid sub-headings
    return best_match if best_score >= 60 else None


def convert_headings_to_h2(html_content, verbose=False):
    """Convert headings in <p><strong> format to H2 tags for fixed sections"""
    if not html_content:
        return html_content, 0
    
    soup = BeautifulSoup(html_content, 'html.parser')
    converted_count = 0
    converted_headings = []
    
    # First, find and convert <p><strong>Heading Text</strong></p> patterns
    # This is the main requirement: convert <p><strong>Heading</strong></p> to <h2>Heading</h2>
    for p in soup.find_all('p'):
        # Check if paragraph contains a strong tag
        strong_tags = p.find_all(['strong', 'b'])
        
        if strong_tags:
            # Get the text from the first strong tag
            strong_text = strong_tags[0].get_text(strip=True)
            
            # Check if this matches any of the fixed headings
            if strong_text:
                # Try exact match first (case-insensitive, whitespace normalized)
                exact_match = None
                for fixed_heading in FIXED_HEADINGS:
                    if normalize_text(strong_text) == normalize_text(fixed_heading):
                        exact_match = fixed_heading
                        break
                
                # If exact match found, convert entire paragraph to H2
                if exact_match:
                    h2_tag = soup.new_tag('h2')
                    h2_tag.string = exact_match
                    p.replace_with(h2_tag)
                    converted_count += 1
                    converted_headings.append(f'"{strong_text}" -> "{exact_match}"')
                    continue
                
                # Try fuzzy matching for close matches
                matched_key = match_heading_to_section(strong_text)
                if matched_key:
                    # Find the exact fixed heading text
                    for fixed_heading in FIXED_HEADINGS:
                        key = re.sub(r'[^a-z0-9]+', '_', fixed_heading.lower())
                        if key == matched_key:
                            h2_tag = soup.new_tag('h2')
                            h2_tag.string = fixed_heading
                            p.replace_with(h2_tag)
                            converted_count += 1
                            converted_headings.append(f'"{strong_text}" -> "{fixed_heading}"')
                            break
    
    # Also convert existing headings (h1, h3-h6) to H2 if they match fixed sections
    all_headings = soup.find_all(['h1', 'h3', 'h4', 'h5', 'h6'])
    for heading in all_headings:
        heading_text = heading.get_text(strip=True)
        if not heading_text:
            continue
        
        # Check exact match first
        exact_match = None
        for fixed_heading in FIXED_HEADINGS:
            if heading_text.strip() == fixed_heading.strip():
                exact_match = fixed_heading
                break
        
        if exact_match:
            h2_tag = soup.new_tag('h2')
            h2_tag.string = exact_match
            heading.replace_with(h2_tag)
            converted_count += 1
            converted_headings.append(f'"{heading_text}" (h{heading.name}) -> "{exact_match}" (h2)')
        else:
            # Try fuzzy matching
            matched_key = match_heading_to_section(heading_text)
            if matched_key:
                # Find the exact fixed heading text
                for fixed_heading in FIXED_HEADINGS:
                    key = re.sub(r'[^a-z0-9]+', '_', fixed_heading.lower())
                    if key == matched_key:
                        h2_tag = soup.new_tag('h2')
                        h2_tag.string = fixed_heading
                        heading.replace_with(h2_tag)
                        converted_count += 1
                        converted_headings.append(f'"{heading_text}" (h{heading.name}) -> "{fixed_heading}" (h2)')
                        break
    
    # Normalize existing H2 headings to match exact fixed heading text
    # This ensures all H2 headings use the exact fixed heading text (e.g., "&" instead of "and")
    h2_headings = soup.find_all('h2')
    for h2 in h2_headings:
        h2_text = h2.get_text(strip=True)
        if not h2_text:
            continue
        
        matched_key = match_heading_to_section(h2_text)
        if matched_key:
            # Find the exact fixed heading text
            for fixed_heading in FIXED_HEADINGS:
                key = re.sub(r'[^a-z0-9]+', '_', fixed_heading.lower())
                if key == matched_key:
                    if h2_text != fixed_heading:
                        h2.string = fixed_heading
                        converted_count += 1  # Count normalization as a conversion
                        converted_headings.append(f'"{h2_text}" (h2) -> "{fixed_heading}" (h2 normalized)')
                    break
    
    return str(soup), converted_count, converted_headings


def section_html_is_trivial(html: str | None) -> bool:
    """True if fragment has no visible text (empty, whitespace, or nbsp-only paragraphs)."""
    if not html or not str(html).strip():
        return True
    soup = BeautifulSoup(str(html), "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"[\xa0\s]+", " ", text).strip()
    return len(text) == 0


def extract_body_before_first_heading(soup: BeautifulSoup, first_heading) -> str:
    """HTML before the first top-level heading (hero, subtitle, intro before Overview h2)."""
    if not first_heading:
        return ""
    content_before: list[str] = []
    current = soup.contents[0] if soup.contents else None
    while current and current != first_heading:
        if hasattr(current, "name") and current.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            break
        if current and str(current).strip():
            content_before.append(str(current))
        current = current.next_sibling if hasattr(current, "next_sibling") else None
    return "".join(content_before).strip()


def extract_content_until_next_heading(element, all_elements, current_index):
    """Extract all content until the next heading"""
    content = []
    i = current_index + 1
    
    while i < len(all_elements):
        elem = all_elements[i]
        
        # Stop if we hit another heading
        if elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            break
        
        # Collect the element
        content.append(str(elem))
        i += 1
    
    return ''.join(content)


def generate_content_json(html_content, course_name=None):
    """Generate content_json from HTML content
    
    Args:
        html_content: HTML content to parse
        course_name: Name of the course (for programtitle)
    
    Returns:
        dict with structure:
        {
            'programtitle': course_name,
            'overview': overview_content,
            'sections': {...}
        }
    """
    if not html_content:
        return {
            'programtitle': course_name or '',
            'overview': '',
            'sections': {}
        }
    
    soup = BeautifulSoup(html_content, 'html.parser')
    accordion_data = {}
    
    # Initialize all sections
    for heading in FIXED_HEADINGS:
        key = re.sub(r'[^a-z0-9]+', '_', heading.lower())
        accordion_data[key] = {
            'title': heading,
            'html': ''
        }
    
    # Get all elements
    all_elements = list(soup.children)
    
    # Find all H2 headings
    h2_headings = soup.find_all('h2')
    
    if not h2_headings:
        # No H2 headings found, try other heading tags
        h2_headings = soup.find_all(['h1', 'h3', 'h4', 'h5', 'h6'])
    
    # First, identify which headings match fixed sections
    matched_headings_info = []
    for i, heading in enumerate(h2_headings):
        heading_text = heading.get_text(strip=True)
        if not heading_text:
            continue
        
        matched_key = match_heading_to_section(heading_text)
        if matched_key:
            matched_headings_info.append({
                'index': i,
                'heading': heading,
                'key': matched_key,
                'text': heading_text
            })
    
    # Process each matched heading and extract content until next matched heading
    for idx, heading_info in enumerate(matched_headings_info):
        heading = heading_info['heading']
        matched_key = heading_info['key']
        
        # Find the next matched heading (if any)
        next_matched_heading = None
        if idx + 1 < len(matched_headings_info):
            next_matched_heading = matched_headings_info[idx + 1]['heading']
        
        # Extract all content after this heading until the next matched heading
        content_elements = []
        current = heading.next_sibling
        
        while current:
            # Stop only if we hit the next matched heading
            if next_matched_heading and current == next_matched_heading:
                break
            
            # Also stop if we hit any heading that matches a fixed section (safety check)
            if hasattr(current, 'name') and current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                current_text = current.get_text(strip=True)
                if current_text and match_heading_to_section(current_text):
                    # This is another matched section heading, stop here
                    break
            
            # Include all content (including sub-headings, paragraphs, lists, etc.)
            if current and str(current).strip():
                content_elements.append(str(current))
            
            current = current.next_sibling
        
        content_html = ''.join(content_elements).strip()
        
        # Update accordion data
        if matched_key in accordion_data:
            # If there's already content (from sub-headings), append it
            existing_content = accordion_data[matched_key]['html']
            if existing_content and content_html:
                accordion_data[matched_key]['html'] = existing_content + content_html
            elif content_html:
                accordion_data[matched_key]['html'] = content_html
            
            # Update title to match fixed heading exactly
            for h in FIXED_HEADINGS:
                key = re.sub(r'[^a-z0-9]+', '_', h.lower())
                if key == matched_key:
                    accordion_data[matched_key]['title'] = h
                    break
    
    # Extract overview: use body between Overview h2 and next section, but if that is only
    # placeholders, pull hero/subtitle HTML from before the first heading (e.g. parenthetical
    # under the title that sits above <h2>Overview</h2>).
    overview_content = ''
    overview_key = 'overview'
    before_first = ''
    if h2_headings:
        before_first = extract_body_before_first_heading(soup, h2_headings[0])

    inner_overview = ''
    if overview_key in accordion_data:
        inner_overview = (accordion_data[overview_key]['html'] or '').strip()

    if overview_key in accordion_data:
        if section_html_is_trivial(inner_overview):
            if before_first:
                accordion_data[overview_key]['html'] = before_first
                overview_content = before_first
            else:
                accordion_data[overview_key]['html'] = ''
                overview_content = ''
        else:
            overview_content = inner_overview
            if before_first and not section_html_is_trivial(before_first):
                inner_plain = BeautifulSoup(inner_overview, 'html.parser').get_text(' ', strip=True)
                lead_plain = BeautifulSoup(before_first, 'html.parser').get_text(' ', strip=True)
                if lead_plain and lead_plain[:40] not in inner_plain:
                    merged = (before_first.rstrip() + inner_overview).strip()
                    accordion_data[overview_key]['html'] = merged
                    overview_content = merged
    
    # Build final JSON structure
    result = {
        'programtitle': course_name or '',
        'overview': overview_content,
        'sections': accordion_data
    }
    
    return result


class Command(BaseCommand):
    help = 'Fix vocational course headings: convert to H2 and update content_json'

    def add_arguments(self, parser):
        parser.add_argument(
            '--course-id',
            type=int,
            help='Process only a specific course by ID',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without saving',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        course_id = options.get('course_id')
        dry_run = options.get('dry_run', False)
        
        # Get courses to process
        if course_id:
            courses = VocationalCourse.objects.filter(pk=course_id)
        else:
            courses = VocationalCourse.objects.filter(content_html__isnull=False).exclude(content_html='')
        
        total_courses = courses.count()
        self.stdout.write(self.style.SUCCESS(f'Found {total_courses} course(s) to process'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))
        
        processed = 0
        updated = 0
        errors = 0
        
        for course in courses:
            try:
                if not course.content_html:
                    self.stdout.write(self.style.WARNING(f'Skipping course {course.id} ({course.name}): No content_html'))
                    continue
                
                # Always regenerate JSON (overwrite existing if any)
                self.stdout.write(f'\nProcessing course {course.id}: {course.name}')
                
                # Convert headings to H2
                updated_html, converted_count, converted_headings = convert_headings_to_h2(course.content_html, verbose=options.get('verbosity', 1) > 1)
                
                if converted_count > 0:
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Converted {converted_count} heading(s) to H2:'))
                    for heading_info in converted_headings:
                        self.stdout.write(f'    - {heading_info}')
                else:
                    self.stdout.write(f'  - No headings converted (may already be H2 or no matching headings found)')
                
                # Generate content_json
                content_json = generate_content_json(updated_html, course_name=course.name)
                
                # Count sections with content
                sections_with_content = sum(1 for s in content_json.get('sections', {}).values() if s.get('html', '').strip())
                overview_has_content = bool(content_json.get('overview', '').strip())
                self.stdout.write(f'  ✓ Generated JSON with {sections_with_content} section(s) containing content')
                if overview_has_content:
                    self.stdout.write(f'  ✓ Overview content extracted ({len(content_json.get("overview", ""))} chars)')
                if content_json.get('programtitle'):
                    self.stdout.write(f'  ✓ Program title: {content_json.get("programtitle")}')
                
                if not dry_run:
                    # Update database
                    course.content_html = updated_html
                    course.content_json = content_json
                    course.save(update_fields=['content_html', 'content_json'])
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Saved to database'))
                    updated += 1
                else:
                    self.stdout.write(self.style.WARNING(f'  [DRY RUN] Would save to database'))
                
                processed += 1
                
            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Error processing course {course.id}: {str(e)}'))
                import traceback
                self.stdout.write(traceback.format_exc())
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'Summary:'))
        self.stdout.write(f'  Total courses: {total_courses}')
        self.stdout.write(f'  Processed: {processed}')
        self.stdout.write(f'  Updated: {updated}')
        self.stdout.write(f'  Errors: {errors}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nThis was a DRY RUN. No changes were saved.'))
            self.stdout.write('Run without --dry-run to apply changes.')
