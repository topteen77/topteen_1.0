#!/usr/bin/env python3
"""
Generate MCQ HTML from JSON data
"""

import html


def generate_mcq_html_from_json(mcq_data: dict) -> str:
    """
    Generate HTML for MCQ from JSON data.
    
    Args:
        mcq_data: Dictionary with MCQ structure containing title and questions
        
    Returns:
        HTML string for MCQ
    """
    questions = mcq_data.get('questions', [])
    title = mcq_data.get('title', 'Multiple Choice Questions')
    
    html_parts = []
    
    # Add title
    html_parts.append(f'<h1>{html.escape(title)}</h1>')
    
    # Process each question
    for q in questions:
        q_num = q.get('question_number', 0)
        q_text = html.escape(q.get('question_text', ''))
        options = q.get('options', [])
        correct_answer = q.get('correct_answer', {})
        
        # Question
        html_parts.append(f'<div class="question">')
        html_parts.append(f'<p><strong>Question {q_num}: {q_text}</strong></p>')
        
        # Options
        if options:
            html_parts.append('<div class="options">')
            for opt in options:
                opt_letter = opt.get('letter', '')
                opt_text = html.escape(opt.get('text', ''))
                html_parts.append(f'<p>{opt_letter}) {opt_text}</p>')
            html_parts.append('</div>')
        
        # Correct answer
        if correct_answer:
            answer_letter = correct_answer.get('letter', '')
            answer_text = html.escape(correct_answer.get('text', ''))
            html_parts.append(f'<p><strong>Correct Answer:</strong> {answer_letter}) {answer_text}</p>')
        
        html_parts.append('</div>')
        html_parts.append('<p>&nbsp;</p>')  # Spacing between questions
    
    # Wrap in HTML document
    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{html.escape(title)}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 20px auto;
            padding: 20px;
            line-height: 1.6;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        .question {{
            margin: 20px 0;
            padding: 15px;
            background: #f8f9fa;
            border-left: 4px solid #3498db;
        }}
        .options {{
            margin: 10px 0 10px 20px;
        }}
        .options p {{
            margin: 5px 0;
        }}
        strong {{
            color: #2c3e50;
        }}
    </style>
</head>
<body>
{''.join(html_parts)}
</body>
</html>"""
    
    return full_html


if __name__ == "__main__":
    # Test
    import json
    import sys
    
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
        with open(json_file, 'r', encoding='utf-8') as f:
            mcq_data = json.load(f)
        
        html_output = generate_mcq_html_from_json(mcq_data)
        print(html_output)
    else:
        print("Usage: python mcq_html_generator.py <mcq_json_file>")
