"""
Utility functions for heatmap data aggregation and analytics
"""
from django.db.models import Count, Avg, Q
from institute.models import Institute, StudentManagement, InstituteGroup, InstituteMarketingGroup
from app.models import Results, TestCompletion
from users.models import User
import json


def get_career_clusters():
    """Return list of career clusters based on streams"""
    return {
        'PCM': ['AI & Digital Tech', 'Renewable Energy', 'Advanced Manufacturing', 'Space & Aerospace', 'Robotics & Automation'],
        'CBM': ['Healthcare & Biotech', 'Finance & Analytics'],
        'COMM': ['Finance & Analytics', 'Legal & Governance', 'Media & Communications'],
        'HME': ['Creative Arts', 'Social Innovation', 'Hospitality & Tourism'],
        'HMB': ['Healthcare & Biotech', 'Social Innovation']
    }


def calculate_interest_level(student, test2_result):
    """Calculate interest level from test2 (RIASEC) scores"""
    if not test2_result or not test2_result.scores:
        return 0
    
    scores = test2_result.scores
    if isinstance(scores, dict):
        # Get max score from RIASEC categories
        max_score = max(scores.values()) if scores else 0
        # Normalize to 0-100 scale (assuming max is around 6 clicks per question)
        return min(100, (max_score / 6) * 100) if max_score > 0 else 0
    return 0


def calculate_knowledge_level(student, test3_result):
    """Calculate knowledge level from test3 (Intelligence) scores"""
    if not test3_result or not test3_result.scores:
        return 0
    
    scores = test3_result.scores
    if isinstance(scores, dict):
        # Get average of all intelligence scores
        values = [v for v in scores.values() if isinstance(v, (int, float))]
        if values:
            avg_score = sum(values) / len(values)
            # Normalize to 0-100 scale
            return min(100, (avg_score / 10) * 100) if avg_score > 0 else 0
    return 0


def calculate_alignment(student, test1_result, test2_result, test3_result):
    """Calculate alignment based on combined test scores"""
    interest = calculate_interest_level(student, test2_result)
    knowledge = calculate_knowledge_level(student, test3_result)
    
    # Get personality score from test1
    personality_score = 0
    if test1_result and test1_result.results:
        results = test1_result.results
        if isinstance(results, dict):
            values = [v for v in results.values() if isinstance(v, (int, float))]
            if values:
                personality_score = sum(values) / len(values)
    
    # Combined alignment score (weighted average)
    alignment = (interest * 0.4 + knowledge * 0.4 + personality_score * 0.2)
    return min(100, alignment)


def categorize_career_segment(interest, knowledge, alignment):
    """Categorize career segment based on metrics"""
    if interest > 70 and knowledge < 40:
        return {
            'category': 'High Risk',
            'color': '#EF4444',
            'priority': 1
        }
    elif interest > 50 and knowledge > 60:
        return {
            'category': 'Maintenance',
            'color': '#F59E0B',
            'priority': 2
        }
    elif alignment > 70:
        return {
            'category': 'High Alignment',
            'color': '#10B981',
            'priority': 3
        }
    else:
        return {
            'category': 'Monitor',
            'color': '#6B7280',
            'priority': 4
        }


def aggregate_student_career_data(students_queryset, demographic_type='grade'):
    """
    Aggregate student career data by demographics
    
    Args:
        students_queryset: QuerySet of StudentManagement objects
        demographic_type: 'grade', 'section', or 'stream'
    
    Returns:
        Dictionary with aggregated data
    """
    career_clusters = get_career_clusters()
    aggregated_data = {}
    
    for student_mgmt in students_queryset:
        student = student_mgmt.student
        if not student:
            continue
        
        # Get demographic value
        if demographic_type == 'grade':
            # Extract grade from class_and_section (e.g., "Class 10 A" -> "Class 10")
            class_section = student_mgmt.class_and_section
            if class_section and class_section.class_and_section:
                grade = class_section.class_and_section.split()[0] + ' ' + class_section.class_and_section.split()[1] if len(class_section.class_and_section.split()) >= 2 else 'Unknown'
            else:
                grade = 'Unknown'
            demographic_key = grade
        elif demographic_type == 'section':
            class_section = student_mgmt.class_and_section
            if class_section and class_section.class_and_section:
                section = class_section.class_and_section.split()[-1] if len(class_section.class_and_section.split()) > 2 else 'Unknown'
            else:
                section = 'Unknown'
            demographic_key = f'Section {section}'
        else:  # stream
            class_section = student_mgmt.class_and_section
            demographic_key = class_section.stream if class_section and class_section.stream else 'Unknown'
        
        # Get test results
        test1_result = Results.objects.filter(user=student, test_paper='test1').first()
        test2_result = Results.objects.filter(user=student, test_paper='test2').first()
        test3_result = Results.objects.filter(user=student, test_paper='test3').first()
        
        # Calculate metrics
        interest = calculate_interest_level(student, test2_result)
        knowledge = calculate_knowledge_level(student, test3_result)
        alignment = calculate_alignment(student, test1_result, test2_result, test3_result)
        clarity_gap = abs(interest - knowledge)
        
        # Get stream/cluster
        stream = demographic_key if demographic_type == 'stream' else (class_section.stream if class_section and class_section.stream else 'Unknown')
        
        # Map stream to career clusters
        clusters = career_clusters.get(stream, [stream] if stream != 'Unknown' else ['Unknown'])
        
        for cluster in clusters:
            key = f"{cluster}_{demographic_key}"
            if key not in aggregated_data:
                aggregated_data[key] = {
                    'cluster': cluster,
                    'demographic': demographic_key,
                    'interests': [],
                    'knowledges': [],
                    'alignments': [],
                    'clarity_gaps': [],
                    'students': []
                }
            
            aggregated_data[key]['interests'].append(interest)
            aggregated_data[key]['knowledges'].append(knowledge)
            aggregated_data[key]['alignments'].append(alignment)
            aggregated_data[key]['clarity_gaps'].append(clarity_gap)
            aggregated_data[key]['students'].append(student.id)
    
    # Calculate averages and categorize
    heatmap_data = []
    for key, data in aggregated_data.items():
        if data['students']:
            avg_interest = sum(data['interests']) / len(data['interests'])
            avg_knowledge = sum(data['knowledges']) / len(data['knowledges'])
            avg_alignment = sum(data['alignments']) / len(data['alignments'])
            avg_clarity_gap = sum(data['clarity_gaps']) / len(data['clarity_gaps'])
            
            category_info = categorize_career_segment(avg_interest, avg_knowledge, avg_alignment)
            
            heatmap_data.append({
                'cluster': data['cluster'],
                'demographic': data['demographic'],
                'interest': round(avg_interest, 1),
                'knowledge': round(avg_knowledge, 1),
                'alignment': round(avg_alignment, 1),
                'clarityGap': round(avg_clarity_gap, 1),
                'category': category_info['category'],
                'color': category_info['color'],
                'priority': category_info['priority'],
                'studentCount': len(data['students'])
            })
    
    return heatmap_data


def get_heatmap_data_for_group(group_admin, group_type='institute', demographic_type='grade'):
    """
    Get heatmap data for institute group or marketing group
    
    Args:
        group_admin: User object (group admin)
        group_type: 'institute' or 'marketing'
        demographic_type: 'grade', 'section', or 'stream'
    
    Returns:
        Dictionary with heatmap data, stats, and demographics
    """
    if group_type == 'institute':
        institute_group = InstituteGroup.objects.filter(institute_group_admin=group_admin).first()
        if not institute_group:
            return get_empty_heatmap_data()
        students = StudentManagement.objects.filter(institute__institute_group=institute_group)
    else:  # marketing
        marketing_group = InstituteMarketingGroup.objects.filter(marketing_group_admin=group_admin).first()
        if not marketing_group:
            return get_empty_heatmap_data()
        students = StudentManagement.objects.filter(institute__marketing_group=marketing_group)
    
    # Aggregate data first
    heatmap_data = aggregate_student_career_data(students, demographic_type)
    
    # Extract demographics from the heatmap data (this includes "Unknown" if present)
    demographics = {
        'grade': [],
        'section': [],
        'stream': []
    }
    
    # Get unique demographics from heatmap data
    for data in heatmap_data:
        demo = data.get('demographic', '')
        if demo and demo not in demographics[demographic_type]:
            demographics[demographic_type].append(demo)
    
    # Also get from students for completeness (in case some students don't have test results)
    for student_mgmt in students.select_related('class_and_section').distinct():
        class_section = student_mgmt.class_and_section
        if demographic_type == 'grade':
            if class_section and class_section.class_and_section:
                parts = class_section.class_and_section.split()
                if len(parts) >= 2:
                    grade = f"{parts[0]} {parts[1]}"
                    if grade not in demographics['grade']:
                        demographics['grade'].append(grade)
        elif demographic_type == 'section':
            if class_section and class_section.class_and_section:
                parts = class_section.class_and_section.split()
                if len(parts) > 2:
                    section = f"Section {parts[-1]}"
                    if section not in demographics['section']:
                        demographics['section'].append(section)
        elif demographic_type == 'stream':
            if class_section and class_section.stream:
                if class_section.stream not in demographics['stream']:
                    demographics['stream'].append(class_section.stream)
    
    # Sort demographics (put Unknown at the end)
    demographics['grade'] = sorted(demographics['grade'], key=lambda x: (
        int(x.split()[-1]) if x.split()[-1].isdigit() and x != 'Unknown' else 999
    ))
    demographics['section'] = sorted(demographics['section'])
    demographics['stream'] = sorted(demographics['stream'])
    
    # Calculate stats
    stats = {
        'highRisk': len([d for d in heatmap_data if d['category'] == 'High Risk']),
        'aligned': len([d for d in heatmap_data if d['category'] == 'High Alignment']),
        'avgClarityGap': round(sum(d['clarityGap'] for d in heatmap_data) / len(heatmap_data), 1) if heatmap_data else 0
    }
    
    return {
        'heatmapData': heatmap_data,
        'stats': stats,
        'demographics': demographics
    }


def get_heatmap_data_for_institute(institute, demographic_type='grade'):
    """
    Get heatmap data for a single institute
    
    Args:
        institute: Institute object
        demographic_type: 'grade', 'section', or 'stream'
    
    Returns:
        Dictionary with heatmap data, stats, and demographics
    """
    if not institute:
        return get_empty_heatmap_data()
    
    students = StudentManagement.objects.filter(institute=institute)
    
    # Aggregate data first
    heatmap_data = aggregate_student_career_data(students, demographic_type)
    
    # Extract demographics from the heatmap data (this includes "Unknown" if present)
    demographics = {
        'grade': [],
        'section': [],
        'stream': []
    }
    
    # Get unique demographics from heatmap data - PRIMARY SOURCE
    # This ensures we get demographics that actually have data
    for data in heatmap_data:
        demo = data.get('demographic', '')
        # Include even if it's "Unknown" or empty - we'll handle empty separately
        if demo:  # Non-empty string
            if demo not in demographics[demographic_type]:
                demographics[demographic_type].append(demo)
        elif not demo and heatmap_data:  # If we have data but no demographic, add "Unknown"
            if 'Unknown' not in demographics[demographic_type]:
                demographics[demographic_type].append('Unknown')
    
    # Also get from students for completeness (in case some students don't have test results)
    # This helps populate demographics even if they don't have test data yet
    for student_mgmt in students.select_related('class_and_section').distinct():
        class_section = student_mgmt.class_and_section
        if demographic_type == 'grade':
            if class_section and class_section.class_and_section:
                parts = class_section.class_and_section.split()
                if len(parts) >= 2:
                    grade = f"{parts[0]} {parts[1]}"
                    if grade not in demographics['grade']:
                        demographics['grade'].append(grade)
        elif demographic_type == 'section':
            if class_section and class_section.class_and_section:
                parts = class_section.class_and_section.split()
                if len(parts) > 2:
                    section = f"Section {parts[-1]}"
                    if section not in demographics['section']:
                        demographics['section'].append(section)
        elif demographic_type == 'stream':
            if class_section and class_section.stream:
                if class_section.stream not in demographics['stream']:
                    demographics['stream'].append(class_section.stream)
    
    # Sort demographics (put Unknown at the end)
    demographics['grade'] = sorted(demographics['grade'], key=lambda x: (
        int(x.split()[-1]) if x.split()[-1].isdigit() and x != 'Unknown' else 999
    ))
    demographics['section'] = sorted(demographics['section'])
    demographics['stream'] = sorted(demographics['stream'])
    
    # Calculate stats
    stats = {
        'highRisk': len([d for d in heatmap_data if d['category'] == 'High Risk']),
        'aligned': len([d for d in heatmap_data if d['category'] == 'High Alignment']),
        'avgClarityGap': round(sum(d['clarityGap'] for d in heatmap_data) / len(heatmap_data), 1) if heatmap_data else 0
    }
    
    return {
        'heatmapData': heatmap_data,
        'stats': stats,
        'demographics': demographics
    }


def get_empty_heatmap_data():
    """Return empty heatmap data structure"""
    return {
        'heatmapData': [],
        'stats': {
            'highRisk': 0,
            'aligned': 0,
            'avgClarityGap': 0
        },
        'demographics': {
            'grade': [],
            'section': [],
            'stream': []
        }
    }

