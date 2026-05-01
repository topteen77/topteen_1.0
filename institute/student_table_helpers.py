"""
Centralized helper functions for student table rendering across different roles.
This module provides reusable functions for handling student table data and AJAX requests.
"""
from django.core.paginator import Paginator
from counselor.views import (
    get_students_by_role,
    get_class_and_sections_by_role,
    get_class_counts,
    apply_student_filters,
    get_results_data_for_students,
    get_unique_streams_by_role
)
from institute.views import InstituteDashboardView


def get_student_table_context(request, institute=None, counselor=None, per_page=10):
    """
    Centralized function to get context for student table rendering.
    Can be used by any role (institute, counselor, marketing group admin, etc.)
    
    Args:
        request: Django request object
        institute: Institute object (optional, for institute/marketing group views)
        counselor: Counselor object (optional, for counselor views)
        per_page: Number of records per page (default: 10)
    
    Returns:
        dict: Context dictionary with student data, filters, pagination, etc.
    """
    # Get students based on role using centralized function
    stu_manage = get_students_by_role(request.user, counselor=counselor, institute=institute)
    
    # Optimize queryset
    if hasattr(stu_manage, 'select_related'):
        stu_manage = stu_manage.select_related('student', 'class_and_section', 'institute')
    
    # Get filter parameters
    test_taken_filter = request.GET.get('test_taken', '')
    stream_filter = request.GET.get('stream', '')
    
    # Get class and sections for filter dropdown
    class_and_sections = get_class_and_sections_by_role(request.user, stu_manage)
    class_counts = get_class_counts(stu_manage)
    
    # Get unique streams using centralized function
    unique_streams = get_unique_streams_by_role(request.user, stu_manage)
    
    # Get results data for all students (optimized batch fetch)
    # Use the optimized method from InstituteDashboardView
    dashboard_view = InstituteDashboardView()
    
    # Batch fetch test-related data
    from app.models import TestCompletion, Results
    from app_post_matric.models import TestSession as PostMatricTestSession
    
    student_users = [stu.student for stu in stu_manage if stu.student]
    
    # Batch fetch TestCompletion records
    test_completion_map = {}
    if student_users:
        test_completions = TestCompletion.objects.filter(user__in=student_users).select_related('user')
        test_completion_map = {tc.user: tc for tc in test_completions}
    
    # Batch fetch post-matric TestSession records
    post_matric_sessions_map = {}
    if student_users:
        post_matric_sessions = PostMatricTestSession.objects.filter(
            user__in=student_users
        ).select_related('user', 'test')
        for session in post_matric_sessions:
            if session.user not in post_matric_sessions_map:
                post_matric_sessions_map[session.user] = []
            post_matric_sessions_map[session.user].append(session)
    
    # Batch fetch Results
    results_queryset_map = {}
    if student_users:
        results_queryset = Results.objects.filter(user__in=student_users).select_related('user')
        for result in results_queryset:
            if result.user not in results_queryset_map:
                results_queryset_map[result.user] = []
            results_queryset_map[result.user].append(result)
    
    # Fetch results for each student using optimized method
    results_data = {}
    for stu in stu_manage:
        if not stu.student:
            continue
        user = stu.student
        student_result = dashboard_view._get_student_test_result_optimized(
            user,
            stu,
            test_completion_map.get(user),
            post_matric_sessions_map.get(user, []),
            results_queryset_map.get(user, [])
        )
        results_data[user.id] = student_result
    
    # Apply filters using centralized function
    filtered_students = apply_student_filters(stu_manage, request, results_data=results_data)
    
    # Handle stream filter separately if needed
    if stream_filter:
        if hasattr(filtered_students, 'filter'):
            filtered_students = filtered_students.filter(class_and_section__stream=stream_filter)
        else:
            filtered_students = [
                s for s in filtered_students
                if hasattr(s, 'class_and_section') and s.class_and_section and
                s.class_and_section.stream == stream_filter
            ]
    
    # Handle per_page parameter
    per_page_param = request.GET.get('per_page', str(per_page))
    if per_page_param == 'all':
        per_page_value = 10000  # Large number to show all
    else:
        try:
            per_page_value = int(per_page_param)
        except (ValueError, TypeError):
            per_page_value = per_page
    
    # Pagination
    if isinstance(filtered_students, list):
        sorted_students = sorted(filtered_students, key=lambda x: x.created, reverse=True)
        pages = Paginator(sorted_students, per_page_value)
    else:
        pages = Paginator(filtered_students.order_by('-created'), per_page_value)
    
    page_number = request.GET.get('page', 1)
    total_students = pages.get_page(page_number)
    
    return {
        'total_students': total_students,
        'total_students_count': list(stu_manage),
        'class_and_sections': class_and_sections,
        'class_counts': class_counts,
        'unique_streams': unique_streams,
        'results_data': results_data,
        'stu': filtered_students if hasattr(filtered_students, 'filter') else filtered_students,
    }


def get_student_table_config(role='institute'):
    """
    Get table configuration for different roles.
    
    Args:
        role: Role name ('institute', 'counselor', 'marketing', etc.)
    
    Returns:
        dict: Table configuration with column visibility settings
    """
    configs = {
        'institute': {
            'show_stream': True,
            'show_email': False,
            'show_contact': False,
            'show_created': True,
            'show_report': True,
            'show_actions': True,
            'show_block': True,
            'show_followup': False,
            'show_institute': False,
            'role': 'institute'
        },
        'counselor': {
            'show_stream': False,
            'show_email': True,
            'show_contact': True,
            'show_created': False,
            'show_report': True,
            'show_actions': False,
            'show_block': False,
            'show_followup': True,
            'show_institute': False,
            'role': 'counselor'
        },
        'marketing': {
            'show_stream': False,
            'show_email': True,
            'show_contact': True,
            'show_created': False,
            'show_report': True,
            'show_actions': False,
            'show_block': False,
            'show_followup': False,
            'show_institute': True,
            'role': 'marketing'
        },
        'institute_group': {
            'show_stream': True,
            'show_email': False,
            'show_contact': False,
            'show_created': True,
            'show_report': True,
            'show_actions': False,
            'show_block': False,
            'show_followup': False,
            'show_institute': True,
            'role': 'institute_group'
        },
    }
    
    return configs.get(role, configs['institute'])


def get_student_action_urls(role='institute'):
    """
    Get action URLs for different roles.
    
    Args:
        role: Role name
    
    Returns:
        dict: Action URLs for update, delete, block, change_password
    """
    urls = {
        'institute': {
            'update': 'institute:update_student',
            'delete': 'institute:delete_student',
            'block': 'institute:institutestudentblock',
            'change_password': 'institute:change_student_password'
        },
        'counselor': {
            'update': None,
            'delete': None,
            'block': None,
            'change_password': None
        },
        'marketing': {
            'update': None,
            'delete': None,
            'block': None,
            'change_password': None
        },
        'institute_group': {
            'update': None,
            'delete': None,
            'block': None,
            'change_password': None
        },
    }
    
    return urls.get(role, urls['institute'])

