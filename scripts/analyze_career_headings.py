#!/usr/bin/env python3
"""
Analyze career HTML documents to check heading compliance.
Checks for:
1. Documents with all required headings
2. Documents missing some headings
3. Documents with extra headings not in the standard list
"""

import os
from pathlib import Path
from bs4 import BeautifulSoup
from collections import defaultdict
import json

# Standard headings list
STANDARD_HEADINGS = [
    "Introduction",
    "Career Description",
    "Roles and Responsibilities",
    "Study Route & Eligibility Criteria",
    "Significant Observations",
    "Internships & Practical Exposure",
    "Courses & Specializations",
    "Top Institutes- India",
    "Top Institutes- International",
    "Entrance Tests Required",
    "Ideal Progressing Career Path",
    "Major Areas of Employment",
    "Prominent Employers",
    "Pros and Cons of the Profession",
    "Industry Trends and Future Outlook",
    "Salary Expectations",
    "Key Software Tools",
    "Professional Organizations and Networks",
    "Notable Industry Leaders",
    "Advice for Aspiring"
]

# Normalize heading text for comparison (case-insensitive, strip whitespace)
def normalize_heading(text):
    """Normalize heading text for comparison"""
    if not text:
        return ""
    return text.strip().lower()

# Create normalized standard headings set
STANDARD_HEADINGS_NORMALIZED = {normalize_heading(h) for h in STANDARD_HEADINGS}

def extract_headings_from_html(html_path):
    """Extract all headings (h1, h2, h3, h4, and strong tags) from HTML file"""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        headings = []
        seen_normalized = set()
        
        # Extract all headings (h1-h4)
        for tag in ['h1', 'h2', 'h3', 'h4']:
            for heading in soup.find_all(tag):
                text = heading.get_text(strip=True)
                if text:
                    normalized = normalize_heading(text)
                    if normalized not in seen_normalized:
                        headings.append(text)
                        seen_normalized.add(normalized)
        
        # Also check for headings in <strong> tags (common pattern in these documents)
        for strong in soup.find_all('strong'):
            text = strong.get_text(strip=True)
            # Only consider if it looks like a heading (not too long, reasonable length)
            if text and 5 <= len(text) <= 150:
                normalized = normalize_heading(text)
                if normalized not in seen_normalized:
                    # Check if it's likely a heading (not in a list item, not part of a sentence)
                    parent = strong.parent
                    if parent:
                        # If parent is p or div and text is at the start, it's likely a heading
                        if parent.name in ['p', 'div']:
                            parent_text = parent.get_text(strip=True)
                            # Check if the strong text appears at the start of parent
                            if parent_text.startswith(text) or parent_text.startswith(text.replace('\xa0', ' ')):
                                headings.append(text)
                                seen_normalized.add(normalized)
                        # If parent is already a heading tag, skip
                        elif parent.name not in ['h1', 'h2', 'h3', 'h4']:
                            # Check if it's standalone (not nested in other text)
                            siblings = [sibling for sibling in parent.children if hasattr(sibling, 'string')]
                            if len(siblings) == 1 or (len(siblings) == 2 and any(s.string and s.string.strip() == '' for s in siblings)):
                                headings.append(text)
                                seen_normalized.add(normalized)
        
        return headings
    except Exception as e:
        print(f"Error reading {html_path}: {e}")
        return []

def analyze_document(html_path, filename):
    """Analyze a single document and return analysis results"""
    headings = extract_headings_from_html(html_path)
    headings_normalized = {normalize_heading(h) for h in headings}
    
    # Find missing headings
    missing = []
    for std_heading in STANDARD_HEADINGS:
        std_normalized = normalize_heading(std_heading)
        if std_normalized not in headings_normalized:
            missing.append(std_heading)
    
    # Find extra headings (not in standard list)
    extra = []
    for heading in headings:
        heading_normalized = normalize_heading(heading)
        if heading_normalized not in STANDARD_HEADINGS_NORMALIZED:
            extra.append(heading)
    
    # Check if all headings are present
    has_all = len(missing) == 0
    
    return {
        'filename': filename,
        'headings_found': headings,
        'headings_count': len(headings),
        'missing_headings': missing,
        'missing_count': len(missing),
        'extra_headings': extra,
        'extra_count': len(extra),
        'has_all_headings': has_all
    }

def main():
    """Main analysis function"""
    base_dir = Path('/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/demo-topteens/career_html_output')
    
    if not base_dir.exists():
        print(f"Error: Directory {base_dir} does not exist!")
        return
    
    # Find all HTML and TXT files (recursively)
    html_files = list(base_dir.glob('**/*.html')) + list(base_dir.glob('**/*.txt'))
    
    if not html_files:
        print(f"No HTML or TXT files found in {base_dir}")
        return
    
    print(f"Found {len(html_files)} HTML files\n")
    print("=" * 80)
    print("CAREER HEADINGS ANALYSIS REPORT")
    print("=" * 80)
    print()
    
    # Analyze all documents
    results = []
    for html_file in sorted(html_files):
        result = analyze_document(html_file, html_file.name)
        results.append(result)
    
    # Categorize results
    complete_docs = [r for r in results if r['has_all_headings']]
    incomplete_docs = [r for r in results if not r['has_all_headings']]
    
    # Print summary
    print("SUMMARY")
    print("-" * 80)
    print(f"Total documents analyzed: {len(results)}")
    print(f"Documents with ALL headings: {len(complete_docs)}")
    print(f"Documents with MISSING headings: {len(incomplete_docs)}")
    print()
    
    # Print documents with all headings
    if complete_docs:
        print("=" * 80)
        print("1. DOCUMENTS WITH ALL REQUIRED HEADINGS")
        print("=" * 80)
        for doc in complete_docs:
            print(f"  ✓ {doc['filename']} ({doc['headings_count']} headings)")
        print()
    
    # Print documents with missing headings
    if incomplete_docs:
        print("=" * 80)
        print("2. DOCUMENTS WITH MISSING HEADINGS")
        print("=" * 80)
        for doc in incomplete_docs:
            print(f"\n  ✗ {doc['filename']}")
            print(f"    Missing ({doc['missing_count']}): {', '.join(doc['missing_headings']) if doc['missing_headings'] else 'None'}")
            print(f"    Found headings: {doc['headings_count']}")
        print()
    
    # Print documents with extra headings
    docs_with_extra = [r for r in results if r['extra_count'] > 0]
    if docs_with_extra:
        print("=" * 80)
        print("3. DOCUMENTS WITH EXTRA HEADINGS (Not in standard list)")
        print("=" * 80)
        for doc in docs_with_extra:
            print(f"\n  ⚠ {doc['filename']}")
            print(f"    Extra headings ({doc['extra_count']}):")
            for extra in doc['extra_headings']:
                print(f"      - {extra}")
        print()
    
    # Generate detailed statistics
    print("=" * 80)
    print("4. HEADING STATISTICS")
    print("=" * 80)
    
    # Count how many documents have each standard heading
    heading_counts = defaultdict(int)
    for result in results:
        found_normalized = {normalize_heading(h) for h in result['headings_found']}
        for std_heading in STANDARD_HEADINGS:
            if normalize_heading(std_heading) in found_normalized:
                heading_counts[std_heading] += 1
    
    print("\nFrequency of each standard heading across all documents:")
    for heading in STANDARD_HEADINGS:
        count = heading_counts[heading]
        percentage = (count / len(results)) * 100 if results else 0
        status = "✓" if count == len(results) else "⚠"
        print(f"  {status} {heading}: {count}/{len(results)} ({percentage:.1f}%)")
    
    # Find most common extra headings
    all_extra_headings = defaultdict(int)
    for result in results:
        for extra in result['extra_headings']:
            all_extra_headings[extra] += 1
    
    if all_extra_headings:
        print("\nMost common extra headings (not in standard list):")
        sorted_extra = sorted(all_extra_headings.items(), key=lambda x: x[1], reverse=True)
        for heading, count in sorted_extra[:10]:  # Top 10
            print(f"  - {heading}: appears in {count} document(s)")
    
    # Save detailed JSON report
    json_report = {
        'standard_headings': STANDARD_HEADINGS,
        'total_documents': len(results),
        'complete_documents': len(complete_docs),
        'incomplete_documents': len(incomplete_docs),
        'documents': results,
        'heading_statistics': dict(heading_counts),
        'extra_headings_frequency': dict(all_extra_headings)
    }
    
    json_path = base_dir / 'heading_analysis_report.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'=' * 80}")
    print(f"Detailed JSON report saved to: {json_path}")
    print("=" * 80)

if __name__ == '__main__':
    main()

