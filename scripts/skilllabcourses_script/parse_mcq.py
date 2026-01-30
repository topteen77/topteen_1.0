#!/usr/bin/env python3
"""
Parse MCQ from HTML or DOCX and extract structured data:
- MCQ title
- Questions with options
- Correct answers
"""

import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from pathlib import Path


class MCQParser:
    """Parse MCQs from HTML or text content"""
    
    def __init__(self):
        self.questions = []
    
    def parse_from_html(self, html_content: str) -> Dict:
        """
        Parse MCQ from HTML content.
        Returns dict with title, questions list.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        body = soup.find('body') or soup
        
        # Extract title (usually first paragraph or h1/h2)
        title = self._extract_title(body)
        
        # Extract all questions
        questions = self._extract_questions(body)
        
        return {
            'title': title,
            'questions': questions,
            'total_questions': len(questions)
        }
    
    def _extract_title(self, body) -> str:
        """Extract MCQ title from body"""
        # Look for h1, h2, or first strong paragraph
        title_elem = body.find(['h1', 'h2'])
        if title_elem:
            return title_elem.get_text(strip=True)
        
        # Check first paragraph for title
        first_p = body.find('p')
        if first_p:
            text = first_p.get_text(strip=True)
            # If it's short and looks like a title
            if len(text) < 100 and ('MCQ' in text.upper() or 'Quiz' in text or 'Questions' in text):
                return text
        
        return "MCQ Questions"
    
    def _extract_questions(self, body) -> List[Dict]:
        """Extract all questions from body"""
        questions = []
        
        # Get all paragraphs
        paragraphs = body.find_all('p')
        
        current_question = None
        current_options = []
        current_correct_answer = None
        
        for para in paragraphs:
            text = para.get_text(strip=True)
            if not text:
                continue
            
            # Check if this is a question
            question_match = re.match(r'^(?:Question\s+)?(\d+)[:\.]\s*(.+?)$', text, re.IGNORECASE | re.DOTALL)
            if question_match:
                # Save previous question if exists
                if current_question:
                    questions.append({
                        'question_number': current_question['number'],
                        'question_text': current_question['text'],
                        'options': current_options,
                        'correct_answer': current_correct_answer
                    })
                
                # Start new question
                q_num = question_match.group(1)
                q_text = question_match.group(2).strip()
                
                # Remove "Question X:" prefix if still present
                q_text = re.sub(r'^Question\s+\d+[:\.]\s*', '', q_text, flags=re.IGNORECASE).strip()
                
                # Check if options are on the same line
                # Pattern: Question text followed by A) option B) option etc.
                # First, find where options start (look for A) or A. pattern)
                first_option_match = re.search(r'\b([A-D])[\.\)]\s+', q_text, re.IGNORECASE)
                if first_option_match:
                    # Split question text and options
                    q_text_only = q_text[:first_option_match.start()].strip()
                    options_text = q_text[first_option_match.start():]
                    
                    # Extract all options from the options text
                    # Handle both A) and A. formats, and handle newlines
                    options_in_line = re.findall(r'([A-D])[\.\)]\s*([^\nA-D]+?)(?=\s+[A-D][\.\)]|\n|$)', options_text, re.IGNORECASE | re.DOTALL)
                    
                    # Also try to match options that might be on separate lines
                    if not options_in_line:
                        # Try matching with newlines
                        options_in_line = re.findall(r'([A-D])[\.\)]\s*([^\n]+)', options_text, re.IGNORECASE)
                else:
                    q_text_only = q_text
                    options_in_line = []
                
                current_question = {
                    'number': int(q_num),
                    'text': q_text_only
                }
                current_options = []
                
                # Add options found on the same line
                if options_in_line:
                    for opt_letter, opt_text in options_in_line:
                        current_options.append({
                            'letter': opt_letter.upper(),
                            'text': opt_text.strip()
                        })
                
                current_correct_answer = None
                continue
            
            # Check if this contains options (A, B, C, D)
            # Handle both formats: A) option or A. option
            options_match = re.findall(r'([A-D])[\.\)]\s*([^A-D\)\.]+?)(?=\s+[A-D][\.\)]|$)', text, re.IGNORECASE)
            if options_match:
                for option_letter, option_text in options_match:
                    # Check if we already have this option
                    if not any(opt['letter'] == option_letter.upper() for opt in current_options):
                        current_options.append({
                            'letter': option_letter.upper(),
                            'text': option_text.strip()
                        })
                continue
            
            # Check if this is the correct answer
            correct_match = re.search(r'Correct\s+Answer[:\.]\s*([A-D])\)\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
            if correct_match:
                answer_letter = correct_match.group(1).upper()
                answer_text = correct_match.group(2).strip()
                current_correct_answer = {
                    'letter': answer_letter,
                    'text': answer_text
                }
                continue
            
            # If we have a current question and this paragraph doesn't match patterns,
            # it might be part of the question text or options
            if current_question and not current_options:
                # Might be continuation of question text
                if len(text) > 20:
                    current_question['text'] += ' ' + text
            elif current_question and current_options:
                # Check if this paragraph contains options in a different format
                # Look for patterns like "A. option text" or "A) option text"
                alt_options = re.findall(r'([A-D])[\.\)]\s*([^\n]+)', text)
                if alt_options:
                    for opt_letter, opt_text in alt_options:
                        # Check if we already have this option
                        if not any(opt['letter'] == opt_letter.upper() for opt in current_options):
                            current_options.append({
                                'letter': opt_letter.upper(),
                                'text': opt_text.strip()
                            })
        
        # Save last question
        if current_question:
            questions.append({
                'question_number': current_question['number'],
                'question_text': current_question['text'],
                'options': current_options,
                'correct_answer': current_correct_answer
            })
        
        return questions
    
    def parse_from_text(self, text_content: str) -> Dict:
        """Parse MCQ from plain text content"""
        # Convert text to simple HTML for parsing
        html_content = f"<body><p>{text_content}</p></body>"
        return self.parse_from_html(html_content)


def parse_mcq_file(file_path: Path) -> Optional[Dict]:
    """
    Parse MCQ from file (HTML or DOCX converted to text).
    Returns structured MCQ data.
    """
    if not file_path.exists():
        return None
    
    parser = MCQParser()
    
    if file_path.suffix == '.html':
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return parser.parse_from_html(content)
    else:
        # For other formats, read as text
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return parser.parse_from_text(content)


if __name__ == "__main__":
    # Test parsing
    import sys
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
        result = parse_mcq_file(file_path)
        if result:
            import json
            print(json.dumps(result, indent=2))
        else:
            print("Failed to parse MCQ file")
    else:
        print("Usage: python parse_mcq.py <mcq_file.html>")
