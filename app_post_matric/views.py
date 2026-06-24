from rest_framework import viewsets, permissions, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
# from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import UserProfile
from django.utils.dateparse import parse_datetime
# from .models import User
from .aptitude_area_labels import (
    normalize_aptitude_categories,
    resolve_aptitude_json_area,
)
from .test_display_labels import test_display_title
from .models import (
    TestCategory, Test, Question, Answer,
    TestSession, UserResponse, TestResult, Sections, SectionSession, TestTopCategories,
    TestCompletionPopup, CareerMatch, AptitudeCombinationMapping, ClusterMapping,
)
from careers.models import Career, CareerCluster
from .serializers import (
    TestCategorySerializer, TestCategoryDetailSerializer,
    TestSerializer, TestDetailSerializer,
    QuestionSerializer, AnswerSerializer,
    TestSessionSerializer, TestSessionDetailSerializer,
    UserResponseSerializer, TestResultSerializer,
    UserSerializer, ResponseDetailSerializer, SectionsSerializer, SectionSessionSerializer
)
import logging
import re
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import authenticate, login as auth_login, logout, get_user_model
from core.breadcrumbs import get_breadcrumb
# from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.template.loader import get_template
from django.conf import settings
from django.utils.text import slugify
User = get_user_model()
logger = logging.getLogger(__name__)


def _staff_report_student_id_from_request(request):
    """Resolve student user id when staff opens a report in an embed iframe."""
    raw = (request.GET.get("user_id") or "").strip()
    ref = (request.META.get("HTTP_REFERER") or "") + " " + (request.path or "")
    ref_m = re.search(r"combined_report/(\d+)", ref)
    ref_id = int(ref_m.group(1)) if ref_m else None
    if raw.isdigit():
        qid = int(raw)
        if ref_id and ref_id != qid:
            return ref_id
        return qid
    if (request.GET.get("embed") or "").strip() != "1":
        return None
    if ref_id:
        return ref_id
    return None


def _staff_can_view_student_report(request, student_uid) -> bool:
    """
    Institute, marketing-group, and institute-group admins may view a student's
    post-matric reports only when that student belongs to an institute they manage.
    """
    from core import choices
    from institute.models import StudentManagement

    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return False
    try:
        sid = int(student_uid)
    except (TypeError, ValueError):
        return False
    if sid == int(user.id):
        return True
    if user.is_superuser:
        return True

    try:
        ut = int(getattr(user, "user_type", 0) or 0)
    except Exception:
        ut = 0

    sm = (
        StudentManagement.objects.filter(student_id=sid)
        .select_related(
            "institute",
            "institute__institute_group",
            "institute__marketing_group",
        )
        .first()
    )
    if not sm or not sm.institute_id:
        return False
    institute = sm.institute
    if institute.created_by_id == user.id:
        return True
    ig = getattr(institute, "institute_group", None)
    if ig and getattr(ig, "institute_group_admin_id", None) == user.id:
        return True
    mg = getattr(institute, "marketing_group", None)
    if mg and getattr(mg, "marketing_group_admin_id", None) == user.id:
        return True
    if ut == choices.UserType.COUNSELOR:
        try:
            from counselor.models import Counselor

            if Counselor.qs_for_institute(institute).filter(coun_user=user).exists():
                return True
        except Exception:
            pass
    return False


def _report_display_fields_for_student(student_user, *, session_end=None):
    """Header fields for results.html (StudentManagement + UserProfile)."""
    from institute.models import StudentManagement

    name = (getattr(student_user, "name", None) or "").strip()
    if not name or name.lower() == "none":
        name = (getattr(student_user, "first_name", None) or "").strip()
    email = (getattr(student_user, "email", None) or "").strip()
    if not name and email:
        name = email.split("@")[0]
    schoolname = None
    grade = None
    gender_display = None
    created_date = session_end
    try:
        sm = (
            StudentManagement.objects.filter(student=student_user)
            .select_related("class_and_section", "institute")
            .order_by("-modified")
            .first()
        )
        if sm:
            if getattr(sm.student, "name", None):
                _sn = (sm.student.name or "").strip()
                if _sn and _sn.lower() != "none":
                    name = _sn
            if sm.class_and_section:
                grade = getattr(sm.class_and_section, "class_and_section", None) or grade
                _stream = getattr(sm.class_and_section, "stream", None) or ""
                if grade and _stream:
                    grade = f"{grade} - {_stream}"
            if sm.institute and getattr(sm.institute, "name", None):
                schoolname = sm.institute.name
    except Exception:
        pass
    try:
        user_profile = student_user.user_profile
        gender_value = user_profile.gender
        if gender_value == 20:
            gender_display = "Male"
        elif gender_value == 30:
            gender_display = "Female"
        elif gender_value == 10:
            gender_display = "Unknown"
        else:
            gender_display = "Unknown"
        if not schoolname:
            schoolname = user_profile.schoolname
        if not grade:
            grade = user_profile.grade
    except Exception:
        pass
    return {
        "student_name": name or email or "Student",
        "schoolname": schoolname or "-",
        "grade": grade or "-",
        "gender": gender_display or "",
        "created_date": _format_ui_datetime(created_date) if created_date else "",
    }


def _format_ui_datetime(value):
    """Return a UI-friendly local datetime string."""
    if not value:
        return None
    dt_value = value
    if isinstance(value, str):
        dt_value = parse_datetime(value)
        if dt_value is None:
            return value
    if timezone.is_naive(dt_value):
        dt_value = timezone.make_aware(dt_value, timezone.get_current_timezone())
    local_dt = timezone.localtime(dt_value)
    return local_dt.strftime("%d %b %Y, %I:%M %p")


def logout_view(request):
    logout(request)
    # For API-style logout (you can return JSON or redirect)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'message': 'Logged out successfully'}, status=200)
    return redirect('/api/login/')  # or wherever your login/home page is

from django.http import HttpResponse
import openpyxl

def download_users_excel(request):
    # Create a new Excel workbook
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Users"

    # Write headers
    sheet["A1"] = "Username"
    sheet["B1"] = "Email"

    # Write user data
    users = User.objects.all()
    for i, user in enumerate(users, start=2):  # start=2 (row 2 onwards)
        sheet[f"A{i}"] = user.username
        sheet[f"B{i}"] = user.email

    # Create HTTP response with Excel content
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="users.xlsx"'

    workbook.save(response)
    return response


def Index(request):
    return render(request, "index.html")


# def PaymentGatewayMatric(request):
#     return render(request, "payment-gateway.html")

# def PaymentGatewayPostMatric(request):
#     return render(request, "payment-gateway1.html")

# @login_required
def Home(request):
    import json
    from .models import TestSession, SectionSession
    from django.shortcuts import redirect
    from django.urls import reverse
    from psychometric_tests.models import PsychometricTestPayment
    from core import choices
    from institute.models import StudentManagement
    
    # Check if user is authenticated and is an institute-registered student (exempt from payment check)
    if request.user.is_authenticated:
        is_institute_student = StudentManagement.objects.filter(student=request.user).exists()
        
        # Only check payment for non-institute students
        if not is_institute_student:
            # Determine student class from UserProfile
            student_class = None
            try:
                user_profile = request.user.user_profile
                if user_profile and user_profile.grade:
                    student_class = str(user_profile.grade)
            except (AttributeError, UserProfile.DoesNotExist):
                pass
            
            # Check if user has purchased test for their class
            if student_class == "12":
                # Class 12 should have ADVANCED test (Career Direction)
                has_payment = PsychometricTestPayment.objects.filter(
                    user=request.user,
                    test_type=choices.PsychometricTestType.ADVANCED,
                    is_success=choices.YesNoChoices.YES
                ).exists()
                if not has_payment:
                    # Redirect to Career Direction buy page
                    return redirect(reverse('psychometrictests:PsychometricTest12'))
    
    context = {}
    
    # If user is authenticated, get test sessions and status
    if request.user.is_authenticated:
        try:
            # Initialize test status dictionary with default values for all tests
            test_status = {
                1: {'completed': False},
                2: {'completed': False},
                3: {'completed': False},
                4: {
                    'completed': False,
                    'total_sections': 0,
                    'completed_sections': 0,
                    'sections_status': {}
                }
            }
            
            # Check for latest completed session for each test (1, 2, 3, 4)
            for test_id in [1, 2, 3, 4]:
                # Get the latest completed session for this test
                latest_session = TestSession.objects.filter(
                    user=request.user,
                    test_id=test_id,
                    is_completed=True
                ).order_by('-end_time').first()
                
                if latest_session:
                    if test_id == 4:
                        # For test 4 (Aptitude), check section sessions
                        section_sessions = SectionSession.objects.filter(session=latest_session)
                        sections_status = {}
                        
                        for section_session in section_sessions:
                            sections_status[section_session.section.title] = {
                                'completed': section_session.is_completed,
                                'session_id': section_session.id
                            }
                        
                        test_status[4].update({
                            'completed': latest_session.is_completed,
                            'session_id': latest_session.id,
                            'total_sections': section_sessions.count(),
                            'completed_sections': section_sessions.filter(is_completed=True).count(),
                            'sections_status': sections_status
                        })
                    else:
                        # For tests 1, 2, 3
                        test_status[test_id] = {
                            'completed': latest_session.is_completed,
                            'session_id': latest_session.id
                        }
            
            context['test_status'] = json.dumps(test_status)
        except Exception as e:
            print(f"Error in Home view: {str(e)}")
            context['test_status'] = json.dumps({
                1: {'completed': False},
                2: {'completed': False},
                3: {'completed': False},
                4: {
                    'completed': False,
                    'total_sections': 0,
                    'completed_sections': 0,
                    'sections_status': {}
                }
            })
    
    return render(request, "template20/app_post_matric/home.html", context)

@login_required
def Profile(request):
    from .models import TestSession, TestResult
    from users.models import UserProfile
    
    user = request.user
    context = {
        'user': user,
    }
    
    # Get user profile data
    try:
        user_profile = user.user_profile
        context['user_profile'] = user_profile
    except UserProfile.DoesNotExist:
        context['user_profile'] = None
    
    # Get test statistics
    test_sessions = TestSession.objects.filter(user=user, is_completed=True)
    context['tests_completed'] = test_sessions.count()
    context['test_sessions'] = test_sessions
    
    # Calculate average score if results exist
    results = TestResult.objects.filter(session__user=user)
    if results.exists():
        total_score = sum(r.score or 0 for r in results)
        avg_score = total_score / results.count() if results.count() > 0 else 0
        context['avg_score'] = round(avg_score, 1)
    else:
        context['avg_score'] = 0
    
    return render(request, "template20/app_post_matric/profile.html", context)

@login_required
def Report(request):
    return render(request, "pdf_template_final.html")

@login_required
def Tests(request):
    import json
    from django.shortcuts import redirect
    from django.urls import reverse
    from psychometric_tests.models import PsychometricTestPayment
    from core import choices
    from institute.models import StudentManagement
    
    # Debug logging
    print("\n" + "="*80)
    print(f"[TESTS VIEW] User: {request.user.email} (ID: {request.user.id})")
    print("="*80)
    
    # Check if user is an institute-registered student (exempt from payment check)
    is_institute_student = StudentManagement.objects.filter(student=request.user).exists()
    
    # Only check payment for non-institute students
    if not is_institute_student:
        # Determine student class from UserProfile
        student_class = None
        try:
            user_profile = request.user.user_profile
            if user_profile and user_profile.grade:
                student_class = str(user_profile.grade)
        except (AttributeError, UserProfile.DoesNotExist):
            pass
        
        # Check if user has purchased test for their class
        if student_class == "12":
            # Class 12 should have ADVANCED test (Career Direction)
            has_payment = PsychometricTestPayment.objects.filter(
                user=request.user,
                test_type=choices.PsychometricTestType.ADVANCED,
                is_success=choices.YesNoChoices.YES
            ).exists()
            if not has_payment:
                # Redirect to Career Direction buy page
                return redirect(reverse('psychometrictests:PsychometricTest12'))
    
    # Initialize test status dictionary with default values for all tests
    test_status = {
        1: {'completed': False},
        2: {'completed': False},
        3: {'completed': False},
        4: {
            'completed': False,
            'total_sections': 0,
            'completed_sections': 0,
            'sections_status': {}
        }
    }
    
    # Map test IDs to test types for popup identification
    test_type_map = {}  # Will store {test_id: test_type}
    
    try:
        # Debug: Check all sessions first
        all_sessions = TestSession.objects.filter(user=request.user)
        print(f"[DEBUG] Total sessions for user: {all_sessions.count()}")
        for sess in all_sessions:
            print(f"  - Session ID {sess.id}: Test ID {sess.test.id} ({sess.test.title}), Completed: {sess.is_completed}, End Time: {sess.end_time}")
        
        # Check for latest completed session for each test (1, 2, 3, 4) - fixes issue with multiple sessions
        print("\n[DEBUG] Checking completed sessions for each test:")
        for test_id in [1, 2, 3, 4]:
            # Get the latest completed session for this test (same pattern as Home view)
            latest_session = TestSession.objects.filter(
                user=request.user,
                test_id=test_id,
                is_completed=True
            ).order_by('-end_time').first()
            
            if latest_session:
                print(f"  ✅ Test {test_id}: Found completed session (ID: {latest_session.id}, End: {latest_session.end_time})")
                test_title = latest_session.test.title.lower().strip()
                
                # Identify test type for popup mapping
                if 'personality assessment' in test_title:
                    test_type_map[test_id] = 'personality'
                elif 'motivation assessment' in test_title:
                    test_type_map[test_id] = 'motivation'
                elif 'career interest inventory' in test_title or str(test_id) == '3':
                    test_type_map[test_id] = 'career_interest'
                elif 'aptitude assessment' in test_title:
                    test_type_map[test_id] = 'aptitude'
                
                if test_id == 4:
                    # For test 4 (Aptitude), check section sessions
                    section_sessions = SectionSession.objects.filter(session=latest_session)
                    sections_status = {}
                    
                    for section_session in section_sessions:
                        sections_status[section_session.section.title] = {
                            'completed': section_session.is_completed,
                            'session_id': section_session.id
                        }
                    
                    test_status[4].update({
                        'completed': latest_session.is_completed,
                        'session_id': latest_session.id,
                        'total_sections': section_sessions.count(),
                        'completed_sections': section_sessions.filter(is_completed=True).count(),
                        'sections_status': sections_status
                    })
                else:
                    # For tests 1, 2, 3
                    test_status[test_id] = {
                        'completed': latest_session.is_completed,
                        'session_id': latest_session.id
                    }
            else:
                print(f"  ❌ Test {test_id}: No completed session found")
        
        # Debug: Print final test status
        print("\n[DEBUG] Final Test Status:")
        for test_id, status in test_status.items():
            completed = status.get('completed', False)
            session_id = status.get('session_id', 'N/A')
            status_icon = "✅" if completed else "❌"
            print(f"  {status_icon} Test {test_id}: completed={completed}, session_id={session_id}")
    except Exception as test_status_error:
        import traceback
        print(f"\n[ERROR] Error building test_status: {str(test_status_error)}")
        traceback.print_exc()
        print("[ERROR] Continuing with default test_status")
    
    # Check which popups have been answered (handle missing table gracefully)
    # This is separate from test_status building so errors here don't affect test status
    answered_popups = set()
    try:
        # Use raw SQL check first to see if table exists, then query
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'app_post_matric_testcompletionpopup'")
            table_exists = cursor.fetchone() is not None
        
        if table_exists:
            popup_answers = TestCompletionPopup.objects.filter(user=request.user)
            answered_popups = {popup.test_type for popup in popup_answers}
            print(f"\n[DEBUG] Answered popups: {answered_popups}")
        else:
            print(f"[DEBUG] TestCompletionPopup table does not exist - skipping popup check")
            answered_popups = set()
    except Exception as popup_error:
        # Table might not exist in production DB copy - this is OK, just log it
        print(f"[DEBUG] TestCompletionPopup query error (non-critical): {str(popup_error)}")
        print(f"[DEBUG] Continuing without popup data (this is OK)")
        answered_popups = set()
    
    # Determine which popups need to be shown
    # Popup should be shown if: test is completed AND popup hasn't been answered
    popup_status = {
        'personality': False,
        'motivation': False,
        'career_interest': False,
        'aptitude': False
    }
    
    # Check each completed test to see if popup needs to be shown
    for test_id, status_info in test_status.items():
        if status_info.get('completed', False):
            test_type = test_type_map.get(test_id)
            if test_type and test_type not in answered_popups:
                popup_status[test_type] = True
    
    print(f"[DEBUG] Popup status: {popup_status}")
    print(f"[DEBUG] Test type map: {test_type_map}")
    print("="*80 + "\n")
    
    context = {
        'test_status': json.dumps(test_status),
        'popup_status': json.dumps(popup_status),
        'test_type_map': json.dumps(test_type_map),
        'breadcrumb': get_breadcrumb([{'text': 'Tests', 'url': ''}]),
    }
    
    print(f"[SUCCESS] Returning context with test_status: {test_status}")
    return render(request, "template20/app_post_matric/tests.html", context)


@login_required
def save_popup_answer(request):
    """Save popup answer and send email after 3rd popup (career_interest)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    try:
        test_type = request.POST.get('test_type')
        answer = request.POST.get('answer')
        country = request.POST.get('country', None)
        
        if not test_type or not answer:
            return JsonResponse({'error': 'test_type and answer are required'}, status=400)
        
        # Validate test_type
        valid_test_types = ['personality', 'motivation', 'career_interest', 'aptitude']
        if test_type not in valid_test_types:
            return JsonResponse({'error': f'Invalid test_type. Must be one of: {", ".join(valid_test_types)}'}, status=400)
        
        # Save or update the popup answer
        popup_answer, created = TestCompletionPopup.objects.update_or_create(
            user=request.user,
            test_type=test_type,
            defaults={
                'answer': answer,
                'country': country
            }
        )
        
        # If this is the 3rd popup (career_interest), send email to admins
        if test_type == 'career_interest':
            try:
                from communication.com_service import ComService
                cs = ComService()
                
                # Get all 3 popup answers (personality, motivation, career_interest)
                popup_answers = TestCompletionPopup.objects.filter(
                    user=request.user,
                    test_type__in=['personality', 'motivation', 'career_interest']
                ).order_by('test_type')
                
                # Prepare data for email
                answers_data = {}
                for popup in popup_answers:
                    answers_data[popup.test_type] = {
                        'answer': popup.answer,
                        'country': popup.country
                    }
                
                # Send email
                cs.send_test_popup_answers_email(request.user, answers_data)
            except Exception as e:
                print(f"Error sending email after career_interest popup: {str(e)}")
                # Don't fail the request if email fails
        
        return JsonResponse({
            'success': True,
            'message': 'Popup answer saved successfully',
            'created': created
        })
    
    except Exception as e:
        print(f"Error in save_popup_answer: {str(e)}")
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)


import json
import os
from django.conf import settings


def career_cluster_label_lookup_keys(raw_name):
    """Normalized lookup keys for matching report labels to CareerCluster maps."""
    name = str(raw_name or '').strip()
    if not name:
        return []
    keys = set()
    lower_name = name.lower()
    keys.add(lower_name)
    keys.add(lower_name.replace('&', 'and'))
    keys.add(lower_name.replace(' and ', ' & '))
    compact = re.sub(r'\s+', ' ', lower_name)
    keys.add(compact)
    keys.add(compact.replace('&', 'and'))
    keys.add(re.sub(r'[^a-z0-9 ]+', ' ', compact).strip())
    return [k.strip() for k in keys if k and k.strip()]


def _cluster_resolve_lookup(label, cluster_resolve_map):
    for key in career_cluster_label_lookup_keys(label):
        if key in cluster_resolve_map:
            return cluster_resolve_map[key]
    return None


def _cluster_url_only_lookup(label, cluster_url_map):
    for key in career_cluster_label_lookup_keys(label):
        if key in cluster_url_map:
            return cluster_url_map[key]
    return None


def enrich_combined_report_cluster_links(context, cluster_resolve_map, cluster_url_map):
    """
    Ensure cluster names/URLs use DB titles and career library links.
    Fixes cases where aptitude M2M has no URL or the template never uses resolve maps.
    """
    am = context.get('aptitude_mapping')
    if isinstance(am, dict):
        for item in am.get('clusters') or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get('name') or '').strip()
            if not name:
                continue
            resolved = _cluster_resolve_lookup(name, cluster_resolve_map)
            if resolved:
                if resolved.get('name'):
                    item['name'] = resolved['name']
                if resolved.get('url'):
                    item['url'] = resolved['url']
            if not item.get('url'):
                item['url'] = _cluster_url_only_lookup(
                    item.get('name') or name, cluster_url_map
                )

    for guidance in context.get('career_guidance_selected') or []:
        if not isinstance(guidance, dict):
            continue
        raw_list = guidance.get('Career_Clusters')
        if not raw_list:
            continue
        seen = set()
        resolved_rows = []
        for raw in raw_list:
            label = str(raw or '').strip()
            if not label:
                continue
            res = _cluster_resolve_lookup(label, cluster_resolve_map)
            display = (res.get('name') if res else None) or label
            url = (res.get('url') if res else None) or _cluster_url_only_lookup(
                label, cluster_url_map
            )
            dedupe = (display or '').lower()
            if dedupe in seen:
                continue
            seen.add(dedupe)
            resolved_rows.append({'name': display, 'url': url})
        guidance['Career_Clusters_resolved'] = resolved_rows

    for item in context.get('psychometric_career_clusters') or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip()
        if not name:
            continue
        if item.get('url'):
            continue
        resolved = _cluster_resolve_lookup(name, cluster_resolve_map)
        if resolved:
            if resolved.get('name'):
                item['name'] = resolved['name']
            if resolved.get('url'):
                item['url'] = resolved['url']
        if not item.get('url'):
            item['url'] = _cluster_url_only_lookup(item.get('name') or name, cluster_url_map)


def resolve_riasec_high_categories(session, stored_high_category=None):
    """Derive RIASEC code from TestResult scores; fall back to stored TestTopCategories."""
    from app.interest_report_utils import riasec_code_string_from_scores

    test_result = TestResult.objects.filter(session=session).first()
    if test_result and test_result.result_data:
        code = riasec_code_string_from_scores(test_result.result_data)
        if code:
            return code
    if stored_high_category:
        return str(stored_high_category).strip("[]").strip()
    return ''


def normalize_test_result_data_for_charts(stored_data, is_aptitude=False):
    """Normalize personality/career scores for chart JSON; keep metadata keys (e.g. _top_3_categories)."""
    if not isinstance(stored_data, dict):
        return stored_data
    if is_aptitude:
        return stored_data.copy()
    normalized_data = {}
    for key, value in stored_data.items():
        if str(key).startswith('_'):
            normalized_data[key] = value
            continue
        if isinstance(value, dict):
            if 'score' in value:
                normalized_data[key] = {'score': value['score']}
            elif isinstance(value, (int, float)):
                normalized_data[key] = {'score': value}
            else:
                normalized_data[key] = value
        elif isinstance(value, (int, float)):
            normalized_data[key] = {'score': value}
        else:
            normalized_data[key] = {'score': 0}
    return normalized_data


def get_hexaco_or_riasec_career_mapping(latest_session):
    try:

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'hexaco_personality.json')
        with open(path, 'r', encoding='utf-8') as file:
            hexaco_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'interest_riasec.json')
        with open(path, 'r', encoding='utf-8') as file:
            riasec_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'Motivation_Career.json')
        with open(path, 'r', encoding='utf-8') as file:
            motivation_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'aptitude_weak_areas_improvement_plan_2.json')
        with open(path, 'r', encoding='utf-8') as file:
            aptitude_weak_areas_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'aptitude_strength_narrative_1.json')
        with open(path, 'r', encoding='utf-8') as file:
            aptitude_strength_narrative_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'Aptitude_report_main-modified1.json')
        with open(path, 'r', encoding='utf-8') as file:
            Aptitude_report_main_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'aptitude_recommendations_for_colleges_3.json')
        with open(path, 'r',encoding='utf-8') as file:
            aptitude_recommendations_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'merged-1754477770562.json')
        with open(path, 'r',encoding='utf-8') as file:
            career_mergerd_path = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'combined_report_Average_above_average.json')
        with open(path, 'r',encoding='utf-8') as file:
            CombinedReport_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'aptitute interpretation.json')
        with open(path, 'r',encoding='utf-8') as file:
            aptitude_interpretation_data = json.load(file)

        return hexaco_data, riasec_data.get('code'), motivation_data.get('rows'), aptitude_weak_areas_data.get('rows'), aptitude_strength_narrative_data.get('rows'), Aptitude_report_main_data.get('rows'),aptitude_recommendations_data.get('rows'), career_mergerd_path, CombinedReport_data.get('rows'), aptitude_interpretation_data
        

    except Exception as e:
        print("exception: ",e)
        return None, None, None, None, None, None , None, None, None

def map_hexaco_code_to_trait(code):
    """Map single letter code to full trait name"""
    mapping = {
        'H': 'Honesty-Humility',
        'E': 'Emotionality',
        'X': 'eXtraversion',
        'A': 'Agreeableness',
        'C': 'Conscientiousness',
        'O': 'Openness to Experience'
    }
    return mapping.get(code, code)

def map_motivation_domain_to_trait(code):
    """Map single letter code to full trait name"""
    mapping = {
        'Business': 'Business Professions',
        'Engineer': 'Technology Professions',
        'Social': 'Humanities & Social Service',
        'Medical': 'Medical-Science Professions',
    }
    return mapping.get(code, code)

def get_hexaco_career_recommendations(high_categories, low_category, latest_session):

    # Initialize default return structure
    result = {
        'careers_to_opt': {},
        'careers_to_avoid': [],
        'high_trait_descriptions': {},
        'low_trait_descriptions': {},
        'dominant_trait_explanations': [],
        'combined_code_explanation': None,

        'riasec_careers_to_opt': {
            "Traditional": [],
            "Trending": [],
            "Futuristic": []
        },
        'riasec_key_descriptions': [],
        'riasec_key_drivers': [],
        'riasec_summaries': [],

        'career_code_discription':[],

        'motivation_careers_to_opt': {
            "Motivation Style": [],
            "Career Category & Roles": [],
            "Key Characteristics & Details": []
        },
        'motivation_key_description': None,
        'motivation_key_drivers': [],
        'motivation_summary': None,
        
        'aptitude_improvement_plan': [],
        'aptitude_strength_narrative': [],
        'aptitude_Recommended_College_Courses':[],
        'aptitude_roles_guidance':[],
        'career_guidance_selected':[],
        }
    
    try:        
        hexaco_data, riasec_data, motivation_data, aptitude_weak_areas_data , aptitude_strength_narrative_data, Aptitude_report_main_data, aptitude_recommendations_data, career_mergerd_path, CombinedReport_data, aptitude_interpretation_data = get_hexaco_or_riasec_career_mapping(latest_session)
        
        # Store aptitude_interpretation_data in a variable accessible in the function
        if aptitude_interpretation_data is None:
            aptitude_interpretation_data = {}
        
        
        if latest_session.test.title == 'Career Interest Inventory':
            # Process RIASEC codes
            
            riasec_code_categories = high_categories
            logger.debug(f"\n=== RIASEC DEBUG ===")
            logger.debug(f"high_categories (RIASEC Code): {high_categories}")

            if high_categories in career_mergerd_path:
                ris_data = {f"{high_categories}": career_mergerd_path[high_categories]}
                result['career_code_discription'] = [ris_data]
                logger.debug(f"Description data for {high_categories}: {ris_data}")
            else:
                logger.debug(f"Warning: RIASEC code {high_categories} not found in career_mergerd_path.")
            
            if riasec_code_categories in riasec_data:
                category_data = riasec_data[riasec_code_categories]
                
                # Process each career category
                for category in ["Traditional", "Trending", "Futuristic"]:
                    riasec_key = f"{category}_Careers" if category != "Futuristic" else "Futuristic_Emerging_Careers"
                    if riasec_key in category_data:
                        careers = category_data[riasec_key].split("<br/>")
                        result['riasec_careers_to_opt'][category] = [c.strip() for c in careers if c.strip()]
            else:
                logger.debug(f"Warning: RIASEC code {riasec_code_categories} not found in data.")
            
            # Load RIASEC key descriptions, drivers, and summaries
            # Extract individual letters from RIASEC code (e.g., "CES" -> ["C", "E", "S"])
            if high_categories and len(high_categories) >= 1:
                riasec_letters = list(high_categories.upper()[:3])  # Get first 3 letters
                logger.debug(f"Extracted RIASEC letters: {riasec_letters}")
                
                # Load interest_riasec.json to get the new sections (using the already loaded hexaco_data structure)
                # We need to load the full JSON to access the new top-level keys
                interest_json_path = os.path.join(settings.BASE_DIR, 'static', 'data', 'interest_riasec.json')
                with open(interest_json_path, 'r', encoding='utf-8') as file:
                    interest_json_data = json.load(file)
                
                # Get key descriptions for each letter in the code
                key_descriptions_list = interest_json_data.get('RIASEC_Key_Descriptions', [])
                logger.debug(f"Found {len(key_descriptions_list)} key descriptions")
                for letter in riasec_letters:
                    desc = next((d for d in key_descriptions_list if d.get('RIASEC_Code') == letter), None)
                    if desc:
                        logger.debug(f"✓ Found key_description for {letter}")
                        result['riasec_key_descriptions'].append(desc)
                    else:
                        logger.debug(f"✗ No key_description found for {letter}")
                
                # Get key drivers for each letter in the code
                key_drivers_list = interest_json_data.get('RIASEC_Key_Drivers', [])
                logger.debug(f"Found {len(key_drivers_list)} key drivers lists")
                for letter in riasec_letters:
                    drivers = next((d for d in key_drivers_list if d.get('RIASEC_Code') == letter), None)
                    if drivers:
                        logger.debug(f"✓ Found key_drivers for {letter} with {len(drivers.get('Key Drivers', []))} drivers")
                        result['riasec_key_drivers'].append(drivers)
                    else:
                        logger.debug(f"✗ No key_drivers found for {letter}")
                
                # Get summaries for each letter in the code
                summaries_list = interest_json_data.get('RIASEC_Summaries', [])
                logger.debug(f"Found {len(summaries_list)} summaries")
                for letter in riasec_letters:
                    summary = next((s for s in summaries_list if s.get('RIASEC_Code') == letter), None)
                    if summary:
                        logger.debug(f"✓ Found summary for {letter}")
                        result['riasec_summaries'].append(summary)
                    else:
                        logger.debug(f"✗ No summary found for {letter}")
            
            logger.debug("=== END RIASEC DEBUG ===")


        elif latest_session.test.title == 'Personality Assessment':
            high_trait_descriptions = {}
            low_trait_descriptions = {}
            
            # Process high categories
            for category_code in high_categories:
                trait_name = map_hexaco_code_to_trait(category_code)
                if trait_name not in result['careers_to_opt']:
                    result['careers_to_opt'][trait_name] = []  # Initialize empty list for careers
                
                for trait_data in hexaco_data.get('HEXACO_Career_to_opt', []):
                    if trait_data['HEXACO Trait'] == trait_name and trait_data['Score Type'] == 'High':
                        result['careers_to_opt'][trait_name].extend(trait_data['Suggested Careers'])
                        
                        key = f"{trait_name}"
                        if key not in high_trait_descriptions:
                            high_trait_descriptions[key] = []
                        high_trait_descriptions[key].append(trait_data['Trait Description'])

                # Process low category
                if low_category:
                    low_trait_name = map_hexaco_code_to_trait(low_category)
                    
                    for trait_data in hexaco_data.get('HEXACO_Careers_to_Avoid', []):
                        if trait_data['HEXACO Trait'] == low_trait_name and trait_data['Score Type'] == 'Low':
                            result['careers_to_avoid'] = trait_data['Careers to Avoid']
                            low_trait_descriptions[f"{low_trait_name}"] = trait_data['Trait Description']

                # Remove duplicates in careers_to_opt
                for trait_name, careers in result['careers_to_opt'].items():
                    result['careers_to_opt'][trait_name] = list(dict.fromkeys(careers))

                # Add descriptions to the result
                result['high_trait_descriptions'] = high_trait_descriptions
                result['low_trait_descriptions'] = low_trait_descriptions
                
                # Get dominant trait explanations for high categories
                dominant_explanations = []
                for category_code in high_categories:
                    for explanation in hexaco_data.get('HEXACO_Dominant_Trait_Explanations', []):
                        if explanation.get('Trait Code') == category_code:
                            dominant_explanations.append(explanation)
                            break
                result['dominant_trait_explanations'] = dominant_explanations
                
                # Get combined code explanation if we have 2 high categories
                if len(high_categories) >= 2:
                    # Create combined code (e.g., "H & C")
                    combined_code = f"{high_categories[0]} & {high_categories[1]}"
                    # Also try reverse order
                    combined_code_reverse = f"{high_categories[1]} & {high_categories[0]}"
                    
                    for explanation in hexaco_data.get('HEXACO_Combined_Code_Explanations', []):
                        if explanation.get('Combined Code') == combined_code or explanation.get('Combined Code') == combined_code_reverse:
                            result['combined_code_explanation'] = explanation
                            break

        elif latest_session.test.title == 'Motivation Assessment':
            domain = map_motivation_domain_to_trait(high_categories)
            logger.debug(f"\n=== MOTIVATION DEBUG ===")
            logger.debug(f"high_categories: {high_categories}")
            logger.debug(f"Mapped domain: {domain}")
            
            domain_data = next((row for row in motivation_data if row['Domain'] == domain), None)
            if not domain_data:
                logger.debug(f"ERROR: domain_data is None for domain: {domain}")
            else:
                logger.debug(f"Found domain_data for: {domain}")

            # Ensure Motivation Style is a list
            motivation_style = domain_data['Motivation Style']
            result['motivation_careers_to_opt']['Motivation Style'] = [motivation_style.strip('.')]  # convert to list and remove final dot if any

            # Remove trailing dots from entries in Career Category & Roles
            roles = domain_data['Career Category & Roles']
            cleaned_roles = [role.rstrip('.') for role in roles]
            result['motivation_careers_to_opt']['Career Category & Roles'] = cleaned_roles

            # Remove trailing dots from Key Characteristics & Details
            details = domain_data.get('Key Characteristics & Details', ['No details available'])
            cleaned_details = [detail.rstrip('.') for detail in details]
            result['motivation_careers_to_opt']['Key Characteristics & Details'] = cleaned_details
            
            # Load Motivation_Career.json to get the new sections
            motivation_json_path = os.path.join(settings.BASE_DIR, 'static', 'data', 'Motivation_Career.json')
            with open(motivation_json_path, 'r', encoding='utf-8') as file:
                motivation_json_data = json.load(file)
            
            # Get motivation key description
            key_descriptions = motivation_json_data.get('Motivation_Key_Descriptions', [])
            logger.debug(f"Found {len(key_descriptions)} key descriptions")
            key_description = next((desc for desc in key_descriptions if desc['Domain'] == domain), None)
            if key_description:
                logger.debug(f"✓ Found key_description for domain: {domain}")
                result['motivation_key_description'] = key_description
            else:
                logger.debug(f"✗ No key_description found for domain: {domain}")
                logger.debug(f"Available domains in key_descriptions: {[d.get('Domain') for d in key_descriptions]}")
            
            # Get motivation key drivers
            key_drivers_list = motivation_json_data.get('Motivation_Key_Drivers', [])
            logger.debug(f"Found {len(key_drivers_list)} key drivers lists")
            key_drivers = next((drivers for drivers in key_drivers_list if drivers['Domain'] == domain), None)
            if key_drivers:
                logger.debug(f"✓ Found key_drivers for domain: {domain}")
                # Check if Key Drivers is a list of objects or strings
                drivers_data = key_drivers.get('Key Drivers', [])
                if drivers_data and isinstance(drivers_data[0], dict):
                    # New format with Title, Description, Icon
                    logger.debug(f"Using new format with {len(drivers_data)} drivers")
                    result['motivation_key_drivers'] = drivers_data
                else:
                    # Old format - convert strings to objects
                    logger.debug(f"Converting old format with {len(drivers_data)} drivers")
                    converted_drivers = []
                    for driver_str in drivers_data:
                        if ':' in driver_str:
                            parts = driver_str.split(':', 1)
                            converted_drivers.append({
                                'Title': parts[0].strip(),
                                'Description': parts[1].strip(),
                                'Icon': 'fas fa-circle'  # Default icon
                            })
                        else:
                            converted_drivers.append({
                                'Title': driver_str,
                                'Description': '',
                                'Icon': 'fas fa-circle'
                            })
                    result['motivation_key_drivers'] = converted_drivers
            else:
                logger.debug(f"✗ No key_drivers found for domain: {domain}")
                logger.debug(f"Available domains in key_drivers: {[d.get('Domain') for d in key_drivers_list]}")
            
            # Get motivation summary
            summaries = motivation_json_data.get('Motivation_Summaries', [])
            logger.debug(f"Found {len(summaries)} summaries")
            summary = next((summ for summ in summaries if summ['Domain'] == domain), None)
            if summary:
                logger.debug(f"✓ Found summary for domain: {domain}")
                result['motivation_summary'] = summary
            else:
                logger.debug(f"✗ No summary found for domain: {domain}")
                logger.debug(f"Available domains in summaries: {[s.get('Domain') for s in summaries]}")
            
            logger.debug("=== END MOTIVATION DEBUG ===")

        elif latest_session.test.title == 'Aptitude Assessment':
            try:
                # Ensure result lists exist (safe if already present)
                for key in [
                    'aptitude_improvement_plan',
                    'aptitude_strength_narrative',
                    'aptitude_Recommended_College_Courses',
                    'aptitude_roles_guidance',
                    'career_guidance_selected'
                ]:
                    result.setdefault(key, [])

                # Extract categories safely
                above_categories = high_categories.get("Above Average", []) or []
                average_categories = high_categories.get("Average", []) or []
                below_categories  = high_categories.get("Below Average", []) or []

                # ---------- Helper: Normalize area names ----------
                def normalize_area(area):
                    area = area.replace('&', 'and').replace('Clerical speed & Accuracy', 'Clerical speed and Accuracy')
                    return re.sub(r'\s+', ' ', area.strip().lower())

                # ---------- Build fast lookup maps (canonical keys for legacy spellings) ----------
                weak_map = {}
                for row in (aptitude_weak_areas_data or []):
                    key = row.get('Areas')
                    if key:
                        weak_map[resolve_aptitude_json_area(key)] = row
                strength_map = {}
                for row in (aptitude_strength_narrative_data or []):
                    key = row.get('Areas')
                    if key:
                        strength_map[resolve_aptitude_json_area(key)] = row
                rec_map = {normalize_area(row.get('Areas')): row for row in (aptitude_recommendations_data or []) if row.get('Areas')}
                roles_map = {}
                for row in (Aptitude_report_main_data or []):
                    k = normalize_area(row.get('Area'))
                    if k:
                        roles_map.setdefault(k, []).append(row)

                # ---------- Below Average: Improvement Plan ----------
                json_plans = []
                for area in below_categories:
                    data = weak_map.get(resolve_aptitude_json_area(area))
                    if data:
                        remarks = [(r or '').rstrip('.') for r in data.get('Remarks', [])]
                        duration = data.get('Duration', 'No details available')
                        json_plans.append({
                            'Area': data.get('Areas', 'Unknown'),
                            'Remarks': remarks,
                            'Duration': duration,
                            'Category': 'Below Average',
                        })

                from app.aptitude_improvement_plans import CLASS_12, merge_improvement_plans
                result['aptitude_improvement_plan'] = merge_improvement_plans(
                    below_categories,
                    json_plans,
                    education_level=CLASS_12,
                )

                # ---------- Helper: Strength + Recommendations + Roles ----------
                def process_strength_recs_roles(areas):
                    for area in areas:
                        area_key = resolve_aptitude_json_area(area)
                        # Strength narrative
                        srow = strength_map.get(area_key)
                        if srow:
                            major_points = [(r or '').rstrip('.') for r in srow.get('Major points', [])]
                            result['aptitude_strength_narrative'].append({
                                'Area': srow.get('Areas', 'Unknown'),
                                'Major_points': major_points
                            })
                        # Recommendations
                        rrow = rec_map.get(normalize_area(area_key))
                        if rrow:
                            recommended_college = list(rrow.get('Recommended College Courses', []))
                            rec_entry = {
                                'Area': rrow.get('Areas', 'Unknown'),
                                'Recommended_College': recommended_college,
                                'Universities': list(rrow.get('Universities', [])),
                            }
                            # Optional hint fields (only included when present in source data)
                            for hint_key in ['Eligibility', 'Stream', 'Entrance Exams', 'Entrance Path', 'Duration']:
                                hint_value = rrow.get(hint_key)
                                if hint_value:
                                    rec_entry[hint_key] = hint_value
                            result['aptitude_Recommended_College_Courses'].append(rec_entry)
                        # Roles guidance
                        matches = roles_map.get(normalize_area(area_key), [])
                        if matches:
                            first = matches[0]
                            area_group = {
                                "Area": first.get('Area', 'Unknown'),
                                "Guidance": first.get('Guidance', 'No guidance available'),
                                "Recommendations": [
                                    {"Role": m.get("Role")} for m in matches
                                ]
                            }
                            result['aptitude_roles_guidance'].append(area_group)

                # ---------- Above Average + Average: Strength/Recommendations/Roles ----------
                from app.class12_aptitude_report_utils import apply_consolidated_to_aptitude_result

                consolidated_key = apply_consolidated_to_aptitude_result(
                    result,
                    above_categories,
                    average_categories,
                )
                if not consolidated_key:
                    process_strength_recs_roles(above_categories)
                    process_strength_recs_roles(average_categories)
                else:
                    result['class12_aptitude_combination_key'] = consolidated_key

                # ---------- Student-facing grouped course cards ----------
                # Build "Course + mapped area(s) + optional eligibility hints" structure for dashboard.
                course_cards_map = {}
                for row in result.get('aptitude_Recommended_College_Courses', []):
                    area_name = str(row.get('Area', '') or '').strip()
                    course_names = row.get('Recommended_College', []) or []
                    universities = row.get('Universities', []) or []

                    hint_items = []
                    for hint_key in ['Eligibility', 'Stream', 'Entrance Exams', 'Entrance Path', 'Duration']:
                        hint_val = row.get(hint_key)
                        if not hint_val:
                            continue
                        if isinstance(hint_val, list):
                            hint_text = ', '.join([str(v).strip() for v in hint_val if str(v).strip()])
                        else:
                            hint_text = str(hint_val).strip()
                        if hint_text:
                            hint_items.append(f"{hint_key}: {hint_text}")

                    for raw_course in course_names:
                        course_name = str(raw_course or '').strip()
                        if not course_name:
                            continue
                        card = course_cards_map.get(course_name)
                        if not card:
                            card = {
                                'course_name': course_name,
                                'mapped_areas': [],
                                'universities': [],
                                'eligibility_hints': [],
                            }
                            course_cards_map[course_name] = card

                        if area_name and area_name not in card['mapped_areas']:
                            card['mapped_areas'].append(area_name)

                        for uni in universities:
                            uni_name = str(uni or '').strip()
                            if uni_name and uni_name not in card['universities']:
                                card['universities'].append(uni_name)

                        for hint_text in hint_items:
                            if hint_text not in card['eligibility_hints']:
                                card['eligibility_hints'].append(hint_text)

                result['aptitude_course_recommendation_cards'] = sorted(
                    list(course_cards_map.values()),
                    key=lambda item: item.get('course_name', '').lower()
                )

                # ---------- Combined Report: Exact Area Match ----------
                # selected_areas = set(above_categories + average_categories)
                # normalized_selected = set(normalize_area(a) for a in selected_areas)

                # # Find the combined report entries with exactly these areas
                # career_guidance_selected = [
                #     {
                #         'Areas': entry['Areas'],
                #         'Career_Clusters': entry['Career Clusters'],
                #         'Career_Roles': entry['Career Roles'],
                #         'Educational_Pathways': entry['Educational Pathways']
                #     }
                #     for entry in (CombinedReport_data or [])
                #     if set(normalize_area(a) for a in entry['Areas'].split(',')) == normalized_selected
                # ]

                # # Append to result for Django template looping
                # result['career_guidance_selected'].extend(career_guidance_selected)

                # For debugging (optional)
                # print(json.dumps(result['career_guidance_selected'], indent=2))
            
            	# ---------- Combined Report: Flexible Match ----------
                # ---------- Combined Report: Exact Area Match ----------
                # Combine above average and average categories
                selected_areas = set(above_categories + average_categories)

                # CRITICAL CHECK: If both lists are empty, skip career_guidance logic but still return result (do not return None)
                if not selected_areas:
                    career_guidance_selected = []
                    result['career_guidance_selected'].extend(career_guidance_selected)
                else:
                    # Normalize selected areas to match JSON format
                    normalized_selected = set()
                    for area in selected_areas:
                        mapped_area = resolve_aptitude_json_area(area)
                        # Normalize the mapped area to lowercase for comparison
                        normalized_selected.add(normalize_area(mapped_area))


                    # Find the combined report entries with exactly these areas
                    career_guidance_selected = []
                    
                    for entry in (CombinedReport_data or []):
                        # Handle both single area and comma-separated areas
                        entry_areas = entry['Areas']
                        if isinstance(entry_areas, str):
                            # Split by comma and normalize each area
                            entry_area_list = [normalize_area(area.strip()) for area in entry_areas.split(',')]
                        else:
                            # If it's already a list, normalize each area
                            entry_area_list = [normalize_area(area.strip()) for area in entry_areas]
                        
                        # Check if this entry matches our selected areas
                        if set(entry_area_list) == normalized_selected:
                            career_guidance_selected.append({
                                'Areas': entry['Areas'],
                                'Career_Clusters': entry['Career Clusters'],
                                'Career_Roles': entry['Career Roles'],
                                'Educational_Pathways': entry['Educational Pathways']
                            })

                    # If no exact match found, try to find entries that contain all our areas
                    if not career_guidance_selected:
                        # print("No exact match found, looking for entries that contain all selected areas...")
                        for entry in (CombinedReport_data or []):
                            entry_areas = entry['Areas']
                            if isinstance(entry_areas, str):
                                entry_area_list = [normalize_area(area.strip()) for area in entry_areas.split(',')]
                            else:
                                entry_area_list = [normalize_area(area.strip()) for area in entry_areas]
                            
                            # Check if this entry contains all our selected areas
                            if normalized_selected.issubset(set(entry_area_list)):
                                career_guidance_selected.append({
                                    'Areas': entry['Areas'],
                                    'Career_Clusters': entry['Career Clusters'],
                                    'Career_Roles': entry['Career Roles'],
                                    'Educational_Pathways': entry['Educational Pathways']
                                })
                                # print(f"Found superset match: {entry['Areas']}")

                    # print("career_guidance_selected", career_guidance_selected)

                    # Ensure unique values in each field
                    if career_guidance_selected:
                        # Collect all unique values for each field
                        unique_areas = set()
                        unique_clusters = set()
                        unique_roles = set()
                        unique_pathways = set()
                        
                        for entry in career_guidance_selected:
                            # Handle areas (can be string or list)
                            areas = entry['Areas']
                            if isinstance(areas, str):
                                areas = [area.strip() for area in areas.split(',')]
                            unique_areas.update(areas)
                            
                            # Handle clusters (should be list)
                            clusters = entry['Career_Clusters']
                            if isinstance(clusters, list):
                                unique_clusters.update([cluster.strip() for cluster in clusters])
                            else:
                                unique_clusters.update([clusters.strip()])
                            
                            # Handle roles (should be list)
                            roles = entry['Career_Roles']
                            if isinstance(roles, list):
                                unique_roles.update([role.strip() for role in roles])
                            else:
                                unique_roles.update([roles.strip()])
                            
                            # Handle pathways (should be list)
                            pathways = entry['Educational_Pathways']
                            if isinstance(pathways, list):
                                unique_pathways.update([pathway.strip() for pathway in pathways])
                            else:
                                unique_pathways.update([pathways.strip()])
                        
                        # Create a single entry with unique values as lists (not comma-separated strings)
                        career_guidance_selected = [{
                            'Areas': ', '.join(sorted(unique_areas)),
                            'Career_Clusters': sorted(unique_clusters),  # Keep as list for template iteration
                            'Career_Roles': sorted(unique_roles),  # Keep as list for template iteration
                            'Educational_Pathways': sorted(unique_pathways)  # Keep as list for template iteration
                        }]

                    # Append to result for Django template looping
                    result['career_guidance_selected'].extend(career_guidance_selected)

            except Exception as e:
                print(f"Error processing Aptitude Assessment data: {e}")



    except Exception as e:
        print(f"Error in career recommendations: {str(e)}")
    
    return result


@login_required
def Results_list(request):
    """Display list of all test results"""
    return render(request, "template20/app_post_matric/results_list.html", {
        'breadcrumb': get_breadcrumb([
            {'text': 'Tests', 'url': reverse('post_matric:tests')},
            {'text': 'Results', 'url': ''},
        ]),
    })

@login_required
def Results(request):
    try:
        from institute.models import StudentManagement
        from django.shortcuts import get_object_or_404
        
        embed_mode = (request.GET.get("embed") or "").strip() == "1"
        user_id = _staff_report_student_id_from_request(request)
        target_user = request.user
        viewing_student_report = False

        if user_id:
            try:
                uid = int(user_id)
                viewing_student_report = uid != int(request.user.id)
                if _staff_can_view_student_report(request, uid):
                    target_user = get_object_or_404(User, id=uid)
                elif not viewing_student_report:
                    target_user = request.user
                else:
                    target_user = request.user
                    viewing_student_report = False
            except (ValueError, TypeError):
                target_user = request.user
                viewing_student_report = False
        
        # Get test_id from query params or session
        test_id = request.GET.get('test_id', None)
        if test_id is not None:
            try:
                test_id = int(test_id)
            except ValueError:
                test_id = request.GET.get('test_id') or request.session.get('last_test_id')
        
        # Get the test session using direct parameters (fixes foreign key lookup issue)
        if test_id:
            try:
                test_id = int(test_id) if not isinstance(test_id, int) else test_id
                latest_session = TestSession.objects.filter(
                    user=target_user,
                    test_id=test_id,
                    is_completed=True
                ).order_by('-end_time').first()
            except (ValueError, TypeError):
                # Invalid test_id, query without it
                latest_session = TestSession.objects.filter(
                    user=target_user,
                    is_completed=True
                ).order_by('-end_time').first()
        else:
            latest_session = TestSession.objects.filter(
                user=target_user,
                is_completed=True
            ).order_by('-end_time').first()
        
        if not latest_session:
            _no_sess_display = _report_display_fields_for_student(target_user)
            return render(request, "results.html", {
                'error': 'No completed test found',
                'no_results': True,
                'viewing_student_report': viewing_student_report or (
                    embed_mode and getattr(target_user, "id", None) != getattr(request.user, "id", None)
                ),
                'embed_mode': embed_mode,
                'report_student_id': getattr(target_user, "id", None),
                'student_name': _no_sess_display["student_name"],
                'schoolname': _no_sess_display["schoolname"],
                'grade': _no_sess_display["grade"],
                'gender': _no_sess_display["gender"],
                'created_date': _no_sess_display["created_date"],
            })
        
        
        # Get categories record
        categories_record = TestTopCategories.objects.filter(
            user=target_user,
            test_paper=latest_session.test
        ).first()
        import ast
        # Extract high and low categories
        high_categories = []
        low_category = None

        
        if categories_record:
            if latest_session.test.title == 'Personality Assessment':
                high_categories = [cat.strip() for cat in ast.literal_eval(categories_record.high_category)]
            elif latest_session.test.title == 'Aptitude Assessment':
                raw = categories_record.high_category
                try:
                    high_categories = json.loads(raw) if raw else {}
                    if not isinstance(high_categories, dict):
                        high_categories = {}
                    else:
                        high_categories = normalize_aptitude_categories(high_categories)
                except (TypeError, ValueError):
                    high_categories = {}
            elif latest_session.test.title == 'Career Interest Inventory':
                high_categories = resolve_riasec_high_categories(
                    latest_session,
                    categories_record.high_category,
                )
            else:
                high_categories = categories_record.high_category
                high_categories = high_categories.strip("[]").strip() if high_categories else ''

            low_category = categories_record.low_category

        all_tests_completed = False

        # Check if all 4 tests are completed
        all_tests_completed = False
        
        # Check for completed sessions for each test type (subject user when staff views a student)
        _session_user = target_user if viewing_student_report else request.user
        test1_completed = TestSession.objects.filter(
            user=_session_user,
            test__id=1,
            is_completed=True,
        ).exists()

        test2_completed = TestSession.objects.filter(
            user=_session_user,
            test__id=2,
            is_completed=True,
        ).exists()

        test3_completed = TestSession.objects.filter(
            user=_session_user,
            test__id=3,
            is_completed=True,
        ).exists()

        test4_completed = TestSession.objects.filter(
            user=_session_user,
            test__id=4,
            is_completed=True,
        ).exists()
        
        if test1_completed and test2_completed and test3_completed and test4_completed:
            all_tests_completed = True

        report_user = target_user
        _display = _report_display_fields_for_student(
            report_user,
            session_end=latest_session.end_time or latest_session.created_at,
        )
        student_name = _display["student_name"]
        schoolname = _display["schoolname"]
        grade = _display["grade"]
        gender_display = _display["gender"]
        created_date = _display["created_date"]

        context = {
            'user': request.user,
            'viewing_student_report': viewing_student_report,
            'embed_mode': embed_mode,
            'report_student_id': report_user.id,
            'test_id': test_id,
            'all_tests_completed': all_tests_completed,
            'high_categories': high_categories,
            'low_category': low_category,
            'test_name': test_display_title(latest_session.test.title),
            'test_type': latest_session.test.title,
            'completed_at': latest_session.end_time,
            'completed_at_display': _format_ui_datetime(latest_session.end_time),
            'result_data': latest_session.result or {},
            'no_results': False,
            # Add user profile information
            'created_date': created_date if 'created_date' in locals() else None,
            'gender': gender_display if 'gender_display' in locals() else None,
            'schoolname': schoolname if 'schoolname' in locals() else None,
            'student_name': student_name if 'student_name' in locals() else None,
            'grade': grade if 'grade' in locals() else None
        }
        

        if test_id == 4:
            if isinstance(high_categories, dict):
                context['above_list'] = high_categories.get("Above Average", [])
                context['average_list'] = high_categories.get("Average", [])
                context['below_list'] = high_categories.get("Below Average", [])
            else:
                context['above_list'] = []
                context['average_list'] = []
                context['below_list'] = []
        else:
            pass
        
        # Load JSON data for all test types
        hexaco_data, riasec_data, motivation_data, aptitude_weak_areas_data , aptitude_strength_narrative_data, Aptitude_report_main_data, aptitude_recommendations_data, career_mergerd_path, CombinedReport_data, aptitude_interpretation_data = get_hexaco_or_riasec_career_mapping(latest_session)
        
        if aptitude_interpretation_data is None:
            aptitude_interpretation_data = {}
        
        # If it's a personality test (HEXACO), get career recommendations
        if latest_session.test.title == 'Personality Assessment' and high_categories:
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            # breakpoint()
            context.update({
                'careers_to_opt': hexaco_recommendations['careers_to_opt'],
                'careers_to_avoid': hexaco_recommendations['careers_to_avoid'],
                'high_trait_descriptions': hexaco_recommendations['high_trait_descriptions'],
                'low_trait_descriptions': hexaco_recommendations['low_trait_descriptions'],
                'high_traits': [map_hexaco_code_to_trait(cat) for cat in high_categories],
                'low_trait': map_hexaco_code_to_trait(low_category) if low_category else None,
                'dominant_trait_explanations': hexaco_recommendations.get('dominant_trait_explanations', []),
                'combined_code_explanation': hexaco_recommendations.get('combined_code_explanation', None)
            })

        elif latest_session.test.title == 'Career Interest Inventory' and high_categories:
            
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            context.update({
                'riasec_careers_to_opt': hexaco_recommendations['riasec_careers_to_opt'],
                'career_code_discription': hexaco_recommendations['career_code_discription'],
                'riasec_key_descriptions': hexaco_recommendations.get('riasec_key_descriptions', []),
                'riasec_key_drivers': hexaco_recommendations.get('riasec_key_drivers', []),
                'riasec_summaries': hexaco_recommendations.get('riasec_summaries', []),
            })
        elif latest_session.test.title == 'Motivation Assessment' and high_categories:
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            
            context.update({
                'high_categories': high_categories,
                'motivation_careers_to_opt': hexaco_recommendations['motivation_careers_to_opt'],
                'motivation_key_description': hexaco_recommendations.get('motivation_key_description', None),
                'motivation_key_drivers': hexaco_recommendations.get('motivation_key_drivers', []),
                'motivation_summary': hexaco_recommendations.get('motivation_summary', None),
            })
        elif latest_session.test.title == 'Aptitude Assessment' and high_categories:
            
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            from app.class12_aptitude_report_utils import aptitude_assessment_report_context

            context.update(
                aptitude_assessment_report_context(
                    high_categories,
                    aptitude_interpretation_data,
                    hexaco_recommendations,
                )
            )
        
        # Build test_results_data for JavaScript (pdf-results.js)
        test_results_data = []
        title = latest_session.test.title
        duration_minutes = 0
        if latest_session.start_time and latest_session.end_time:
            duration = latest_session.end_time - latest_session.start_time
            duration_minutes = int(duration.total_seconds() / 60)

        test_data = {
            'test_id': latest_session.test.id,
            'test_title': title,
            'duration_minutes': duration_minutes,
            'result_data': {},
            'responses': []
        }

        # Try to use stored TestResult first (most accurate)
        try:
            from .models import TestResult
            test_result = TestResult.objects.filter(session=latest_session).first()
            if test_result and test_result.result_data:
                stored_data = test_result.result_data
                if isinstance(stored_data, dict):
                    test_data['result_data'] = normalize_test_result_data_for_charts(
                        stored_data,
                        is_aptitude='Aptitude' in title,
                    )
                if test_result.category_counts:
                    test_data['category_counts'] = test_result.category_counts.copy()
            else:
                # Fallback: Aggregate results from stored responses
                responses = []
                try:
                    responses_obj = getattr(latest_session, 'responses', None)
                    if responses_obj is not None:
                        responses = list(responses_obj.all())
                        # Convert responses to serializable format
                        test_data['responses'] = []
                        for resp in responses:
                            if hasattr(resp, 'selected_answer') and resp.selected_answer:
                                test_data['responses'].append({
                                    'selected_answer': resp.selected_answer
                                })
                except Exception:
                    pass

                if 'Personality' in title:
                    test_data['result_data'] = {
                        'H': {'score': 0}, 'E': {'score': 0}, 'X': {'score': 0},
                        'A': {'score': 0}, 'C': {'score': 0}, 'O': {'score': 0}
                    }
                    for resp in responses:
                        if hasattr(resp, 'selected_answer') and resp.selected_answer:
                            ans = resp.selected_answer
                            if isinstance(ans, dict) and 'dimension' in ans:
                                dim = ans['dimension']
                                if dim in test_data['result_data']:
                                    try:
                                        test_data['result_data'][dim]['score'] += int(ans.get('score', 0))
                                    except Exception:
                                        pass

                elif 'Career' in title or 'Interest' in title:
                    test_data['result_data'] = {
                        'R': {'score': 0}, 'I': {'score': 0}, 'A': {'score': 0},
                        'S': {'score': 0}, 'E': {'score': 0}, 'C': {'score': 0}
                    }
                    for resp in responses:
                        if hasattr(resp, 'selected_answer') and resp.selected_answer:
                            ans = resp.selected_answer
                            if isinstance(ans, dict) and 'dimension' in ans:
                                dim = ans['dimension']
                                if dim in test_data['result_data']:
                                    try:
                                        test_data['result_data'][dim]['score'] += int(ans.get('score', 0))
                                    except Exception:
                                        pass

                elif 'Motivation' in title:
                    test_data['category_counts'] = {'Achievement': 0, 'Power': 0, 'Affiliation': 0}
                    for resp in responses:
                        if hasattr(resp, 'selected_answer') and resp.selected_answer:
                            ans = resp.selected_answer
                            if isinstance(ans, dict) and 'category' in ans:
                                cat = ans['category']
                                if cat in test_data['category_counts']:
                                    test_data['category_counts'][cat] += 1

                elif 'Aptitude' in title:
                    test_data['result_data'] = {}
                    for resp in responses:
                        if hasattr(resp, 'selected_answer') and resp.selected_answer:
                            ans = resp.selected_answer
                            if isinstance(ans, dict) and 'sections' in ans:
                                sections = ans['sections']
                                for section_name, section_data in sections.items():
                                    if section_name not in test_data['result_data']:
                                        test_data['result_data'][section_name] = 0
                                    if 'submitted_answers' in section_data:
                                        for _qid, qdata in section_data['submitted_answers'].items():
                                            if qdata.get('correct_answer') == qdata.get('selected_answer'):
                                                test_data['result_data'][section_name] += 1
        except Exception as e:
            logger.exception("Error getting test result data")

        test_results_data.append(test_data)

        # Attach JSON for client scripts (pdf-results.js will prefer this over API fetch)
        import json as _json
        context['test_results_json'] = _json.dumps(test_results_data)
        
        context['breadcrumb'] = get_breadcrumb([
            {'text': 'Tests', 'url': reverse('post_matric:tests')},
            {'text': 'Results', 'url': ''},
        ])
        return render(request, "results.html", context)    
        
    except Exception as e:
        return render(request, "results.html", {
            'error': f'An error occurred: {str(e)}',
            'no_results': True
        })


@login_required
def CombinedReport(request, user_id=None):
    try:
        embed_mode = (request.GET.get("embed") or "").strip() == "1"
        route_student_id = int(user_id) if user_id else None

        if route_student_id and not _staff_can_view_student_report(request, route_student_id):
            return render(
                request,
                "template20/app_post_matric/combined_report.html",
                {
                    "error": "You do not have permission to view this report.",
                    "no_results": True,
                    "embed_mode": embed_mode,
                    "report_student_id": route_student_id,
                    "profile_user": None,
                    "breadcrumb": get_breadcrumb([
                        {"text": "Tests", "url": reverse("post_matric:tests")},
                        {"text": "Results", "url": reverse("post_matric:results_list")},
                        {"text": "Combined Report", "url": ""},
                    ]),
                },
            )

        # Get the target user (student) whose report we want to view
        if route_student_id:
            target_user = get_object_or_404(User, id=route_student_id)
        else:
            target_user = request.user
            route_student_id = int(request.user.id)
        report_student_id = int(target_user.id)
        
        # Get completed test sessions for the TARGET USER (not the logged-in user)
        completed_sessions = TestSession.objects.filter(
            user=target_user,
            is_completed=True
        ).order_by('-end_time')
        
        if not completed_sessions:
            return render(request, "template20/app_post_matric/combined_report.html", {
                'error': 'No completed test found',
                'no_results': True,
                'user': target_user,
                'profile_user': target_user,
                'report_student_id': report_student_id,
                'embed_mode': embed_mode,
                'viewing_student_report': bool(
                    route_student_id and route_student_id != int(request.user.id)
                ),
                'breadcrumb': get_breadcrumb([
                    {'text': 'Tests', 'url': reverse('post_matric:tests')},
                    {'text': 'Results', 'url': reverse('post_matric:results_list')},
                    {'text': 'Combined Report', 'url': ''},
                ]),
            })

        user = target_user
        report_student_name = getattr(user, 'name', None) or user.email or str(user)
        report_student_email = getattr(user, 'email', None) or None
        report_student_mobile = getattr(user, 'mobile', None) or None
        report_student_class = None

        try:
            # Retrieve the UserProfile for the logged-in user (create if not exists)
            user_profile, created = UserProfile.objects.get_or_create(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        try:
            from institute.models import StudentManagement
            sm = (
                StudentManagement.objects.filter(student=user)
                .select_related("class_and_section")
                .order_by("-modified")
                .first()
            )
            if sm and getattr(sm, "class_and_section", None):
                report_student_class = getattr(sm.class_and_section, "class_and_section", None) or None
                _stream = getattr(sm.class_and_section, "stream", None) or ""
                if report_student_class and _stream:
                    report_student_class = f"{report_student_class} - {_stream}"
        except Exception:
            pass

        try:
            # Retrieve the UserProfile for the target user
            user_profile = user.user_profile
            # Access attributes from the User object
            first_session = completed_sessions[0]
            created_date = first_session.created_at if hasattr(first_session,'created_at') else first_session.end_time
            gender_value = user_profile.gender
            if gender_value == 10:  # GenderChoices.UNKNOWN
                gender_display = "Unknown"
            elif gender_value == 20:  # GenderChoices.MALE
                gender_display = "Male"
            elif gender_value == 30:  # GenderChoices.FEMALE
                gender_display = "Female"
            else:
                gender_display = "Unknown"  # Default fallback
            schoolname = user_profile.schoolname
            student_name = getattr(user, 'name', None) or user.email or str(user)
            grade = user_profile.grade
            if not report_student_class:
                report_student_class = grade
            if not report_student_mobile:
                report_student_mobile = getattr(user_profile, 'mobile', None) or report_student_mobile

        except UserProfile.DoesNotExist:
            print("UserProfile does not exist.")

        # Initialize context and containers
        viewing_student_report = bool(
            route_student_id is not None and route_student_id != int(request.user.id)
        )
        context = {
            'user': target_user,  # Use the target user, not request.user
            'profile_user': target_user,
            'report_student_id': report_student_id,
            'completed_tests': [],
            'no_results': False,
            'viewing_as_admin': viewing_student_report,
            'viewing_student_report': viewing_student_report,
            'embed_mode': embed_mode,
            # Add user profile information
            'created_date': created_date if 'created_date' in locals() else None,
            'gender': gender_display if 'gender_display' in locals() else None,
            'schoolname': schoolname if 'schoolname' in locals() else None,
            'student_name': student_name if 'student_name' in locals() else None,
            'grade': grade if 'grade' in locals() else None,
            'report_student_name': report_student_name,
            'report_student_email': report_student_email,
            'report_student_mobile': report_student_mobile,
            'report_student_class': report_student_class,
        }
        
        latest_sessions = {}
        
        # Process each completed session
        for session in completed_sessions:
            test_title = session.test.title
            
            # Only keep the latest session for each test type
            if test_title not in latest_sessions:
                latest_sessions[test_title] = session
                context['completed_tests'].append({
                    'title': test_title,
                    'display_title': test_display_title(test_title),
                    'completed_at': session.end_time,
                    'completed_at_display': _format_ui_datetime(session.end_time),
                    'test_id': session.test.id
                })

        context['completed_tests'].sort(
            key=lambda t: {1: 0, 2: 1, 3: 2, 4: 3}.get(t.get('test_id'), 99)
        )

        # -------------------- Build data for client charts (for target_user) --------------------
        # This allows institute users to view a student's charts without hitting /api/results/
        test_results_data = []
        for title, session in latest_sessions.items():
            # Duration in minutes
            duration_minutes = 0
            if session.start_time and session.end_time:
                duration = session.end_time - session.start_time
                duration_minutes = int(duration.total_seconds() / 60)

            test_data = {
                'test_id': session.test.id,
                'test_title': title,
                'duration_minutes': duration_minutes,
                'result_data': {}
            }

            # Try to use stored TestResult first (most accurate)
            try:
                test_result = TestResult.objects.filter(session=session).first()
                if test_result and test_result.result_data:
                    # Use stored result_data if available
                    stored_data = test_result.result_data
                    if isinstance(stored_data, dict):
                        test_data['result_data'] = normalize_test_result_data_for_charts(
                            stored_data,
                            is_aptitude='Aptitude' in title,
                        )
                    if test_result.category_counts:
                        test_data['category_counts'] = test_result.category_counts.copy()
                else:
                    # Fallback: Aggregate results from stored responses JSON
                    responses = []
                    try:
                        responses_obj = getattr(session, 'responses', None)
                        if responses_obj is not None:
                            responses = responses_obj.all()
                    except Exception:
                        responses = []

                    if 'Personality' in title:
                        # Sum scores per HEXACO dimension
                        test_data['result_data'] = {
                            'H': {'score': 0}, 'E': {'score': 0}, 'X': {'score': 0},
                            'A': {'score': 0}, 'C': {'score': 0}, 'O': {'score': 0}
                        }
                        for resp in responses:
                            if hasattr(resp, 'selected_answer') and resp.selected_answer:
                                ans = resp.selected_answer
                                if isinstance(ans, dict) and 'dimension' in ans:
                                    dim = ans['dimension']
                                    if dim in test_data['result_data']:
                                        try:
                                            test_data['result_data'][dim]['score'] += int(ans.get('score', 0))
                                        except Exception:
                                            pass

                    elif 'Career' in title or 'Interest' in title:
                        # RIASEC scores
                        test_data['result_data'] = {
                            'R': {'score': 0}, 'I': {'score': 0}, 'A': {'score': 0},
                            'S': {'score': 0}, 'E': {'score': 0}, 'C': {'score': 0}
                        }
                        for resp in responses:
                            if hasattr(resp, 'selected_answer') and resp.selected_answer:
                                ans = resp.selected_answer
                                if isinstance(ans, dict) and 'dimension' in ans:
                                    dim = ans['dimension']
                                    if dim in test_data['result_data']:
                                        try:
                                            test_data['result_data'][dim]['score'] += int(ans.get('score', 0))
                                        except Exception:
                                            pass

                    elif 'Motivation' in title:
                        # Category counts
                        test_data['category_counts'] = {'Achievement': 0, 'Power': 0, 'Affiliation': 0}
                        for resp in responses:
                            if hasattr(resp, 'selected_answer') and resp.selected_answer:
                                ans = resp.selected_answer
                                if isinstance(ans, dict) and 'category' in ans:
                                    cat = ans['category']
                                    if cat in test_data['category_counts']:
                                        test_data['category_counts'][cat] += 1

                    elif 'Aptitude' in title:
                        # Per-section correct counts
                        test_data['result_data'] = {}
                        for resp in responses:
                            if hasattr(resp, 'selected_answer') and resp.selected_answer:
                                ans = resp.selected_answer
                                if isinstance(ans, dict) and 'sections' in ans:
                                    sections = ans['sections']
                                    for section_name, section_data in sections.items():
                                        if section_name not in test_data['result_data']:
                                            test_data['result_data'][section_name] = 0
                                        if 'submitted_answers' in section_data:
                                            for _qid, qdata in section_data['submitted_answers'].items():
                                                if qdata.get('correct_answer') == qdata.get('selected_answer'):
                                                    test_data['result_data'][section_name] += 1
            except Exception as e:
                logger.exception("Error getting test result data (combined report)")

            test_results_data.append(test_data)

        # Attach JSON for client scripts (pdf-results.js will prefer this over API fetch)
        import json as _json
        context['test_results_json'] = _json.dumps(test_results_data)
        
        # Check if all 4 tests are completed FOR THE TARGET USER
        test1_completed = TestSession.objects.filter(
            user=target_user, 
            test__id=1,
            is_completed=True
        ).exists()
        
        test2_completed = TestSession.objects.filter(
            user=target_user, 
            test__id=2,
            is_completed=True
        ).exists()
        
        test3_completed = TestSession.objects.filter(
            user=target_user, 
            test__id=3,
            is_completed=True
        ).exists()
        
        test4_completed = TestSession.objects.filter(
            user=target_user, 
            test__id=4,
            is_completed=True
        ).exists()
        
        all_tests_completed = test1_completed and test2_completed and test3_completed and test4_completed
        context['all_tests_completed'] = all_tests_completed
        
        # Process each test type if available
        personality_session = latest_sessions.get('Personality Assessment')
        career_session = latest_sessions.get('Career Interest Inventory')
        motivation_session = latest_sessions.get('Motivation Assessment')
        aptitude_session = latest_sessions.get('Aptitude Assessment')
        
        # Process personality test data
        if personality_session:
            try:
                # Get categories record for personality test
                categories_record = TestTopCategories.objects.filter(
                    user=target_user,  # Use target_user instead of request.user
                    test_paper=personality_session.test
                ).first()
                
                if categories_record:
                    import ast
                    try:
                        high_categories = [cat.strip() for cat in ast.literal_eval(categories_record.high_category)]
                        low_category = categories_record.low_category
                        
                        hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, personality_session)
                        context.update({
                            'high_categories': high_categories,
                            'low_category': low_category,
                            'careers_to_opt': hexaco_recommendations['careers_to_opt'],
                            'careers_to_avoid': hexaco_recommendations['careers_to_avoid'],
                            'high_trait_descriptions': hexaco_recommendations['high_trait_descriptions'],
                            'low_trait_descriptions': hexaco_recommendations['low_trait_descriptions'],
                            'high_traits': [map_hexaco_code_to_trait(cat) for cat in high_categories],
                            'low_trait': map_hexaco_code_to_trait(low_category) if low_category else None
                        })
                    except (ValueError, SyntaxError) as e:
                        logger.exception("Error parsing personality categories")
            except Exception as e:
                logger.exception("Error processing personality test data")

        # Process career interest data
        if career_session:
            try:
                # Get categories record for career interest test
                categories_record = TestTopCategories.objects.filter(
                    user=target_user,  # Use target_user instead of request.user
                    test_paper=career_session.test
                ).first()
                
                if categories_record:
                    try:
                        high_categories = resolve_riasec_high_categories(
                            career_session,
                            categories_record.high_category,
                        )
                        low_category = categories_record.low_category
                        
                        hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, career_session)
                        context.update({
                            'riasec_high_categories': high_categories,
                            'riasec_careers_to_opt': hexaco_recommendations['riasec_careers_to_opt'],
                            'career_code_discription': hexaco_recommendations['career_code_discription'],
                        })
                    except Exception as e:
                        logger.exception("Error processing career interest data")
            except Exception as e:
                logger.exception("Error processing career session data")
            
        # Process motivation data
        if motivation_session:
            try:
                # Get categories record for motivation test
                categories_record = TestTopCategories.objects.filter(
                    user=target_user,  # Use target_user instead of request.user
                    test_paper=motivation_session.test
                ).first()
                
                if categories_record:
                    try:
                        high_categories = categories_record.high_category
                        low_category = categories_record.low_category
                        
                        hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, motivation_session)
                        context.update({
                            'motivation_high_category': high_categories,
                            'motivation_careers_to_opt': hexaco_recommendations['motivation_careers_to_opt'],
                            'motivation_key_description': hexaco_recommendations.get('motivation_key_description', None),
                            'motivation_key_drivers': hexaco_recommendations.get('motivation_key_drivers', []),
                            'motivation_summary': hexaco_recommendations.get('motivation_summary', None),
                        })
                    except Exception as e:
                        logger.exception("Error processing motivation data")
            except Exception as e:
                logger.exception("Error processing motivation session data")
            
        # Process aptitude data
        if aptitude_session:
            try:
                # Get categories record for aptitude test
                categories_record = TestTopCategories.objects.filter(
                    user=target_user,  # Use target_user instead of request.user
                    test_paper=aptitude_session.test
                ).first()
                
                if categories_record:
                    try:
                        import json
                        high_categories = json.loads(categories_record.high_category)
                        if isinstance(high_categories, dict):
                            high_categories = normalize_aptitude_categories(high_categories)
                        
                        # Prepare aptitude lists and 2-digit codes
                        above_list = high_categories.get("Above Average", [])
                        average_list = high_categories.get("Average", [])
                        below_list = high_categories.get("Below Average", [])
                        
                        # Map full aptitude names to their 2-letter codes
                        def map_aptitude_name_to_code(name):
                            name = name.strip().lower()
                            mapping = {
                                'abstract reasoning': 'AR',
                                'numerical reasoning': 'NR',
                                'logical reasoning': 'LR',
                                'language & verbal reasoning': 'LVR',
                                'language and verbal reasoning': 'LVR',
                                'mechanical reasoning': 'MR',
                                'spatial reasoning': 'SR',
                                'clerical speed & accuracy': 'CR',
                                'clerical speed and accuracy': 'CR',
                                'clerical': 'CR',
                            }
                            return mapping.get(name, None)
                        
                        # Helper to get 2-letters, if code is 3 letters, use first letter and last (e.g. LVR -> LR)
                        def normalize_code(code):
                            if code is None:
                                return None
                            # if len(code) == 2:
                            #     return code
                            # elif len(code) == 3:
                            #     # specific mapping - LVR (Language & Verbal Reasoning) -> LR (Verbal/Logical Reasoning)
                            #     if code == "LVR":
                            #         return "LR"
                            #     return code[:2]
                            return code
                        
                        # Combine all aptitudes to get an unique code for the combination (sorted for consistency)
                        all_selected_names = []
                        all_selected_names.extend(above_list)
                        all_selected_names.extend(average_list)
                        # (We skip below, as we often want only strengths/averages for combination mapping)
                        aptitude_codes = [normalize_code(map_aptitude_name_to_code(name)) for name in all_selected_names if map_aptitude_name_to_code(name) is not None]
                        logger.debug("aptitude_codes: %s", aptitude_codes)
                        # Only keep unique and non-None
                        aptitude_codes = sorted(list(set(aptitude_codes)))
                        logger.debug("aptitude_codes (sorted): %s", aptitude_codes)
                        # Generate final two-letter combo code (alpha order), e.g., ["AR", "NR"] => "AR_NR"
                        two_digit_combo_code = "+".join(aptitude_codes)
                        logger.debug("two_digit_combo_code: %s", two_digit_combo_code)

                        # Add to context: test name and generated combo code
                        context.update({
                            'above_list': above_list,
                            'average_list': average_list,
                            'below_list': below_list,
                            'aptitude_test_name': aptitude_session.test.title if hasattr(aptitude_session, 'test') else "Aptitude Assessment",
                            'aptitude_combination_code': two_digit_combo_code,
                        })
                        # This combo code (two_digit_combo_code) is to be used for matching in db [AptitudeCombinationMapping]
                        logger.debug("high_categories: %s", high_categories)
                        hexaco_recommendations = get_hexaco_career_recommendations(high_categories, None, aptitude_session)
                        context.update({
                            'aptitude_improvement_plan': hexaco_recommendations['aptitude_improvement_plan'],
                            'aptitude_strength_narrative': hexaco_recommendations['aptitude_strength_narrative'],
                            'aptitude_Recommended_College_Courses': hexaco_recommendations['aptitude_Recommended_College_Courses'],
                            'aptitude_course_recommendation_cards': hexaco_recommendations.get('aptitude_course_recommendation_cards', []),
                            'aptitude_roles_guidance': hexaco_recommendations['aptitude_roles_guidance'],
                            'career_guidance_selected': hexaco_recommendations['career_guidance_selected'],
                        })
                        
                        # print("hexaco_recommendations['aptitude_improvement_plan']: ", hexaco_recommendations['aptitude_improvement_plan'])
                        # print("hexaco_recommendations['aptitude_strength_narrative']: ", hexaco_recommendations['aptitude_strength_narrative'])
                        # print("hexaco_recommendations['aptitude_Recommended_College_Courses']: ", hexaco_recommendations['aptitude_Recommended_College_Courses'])
                        # print("hexaco_recommendations['aptitude_roles_guidance']: ", hexaco_recommendations['aptitude_roles_guidance'])
                        # print("hexaco_recommendations['career_guidance_selected']: ", hexaco_recommendations['career_guidance_selected'])
                        # print("len(hexaco_recommendations['career_guidance_selected']): ", len(hexaco_recommendations['career_guidance_selected']))
                        # Fetch AptitudeCombinationMapping data based on aptitude codes
                        # (do not import `reverse` here — it shadows the module import and breaks
                        # earlier/later uses of reverse() in this function via UnboundLocalError)
                        from django.utils.html import format_html
                        from careers.models import CareerCluster
                        from courses.models import Course
                        
                        # Map full aptitude names to codes
                        def map_aptitude_name_to_code(name):
                            """Convert full aptitude name to code"""
                            name_lower = name.lower().strip()
                            mapping = {
                                'abstract reasoning': 'AR',
                                'numerical reasoning': 'NR',
                                'logical reasoning': 'LR',
                                'language & verbal reasoning': 'LVR',
                                'language and verbal reasoning': 'LVR',
                                'mechanical reasoning': 'MR',
                                'spatial reasoning': 'SR',
                                'clerical speed & accuracy': 'CR',
                                'clerical speed and accuracy': 'CR',
                                'clerical': 'CR',
                            }
                            return mapping.get(name_lower, None)
                        
                        # Collect aptitude names and convert to codes
                        # ONLY use Above Average + Average - exclude Below Average for clusters/roles/pathways
                        all_aptitude_names = []
                        all_aptitude_names.extend(high_categories.get("Above Average", []))
                        all_aptitude_names.extend(high_categories.get("Average", []))
                        # Below Average is excluded - not used for combination mapping
                        
                        # Convert names to codes (keep original order, do not sort)
                        aptitude_codes = []
                        for name in all_aptitude_names:
                            code = map_aptitude_name_to_code(name)
                            if code and code not in aptitude_codes:
                                aptitude_codes.append(code)
                                
                        
                        logger.debug(f"Aptitude codes extracted: {aptitude_codes} ({len(aptitude_codes)} codes) - ORIGINAL ORDER (not sorted)")
                        
                        # Generate all possible combinations from user's codes
                        # Check BOTH original order AND sorted order to match database entries
                        codes_to_check = []
                        
                        # First: Generate combinations in ORIGINAL ORDER (as extracted)
                        logger.debug(f"Generating combinations from ORIGINAL order: {aptitude_codes}")
                        from itertools import combinations
                        for r in range(len(aptitude_codes), 0, -1):  # Start from longest
                            for combo in combinations(aptitude_codes, r):
                                combo_str = '+'.join(combo)  # Format: "CR+LVR+NR" (original order)
                                if combo_str not in codes_to_check:
                                    codes_to_check.append(combo_str)
                        
                        # Second: Also generate combinations in SORTED ORDER (for database matching)
                        sorted_codes = sorted(aptitude_codes)
                        if sorted_codes != aptitude_codes:
                            logger.debug(f"Also generating combinations from SORTED order: {sorted_codes}")
                            for r in range(len(sorted_codes), 0, -1):  # Start from longest
                                for combo in combinations(sorted_codes, r):
                                    combo_str = '+'.join(combo)  # Format: "CR+LVR+NR" (sorted order)
                                    if combo_str not in codes_to_check:
                                        codes_to_check.append(combo_str)
                        
                        logger.debug(f"codes_to_check: {codes_to_check} (total: {len(codes_to_check)} combinations to check)")
                        
                        # Compare aptitude_codes with AptitudeCombinationMapping in database
                        # Find the best matching combination (longest/most comprehensive match)
                        best_mapping = None
                        best_code = None
                        checked_count = 0
                        found_matches = []
                        
                        # Check what combinations exist in database for these codes (handle missing table gracefully)
                        all_db_codes = []
                        matching_db_codes = []
                        codes_set = set(aptitude_codes)
                        
                        try:
                            # Check if table exists
                            from django.db import connection
                            with connection.cursor() as cursor:
                                cursor.execute("SHOW TABLES LIKE 'app_post_matric_aptitudecombinationmapping'")
                                table_exists = cursor.fetchone() is not None
                            
                            if table_exists:
                                all_db_codes = list(AptitudeCombinationMapping.objects.values_list('aptitude_code', flat=True))
                                for db_code in all_db_codes:
                                    db_codes_list = db_code.split('+')
                                    if set(db_codes_list) == codes_set:  # Same codes, different order
                                        matching_db_codes.append(db_code)
                            else:
                                logger.debug("[DEBUG] AptitudeCombinationMapping table does not exist - skipping mapping")
                        except Exception as e:
                            logger.debug(f"[DEBUG] Error accessing AptitudeCombinationMapping table (non-critical): {str(e)}")
                            all_db_codes = []
                        
                        logger.debug(f"\n🔍 Comparing aptitude_codes ({aptitude_codes}) with AptitudeCombinationMapping in database...")
                        if matching_db_codes:
                            logger.debug(f"   Found matching codes in DB (same codes, different order): {matching_db_codes}")
                        logger.debug(f"   Checking combinations in order (longest to shortest)...")
                        
                        # Check combinations in order (longest first)
                        for code in codes_to_check:
                            checked_count += 1
                            try:
                                # print(f"   [{checked_count}] Checking: {code}")
                                mapping = AptitudeCombinationMapping.objects.filter(aptitude_code=code).first()
                                if mapping:
                                    found_matches.append({
                                        'code': code,
                                        'areas': mapping.aptitude_areas,
                                        'clusters_count': mapping.clusters.count(),
                                        'roles_count': mapping.roles.count(),
                                        'pathways_count': mapping.pathways.count()
                                    })
                                    # print(f"      ✓ MATCH FOUND in database: {code}")
                                    # print(f"      Areas: {mapping.aptitude_areas}")
                                    # print(f"      Clusters: {mapping.clusters.count()}, Roles: {mapping.roles.count()}, Pathways: {mapping.pathways.count()}")
                                # else:
                                #     print(f"      ✗ Not found: {code}")
                            except Exception as e:
                                logger.debug(f"      ❌ Error checking {code}: {e}")
                        
                        # If no exact match found, try matching_db_codes (same codes, different order)
                        if not found_matches and matching_db_codes:
                            logger.debug(f"\n   No exact order match found. Trying matching codes from DB (different order)...")
                            for db_code in matching_db_codes:
                                checked_count += 1
                                try:
                                    # print(f"   [{checked_count}] Checking DB code: {db_code}")
                                    mapping = AptitudeCombinationMapping.objects.filter(aptitude_code=db_code).first()
                                    if mapping:
                                        found_matches.append({
                                            'code': db_code,
                                            'areas': mapping.aptitude_areas,
                                            'clusters_count': mapping.clusters.count(),
                                            'roles_count': mapping.roles.count(),
                                            'pathways_count': mapping.pathways.count()
                                        })
                                        # print(f"      ✓ MATCH FOUND in database: {db_code}")
                                        # print(f"      Areas: {mapping.aptitude_areas}")
                                        # print(f"      Clusters: {mapping.clusters.count()}, Roles: {mapping.roles.count()}, Pathways: {mapping.pathways.count()}")
                                        # Add to codes_to_check for processing
                                        if db_code not in codes_to_check:
                                            codes_to_check.append(db_code)
                                except Exception as e:
                                    logger.debug(f"      ❌ Error checking {db_code}: {e}")
                        
                        # Process the best match (prioritize complete matches with all codes)
                        # Check matching_db_codes first if it has entries with all codes
                        match_code_to_use = None
                        total_codes_count = len(aptitude_codes)
                        
                        # Prioritize matching_db_codes if it contains entries with all codes
                        if matching_db_codes:
                            # Check if any matching_db_code has all codes
                            for db_code in matching_db_codes:
                                db_code_count = len(db_code.split('+'))
                                if db_code_count == total_codes_count:
                                    match_code_to_use = db_code
                                    logger.debug(f"\n   ✅ Using complete DB match (all {total_codes_count} codes): {match_code_to_use}")
                                    break
                        
                        # If no complete match in matching_db_codes, use found_matches
                        if not match_code_to_use and found_matches:
                            # Use the longest match from codes_to_check
                            match_code_to_use = found_matches[0]['code']
                            logger.debug(f"\n   ✅ Using match from codes_to_check: {match_code_to_use}")
                        elif not match_code_to_use and matching_db_codes:
                            # Fallback to first matching_db_code
                            match_code_to_use = matching_db_codes[0]
                            logger.debug(f"\n   ✅ Using DB match (different order): {match_code_to_use}")
                        
                        # Get clusters, roles, pathways from the matched code
                        if match_code_to_use:
                            try:
                                mapping = AptitudeCombinationMapping.objects.filter(aptitude_code=match_code_to_use).first()
                                if mapping:
                                    # Get clusters with hyperlinks
                                    clusters_data = []
                                    for cluster in mapping.clusters.all():
                                        try:
                                            safe_slug = (cluster.slug or slugify(cluster.name or '') or 'cluster')
                                            url = reverse('careers:careerlibrary', kwargs={'cluster_slug': safe_slug, 'cluster_id': cluster.id})
                                            clusters_data.append({
                                                'name': cluster.name,
                                                'url': url
                                            })
                                        except Exception as e:
                                            logger.debug(f"Error creating cluster URL for {cluster.name}: {e}")
                                            clusters_data.append({
                                                'name': cluster.name,
                                                'url': None
                                            })
                                    
                                    # Get roles with hyperlinks
                                    roles_data = []
                                    for role in mapping.roles.all():
                                        try:
                                            url = reverse('careers:careerdetail', kwargs={'slug': role.slug, 'career_id': role.id})
                                            roles_data.append({
                                                'name': role.name,
                                                'url': url
                                            })
                                        except Exception as e:
                                            logger.debug(f"Error creating role URL for {role.name}: {e}")
                                            roles_data.append({
                                                'name': role.name,
                                                'url': None
                                            })
                                    
                                    # Get pathways with hyperlinks
                                    pathways_data = []
                                    for pathway in mapping.pathways.all():
                                        try:
                                            # Use public course URL that students can access
                                            url = reverse('courses:coursedetail', kwargs={'course_id': pathway.id})
                                            pathways_data.append({
                                                'name': pathway.name,
                                                'url': url
                                            })
                                        except Exception as e:
                                            logger.debug(f"Error creating pathway URL for {pathway.name}: {e}")
                                            pathways_data.append({
                                                'name': pathway.name,
                                                'url': None
                                            })
                                    
                                    # Store the mapping if it has data
                                    if clusters_data or roles_data or pathways_data:
                                        best_mapping = {
                                            'aptitude_code': match_code_to_use,
                                            'aptitude_areas': mapping.aptitude_areas,
                                            'clusters': clusters_data,
                                            'roles': roles_data,
                                            'pathways': pathways_data
                                        }
                                        best_code = match_code_to_use
                                        logger.debug(f"   ✅ SELECTED: {best_code} (matching combination with data)")
                                    else:
                                        logger.debug(f"   ⚠ Found but no data (clusters/roles/pathways empty)")
                            except Exception as e:
                                logger.debug(f"   ❌ Error processing {match_code_to_use}: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # Summary of matching results
                        # print(f"\n📊 Matching Summary:")
                        # print(f"   Aptitude codes extracted: {aptitude_codes} (original order, not sorted)")
                        # print(f"   Total combinations checked: {checked_count}")
                        # print(f"   Matches found in database: {len(found_matches)}")
                        # if found_matches:
                        #     print(f"   All matches found:")
                        #     for match in found_matches:
                        #         print(f"      - {match['code']}: {match['areas']}")
                        
                        # Store the best mapping in context (clusters, roles, pathways from DB)
                        context['aptitude_mapping'] = best_mapping
                        if best_mapping:
                            logger.debug(f"\n✅ FINAL RESULT - Displaying from database:")
                            logger.debug(f"   Aptitude Code: {best_code}")
                            logger.debug(f"   Aptitude Areas: {best_mapping['aptitude_areas']}")
                            logger.debug(f"   Clusters: {len(best_mapping['clusters'])}")
                            logger.debug("   Clusters:")
                            for cluster in best_mapping['clusters']:
                                logger.debug(f"      - {cluster['name']}")
                            logger.debug(f"   Roles: {len(best_mapping['roles'])}")
                            logger.debug("   Roles:")
                            for role in best_mapping['roles']:
                                logger.debug(f"      - {role['name']}")
                            logger.debug(f"   Pathways: {len(best_mapping['pathways'])}")
                            logger.debug("   Pathways:")
                            for pathway in best_mapping['pathways']:
                                logger.debug(f"      - {pathway['name']}")
                        else:
                            logger.debug(f"\n⚠️  NO MATCH FOUND!")
                            logger.debug(f"   Extracted codes: {aptitude_codes}")
                            logger.debug(f"   Checked {len(codes_to_check)} combinations but none matched in AptitudeCombinationMapping")
                            logger.debug(f"   Make sure the combination exists in the database")
                    except json.JSONDecodeError as e:
                        logger.debug(f"Error decoding aptitude categories JSON: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
                    except Exception as e:
                        logger.debug(f"Error processing aptitude data: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
            except Exception as e:
                logger.exception("Error processing aptitude session data")

        # Build psychometric career clusters fallback (used when aptitude clusters are missing)
        try:
            import re
            psychometric_careers = []

            # Personality careers_to_opt can be dict(trait -> [careers]) or list
            personality_careers = context.get('careers_to_opt', [])
            if isinstance(personality_careers, dict):
                for items in personality_careers.values():
                    if isinstance(items, list):
                        psychometric_careers.extend(items)
            elif isinstance(personality_careers, list):
                psychometric_careers.extend(personality_careers)

            # RIASEC careers_to_opt is generally dict(category -> [careers])
            riasec_careers = context.get('riasec_careers_to_opt', [])
            if isinstance(riasec_careers, dict):
                for items in riasec_careers.values():
                    if isinstance(items, list):
                        psychometric_careers.extend(items)
            elif isinstance(riasec_careers, list):
                psychometric_careers.extend(riasec_careers)

            # Add aptitude recommended roles as additional psychometric signals
            aptitude_roles_guidance = context.get('aptitude_roles_guidance', []) or []
            for area_group in aptitude_roles_guidance:
                if not isinstance(area_group, dict):
                    continue
                for role_item in area_group.get('Recommendations', []) or []:
                    if isinstance(role_item, dict):
                        role_name = role_item.get('Role')
                    else:
                        role_name = role_item
                    if role_name:
                        psychometric_careers.append(role_name)

            cleaned_career_names = []
            seen_names = set()
            for name in psychometric_careers:
                clean_name = str(name or '').strip()
                if not clean_name:
                    continue
                lowered = clean_name.lower()
                if lowered in seen_names:
                    continue
                seen_names.add(lowered)
                cleaned_career_names.append(clean_name)

            psychometric_clusters = []
            if cleaned_career_names:
                # Normalize name to improve matching between recommendation labels and Career.name
                def _normalize_name(text):
                    return re.sub(r'[^a-z0-9]+', '', str(text or '').lower()).strip()

                normalized_targets = set(_normalize_name(name) for name in cleaned_career_names if name)

                # First pass: published careers
                from core import choices
                career_qs = Career.objects.filter(
                    publish_status=choices.PublishStatus.PUBLISHED
                ).prefetch_related('career_cluster')
                if not career_qs.exists():
                    # Fallback if publish flag is not maintained in this environment
                    career_qs = Career.objects.all().prefetch_related('career_cluster')

                cluster_seen = set()
                matched_any = False
                for career_obj in career_qs:
                    normalized_db_name = _normalize_name(getattr(career_obj, 'name', ''))
                    if normalized_db_name not in normalized_targets:
                        continue
                    matched_any = True
                    for cluster in career_obj.career_cluster.all():
                        cluster_name = str(getattr(cluster, 'name', '') or '').strip()
                        if not cluster_name:
                            continue
                        key = cluster_name.lower()
                        if key in cluster_seen:
                            continue
                        cluster_seen.add(key)
                        cluster_url = None
                        try:
                            safe_slug = (cluster.slug or slugify(cluster_name) or 'cluster')
                            cluster_url = reverse(
                                'careers:careerlibrary',
                                kwargs={'cluster_slug': safe_slug, 'cluster_id': cluster.id}
                            )
                        except Exception:
                            cluster_url = None
                        psychometric_clusters.append({
                            'name': cluster_name,
                            'url': cluster_url
                        })

                # Second pass fallback: loose contains matching when exact normalized names do not match
                if not matched_any:
                    for rec_name in cleaned_career_names:
                        token = str(rec_name or '').strip()
                        if not token:
                            continue
                        loose_qs = Career.objects.filter(name__icontains=token[:40]).prefetch_related('career_cluster')[:10]
                        for career_obj in loose_qs:
                            for cluster in career_obj.career_cluster.all():
                                cluster_name = str(getattr(cluster, 'name', '') or '').strip()
                                if not cluster_name:
                                    continue
                                key = cluster_name.lower()
                                if key in cluster_seen:
                                    continue
                                cluster_seen.add(key)
                                cluster_url = None
                                try:
                                    safe_slug = (cluster.slug or slugify(cluster_name) or 'cluster')
                                    cluster_url = reverse(
                                        'careers:careerlibrary',
                                        kwargs={'cluster_slug': safe_slug, 'cluster_id': cluster.id}
                                    )
                                except Exception:
                                    cluster_url = None
                                psychometric_clusters.append({
                                    'name': cluster_name,
                                    'url': cluster_url
                                })

            context['psychometric_career_clusters'] = sorted(
                psychometric_clusters,
                key=lambda item: str(item.get('name', '')).lower()
            )
        except Exception as e:
            logger.warning(f"Error building psychometric_career_clusters: {e}")
            context['psychometric_career_clusters'] = []

        # Build cluster name -> URL map for template linking of text-only cluster sources
        # Includes common aliases so DB clusters still link when recommendation text varies
        # (e.g. "&" vs "and", punctuation differences, repeated spaces).
        try:
            cluster_url_map = {}
            for cluster in CareerCluster.objects.all().only('id', 'slug', 'name'):
                cluster_name = str(getattr(cluster, 'name', '') or '').strip()
                if not cluster_name:
                    continue
                try:
                    safe_slug = (cluster.slug or slugify(cluster_name) or 'cluster')
                    cluster_url = reverse(
                        'careers:careerlibrary',
                        kwargs={'cluster_slug': safe_slug, 'cluster_id': cluster.id}
                    )
                except Exception:
                    cluster_url = None

                for key in career_cluster_label_lookup_keys(cluster_name):
                    if key in cluster_url_map:
                        continue
                    cluster_url_map[key] = cluster_url

            # Report JSON uses short labels; map them to live CareerCluster title + career library URL.
            cluster_resolve_map = {}

            def _resolve_entry_for_cluster_obj(cluster):
                if not cluster:
                    return None
                try:
                    safe_slug = (cluster.slug or slugify(cluster.name or '') or 'cluster')
                    url = reverse(
                        'careers:careerlibrary',
                        kwargs={'cluster_slug': safe_slug, 'cluster_id': cluster.id},
                    )
                except Exception:
                    url = None
                display = str(getattr(cluster, 'name', '') or '').strip()
                if not display:
                    return None
                return {'name': display, 'url': url}

            def _merge_cluster_resolve_keys(raw_label, cluster, overwrite=False):
                entry = _resolve_entry_for_cluster_obj(cluster)
                if not entry:
                    return
                for key in career_cluster_label_lookup_keys(raw_label):
                    if not key:
                        continue
                    if overwrite or key not in cluster_resolve_map:
                        cluster_resolve_map[key] = entry

            mapping_path = os.path.join(
                settings.BASE_DIR, 'static', 'data', 'combined_report_data', 'excel_to_db_mapping.json',
            )
            if os.path.isfile(mapping_path):
                try:
                    with open(mapping_path, 'r', encoding='utf-8') as f:
                        mapping_json = json.load(f)
                    for raw_label, targets in (mapping_json.get('cluster_mappings') or {}).items():
                        if not targets or not isinstance(targets, list):
                            continue
                        cid = targets[0].get('id')
                        if not cid:
                            continue
                        cluster = CareerCluster.objects.filter(pk=cid).first()
                        _merge_cluster_resolve_keys(raw_label, cluster, overwrite=False)
                except Exception as ex:
                    logger.warning("Error loading excel_to_db_mapping cluster_mappings: %s", ex)

            label_ids_path = os.path.join(
                settings.BASE_DIR, 'static', 'data', 'report_cluster_label_ids.json',
            )
            if os.path.isfile(label_ids_path):
                try:
                    with open(label_ids_path, 'r', encoding='utf-8') as f:
                        label_id_map = json.load(f)
                    for raw_label, cid in (label_id_map or {}).items():
                        cluster = CareerCluster.objects.filter(pk=cid).first()
                        _merge_cluster_resolve_keys(str(raw_label), cluster, overwrite=False)
                except Exception as ex:
                    logger.warning("Error loading report_cluster_label_ids.json: %s", ex)

            try:
                for cm in ClusterMapping.objects.select_related('db_cluster').filter(
                    db_cluster__isnull=False,
                ):
                    _merge_cluster_resolve_keys(cm.excel_name, cm.db_cluster, overwrite=True)
            except Exception as ex:
                logger.warning("Error merging ClusterMapping into cluster_resolve_map: %s", ex)

            enrich_combined_report_cluster_links(context, cluster_resolve_map, cluster_url_map)

            context['cluster_resolve_map'] = cluster_resolve_map
            context['cluster_url_map'] = cluster_url_map
        except Exception as e:
            logger.warning("Error building cluster_url_map: %s", e)
            context['cluster_url_map'] = {}
            context['cluster_resolve_map'] = {}
        
        context['breadcrumb'] = get_breadcrumb([
            {'text': 'Tests', 'url': reverse('post_matric:tests')},
            {'text': 'Results', 'url': reverse('post_matric:results_list')},
            {'text': 'Combined Report', 'url': ''},
        ])

        # Provide aptitude banding from backend (Above/Average/Below) for charts
        import json as _json
        context['aptitude_band_json'] = _json.dumps({
            'above': context.get('above_list', []) or [],
            'average': context.get('average_list', []) or [],
            'below': context.get('below_list', []) or [],
        })
        return render(request, "template20/app_post_matric/combined_report.html", context)
        
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.exception("Error in CombinedReport")
        return render(request, "template20/app_post_matric/combined_report.html", {
            'error': f'An error occurred: {str(e)}',
            'traceback': trace,
            'no_results': True,
            'embed_mode': (request.GET.get("embed") or "").strip() == "1",
            'report_student_id': user_id,
            'profile_user': None,
            'viewing_student_report': False,
            'breadcrumb': get_breadcrumb([
                {'text': 'Tests', 'url': reverse('post_matric:tests')},
                {'text': 'Results', 'url': reverse('post_matric:results_list')},
                {'text': 'Combined Report', 'url': ''},
            ]),
        })


# def CombinedReport(request, user_id=None):
#     try:
#         print("user_id:", user_id)
        
#         # Get the target user (student) whose report we want to view
#         if user_id:
#             target_user = get_object_or_404(User, id=user_id)
#             print(f"Viewing report for student: {target_user}")
#         else:
#             target_user = request.user
#             print(f"Viewing own report as: {target_user}")
        
#         # Get completed test sessions for the TARGET USER
#         completed_sessions = TestSession.objects.filter(
#             user=target_user,
#             is_completed=True
#         ).order_by('-end_time')
        
#         if not completed_sessions:
#             return render(request, "combined_report.html", {
#                 'error': 'No completed test found',
#                 'no_results': True,
#                 'user': target_user
#             })

#         # Initialize context and containers
#         context = {
#             'user': target_user,
#             'completed_tests': [],
#             'no_results': False,
#             'viewing_as_admin': user_id is not None
#         }
        
#         # Prepare test results data for JavaScript
#         test_results_data = []
        
#         latest_sessions = {}
        
#         # Process each completed session
#         for session in completed_sessions:
#             test_title = session.test.title
            
#             # Only keep the latest session for each test type
#             if test_title not in latest_sessions:
#                 latest_sessions[test_title] = session
                
#                 # Calculate duration in minutes
#                 duration_minutes = 0
#                 if session.start_time and session.end_time:
#                     duration = session.end_time - session.start_time
#                     duration_minutes = int(duration.total_seconds() / 60)
                
#                 context['completed_tests'].append({
#                     'title': test_title,
#                     'completed_at': session.end_time,
#                     'test_id': session.test.id
#                 })
                
#                 # Add session data for JavaScript
#                 test_data = {
#                     'test_id': session.test.id,
#                     'test_title': test_title,
#                     'duration_minutes': duration_minutes,  # Use calculated duration
#                     'result_data': {}  # Will be populated based on test type
#                 }
                
#                 # Get test-specific data
#                 if 'Personality' in test_title:
#                     # Get personality test data
#                     try:
#                         categories_record = TestTopCategories.objects.filter(
#                             user=target_user,
#                             test_paper=session.test
#                         ).first()
                        
#                         if categories_record:
#                             import ast
#                             try:
#                                 high_categories = ast.literal_eval(categories_record.high_category)
#                                 test_data['result_data'] = {
#                                     'H': {'score': 0},
#                                     'E': {'score': 0},
#                                     'X': {'score': 0},
#                                     'A': {'score': 0},
#                                     'C': {'score': 0},
#                                     'O': {'score': 0}
#                                 }
                                
#                                 # Get actual scores from test responses - FIX HERE
#                                 responses = session.responses.all()  # Changed from testresponse_set to responses
#                                 for response in responses:
#                                     if hasattr(response, 'selected_answer') and response.selected_answer:
#                                         answer_data = response.selected_answer
#                                         if isinstance(answer_data, dict) and 'dimension' in answer_data:
#                                             dim = answer_data['dimension']
#                                             if dim in test_data['result_data']:
#                                                 test_data['result_data'][dim]['score'] += int(answer_data.get('score', 0))
#                             except (ValueError, SyntaxError) as e:
#                                 print(f"Error parsing personality categories: {e}")
#                     except Exception as e:
#                         print(f"Error processing personality data for JS: {e}")
#                         import traceback
#                         print(traceback.format_exc())
                
#                 elif 'Career' in test_title or 'Interest' in test_title:
#                     # Get career interest data
#                     try:
#                         test_data['result_data'] = {
#                             'R': {'score': 0},
#                             'I': {'score': 0},
#                             'A': {'score': 0},
#                             'S': {'score': 0},
#                             'E': {'score': 0},
#                             'C': {'score': 0}
#                         }
                        
#                         # Get scores from responses - FIX HERE
#                         responses = session.responses.all()  # Changed from testresponse_set to responses
#                         for response in responses:
#                             if hasattr(response, 'selected_answer') and response.selected_answer:
#                                 answer_data = response.selected_answer
#                                 if isinstance(answer_data, dict) and 'dimension' in answer_data:
#                                     dim = answer_data['dimension']
#                                     if dim in test_data['result_data']:
#                                         test_data['result_data'][dim]['score'] += int(answer_data.get('score', 0))
#                     except Exception as e:
#                         print(f"Error processing career data for JS: {e}")
                
#                 elif 'Motivation' in test_title:
#                     # Get motivation data
#                     try:
#                         categories_record = TestTopCategories.objects.filter(
#                             user=target_user,
#                             test_paper=session.test
#                         ).first()
                        
#                         if categories_record:
#                             # Create category counts
#                             test_data['category_counts'] = {
#                                 'Achievement': 0,
#                                 'Power': 0,
#                                 'Affiliation': 0
#                             }
                            
#                             # Get counts from responses - FIX HERE
#                             responses = session.responses.all()  # Changed from testresponse_set to responses
#                             for response in responses:
#                                 if hasattr(response, 'selected_answer') and response.selected_answer:
#                                     answer_data = response.selected_answer
#                                     if isinstance(answer_data, dict) and 'category' in answer_data:
#                                         cat = answer_data['category']
#                                         if cat in test_data['category_counts']:
#                                             test_data['category_counts'][cat] += 1
#                     except Exception as e:
#                         print(f"Error processing motivation data for JS: {e}")
                
#                 elif 'Aptitude' in test_title:
#                     # Get aptitude data
#                     try:
#                         test_data['result_data'] = {}
                        
#                         # Get aptitude sections and scores - FIX HERE
#                         responses = session.responses.all()  # Changed from testresponse_set to responses
#                         for response in responses:
#                             if hasattr(response, 'selected_answer') and response.selected_answer:
#                                 answer_data = response.selected_answer
#                                 if isinstance(answer_data, dict) and 'sections' in answer_data:
#                                     sections = answer_data['sections']
#                                     for section_name, section_data in sections.items():
#                                         if section_name not in test_data['result_data']:
#                                             test_data['result_data'][section_name] = 0
                                        
#                                         # Count correct answers
#                                         if 'submitted_answers' in section_data:
#                                             for q_id, q_data in section_data['submitted_answers'].items():
#                                                 if q_data.get('correct_answer') == q_data.get('selected_answer'):
#                                                     test_data['result_data'][section_name] += 1
                        
#                         # Add responses for detailed processing
#                         test_data['responses'] = [{'selected_answer': {'sections': sections}}]
#                     except Exception as e:
#                         print(f"Error processing aptitude data for JS: {e}")
                
#                 test_results_data.append(test_data)
        
#         # Add test results data to context for JavaScript
#         import json
#         context['test_results_json'] = json.dumps(test_results_data)
        
#         # Continue with the rest of your existing code...
#         # (Check if all 4 tests are completed, process each test type, etc.)
        
#         # Check if all 4 tests are completed FOR THE TARGET USER
#         test1_completed = TestSession.objects.filter(
#             user=target_user, 
#             test__id=1,
#             is_completed=True
#         ).exists()
        
#         test2_completed = TestSession.objects.filter(
#             user=target_user, 
#             test__id=2,
#             is_completed=True
#         ).exists()
        
#         test3_completed = TestSession.objects.filter(
#             user=target_user, 
#             test__id=3,
#             is_completed=True
#         ).exists()
        
#         test4_completed = TestSession.objects.filter(
#             user=target_user, 
#             test__id=4,
#             is_completed=True
#         ).exists()
        
#         all_tests_completed = test1_completed and test2_completed and test3_completed and test4_completed
#         context['all_tests_completed'] = all_tests_completed
        
#         # Process each test type if available
#         personality_session = latest_sessions.get('Personality Assessment')
#         career_session = latest_sessions.get('Career Interest Inventory')
#         motivation_session = latest_sessions.get('Motivation Assessment')
#         aptitude_session = latest_sessions.get('Aptitude Assessment')
        
#         # Process personality test data
#         if personality_session:
#             try:
#                 # Get categories record for personality test
#                 categories_record = TestTopCategories.objects.filter(
#                     user=target_user,  # Use target_user instead of request.user
#                     test_paper=personality_session.test
#                 ).first()
                
#                 if categories_record:
#                     import ast
#                     try:
#                         high_categories = [cat.strip() for cat in ast.literal_eval(categories_record.high_category)]
#                         low_category = categories_record.low_category
                        
#                         hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, personality_session)
#                         context.update({
#                             'high_categories': high_categories,
#                             'low_category': low_category,
#                             'careers_to_opt': hexaco_recommendations['careers_to_opt'],
#                             'careers_to_avoid': hexaco_recommendations['careers_to_avoid'],
#                             'high_trait_descriptions': hexaco_recommendations['high_trait_descriptions'],
#                             'low_trait_descriptions': hexaco_recommendations['low_trait_descriptions'],
#                             'high_traits': [map_hexaco_code_to_trait(cat) for cat in high_categories],
#                             'low_trait': map_hexaco_code_to_trait(low_category) if low_category else None
#                         })
#                     except (ValueError, SyntaxError) as e:
#                         print(f"Error parsing personality categories: {e}")
#                         import traceback
#                         print(traceback.format_exc())
#             except Exception as e:
#                 print(f"Error processing personality test data: {e}")
#                 import traceback
#                 print(traceback.format_exc())

#         # Process career interest data
#         if career_session:
#             try:
#                 # Get categories record for career interest test
#                 categories_record = TestTopCategories.objects.filter(
#                     user=target_user,  # Use target_user instead of request.user
#                     test_paper=career_session.test
#                 ).first()
                
#                 if categories_record:
#                     try:
#                         high_categories = categories_record.high_category.strip("[]").strip()
#                         low_category = categories_record.low_category
                        
#                         hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, career_session)
#                         context.update({
#                             'riasec_high_categories': high_categories,
#                             'riasec_careers_to_opt': hexaco_recommendations['riasec_careers_to_opt'],
#                             'career_code_discription': hexaco_recommendations['career_code_discription'],
#                         })
#                     except Exception as e:
#                         print(f"Error processing career interest data: {e}")
#                         import traceback
#                         print(traceback.format_exc())
#             except Exception as e:
#                 print(f"Error processing career session data: {e}")
#                 import traceback
#                 print(traceback.format_exc())
            
#         # Process motivation data
#         if motivation_session:
#             try:
#                 # Get categories record for motivation test
#                 categories_record = TestTopCategories.objects.filter(
#                     user=target_user,  # Use target_user instead of request.user
#                     test_paper=motivation_session.test
#                 ).first()
                
#                 if categories_record:
#                     try:
#                         high_categories = categories_record.high_category
#                         low_category = categories_record.low_category
                        
#                         hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, motivation_session)
#                         context.update({
#                             'motivation_high_category': high_categories,
#                             'motivation_careers_to_opt': hexaco_recommendations['motivation_careers_to_opt'],
#                         })
#                     except Exception as e:
#                         print(f"Error processing motivation data: {e}")
#                         import traceback
#                         print(traceback.format_exc())
#             except Exception as e:
#                 print(f"Error processing motivation session data: {e}")
#                 import traceback
#                 print(traceback.format_exc())
            
#         # Process aptitude data
#         if aptitude_session:
#             try:
#                 # Get categories record for aptitude test
#                 categories_record = TestTopCategories.objects.filter(
#                     user=target_user,  # Use target_user instead of request.user
#                     test_paper=aptitude_session.test
#                 ).first()
                
#                 if categories_record:
#                     try:
#                         import json
#                         high_categories = json.loads(categories_record.high_category)
                        
#                         context.update({
#                             'above_list': high_categories.get("Above Average", []),
#                             'average_list': high_categories.get("Average", []),
#                             'below_list': high_categories.get("Below Average", [])
#                         })
                        
#                         hexaco_recommendations = get_hexaco_career_recommendations(high_categories, None, aptitude_session)
#                         context.update({
#                             'aptitude_improvement_plan': hexaco_recommendations['aptitude_improvement_plan'],
#                             'aptitude_strength_narrative': hexaco_recommendations['aptitude_strength_narrative'],
#                             'aptitude_Recommended_College_Courses': hexaco_recommendations['aptitude_Recommended_College_Courses'],
#                             'aptitude_roles_guidance': hexaco_recommendations['aptitude_roles_guidance'],
#                             'career_guidance_selected': hexaco_recommendations['career_guidance_selected'],
#                         })
#                     except json.JSONDecodeError as e:
#                         print(f"Error decoding aptitude categories JSON: {e}")
#                         import traceback
#                         print(traceback.format_exc())
#                     except Exception as e:
#                         print(f"Error processing aptitude data: {e}")
#                         import traceback
#                         print(traceback.format_exc())
#             except Exception as e:
#                 print(f"Error processing aptitude session data: {e}")
#                 import traceback
#                 print(traceback.format_exc())
        
#         return render(request, "combined_report.html", context)
        
#     except Exception as e:
#         import traceback
#         trace = traceback.format_exc()
#         print(f"Error in CombinedReport: {str(e)}")
#         print(trace)
#         return render(request, "combined_report.html", {
#             'error': f'An error occurred: {str(e)}',
#             'traceback': trace,
#             'no_results': True
#         })




def Results_details(request):
    return render(request, "result-details.html")

def Take_test(request, id):
    
    return render(request, "template20/app_post_matric/take_test.html", {"test_id": id})

def Test_details(request, id):
    return render(request, "template20/app_post_matric/test_details.html", {
        "test_id": id,
        "breadcrumb": get_breadcrumb([
            {"text": "Tests", "url": reverse("post_matric:tests")},
            {"text": "Test Details", "url": ""},
        ]),
    })

@login_required
def Test_results(request, id):
    """
    Legacy endpoint.

    The product's current UX routes "View Result" through `Results`:
    `/api/web/results/?test_id=<test_id>[&user_id=<student_id>]`
    so this view now redirects to keep behavior consistent.
    """
    from urllib.parse import urlencode
    params = {"test_id": id}
    user_id = request.GET.get("user_id")
    if user_id:
        params["user_id"] = user_id
    if (request.GET.get("embed") or "").strip() == "1":
        params["embed"] = "1"
    return redirect(f"{reverse('post_matric:results')}?{urlencode(params)}")

    try:
        from institute.models import StudentManagement
        from django.shortcuts import get_object_or_404
        
        # Get user_id from query params (for institute/marketing users viewing student results)
        user_id = request.GET.get('user_id', None)
        target_user = request.user  # Default to logged-in user
        
        # If user_id is provided, check permissions and get target user
        if user_id:
            try:
                user_id = int(user_id)
                # Check if logged-in user has permission to view other users' results
                is_institute_user = StudentManagement.objects.filter(
                    student__id=user_id
                ).filter(
                    institute__created_by=request.user
                ).exists() or request.user.is_superuser
                
                # Check if user is marketing/institute admin
                from core import choices
                is_admin = (
                    request.user.is_superuser or
                    request.user.user_type == choices.UserType.INSTITUTE or
                    request.user.user_type == choices.UserType.MARKETINGGROUPADMIN or
                    request.user.user_type == choices.UserType.INSTITUTEGROUPADMIN
                )
                
                if is_institute_user or is_admin:
                    target_user = get_object_or_404(User, id=user_id)
                else:
                    # No permission, use own user
                    target_user = request.user
            except (ValueError, TypeError):
                # Invalid user_id, use logged-in user
                target_user = request.user
        
        # Use id from URL as test_id
        test_id = id
        
        # Get the test session using direct parameters (fixes foreign key lookup issue)
        if test_id:
            try:
                test_id = int(test_id) if not isinstance(test_id, int) else test_id
                latest_session = TestSession.objects.filter(
                    user=target_user,
                    test_id=test_id,
                    is_completed=True
                ).order_by('-end_time').first()
            except (ValueError, TypeError):
                # Invalid test_id, query without it
                latest_session = TestSession.objects.filter(
                    user=target_user,
                    is_completed=True
                ).order_by('-end_time').first()
        else:
            latest_session = TestSession.objects.filter(
                user=target_user,
                is_completed=True
            ).order_by('-end_time').first()
        
        if not latest_session:
            return render(request, "template20/app_post_matric/test_results.html", {
                'error': 'No completed test found',
                'no_results': True,
                'breadcrumb': get_breadcrumb([
                    {'text': 'Tests', 'url': reverse('post_matric:tests')},
                    {'text': 'Results', 'url': ''},
                ]),
            })
        
        
        # Get categories record
        categories_record = TestTopCategories.objects.filter(
            user=target_user,
            test_paper=latest_session.test
        ).first()
        import ast
        # Extract high and low categories
        high_categories = []
        low_category = None

        
        if categories_record:
            if latest_session.test.title == 'Personality Assessment':
                high_categories = [cat.strip() for cat in ast.literal_eval(categories_record.high_category)]
            elif latest_session.test.title == 'Aptitude Assessment':
                high_categories = categories_record.high_category
                try:
                    if high_categories:
                        high_categories = json.loads(high_categories)
                    else:
                        high_categories = {}
                    if isinstance(high_categories, dict):
                        high_categories = normalize_aptitude_categories(high_categories)
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error parsing high_categories JSON: {e}")
                    high_categories = {}
            elif latest_session.test.title == 'Career Interest Inventory':
                high_categories = resolve_riasec_high_categories(
                    latest_session,
                    categories_record.high_category,
                )
            else:
                high_categories = categories_record.high_category
                high_categories = high_categories.strip("[]").strip() if high_categories else ''

            low_category = categories_record.low_category

        all_tests_completed = False

        # Check if all 4 tests are completed
        all_tests_completed = False
        
        # Check for completed sessions for each test type
        test1_completed = TestSession.objects.filter(
            user=target_user, 
            test__id=1,
            is_completed=True
        ).exists()
        
        test2_completed = TestSession.objects.filter(
            user=target_user, 
            test__id=2,
            is_completed=True
        ).exists()
        
        test3_completed = TestSession.objects.filter(
            user=target_user, 
            test__id=3,
            is_completed=True
        ).exists()
        
        test4_completed = TestSession.objects.filter(
            user=target_user, 
            test__id=4,
            is_completed=True
        ).exists()
        
        if test1_completed and test2_completed and test3_completed and test4_completed:
            all_tests_completed = True

        user = target_user
        try:
            # Retrieve the UserProfile for the target user (create if not exists)
            user_profile, created = UserProfile.objects.get_or_create(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        try:
            # Retrieve the UserProfile for the target user
            user_profile = user.user_profile
            # Access attributes from the User object
            created_date = latest_session.created_at
            gender_value = user_profile.gender
            if gender_value == 10:  # GenderChoices.UNKNOWN
                gender_display = "Unknown"
            elif gender_value == 20:  # GenderChoices.MALE
                gender_display = "Male"
            elif gender_value == 30:  # GenderChoices.FEMALE
                gender_display = "Female"
            else:
                gender_display = "Unknown"  # Default fallback
            schoolname = user_profile.schoolname
            student_name = user.email  # Assuming email is used as student name
            grade = user_profile.grade

        except UserProfile.DoesNotExist:
            print("UserProfile does not exist.")

    
        
        
        context = {
            'user': target_user,
            'viewing_as_admin': user_id is not None if 'user_id' in locals() else False,
            'test_id': test_id,
            'all_tests_completed': all_tests_completed,
            'high_categories': high_categories,
            'low_category': low_category,
            'test_name': test_display_title(latest_session.test.title),
            'test_type': latest_session.test.title,
            'completed_at': latest_session.end_time,
            'completed_at_display': _format_ui_datetime(latest_session.end_time),
            'result_data': latest_session.result or {},
            'no_results': False,
            # Add user profile information
            'created_date': created_date if 'created_date' in locals() else None,
            'gender': gender_display if 'gender_display' in locals() else None,
            'schoolname': schoolname if 'schoolname' in locals() else None,
            'student_name': student_name if 'student_name' in locals() else None,
            'grade': grade if 'grade' in locals() else None
        }
        

        if test_id == 4:
            # Ensure high_categories is a dictionary for aptitude tests
            if isinstance(high_categories, dict):
                context['above_list'] = high_categories.get("Above Average", [])
                context['average_list'] = high_categories.get("Average", [])
                context['below_list'] = high_categories.get("Below Average", [])
            else:
                # If high_categories is not a dict, set empty lists
                context['above_list'] = []
                context['average_list'] = []
                context['below_list'] = []
                print(f"Warning: high_categories is not a dict for test_id=4. Type: {type(high_categories)}, Value: {high_categories}")
        else:
            pass
        
        # Load JSON data for all test types
        hexaco_data, riasec_data, motivation_data, aptitude_weak_areas_data , aptitude_strength_narrative_data, Aptitude_report_main_data, aptitude_recommendations_data, career_mergerd_path, CombinedReport_data, aptitude_interpretation_data = get_hexaco_or_riasec_career_mapping(latest_session)
        
        if aptitude_interpretation_data is None:
            aptitude_interpretation_data = {}
        
        # If it's a personality test (HEXACO), get career recommendations
        if latest_session.test.title == 'Personality Assessment' and high_categories:
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            # breakpoint()
            context.update({
                'careers_to_opt': hexaco_recommendations['careers_to_opt'],
                'careers_to_avoid': hexaco_recommendations['careers_to_avoid'],
                'high_trait_descriptions': hexaco_recommendations['high_trait_descriptions'],
                'low_trait_descriptions': hexaco_recommendations['low_trait_descriptions'],
                'high_traits': [map_hexaco_code_to_trait(cat) for cat in high_categories],
                'low_trait': map_hexaco_code_to_trait(low_category) if low_category else None,
                'dominant_trait_explanations': hexaco_recommendations.get('dominant_trait_explanations', []),
                'combined_code_explanation': hexaco_recommendations.get('combined_code_explanation', None)
            })

        elif latest_session.test.title == 'Career Interest Inventory' and high_categories:
            
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            context.update({
                'riasec_careers_to_opt': hexaco_recommendations['riasec_careers_to_opt'],
                'career_code_discription': hexaco_recommendations['career_code_discription'],
                'riasec_key_descriptions': hexaco_recommendations.get('riasec_key_descriptions', []),
                'riasec_key_drivers': hexaco_recommendations.get('riasec_key_drivers', []),
                'riasec_summaries': hexaco_recommendations.get('riasec_summaries', []),
            })
        elif latest_session.test.title == 'Motivation Assessment' and high_categories:
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            
            context.update({
                'high_categories': high_categories,
                'motivation_careers_to_opt': hexaco_recommendations['motivation_careers_to_opt'],
                'motivation_key_description': hexaco_recommendations.get('motivation_key_description', None),
                'motivation_key_drivers': hexaco_recommendations.get('motivation_key_drivers', []),
                'motivation_summary': hexaco_recommendations.get('motivation_summary', None),
            })
        elif latest_session.test.title == 'Aptitude Assessment' and high_categories:
            
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            from app.class12_aptitude_report_utils import aptitude_assessment_report_context

            context.update(
                aptitude_assessment_report_context(
                    high_categories,
                    aptitude_interpretation_data,
                    hexaco_recommendations,
                )
            )
        
        # Build test_results_data for JavaScript (pdf-results.js)
        test_results_data = []
        title = latest_session.test.title
        duration_minutes = 0
        if latest_session.start_time and latest_session.end_time:
            duration = latest_session.end_time - latest_session.start_time
            duration_minutes = int(duration.total_seconds() / 60)

        test_data = {
            'test_id': latest_session.test.id,
            'test_title': title,
            'duration_minutes': duration_minutes,
            'result_data': {},
            'responses': []
        }

        # Try to use stored TestResult first (most accurate)
        try:
            from .models import TestResult
            test_result = TestResult.objects.filter(session=latest_session).first()
            if test_result and test_result.result_data:
                stored_data = test_result.result_data
                if isinstance(stored_data, dict):
                    test_data['result_data'] = normalize_test_result_data_for_charts(
                        stored_data,
                        is_aptitude='Aptitude' in title,
                    )
                if test_result.category_counts:
                    test_data['category_counts'] = test_result.category_counts.copy()
            else:
                # Fallback: Aggregate results from stored responses
                responses = []
                try:
                    responses_obj = getattr(latest_session, 'responses', None)
                    if responses_obj is not None:
                        responses = list(responses_obj.all())
                        # Convert responses to serializable format
                        test_data['responses'] = []
                        for resp in responses:
                            if hasattr(resp, 'selected_answer') and resp.selected_answer:
                                test_data['responses'].append({
                                    'selected_answer': resp.selected_answer
                                })
                except Exception:
                    pass

                if 'Personality' in title:
                    test_data['result_data'] = {
                        'H': {'score': 0}, 'E': {'score': 0}, 'X': {'score': 0},
                        'A': {'score': 0}, 'C': {'score': 0}, 'O': {'score': 0}
                    }
                    for resp in responses:
                        if hasattr(resp, 'selected_answer') and resp.selected_answer:
                            ans = resp.selected_answer
                            if isinstance(ans, dict) and 'dimension' in ans:
                                dim = ans['dimension']
                                if dim in test_data['result_data']:
                                    try:
                                        test_data['result_data'][dim]['score'] += int(ans.get('score', 0))
                                    except Exception:
                                        pass

                elif 'Career' in title or 'Interest' in title:
                    test_data['result_data'] = {
                        'R': {'score': 0}, 'I': {'score': 0}, 'A': {'score': 0},
                        'S': {'score': 0}, 'E': {'score': 0}, 'C': {'score': 0}
                    }
                    for resp in responses:
                        if hasattr(resp, 'selected_answer') and resp.selected_answer:
                            ans = resp.selected_answer
                            if isinstance(ans, dict) and 'dimension' in ans:
                                dim = ans['dimension']
                                if dim in test_data['result_data']:
                                    try:
                                        test_data['result_data'][dim]['score'] += int(ans.get('score', 0))
                                    except Exception:
                                        pass

                elif 'Motivation' in title:
                    test_data['category_counts'] = {'Achievement': 0, 'Power': 0, 'Affiliation': 0}
                    for resp in responses:
                        if hasattr(resp, 'selected_answer') and resp.selected_answer:
                            ans = resp.selected_answer
                            if isinstance(ans, dict) and 'category' in ans:
                                cat = ans['category']
                                if cat in test_data['category_counts']:
                                    test_data['category_counts'][cat] += 1

                elif 'Aptitude' in title:
                    test_data['result_data'] = {}
                    for resp in responses:
                        if hasattr(resp, 'selected_answer') and resp.selected_answer:
                            ans = resp.selected_answer
                            if isinstance(ans, dict) and 'sections' in ans:
                                sections = ans['sections']
                                for section_name, section_data in sections.items():
                                    if section_name not in test_data['result_data']:
                                        test_data['result_data'][section_name] = 0
                                    if 'submitted_answers' in section_data:
                                        for _qid, qdata in section_data['submitted_answers'].items():
                                            if qdata.get('correct_answer') == qdata.get('selected_answer'):
                                                test_data['result_data'][section_name] += 1
        except Exception as e:
            print(f"Error getting test result data: {e}")
            import traceback
            traceback.print_exc()

        test_results_data.append(test_data)

        # Attach JSON for client scripts (pdf-results.js will prefer this over API fetch)
        import json as _json
        context['test_results_json'] = _json.dumps(test_results_data)
        
        context['breadcrumb'] = get_breadcrumb([
            {'text': 'Tests', 'url': reverse('post_matric:tests')},
            {'text': 'Results', 'url': ''},
        ])
        return render(request, "template20/app_post_matric/test_results.html", context)    
    
    except Exception as e:
        import json as _json
        return render(request, "template20/app_post_matric/test_results.html", {
            'error': f'An error occurred: {str(e)}',
            'no_results': True,
            'test_results_json': _json.dumps([]),
            'breadcrumb': get_breadcrumb([
                {'text': 'Tests', 'url': reverse('post_matric:tests')},
                {'text': 'Results', 'url': ''},
            ]),
        })


@login_required
def download_test_results_pdf(request, id):
    """Generate and download PDF for test results"""
    try:
        import weasyprint
        import ssl
        from institute.models import StudentManagement
        
        # Use id from URL as test_id
        test_id = id
        user_id = request.GET.get('user_id', None)
        target_user = request.user

        # Support institute/admin users downloading a student's PDF
        if user_id:
            try:
                user_id = int(user_id)
                is_institute_user = StudentManagement.objects.filter(
                    student__id=user_id
                ).filter(
                    institute__created_by=request.user
                ).exists() or request.user.is_superuser

                from core import choices
                is_admin = (
                    request.user.is_superuser or
                    request.user.user_type == choices.UserType.INSTITUTE or
                    request.user.user_type == choices.UserType.MARKETINGGROUPADMIN or
                    request.user.user_type == choices.UserType.INSTITUTEGROUPADMIN
                )

                if is_institute_user or is_admin:
                    target_user = get_object_or_404(User, id=user_id)
            except (ValueError, TypeError):
                target_user = request.user
        
        # Build the query
        query = {
            'user': target_user,
            'is_completed': True
        }
        
        if test_id:
            query['test_id'] = test_id
        
        # Get the test session
        latest_session = TestSession.objects.filter(**query).order_by('-end_time').first()
        
        if not latest_session:
            return HttpResponse('No completed test found', status=404)
        
        # Reuse the same context building logic from Test_results
        # (Copy the context building code from Test_results view)
        # For now, we'll build a simplified context for PDF
        from datetime import datetime
        context = {
            'test_name': test_display_title(latest_session.test.title),
            'test_type': latest_session.test.title,
            'completed_at': latest_session.end_time,
            'user': target_user,
            'test_id': test_id,
            'now': datetime.now(),
        }
        
        # Get categories record and build context similar to Test_results
        categories_record = TestTopCategories.objects.filter(
            user=target_user,
            test_paper=latest_session.test
        ).first()
        
        import ast
        import json
        high_categories = []
        low_category = None
        
        if categories_record:
            if latest_session.test.title == 'Personality Assessment':
                high_categories = [cat.strip() for cat in ast.literal_eval(categories_record.high_category)]
            elif latest_session.test.title == 'Aptitude Assessment':
                high_categories = categories_record.high_category
                try:
                    if high_categories:
                        high_categories = json.loads(high_categories)
                    else:
                        high_categories = {}
                    if isinstance(high_categories, dict):
                        high_categories = normalize_aptitude_categories(high_categories)
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error parsing high_categories JSON: {e}")
                    high_categories = {}
            elif latest_session.test.title == 'Career Interest Inventory':
                high_categories = resolve_riasec_high_categories(
                    latest_session,
                    categories_record.high_category,
                )
            else:
                high_categories = categories_record.high_category
                high_categories = high_categories.strip("[]").strip() if high_categories else ''
            
            low_category = categories_record.low_category
        
        # Load JSON data for all test types
        hexaco_data, riasec_data, motivation_data, aptitude_weak_areas_data , aptitude_strength_narrative_data, Aptitude_report_main_data, aptitude_recommendations_data, career_mergerd_path, CombinedReport_data, aptitude_interpretation_data = get_hexaco_or_riasec_career_mapping(latest_session)
        
        if aptitude_interpretation_data is None:
            aptitude_interpretation_data = {}
        
        # Add test-specific context based on test type
        if latest_session.test.title == 'Personality Assessment' and high_categories:
            # Use the function that generates recommendations (defined in this file)
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            context.update({
                'high_traits': [cat for cat in high_categories] if isinstance(high_categories, list) else [],
                'low_trait': low_category,
                'careers_to_opt': list(hexaco_recommendations.get('careers_to_opt', {}).values())[0] if hexaco_recommendations.get('careers_to_opt') else [],
                'careers_to_avoid': list(hexaco_recommendations.get('careers_to_avoid', {}).values())[0] if hexaco_recommendations.get('careers_to_avoid') else [],
                'high_trait_descriptions': hexaco_recommendations.get('high_trait_descriptions', {}),
                'low_trait_descriptions': hexaco_recommendations.get('low_trait_descriptions', {}),
                'dominant_trait_explanations': hexaco_recommendations.get('dominant_trait_explanations', []),
                'combined_code_explanation': hexaco_recommendations.get('combined_code_explanation', None)
            })
        elif latest_session.test.title == 'Career Interest Inventory' and high_categories:
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            context.update({
                'riasec_careers_to_opt': list(hexaco_recommendations.get('riasec_careers_to_opt', {}).values())[0] if hexaco_recommendations.get('riasec_careers_to_opt') else [],
                'career_code_discription': hexaco_recommendations.get('career_code_discription', []),
            })
        elif latest_session.test.title == 'Motivation Assessment' and high_categories:
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            context.update({
                'motivation_careers_to_opt': list(hexaco_recommendations.get('motivation_careers_to_opt', {}).values())[0] if hexaco_recommendations.get('motivation_careers_to_opt') else [],
                'motivation_key_description': hexaco_recommendations.get('motivation_key_description', None),
                'motivation_key_drivers': hexaco_recommendations.get('motivation_key_drivers', []),
                'motivation_summary': hexaco_recommendations.get('motivation_summary', None),
            })
        elif latest_session.test.title == 'Aptitude Assessment' and high_categories:
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            from app.class12_aptitude_report_utils import aptitude_assessment_report_context

            context.update(
                aptitude_assessment_report_context(
                    high_categories,
                    aptitude_interpretation_data,
                    hexaco_recommendations,
                )
            )
        
        # Render PDF template
        template = get_template('template20/app_post_matric/test_results_pdf.html')
        html = template.render(context)
        
        # Configure SSL to disable verification for WeasyPrint image loading
        original_ssl_context = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context
        
        try:
            pdf_file = weasyprint.HTML(
                string=html,
                base_url=request.build_absolute_uri('/')
            ).write_pdf()
        finally:
            # Restore original SSL context
            ssl._create_default_https_context = original_ssl_context
        
        # Create HTTP response with PDF
        response = HttpResponse(content_type='application/pdf')
        user_name = request.user.username or f"user_{request.user.id}"
        test_name_slug = latest_session.test.title.replace(' ', '_')
        filename = f"{user_name}-{test_name_slug}_Results.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write(pdf_file)
        
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HttpResponse(f'Error generating PDF: {str(e)}', status=500)


def test_sections(request, test_id):
    return render(request, 'template20/app_post_matric/test_sections.html', {
        'test': test_id,
        'breadcrumb': get_breadcrumb([
            {'text': 'Tests', 'url': reverse('post_matric:tests')},
            {'text': 'Aptitude Assessment', 'url': ''},
        ]),
    })

@login_required
def section_details(request,testId, section_id, session_id):
    from .models import Sections, TestSession, SectionSession
    from django.urls import reverse
    
    section = get_object_or_404(Sections, id=section_id)
    test_session = get_object_or_404(TestSession, id=session_id, user=request.user)
    
    # Get or create section session
    try:
        section_session = SectionSession.objects.get(
            session=test_session,
            section=section
        )
    except SectionSession.DoesNotExist:
        section_session = SectionSession.objects.create(
            session=test_session,
            section=section,
            start_time=timezone.now(),
            is_completed=False
        )
    
    context = {
        'section': section,
        'section_id': section_id,
        'session_id': session_id,
        'test_id': testId,
        'test_session': test_session,
        'section_session': section_session,
        'time_limit': section.time_limit or 20,  # Default 20 minutes if not set
    }
    
    return render(request, 'template20/app_post_matric/section_details.html', context)
    # return render(request, 'section_details.html', context)

@login_required
def section_results(request, testId, result_id):
    return render(request, 'template20/app_post_matric/section_results.html', {
        'testId': testId,
        'result_id': result_id,
        'breadcrumb': get_breadcrumb([
            {'text': 'Tests', 'url': reverse('post_matric:tests')},
            {'text': 'Results', 'url': reverse('post_matric:results_list')},
            {'text': 'Section Results', 'url': ''},
        ]),
    })

def start_section(request, section_id):
    # Implementation for starting a section
    pass

def section_session_detail(request, session_id):
    # Implementation for viewing section session details
    pass

def login_view(request):
    if request.method == "POST":
        login_input = request.POST.get("username")  # This can be username or email
        password = request.POST.get("password")
        
        # In your custom User model, email is the USERNAME_FIELD
        user = authenticate(request, email=login_input, password=password)
        
        if user:
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            auth_login(request, user)
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('/api/web/home/')
        else:
            return render(request, "login.html", {"error": "Invalid credentials"})
    return render(request, "login.html")



def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        
        if User.objects.filter(email=email).exists():
            return render(request, "register.html", {"error": "Email already exists"})
        
        # Use the custom User model's create_user method
        user = User.objects.create_user(
            email=email,
            name=username,
            password=password
        )
        
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        auth_login(request, user)
        return redirect("/api/web/home/")
    return render(request, "register.html")



class AnswerViewSet(viewsets.ModelViewSet):
    queryset = Answer.objects.all()
    serializer_class = AnswerSerializer

    def get_serializer_context(self):
        """Add request to serializer context for proper image URL generation"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        queryset = Answer.objects.all()
        question_id = self.request.query_params.get('question', None)
        if question_id is not None:
            queryset = queryset.filter(question_id=question_id)
        return queryset.select_related('question')  # Optimize queries

class SectionsViewSet(viewsets.ModelViewSet):
    queryset = Sections.objects.all()
    serializer_class = SectionsSerializer

class SectionSessionViewSet(viewsets.ModelViewSet):
    serializer_class = SectionSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SectionSession.objects.filter(session__user=self.request.user)

    def create(self, request, *args, **kwargs):
        session_id = request.data.get('session')
        section_id = request.data.get('section')

        if not session_id or not section_id:
            return Response(
                {"error": "Both session and section IDs are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get the test session
            test_session = TestSession.objects.get(
                id=session_id,
                user=request.user,
                is_completed=False
            )
            
            # Get or update the section session
            section_session = SectionSession.objects.filter(
                session=test_session,
                section_id=section_id,
                is_completed=False
            ).first()
            
            if not section_session:
                # If no section session exists, create new one
                section = Sections.objects.get(id=section_id)
                section_session = SectionSession.objects.create(
                    session=test_session,
                    section=section,
                    start_time=timezone.now(),
                    is_completed=False
                )
            else:
                # Update existing section session
                section_session.start_time = timezone.now()
                section_session.save()

            serializer = self.get_serializer(section_session)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except TestSession.DoesNotExist:
            return Response(
                {"error": "Invalid or completed test session"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Sections.DoesNotExist:
            return Response(
                {"error": "Section not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class TestCategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for test categories
    """
    queryset = TestCategory.objects.all()
    serializer_class = TestCategorySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TestCategoryDetailSerializer
        return TestCategorySerializer

class TestViewSet(viewsets.ModelViewSet):
    
    """
    API endpoint for tests
    """
    queryset = Test.objects.filter(is_active=True)
    serializer_class = TestSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TestDetailSerializer
        return TestSerializer

    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start or reset a test session"""
        test = self.get_object()
        session = TestSession.objects.filter(user=request.user, test=test).order_by('-attempt_count').first()
        if session and session.is_completed:
            # Block retake: return error
            return Response(
                {"detail": "You have already completed this test. Retake is not allowed."},
                status=status.HTTP_403_FORBIDDEN
            )
        # Otherwise, get or create session
        session = TestSession.get_or_update_session(request.user, test)
        serializer = TestSessionDetailSerializer(session, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class QuestionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for questions (read-only)
    """
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer

    def get_queryset(self):
        queryset = Question.objects.all()
        test_id = self.request.query_params.get('test', None)
        section_id = self.request.query_params.get('section', None)
        question_dimension = self.request.query_params.get('dimension', None)
        question_level = self.request.query_params.get('level', None)

        if test_id:
            queryset = queryset.filter(test_id=test_id)
        if section_id:
            queryset = queryset.filter(section_id=section_id)
        if question_dimension:
            queryset = queryset.filter(question_dimension=question_dimension)
        if question_level:
            queryset = queryset.filter(question_level=question_level)

        return queryset

class TestSessionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for test sessions
    """
    serializer_class = TestSessionSerializer
    permission_classes = [permissions.AllowAny]  # Consider changing this to IsAuthenticated in production

    def get_queryset(self):
        return TestSession.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ['retrieve', 'list']:
            return TestSessionDetailSerializer
        return TestSessionSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new test session"""
        test_id = request.data.get('test')
        
        if not test_id:
            return Response(
                {"error": "Test ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            test = Test.objects.get(id=test_id)
            
            # Use get_or_update_session to handle everything
            session = TestSession.get_or_update_session(request.user, test)
            
            # Return the session with its section sessions
            serializer = TestSessionDetailSerializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Test.DoesNotExist:
            return Response(
                {"error": f"Test with ID {test_id} does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit and complete a test session"""
        try:
            session = self.get_object()

            if session.is_completed:
                return Response(
                    {"detail": "This test session is already completed."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get user responses
            # For aptitude tests, get the response without section_section (the main response that contains all sections)
            # For other tests, get any response
            if 'aptitude assessment' in session.test.title.lower().strip():
                user_response = session.responses.filter(session_section__isnull=True).first()
                if not user_response:
                    # Fallback to last response if no main response found
                    user_response = session.responses.last()
            else:
                user_response = session.responses.last()
            
            if not user_response:
                return Response(
                    {"detail": "No responses found for this session."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Extract submitted answers from the response
            response_data = user_response.selected_answer
            if not response_data:
                return Response(
                    {"detail": f"Invalid response data format. No response data found. Response ID: {user_response.id}, selected_answer: {response_data}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # For aptitude test, handle section-based structure
            if 'aptitude assessment' in session.test.title.lower().strip():
                if not isinstance(response_data, dict):
                    return Response(
                        {"detail": f"Invalid response data format for aptitude test. Expected dict, got {type(response_data).__name__}."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                # Check if it's the new format (with sections) or old format (with submitted_answers directly)
                if 'sections' not in response_data:
                    # Old format detected - this shouldn't happen if save_responses is working correctly
                    # But if it does, we need to handle it or provide a clear error
                    if 'submitted_answers' in response_data:
                        # This is old format - delete this response and ask user to re-save
                        # Delete the old format response to force recreation with new format
                        user_response.delete()
                        return Response(
                            {"detail": f"Found old response format. Please re-save your section responses. The old response has been cleared. Available keys in old format: {list(response_data.keys())}"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    else:
                        return Response(
                            {"detail": f"Invalid response data format for aptitude test. Missing 'sections' key. Available keys: {list(response_data.keys())}"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                submitted_answers = response_data.get('sections', {})
            else:
                # For other tests, use the standard format
                if 'submitted_answers' not in response_data:
                    return Response(
                        {"detail": "Invalid response data format."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                submitted_answers = response_data['submitted_answers']
            category_counts = response_data.get('category_counts', {})
            
            # Process the test based on its type
            test_title = session.test.title.lower().strip()
            result_data = {}
            total_score = 0

            # breakpoint()

            if 'personality assessment' in test_title:
                result_data, total_score = self._process_personality_test(submitted_answers, session)
            elif 'motivation assessment' in test_title:
                result_data, category_counts = self._process_motivation_test(submitted_answers, session)
            elif 'career interest inventory' in test_title or session.test.id =='3':
                result_data = self._process_career_test(submitted_answers, session)
            elif 'aptitude assessment' in test_title:
                result_data, total_score, completed_count = self._process_aptitude_test(session)
                # Check all section sessions to see if they're all completed
                section_sessions = session.section_sessions.all()
                total_sections = section_sessions.count()
                completed_sections = section_sessions.filter(is_completed=True).count()

            # Create or update test result
            test_result, created = TestResult.objects.update_or_create(
                session=session,
                defaults={
                    'score': total_score,
                    'result_data': result_data,
                    'category_counts': category_counts,
                    'feedback': f"Thank you for completing {session.test.title}. Your results have been processed."
                }
            )

            # Mark session as completed
            if 'aptitude assessment' in test_title:
                # Check if all section sessions are completed
                if total_sections > 0 and completed_sections == total_sections:
                    session.is_completed = True
                    session.end_time = timezone.now()
                    session.save()
                # Don't mark as incomplete if we're still in progress
                # The session will remain incomplete until all sections are done
            else:
                session.is_completed = True
                session.end_time = timezone.now()
                session.save()

            # Return the result
            serializer = TestResultSerializer(test_result)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error in submit: {str(e)}")
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_personality_test(self, submitted_answers, session):
        result_data = {}
        total_score = 0
        from .models import Answer
        
        for question_key, answer_obj in submitted_answers.items():
            # Handle different question_key formats: "1" or "Question_1"
            try:
                if '_' in str(question_key):
                    question_order = int(str(question_key).split('_')[1])
                else:
                    # question_key is just the question ID
                    question = session.test.questions.filter(id=int(question_key)).first()
                    if question:
                        question_order = question.order
                    else:
                        continue
            except (ValueError, IndexError):
                # Try to get question by ID directly
                question = session.test.questions.filter(id=int(question_key)).first()
                if not question:
                    continue
                question_order = question.order
            
            question = session.test.questions.filter(order=question_order).first()
            if not question:
                continue

            dimension = question.question_dimension
            pattern = question.parttern
            
            # Handle different answer formats: list of answer IDs, dict, or single value
            if isinstance(answer_obj, list):
                # List of answer IDs - fetch Answer objects and sum scores
                score = 0
                for answer_id in answer_obj:
                    try:
                        answer = Answer.objects.get(id=int(answer_id), question=question)
                        score += answer.score or 0
                    except (Answer.DoesNotExist, ValueError):
                        pass
            elif isinstance(answer_obj, dict):
                raw_score = answer_obj.get('score', 0)
                score = raw_score
            else:
                # Single answer ID or score value
                try:
                    answer = Answer.objects.get(id=int(answer_obj), question=question)
                    score = answer.score or 0
                except (Answer.DoesNotExist, ValueError):
                    score = int(answer_obj) if isinstance(answer_obj, (int, str)) and str(answer_obj).isdigit() else 0
            
            if dimension not in result_data:
                result_data[dimension] = {'score': 0, 'count': 0}
                
            result_data[dimension]['score'] += score
            result_data[dimension]['count'] += 1
            total_score += score

        # Calculate averages
        for dim in result_data:
            count = result_data[dim]['count']
            if count > 0:
                result_data[dim]['average'] = result_data[dim]['score']

        # Sort dimensions by score and get top 3
        sorted_dimensions = sorted(
            result_data.items(), 
            key=lambda x: x[1]['score'], 
            reverse=True
        )
        
        # Get top 3 categories
        top_categories = [dim[0] for dim in sorted_dimensions[:2]]
        # Get the single lowest scoring category
        lowest_category = sorted_dimensions[-1][0] if sorted_dimensions else None
        
        # Save top categories to database
        # Delete existing top categories for this test session
        TestTopCategories.objects.filter(
            user=session.user,
            test_paper=session.test
        ).delete()
        
        # Save new top categories
        
        TestTopCategories.objects.update_or_create(
            user=session.user,
            test_paper=session.test,
            high_category=top_categories,
            low_category =lowest_category

        )
        
        # Optionally, add top categories to result_data for frontend use
        result_data['_top_categories'] = top_categories
        result_data['_lowest_category'] = lowest_category
                
        return result_data, total_score

    def _process_motivation_test(self, submitted_answers, session):
        category_counts = {}
        result_data = {}
        from .models import Answer
        
        for question_key, answer_obj in submitted_answers.items():
            # Handle different answer formats: list of answer IDs, dict, or single value
            if isinstance(answer_obj, list):
                # List of answer IDs - fetch Answer objects and get categories
                for answer_id in answer_obj:
                    try:
                        answer = Answer.objects.get(id=int(answer_id))
                        if answer.category:
                            category_counts[answer.category] = category_counts.get(answer.category, 0) + 1
                    except (Answer.DoesNotExist, ValueError):
                        pass
            elif isinstance(answer_obj, dict):
                category = answer_obj.get('category')
                if category:
                    category_counts[category] = category_counts.get(category, 0) + 1
            else:
                # Single answer ID
                try:
                    answer = Answer.objects.get(id=int(answer_obj))
                    if answer.category:
                        category_counts[answer.category] = category_counts.get(answer.category, 0) + 1
                except (Answer.DoesNotExist, ValueError):
                    pass
                    
        result_data['category_distribution'] = category_counts

        if category_counts:
            # Get the category with highest count
            highest_category = max(category_counts, key=category_counts.get)
            lowest_category = min(category_counts, key=category_counts.get)
            
            # Delete existing entries
            TestTopCategories.objects.filter(
                user=session.user,
                test_paper=session.test
            ).delete()
            
            # Save highest category
            TestTopCategories.objects.update_or_create(
                user=session.user,
                test_paper=session.test,
                high_category=highest_category,
                low_category = lowest_category
            )
            
            # Add to result_data
            result_data['_highest_category'] = highest_category
            result_data['_lowest_category'] = lowest_category
        
        return result_data, category_counts

    def _process_career_test(self, submitted_answers, session):
        # Initialize dimensions dictionary to store scores
        result_data = {}
        
        # Process each answer
        for question_key, answer_obj in submitted_answers.items():
            # Handle different question_key formats: "1" or "Question_1"
            try:
                if '_' in str(question_key):
                    question_order = int(str(question_key).split('_')[1])
                else:
                    # question_key is just the question ID
                    question = session.test.questions.filter(id=int(question_key)).first()
                    if question:
                        question_order = question.order
                    else:
                        continue
            except (ValueError, IndexError):
                # Try to get question by ID directly
                question = session.test.questions.filter(id=int(question_key)).first()
                if not question:
                    continue
                question_order = question.order
            
            # Get the question
            question = session.test.questions.filter(order=question_order).first()
            if not question:
                continue

            # Get dimension from question (R, I, A, S, E, C)
            dimension = question.question_dimension
            if dimension:
                # Remove trailing numbers (like IRE2 -> IRE)
                dimension = re.sub(r'\d+$', '', dimension)
            
            # Handle different answer formats: list of answer IDs, dict, or single value
            if isinstance(answer_obj, list):
                # List of answer IDs - fetch Answer objects and sum scores
                score = 0.0
                for answer_id in answer_obj:
                    try:
                        answer = Answer.objects.get(id=int(answer_id), question=question)
                        score += float(answer.score or 0)
                    except (Answer.DoesNotExist, ValueError):
                        pass
            elif isinstance(answer_obj, dict):
                score = float(answer_obj.get('score', 0))
            else:
                # Single answer ID or score value
                try:
                    answer = Answer.objects.get(id=int(answer_obj), question=question)
                    score = float(answer.score or 0)
                except (Answer.DoesNotExist, ValueError):
                    score = float(answer_obj) if isinstance(answer_obj, (int, float, str)) and (isinstance(answer_obj, (int, float)) or str(answer_obj).replace('.', '').isdigit()) else 0.0

            # Initialize dimension in result_data if not exists
            if dimension not in result_data:
                result_data[dimension] = {
                    'score': 0,
                    'count': 0,
                    'name': self._get_dimension_name(dimension)  # Add dimension full name
                }
            
            # Add score to dimension
            result_data[dimension]['score'] += score
            result_data[dimension]['count'] += 1

        # Calculate averages for each dimension
        for dim in result_data:
            count = result_data[dim]['count']
            if count > 0:
                result_data[dim]['average'] = round(result_data[dim]['score'] / count, 2)
                result_data[dim]['total'] = result_data[dim]['score']  # Keep total score

        # Sort dimensions by total score
        sorted_dimensions = sorted(
            result_data.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )
        
        from app.interest_report_utils import top_riasec_codes_from_scores

        # Get top 3 and lowest 1 (ties broken by canonical RIASEC order)
        top_3_categories = top_riasec_codes_from_scores(result_data, limit=3)
        lowest_category = sorted_dimensions[-1][0] if sorted_dimensions else None
        
        # Delete existing entries
        TestTopCategories.objects.filter(
            user=session.user,
            test_paper=session.test
        ).delete()
        
        # Save top 3 categories
        
        TestTopCategories.objects.update_or_create(
            user=session.user,
            test_paper=session.test,
            high_category = f"[{''.join(top_3_categories)}]",
            low_category  =lowest_category
        )
        
        # Add to result_data for frontend use
        result_data['_top_3_categories'] = top_3_categories
        result_data['_lowest_category'] = lowest_category

        return result_data

    def _get_dimension_name(self, dimension):
        """Helper method to get full names of RIASEC dimensions"""
        dimension_names = {
            'R': 'Realistic',
            'I': 'Investigative',
            'A': 'Artistic',
            'S': 'Social',
            'E': 'Enterprising',
            'C': 'Conventional'
        }
        return dimension_names.get(dimension, dimension)
    
    def _process_aptitude_test(self, session):
        result_data = {}
        total_score = 0
        completed_count = 0
        performance_levels = {
            'Above Average': [],
            'Average': [],
            'Below Average': []
        }

        section_sessions = session.section_sessions.all().order_by('id')
        all_responses = UserResponse.objects.filter(session=session)

        for section_session in section_sessions:
            section_name = resolve_aptitude_json_area(section_session.section.title)
            section_score = 0
            accuracy = 0  # to track score percent
            total_questions = 0
            correct_count = 0

            for response in all_responses:
                if not response.selected_answer:
                    continue

                response_data = response.selected_answer
                section_data = None

                if 'sections' in response_data and section_name in response_data['sections']:
                    section_data = response_data['sections'][section_name]
                elif response.session_section == section_session:
                    section_data = response_data

                if section_data:
                    section_answers = section_data.get('submitted_answers', {})
                    current_score = section_data.get('score', 0)

                    if section_answers:
                        section_session.is_completed = True
                        if not section_session.end_time:
                            section_session.end_time = timezone.now()
                        section_session.save()

                        total_questions = len(section_answers)

                        correct_count = sum(
                            1 for ans in section_answers.values()
                            if isinstance(ans, dict)
                            and ans.get('correct_answer')
                            and ans.get('selected_answer')
                            and ans.get('correct_answer').strip().lower() == ans.get('selected_answer').strip().lower()
                        )

                        if current_score == 0:
                            accuracy = (correct_count / total_questions) * 100 if total_questions > 0 else 0
                            section_score = round((correct_count / total_questions) * 10, 2) if total_questions > 0 else 0
                        else:
                            section_score = current_score
                            accuracy = (correct_count / total_questions) * 100 if total_questions > 0 else 0

                        break

            # Categorize section into performance level
            if accuracy >= 70:
                performance_levels['Above Average'].append(section_name)
            elif accuracy >= 40:
                performance_levels['Average'].append(section_name)
            else:
                performance_levels['Below Average'].append(section_name)

            # Count as completed if section has score OR if section_session is marked as completed
            if section_score > 0 or section_session.is_completed:
                completed_count += 1
                # Ensure section_session is marked as completed if it has a score
                if section_score > 0 and not section_session.is_completed:
                    section_session.is_completed = True
                    if not section_session.end_time:
                        section_session.end_time = timezone.now()
                    section_session.save()

            result_data[section_name] = section_score

            # result_data[section_name] = {
            #     'score': section_score,
            #     'accuracy': round(accuracy, 2)
            # }

            total_score += section_score

        # Calculate average total score
        if section_sessions.count() > 0:
            total_score = total_score / section_sessions.count()

        # Add performance level breakdown to result
        result_data['performance_levels'] = performance_levels

        # First delete existing entries for this user/test
        TestTopCategories.objects.filter(
            user=session.user,
            test_paper=session.test
        ).delete()

        # Convert performance_levels dict to a JSON string for storage
        performance_summary = json.dumps(performance_levels)
        # Save the performance level data into the DB
        TestTopCategories.objects.update_or_create(
            user=session.user,
            test_paper=session.test,
            defaults={
                'high_category': performance_summary,
                'low_category': 'N/A'  # or something else meaningful for aptitude
            }
        )

        return result_data, total_score, completed_count

    @action(detail=True, methods=['get'])
    def answers_summary(self, request, pk=None):
        session = self.get_object()
        user_response = session.responses.first()
        submitted_answers = user_response.selected_answer.get('submitted_answers', {}) if user_response else {}

        questions = session.test.questions.all()
        answers_summary = []
        for question in questions:
            answer_key = f"Question_{question.order}"
            answer_value = submitted_answers.get(answer_key)
            selected_answer = question.answers.filter(score=answer_value).first() if answer_value is not None else None
            answers_summary.append({
                "question_text": question.text,
                "answer_text": selected_answer.text if selected_answer else "N/A",
                "answer_value": answer_value,
                "question": {
                    "image_url": question.image.url if getattr(question, 'image', None) else None,
                }
            })

        return Response(answers_summary)

class UserResponseViewSet(viewsets.ModelViewSet):
    queryset = UserResponse.objects.all()
    serializer_class = UserResponseSerializer

    @action(detail=True, methods=['post'])
    def save_responses(self, request, pk=None):
        """
        Custom action to save all responses for a session.
        POST /api/responses/<session_id>/save_responses/
        """
        # breakpoint()

        try:
            # Get required data from request
            submitted_answers = request.data.get('submitted_answers', {})
            section_session_id = request.data.get('section_session')
            category_counts = request.data.get('category_counts', {})
            score = request.data.get('score', 0)
            
            # Get the session
            session = TestSession.objects.get(id=pk)
            test = session.test

            # Get section session if provided
            section_session = None
            if section_session_id:
                section_session = SectionSession.objects.get(id=section_session_id)

            # Check if this is a multi-section test (like test4)
            has_sections = section_session_id is not None
            
            if has_sections:
                # MULTI-SECTION LOGIC (for test4 and similar tests)
                section_identifier = section_session.section.title
                
                # Get existing response or create new one (must have session_section=None for multi-section tests)
                try:
                    response = UserResponse.objects.get(
                        session=session,
                        test=test,
                        attempt_number=session.attempt_count,
                        session_section=None  # Must be None for multi-section tests
                    )
                    existing_data = response.selected_answer or {"sections": {}, "metadata": {}}
                except UserResponse.DoesNotExist:
                    existing_data = {"sections": {}, "metadata": {}}

                # Ensure proper structure for multi-section
                # If old format exists (with submitted_answers directly), convert to new format
                if "sections" not in existing_data:
                    if "submitted_answers" in existing_data:
                        # This is old format - we can't migrate it without section info, so start fresh
                        existing_data = {"sections": {}, "metadata": {}}
                    else:
                        existing_data["sections"] = {}
                if "metadata" not in existing_data:
                    existing_data["metadata"] = {}

                # Add the new section data
                existing_data["sections"][section_identifier] = {
                    "submitted_answers": submitted_answers,
                    "category_counts": category_counts,
                    "score": score,
                    "section_session_id": section_session_id,
                }

                # Update metadata
                existing_data["metadata"]["total_sections"] = len(existing_data["sections"])
                existing_data["metadata"]["last_updated"] = timezone.now().isoformat()
                existing_data["metadata"]["total_score"] = sum(
                    section.get("score", 0) for section in existing_data["sections"].values()
                )

                # Update or create the response (for multi-section tests, use session_section=None to store all sections in one response)
                response, created = UserResponse.objects.update_or_create(
                    session=session,
                    test=test,
                    attempt_number=session.attempt_count,
                    session_section=None,  # Main response that contains all sections
                    defaults={
                        'selected_answer': existing_data
                    }
                )
                
            else:
                # SINGLE-SECTION LOGIC (for existing tests - no changes)
                answer_data = {
                    'submitted_answers': submitted_answers,
                    'category_counts': category_counts,
                    'score': score
                }
                
                # Use your existing method for single tests
                response = UserResponse.update_or_create_response(
                    session=session,
                    session_section=None,
                    test=test,
                    answer_data=answer_data
                )

            serializer = self.get_serializer(response)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except TestSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except SectionSession.DoesNotExist:
            return Response(
                {"error": "Section session not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # try:
        #     # Get required data from request
        #     submitted_answers = request.data.get('submitted_answers', {})
        #     section_session_id = request.data.get('section_session')
            
        #     # Get the session
        #     session = TestSession.objects.get(id=pk)
        #     test = session.test

        #     # Get section session if provided
        #     section_session = None
        #     # if section_session_id:
        #     #     section_session = SectionSession.objects.get(id=section_session_id)

        #     # Use the update_or_create_response class method
        #     response = UserResponse.update_or_create_response(
        #         session=session,
        #         session_section=section_session,
        #         test=test,
        #         answer_data=submitted_answers
        #     )

        #     serializer = self.get_serializer(response)
        #     return Response(serializer.data, status=status.HTTP_200_OK)

        # except TestSession.DoesNotExist:
        #     return Response(
        #         {"error": "Session not found"}, 
        #         status=status.HTTP_404_NOT_FOUND
        #     )
        # except SectionSession.DoesNotExist:
        #     return Response(
        #         {"error": "Section session not found"}, 
        #         status=status.HTTP_404_NOT_FOUND
        #     )
        # except Exception as e:
        #     return Response(
        #         {"error": str(e)}, 
        #         status=status.HTTP_500_INTERNAL_SERVER_ERROR
        #     )

    def create(self, request, *args, **kwargs):
        """Create a new response"""
        try:
            session_id = request.data.get('session')
            section_session_id = request.data.get('section_session')
            submitted_answers = request.data.get('submitted_answers', {})

            if not session_id:
                return Response(
                    {"error": "Session ID is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get the session and test
            session = TestSession.objects.get(id=session_id)
            test = session.test

            # Get section session if provided
            section_session = None
            if section_session_id:
                section_session = SectionSession.objects.get(id=section_session_id)

            # Use the update_or_create_response class method
            response = UserResponse.update_or_create_response(
                session=session,
                session_section=section_session,
                test=test,
                answer_data=submitted_answers
            )

            serializer = self.get_serializer(response)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except TestSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TestResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for test results (read-only)
    """
    serializer_class = TestResultSerializer
    # permission_classes = [permissions.IsAuthenticated]
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return TestResult.objects.filter(session__user=self.request.user).order_by('-created_at')

class RegisterView(generics.CreateAPIView):
    """
    API endpoint for user registration
    """
    queryset = get_user_model().objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Create the user
            user = serializer.save()
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                "user": UserSerializer(user).data,
                "token": str(refresh.access_token),
                "refresh": str(refresh)
            }, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CurrentUserView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for current user profile
    """
    serializer_class = UserSerializer
    # permission_classes = [permissions.IsAuthenticated]
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        return self.request.user


def get_career_recommendations_from_tests(user):
    """
    Get career recommendations based on user's test results (RIASEC, Motivation, Aptitude)
    Returns a list of (Career, match_score) tuples sorted by score
    """
    from careers.models import Career
    from core import choices
    from django.conf import settings
    import ast
    import json
    
    # Debug logging helper (only in DEBUG mode)
    def debug_log(message):
        if settings.DEBUG:
            print(f"[DEBUG] Career Recommendations - {message}")
    
    debug_log(f"Getting career recommendations for user: {user.email or user.mobile}")
    
    recommended_career_names = set()
    career_scores = {}  # {career_name: score}
    
    # Get test sessions for Career Interest Inventory (RIASEC)
    riasec_session = TestSession.objects.filter(
        user=user,
        test__title='Career Interest Inventory',
        is_completed=True
    ).order_by('-end_time').first()
    
    # Get test session for Motivation Assessment
    motivation_session = TestSession.objects.filter(
        user=user,
        test__title='Motivation Assessment',
        is_completed=True
    ).order_by('-end_time').first()
    
    # Get test session for Aptitude Assessment
    aptitude_session = TestSession.objects.filter(
        user=user,
        test__title='Aptitude Assessment',
        is_completed=True
    ).order_by('-end_time').first()
    
    # Process RIASEC (Career Interest Inventory) results
    if riasec_session:
        try:
            categories_record = TestTopCategories.objects.filter(
                user=user,
                test_paper=riasec_session.test
            ).first()
            
            if categories_record:
                high_categories = resolve_riasec_high_categories(
                    riasec_session,
                    categories_record.high_category,
                )
                low_category = categories_record.low_category
                
                debug_log(f"RIASEC Code: {high_categories}")
                
                hexaco_recommendations = get_hexaco_career_recommendations(
                    high_categories, low_category, riasec_session
                )
                
                # Extract career names from RIASEC recommendations
                riasec_careers = hexaco_recommendations.get('riasec_careers_to_opt', {})
                riasec_career_list = []
                for category in ["Traditional", "Trending", "Futuristic"]:
                    careers = riasec_careers.get(category, [])
                    for career_name in careers:
                        career_name_clean = career_name.strip()
                        recommended_career_names.add(career_name_clean)
                        riasec_career_list.append(f"{career_name_clean} ({category})")
                        # Higher score for Trending and Futuristic careers
                        if category == "Futuristic":
                            career_scores[career_name_clean] = career_scores.get(career_name_clean, 0) + 30
                        elif category == "Trending":
                            career_scores[career_name_clean] = career_scores.get(career_name_clean, 0) + 25
                        else:  # Traditional
                            career_scores[career_name_clean] = career_scores.get(career_name_clean, 0) + 20
                
                if riasec_career_list:
                    debug_log(f"RIASEC Careers Found ({len(riasec_career_list)}):")
                    for career in riasec_career_list:
                        debug_log(f"  - {career}")
                else:
                    debug_log("No RIASEC careers found")
        except Exception as e:
            debug_log(f"Error processing RIASEC results: {e}")
            print(f"Error processing RIASEC results: {e}")
    
    # Process Motivation Assessment results
    if motivation_session:
        try:
            categories_record = TestTopCategories.objects.filter(
                user=user,
                test_paper=motivation_session.test
            ).first()
            
            if categories_record:
                high_categories = categories_record.high_category
                low_category = categories_record.low_category
                
                debug_log(f"Motivation Category: {high_categories}")
                
                hexaco_recommendations = get_hexaco_career_recommendations(
                    high_categories, low_category, motivation_session
                )
                
                # Extract career names from Motivation recommendations
                motivation_careers = hexaco_recommendations.get('motivation_careers_to_opt', {})
                career_roles = motivation_careers.get('Career Category & Roles', [])
                motivation_career_list = []
                for role in career_roles:
                    if role and role.strip():
                        role_clean = role.strip()
                        recommended_career_names.add(role_clean)
                        motivation_career_list.append(role_clean)
                        career_scores[role_clean] = career_scores.get(role_clean, 0) + 15
                
                if motivation_career_list:
                    debug_log(f"Motivation Careers Found ({len(motivation_career_list)}):")
                    for career in motivation_career_list:
                        debug_log(f"  - {career}")
                else:
                    debug_log("No Motivation careers found")
        except Exception as e:
            debug_log(f"Error processing Motivation results: {e}")
            print(f"Error processing Motivation results: {e}")
    
    # Match career names to Career objects in database
    matched_careers = []
    unmatched_careers = []
    
    debug_log(f"Total unique career names from tests: {len(recommended_career_names)}")
    
    for career_name in recommended_career_names:
        # Try exact match first
        career = Career.objects.filter(
            name__iexact=career_name,
            publish_status=choices.PublishStatus.PUBLISHED
        ).first()
        
        match_type = "exact"
        # If not found, try partial match
        if not career:
            career = Career.objects.filter(
                name__icontains=career_name,
                publish_status=choices.PublishStatus.PUBLISHED
            ).first()
            match_type = "partial" if career else "none"
        
        if career:
            score = career_scores.get(career_name, 50.0)  # Default score if not found
            matched_careers.append((career, min(score, 100.0)))
            debug_log(f"  ✓ Matched ({match_type}): '{career_name}' → '{career.name}' (Score: {min(score, 100.0)})")
        else:
            unmatched_careers.append(career_name)
            debug_log(f"  ✗ Not found: '{career_name}'")
    
    # Sort by score descending
    matched_careers.sort(key=lambda x: x[1], reverse=True)
    
    debug_log(f"Successfully matched: {len(matched_careers)} careers")
    debug_log(f"Not found in database: {len(unmatched_careers)} careers")
    
    if matched_careers:
        debug_log("Final Recommended Careers (sorted by score):")
        for idx, (career, score) in enumerate(matched_careers[:20], 1):  # Show top 20
            debug_log(f"  {idx}. {career.name} (Score: {score:.1f}%)")
    
    return matched_careers


def career_swipe(request):
    """
    Career swipe: cluster-first. User chooses cluster(s) → swipe careers from that cluster.
    Completed clusters are tracked in session and shown as "checked".
    """
    from careers.models import Career, CareerCluster
    from core import choices
    from core.choices import ObjectStatus
    from django.conf import settings
    from django.db.models import Q, Count
    
    # Merge pending likes from session into user profile (after login)
    if request.user.is_authenticated and request.session.get('career_swipe_pending_likes'):
        from .models import CareerMatch
        pending = request.session.pop('career_swipe_pending_likes', [])
        request.session.modified = True
        for item in pending:
            try:
                cid = item.get('career_id')
                score = item.get('match_score', 0)
                if cid:
                    career = Career.objects.get(id=cid)
                    CareerMatch.objects.update_or_create(
                        user=request.user,
                        career=career,
                        defaults={'action': 'like', 'match_score': score}
                    )
            except (Career.DoesNotExist, ValueError, TypeError):
                pass
    
    def debug_log(message):
        if settings.DEBUG:
            print(f"[DEBUG] Career Swipe - {message}")
    
    # Viewed/checked cluster IDs (session)
    viewed_ids = list(request.session.get('career_swipe_viewed_cluster_ids') or [])
    try:
        viewed_ids = [int(x) for x in viewed_ids if x]
    except (ValueError, TypeError):
        viewed_ids = []
    
    # Selected cluster(s) from GET (?clusters=1 or ?clusters=1,2)
    cluster_param = (request.GET.get('clusters') or '').strip()
    selected_cluster_ids = []
    if cluster_param:
        for part in cluster_param.split(','):
            try:
                selected_cluster_ids.append(int(part.strip()))
            except (ValueError, TypeError):
                pass
    selected_cluster_ids = list(dict.fromkeys(selected_cluster_ids))
    
    # Anonymous: no profile/test data
    if not request.user.is_authenticated:
        has_tests = False
        user_profile_data = None
        has_hobbies = False
        has_interests = False
        show_profile_completion_popup = False
        recommended_careers = []
    else:
        # Check if user has completed tests
        has_tests = TestSession.objects.filter(
            user=request.user,
            is_completed=True
        ).exists()
        
        # Get user profile data and check if hobbies/interests are completed
        user_profile_data = None
        has_hobbies = False
        has_interests = False
        profile_complete = False
        
        if hasattr(request.user, 'user_profile') and request.user.user_profile:
            profile = request.user.user_profile
            hobbies_count = profile.hobbies.count()
            subjects_count = profile.subject.count()
            
            has_hobbies = hobbies_count > 0
            has_interests = subjects_count > 0
            profile_complete = has_hobbies and has_interests
            
            user_profile_data = {
                'hobbies': [h.name for h in profile.hobbies.all()],
                'subjects': [s.name for s in profile.subject.all()],
                'figure_out': [f.name for f in profile.figure_out.all()],
                'grade': profile.grade if profile.grade else None
            }
            
            # Debug logging - show info if student has interests/hobbies OR psychometric tests
            if has_hobbies or has_interests or has_tests:
                debug_log(f"User: {request.user.email or request.user.mobile}")
                debug_log(f"  Has Hobbies: {has_hobbies} (count: {hobbies_count})")
                debug_log(f"  Has Interests/Subjects: {has_interests} (count: {subjects_count})")
                debug_log(f"  Has Psychometric Tests: {has_tests}")
                debug_log(f"  Profile Complete: {profile_complete}")
                if profile_complete:
                    debug_log(f"  ✅ Profile is complete - No popup needed")
                else:
                    debug_log(f"  ⚠️  Profile incomplete - Showing completion popup")
        else:
            debug_log(f"User: {request.user.email or request.user.mobile}")
            debug_log(f"  No UserProfile found - Showing completion popup")
        
        # Check if profile needs completion (missing hobbies OR interests)
        # Popup shows if at least one (hobbies OR interests) is missing
        show_profile_completion_popup = not (has_hobbies and has_interests)
        
        # For match % in swipe mode: test-based or profile-based scores
        recommended_careers = []
        if has_tests:
            try:
                recommended_careers = get_career_recommendations_from_tests(request.user)
                debug_log(f"Found {len(recommended_careers)} careers from test results")
            except Exception as e:
                debug_log(f"Error getting test-based recommendations: {e}")
                recommended_careers = []
    
    show_match_score = request.user.is_authenticated and (has_tests or has_hobbies or has_interests)
    
    # Cluster list for picker: from DB (like career-battle), with stream count and sample career names
    clusters_queryset = CareerCluster.objects.filter(parent__isnull=True).order_by('name')
    if not clusters_queryset.exists():
        clusters_queryset = CareerCluster.objects.all().order_by('name')
    
    cluster_ids = [c.id for c in clusters_queryset]
    # One query: all (cluster_id, career_name) for these clusters, published only
    from collections import defaultdict
    stream_by_cluster = defaultdict(list)
    if cluster_ids:
        for cid, name in Career.objects.filter(
            career_cluster__id__in=cluster_ids,
            publish_status=choices.PublishStatus.PUBLISHED
        ).values_list('career_cluster', 'name').distinct():
            if name and name not in stream_by_cluster[cid]:
                stream_by_cluster[cid].append(name)
    for cid in stream_by_cluster:
        stream_by_cluster[cid].sort()
    
    clusters_with_streams = []
    for c in clusters_queryset:
        names = stream_by_cluster.get(c.id, [])
        clusters_with_streams.append({
            'cluster': c,
            'stream_count': len(names),
            'stream_names': names[:10],
        })
    
    careers = []
    current_cluster_names = []
    show_swipe = False
    
    if selected_cluster_ids:
        valid_clusters = list(CareerCluster.objects.filter(
            id__in=selected_cluster_ids,
            object_status=ObjectStatus.ACTIVE
        ))
        valid_ids = [c.id for c in valid_clusters]
        current_cluster_names = [c.name for c in valid_clusters if c.name]
        
        if valid_ids:
            # Mark these clusters as checked (viewed)
            for cid in valid_ids:
                if cid not in viewed_ids:
                    viewed_ids.append(cid)
            request.session['career_swipe_viewed_cluster_ids'] = viewed_ids
            request.session.modified = True
            
            careers_queryset = Career.objects.filter(
                career_cluster__id__in=valid_ids,
                publish_status=choices.PublishStatus.PUBLISHED
            ).distinct().select_related().prefetch_related(
                'career_cluster', 'skills', 'career_tags'
            )[:50]
            
            career_score_map = {}
            if show_match_score and recommended_careers:
                for career, score in recommended_careers:
                    career_score_map[career] = score
            elif show_match_score and user_profile_data and request.user.is_authenticated:
                for career in careers_queryset:
                    score = 50.0
                    if user_profile_data.get('hobbies'):
                        career_tags = [t.name.lower() for t in career.career_tags.all()]
                        hobby_names = [h.lower() for h in user_profile_data['hobbies']]
                        score += sum(1 for h in hobby_names if h in ' '.join(career_tags)) * 10
                    if user_profile_data.get('subjects'):
                        career_skills = [s.name.lower() for s in career.skills.all()]
                        subject_names = [s.lower() for s in user_profile_data['subjects']]
                        score += sum(1 for s in subject_names if s in ' '.join(career_skills)) * 8
                    career_score_map[career] = min(score, 100.0)
            
            for career in careers_queryset:
                match_score = career_score_map.get(career, 85.0) if show_match_score else 0
                career_data = {
                    'career': career,
                    'image_url': career.get_image_url() or '/static/images/career-icon.png',
                    'url': career.url(),
                    'clusters': [c.name for c in career.career_cluster.all()],
                    'skills': [s.name for s in career.skills.all()[:5]],
                    'match_score': round(match_score, 1)
                }
                careers.append(career_data)
            show_swipe = True
    
    clusters = list(clusters_queryset)
    viewed_cluster_names = list(CareerCluster.objects.filter(id__in=viewed_ids).order_by('name').values_list('name', flat=True)) if viewed_ids else []
    
    from django.urls import reverse
    from urllib.parse import urlencode
    login_next = request.build_absolute_uri(reverse('post_matric:career_swipe'))
    login_qs = urlencode({'next': login_next, 'embed': '1'})
    login_url = reverse('users:login') + '?' + login_qs
    login_url_absolute = request.build_absolute_uri(reverse('users:login') + '?' + login_qs)
    login_url_next_matches = reverse('users:login') + '?' + urlencode({
        'next': request.build_absolute_uri(reverse('post_matric:view_matches'))
    })
    
    context = {
        'careers': careers,
        'show_swipe': show_swipe,
        'clusters': clusters,
        'clusters_with_streams': clusters_with_streams,
        'viewed_cluster_ids': viewed_ids,
        'viewed_cluster_names': viewed_cluster_names,
        'current_cluster_names': current_cluster_names,
        'show_match_score': show_match_score,
        'has_tests': has_tests,
        'user_profile_data': user_profile_data,
        'user': request.user,
        'show_profile_completion_popup': show_profile_completion_popup,
        'has_hobbies': has_hobbies,
        'has_interests': has_interests,
        'user_authenticated': request.user.is_authenticated,
        'login_url': login_url,
        'login_url_absolute': login_url_absolute,
        'login_url_next_matches': login_url_next_matches,
        'career_swipe_next': request.build_absolute_uri(reverse('post_matric:career_swipe')),
    }
    
    return render(request, 'template20/app_post_matric/career_swipe.html', context)


@login_required
def view_matches(request):
    """
    View My Matches - Display all careers user has liked
    """
    from careers.models import Career
    from .models import CareerMatch
    
    # Get all liked careers for the user (handle missing table gracefully)
    matches = []
    try:
        # Check if table exists
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'app_post_matric_careermatch'")
            table_exists = cursor.fetchone() is not None
        
        if table_exists:
            matches = CareerMatch.objects.filter(
                user=request.user,
                action='like'
            ).select_related('career').order_by('-created_at')
        else:
            print("[DEBUG] CareerMatch table does not exist - returning empty matches")
    except Exception as e:
        print(f"[DEBUG] Error accessing CareerMatch table (non-critical): {str(e)}")
        matches = []
    
    context = {
        'matches': matches,
        'match_count': len(matches) if isinstance(matches, list) else matches.count()
    }
    
    return render(request, 'template20/app_post_matric/career_matches.html', context)


@login_required
def top_recommendations(request):
    """
    Top Recommendations - Show top N career matches based on user profile/test results
    Uses same logic as career_swipe for consistency
    """
    from careers.models import Career
    from core import choices
    from .models import CareerMatch
    from django.conf import settings
    
    # Debug logging helper (only in DEBUG mode)
    def debug_log(message):
        if settings.DEBUG:
            print(f"[DEBUG] Top Recommendations - {message}")
    
    debug_log(f"Getting top recommendations for user: {request.user.email or request.user.mobile}")
    
    # Check if user has completed tests
    has_tests = TestSession.objects.filter(
        user=request.user,
        is_completed=True
    ).exists()
    
    # Get user profile data for matching
    user_profile_data = None
    has_hobbies = False
    has_interests = False
    
    if hasattr(request.user, 'user_profile') and request.user.user_profile:
        profile = request.user.user_profile
        hobbies_count = profile.hobbies.count()
        subjects_count = profile.subject.count()
        
        has_hobbies = hobbies_count > 0
        has_interests = subjects_count > 0
        
        user_profile_data = {
            'hobbies': [h.name for h in profile.hobbies.all()],
            'subjects': [s.name for s in profile.subject.all()],
            'figure_out': [f.name for f in profile.figure_out.all()],
            'grade': profile.grade if profile.grade else None
        }
        
        debug_log(f"  Has Hobbies: {has_hobbies} (count: {hobbies_count})")
        debug_log(f"  Has Interests/Subjects: {has_interests} (count: {subjects_count})")
        debug_log(f"  Has Psychometric Tests: {has_tests}")
    
    # Get career recommendations from test results if available
    scored_careers = []
    if has_tests:
        try:
            recommended_careers = get_career_recommendations_from_tests(request.user)
            scored_careers = recommended_careers[:20]  # Top 20 from test results
            debug_log(f"Using {len(scored_careers)} test-recommended careers")
        except Exception as e:
            debug_log(f"Error getting test-based recommendations: {e}")
            scored_careers = []
    
    # If no test results, use profile-based matching (same logic as career_swipe)
    if not scored_careers and user_profile_data and (has_hobbies or has_interests):
        debug_log("No test results - Using profile-based recommendations")
        all_careers = Career.objects.filter(
            publish_status=choices.PublishStatus.PUBLISHED
        ).select_related().prefetch_related('career_cluster', 'skills', 'career_tags')
        
        for career in all_careers[:100]:  # Check top 100 for performance
            score = 50.0  # Base score
            
            # Score based on hobbies
            if user_profile_data.get('hobbies'):
                career_tags = [tag.name.lower() for tag in career.career_tags.all()]
                hobby_names = [h.lower() for h in user_profile_data['hobbies']]
                hobby_matches = sum(1 for hobby in hobby_names if hobby in ' '.join(career_tags))
                score += hobby_matches * 10
                if hobby_matches > 0:
                    debug_log(f"  Career '{career.name}' matched {hobby_matches} hobbies")
            
            # Score based on subjects/interests
            if user_profile_data.get('subjects'):
                career_skills = [s.name.lower() for s in career.skills.all()]
                subject_names = [s.lower() for s in user_profile_data['subjects']]
                subject_matches = sum(1 for subject in subject_names if subject in ' '.join(career_skills))
                score += subject_matches * 8
                if subject_matches > 0:
                    debug_log(f"  Career '{career.name}' matched {subject_matches} subjects")
            
            scored_careers.append((career, min(score, 100.0)))
        
        debug_log(f"Profile-based recommendations: {len(scored_careers)} careers")
    elif not scored_careers:
        # Fallback to all published careers if no test results and no profile data
        debug_log("No test results, no profile data - Using default published careers")
        careers_queryset = Career.objects.filter(
            publish_status=choices.PublishStatus.PUBLISHED
        ).select_related().prefetch_related('career_cluster', 'skills', 'career_tags')
        
        for career in careers_queryset[:50]:  # Limit for performance
            score = 50.0  # Base score
            scored_careers.append((career, min(score, 100.0)))
    
    # Sort by score descending and take top 10
    scored_careers.sort(key=lambda x: x[1], reverse=True)
    top_careers = scored_careers[:10]
    
    if top_careers:
        debug_log("Top 10 Recommended Careers:")
        for idx, (career, score) in enumerate(top_careers, 1):
            debug_log(f"  {idx}. {career.name} (Score: {score:.1f}%)")
    
    context = {
        'top_careers': top_careers,
        'has_tests': has_tests,
        'user_profile_data': user_profile_data
    }
    
    return render(request, 'template20/app_post_matric/top_recommendations.html', context)


@login_required
def career_clusters_info(request):
    """
    Career Clusters Info - Display information about all 16 career clusters
    """
    from careers.models import CareerCluster, Career
    from core import choices
    
    # Get all top-level career clusters
    clusters = CareerCluster.objects.filter(parent__isnull=True).prefetch_related('career_clusters')
    
    # Get sample careers for each cluster
    cluster_data = []
    for cluster in clusters:
        careers = Career.objects.filter(
            career_cluster=cluster,
            publish_status=choices.PublishStatus.PUBLISHED
        )[:3]  # Get 3 sample careers
        cluster_data.append({
            'cluster': cluster,
            'sample_careers': list(careers),
            'career_count': Career.objects.filter(
                career_cluster=cluster,
                publish_status=choices.PublishStatus.PUBLISHED
            ).count()
        })
    
    context = {
        'cluster_data': cluster_data,
        'total_clusters': len(cluster_data)
    }
    
    return render(request, 'template20/app_post_matric/career_clusters.html', context)


def swipe_career_api(request):
    """
    API endpoint to handle swipe actions (like/pass).
    Anonymous users: 'like' is stored in session and merged to profile after login.
    Authenticated users: saved to CareerMatch.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        import json
        data = json.loads(request.body)
        career_id = data.get('career_id')
        action = data.get('action')  # 'like' or 'pass'
        match_score = data.get('match_score', 0)
        notes = data.get('notes', '')
        
        if not career_id or action not in ['like', 'pass']:
            return JsonResponse({'error': 'Invalid data'}, status=400)
        
        from careers.models import Career
        career = Career.objects.get(id=career_id)
        
        if not request.user.is_authenticated:
            # Anonymous: store 'like' in session; 'pass' is not stored
            if action == 'like':
                key = 'career_swipe_pending_likes'
                pending = request.session.get(key, [])
                # Avoid duplicates
                if not any(p.get('career_id') == career_id for p in pending):
                    pending.append({
                        'career_id': career_id,
                        'match_score': match_score,
                    })
                    request.session[key] = pending
                    request.session.modified = True
            return JsonResponse({
                'success': True,
                'action': action,
                'career_id': career_id,
                'anonymous': True,
            })
        
        # Authenticated: save to CareerMatch
        match = None
        created = False
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SHOW TABLES LIKE 'app_post_matric_careermatch'")
                table_exists = cursor.fetchone() is not None
            
            if table_exists:
                match, created = CareerMatch.objects.update_or_create(
                    user=request.user,
                    career=career,
                    defaults={
                        'action': action,
                        'match_score': match_score,
                        'notes': notes
                    }
                )
            else:
                print("[DEBUG] CareerMatch table does not exist - skipping match save")
        except Exception as e:
            print(f"[DEBUG] Error accessing CareerMatch table (non-critical): {str(e)}")
        
        return JsonResponse({
            'success': True,
            'action': action,
            'career_id': career_id,
            'created': created if match else False
        })
        
    except Career.DoesNotExist:
        return JsonResponse({'error': 'Career not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)