"""
Utility functions for converting DOCX files to HTML for Career admin.
Simple and production-ready implementation.
"""

import re
import html
from docx import Document
from bs4 import BeautifulSoup


def convert_docx_to_html(docx_file):
    """
    Convert uploaded DOCX file to HTML format.
    
    Args:
        docx_file: Django UploadedFile object
        
    Returns:
        str: HTML content of the document
    """
    doc = Document(docx_file)
    html_content = []
    
    for paragraph in doc.paragraphs:
        if not paragraph.text.strip():
            continue
            
        para_html = convert_paragraph_to_html(paragraph)
        if para_html:
            html_content.append(para_html)
    
    full_html = '\n'.join(html_content)
    cleaned_html = clean_redundant_tags(full_html)
    
    return cleaned_html


def convert_paragraph_to_html(paragraph):
    """Convert docx paragraph to HTML"""
    if not paragraph.text.strip():
        return ""
    
    # Check if this is a heading or title
    if paragraph.style.name.startswith('Heading'):
        level = paragraph.style.name.replace('Heading ', '')
        try:
            level = int(level)
            if level == 0:
                level = 1  # Level 0 should be H1
            return f"<h{level}>{paragraph.text.strip()}</h{level}>"
        except ValueError:
            pass
    elif paragraph.style.name == 'Title':
        return f"<h1>{paragraph.text.strip()}</h1>"
    
    # Check if this is a list item
    if paragraph.style.name.startswith('List'):
        return convert_list_item_to_html(paragraph)
    
    # Regular paragraph
    runs_html = []
    for run in paragraph.runs:
        run_text = run.text
        
        # Replace problematic Unicode characters
        run_text = run_text.replace('→', '->')
        run_text = run_text.replace('₹', 'Rs.')
        run_text = run_text.replace('–', '-')
        run_text = run_text.replace('—', '-')
        run_text = run_text.replace('"', '"')
        run_text = run_text.replace('"', '"')
        run_text = run_text.replace(''', "'")
        run_text = run_text.replace(''', "'")
        
        # HTML escape the text
        run_text = html.escape(run_text)
        
        # Apply formatting
        if run.bold:
            run_text = f"<strong>{run_text}</strong>"
        if run.italic:
            run_text = f"<em>{run_text}</em>"
        
        runs_html.append(run_text)
    
    # Join all runs and wrap in paragraph tag
    para_text = ''.join(runs_html)
    if para_text.strip():
        return f"<p>{para_text}</p>"
    
    return ""


def convert_list_item_to_html(paragraph):
    """Convert list item paragraph to HTML"""
    runs_html = []
    for run in paragraph.runs:
        run_text = run.text
        
        # Replace problematic Unicode characters
        run_text = run_text.replace('→', '->')
        run_text = run_text.replace('₹', 'Rs.')
        run_text = run_text.replace('–', '-')
        run_text = run_text.replace('—', '-')
        run_text = run_text.replace('"', '"')
        run_text = run_text.replace('"', '"')
        run_text = run_text.replace(''', "'")
        run_text = run_text.replace(''', "'")
        
        # HTML escape the text
        run_text = html.escape(run_text)
        
        # Apply formatting
        if run.bold:
            run_text = f"<strong>{run_text}</strong>"
        if run.italic:
            run_text = f"<em>{run_text}</em>"
        
        runs_html.append(run_text)
    
    item_text = ''.join(runs_html)
    if item_text.strip():
        return f"<li>{item_text}</li>"
    
    return ""


def clean_redundant_tags(html_content):
    """
    Clean up redundant HTML tags like </strong><strong> or </em><em>.
    Also convert <p><strong> patterns to proper heading tags.
    
    Args:
        html_content (str): Raw HTML content
        
    Returns:
        str: Cleaned HTML content
    """
    # Convert <p><strong> patterns to heading tags
    html_content = convert_strong_paragraphs_to_headings(html_content)
    
    # Remove consecutive closing and opening tags of the same type
    html_content = re.sub(r'</strong><strong>', '', html_content)
    html_content = re.sub(r'</em><em>', '', html_content)
    html_content = re.sub(r'</b><b>', '', html_content)
    html_content = re.sub(r'</i><i>', '', html_content)
    
    # Remove empty tags
    html_content = re.sub(r'<strong></strong>', '', html_content)
    html_content = re.sub(r'<em></em>', '', html_content)
    html_content = re.sub(r'<b></b>', '', html_content)
    html_content = re.sub(r'<i></i>', '', html_content)
    
    # Remove multiple consecutive spaces
    html_content = re.sub(r' +', ' ', html_content)
    
    # Remove spaces before closing tags
    html_content = re.sub(r' +</', '</', html_content)
    
    return html_content


def convert_strong_paragraphs_to_headings(html_content):
    """
    Convert <p><strong> patterns to appropriate heading tags.
    
    Args:
        html_content (str): HTML content with <p><strong> patterns
        
    Returns:
        str: HTML content with proper heading tags
    """
    lines = html_content.split('\n')
    processed_lines = []
    h1_found = False
    
    for line in lines:
        # Check if line matches <p><strong>pattern</strong></p>
        strong_match = re.match(r'<p><strong>(.*?)</strong></p>', line.strip())
        
        if strong_match:
            content = strong_match.group(1).strip()
            
            # Determine heading level based on content patterns
            heading_level = determine_heading_level(content)
            
            # Ensure only one H1 per file
            if heading_level == 1 and not h1_found:
                heading_tag = f"<h1>{content}</h1>"
                processed_lines.append(heading_tag)
                h1_found = True
            elif heading_level == 1:
                # Convert H1 to H2 if H1 already exists
                heading_tag = f"<h2>{content}</h2>"
                processed_lines.append(heading_tag)
            else:
                heading_tag = f"<h{heading_level}>{content}</h{heading_level}>"
                processed_lines.append(heading_tag)
        else:
            processed_lines.append(line)
    
    return '\n'.join(processed_lines)


def determine_heading_level(content):
    """
    Determine the appropriate heading level based on content analysis.
    
    Args:
        content (str): The text content to analyze
        
    Returns:
        int: Appropriate heading level (1-4)
    """
    content_lower = content.lower()
    
    # H1 patterns - Main career titles
    h1_patterns = [
        r'^[a-z\s]+$',  # Simple career names
        r'career description',
        r'overview',
        r'introduction'
    ]
    
    # H2 patterns - Major sections
    h2_patterns = [
        r'roles?\s+and\s+responsibilities',
        r'study\s+route',
        r'eligibility\s+criteria',
        r'courses?\s+and\s+specializations?',
        r'top\s+institutes?',
        r'entrance\s+tests?',
        r'career\s+path',
        r'leading\s+professions?',
        r'major\s+areas?\s+of\s+employment',
        r'prominent\s+employers?',
        r'pros\s+and\s+cons',
        r'skills?\s+required',
        r'industry\s+trends?',
        r'salary\s+expectations?'
    ]
    
    # H3 patterns - Sub-sections
    h3_patterns = [
        r'^[a-z\s]+:$',  # Simple labels ending with colon
        r'internships?',
        r'practical\s+exposure'
    ]
    
    # Check for H1 patterns
    for pattern in h1_patterns:
        if re.search(pattern, content_lower):
            return 1
    
    # Check for H2 patterns
    for pattern in h2_patterns:
        if re.search(pattern, content_lower):
            return 2
    
    # Check for H3 patterns
    for pattern in h3_patterns:
        if re.search(pattern, content_lower):
            return 3
    
    # Default to H4 for other strong content
    return 4


def extract_career_data_from_html(html_content):
    """
    Extract title (for name), summary (first paragraph), and description (full content) from HTML.
    
    Args:
        html_content (str): HTML content
        
    Returns:
        tuple: (title, summary, description)
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract title from first H1 tag
    title = ""
    h1_tag = soup.find('h1')
    if h1_tag:
        title = h1_tag.get_text().strip()
    
    # If no H1, try to get title from first strong paragraph
    if not title:
        first_strong_p = soup.find('p')
        if first_strong_p and first_strong_p.find('strong'):
            title = first_strong_p.find('strong').get_text().strip()
    
    # Extract summary from first paragraph (skip H1)
    summary = ""
    paragraphs = soup.find_all('p')
    for p in paragraphs:
        # Skip if this paragraph contains the title
        if title and title in p.get_text():
            continue
        summary = p.get_text().strip()
        if summary:
            break
    
    # Truncate summary to 250 characters
    if summary and len(summary) > 250:
        summary = summary[:247] + "..."
    
    # Use full HTML content as description
    description = html_content
    
    return title, summary, description
