from datetime import datetime, date, timedelta
import json
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render
from django.core.paginator import Paginator
from app.models import Answer, Results
from institute.filters import StudentFilter
from institute.models import ClassAndSection, Institute, StudentManagement
from .models import Counselor, Quiz, Chapter, Part, QuizAnswers, QuizResults , VideoProgress ,CounselorCourse ,Notes, CounselorCertification
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count
from django.utils import timezone
from django.views import View
from .models import Counselor, FollowUpStatus
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt

from django.http import JsonResponse, HttpResponse, HttpResponse


from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

User = get_user_model()

# Create your views here.

# def CounselorMainDashboard(request):
    
#     return render(request, 'topteenfrontend/user/app/counselor_dashboard.html')

def get_students_by_role(user, counselor=None, institute=None):
    """
    Centralized function to get students based on user role.
    
    Args:
        user: The User object (request.user)
        counselor: Counselor object (required if user is a counselor)
        institute: Institute object (if provided, filter by this specific institute regardless of role)
    
    Returns:
        QuerySet of StudentManagement objects based on role:
        - Counselor: Only assigned students
        - Institute: All students in their own institute
        - Institute Group Admin: All students in institutes within their group (or specific institute if provided)
        - Marketing Group Admin: All students in institutes within their marketing group (or specific institute if provided)
    """
    from core import choices
    from institute.models import InstituteGroup, InstituteMarketingGroup
    
    # If counselor is provided, always return only assigned students for that counselor
    # This takes priority over institute filtering to ensure correct data when viewing counselor dashboard
    if counselor:
        if not counselor.counselor_admin:
            return StudentManagement.objects.none()
        
        # If institute is also provided, verify it matches the counselor's institute
        if institute and counselor.counselor_admin.id != institute.id:
            return StudentManagement.objects.none()
        
        institute = counselor.counselor_admin
        # Return only assigned students (not unassigned) - matching production code
        students = counselor.get_students(institute=institute)
        # Optimize with select_related to avoid N+1 queries
        return students.select_related('student', 'class_and_section', 'institute')
    
    # If a specific institute is provided (but no counselor), filter by that institute regardless of role
    # This ensures that when viewing a specific institute page, only that institute's data is shown
    if institute:
        # Verify user has permission to view this institute
        user_type = user.user_type
        
        if user_type == choices.UserType.INSTITUTE:
            # Institute users can only see their own institute
            user_institute = Institute.objects.filter(created_by=user).first()
            if user_institute and user_institute.id != institute.id:
                return StudentManagement.objects.none()
        elif user_type == choices.UserType.INSTITUTEGROUPADMIN:
            # Institute Group Admin can see institutes in their group
            institute_group = InstituteGroup.objects.filter(institute_group_admin=user).first()
            if institute_group and institute.institute_group != institute_group:
                return StudentManagement.objects.none()
        elif user_type == choices.UserType.MARKETINGGROUPADMIN:
            # Marketing Group Admin can see institutes in their marketing group
            marketing_group = InstituteMarketingGroup.objects.filter(marketing_group_admin=user).first()
            if marketing_group and institute.marketing_group != marketing_group:
                return StudentManagement.objects.none()
        elif user_type == choices.UserType.COUNSELOR:
            # Counselor can see students from their assigned institute
            if not counselor:
                try:
                    counselor = Counselor.objects.select_related('counselor_admin', 'coun_user').get(coun_user=user)
                except Counselor.DoesNotExist:
                    return StudentManagement.objects.none()
            
            # If counselor is associated with an institute, they can only see that institute's students
            if counselor.counselor_admin:
                if institute and counselor.counselor_admin.id != institute.id:
                    return StudentManagement.objects.none()
            else:
                # If counselor is not associated with any institute, they can only see students with no institute
                if institute is not None:
                    return StudentManagement.objects.none()
        
        # Return students for the specific institute (or None if institute is None)
        if institute:
            return StudentManagement.objects.filter(institute=institute).select_related('student', 'class_and_section', 'institute')
        else:
            return StudentManagement.objects.filter(institute__isnull=True).select_related('student', 'class_and_section', 'institute')
    
    # If counselor is provided, always return only assigned students for that counselor
    # This ensures that when viewing a counselor dashboard (even by marketing/institute users),
    # only the counselor's assigned students are shown
    if counselor:
        if not counselor.counselor_admin:
            return StudentManagement.objects.none()
        
        institute = counselor.counselor_admin
        # Return only assigned students (not unassigned) - matching production code
        students = counselor.get_students(institute=institute)
        # Optimize with select_related to avoid N+1 queries
        return students.select_related('student', 'class_and_section', 'institute')
    
    # If counselor is explicitly provided, return only assigned students for that counselor
    # This ensures that when viewing a counselor dashboard (even as a marketing user),
    # we show only the counselor's assigned students, not all students in the marketing group
    if counselor:
        if not counselor.counselor_admin:
            return StudentManagement.objects.none()
        
        institute = counselor.counselor_admin
        # Return only assigned students (not unassigned) - matching production code
        students = counselor.get_students(institute=institute)
        # Optimize with select_related to avoid N+1 queries
        return students.select_related('student', 'class_and_section', 'institute')
    
    # If no specific institute provided, use role-based logic
    user_type = user.user_type
    
    if user_type == choices.UserType.COUNSELOR:
        # Counselor sees only their assigned students (matching production code)
        # Try to get counselor from user
        try:
            counselor = Counselor.objects.select_related('counselor_admin', 'coun_user').get(coun_user=user)
        except Counselor.DoesNotExist:
            return StudentManagement.objects.none()
        
        if not counselor.counselor_admin:
            return StudentManagement.objects.none()
        
        institute = counselor.counselor_admin
        # Return only assigned students (not unassigned) - matching production code
        students = counselor.get_students(institute=institute)
        # Optimize with select_related to avoid N+1 queries
        return students.select_related('student', 'class_and_section', 'institute')
    
    elif user_type == choices.UserType.INSTITUTE:
        # Institute sees all students in their own institute
        if not institute:
            # Try to get institute from user
            try:
                institute = Institute.objects.filter(created_by=user).first()
            except Institute.DoesNotExist:
                return StudentManagement.objects.none()
        
        if not institute:
            return StudentManagement.objects.none()
        
        return StudentManagement.objects.filter(institute=institute).select_related('student', 'class_and_section', 'institute')
    
    elif user_type == choices.UserType.INSTITUTEGROUPADMIN:
        # Institute Group Admin sees all students in institutes within their group
        institute_group = InstituteGroup.objects.filter(institute_group_admin=user).first()
        if not institute_group:
            return StudentManagement.objects.none()
        
        return StudentManagement.objects.filter(institute__institute_group=institute_group).select_related('student', 'class_and_section', 'institute')
    
    elif user_type == choices.UserType.MARKETINGGROUPADMIN:
        # Marketing Group Admin sees all students in institutes within their marketing group
        marketing_group = InstituteMarketingGroup.objects.filter(marketing_group_admin=user).first()
        if not marketing_group:
            return StudentManagement.objects.none()
        
        return StudentManagement.objects.filter(institute__marketing_group=marketing_group).select_related('student', 'class_and_section', 'institute')
    
    else:
        # Unknown role, return empty queryset
        return StudentManagement.objects.none()


def get_class_and_sections_by_role(user, students_queryset):
    """
    Get class_and_sections based on user role and the students they can see.
    Returns distinct class_and_sections for the students in the queryset.
    
    Args:
        user: The User object (request.user)
        students_queryset: QuerySet of StudentManagement objects
    
    Returns:
        QuerySet of ClassAndSection objects (distinct, ordered)
    """
    if not students_queryset.exists():
        return ClassAndSection.objects.none()
    
    # Get distinct class_and_sections from the students queryset
    class_and_sections = ClassAndSection.objects.filter(
        student_management__in=students_queryset
    ).distinct().order_by('class_and_section')
    
    return class_and_sections


def apply_student_filters(students_data, request, results_data=None):
    """
    Centralized function to apply common filters to student data.
    Works with both QuerySet and list of student dictionaries.
    
    Args:
        students_data: QuerySet of StudentManagement objects or list of student dicts
        request: Django request object with GET parameters
        results_data: Optional dict of test results (for test_taken filter)
                      Format: {student_user: {'test_status': 'completed'|'in_progress'|'no_tests', ...}}
    
    Returns:
        Filtered students_data (same type as input)
    """
    # Get filter parameters from request
    class_filter = request.GET.get('class_and_section', '').strip()
    name_filter = request.GET.get('student_name', '').strip()
    test_taken_filter = request.GET.get('test_taken', '').strip()
    
    # Handle QuerySet
    if hasattr(students_data, 'filter'):
        # It's a QuerySet
        queryset = students_data
        
        # Apply class filter
        if class_filter:
            queryset = queryset.filter(class_and_section__class_and_section=class_filter)
        
        # Apply name filter
        if name_filter:
            queryset = queryset.filter(student__name__icontains=name_filter)
        
        # Apply test_taken filter (requires results_data)
        if test_taken_filter and results_data:
            # We need to filter based on test_status in results_data
            # This is more complex for QuerySet, so we'll convert to list and filter
            student_list = list(queryset)
            filtered_list = []
            for student_mgmt in student_list:
                student_user = student_mgmt.student
                student_result = results_data.get(student_user, {})
                test_status = student_result.get('test_status', 'no_tests')
                
                if test_taken_filter == 'Yes' and test_status == 'completed':
                    filtered_list.append(student_mgmt)
                elif test_taken_filter == 'No' and test_status == 'no_tests':
                    filtered_list.append(student_mgmt)
                elif test_taken_filter == 'In Progress' and test_status == 'in_progress':
                    filtered_list.append(student_mgmt)
            
            return filtered_list
        
        return queryset
    
    # Handle list of dictionaries (merged_data format)
    else:
        # It's a list
        filtered_data = list(students_data)
        
        # Apply class filter
        if class_filter:
            filtered_data = [
                s for s in filtered_data
                if hasattr(s, 'get') and s.get('student') and 
                hasattr(s['student'], 'class_and_section') and
                s['student'].class_and_section and
                str(s['student'].class_and_section.class_and_section) == class_filter
            ]
        
        # Apply name filter
        if name_filter:
            filtered_data = [
                s for s in filtered_data
                if hasattr(s, 'get') and s.get('student') and
                hasattr(s['student'], 'student') and
                name_filter.lower() in s['student'].student.name.lower()
            ]
        
        # Apply test_taken filter
        if test_taken_filter and results_data:
            filtered_list = []
            for student_info in filtered_data:
                student = student_info.get('student')
                if student:
                    student_user = getattr(student, 'student', student)
                    student_result = results_data.get(student_user, {})
                    test_status = student_result.get('test_status', 'no_tests')
                    
                    if test_taken_filter == 'Yes' and test_status == 'completed':
                        filtered_list.append(student_info)
                    elif test_taken_filter == 'No' and test_status == 'no_tests':
                        filtered_list.append(student_info)
                    elif test_taken_filter == 'In Progress' and test_status == 'in_progress':
                        filtered_list.append(student_info)
            
            filtered_data = filtered_list
        
        return filtered_data


def get_class_counts(students_queryset):
    """
    Centralized function to get class counts for display in dropdown.
    
    Args:
        students_queryset: QuerySet or list of StudentManagement objects
    
    Returns:
        Dict with class names as keys and student counts as values
    """
    class_counts = {}
    
    # Handle QuerySet
    if hasattr(students_queryset, 'values_list'):
        for student in students_queryset:
            if student.class_and_section:
                class_name = student.class_and_section.class_and_section
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
    # Handle list
    else:
        for student_item in students_queryset:
            # Handle both StudentManagement objects and dict format
            if hasattr(student_item, 'class_and_section'):
                student = student_item
            elif isinstance(student_item, dict) and 'student' in student_item:
                student = student_item['student']
            else:
                continue
            
            if student.class_and_section:
                class_name = student.class_and_section.class_and_section
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
    
    return class_counts


def get_unique_streams_by_role(user, students_queryset):
    """
    Get unique streams based on user role and the students they can see.
    Returns distinct stream values for the students in the queryset.
    
    Args:
        user: The User object (request.user)
        students_queryset: QuerySet of StudentManagement objects
    
    Returns:
        List of unique stream values (distinct, ordered, excluding None/empty)
    """
    if not students_queryset.exists() if hasattr(students_queryset, 'exists') else not students_queryset:
        return []
    
    # Get distinct streams from the students queryset
    if hasattr(students_queryset, 'values_list'):
        # QuerySet - use database distinct
        streams = students_queryset.filter(
            class_and_section__stream__isnull=False
        ).exclude(
            class_and_section__stream=''
        ).values_list(
            'class_and_section__stream', flat=True
        ).distinct().order_by('class_and_section__stream')
        return list(streams)
    else:
        # List - use Python set
        streams_set = set()
        for student_item in students_queryset:
            if hasattr(student_item, 'class_and_section'):
                student = student_item
            elif isinstance(student_item, dict) and 'student' in student_item:
                student = student_item['student']
            else:
                continue
            
            if student.class_and_section and student.class_and_section.stream:
                streams_set.add(student.class_and_section.stream)
        
        return sorted(list(streams_set))


def get_students_in_institute(counselor):
    """
    Fetch assigned students for a given counselor.
    Note: This function is kept for backward compatibility but now only returns assigned students.
    Use get_students_by_role() for new code.
    """
    if not counselor or not counselor.counselor_admin:
        return StudentManagement.objects.none(), StudentManagement.objects.none(), StudentManagement.objects.none()
    
    institute = counselor.counselor_admin
    all_institute_students = StudentManagement.objects.filter(institute=institute)
    
    # Get assigned students only
    assigned_students = counselor.get_students(institute=institute)
    assigned_student_ids = assigned_students.values_list('id', flat=True)
    unassigned_students = all_institute_students.exclude(id__in=assigned_student_ids)

    # Counselor should only see assigned students, not unassigned
    students_to_display = assigned_students
    return students_to_display, assigned_students, unassigned_students

def get_results_data_for_students(students):
    """Prepare results data for a list of students using the same logic as institute dashboard."""
    from app.models import TestCompletion, Results
    from app_post_matric.models import TestSession
    from institute.models import StudentManagement
    from django.urls import reverse
    import re
    
    results_data = {}
    
    for student_management in students:
        student = student_management.student  # Access the student related to StudentManagement
        
        try:
            # Check student's class to determine which system to use
            student_mgmt = StudentManagement.objects.filter(student=student).first()
            
            if student_mgmt and student_mgmt.class_and_section:
                class_name = student_mgmt.class_and_section.class_and_section
                
                # Extract class number
                class_number = None
                try:
                    numbers = re.findall(r'\d+', class_name)
                    if numbers:
                        class_number = int(numbers[0])
                except (ValueError, IndexError):
                    pass
                
                # Determine system based on class
                if class_number and class_number >= 11:
                    # Class 11-12: Use post-matric system
                    post_matric_sessions = TestSession.objects.filter(user=student)
                    student_result = _get_post_matric_test_result(student, post_matric_sessions)
                else:
                    # Class 10 and below: Use psychometric system
                    student_result = _get_psychometric_test_result(student)
            else:
                # No class information, default to psychometric system
                student_result = _get_psychometric_test_result(student)
                
        except Exception as e:
            print(f"Error getting test result for student {student}: {e}")
            student_result = {
                "test_success": False,
                "test_link": None,
                "success_count": 0,
                "test_status": "no_tests",
                "tooltip": "Error loading test data"
            }
        
        if student_result:
            results_data[student] = student_result
        else:
            # Default values if no result
            results_data[student] = {
                "test_success": False,
                "test_link": None,
                "success_count": 0,
                "test_status": "no_tests",
                "tooltip": "No tests taken"
            }
        
    return results_data


def _get_psychometric_test_result(user):
    """Handle psychometric students (class 1-10) using TestCompletion/Results."""
    from app.models import TestCompletion, Results
    from django.urls import reverse
    
    try:
        # Check TestCompletion first to determine if student has completed tests
        test_completion = None
        try:
            test_completion = TestCompletion.objects.get(user=user)
        except TestCompletion.DoesNotExist:
            # If no TestCompletion record exists, student hasn't taken any tests
            return {
                "streams": {},
                "test_success": False,
                "test_link": reverse('app:test_buttons'),
                "success_count": 0,
                "test_status": "no_tests",
                "test_details": {
                    "test1": False,
                    "test2": False,
                    "test3": False
                },
                "tooltip": "No tests taken"
            }
        
        # Get individual test completion status
        test1_complete = test_completion.test1_complete
        test2_complete = test_completion.test2_complete
        
        # Verify test3_complete - only True if ALL subtests are complete
        all_test3_subtests_complete = (
            test_completion.numerical_complete and
            test_completion.verbal_complete and
            test_completion.logical_complete and
            test_completion.emotional_complete and
            test_completion.machanical_complete and
            test_completion.language_complete and
            test_completion.spatial_complete
        )
        
        test3_complete = test_completion.test3_complete if all_test3_subtests_complete else False
        
        # Count completed tests
        completed_tests = sum([test1_complete, test2_complete, test3_complete])
        
        # Create detailed tooltip showing all test statuses
        completed_list = []
        not_completed_list = []
        
        if test1_complete:
            completed_list.append("Career Interest")
        else:
            not_completed_list.append("Career Interest")
            
        if test2_complete:
            completed_list.append("Intelligence")
        else:
            not_completed_list.append("Intelligence")
            
        if test3_complete:
            completed_list.append("Personality")
        else:
            not_completed_list.append("Personality")
        
        # Create detailed tooltip showing all test statuses
        tooltip_parts = []
        if completed_list:
            tooltip_parts.append(f"Completed: {', '.join(completed_list)}")
        if not_completed_list:
            tooltip_parts.append(f"Not completed: {', '.join(not_completed_list)}")
        tooltip = " | ".join(tooltip_parts)
        
        # Determine overall status
        if completed_tests == 0:
            test_status = "no_tests"
        elif completed_tests == 3:
            test_status = "completed"
        else:
            test_status = "in_progress"
        
        # Get test link - only provide link if all tests are completed
        test_link = None
        if test_status == "completed":
            results = Results.objects.filter(user=user)
            if results.exists():
                latest_result = results.last()
                test_link = latest_result.get_test_report_or_test_link(user) if latest_result else None
        
        return {
            "streams": {},
            "test_success": completed_tests > 0,
            "test_link": test_link,
            "success_count": completed_tests,
            "test_status": test_status,
            "test_details": {
                "test1": test1_complete,
                "test2": test2_complete,
                "test3": test3_complete
            },
            "tooltip": tooltip
        }
        
    except Exception as e:
        print(f"Error in _get_psychometric_test_result: {e}")
        return {
            "streams": {},
            "test_success": False,
            "test_link": None,
            "success_count": 0,
            "test_status": "no_tests",
            "test_details": {
                "test1": False,
                "test2": False,
                "test3": False
            },
            "tooltip": "Error loading test data"
        }


def _get_post_matric_test_result(user, test_sessions):
    """Handle post-matric students (class 11-12) using TestSession/TestResult."""
    from app_post_matric.models import TestSession
    from django.urls import reverse
    
    try:
        # Initialize test completion status for 4 tests
        test_completion = {
            1: False,  # Personality Assessment
            2: False,  # Motivation Assessment
            3: False,  # Career Interest Inventory  
            4: False   # Aptitude Assessment
        }
        
        # Check completed sessions
        completed_sessions = test_sessions.filter(is_completed=True)
        for session in completed_sessions:
            test_id = session.test.id
            if test_id in test_completion:
                test_completion[test_id] = True
        
        # Count completed tests
        completed_tests = sum(test_completion.values())
        
        # Determine overall status and create detailed tooltip
        completed_list = []
        not_completed_list = []
        
        if test_completion[1]:
            completed_list.append("Personality")
        else:
            not_completed_list.append("Personality")
            
        if test_completion[2]:
            completed_list.append("Motivation")
        else:
            not_completed_list.append("Motivation")
            
        if test_completion[3]:
            completed_list.append("Career Interest")
        else:
            not_completed_list.append("Career Interest")
            
        if test_completion[4]:
            completed_list.append("Aptitude")
        else:
            not_completed_list.append("Aptitude")
        
        # Create detailed tooltip showing all test statuses
        tooltip_parts = []
        if completed_list:
            tooltip_parts.append(f"Completed: {', '.join(completed_list)}")
        if not_completed_list:
            tooltip_parts.append(f"Not completed: {', '.join(not_completed_list)}")
        tooltip = " | ".join(tooltip_parts)
        
        # Determine overall status
        if completed_tests == 0:
            test_status = "no_tests"
        elif completed_tests == 4:
            test_status = "completed"
        else:
            test_status = "in_progress"
        
        # Get test link - only provide link if all tests are completed
        test_link = None
        if test_status == "completed":
            test_link = reverse('post_matric:combined_report', args=[user.id])
        
        return {
            "streams": {},
            "test_success": completed_tests > 0,
            "test_link": test_link,
            "success_count": completed_tests,
            "test_status": test_status,
            "test_details": {
                "test1": test_completion[1],
                "test2": test_completion[2],
                "test3": test_completion[3],
                "test4": test_completion[4]
            },
            "tooltip": tooltip
        }
            
    except Exception as e:
        print(f"Error in _get_post_matric_test_result: {e}")
        return {
            "streams": {},
            "test_success": False,
            "test_link": None,
            "success_count": 0,
            "test_status": "no_tests",
            "test_details": {
                "test1": False,
                "test2": False,
                "test3": False,
                "test4": False
            },
            "tooltip": "Error loading test data"
        }


import logging
logger = logging.getLogger(__name__)



@login_required(login_url=reverse_lazy('users:login'))

def Students_follow_up(request, coun_id):
    from core import choices
    from django.http import Http404
    
    # Get the counselor and institute details
    counselor = get_object_or_404(Counselor, id=coun_id)
    
    # Security check: Ensure counselors can only access their own follow-up page
    if request.user.user_type == choices.UserType.COUNSELOR:
        # If user is a counselor, they must be the owner of this counselor record
        if counselor.coun_user != request.user:
            raise Http404("You don't have permission to access this counselor's follow-up page.")
    
    # Get counselor's associated institute
    counselor_institute = counselor.counselor_admin
    
    # Use centralized role-based function to get students - ALL students from counselor's institute (if associated)
    # Pass both counselor and institute to ensure correct filtering regardless of logged-in user's role
    students_to_display = get_students_by_role(request.user, counselor=counselor, institute=counselor_institute)
    
    # Get assigned student IDs separately for follow-up filtering
    # Follow-ups should only be shown for students actually assigned to this counselor
    if counselor.counselor_admin:
        # Get students assigned to this counselor from their institute
        assigned_students = counselor.get_students(institute=counselor.counselor_admin)
        assigned_student_ids = assigned_students.values_list('id', flat=True) if hasattr(assigned_students, 'values_list') else [s.id for s in assigned_students]
    else:
        # If no institute, get assigned students (though this might be empty)
        assigned_students = counselor.students.filter(institute__isnull=True)
        assigned_student_ids = assigned_students.values_list('id', flat=True) if hasattr(assigned_students, 'values_list') else [s.id for s in assigned_students]
    
    # Initialize follow_up_data as an empty list
    follow_up_data = []

    if request.method == 'POST':
        # Retrieve the student ID from the form
        student_id = request.POST.get('student_id')
        if student_id:
            logger.debug(f"Received student ID: {student_id}")
            try:
                # Only allow creating follow-ups for assigned students
                student_management_instance = assigned_students.get(id=student_id)
            except StudentManagement.DoesNotExist:
                logger.warning("Student not found or not assigned to counselor.")
                messages.error(request, 'Selected student is not assigned to you.')
                return redirect('counselor:Counselor_follow_up_page', coun_id=coun_id)

            # Create or update the follow-up instance
            follow_up_instance, created = FollowUpStatus.objects.update_or_create(
                counselor=counselor,
                student=student_management_instance,
                defaults={
                    'mode_of_follow_up': request.POST.get('mode_of_follow_up'),
                    'follow_up_status': request.POST.get('follow_up_status'),
                    'last_follow_up_date': request.POST.get('last_follow_up_date'),
                    'next_follow_up_date': request.POST.get('next_follow_up_date'),
                    'message': request.POST.get('message'),
                    'is_followed_up': request.POST.get('is_followed_up') == 'on'
                }
            )

            if not created:
                follow_up_instance.mode_of_follow_up = request.POST.get('mode_of_follow_up')
                follow_up_instance.follow_up_status = request.POST.get('follow_up_status')
                follow_up_instance.last_follow_up_date = request.POST.get('last_follow_up_date')
                follow_up_instance.next_follow_up_date = request.POST.get('next_follow_up_date')
                follow_up_instance.message = request.POST.get('message')
                follow_up_instance.is_followed_up = request.POST.get('is_followed_up') == 'on'
                follow_up_instance.save()

            logger.debug("Follow-up entry saved successfully.")
            messages.success(request, 'Follow-up created successfully!')
            return redirect('counselor:Counselor_follow_up_page', coun_id=coun_id)
        else:
            logger.warning("No student ID provided.")

    # Retrieve follow-up data only for assigned students
    follow_ups = FollowUpStatus.objects.filter(
        counselor=counselor,
        student_id__in=assigned_student_ids
    ).select_related('student', 'student__student')
    
    # Create a dictionary to hold follow-up data by student ID
    follow_up_data = {}
    total_is_followed_up_count = 0
    
    for follow_up in follow_ups:
        if follow_up.student.id not in follow_up_data:
            follow_up_data[follow_up.student.id] = {
                'follow_ups': []
            }
        follow_up_data[follow_up.student.id]['follow_ups'].append({
            'is_followed_up': follow_up.is_followed_up,
            'message': follow_up.message,
            'last_follow_up_date': follow_up.last_follow_up_date,
            'next_follow_up_date': follow_up.next_follow_up_date,
        })
        
        # Increment the count if this follow-up is marked as followed up
        if follow_up.is_followed_up:
            total_is_followed_up_count += 1

    # Merging the data
    merged_data = []
    for student in students_to_display:
        student_info = {
            'student': student,
            'follow_ups': follow_up_data.get(student.id, {'follow_ups': []})['follow_ups'],
        }
        merged_data.append(student_info)

    # Sorting merged data
    merged_data = sorted(merged_data, key=lambda x: x['student'].student.name.lower())
    
    # Apply filters using centralized function (no test_taken filter in follow-up page)
    merged_data = apply_student_filters(merged_data, request, results_data=None)

    
    # Setting up pagination
    paginator = Paginator(merged_data, 10)  # 10 students per page
    page_number = request.GET.get('page')
    students_page = paginator.get_page(page_number)

    # Get class counts for display in dropdown using centralized function
    class_counts = get_class_counts(students_to_display)

    # Render context
    context = {
        'counselors': counselor,
        'students': students_page,
        'class_and_sections': get_class_and_sections_by_role(request.user, students_to_display),
        'class_counts': class_counts,  # Add class counts for dropdown
        'students_count': students_to_display,
        'total_is_followed_up_count': total_is_followed_up_count,
        'coun_id' : coun_id
    }

    return render(request, 'template20/counselor/follow_up_page.html', context)

def CounselorCoursepayment(request):
    from django.conf import settings
    import razorpay
    client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
    data = { "amount": 500*100, "currency": "INR", "receipt": "order_rcptid_11" }
    payment = client.order.create(data=data)
    context = {
        'key': settings.RAZORPAY_API_KEY,
        'payment': payment
    }
    return render(request, 'template20/counselor/course_payment.html', context)
def display_pdfs(request):
    return render(request, 'template20/counselor/display_pdfs.html')

@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class CourseStartsView(View):
    def get(self, request, counselor_id):
        from core import choices
        from django.http import Http404
        
        # Retrieve the counselor using the provided ID
        counselor = get_object_or_404(Counselor, id=counselor_id)
        
        # Security check: Ensure counselors can only access their own course
        if request.user.user_type == choices.UserType.COUNSELOR:
            # If user is a counselor, they must be the owner of this counselor record
            if counselor.coun_user != request.user:
                raise Http404("You don't have permission to access this counselor's course.")
        
        user = request.user
        course_with_related_data = CounselorCourse.objects.prefetch_related(
                'chapters__parts__quizzes__questions__answers'
            ).first()

        part_ids = course_with_related_data.chapters.all().values_list('parts__id', flat=True)
        progress_data = VideoProgress.objects.filter(user=user, video_id__in=[f"video-{part_id}" for part_id in part_ids])
        video_progress = {int(progress.video_id.split('-')[1]): progress.completed for progress in progress_data}

        last_part = Part.objects.filter(chapter__course=course_with_related_data).last()

        completed_parts = sum(1 for completed in video_progress.values() if completed)

        # Initialize counts
        chapter_count = 0
        part_count = 0
        question_count = 0

        if course_with_related_data:
            # Count chapters, parts, and questions
            chapter_count = course_with_related_data.chapters.count()
            for chapter in course_with_related_data.chapters.all():
                part_count += chapter.parts.count()
                for part in chapter.parts.all():
                    question_count += part.quizzes.values('questions').count()  # Count questions in quizzes

        # Print the counts
        progress_percentage = int((completed_parts / part_count * 100)) if part_count > 0 else 0
        # Prepare the context for the template

        

        context = {
            'counselors': counselor,
            'course': course_with_related_data,
            'chapter_count': chapter_count,
            'part_count': part_count,
            'question_count': question_count,
            'video_progress':video_progress,
            'last':last_part,
            'progress_percentage':progress_percentage,
            # Add other context variables as needed
        }

        # Render the template with the context
        return render(request, 'template20/counselor/course_information.html', context)

# @csrf_exempt  # Use this only if you need to bypass CSRF verification for testing. Not recommended for production.
def Counselorenrolledcourse(request):
    if request.method == 'POST':
        results = {}

        # Loop through each part in the submitted data
        for part_id in request.POST.getlist('part_id'):
            part = get_object_or_404(Part, id=part_id)
            results[part.id] = {
                'quiz_results': [],  # List to hold results for quizzes in this part
                'correct_count': 0,
                'incorrect_count': 0,
            }

            for quiz in part.quizzes.all():
                total_questions_each_quiz = quiz.questions.all().count()
                correct_answers_map = {}

                for question in quiz.questions.all():
                    user_answer_id = request.POST.get(f'question_{question.id}')
                    user_answer = None

                    if user_answer_id:
                        try:
                            user_answer = QuizAnswers.objects.get(id=user_answer_id)
                        except QuizAnswers.DoesNotExist:
                            pass

                    correct_answer = question.answers.filter(is_correct=True).first()
                    is_correct = user_answer == correct_answer if user_answer else False

                    # Increment counts based on whether the answer is correct
                    if is_correct:
                        results[part.id]['correct_count'] += 1
                    else:
                        results[part.id]['incorrect_count'] += 1
                    
                    # Fill correct_option based on user and correct answers
                    correct_answers_map[f'ques_{question.id}'] = {
                        'correct_ans': correct_answer.answer_text if correct_answer else None,
                        'selected_ans': user_answer.answer_text if user_answer else None,
                    }

                results[part.id]['quiz_results'].append({
                    'quiz_id': quiz.id,
                    'total_questions_in_quiz': total_questions_each_quiz,
                    'correct_option': correct_answers_map,
                    'quiz_result': {
                        'correct_answers': results[part.id]['correct_count'],
                        'incorrect_answers': results[part.id]['incorrect_count'],
                    }
                })

        # Prepare final data structure
        data = {
            "userId": request.user.id,
            "scores": []
        }

        for part_id, part_results in results.items():
            for quiz in part_results['quiz_results']:
                score_info = {
                    "part_id": part_id,
                    "quiz_id": quiz["quiz_id"],
                    "total_questions_in_quiz": quiz["total_questions_in_quiz"],
                    "correct_option": quiz["correct_option"],
                    "quiz_result": {
                        "correct_answers": quiz['quiz_result']['correct_answers'],
                        "incorrect_answers": quiz['quiz_result']['incorrect_answers'],
                    },
                }
                data['scores'].append(score_info)
        # Convert the dictionary to a JSON string

       
        json_data = json.dumps(data, indent=4)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get the existing QuizResults instance for the user
        user = get_object_or_404(User, id=data['userId'])
        quiz_results, created = QuizResults.objects.get_or_create(user=user)
     
        new_score_data = data["scores"]  # Directly use 'data' as it is a list of score data

        # Ensure scores is a list before modifying it
        if isinstance(quiz_results.scores, str):
            # If 'scores' is a string (e.g., JSON string), load it as a list
            quiz_results.scores = json.loads(quiz_results.scores)
        elif not isinstance(quiz_results.scores, list):
            # If it's neither a string nor a list, initialize it as an empty list
            quiz_results.scores = []

        # Loop through each new score in the data
        for new_score in new_score_data:
            part_id = new_score["part_id"]
            quiz_id = new_score["quiz_id"]
            # Check if the part_id and quiz_id exist in the current scores
            existing_score = None
            for score in quiz_results.scores:
                if score["part_id"] == part_id and score["quiz_id"] == quiz_id:
                    existing_score = score
                    break

            if existing_score:
                # If the score data exists, update it with the new data
                existing_score.update(new_score)
            else:
                # If no matching part_id and quiz_id, append the new data
                quiz_results.scores.append(new_score)  # Append new_score instead of new_score_data

        # Save the updated data
        
        quiz_results.save()
        return render(request, 'results.html', {'json_data': json_data})

    try:
        # Prefetch parts, their quizzes, questions, and answers
        chapters = Chapter.objects.prefetch_related(
            'parts__quizzes__questions__answers'
        ).all()
    except Chapter.DoesNotExist:
        chapters = []

    context = {
        'chapters': chapters
    }

    return render(request, 'topteenfrontend/user/app/counselor-enrolled-course.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def CounselorDashboard(request, coun_id=None):
    from core import choices
    from django.http import Http404, JsonResponse
    
    counselor = get_object_or_404(Counselor, id=coun_id)
    
    # Security check: Ensure counselors can only access their own dashboard
    if request.user.user_type == choices.UserType.COUNSELOR:
        # If user is a counselor, they must be the owner of this counselor record
        if counselor.coun_user != request.user:
            raise Http404("You don't have permission to access this counselor's dashboard.")
    
    # Check if this is an AJAX request for specific data
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data_type = request.GET.get('data_type', '')
        
        if data_type == 'students':
            # Optimized AJAX handler for student table only
            return _get_counselor_student_table_ajax(request, counselor, coun_id)
        elif data_type == 'stats':
            # AJAX handler for statistics
            return _get_counselor_stats_ajax(counselor)
        elif data_type == 'sessions':
            # AJAX handler for session chart data
            return _get_counselor_sessions_ajax(counselor, coun_id)
    
    # Get counselor's associated institute
    counselor_institute = counselor.counselor_admin
    
    # Lightweight initial page load - only essential data
    # Use optimized queries with select_related and prefetch_related
    # Pass both counselor and institute to ensure correct filtering regardless of logged-in user's role
    # This returns ONLY assigned students (matching production code)
    students_to_display = get_students_by_role(request.user, counselor=counselor, institute=counselor_institute)
    
    # Get assigned student IDs for follow-up filtering (students_to_display already contains assigned students)
    assigned_student_ids = students_to_display.values_list('id', flat=True) if hasattr(students_to_display, 'values_list') else [s.id for s in students_to_display]
    
    # Retrieve follow-up data for assigned students (matching production code - filter only by counselor)
    follow_ups = FollowUpStatus.objects.filter(
        counselor=counselor,
        student_id__in=assigned_student_ids
    ).select_related('student', 'student__student')
    
    # Get basic counts efficiently - only for assigned students
    total_is_followed_up_count = follow_ups.filter(is_followed_up=True).count()
    
    # Get class counts and sections efficiently (only for filters)
    class_and_sections = get_class_and_sections_by_role(request.user, students_to_display)
    class_counts = get_class_counts(students_to_display)
    unique_streams = get_unique_streams_by_role(request.user, students_to_display)
    
    # For initial load, only get minimal data needed for filters
    # Heavy processing (results_data, merged_data) will be done via AJAX
    per_page = request.GET.get('per_page', '10')
    
    # Initialize lightweight context for initial page load
    context = {
        'counselors': counselor,
        'coun_id': coun_id,
        'counselor_institute': counselor_institute,  # Add institute to context for verification
        'per_page': per_page,
        'class_and_sections': class_and_sections,
        'class_counts': class_counts,
        'unique_streams': unique_streams,
        'total_is_followed_up_count': total_is_followed_up_count,
        'students_count': students_to_display.count() if hasattr(students_to_display, 'count') else len(students_to_display),
        'key': settings.RAZORPAY_API_KEY,
        'secrit': settings.RAZORPAY_API_SECRET,
    }
    
    # Only load student table data if explicitly requested (not on initial page load)
    # This will be loaded via AJAX after page loads
    if request.GET.get('load_table', 'false') == 'true':
        # Load full table data
        context.update(_get_counselor_full_table_context(request, counselor, students_to_display, follow_ups, per_page))
    
    return render(request, 'template20/counselor/counselor_dashboard.html', context)


def _get_counselor_student_table_ajax(request, counselor, coun_id):
    """Optimized AJAX handler for student table with pagination."""
    from django.core.paginator import Paginator
    
    # Get counselor's associated institute
    counselor_institute = counselor.counselor_admin
    
    # Get students with optimized query - ONLY assigned students (matching production code)
    # Pass both counselor and institute to ensure correct filtering regardless of logged-in user's role
    students_to_display = get_students_by_role(request.user, counselor=counselor, institute=counselor_institute)
    
    # Get assigned student IDs for follow-up filtering (students_to_display already contains assigned students)
    assigned_student_ids = students_to_display.values_list('id', flat=True) if hasattr(students_to_display, 'values_list') else [s.id for s in students_to_display]
    
    # Retrieve follow-up data for assigned students (matching production code - filter only by counselor)
    follow_ups = FollowUpStatus.objects.filter(
        counselor=counselor,
        student_id__in=assigned_student_ids
    ).select_related('student', 'student__student')
    
    # Build follow_up_data efficiently
    follow_up_data = {}
    for follow_up in follow_ups:
        student_id = follow_up.student.id
        if student_id not in follow_up_data:
            follow_up_data[student_id] = {'follow_ups': []}
        follow_up_data[student_id]['follow_ups'].append({
            'is_followed_up': follow_up.is_followed_up,
            'message': follow_up.message,
            'last_follow_up_date': follow_up.last_follow_up_date,
            'next_follow_up_date': follow_up.next_follow_up_date,
        })
    
    # Build merged_data only for current page
    merged_data = []
    for student in students_to_display:
        merged_data.append({
            'student': student,
            'follow_ups': follow_up_data.get(student.id, {'follow_ups': []})['follow_ups'],
        })
    
    # Sort only once
    merged_data = sorted(merged_data, key=lambda x: x['student'].student.name.lower())
    
    # Get results_data only for filtered students (optimize this)
    # Limit to first 100 students for results_data to avoid N+1
    students_for_results = students_to_display[:100] if hasattr(students_to_display, '__getitem__') else list(students_to_display)[:100]
    results_data = get_results_data_for_students(students_for_results)
    
    # Apply filters
    merged_data = apply_student_filters(merged_data, request, results_data)
    
    # Pagination
    per_page = request.GET.get('per_page', '10')
    if per_page == 'all':
        students_page = merged_data
        paginator = None
    else:
        try:
            per_page_int = int(per_page)
            if per_page_int not in [10, 100]:
                per_page_int = 10
        except (ValueError, TypeError):
            per_page_int = 10
        
        paginator = Paginator(merged_data, per_page_int)
        page_number = request.GET.get('page', 1)
        students_page = paginator.get_page(page_number)
    
    # Get class counts and sections for filters
    class_and_sections = get_class_and_sections_by_role(request.user, students_to_display)
    class_counts = get_class_counts(students_to_display)
    unique_streams = get_unique_streams_by_role(request.user, students_to_display)
    
    context = {
        'counselors': counselor,
        'students': students_page,
        'paginator': paginator,
        'per_page': per_page,
        'results_data': results_data,
        'class_and_sections': class_and_sections,
        'class_counts': class_counts,
        'unique_streams': unique_streams,
        'coun_id': coun_id,
        'follow_up_data': follow_up_data,
        'merged_data': merged_data,
    }
    
    return render(request, 'template20/counselor/counselor_dashboard_table.html', context)


def _get_counselor_stats_ajax(counselor):
    """AJAX handler for statistics."""
    # Get counselor's associated institute
    counselor_institute = counselor.counselor_admin
    
    # Get ONLY assigned students (matching production code)
    # Pass both counselor and institute to ensure correct filtering regardless of logged-in user's role
    students_to_display = get_students_by_role(counselor.coun_user, counselor=counselor, institute=counselor_institute)
    
    # Get assigned student IDs for follow-up filtering (students_to_display already contains assigned students)
    assigned_student_ids = students_to_display.values_list('id', flat=True) if hasattr(students_to_display, 'values_list') else [s.id for s in students_to_display]
    
    # Count follow-ups only for assigned students (matching production code - filter only by counselor)
    total_is_followed_up_count = FollowUpStatus.objects.filter(
        counselor=counselor,
        student_id__in=assigned_student_ids,
        is_followed_up=True
    ).count()
    
    # Count counseled students (follow_up_status='completed') only for assigned students
    counseled_count = FollowUpStatus.objects.filter(
        counselor=counselor,
        student_id__in=assigned_student_ids,
        follow_up_status='completed'
    ).values('student_id').distinct().count()
    
    return JsonResponse({
        'total_students': students_to_display.count() if hasattr(students_to_display, 'count') else len(students_to_display),
        'total_followed_up': total_is_followed_up_count,
        'total_counseled': counseled_count,
    })


def _get_counselor_sessions_ajax(counselor, coun_id):
    """AJAX handler for session chart data."""
    from django.db.models import Count
    
    # Get counselor's associated institute
    counselor_institute = counselor.counselor_admin
    
    # Get ONLY assigned students (matching production code)
    # Pass both counselor and institute to ensure correct filtering regardless of logged-in user's role
    students_to_display = get_students_by_role(counselor.coun_user, counselor=counselor, institute=counselor_institute)
    
    # Get assigned student IDs for session filtering (students_to_display already contains assigned students)
    assigned_student_ids = students_to_display.values_list('id', flat=True) if hasattr(students_to_display, 'values_list') else [s.id for s in students_to_display]
    
    # Filter sessions only for assigned students (matching production code - filter only by counselor)
    sessions_data = (
        FollowUpStatus.objects
        .filter(counselor_id=coun_id, student_id__in=assigned_student_ids)
        .values('last_follow_up_date')
        .annotate(session_count=Count('id'))
    )
    
    week_data = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    reference_date = date.today()
    
    for session in sessions_data:
        try:
            session_date = session.get('last_follow_up_date')
            if session_date:
                if isinstance(session_date, str):
                    if 'T' in session_date:
                        session_date = datetime.fromisoformat(session_date.split('T')[0]).date()
                    else:
                        session_date = datetime.strptime(session_date, "%Y-%m-%d").date()
                
                day_of_week = session_date.weekday()
                if day_of_week < 6:
                    week_data[day_of_week] += session.get('session_count', 0)
        except (KeyError, ValueError, TypeError):
            continue
    
    days_since_monday = reference_date.weekday()
    week_start = reference_date - timedelta(days=days_since_monday)
    
    final_data = []
    for day, count in week_data.items():
        day_date = week_start + timedelta(days=day)
        final_data.append({
            "day": day_date.strftime("%Y-%m-%d"),
            "session_count": count
        })
    
    couns_sessions_data = [{
        'counselor_id': counselor.id,
        'counselor_name': counselor.counselor_name,
        'sessions': final_data
    }]
    
    return JsonResponse({'sessions_data': couns_sessions_data})


def _get_counselor_full_table_context(request, counselor, students_to_display, follow_ups, per_page):
    """Get full table context - used only when explicitly needed."""
    # This is the old heavy processing logic, but only called when needed
    follow_up_data = {}
    total_is_followed_up_count = 0
    
    for follow_up in follow_ups:
        if follow_up.student.id not in follow_up_data:
            follow_up_data[follow_up.student.id] = {'follow_ups': []}
        follow_up_data[follow_up.student.id]['follow_ups'].append({
            'is_followed_up': follow_up.is_followed_up,
            'message': follow_up.message,
            'last_follow_up_date': follow_up.last_follow_up_date,
            'next_follow_up_date': follow_up.next_follow_up_date,
        })
        if follow_up.is_followed_up:
            total_is_followed_up_count += 1
    
    merged_data = []
    for student in students_to_display:
        merged_data.append({
            'student': student,
            'follow_ups': follow_up_data.get(student.id, {'follow_ups': []})['follow_ups'],
        })
    
    merged_data = sorted(merged_data, key=lambda x: x['student'].student.name.lower())
    
    # Limit results_data processing
    students_for_results = students_to_display[:100] if hasattr(students_to_display, '__getitem__') else list(students_to_display)[:100]
    results_data = get_results_data_for_students(students_for_results)
    merged_data = apply_student_filters(merged_data, request, results_data)
    
    # Pagination
    if per_page == 'all':
        students_page = merged_data
        paginator = None
    else:
        try:
            per_page_int = int(per_page)
            if per_page_int not in [10, 100]:
                per_page_int = 10
        except (ValueError, TypeError):
            per_page_int = 10
        
        paginator = Paginator(merged_data, per_page_int)
        page_number = request.GET.get('page', 1)
        students_page = paginator.get_page(page_number)
    
    return {
        'students': students_page,
        'paginator': paginator,
        'results_data': results_data,
        'total_is_followed_up_count': total_is_followed_up_count,
        'follow_up_data': follow_up_data,
        'merged_data': merged_data,
    }


# @login_required(login_url=reverse_lazy('users:login'))
class CounselorEnrolledCourseView(View):
    template_name = 'template20/counselor/enrolled_course.html'

    def post(self, request, *args, **kwargs):        

        results = {}
        # Ensure part_id is being processed correctly
        for part_id in request.POST.getlist('part_id'):
            part = get_object_or_404(Part, id=part_id)
            results[part.id] = {'quiz_results': [], 'correct_count': 0, 'incorrect_count': 0}
        
            for quiz in part.quizzes.all():
                total_questions_each_quiz = quiz.questions.count()
                correct_answers_map = {}

                for question in quiz.questions.all():
                    user_answer_id = request.POST.get(f'question_{question.id}')

                    user_answer = None
                    if user_answer_id:
                        try:
                            user_answer = QuizAnswers.objects.get(id=user_answer_id)
                        except QuizAnswers.DoesNotExist:
                            pass
                    
                    correct_answer = question.answers.filter(is_correct=True).first()
                    is_correct = user_answer == correct_answer if user_answer else False
                    if is_correct:
                        results[part.id]['correct_count'] += 1
                    else:
                        results[part.id]['incorrect_count'] += 1
                    
                    # Fill correct_option based on user and correct answers
                    correct_answers_map[f'ques_{question.id}'] = {
                        'correct_ans': correct_answer.answer_text if correct_answer else None,
                        'selected_ans': user_answer.answer_text if user_answer else None,
                    }


                results[part.id]['quiz_results'].append({
                    'quiz_id': quiz.id,
                    'total_questions_in_quiz': total_questions_each_quiz,
                    'correct_option': correct_answers_map,
                    'quiz_result': {
                        'correct_answers': results[part.id]['correct_count'],
                        'incorrect_answers': results[part.id]['incorrect_count'],
                    }
                })

        # Prepare final data structure
        data = {
            "userId": request.user.id,
            "scores": []
        }
        
        for part_id, part_results in results.items():
            for quiz in part_results['quiz_results']:
                score_info = {
                    "part_id": part_id,
                    "quiz_id": quiz["quiz_id"],
                    "total_questions_in_quiz": quiz["total_questions_in_quiz"],
                    "correct_option": quiz["correct_option"],
                    "quiz_result": {
                        "correct_answers": quiz['quiz_result']['correct_answers'],
                        "incorrect_answers": quiz['quiz_result']['incorrect_answers'],
                    },
                }
                data['scores'].append(score_info)
                
        user = get_object_or_404(User, id=data['userId'])
        quiz_results, created = QuizResults.objects.update_or_create(user=user)
        if isinstance(quiz_results.scores, str) or not isinstance(quiz_results.scores, list):
            quiz_results.scores = []
        for new_score in data["scores"]:
            part_id = new_score["part_id"]
            quiz_id = new_score["quiz_id"]
            existing_score = next((score for score in quiz_results.scores if score["part_id"] == part_id and score["quiz_id"] == quiz_id), None)

            
            if existing_score:
                existing_score.update(new_score)
                messages.success(request, "Thank you! Successfully updated data into db.")
            else:
                quiz_results.scores.append(new_score)
                messages.success(request, "Thank you! Successfully created data into db.")

        
        # Save the updated data
        quiz_results.save()
        # url = request.META.get('HTTP_REFERER'){{url ('counselor:counselor_enrolled_course')}}
        
        return redirect('counselor:counselor_enrolled_course')
    
    def get(self, request, *args, **kwargs):
        try:
            # Prefetch parts, their quizzes, questions, and answers
            course_with_related_data = CounselorCourse.objects.prefetch_related(
                'chapters__parts__quizzes__questions__answers'
            ).first()

            # chapter = Chapter.objects.prefetch_related('parts').get(id=chapter_id)
            user = request.user

            # Prepare progress data
            # Prepare video progress
            video_progress = self.get_completed_status(user, course_with_related_data)

            # Fetch the last part based on its ID
            # c = Part.objects.last()

            # Get the last part of the course
            last_part = Part.objects.filter(chapter__course=course_with_related_data).last()

            certification = CounselorCertification.objects.filter(user=request.user).first()  # Assuming one certification per user
            if certification:
                # If a certificate already exists for the user, use the existing code
                certificate_code = certification.certificate_code
            else:
                # Generate a new certificate code
                latest_cert = CounselorCertification.objects.last()
                if latest_cert:
                    certificate_code = f"TPTC{latest_cert.id + 1:04d}"  # Increment last id by 1
                else:
                    certificate_code = "TPTC0001"         

            # Access the last part's details
            if last_part:
                # Check if video progress for the last part exists and is True
                if video_progress.get(last_part.id, False):  # Assuming last_part.id is used as last_id
                    try:

                        quiz_result = QuizResults.objects.get(user=request.user)
                        scores = quiz_result.scores if isinstance(quiz_result.scores, list) else []

                        # Initialize counters
                        total_questions = 0
                        total_correct_answers = 0

                        # Iterate through each quiz result
                        for quiz in scores:
                            total_questions += quiz.get("total_questions_in_quiz", 0)
                            total_correct_answers += quiz.get("quiz_result", {}).get("correct_answers", 0)

                        # Calculate score percentage
                        if total_questions > 0:
                            score_percentage = (total_correct_answers / total_questions) * 100
                        else:
                            score_percentage = 0

                        # Determine the grade based on the score percentage
                        if score_percentage >= 80:
                            grade = "A+"
                        elif score_percentage >= 70:
                            grade = "A"
                        elif score_percentage >= 60:
                            grade = "B+"
                        elif score_percentage >= 50:
                            grade = "B"
                        elif score_percentage >= 40:
                            grade = "C"
                        else:
                            grade = "D"  # Fail or below 50%

                        certification, created = CounselorCertification.objects.update_or_create(
                            user=user,
                            grade=grade,  # Fields to identify the record
                            defaults={  # Fields to update or create with
                                'certificate_code': certificate_code,
                            }
                        )

                        if created:
                            print("A new certification record was created.")
                        else:
                            print("An existing certification record was updated.")

                        # Output the results (for debugging purposes)
                        

                    except QuizResults.DoesNotExist:
                        print("No quiz results found for this user.")
                else:
                    print("Video progress for this part is not completed or doesn't exist.")

            else:
                print("No parts found for the course.")

            # video_progress = VideoProgress.objects.filter(user=request.user)
            notes = Notes.objects.filter(user=request.user)
        except Chapter.DoesNotExist:
            course_with_related_data = []
            notes = []
            video_progress = []
            last_part = []
            certification = []

        try: 

            quiz_result = QuizResults.objects.get(user=user)
            scores = quiz_result.scores if isinstance(quiz_result.scores, list) else []

            found = {}
            answers_data = {}  # To store correct and incorrect counts for each part
            correct_selected = {}
            correct_ans_selected={}

            for chapter in course_with_related_data.chapters.all():
                
                for part in chapter.parts.all():
                    part_scores = [score for score in scores if score.get('part_id') == part.id]

                    # Extract correct and incorrect counts from the scores
                    correct_count = sum(score['quiz_result']['correct_answers'] for score in part_scores)
                    incorrect_count = sum(score['quiz_result']['incorrect_answers'] for score in part_scores)
                    found[part.id] = bool(part_scores)  # Mark as found if there are scores for this part
                    answers_data[part.id] = {
                        'correct': correct_count,
                        'incorrect': incorrect_count
                    }
                    
                    # Lists to hold correct and incorrect answers
                    correct_answers = []
                    incorrect_answers = []

                    # Loop through the scores
                    for quiz in scores:
                        part_id = quiz['part_id']
                        for question_key, question_data in quiz['correct_option'].items():
                            selected_answer = question_data['selected_ans'] # Or question_data['answer_text'] if you have the text
                            correct_selected.setdefault(part_id, {})[question_key] = selected_answer

                            correct_ans = question_data['correct_ans'] # Or question_data['answer_text'] if you have the text
                            correct_ans_selected.setdefault(part_id, {})[question_key] = correct_ans

                            # if selected_answer == correct_answer:
                            #     correct_answers.append((part_id, question_key, correct_answer, selected_answer))
                            # else:
                            #     incorrect_answers.append((part_id, question_key, correct_answer, selected_answer))
            print("answers_data ",answers_data)
            print("correct_selected ",correct_selected)
            print("correct_ans_selected ",correct_ans_selected)
            print("found",found)
        except QuizResults.DoesNotExist:
            scores = []
            found = {}
            answers_data = {}
            part_scores = []
            correct_answers = []
            incorrect_answers = []
            correct_selected = []
            correct_ans_selected =[]

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            scores = []
            found = {}
            answers_data = {}
            part_scores = []
            correct_answers = []
            incorrect_answers = []
            correct_selected = []
            correct_ans_selected =[]
        
        

        context = {
            'user': '336',
            'notes':notes,
            'last':last_part,
            'video_progress':video_progress,
            'course': course_with_related_data,
            'certification':certification,
            'scores':scores,
            'found' : found,
            'answers_data': answers_data,
            'part_scores': part_scores,
            'correct_answers':correct_answers,
            'incorrect_answers':incorrect_answers,
            'correct_selected':correct_selected,
            'correct_ans_selected':correct_ans_selected,
        }

        return render(request, self.template_name, context)

    @staticmethod
    def get_completed_status(user, course):
        """
        Retrieve the `completed` status for all parts in the course for the given user.
        """
        part_ids = course.chapters.all().values_list('parts__id', flat=True)
        progress_data = VideoProgress.objects.filter(user=user, video_id__in=[f"video-{part_id}" for part_id in part_ids])
        video_progress = {int(progress.video_id.split('-')[1]): progress.completed for progress in progress_data}
        return video_progress



import traceback
from django.utils.decorators import method_decorator
from django.middleware.csrf import get_token
# <-- testing the form submission with the ajax-->
from django.views.decorators.csrf import csrf_protect
@csrf_protect

@csrf_exempt
def get_progress_and_duration(request, video_id):
    if request.method == 'GET':
        try:
            # Ensure the user is authenticated
            user = request.user
            if not user.is_authenticated:
                return JsonResponse({'status': 'fail', 'error': 'User not authenticated'}, status=403)

            # Retrieve the progress and duration for the specific user and video
            video_progress = VideoProgress.objects.filter(user=user, video_id=video_id).first()

            if video_progress:
                progress_data = {
                    'progress': video_progress.progress,
                    'duration': video_progress.duration
                }
                return JsonResponse({'status': 'success', **progress_data}, status=200)
            else:
                return JsonResponse({'status': 'fail', 'error': 'Video progress not found'}, status=404)

        except Exception as e:
            logger.error(f"Error retrieving video progress: {e}")
            return JsonResponse({'status': 'fail', 'error': str(e)}, status=500)

    return JsonResponse({'status': 'fail', 'error': 'Invalid request method'}, status=400)


@csrf_exempt
def update_progress(request):
    if request.method == 'POST':
        try:            
            data = json.loads(request.body)
            video_id = data.get('video_id')
            progress = data.get('progress')
            duration = data.get('duration')

            # Ensure user is authenticated
            user = request.user
            if not user.is_authenticated:
                return JsonResponse({'status': 'fail', 'error': 'User not authenticated'}, status=403)

            # Validate input data
            if video_id is None or progress is None:
                return JsonResponse({'status': 'fail', 'error': 'Missing video_id or progress'}, status=400)

            if not isinstance(progress, (int, float)) or progress < 0 or progress > 100:
                return JsonResponse({'status': 'fail', 'error': 'Progress must be a number between 0 and 100'}, status=400)

            # Update or create progress record
            video_progress, created = VideoProgress.objects.update_or_create(
                user=user,
                video_id=video_id,
                defaults={'progress': progress, 'duration': duration}
            )
            if progress >= 100:
                video_progress.progress = 100
                video_progress.completed = True
                video_progress.save()

            return JsonResponse({'status': 'success', 'progress': video_progress.progress})

        except json.JSONDecodeError:
            return JsonResponse({'status': 'fail', 'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'status': 'fail', 'error': str(e)}, status=500)

    return JsonResponse({'status': 'fail', 'error': 'Invalid request method'}, status=400)


def add_note(request, part_id):
    if request.method == "POST":
        part = get_object_or_404(Part, id=part_id)
        content = request.POST.get('content')
        video_timestamp = request.POST.get('time')

        note = Notes.objects.create(
            user=request.user,
            part=part,
            content=content,
            video_timestamp=video_timestamp
        )
        # Return the note details in the response
        return JsonResponse({
            "id": note.id,
            "content": note.content,
            "time": note.video_timestamp
        })

def edit_note(request, note_id, part_id):
    if request.method == "POST":
        note = get_object_or_404(Notes, id=note_id, user=request.user)
        note.content = request.POST.get('content')
        note.video_timestamp = request.POST.get('time')

        note.save()
        # Return updated note details
        return JsonResponse({
            "id": note.id,
            "content": note.content,
            "time": note.video_timestamp,
            "updated_at": note.updated_at if hasattr(note, 'updated_at') else None
        })

def delete_note(request, note_id):
    if request.method == "POST":
        note = get_object_or_404(Notes, id=note_id, user=request.user)
        note.delete()
        return JsonResponse({"success": True, "id": note_id})


def TestVttVideo(request):
    return render(request, 'template20/counselor/test_vtt_video.html')