"""
Runtime Career Description JSON Parser
Parses career.description into 11 structured JSON sections at runtime
"""
import json
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class CareerDescriptionJSONParser:
    """Parse career description into 11 structured JSON sections at runtime"""
    
    # Section mapping: section_key -> [possible heading keywords]
    SECTION_MAPPING = {
        'overview': ['overview', 'introduction', 'summary'],
        'career_description': ['career description', 'description'],
        'roles_and_responsibilities': [
            'roles and responsibilities', 'roles & responsibilities', 
            'responsibilities', 'role description'
        ],
        'study_route_and_eligibility_criteria': [
            'study route', 'eligibility criteria', 
            'study route & eligibility criteria', 'eligibility', 'route'
        ],
        'significant_observations': [
            'significant observations', 'academic related points', 
            'observations'
        ],
        'internships_and_practical_exposure': [
            'internships', 'practical exposure', 
            'internships & practical exposure', 'practical training'
        ],
        'courses_and_specializations': [
            'courses', 'specializations', 
            'courses & specializations',
            'courses and specializations to enter the field'
        ],
        'prominent_employers': [
            'prominent employers', 'leading employers', 
            'top employers', 'major employers'
        ],
        'salary_expectations': [
            'salary expectations', 'salary', 'compensation'
        ],
        'skills_required_industry_trends': [
            'skills required', 'industry trends', 'future outlook',
            'skills required industry trends and future outlook'
        ],
        'advice_for_aspiring': [
            'advice for aspiring', 'advice', 'tips for aspiring',
            'guidance for aspiring'
        ]
    }
    
    def __init__(self, career):
        self.career = career
        self.description = career.description or ''
        self.combined_content = self.description
        self.soup = BeautifulSoup(self.combined_content, 'html.parser')
        self.sections = {}
    
    def find_section_heading(self, keywords):
        """Find a section heading by keywords"""
        if not self.soup:
            return None
        
        # Search in headings (h1-h6) and paragraphs with strong tags
        for heading in self.soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']):
            text = heading.get_text(strip=True).lower()
            if any(keyword.lower() in text for keyword in keywords):
                # If it's a p tag, check if it contains strong
                if heading.name == 'p':
                    strong = heading.find('strong')
                    if strong:
                        strong_text = strong.get_text(strip=True).lower()
                        if any(keyword.lower() in strong_text for keyword in keywords):
                            return heading
                else:
                    return heading
        
        return None
    
    def get_section_content(self, heading, stop_keywords=None):
        """
        Extract content from a heading until the next major section
        
        Returns:
            dict with 'html' and 'text' content
        """
        if not heading:
            return {'html': '', 'text': ''}
        
        content_html = []
        content_html.append(str(heading))
        
        current = heading
        while current:
            current = current.find_next_sibling()
            if not current:
                break
            
            # Stop at next major heading
            if current.name in ['h1', 'h2', 'h3', 'h4']:
                text = (current.get_text() or '').strip().lower()
                if stop_keywords and any(keyword in text for keyword in stop_keywords):
                    break
                # If it's another major section, stop
                if len(text) > 0:
                    break
            
            # Also stop at certain patterns
            if current.name == 'p':
                strong = current.find('strong')
                if strong:
                    strong_text = strong.get_text(strip=True).lower()
                    # Check if this is a new section heading
                    for section_key, section_keywords in self.SECTION_MAPPING.items():
                        if any(kw in strong_text for kw in section_keywords):
                            # Check if this is a different section
                            heading_text = heading.get_text(strip=True).lower()
                            if not any(kw in heading_text for kw in section_keywords):
                                break
            
            content_html.append(str(current))
        
        html_content = ''.join(content_html)
        soup_content = BeautifulSoup(html_content, 'html.parser')
        text_content = soup_content.get_text(separator='\n', strip=True)
        
        return {
            'html': html_content,
            'text': text_content
        }
    
    def parse_all_sections(self):
        """Parse all sections from the career description"""
        # Parse each section
        for section_key, keywords in self.SECTION_MAPPING.items():
            heading = self.find_section_heading(keywords)
            if heading:
                # Determine stop keywords (next sections)
                stop_keywords = []
                for other_key, other_keywords in self.SECTION_MAPPING.items():
                    if other_key != section_key:
                        stop_keywords.extend(other_keywords)
                
                content = self.get_section_content(heading, stop_keywords)
                self.sections[section_key] = {
                    'title': heading.get_text(strip=True),
                    'html': content['html'],
                    'text': content['text']
                }
            else:
                # Section not found
                self.sections[section_key] = {
                    'title': None,
                    'html': '',
                    'text': ''
                }
        
        # Special handling for overview: Extract only content before "Roles and Responsibilities"
        self._parse_overview_short()
        
        return self.sections
    
    def _parse_overview_short(self):
        """Extract complete overview - all content before Roles and Responsibilities"""
        # Find Roles and Responsibilities heading
        roles_keywords = self.SECTION_MAPPING['roles_and_responsibilities']
        roles_heading = self.find_section_heading(roles_keywords)
        
        if roles_heading:
            # Get all content before Roles and Responsibilities
            overview_content = []
            # Start from the beginning of the document
            current = self.soup.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div'])
            
            # Traverse until we reach Roles heading
            while current and current != roles_heading:
                # Stop if we hit Roles heading
                if current == roles_heading:
                    break
                
                # Check if current element contains Roles heading
                if roles_heading in current.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']):
                    break
                
                # Collect paragraphs and text content
                if current.name == 'p':
                    p_text = current.get_text(strip=True)
                    # Skip if it's a section heading in strong tag
                    strong = current.find('strong')
                    if strong:
                        strong_text = strong.get_text(strip=True).lower()
                        # If it's roles heading, stop
                        if any(kw in strong_text for kw in roles_keywords):
                            break
                        # If it's another major section heading, stop
                        is_other_section = False
                        for section_key, section_keywords in self.SECTION_MAPPING.items():
                            if section_key not in ['overview', 'career_description']:
                                if any(kw in strong_text for kw in section_keywords):
                                    is_other_section = True
                                    break
                        if is_other_section:
                            break
                    
                    # Add paragraph if it has meaningful content
                    if p_text and len(p_text) > 20:
                        overview_content.append(str(current))
                
                # Move to next sibling
                current = current.find_next_sibling()
            
            # Use all collected paragraphs (no truncation)
            if overview_content:
                overview_html_complete = ''.join(overview_content)
                overview_text_complete = BeautifulSoup(overview_html_complete, 'html.parser').get_text(strip=True)
                
                # Update overview section with complete content
                if 'overview' in self.sections:
                    self.sections['overview'] = {
                        'title': 'Overview',
                        'html': overview_html_complete,
                        'text': overview_text_complete
                    }
                elif 'career_description' in self.sections:
                    # If overview not found, update career_description
                    self.sections['career_description'] = {
                        'title': 'Career Description',
                        'html': overview_html_complete,
                        'text': overview_text_complete
                    }
        else:
            # If Roles heading not found, use existing overview/career_description as-is
            overview_section = self.sections.get('overview') or self.sections.get('career_description')
            if overview_section and overview_section.get('html'):
                # Keep the existing content without modification
                pass
    
    def get_json(self, pretty=True):
        """Get the parsed sections as JSON"""
        json_data = {
            'career_id': self.career.id,
            'career_name': self.career.name,
            'career_slug': self.career.slug,
            'sections': self.sections,
            'metadata': {
                'total_sections': len([s for s in self.sections.values() if s['html']]),
                'sections_found': [k for k, v in self.sections.items() if v['html']]
            }
        }
        
        if pretty:
            return json.dumps(json_data, indent=2, ensure_ascii=False)
        return json.dumps(json_data, ensure_ascii=False)
    
    def get_section_html(self, section_key):
        """Get HTML content for a specific section"""
        return self.sections.get(section_key, {}).get('html', '')
    
    def get_section_text(self, section_key):
        """Get text content for a specific section"""
        return self.sections.get(section_key, {}).get('text', '')
    
    def print_debug_json(self):
        """Print JSON to terminal for debugging"""
        print("=" * 80)
        print(f"CAREER JSON PARSER DEBUG OUTPUT")
        print("=" * 80)
        print(f"Career: {self.career.name} (ID: {self.career.id})")
        print(f"Slug: {self.career.slug}")
        print("-" * 80)
        print(self.get_json(pretty=True))
        print("=" * 80)
        
        # Also print section summary
        print("\nSECTION SUMMARY:")
        print("-" * 80)
        for section_key, section_data in self.sections.items():
            has_content = bool(section_data.get('html'))
            title = section_data.get('title', 'N/A')
            content_length = len(section_data.get('html', ''))
            status = "✓" if has_content else "✗"
            print(f"{status} {section_key:40s} | Title: {title[:40]:40s} | Size: {content_length:6d} chars")
        print("-" * 80)

