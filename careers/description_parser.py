"""
Description Parser for Career Model
Handles conversion of <p><strong> to H2 tags and parsing sections
"""
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


def convert_p_strong_to_h2(html_content):
    """
    Convert <p><strong>...</strong></p> patterns to <h2>...</h2> tags.
    
    Converts ALL <p><strong> patterns that look like headings (where paragraph
    contains only a strong tag) to H2 tags. This completes stage1 task.
    
    Args:
        html_content (str): HTML content with <p><strong> patterns
        
    Returns:
        str: HTML content with H2 tags for all heading-like patterns
    """
    if not html_content:
        return html_content
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all <p> tags
        paragraphs = soup.find_all('p')
        
        for p in paragraphs:
            # Check if paragraph contains a <strong> tag
            strong_tag = p.find('strong')
            if strong_tag:
                # Get all text content of the paragraph (stripped)
                p_text = p.get_text(strip=True)
                # Get text content of the strong tag (stripped)
                strong_text = strong_tag.get_text(strip=True)
                
                # If paragraph text equals strong text (meaning it's just the strong tag, possibly with whitespace)
                # This indicates it's a heading, not regular text with emphasis
                if p_text == strong_text and strong_text:
                    # Additional check: skip if it's too short (likely not a heading) or too long (likely content)
                    # Headings are typically between 3 and 200 characters
                    if len(strong_text) < 3 or len(strong_text) > 200:
                        continue
                    
                    # Skip if it looks like a list item or bullet point
                    if strong_text.strip().startswith(('a)', 'b)', 'c)', 'i)', 'ii)', '1.', '2.', '3.', '-', '•', '*')):
                        continue
                    
                        # Create new h2 tag
                        h2_tag = soup.new_tag('h2')
                        
                        # Copy all contents from strong tag to h2 (preserves any nested HTML)
                        for child in strong_tag.children:
                            if hasattr(child, 'extract'):
                                h2_tag.append(child.extract())
                            else:
                                h2_tag.append(str(child))
                        
                        # If no children were copied, use the text content
                        if not h2_tag.contents:
                            h2_tag.string = strong_text
                        
                        # Direct conversion: replace <p><strong> with <h2>
                        p.replace_with(h2_tag)
                                                                                            
        return str(soup)
    
    except Exception as e:
        logger.error(f'Error converting p-strong to H2: {str(e)}', exc_info=True)
        return html_content


class DescriptionSectionParser:
    """
    Parse career description HTML into structured sections based on H2 headings.
    """
    
    def __init__(self, html_content):
        self.html_content = html_content
        self.soup = None
        self.sections = {}
        
        if html_content:
            try:
                self.soup = BeautifulSoup(html_content, 'html.parser')
            except Exception as e:
                logger.error(f'Error parsing HTML: {str(e)}', exc_info=True)
    
    def parse_sections(self):
        """
        Parse HTML content by H2 headings and extract sections.
        
        Returns:
            dict: Dictionary with section names as keys and HTML content as values
                Format: {section_name: html_content, ...}
        """
        if not self.soup:
            return {}
        
        try:
            # Find all H2 tags
            h2_tags = self.soup.find_all('h2')
            
            if not h2_tags:
                # No H2 tags found, return empty dict or single section
                return {}
            
            # Process each H2 and its content
            for i, h2 in enumerate(h2_tags):
                section_name = h2.get_text(strip=True)
                
                # Collect all content between this H2 and the next H2
                content_elements = []
                current = h2.next_sibling
                
                while current:
                    # Stop if we hit another H2
                    if current.name == 'h2':
                        break
                    
                    # Collect the element
                    if current.name:  # Only collect actual HTML elements, not text nodes
                        content_elements.append(str(current))
                    elif isinstance(current, str) and current.strip():
                        # Include significant text nodes
                        content_elements.append(current)
                    
                    current = current.next_sibling
                
                # Combine content
                section_html = ''.join(content_elements) if content_elements else ''
                
                # Include the H2 tag itself in the section
                section_html = str(h2) + section_html
                
                self.sections[section_name] = section_html
            
            return self.sections
        
        except Exception as e:
            logger.error(f'Error parsing sections: {str(e)}', exc_info=True)
            return {}
    
    def get_sections_json(self):
        """
        Get sections as JSON-serializable dictionary.
        
        Returns:
            dict: Sections dictionary
        """
        if not self.sections:
            self.parse_sections()
        
        return self.sections

