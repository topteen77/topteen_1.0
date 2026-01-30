#!/usr/bin/env python3
"""
PDF Templates for professional MCQ and Worksheet PDFs
"""

def verify_mcq_pdf_completeness(mcq_data: dict, html_content: str) -> dict:
    """
    Verify that all MCQ questions, options, and answers are present in PDF HTML.
    Returns verification results.
    """
    questions = mcq_data.get('questions', [])
    
    # Count from JSON
    total_questions = len(questions)
    total_options = sum(len(q.get('options', [])) for q in questions)
    total_answers = sum(1 for q in questions if q.get('correct_answer'))
    
    # Count from HTML - need to count actual question divs, option divs, and answer divs
    html_questions = html_content.count('<div class="question">')
    html_options = html_content.count('<div class="option">')
    html_answers = html_content.count('<div class="correct-answer">')
    
    # Verify each question individually
    missing_items = []
    for q in questions:
        q_num = q.get('question_number', 0)
        q_text = q.get('question_text', '')
        options = q.get('options', [])
        correct_answer = q.get('correct_answer')
        
        # Check if question text appears in HTML
        if q_text and q_text not in html_content:
            missing_items.append(f"Question {q_num} text missing")
        
        # Check if all options appear
        for opt in options:
            opt_text = opt.get('text', '')
            if opt_text and opt_text not in html_content:
                missing_items.append(f"Question {q_num} option {opt.get('letter')} missing")
        
        # Check if correct answer appears
        if correct_answer:
            answer_text = correct_answer.get('text', '')
            if answer_text and answer_text not in html_content:
                missing_items.append(f"Question {q_num} correct answer missing")
    
    return {
        'total_questions': total_questions,
        'html_questions': html_questions,
        'total_options': total_options,
        'html_options': html_options,
        'total_answers': total_answers,
        'html_answers': html_answers,
        'questions_match': html_questions == total_questions,
        'options_match': html_options == total_options,
        'answers_match': html_answers == total_answers,
        'all_match': (html_questions == total_questions and 
                     html_options == total_options and 
                     html_answers == total_answers),
        'missing_items': missing_items
    }


def get_mcq_pdf_from_json(mcq_data: dict, chapter_name: str, course_name: str) -> str:
    """
    Generate professional MCQ PDF template from JSON data.
    Ensures all questions, options, and answers are included.
    """
    import html
    
    questions_html = []
    questions = mcq_data.get('questions', [])
    
    for q in questions:
        q_num = q.get('question_number', 0)
        q_text = html.escape(q.get('question_text', ''))
        options = q.get('options', [])
        correct_answer = q.get('correct_answer', {})
        
        # Build question HTML
        question_html = ['<div class="question">']
        question_html.append(f'<div class="question-number">Question {q_num}</div>')
        question_html.append(f'<div class="question-text">{q_text}</div>')
        
        # Add options - ensure ALL options are included
        if options:
            question_html.append('<div class="options">')
            for opt in options:
                opt_letter = opt.get('letter', '')
                opt_text = html.escape(opt.get('text', ''))
                question_html.append(f'<div class="option"><span class="option-letter">{opt_letter})</span>{opt_text}</div>')
            question_html.append('</div>')
        else:
            # Warn if no options found
            question_html.append('<div class="options"><p style="color: #e74c3c;">Warning: No options found for this question</p></div>')
        
        # Add correct answer - ensure it's included
        if correct_answer:
            answer_letter = correct_answer.get('letter', '')
            answer_text = html.escape(correct_answer.get('text', ''))
            question_html.append('<div class="correct-answer">')
            question_html.append(f'<div class="correct-answer-label">Correct Answer: {answer_letter})</div>')
            question_html.append(f'<div class="correct-answer-text">{answer_text}</div>')
            question_html.append('</div>')
        else:
            # Note if no correct answer
            question_html.append('<div class="correct-answer" style="background: #fff3cd; border-color: #ffc107;"><p style="color: #856404;">Note: No correct answer specified for this question</p></div>')
        
        question_html.append('</div>')
        questions_html.append('\n'.join(question_html))
    
    questions_content = '\n'.join(questions_html)
    mcq_title = html.escape(mcq_data.get('title', 'Multiple Choice Questions'))
    
    template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>MCQ - {chapter_name}</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm 1.5cm;
        }}
        
        body {{
            font-family: 'Arial', 'Helvetica', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            background: #fff;
        }}
        
        .header {{
            border-bottom: 3px solid #2c3e50;
            padding-bottom: 15px;
            margin-bottom: 30px;
        }}
        
        .course-name {{
            font-size: 14pt;
            color: #34495e;
            font-weight: normal;
            margin: 0;
            margin-bottom: 5px;
        }}
        
        .chapter-name {{
            font-size: 18pt;
            color: #2c3e50;
            font-weight: bold;
            margin: 0;
            margin-bottom: 10px;
        }}
        
        .mcq-title {{
            font-size: 16pt;
            color: #e74c3c;
            font-weight: bold;
            text-align: center;
            margin: 20px 0;
            padding: 10px;
            background: #f8f9fa;
            border-left: 4px solid #e74c3c;
        }}
        
        .question {{
            margin: 25px 0;
            padding: 15px;
            background: #f8f9fa;
            border-left: 4px solid #3498db;
            page-break-inside: avoid;
        }}
        
        .question-number {{
            font-size: 13pt;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        
        .question-text {{
            font-size: 11pt;
            color: #2c3e50;
            margin-bottom: 15px;
            line-height: 1.6;
        }}
        
        .options {{
            margin-left: 20px;
            margin-top: 10px;
        }}
        
        .option {{
            margin: 8px 0;
            padding: 8px;
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        
        .option-letter {{
            font-weight: bold;
            color: #3498db;
            margin-right: 8px;
        }}
        
        .correct-answer {{
            margin-top: 15px;
            padding: 10px;
            background: #d4edda;
            border-left: 4px solid #28a745;
            border-radius: 4px;
        }}
        
        .correct-answer-label {{
            font-weight: bold;
            color: #155724;
            margin-bottom: 5px;
        }}
        
        .correct-answer-text {{
            color: #155724;
        }}
        
        .footer {{
            margin-top: 40px;
            padding-top: 15px;
            border-top: 1px solid #ddd;
            text-align: center;
            font-size: 9pt;
            color: #7f8c8d;
        }}
        
        /* Page break handling */
        .question:last-child {{
            page-break-after: auto;
        }}
    </style>
</head>
<body>
    <div class="header">
        <p class="course-name">{course_name}</p>
        <h1 class="chapter-name">{chapter_name}</h1>
    </div>
    
    <div class="mcq-title">{mcq_title}</div>
    
    {questions_content}
    
    <div class="footer">
        <p>Generated for Skill Lab Courses - TopTeens</p>
        <p>Total Questions: {len(questions)}</p>
    </div>
</body>
</html>"""
    
    return template


def get_mcq_pdf_template(html_content: str, chapter_name: str, course_name: str) -> str:
    """
    Generate professional MCQ PDF template with styling.
    """
    # Extract body content from HTML
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    body = soup.find('body')
    body_content = str(body) if body else html_content
    
    template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>MCQ - {chapter_name}</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm 1.5cm;
        }}
        
        body {{
            font-family: 'Arial', 'Helvetica', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            background: #fff;
        }}
        
        .header {{
            border-bottom: 3px solid #2c3e50;
            padding-bottom: 15px;
            margin-bottom: 30px;
        }}
        
        .course-name {{
            font-size: 14pt;
            color: #34495e;
            font-weight: normal;
            margin: 0;
            margin-bottom: 5px;
        }}
        
        .chapter-name {{
            font-size: 18pt;
            color: #2c3e50;
            font-weight: bold;
            margin: 0;
            margin-bottom: 10px;
        }}
        
        .mcq-title {{
            font-size: 16pt;
            color: #e74c3c;
            font-weight: bold;
            text-align: center;
            margin: 20px 0;
            padding: 10px;
            background: #f8f9fa;
            border-left: 4px solid #e74c3c;
        }}
        
        .question {{
            margin: 25px 0;
            padding: 15px;
            background: #f8f9fa;
            border-left: 4px solid #3498db;
            page-break-inside: avoid;
        }}
        
        .question-number {{
            font-size: 13pt;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        
        .question-text {{
            font-size: 11pt;
            color: #2c3e50;
            margin-bottom: 15px;
            line-height: 1.6;
        }}
        
        .options {{
            margin-left: 20px;
            margin-top: 10px;
        }}
        
        .option {{
            margin: 8px 0;
            padding: 8px;
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        
        .option-letter {{
            font-weight: bold;
            color: #3498db;
            margin-right: 8px;
        }}
        
        .correct-answer {{
            margin-top: 15px;
            padding: 10px;
            background: #d4edda;
            border-left: 4px solid #28a745;
            border-radius: 4px;
        }}
        
        .correct-answer-label {{
            font-weight: bold;
            color: #155724;
            margin-bottom: 5px;
        }}
        
        .correct-answer-text {{
            color: #155724;
        }}
        
        .footer {{
            margin-top: 40px;
            padding-top: 15px;
            border-top: 1px solid #ddd;
            text-align: center;
            font-size: 9pt;
            color: #7f8c8d;
        }}
        
        /* Remove default paragraph margins */
        p {{
            margin: 5px 0;
        }}
        
        /* Style for questions in original HTML */
        strong {{
            color: #2c3e50;
        }}
        
        /* Page break handling */
        .question:last-child {{
            page-break-after: auto;
        }}
    </style>
</head>
<body>
    <div class="header">
        <p class="course-name">{course_name}</p>
        <h1 class="chapter-name">{chapter_name}</h1>
    </div>
    
    <div class="mcq-title">Multiple Choice Questions (MCQ)</div>
    
    {body_content}
    
    <div class="footer">
        <p>Generated for Skill Lab Courses - TopTeens</p>
    </div>
</body>
</html>"""
    
    return template


def format_worksheet_html_for_pdf(html_content: str) -> str:
    """
    Format worksheet HTML to add part sections and separators.
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html_content, 'html.parser')
    body = soup.find('body')
    if not body:
        return html_content
    
    formatted_html = []
    in_part_section = False
    
    # Get all elements in order
    elements = body.find_all(['h2', 'h3', 'h4', 'p', 'ul', 'ol', 'table', 'div'])
    
    for element in elements:
        # Skip if element is nested inside another element we've already processed
        parent = element.parent
        if parent and parent.name in ['p', 'li', 'td', 'th', 'div', 'ul', 'ol']:
            if parent in elements:
                continue
        
        if element.name in ['h2', 'h3', 'h4']:
            # Close previous part section if open
            if in_part_section:
                formatted_html.append('</div>')  # Close part-content
                formatted_html.append('</div>')  # Close part-section
                in_part_section = False
            
            # Start new part section
            formatted_html.append('<div class="part-section">')
            formatted_html.append(f'<div class="part-title">{str(element)}</div>')
            formatted_html.append('<div class="part-content">')
            in_part_section = True
        else:
            # Add content to current part section or as standalone
            if element.name == 'p' and element.get_text(strip=True):
                formatted_html.append(str(element))
            elif element.name in ['ul', 'ol', 'table']:
                formatted_html.append(str(element))
            elif element.name == 'div' and element.get('class') != ['part-section']:
                formatted_html.append(str(element))
    
    # Close last part section if open
    if in_part_section:
        formatted_html.append('</div>')  # Close part-content
        formatted_html.append('</div>')  # Close part-section
    
    # If no headings found, return original content with styling
    if not formatted_html:
        formatted_html.append(str(body))
    
    return '\n'.join(formatted_html)


def get_worksheet_pdf_from_html(html_content: str, chapter_name: str, course_name: str) -> str:
    """
    Generate professional Worksheet PDF template from HTML with similar formatting to MCQ PDF.
    Uses structured approach similar to MCQ PDF generation.
    """
    # Format worksheet content with part sections
    formatted_content = format_worksheet_html_for_pdf(html_content)
    
    template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Worksheet - {chapter_name}</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm 1.5cm;
        }}
        
        body {{
            font-family: 'Arial', 'Helvetica', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            background: #fff;
        }}
        
        .header {{
            border-bottom: 3px solid #27ae60;
            padding-bottom: 15px;
            margin-bottom: 30px;
        }}
        
        .course-name {{
            font-size: 14pt;
            color: #34495e;
            font-weight: normal;
            margin: 0;
            margin-bottom: 5px;
        }}
        
        .chapter-name {{
            font-size: 18pt;
            color: #27ae60;
            font-weight: bold;
            margin: 0;
            margin-bottom: 10px;
        }}
        
        .worksheet-title {{
            font-size: 16pt;
            color: #27ae60;
            font-weight: bold;
            text-align: center;
            margin: 20px 0;
            padding: 10px;
            background: #f8f9fa;
            border-left: 4px solid #27ae60;
        }}
        
        .instructions {{
            background: #e8f5e9;
            border-left: 4px solid #27ae60;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        
        .instructions-title {{
            font-weight: bold;
            color: #2e7d32;
            margin-bottom: 8px;
        }}
        
        .content-section {{
            margin: 20px 0;
            padding: 15px;
        }}
        
        .part-section {{
            margin: 30px 0;
            padding: 20px;
            background: linear-gradient(to right, #e8f5e9 0%, #f1f8e9 100%);
            border-left: 5px solid #27ae60;
            border-radius: 5px;
            page-break-inside: avoid;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .part-title {{
            font-size: 15pt;
            font-weight: bold;
            color: #1b5e20;
            margin-bottom: 15px;
            padding-bottom: 12px;
            border-bottom: 3px solid #27ae60;
        }}
        
        .part-content {{
            background: #fff;
            padding: 18px;
            border-radius: 4px;
            margin-top: 12px;
            border: 1px solid #c8e6c9;
        }}
        
        .activity {{
            margin: 25px 0;
            padding: 15px;
            background: #f8f9fa;
            border-left: 4px solid #27ae60;
            border-radius: 4px;
            page-break-inside: avoid;
        }}
        
        .activity-title {{
            font-size: 13pt;
            font-weight: bold;
            color: #27ae60;
            margin-bottom: 10px;
        }}
        
        .space-for-answer {{
            min-height: 50px;
            border: 1px dashed #bdbdbd;
            margin: 10px 0;
            padding: 10px;
            background: #fafafa;
        }}
        
        /* Separator for different parts */
        .separator {{
            height: 2px;
            background: linear-gradient(to right, transparent, #27ae60, transparent);
            margin: 30px 0;
        }}
        
        /* Style headings as part titles */
        h2, h3 {{
            background: #e8f5e9;
            padding: 12px 15px;
            border-left: 4px solid #27ae60;
            margin: 20px 0 15px 0;
            border-radius: 3px;
            color: #1b5e20;
        }}
        
        .footer {{
            margin-top: 40px;
            padding-top: 15px;
            border-top: 1px solid #ddd;
            text-align: center;
            font-size: 9pt;
            color: #7f8c8d;
        }}
        
        /* List styling */
        ul, ol {{
            margin: 10px 0;
            padding-left: 30px;
        }}
        
        li {{
            margin: 8px 0;
        }}
        
        /* Paragraph spacing */
        p {{
            margin: 10px 0;
        }}
        
        /* Table styling */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        
        table td, table th {{
            border: 1px solid #ddd;
            padding: 8px;
        }}
        
        table th {{
            background: #27ae60;
            color: white;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <p class="course-name">{course_name}</p>
        <h1 class="chapter-name">{chapter_name}</h1>
    </div>
    
    <div class="worksheet-title">Worksheet</div>
    
    <div class="instructions">
        <div class="instructions-title">Instructions:</div>
        <p>Please complete all activities in this worksheet. Write your answers in the spaces provided or on separate sheets if needed.</p>
    </div>
    
    <div class="content-section">
        {formatted_content}
    </div>
    
    <div class="footer">
        <p>Generated for Skill Lab Courses - TopTeens</p>
    </div>
</body>
</html>"""
    
    return template


def format_mcq_html_for_pdf(html_content: str) -> str:
    """
    Format MCQ HTML content for better PDF rendering.
    Converts plain text questions to structured format with questions, options, and answers.
    """
    from bs4 import BeautifulSoup
    import re
    import html
    
    soup = BeautifulSoup(html_content, 'html.parser')
    body = soup.find('body')
    if not body:
        return html_content
    
    # Process paragraphs to format questions
    formatted_html = []
    current_question = None
    current_options = []
    current_correct_answer = None
    
    for para in body.find_all('p'):
        text = para.get_text(strip=True)
        if not text or text == '&nbsp;':
            continue
        
        # Check if this is a question
        question_match = re.match(r'^(?:Question\s+)?(\d+)[:\.]\s*(.+?)$', text, re.IGNORECASE | re.DOTALL)
        if question_match:
            # Save previous question if exists
            if current_question:
                formatted_html.append('<div class="question">')
                formatted_html.append(f'<div class="question-number">Question {current_question["number"]}</div>')
                formatted_html.append(f'<div class="question-text">{html.escape(current_question["text"])}</div>')
                
                if current_options:
                    formatted_html.append('<div class="options">')
                    for opt in current_options:
                        formatted_html.append(f'<div class="option"><span class="option-letter">{opt["letter"]})</span>{html.escape(opt["text"])}</div>')
                    formatted_html.append('</div>')
                
                if current_correct_answer:
                    formatted_html.append('<div class="correct-answer">')
                    formatted_html.append(f'<div class="correct-answer-label">Correct Answer: {current_correct_answer["letter"]})</div>')
                    formatted_html.append(f'<div class="correct-answer-text">{html.escape(current_correct_answer["text"])}</div>')
                    formatted_html.append('</div>')
                
                formatted_html.append('</div>')
            
            # Start new question
            q_num = question_match.group(1)
            q_text = question_match.group(2).strip()
            
            # Remove "Question X:" prefix if still present
            q_text = re.sub(r'^Question\s+\d+[:\.]\s*', '', q_text, flags=re.IGNORECASE).strip()
            
            # Check if options are on the same line
            first_option = re.search(r'\b([A-D])[\.\)]\s+', q_text, re.IGNORECASE)
            if first_option:
                q_text_only = q_text[:first_option.start()].strip()
                options_text = q_text[first_option.start():]
                
                # Extract options - handle both A) and A. formats
                options = re.findall(r'([A-D])[\.\)]\s*([^\nA-D]+?)(?=\s+[A-D][\.\)]|\n|$)', options_text, re.IGNORECASE | re.DOTALL)
                
                current_question = {
                    'number': int(q_num),
                    'text': q_text_only
                }
                current_options = []
                
                if options:
                    for opt_letter, opt_text in options:
                        current_options.append({
                            'letter': opt_letter.upper(),
                            'text': opt_text.strip()
                        })
            else:
                current_question = {
                    'number': int(q_num),
                    'text': q_text
                }
                current_options = []
            
            current_correct_answer = None
            continue
        
        # Check if this contains options (if we have a current question)
        if current_question:
            options_match = re.findall(r'([A-D])[\.\)]\s*([^\nA-D]+?)(?=\s+[A-D][\.\)]|\n|$)', text, re.IGNORECASE | re.DOTALL)
            if options_match:
                for opt_letter, opt_text in options_match:
                    # Check if we already have this option
                    if not any(opt['letter'] == opt_letter.upper() for opt in current_options):
                        current_options.append({
                            'letter': opt_letter.upper(),
                            'text': opt_text.strip()
                        })
                continue
        
        # Check if this is correct answer
        correct_match = re.search(r'Correct\s+Answer[:\.]\s*([A-D])\)\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if correct_match:
            answer_letter = correct_match.group(1).upper()
            answer_text = correct_match.group(2).strip()
            current_correct_answer = {
                'letter': answer_letter,
                'text': answer_text
            }
            continue
        
        # If we have a current question and this doesn't match patterns, might be continuation
        if current_question and not current_options and not current_correct_answer:
            # Might be continuation of question text
            if len(text) > 10:
                current_question['text'] += ' ' + text
    
    # Save last question
    if current_question:
        formatted_html.append('<div class="question">')
        formatted_html.append(f'<div class="question-number">Question {current_question["number"]}</div>')
        formatted_html.append(f'<div class="question-text">{html.escape(current_question["text"])}</div>')
        
        if current_options:
            formatted_html.append('<div class="options">')
            for opt in current_options:
                formatted_html.append(f'<div class="option"><span class="option-letter">{opt["letter"]})</span>{html.escape(opt["text"])}</div>')
            formatted_html.append('</div>')
        
        if current_correct_answer:
            formatted_html.append('<div class="correct-answer">')
            formatted_html.append(f'<div class="correct-answer-label">Correct Answer: {current_correct_answer["letter"]})</div>')
            formatted_html.append(f'<div class="correct-answer-text">{html.escape(current_correct_answer["text"])}</div>')
            formatted_html.append('</div>')
        
        formatted_html.append('</div>')
    
    return '\n'.join(formatted_html) if formatted_html else html_content


def get_worksheet_pdf_template(html_content: str, chapter_name: str, course_name: str) -> str:
    """
    Generate professional Worksheet PDF template with styling.
    Alias for get_worksheet_pdf_from_html for backward compatibility.
    """
    return get_worksheet_pdf_from_html(html_content, chapter_name, course_name)
