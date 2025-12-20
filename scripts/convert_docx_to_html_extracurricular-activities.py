#!/usr/bin/env python3
"""
DOCX → JSON Converter for Extracurricular Activities
Converts DOCX files to JSON format with sections as separate records.
Supports single file or batch processing.
"""

import os
import sys
import re
import json
import html
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from docx import Document
from docx.shared import Pt

# Standard section definitions matching activity_tags.py
STANDARD_SECTIONS = [
    {
        'id': 'overview',
        'title': 'Overview/Description',
        'icon': 'bx-info-circle',
        'description': 'Introduction and overview of the activity',
        'keywords': ['overview/description', 'overview', 'description', 'introduction']
    },
    {
        'id': 'objectives',
        'title': 'Objectives & Goals',
        'icon': 'bx-target-lock',
        'description': 'Academic excellence, critical thinking, competitive edge',
        'keywords': ['objectives', 'goals', 'purpose']
    },
    {
        'id': 'participation',
        'title': 'Participation Details',
        'icon': 'bx-log-in-circle',
        'description': 'Eligibility, registration and preparation steps',
        'keywords': ['participation', 'eligibility', 'registration', 'enrollment']
    },
    {
        'id': 'keyskills',
        'title': 'Key Skills / Benefits',
        'icon': 'bx-brain',
        'description': 'Problem solving, time management, teamwork',
        'keywords': ['skill', 'benefit', 'advantage', 'develop', 'enhance']
    },
    {
        'id': 'activities',
        'title': 'Activities & Involvement',
        'icon': 'bx-run',
        'description': 'Practice, workshops, bootcamps and forums',
        'keywords': ['activities', 'involvement', 'practice', 'workshop', 'bootcamp']
    },
    {
        'id': 'achievements',
        'title': 'Achievements & Recognition',
        'icon': 'bx-trophy',
        'description': 'Awards, scholarships and national ranking',
        'keywords': ['achievement', 'recognition', 'award', 'scholarship', 'ranking']
    },
    {
        'id': 'time',
        'title': 'Time Commitment & Scheduling',
        'icon': 'bx-time',
        'description': 'Weekly practice and intensive prep timelines',
        'keywords': ['time', 'commitment', 'scheduling', 'duration', 'schedule']
    },
    {
        'id': 'impact',
        'title': 'Impact on Development',
        'icon': 'bx-heart',
        'description': 'Confidence, networking and growth mindset',
        'keywords': ['impact', 'development', 'growth', 'personal', 'academic']
    },
    {
        'id': 'tips',
        'title': 'Tips for Success',
        'icon': 'bx-check-shield',
        'description': 'Start early, practice consistently, join groups',
        'keywords': ['tips', 'success', 'getting started', 'guide', 'advice']
    },
    {
        'id': 'resources',
        'title': 'Resources & Contact',
        'icon': 'bx-link',
        'description': 'Official sites, platforms and local support',
        'keywords': ['resources', 'contact', 'website', 'platform', 'support']
    },
    {
        'id': 'additional',
        'title': 'Additional Resources',
        'icon': 'bx-book-open',
        'description': 'Further reading, platforms and contact emails',
        'keywords': ['additional', 'more', 'further', 'extra', 'supplementary']
    }
]


def detect_and_linkify_urls(text: str) -> str:
    """Detect URLs in text and convert them to HTML links."""
    url_pattern = r'(https?://[^\s<>"{}|\\^`\[\]]+)'
    
    def replace_url(match):
        url = match.group(1)
        return f'<a href="{url}" target="_blank">{url}</a>'
    
    return re.sub(url_pattern, replace_url, text)


def to_html_entities(text: str) -> str:
    """Convert special characters to HTML entities."""
    if not text:
        return text
    
    text = html.escape(text, quote=False)
    
    result = []
    for char in text:
        codepoint = ord(char)
        if codepoint > 127:
            result.append(f'&#{codepoint};')
        else:
            result.append(char)
    
    return ''.join(result)


def runs_to_html(runs, paragraph_text=None) -> str:
    """Convert paragraph runs to HTML, handling soft enters."""
    parts = []
    all_run_text = ""
    
    for run in runs:
        try:
            text = run.text
            all_run_text += text
            if "\v" in text:
                segments = text.split("\v")
                for i, seg in enumerate(segments):
                    if i > 0:
                        parts.append("<br>")
                    parts.append(_format_run(seg, run))
                continue
            parts.append(_format_run(text, run))
        except Exception as e:
            print(f"Run processing error: {e}")
            continue
    
    # If paragraph_text is provided and contains more text than runs, append missing text
    # This handles cases where URLs or other text is in the paragraph but not in runs
    if paragraph_text and paragraph_text.strip():
        # Get all text from runs (without HTML tags)
        run_text_only = "".join([r.text for r in runs if hasattr(r, 'text')])
        if len(paragraph_text.strip()) > len(run_text_only.strip()):
            # Find the missing part
            missing_start = len(run_text_only)
            missing_text = paragraph_text[missing_start:].strip()
            if missing_text:
                # Format missing text (likely URLs or plain text)
                missing_text = html.escape(missing_text, quote=False)
                missing_text = to_html_entities(missing_text)
                missing_text = detect_and_linkify_urls(missing_text)
                parts.append(missing_text)
    
    return "".join(parts)


def _format_run(text: str, run) -> str:
    """Format a single text run with styling and links."""
    if not text:
        return ""
    text = text.replace("\t", "    ")
    
    # Handle hyperlinks
    try:
        if hasattr(run, 'hyperlink') and run.hyperlink:
            href = run.hyperlink.address or "#"
            if href and href != "#":
                escaped_text = html.escape(text, quote=False)
                escaped_text = to_html_entities(escaped_text)
                return f'<a href="{href}" target="_blank">{escaped_text}</a>'
    except Exception:
        pass
    
    # Apply HTML escaping
    text = html.escape(text, quote=False)
    text = to_html_entities(text)
    text = detect_and_linkify_urls(text)
    
    # Apply formatting
    try:
        if run.bold:
            text = f"<strong>{text}</strong>"
        if run.italic:
            text = f"<em>{text}</em>"
        if run.underline:
            text = f"<u>{text}</u>"
    except:
        pass
    return text


def get_font_size(run) -> float:
    """Get font size from run."""
    try:
        return run.font.size.pt if run.font.size else 11.0
    except:
        return 11.0


def is_numbered_heading(paragraph) -> Tuple[bool, Optional[str]]:
    """
    Check if paragraph is a numbered heading (e.g., "1. Title", "2. Title").
    Returns (is_heading, heading_text_without_number).
    """
    text = paragraph.text.strip()
    if not text:
        return False, None
    
    # Check for numbered pattern: "1. ", "2. ", "1.1. ", etc.
    match = re.match(r'^(\d+\.?\s*)+(.+)$', text)
    if match:
        heading_text = match.group(2).strip()
        # Check if it's a heading by font size or style
        if paragraph.runs:
            max_size = max((get_font_size(r) for r in paragraph.runs), default=11)
            if max_size >= 13 or any(r.bold for r in paragraph.runs):
                return True, heading_text
    
    return False, None


def map_heading_to_section(heading_text: str, position: int) -> Dict:
    """
    Map a heading text to a standard section.
    Uses keyword matching first, then position-based fallback.
    """
    heading_lower = heading_text.lower().strip()
    
    # Priority 1: Check for exact "Overview/Description" match first
    if 'overview/description' in heading_lower or ('overview' in heading_lower and 'description' in heading_lower):
        section = next((s for s in STANDARD_SECTIONS if s['id'] == 'overview'), None)
        if section:
            return {
                'section_id': section['id'],
                'title': section['title'],
                'icon': section['icon'],
                'description': section['description']
            }
    
    # Priority 2: Check for "Key Skills" or "Benefits" specifically
    if 'key skill' in heading_lower or ('skill' in heading_lower and 'benefit' in heading_lower) or 'skills developed' in heading_lower:
        section = next((s for s in STANDARD_SECTIONS if s['id'] == 'keyskills'), None)
        if section:
            return {
                'section_id': section['id'],
                'title': section['title'],
                'icon': section['icon'],
                'description': section['description']
            }
    
    # Priority 3: Check for "Additional Resources" or "Contact Information"
    if 'additional resources' in heading_lower or ('resources' in heading_lower and 'contact' in heading_lower):
        section = next((s for s in STANDARD_SECTIONS if s['id'] == 'resources'), None)
        if section:
            return {
                'section_id': section['id'],
                'title': section['title'],
                'icon': section['icon'],
                'description': section['description']
            }
    
    # Priority 4: Try keyword matching with priority order (most specific first)
    # Order matters - check more specific keywords first
    for section in STANDARD_SECTIONS:
        # Check if heading contains the section title (most specific match)
        section_title_lower = section['title'].lower()
        # Handle "Overview/Description" specially
        if section['id'] == 'overview':
            if 'overview' in heading_lower or ('overview' in heading_lower and 'description' in heading_lower):
                return {
                    'section_id': section['id'],
                    'title': section['title'],
                    'icon': section['icon'],
                    'description': section['description']
                }
        elif section_title_lower in heading_lower or heading_lower in section_title_lower:
            return {
                'section_id': section['id'],
                'title': section['title'],
                'icon': section['icon'],
                'description': section['description']
            }
        
        # Then check keywords (but skip 'overview' and 'description' for objectives)
        for keyword in section['keywords']:
            # Skip if this is objectives and keyword is overview/description (already handled)
            if section['id'] == 'objectives' and keyword in ['overview', 'description']:
                continue
            # Use word boundaries for more precise matching
            if re.search(r'\b' + re.escape(keyword) + r'\b', heading_lower):
                return {
                    'section_id': section['id'],
                    'title': section['title'],
                    'icon': section['icon'],
                    'description': section['description']
                }
    
    # Position-based fallback (1st = overview, 2nd = objectives, 3rd = participation, etc.)
    if position <= len(STANDARD_SECTIONS):
        section = STANDARD_SECTIONS[position - 1]
        return {
            'section_id': section['id'],
            'title': section['title'],
            'icon': section['icon'],
            'description': section['description']
        }
    
    # Default fallback
    return {
        'section_id': f'section_{position}',
        'title': heading_text,
        'icon': 'bx-star',
        'description': ''
    }


def extract_content_until_next_heading(paragraphs, start_idx: int) -> List:
    """Extract all content (paragraphs, lists) until the next numbered heading."""
    content = []
    i = start_idx + 1
    
    while i < len(paragraphs):
        para = paragraphs[i]
        is_heading, _ = is_numbered_heading(para)
        if is_heading:
            break
        
        # Include paragraph even if it appears empty (might have formatting)
        # Only skip if it's truly empty with no runs
        if para.text.strip() or para.runs:
            content.append(para)
        i += 1
    
    return content


def convert_content_to_html(content_paragraphs: List) -> str:
    """Convert a list of paragraphs to HTML."""
    html_parts = []
    in_list = False
    list_items = []
    
    for para in content_paragraphs:
        text = para.text.strip()
        para_html = runs_to_html(para.runs, para.text)
        
        # Skip only if truly empty (no text and no HTML content)
        if not text and not para_html.strip():
            continue
        
        # Check if it's a list item (starts with bullet or number)
        is_list_item = False
        if text:
            bullet_patterns = [
                r'^[•·▪▫‣⁃]',  # Unicode bullets
                r'^[-*+]',      # ASCII bullets
                r'^\d+[\.\)]',  # Numbered lists
                r'^[a-zA-Z][\.\)]',  # Letter lists
            ]
            for pattern in bullet_patterns:
                if re.match(pattern, text):
                    is_list_item = True
                    break
        
        # Check if paragraph starts with <strong> tag (bold text)
        starts_with_bold = para_html.strip().startswith('<strong>')
        
        # Special handling for Resources section structure:
        # - Organization names (bold, no colon) = paragraph
        # - Sub-headings ending with colon (bold) = paragraph  
        # - "Website: URL" = paragraph
        # - "Description: text" = paragraph
        # - Regular list items (with bullets/numbers) = list item
        
        # If it starts with bold and has a colon, it's likely a label (Website:, Description:, etc.) = paragraph
        if starts_with_bold and ':' in text and len(text) > 10:
            is_list_item = False
        # If it's just bold text ending with colon (sub-heading), it's a paragraph
        elif starts_with_bold and text.endswith(':') and len(text) < 100:
            is_list_item = False
        # If it's a bold organization name (no colon, short), it's a paragraph
        elif starts_with_bold and ':' not in text and len(text) < 100:
            is_list_item = False
        # Otherwise, if it starts with bold and is short, might be a list item
        elif starts_with_bold and len(text) < 150:
            # Check if it looks like a list item (ends with colon or has specific pattern)
            if ':' in text[:50]:
                is_list_item = True
        
        if is_list_item:
            if not in_list:
                if list_items:
                    html_parts.append('<ul>')
                    html_parts.extend(list_items)
                    html_parts.append('</ul>')
                    list_items = []
                html_parts.append('<ul>')
                in_list = True
            
            # Remove bullet characters
            clean_text = re.sub(r'^[•·▪▫‣⁃\-\*\+]\s*', '', text)
            clean_text = re.sub(r'^\d+[\.\)]\s*', '', clean_text)
            clean_text = re.sub(r'^[a-zA-Z][\.\)]\s*', '', clean_text)
            
            item_html = para_html
            # Remove prefix if already in HTML
            if clean_text and item_html:
                text_content = re.sub(r'<[^>]+>', '', item_html).strip()
                if text_content.startswith(clean_text.strip()):
                    item_html = re.sub(re.escape(clean_text.strip()) + r'\s*', '', item_html, count=1, flags=re.IGNORECASE)
            
            list_items.append(f'<li>{item_html or clean_text}</li>')
        else:
            if in_list:
                html_parts.extend(list_items)
                html_parts.append('</ul>')
                list_items = []
                in_list = False
            
            # Regular paragraph - include even if it's just formatting
            if para_html.strip():
                html_parts.append(f'<p>{para_html}</p>')
            elif text:
                # Has text but no HTML formatting - still include it
                html_parts.append(f'<p>{text}</p>')
    
    # Close any open list
    if in_list:
        html_parts.extend(list_items)
        html_parts.append('</ul>')
    
    result = ''.join(html_parts)
    # Fix double-encoded HTML entities
    result = result.replace('&amp;amp;', '&amp;')
    result = result.replace('&amp;lt;', '&lt;')
    result = result.replace('&amp;gt;', '&gt;')
    
    return result


def convert_docx_to_json(docx_path: Path) -> Optional[Dict]:
    """
    Convert a DOCX file to JSON structure with sections.
    Returns a dictionary with activity_name, category_name, and sections.
    """
    try:
        doc = Document(str(docx_path))
        
        # Extract main title (first large heading or document title)
        main_title = docx_path.stem
        paragraphs = doc.paragraphs
        
        # Find main title
        for para in paragraphs[:5]:  # Check first 5 paragraphs
            if para.runs:
                max_size = max((get_font_size(r) for r in para.runs), default=11)
                if max_size >= 18 or (max_size >= 15 and any(r.bold for r in para.runs)):
                    main_title = para.text.strip()
                    break
        
        # Find all numbered headings
        sections = []
        section_position = 0
        seen_section_ids = {}  # Track seen section_ids to merge duplicates
        
        for i, para in enumerate(paragraphs):
            is_heading, heading_text = is_numbered_heading(para)
            if is_heading:
                section_position += 1
                
                # Map to standard section
                section_meta = map_heading_to_section(heading_text, section_position)
                section_id = section_meta['section_id']
                
                # Extract content until next heading
                content_paragraphs = extract_content_until_next_heading(paragraphs, i)
                
                # Convert content to HTML
                content_html = convert_content_to_html(content_paragraphs)
                
                # If content is empty, try to get content from the heading paragraph itself
                if not content_html.strip():
                    # Check if there are runs after the heading text
                    para_html = runs_to_html(para.runs)
                    # Remove the heading part
                    heading_match = re.search(r'(\d+\.?\s*)+(.+?)(?=<|$)', para_html)
                    if heading_match:
                        remaining = para_html[heading_match.end():].strip()
                        if remaining:
                            content_html = f'<p>{remaining}</p>'
                
                # Check if we've seen this section_id before
                if section_id in seen_section_ids:
                    # Merge content with existing section
                    existing_idx = seen_section_ids[section_id]
                    existing_content = sections[existing_idx]['content_html']
                    # Combine content with a separator
                    if content_html.strip():
                        sections[existing_idx]['content_html'] = existing_content + '\n' + content_html
                else:
                    # New section
                    sections.append({
                        'section_id': section_id,
                        'title': section_meta['title'],
                        'content_html': content_html,
                        'order': len(sections) + 1,  # Use actual section count, not position
                        'icon': section_meta['icon'],
                        'description': section_meta['description']
                    })
                    seen_section_ids[section_id] = len(sections) - 1
        
        # Determine category from parent folder
        category_name = docx_path.parent.name
        
        return {
            'activity_name': main_title,
            'category_name': category_name,
            'sections': sections
        }
        
    except Exception as e:
        print(f"Error processing {docx_path}: {e}")
        import traceback
        traceback.print_exc()
        return None


def process_single_file(docx_path: Path, output_dir: Path) -> bool:
    """Process a single DOCX file and save JSON."""
    json_data = convert_docx_to_json(docx_path)
    if not json_data:
        return False
    
    # Create output directory structure
    rel_path = docx_path.relative_to(docx_path.parents[1])  # Relative to category parent
    output_file = output_dir / rel_path.parent / f"{docx_path.stem}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Save JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Converted: {docx_path.name} → {output_file}")
    return True


def process_directory(source_dir: Path, output_dir: Path):
    """Process all DOCX files in directory structure."""
    docx_files = [f for f in source_dir.rglob("*.docx") if not f.name.startswith("~$")]
    print(f"Found {len(docx_files)} .docx files")
    
    success = error = 0
    for docx in docx_files:
        try:
            if process_single_file(docx, output_dir):
                success += 1
            else:
                error += 1
        except Exception as e:
            error += 1
            print(f"✗ Failed: {docx}: {e}")
    
    print("\n=== SUMMARY ===")
    print(f"Processed : {success}")
    print(f"Errors    : {error}")
    print(f"Output    : {output_dir.resolve()}")


def main():
    """Main entry point with CLI arguments."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Convert DOCX files to JSON for extracurricular activities'
    )
    parser.add_argument(
        '--source',
        type=str,
        default='/home/itpc6/Public/django/git-repo/7nov/topteenhtml/content- Topteen/extracurricular activities',
        help='Source directory or file path'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='scripts/extracurricular_json_output',
        help='Output directory for JSON files'
    )
    parser.add_argument(
        '--file',
        type=str,
        help='Process a single DOCX file (overrides --source)'
    )
    
    args = parser.parse_args()
    
    source = Path(args.source)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    
    if args.file:
        # Single file mode
        docx_path = Path(args.file)
        if not docx_path.exists():
            print(f"Error: File not found: {docx_path}")
            sys.exit(1)
        
        if not docx_path.suffix.lower() == '.docx':
            print(f"Error: File must be a .docx file: {docx_path}")
            sys.exit(1)
        
        print(f"Processing single file: {docx_path}")
        if process_single_file(docx_path, output):
            print("✓ Conversion successful!")
        else:
            print("✗ Conversion failed!")
            sys.exit(1)
    else:
        # Directory mode (all files)
        if not source.exists():
            print(f"Error: Source directory not found: {source}")
            sys.exit(1)
        
        print(f"Source : {source}")
        print(f"Output : {output}\n")
        process_directory(source, output)


if __name__ == "__main__":
    main()

