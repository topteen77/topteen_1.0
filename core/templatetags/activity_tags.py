from bs4 import BeautifulSoup
import re

def inject_activity_ids(html_content):
    """
    Parses HTML content and injects IDs into section headers for anchor linking.
    Returns the modified HTML.
    """
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all <ul> tags and check if the FIRST <li> contains a <strong> (section header)
    for ul in soup.find_all('ul'):
        lis = ul.find_all('li', recursive=False)
        if lis:  # Check if there are any list items
            first_li = lis[0]
            strong = first_li.find('strong')
            if strong:
                header_text = strong.get_text().strip()
                # Check if this looks like a section header (starts with number or is a known pattern)
                if re.match(r'^\d+\.', header_text) or any(keyword in header_text.lower() for keyword in ['overview', 'participation', 'skill', 'activities', 'achievement', 'time', 'impact', 'tips', 'resources', 'additional']):
                    section_id = generate_id_from_header(header_text)
                    if section_id:
                        ul['id'] = section_id
                        ul['class'] = ul.get('class', []) + ['scroll-section-header']
    
    return str(soup)


def get_all_sections(html_content):
    """
    Returns all 10 standard sections with their availability status.
    Each section has: id, title, icon, description, and exists (boolean).
    """
    # Define all 10 standard sections
    standard_sections = [
        {
            'id': 'objectives',
            'title': 'Objectives & Goals',
            'icon': 'bx-target-lock',
            'description': 'Academic excellence, critical thinking, competitive edge'
        },
        {
            'id': 'participation',
            'title': 'Participation Details',
            'icon': 'bx-log-in-circle',
            'description': 'Eligibility, registration and preparation steps'
        },
        {
            'id': 'keyskills',
            'title': 'Key Skills / Benefits',
            'icon': 'bx-brain',
            'description': 'Problem solving, time management, teamwork'
        },
        {
            'id': 'activities',
            'title': 'Activities & Involvement',
            'icon': 'bx-run',
            'description': 'Practice, workshops, bootcamps and forums'
        },
        {
            'id': 'achievements',
            'title': 'Achievements & Recognition',
            'icon': 'bx-trophy',
            'description': 'Awards, scholarships and national ranking'
        },
        {
            'id': 'time',
            'title': 'Time Commitment & Scheduling',
            'icon': 'bx-time',
            'description': 'Weekly practice and intensive prep timelines'
        },
        {
            'id': 'impact',
            'title': 'Impact on Development',
            'icon': 'bx-heart',
            'description': 'Confidence, networking and growth mindset'
        },
        {
            'id': 'tips',
            'title': 'Tips for Success',
            'icon': 'bx-check-shield',
            'description': 'Start early, practice consistently, join groups'
        },
        {
            'id': 'resources',
            'title': 'Resources & Contact',
            'icon': 'bx-link',
            'description': 'Official sites, platforms and local support'
        },
        {
            'id': 'additional',
            'title': 'Additional Resources',
            'icon': 'bx-book-open',
            'description': 'Further reading, platforms and contact emails'
        }
    ]
    
    # Find which sections actually exist in the content
    existing_ids = set()
    if html_content:
        soup = BeautifulSoup(html_content, 'html.parser')
        for ul in soup.find_all('ul'):
            lis = ul.find_all('li', recursive=False)
            if lis:  # Check if there are any list items
                first_li = lis[0]
                strong = first_li.find('strong')
                if strong:
                    header_text = strong.get_text().strip()
                    # Check if this looks like a section header
                    if re.match(r'^\d+\.', header_text) or any(keyword in header_text.lower() for keyword in ['overview', 'participation', 'skill', 'activities', 'achievement', 'time', 'impact', 'tips', 'resources', 'additional']):
                        section_id = generate_id_from_header(header_text)
                        if section_id:
                            existing_ids.add(section_id)
    
    # Mark which sections exist
    for section in standard_sections:
        section['exists'] = section['id'] in existing_ids
    
    return standard_sections

def generate_id_from_header(header_text):
    """
    Generates a URL-friendly ID from header text, matching standard section IDs.
    """
    # Remove numbering (e.g., "1. ", "2. ")
    text = re.sub(r'^\d+\.\s*', '', header_text)
    
    # Map common variations to standard IDs
    text_lower = text.lower()
    
    # Check for standard section patterns (order matters - check 'additional' before 'resources')
    if 'overview' in text_lower or 'description' in text_lower:
        return 'objectives'
    elif 'participation' in text_lower:
        return 'participation'
    elif 'key skill' in text_lower or 'benefit' in text_lower:
        return 'keyskills'
    elif 'activities' in text_lower or 'involvement' in text_lower:
        return 'activities'
    elif 'achievement' in text_lower or 'recognition' in text_lower:
        return 'achievements'
    elif 'time' in text_lower or 'commitment' in text_lower or 'scheduling' in text_lower:
        return 'time'
    elif 'impact' in text_lower or 'development' in text_lower:
        return 'impact'
    elif 'tips' in text_lower or 'success' in text_lower:
        return 'tips'
    elif 'additional' in text_lower:  # Check 'additional' BEFORE 'resources'
        return 'additional'
    elif 'resources' in text_lower or 'contact' in text_lower:
        return 'resources'
    
    # Fallback: convert to URL-friendly format
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    text = text.strip('-').lower()
    
    return text if text else None
