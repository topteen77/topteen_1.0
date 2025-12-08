"""
Generic Infographic Parser
Parses HTML content and generates infographic data for different sections
"""
import re
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class InfographicParser:
    """Base class for parsing different types of infographics from HTML"""
    
    def __init__(self, html_content):
        self.html_content = html_content
        self.soup = BeautifulSoup(html_content, 'html.parser') if html_content else None
    
    def find_section(self, section_title_keywords):
        """
        Find a section by title keywords.
        
        Args:
            section_title_keywords: List of keywords to search for in headings
            
        Returns:
            BeautifulSoup element or None
        """
        if not self.soup:
            return None
        
        for heading in self.soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'strong']):
            text = heading.get_text(strip=True).lower()
            if any(keyword.lower() in text for keyword in section_title_keywords):
                return heading
        
        return None
    
    def get_section_content(self, section_heading, stop_keywords=None):
        """
        Get all content from a section heading until the next major section.
        
        Args:
            section_heading: BeautifulSoup element (the heading)
            stop_keywords: List of keywords that indicate the next section should stop
            
        Returns:
            BeautifulSoup object containing the section content
        """
        if not section_heading:
            return None
        
        section_content = []
        section_content.append(str(section_heading))
        
        current = section_heading
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
            
            section_content.append(str(current))
        
        return BeautifulSoup(''.join(section_content), 'html.parser')


class StudyRouteParser(InfographicParser):
    """Parser for Study Route & Eligibility Criteria infographics"""
    
    def parse(self):
        """Parse study routes from HTML"""
        section = self.find_section(['Study Route', 'Eligibility Criteria', 'eligibility'])
        if not section:
            return None
        
        section_soup = self.get_section_content(section, ['Significant', 'Observation', 'Pros', 'Cons'])
        if not section_soup:
            return None
        
        return self._parse_routes_from_section(section_soup)
    
    def _parse_routes_from_section(self, section_soup):
        """Parse routes from a section"""
        route_colors = [
            {'name': 'route-1', 'color': '#0064c8', 'display': 'Route 1'},
            {'name': 'route-2', 'color': '#228b22', 'display': 'Route 2'},
            {'name': 'route-3', 'color': '#8a2be2', 'display': 'Route 3'},
            {'name': 'route-4', 'color': '#ff8c00', 'display': 'Route 4'}
        ]
        
        routes = []
        tables = section_soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row_idx, row in enumerate(rows):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    route_cell = cells[0].get_text(strip=True)
                    steps_cell = cells[1].get_text(strip=True)
                    
                    if row_idx == 0 and route_cell.lower() == 'route' and steps_cell.lower() == 'steps':
                        continue
                    
                    if 'route' in route_cell.lower() and route_cell.lower() != 'route':
                        route_match = re.search(r'route\s*(\d+)[:\s]*(.*)', route_cell, re.IGNORECASE)
                        if route_match:
                            route_num = int(route_match.group(1))
                            route_name = route_match.group(2).strip() if route_match.group(2) else f'Route {route_num}'
                        else:
                            route_num = len(routes) + 1
                            route_name = route_cell
                        
                        steps = self._parse_steps(steps_cell)
                        if steps:
                            route_index = route_num - 1
                            if route_index < len(route_colors):
                                route_data = {
                                    'name': route_name,
                                    'class': route_colors[route_index]['name'],
                                    'color': route_colors[route_index]['color'],
                                    'display': route_colors[route_index]['display'],
                                    'steps': steps
                                }
                            else:
                                route_data = {
                                    'name': route_name,
                                    'class': 'route-default',
                                    'color': '#666666',
                                    'display': f'Route {route_num}',
                                    'steps': steps
                                }
                            routes.append(route_data)
        
        return routes if routes else None
    
    def _parse_steps(self, steps_cell):
        """Parse numbered steps from text"""
        steps = []
        step_parts = re.split(r'(\d+)[\.\)]\s+', steps_cell)
        
        if len(step_parts) > 1:
            for i in range(1, len(step_parts), 2):
                if i + 1 < len(step_parts):
                    step_num = int(step_parts[i])
                    step_text = step_parts[i + 1].strip()
                    step_text = re.sub(r'\s+(?=\d+[\.\)]\s)', '', step_text)
                    step_text = re.sub(r'\s+', ' ', step_text)
                    
                    duration = ''
                    duration_patterns = [
                        r'\((\d+[-–]\d+\s*(?:Years?|Months?|Yrs?|Months?))\)',
                        r'\((\d+\s*(?:Years?|Months?|Yrs?|Months?))\)',
                    ]
                    for dur_pattern in duration_patterns:
                        duration_match = re.search(dur_pattern, step_text, re.IGNORECASE)
                        if duration_match:
                            duration = duration_match.group(1)
                            break
                    
                    title = re.sub(r'\([^)]*\)', '', step_text).strip()
                    
                    if title:
                        steps.append({
                            'number': step_num,
                            'title': title,
                            'description': '',
                            'duration': duration
                        })
        
        return steps


class RolesResponsibilitiesParser(InfographicParser):
    """Parser for Roles and Responsibilities infographics"""
    
    def parse(self):
        """Parse roles and responsibilities"""
        section = self.find_section(['Roles and Responsibilities', 'Roles & Responsibilities'])
        if not section:
            return None
        
        section_soup = self.get_section_content(section, ['Study Route', 'Eligibility', 'Pros', 'Cons'])
        if not section_soup:
            return None
        
        return self._parse_roles(section_soup)
    
    def _parse_roles(self, section_soup):
        """Parse roles from HTML structure"""
        roles = []
        
        # Look for lists with bold items (role categories)
        lists = section_soup.find_all(['ul', 'ol'])
        
        for ul in lists:
            items = ul.find_all('li', recursive=False)
            for item in items:
                # Get the bold text (role name)
                bold = item.find(['strong', 'b'])
                if bold:
                    role_name = bold.get_text(strip=True)
                    # Get the sub-items (responsibilities)
                    sub_items = item.find_all('li', recursive=True)
                    responsibilities = []
                    
                    if sub_items:
                        for sub_item in sub_items:
                            text = sub_item.get_text(strip=True)
                            if text and text != role_name:
                                responsibilities.append(text)
                    else:
                        # If no sub-items, get text after bold
                        text = item.get_text(strip=True)
                        if text and text != role_name:
                            # Remove the role name from text
                            text = text.replace(role_name, '').strip()
                            if text:
                                responsibilities.append(text)
                    
                    if role_name:
                        roles.append({
                            'name': role_name,
                            'responsibilities': responsibilities
                        })
        
        return roles if roles else None


class ObservationsParser(InfographicParser):
    """Parser for Significant Observations infographics"""
    
    def parse(self):
        """Parse observations"""
        section = self.find_section(['Significant Observations', 'Observations', 'Academic Related Points'])
        if not section:
            return None
        
        section_soup = self.get_section_content(section, ['Internships', 'Courses', 'Top Institutes'])
        if not section_soup:
            return None
        
        return self._parse_observations(section_soup)
    
    def _parse_observations(self, section_soup):
        """Parse observations from list items"""
        observations = []
        
        lists = section_soup.find_all(['ul', 'ol'])
        for ul in lists:
            items = ul.find_all('li', recursive=False)
            for item in items:
                # Get bold text (observation title)
                bold = item.find(['strong', 'b'])
                if bold:
                    title = bold.get_text(strip=True)
                    # Get description (text after bold)
                    text = item.get_text(strip=True)
                    description = text.replace(title, '').strip()
                    # Remove colon if present
                    if description.startswith(':'):
                        description = description[1:].strip()
                    
                    if title:
                        observations.append({
                            'title': title,
                            'description': description
                        })
        
        return observations if observations else None


class CoursesParser(InfographicParser):
    """Parser for Courses & Specializations infographics"""
    
    def parse(self):
        """Parse courses"""
        section = self.find_section(['Courses & Specializations', 'Courses', 'Specializations'])
        if not section:
            return None
        
        section_soup = self.get_section_content(section, ['Top Institutes', 'Entrance', 'Ideal Progressing'])
        if not section_soup:
            return None
        
        return self._parse_courses(section_soup)
    
    def _parse_courses(self, section_soup):
        """Parse courses from list items"""
        courses = []
        
        lists = section_soup.find_all(['ul', 'ol'])
        for ul in lists:
            items = ul.find_all('li', recursive=False)
            for item in items:
                text = item.get_text(strip=True)
                if text:
                    courses.append({
                        'name': text,
                        'description': ''
                    })
        
        return courses if courses else None


class InstitutesParser(InfographicParser):
    """Parser for Top Institutes infographics"""
    
    def parse(self):
        """Parse institutes from tables"""
        section = self.find_section(['Top Institutes', 'Institutes', 'Education'])
        if not section:
            return None
        
        section_soup = self.get_section_content(section, ['International', 'Entrance', 'Ideal Progressing'])
        if not section_soup:
            return None
        
        return self._parse_institutes(section_soup)
    
    def _parse_institutes(self, section_soup):
        """Parse institutes from table structure"""
        institutes = []
        
        tables = section_soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            headers = []
            
            # Get headers from first row
            if rows:
                header_row = rows[0]
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            
            # Parse data rows
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if cells:
                    institute_data = {}
                    for idx, cell in enumerate(cells):
                        if idx < len(headers):
                            header = headers[idx]
                            text = cell.get_text(strip=True)
                            # Clean up list items
                            if '<li>' in str(cell):
                                items = cell.find_all('li')
                                text = ', '.join([li.get_text(strip=True) for li in items])
                            
                            # Normalize header names
                            header_key = header.lower().replace(' ', '_').replace('/', '_')
                            institute_data[header_key] = text
                    
                    if institute_data:
                        institutes.append(institute_data)
        
        return institutes if institutes else None


class InternshipsParser(InfographicParser):
    """Parser for Internships & Practical Exposure infographics"""
    
    def parse(self):
        """Parse internships"""
        section = self.find_section(['Internships', 'Practical Exposure', 'Internships & Practical Exposure'])
        if not section:
            return None
        
        section_soup = self.get_section_content(section, ['Courses', 'Top Institutes', 'Prominent'])
        if not section_soup:
            return None
        
        return self._parse_internships(section_soup)
    
    def _parse_internships(self, section_soup):
        """Parse internships from list items"""
        internships = []
        
        lists = section_soup.find_all(['ul', 'ol'])
        for ul in lists:
            items = ul.find_all('li', recursive=False)
            for item in items:
                text = item.get_text(strip=True)
                if text:
                    internships.append({
                        'description': text,
                        'type': 'internship' if 'internship' in text.lower() else 'training'
                    })
        
        return internships if internships else None


class ProminentEmployersParser(InfographicParser):
    """Parser for Prominent Employers infographics"""
    
    def parse(self):
        """Parse prominent employers"""
        section = self.find_section(['Prominent Employers', 'Leading Employers', 'Top Employers'])
        if not section:
            return None
        
        section_soup = self.get_section_content(section, ['Salary', 'Pros', 'Skills'])
        if not section_soup:
            return None
        
        return self._parse_employers(section_soup)
    
    def _parse_employers(self, section_soup):
        """Parse employers from table structure"""
        employers = []
        
        tables = section_soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            headers = []
            
            # Get headers from first row
            if rows:
                header_row = rows[0]
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            
            # Parse data rows
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if cells:
                    employer_data = {}
                    for idx, cell in enumerate(cells):
                        if idx < len(headers):
                            header = headers[idx]
                            text = cell.get_text(strip=True)
                            # Clean up list items
                            if '<li>' in str(cell):
                                items = cell.find_all('li')
                                text = ', '.join([li.get_text(strip=True) for li in items])
                            
                            # Normalize header names
                            header_key = header.lower().replace(' ', '_').replace('/', '_')
                            employer_data[header_key] = text
                    
                    if employer_data:
                        employers.append(employer_data)
        
        return employers if employers else None


class SalaryExpectationsParser(InfographicParser):
    """Parser for Salary Expectations infographics"""
    
    def parse(self):
        """Parse salary expectations"""
        section = self.find_section(['Salary Expectations', 'Salary', 'Compensation'])
        if not section:
            return None
        
        section_soup = self.get_section_content(section, ['Skills', 'Industry Trends', 'Advice'])
        if not section_soup:
            return None
        
        return self._parse_salary(section_soup)
    
    def _parse_salary(self, section_soup):
        """Parse salary data from table structure"""
        salary_data = []
        
        tables = section_soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            headers = []
            
            # Get headers from first row
            if rows:
                header_row = rows[0]
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            
            # Parse data rows
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if cells:
                    row_data = {}
                    for idx, cell in enumerate(cells):
                        if idx < len(headers):
                            header = headers[idx]
                            text = cell.get_text(strip=True)
                            
                            # Skip note rows
                            if 'note' in text.lower() or 'varies' in text.lower():
                                continue
                            
                            # Normalize header names
                            header_key = header.lower().replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '').replace('₹', 'rupees').replace('$', 'usd')
                            row_data[header_key] = text
                    
                    if row_data and len(row_data) > 1:  # Must have at least 2 columns
                        salary_data.append(row_data)
        
        return salary_data if salary_data else None


class SkillsIndustryTrendsParser(InfographicParser):
    """Parser for Skills Required & Industry Trends infographics"""
    
    def parse(self):
        """Parse skills and industry trends"""
        section = self.find_section(['Skills Required', 'Industry Trends', 'Future Outlook'])
        if not section:
            return None
        
        section_soup = self.get_section_content(section, ['Advice', 'Salary', 'Pros'])
        if not section_soup:
            return None
        
        return self._parse_skills_trends(section_soup)
    
    def _parse_skills_trends(self, section_soup):
        """Parse skills and trends from lists"""
        data = {
            'skills': [],
            'trends': []
        }
        
        # Find all headings and lists
        headings = section_soup.find_all(['h3', 'h4', 'strong'])
        current_section = None
        
        for element in section_soup.find_all(['h3', 'h4', 'ul', 'ol', 'p']):
            if element.name in ['h3', 'h4']:
                text = element.get_text(strip=True).lower()
                if 'skill' in text:
                    current_section = 'skills'
                elif 'trend' in text or 'outlook' in text or 'future' in text:
                    current_section = 'trends'
            elif element.name in ['ul', 'ol'] and current_section:
                items = element.find_all('li', recursive=False)
                for item in items:
                    text = item.get_text(strip=True)
                    if text:
                        data[current_section].append(text)
        
        # If no section headers found, try to parse all lists
        if not data['skills'] and not data['trends']:
            lists = section_soup.find_all(['ul', 'ol'])
            for ul in lists:
                items = ul.find_all('li', recursive=False)
                for item in items:
                    text = item.get_text(strip=True)
                    if text:
                        # Try to categorize based on content
                        if any(keyword in text.lower() for keyword in ['skill', 'expertise', 'knowledge', 'ability', 'proficiency']):
                            data['skills'].append(text)
                        else:
                            data['trends'].append(text)
        
        return data if (data['skills'] or data['trends']) else None


class AdviceForAspiringParser(InfographicParser):
    """Parser for Advice for Aspiring infographics"""
    
    def parse(self):
        """Parse advice for aspiring professionals"""
        section = self.find_section(['Advice for Aspiring', 'Advice', 'Tips for Aspiring'])
        if not section:
            return None
        
        section_soup = self.get_section_content(section, [])
        if not section_soup:
            return None
        
        return self._parse_advice(section_soup)
    
    def _parse_advice(self, section_soup):
        """Parse advice from list items and paragraphs"""
        advice_items = []
        
        # Parse from lists
        lists = section_soup.find_all(['ul', 'ol'])
        for ul in lists:
            items = ul.find_all('li', recursive=False)
            for item in items:
                text = item.get_text(strip=True)
                if text and len(text) > 20:  # Filter out very short items
                    advice_items.append({
                        'text': text,
                        'type': 'tip'
                    })
        
        # Parse from paragraphs (for concluding paragraphs)
        paragraphs = section_soup.find_all('p')
        for para in paragraphs:
            text = para.get_text(strip=True)
            if text and len(text) > 50:  # Only longer paragraphs
                # Skip if it's already in a list
                if not any(text[:50] in item['text'][:50] for item in advice_items):
                    advice_items.append({
                        'text': text,
                        'type': 'conclusion'
                    })
        
        return advice_items if advice_items else None


# Registry of parsers
INFographic_PARSERS = {
    'study_route': StudyRouteParser,
    'roles_responsibilities': RolesResponsibilitiesParser,
    'observations': ObservationsParser,
    'courses': CoursesParser,
    'institutes': InstitutesParser,
    'internships': InternshipsParser,
    'prominent_employers': ProminentEmployersParser,
    'salary_expectations': SalaryExpectationsParser,
    'skills_industry_trends': SkillsIndustryTrendsParser,
    'advice_for_aspiring': AdviceForAspiringParser,
}


def parse_infographic(html_content, infographic_type):
    """
    Parse infographic data from HTML content.
    
    Args:
        html_content: HTML string to parse
        infographic_type: Type of infographic ('study_route', 'roles_responsibilities', etc.)
        
    Returns:
        Parsed data structure or None
    """
    parser_class = INFographic_PARSERS.get(infographic_type)
    if not parser_class:
        logger.warning(f'Unknown infographic type: {infographic_type}')
        return None
    
    try:
        parser = parser_class(html_content)
        return parser.parse()
    except Exception as e:
        logger.error(f'Error parsing {infographic_type} infographic: {str(e)}')
        return None

