#!/usr/bin/env python3
"""
Script to convert Word documents (.docx) to HTML format and save as .txt files.
This script processes all .docx files in the career library directory and converts them
to HTML with basic formatting preserved (bold, italic, paragraphs, lists).
"""

import os
import sys
import re
from pathlib import Path
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
import html

def convert_docx_to_html(docx_path):
    """
    Convert a single Word document to HTML format.
    
    Args:
        docx_path (str): Path to the .docx file
        
    Returns:
        str: HTML content of the document
    """
    try:
        doc = Document(docx_path)
        html_content = []
        
        # Extract filename without extension for title matching
        filename = Path(docx_path).stem
        
        for paragraph in doc.paragraphs:
            if not paragraph.text.strip():
                continue
                
            # Convert paragraph to HTML
            para_html = convert_paragraph_to_html(paragraph)
            if para_html:
                html_content.append(para_html)
        
        # Clean up redundant HTML tags and handle title conversion
        full_html = '\n'.join(html_content)
        cleaned_html = clean_redundant_tags(full_html, filename)
        
        return cleaned_html
    
    except Exception as e:
        print(f"Error processing {docx_path}: {str(e)}")
        return None

def convert_paragraph_to_html(paragraph):
    """
    Convert a docx paragraph to HTML format.
    
    Args:
        paragraph: docx paragraph object
        
    Returns:
        str: HTML representation of the paragraph
    """
    if not paragraph.text.strip():
        return ""
    
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
    """
    Convert a list item paragraph to HTML.
    
    Args:
        paragraph: docx paragraph object
        
    Returns:
        str: HTML representation of the list item
    """
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
        # Determine if it's a numbered or bulleted list
        if paragraph.style.name.startswith('List Number'):
            return f"<li>{item_text}</li>"
        else:
            return f"<li>{item_text}</li>"
    
    return ""

def clean_redundant_tags(html_content, filename=None):
    """
    Clean up redundant HTML tags like </strong><strong> or </em><em>.
    Also convert <p><strong> patterns to proper heading tags and handle title tags.
    
    Args:
        html_content (str): Raw HTML content
        filename (str): Original filename (without extension) for title matching
        
    Returns:
        str: Cleaned HTML content
    """
    # Convert <p><strong> patterns to heading tags based on content
    html_content = convert_strong_paragraphs_to_headings(html_content, filename)
    
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

def convert_strong_paragraphs_to_headings(html_content, filename=None):
    """
    Convert <p><strong> patterns to appropriate heading tags based on content analysis.
    Also handle title tag conversion for the first H1 that matches filename.
    Ensures only one H1 tag per file.
    
    Args:
        html_content (str): HTML content with <p><strong> patterns
        filename (str): Original filename (without extension) for title matching
        
    Returns:
        str: HTML content with proper heading tags and title tag
    """
    # Split content into lines for analysis
    lines = html_content.split('\n')
    processed_lines = []
    title_added = False
    h1_found = False
    
    for line in lines:
        # Check if line matches <p><strong>pattern</strong></p>
        strong_match = re.match(r'<p><strong>(.*?)</strong></p>', line.strip())
        
        if strong_match:
            content = strong_match.group(1).strip()
            
            # Determine heading level based on content patterns
            heading_level = determine_heading_level(content, 1)
            
            # Check if this should be the first H1 and matches filename
            if (heading_level == 1 and not h1_found and filename and 
                not title_added and content.lower() == filename.lower()):
                # Convert to title tag
                title_tag = f"<title>{content}</title>"
                processed_lines.append(title_tag)
                title_added = True
                h1_found = True
            elif heading_level == 1 and not h1_found:
                # This is the first H1 (not matching filename)
                heading_tag = f"<h1>{content}</h1>"
                processed_lines.append(heading_tag)
                h1_found = True
            else:
                # All other headings should be H2 or lower
                if heading_level == 1:
                    heading_level = 2  # Convert H1 to H2 if H1 already exists
                
                heading_tag = f"<h{heading_level}>{content}</h{heading_level}>"
                processed_lines.append(heading_tag)
        else:
            processed_lines.append(line)
    
    # If no title was added and filename exists, add it as title at the beginning
    if not title_added and filename:
        title_tag = f"<title>{filename}</title>"
        processed_lines.insert(0, title_tag)
    
    return '\n'.join(processed_lines)

def determine_heading_level(content, current_level):
    """
    Determine the appropriate heading level based on content analysis.
    Note: This function determines the logical level, but the actual level
    will be adjusted to ensure only one H1 per file.
    
    Args:
        content (str): The text content to analyze
        current_level (int): Current heading level (not used in this implementation)
        
    Returns:
        int: Appropriate heading level (1-6)
    """
    content_lower = content.lower()
    
    # H1 patterns - Main career titles (only one per file)
    h1_patterns = [
        r'^[a-z\s]+$',  # Simple career names like "Bioinformatician"
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
        r'salary\s+expectations?',
        r'key\s+software\s+tools?',
        r'professional\s+organizations?',
        r'notable.*leaders?',
        r'advice\s+for\s+aspiring'
    ]
    
    # H3 patterns - Sub-sections
    h3_patterns = [
        r'^[a-z\s]+:$',  # Simple labels ending with colon
        r'internships?',
        r'practical\s+exposure',
        r'academic\s+related\s+points',
        r'significant\s+observations'
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

def process_directory(source_dir, output_dir):
    """
    Process all .docx files in the source directory and convert to HTML.
    
    Args:
        source_dir (str): Source directory containing .docx files
        output_dir (str): Output directory for .txt files
    """
    source_path = Path(source_dir)
    output_path = Path(output_dir)
    
    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Find all .docx files recursively
    docx_files = list(source_path.rglob("*.docx"))
    
    # Filter out temporary files (starting with ~$)
    docx_files = [f for f in docx_files if not f.name.startswith('~$')]
    
    print(f"Found {len(docx_files)} .docx files to process")
    
    processed_count = 0
    error_count = 0
    
    for docx_file in docx_files:
        try:
            # Get relative path to maintain directory structure
            relative_path = docx_file.relative_to(source_path)
            
            # Create output filename (replace .docx with .txt)
            output_filename = relative_path.with_suffix('.txt')
            output_file_path = output_path / output_filename
            
            # Create output subdirectory if needed
            output_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert document to HTML
            html_content = convert_docx_to_html(docx_file)
            
            if html_content:
                # Save HTML content to .txt file
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                processed_count += 1
                print(f"✓ Processed: {relative_path}")
            else:
                error_count += 1
                print(f"✗ Failed to process: {relative_path}")
                
        except Exception as e:
            error_count += 1
            print(f"✗ Error processing {docx_file}: {str(e)}")
    
    # Print summary
    print(f"\n=== CONVERSION SUMMARY ===")
    print(f"Total files found: {len(docx_files)}")
    print(f"Successfully processed: {processed_count}")
    print(f"Errors: {error_count}")
    print(f"Output directory: {output_path.absolute()}")

def main():
    """Main function to run the conversion script."""
    # Default paths
    source_directory = "/home/itpc6/Public/share/content- Topteen/career library 2025/final careers"
    output_directory = "career_html_output"
    
    # Check if source directory exists
    if not os.path.exists(source_directory):
        print(f"Error: Source directory does not exist: {source_directory}")
        sys.exit(1)
    
    print("=== Word Document to HTML Converter ===")
    print(f"Source directory: {source_directory}")
    print(f"Output directory: {output_directory}")
    print()
    
    # Process all documents
    process_directory(source_directory, output_directory)

if __name__ == "__main__":
    main()
