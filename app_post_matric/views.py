from rest_framework import viewsets, permissions, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
# from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import UserProfile
# from .models import User
from .models import (
    TestCategory, Test, Question, Answer,
    TestSession, UserResponse, TestResult, Sections, SectionSession, TestTopCategories,
    TestCompletionPopup
)
from .serializers import (
    TestCategorySerializer, TestCategoryDetailSerializer,
    TestSerializer, TestDetailSerializer,
    QuestionSerializer, AnswerSerializer,
    TestSessionSerializer, TestSessionDetailSerializer,
    UserResponseSerializer, TestResultSerializer,
    UserSerializer, ResponseDetailSerializer, SectionsSerializer, SectionSessionSerializer
)
import re
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout, get_user_model
# from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.template.loader import get_template
from django.conf import settings
User = get_user_model()
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
    
    try:
        # Get all test sessions for the current user (same as old code)
        test_sessions = TestSession.objects.filter(user=request.user)
        
        # Initialize test status dictionary with default values for all tests (same as old code)
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
        
        # Update with actual data if it exists (same as old code logic)
        for session in test_sessions:
            test_id = session.test.id
            test_title = session.test.title.lower().strip()
            
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
                section_sessions = SectionSession.objects.filter(session=session)
                sections_status = {}
                
                for section_session in section_sessions:
                    sections_status[section_session.section.title] = {
                        'completed': section_session.is_completed,
                        'session_id': section_session.id
                    }
                
                test_status[4].update({
                    'completed': session.is_completed,
                    'session_id': session.id,
                    'total_sections': section_sessions.count(),
                    'completed_sections': section_sessions.filter(is_completed=True).count(),
                    'sections_status': sections_status
                })
            else:
                test_status[test_id] = {
                    'completed': session.is_completed,
                    'session_id': session.id
                }
        
        # Check which popups have been answered
        popup_answers = TestCompletionPopup.objects.filter(user=request.user)
        answered_popups = {popup.test_type for popup in popup_answers}
        
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
        
        context = {
            'test_status': json.dumps(test_status),
            'popup_status': json.dumps(popup_status),
            'test_type_map': json.dumps(test_type_map)
        }
        
        return render(request, "template20/app_post_matric/tests.html", context)
    except Exception as e:
        print(f"Error in Tests view: {str(e)}")
        return render(request, "template20/app_post_matric/tests.html", {
            'error': 'An error occurred while loading test status.',
            'test_status': json.dumps({
                1: {'completed': False},
                2: {'completed': False},
                3: {'completed': False},
                4: {
                    'completed': False,
                    'total_sections': 0,
                    'completed_sections': 0,
                    'sections_status': {}
                }
            }),
            'popup_status': json.dumps({
                'personality': False,
                'motivation': False,
                'career_interest': False,
                'aptitude': False
            }),
            'test_type_map': json.dumps({})
        })


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

def get_hexaco_or_riasec_career_mapping(latest_session):
    try:

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'hexaco_personality.json')
        with open(path, 'r') as file:
            hexaco_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'interest_riasec.json')
        with open(path, 'r') as file:
            riasec_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'Motivation_Career.json')
        with open(path, 'r') as file:
            motivation_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'aptitude_weak_areas_improvement_plan_2.json')
        with open(path, 'r') as file:
            aptitude_weak_areas_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'aptitude_strength_narrative_1.json')
        with open(path, 'r') as file:
            aptitude_strength_narrative_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'Aptitude_report_main-modified1.json')
        with open(path, 'r') as file:
            Aptitude_report_main_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'aptitude_recommendations_for_colleges_3.json')
        with open(path, 'r') as file:
            aptitude_recommendations_data = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'merged-1754477770562.json')
        with open(path, 'r') as file:
            career_mergerd_path = json.load(file)

        path = os.path.join(settings.BASE_DIR, 'static', 'data', 'combined_report_Average_above_average.json')
        with open(path, 'r') as file:
            CombinedReport_data = json.load(file)

        return hexaco_data, riasec_data.get('code'), motivation_data.get('rows'), aptitude_weak_areas_data.get('rows'), aptitude_strength_narrative_data.get('rows'), Aptitude_report_main_data.get('rows'),aptitude_recommendations_data.get('rows'), career_mergerd_path, CombinedReport_data.get('rows')
        

    except Exception as e:
        print("exception: ",e)
        return None, None, None, None, None, None , None, None

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

        'riasec_careers_to_opt': {
            "Traditional": [],
            "Trending": [],
            "Futuristic": []
        },

        'career_code_discription':[],

        'motivation_careers_to_opt': {
            "Motivation Style": [],
            "Career Category & Roles": [],
            "Key Characteristics & Details": []
        },
        
        'aptitude_improvement_plan': [],
        'aptitude_strength_narrative': [],
        'aptitude_Recommended_College_Courses':[],
        'aptitude_roles_guidance':[],
        'career_guidance_selected':[],
        }
    
    try:        
        hexaco_data, riasec_data, motivation_data, aptitude_weak_areas_data , aptitude_strength_narrative_data, Aptitude_report_main_data, aptitude_recommendations_data, career_mergerd_path, CombinedReport_data = get_hexaco_or_riasec_career_mapping(latest_session)
        
        
        if latest_session.test.title == 'Career Interest Inventory':
            # Process RIASEC codes
            
            riasec_code_categories = high_categories

            if high_categories in career_mergerd_path:
                ris_data = {f"{high_categories}": career_mergerd_path[high_categories]}
                result['career_code_discription'] = [ris_data]
                print(f"Description data for {high_categories}: {ris_data}")
            else:
                print(f"Warning: RIASEC code {high_categories} not found in career_mergerd_path.")
            
            if riasec_code_categories in riasec_data:
                category_data = riasec_data[riasec_code_categories]
                
                # Process each career category
                for category in ["Traditional", "Trending", "Futuristic"]:
                    riasec_key = f"{category}_Careers" if category != "Futuristic" else "Futuristic_Emerging_Careers"
                    if riasec_key in category_data:
                        careers = category_data[riasec_key].split("<br/>")
                        result['riasec_careers_to_opt'][category] = [c.strip() for c in careers if c.strip()]
            else:
                print(f"Warning: RIASEC code {riasec_code_categories} not found in data.")


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

        elif latest_session.test.title == 'Motivation Assessment':
            domain = map_motivation_domain_to_trait(high_categories)
            domain_data = next((row for row in motivation_data if row['Domain'] == domain), None)

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

                # ---------- Build fast lookup maps ----------
                weak_map = {row.get('Areas'): row for row in (aptitude_weak_areas_data or []) if row.get('Areas')}
                strength_map = {row.get('Areas'): row for row in (aptitude_strength_narrative_data or []) if row.get('Areas')}
                rec_map = {normalize_area(row.get('Areas')): row for row in (aptitude_recommendations_data or []) if row.get('Areas')}
                roles_map = {}
                for row in (Aptitude_report_main_data or []):
                    k = normalize_area(row.get('Area'))
                    if k:
                        roles_map.setdefault(k, []).append(row)

                # ---------- Below Average: Improvement Plan ----------
                for area in below_categories:
                    data = weak_map.get(area)
                    if data:
                        remarks  = [(r or '').rstrip('.') for r in data.get('Remarks', [])]
                        duration = data.get('Duration', 'No details available')
                        result['aptitude_improvement_plan'].append({
                            'Area': data.get('Areas', 'Unknown'),
                            'Remarks': remarks,
                            'Duration': duration,
                            'Category': 'Below Average'
                        })

                # ---------- Helper: Strength + Recommendations + Roles ----------
                def process_strength_recs_roles(areas):
                    for area in areas:
                        # Strength narrative
                        srow = strength_map.get(area)
                        if srow:
                            major_points = [(r or '').rstrip('.') for r in srow.get('Major points', [])]
                            result['aptitude_strength_narrative'].append({
                                'Area': srow.get('Areas', 'Unknown'),
                                'Major_points': major_points
                            })
                        # Recommendations
                        rrow = rec_map.get(normalize_area(area))
                        if rrow:
                            recommended_college = list(rrow.get('Recommended College Courses', []))
                            result['aptitude_Recommended_College_Courses'].append({
                                'Area': rrow.get('Areas', 'Unknown'),
                                'Recommended_College': recommended_college
                            })
                        # Roles guidance
                        matches = roles_map.get(normalize_area(area), [])
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
                process_strength_recs_roles(above_categories)
                process_strength_recs_roles(average_categories)

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

                # CRITICAL CHECK: If both lists are empty, return empty result immediately
                if not selected_areas:
                    career_guidance_selected = []
                    result['career_guidance_selected'].extend(career_guidance_selected)
                    return  # or continue with other logic

                # Create a mapping from your area names to JSON area names
                area_mapping = {
                    'Spatial Reasoning': 'Spatial Reasoning',
                    'Clerical speed & Accuracy': 'Clerical speed & Accuracy',  # Keep original JSON name
                    'Language & Verbal Reasoning': 'Language & Verbal Reasoning',  # Keep original JSON name
                    'Numerical Reasoning': 'Numerical Reasoning',
                    'Abstract Reasoning': 'Abstract Reasoning',
                    'Logical Reasoning': 'Logical Reasoning',
                    'Mechanical Reasoning': 'Mechanical Reasoning'
                }

                # Normalize selected areas to match JSON format
                normalized_selected = set()
                for area in selected_areas:
                    mapped_area = area_mapping.get(area, area)  # Use mapping or original if not found
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
                    print("No exact match found, looking for entries that contain all selected areas...")
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
                            print(f"Found superset match: {entry['Areas']}")

                print("career_guidance_selected", career_guidance_selected)

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
    return render(request, "results_list.html")

@login_required
def Results(request):
    try:
        # Get test_id from query params or session
        test_id = request.GET.get('test_id', None)
        if test_id is not None:
            try:
                test_id = int(test_id)
            except ValueError:
                test_id = request.GET.get('test_id') or request.session.get('last_test_id')
        
        # Build the query
        query = {
            'user': request.user,
            'is_completed': True
        }
        
        if test_id:
            query['test_id'] = test_id
        # Get the test session
        latest_session = TestSession.objects.filter(**query).order_by('-end_time').first()
        
        if not latest_session:
            return render(request, "results.html", {
                'error': 'No completed test found',
                'no_results': True
            })
        
        
        # Get categories record
        categories_record = TestTopCategories.objects.filter(
            user=request.user,
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
                
                high_categories = json.loads(high_categories)
            else:
                high_categories = categories_record.high_category
                high_categories = high_categories.strip("[]").strip()

            low_category = categories_record.low_category

        all_tests_completed = False

        # Check if all 4 tests are completed
        all_tests_completed = False
        
        # Check for completed sessions for each test type
        test1_completed = TestSession.objects.filter(
            user=request.user, 
            test__id=1,
            is_completed=True
        ).exists()
        
        test2_completed = TestSession.objects.filter(
            user=request.user, 
            test__id=2,
            is_completed=True
        ).exists()
        
        test3_completed = TestSession.objects.filter(
            user=request.user, 
            test__id=3,
            is_completed=True
        ).exists()
        
        test4_completed = TestSession.objects.filter(
            user=request.user, 
            test__id=4,
            is_completed=True
        ).exists()
        
        if test1_completed and test2_completed and test3_completed and test4_completed:
            all_tests_completed = True

        user = request.user
        try:
            # Retrieve the UserProfile for the logged-in user (create if not exists)
            user_profile, created = UserProfile.objects.get_or_create(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        try:
            # Retrieve the UserProfile for the logged-in user
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
            'user': request.user,
            'test_id': test_id,
            'all_tests_completed': all_tests_completed,
            'high_categories': high_categories,
            'low_category': low_category,
            'test_name': latest_session.test.title,
            'test_type': latest_session.test.title,
            'completed_at': latest_session.end_time,
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
            context['above_list'] = high_categories.get("Above Average", [])
            context['average_list'] = high_categories.get("Average", [])
            context['below_list'] = high_categories.get("Below Average", [])
        else:
            pass
        
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
                'low_trait': map_hexaco_code_to_trait(low_category) if low_category else None
            })

        elif latest_session.test.title == 'Career Interest Inventory' and high_categories:
            
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            context.update({
                'riasec_careers_to_opt': hexaco_recommendations['riasec_careers_to_opt'],
                'career_code_discription': hexaco_recommendations['career_code_discription'],
            })
        elif latest_session.test.title == 'Motivation Assessment' and high_categories:
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            
            context.update({
                'motivation_careers_to_opt': hexaco_recommendations['motivation_careers_to_opt'],
            })
        elif latest_session.test.title == 'Aptitude Assessment' and high_categories:
            
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            # breakpoint()
            context.update({
                'aptitude_improvement_plan': hexaco_recommendations['aptitude_improvement_plan'],
                'aptitude_strength_narrative': hexaco_recommendations['aptitude_strength_narrative'],
                'aptitude_Recommended_College_Courses': hexaco_recommendations['aptitude_Recommended_College_Courses'],
                'aptitude_roles_guidance': hexaco_recommendations['aptitude_roles_guidance'],
                'career_guidance_selected': hexaco_recommendations['career_guidance_selected'],
            })
        
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
                    if 'Aptitude' in title:
                        test_data['result_data'] = stored_data.copy()
                    else:
                        normalized_data = {}
                        for key, value in stored_data.items():
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
                        test_data['result_data'] = normalized_data
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
        
        return render(request, "results.html", context)    
        
    except Exception as e:
        return render(request, "results.html", {
            'error': f'An error occurred: {str(e)}',
            'no_results': True
        })
    
def CombinedReport(request, user_id=None):
    try:
        print("user_id:", user_id)
        
        # Get the target user (student) whose report we want to view
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
            print(f"Viewing report for student: {target_user}")
        else:
            target_user = request.user
            print(f"Viewing own report as: {target_user}")
        
        # Get completed test sessions for the TARGET USER (not the logged-in user)
        completed_sessions = TestSession.objects.filter(
            user=target_user,
            is_completed=True
        ).order_by('-end_time')
        
        if not completed_sessions:
            return render(request, "combined_report.html", {
                'error': 'No completed test found',
                'no_results': True,
                'user': target_user  # Pass the target user to the template
            })

        user = target_user
        try:
            # Retrieve the UserProfile for the logged-in user (create if not exists)
            user_profile, created = UserProfile.objects.get_or_create(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

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
            student_name = user.email  # Assuming email is used as student name
            grade = user_profile.grade

        except UserProfile.DoesNotExist:
            print("UserProfile does not exist.")

        # Initialize context and containers
        context = {
            'user': target_user,  # Use the target user, not request.user
            'completed_tests': [],
            'no_results': False,
            'viewing_as_admin': user_id is not None, # Flag to indicate admin view
            # Add user profile information
            'created_date': created_date if 'created_date' in locals() else None,
            'gender': gender_display if 'gender_display' in locals() else None,
            'schoolname': schoolname if 'schoolname' in locals() else None,
            'student_name': student_name if 'student_name' in locals() else None,
            'grade': grade if 'grade' in locals() else None
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
                    'completed_at': session.end_time,
                    'test_id': session.test.id
                })

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
                        # For Aptitude tests, keep direct numeric values (section names -> scores)
                        if 'Aptitude' in title:
                            test_data['result_data'] = stored_data.copy()
                        else:
                            # For Personality and Career: normalize to {'score': X} structure
                            normalized_data = {}
                            for key, value in stored_data.items():
                                if isinstance(value, dict):
                                    # If it has 'score' key, use it directly
                                    if 'score' in value:
                                        normalized_data[key] = {'score': value['score']}
                                    # If value is just a number, wrap it
                                    elif isinstance(value, (int, float)):
                                        normalized_data[key] = {'score': value}
                                    else:
                                        # Otherwise keep as is
                                        normalized_data[key] = value
                                elif isinstance(value, (int, float)):
                                    # Wrap numeric values for Personality/Career
                                    normalized_data[key] = {'score': value}
                                else:
                                    # Fallback for other types
                                    normalized_data[key] = {'score': 0}
                            test_data['result_data'] = normalized_data
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
                print(f"Error getting test result data: {e}")
                import traceback
                traceback.print_exc()

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
                        print(f"Error parsing personality categories: {e}")
                        import traceback
                        print(traceback.format_exc())
            except Exception as e:
                print(f"Error processing personality test data: {e}")
                import traceback
                print(traceback.format_exc())

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
                        high_categories = categories_record.high_category.strip("[]").strip()
                        low_category = categories_record.low_category
                        
                        hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, career_session)
                        context.update({
                            'riasec_high_categories': high_categories,
                            'riasec_careers_to_opt': hexaco_recommendations['riasec_careers_to_opt'],
                            'career_code_discription': hexaco_recommendations['career_code_discription'],
                        })
                    except Exception as e:
                        print(f"Error processing career interest data: {e}")
                        import traceback
                        print(traceback.format_exc())
            except Exception as e:
                print(f"Error processing career session data: {e}")
                import traceback
                print(traceback.format_exc())
            
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
                        })
                    except Exception as e:
                        print(f"Error processing motivation data: {e}")
                        import traceback
                        print(traceback.format_exc())
            except Exception as e:
                print(f"Error processing motivation session data: {e}")
                import traceback
                print(traceback.format_exc())
            
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
                        
                        context.update({
                            'above_list': high_categories.get("Above Average", []),
                            'average_list': high_categories.get("Average", []),
                            'below_list': high_categories.get("Below Average", [])
                        })
                        
                        hexaco_recommendations = get_hexaco_career_recommendations(high_categories, None, aptitude_session)
                        context.update({
                            'aptitude_improvement_plan': hexaco_recommendations['aptitude_improvement_plan'],
                            'aptitude_strength_narrative': hexaco_recommendations['aptitude_strength_narrative'],
                            'aptitude_Recommended_College_Courses': hexaco_recommendations['aptitude_Recommended_College_Courses'],
                            'aptitude_roles_guidance': hexaco_recommendations['aptitude_roles_guidance'],
                            'career_guidance_selected': hexaco_recommendations['career_guidance_selected'],
                        })
                    except json.JSONDecodeError as e:
                        print(f"Error decoding aptitude categories JSON: {e}")
                        import traceback
                        print(traceback.format_exc())
                    except Exception as e:
                        print(f"Error processing aptitude data: {e}")
                        import traceback
                        print(traceback.format_exc())
            except Exception as e:
                print(f"Error processing aptitude session data: {e}")
                import traceback
                print(traceback.format_exc())
        
        return render(request, "combined_report.html", context)
        
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        print(f"Error in CombinedReport: {str(e)}")
        print(trace)
        return render(request, "combined_report.html", {
            'error': f'An error occurred: {str(e)}',
            'traceback': trace,  # Include the traceback in the context for debugging
            'no_results': True
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
    
    return render(request, "test_details.html", {"test_id": id})

@login_required
def Test_results(request, id):
    try:
        # Use id from URL as test_id
        test_id = id
        
        # Build the query
        query = {
            'user': request.user,
            'is_completed': True
        }
        
        if test_id:
            query['test_id'] = test_id
        # Get the test session
        latest_session = TestSession.objects.filter(**query).order_by('-end_time').first()
        
        if not latest_session:
            return render(request, "template20/app_post_matric/test_results.html", {
                'error': 'No completed test found',
                'no_results': True
            })
        
        
        # Get categories record
        categories_record = TestTopCategories.objects.filter(
            user=request.user,
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
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error parsing high_categories JSON: {e}")
                    high_categories = {}
            else:
                high_categories = categories_record.high_category
                high_categories = high_categories.strip("[]").strip()

            low_category = categories_record.low_category

        all_tests_completed = False

        # Check if all 4 tests are completed
        all_tests_completed = False
        
        # Check for completed sessions for each test type
        test1_completed = TestSession.objects.filter(
            user=request.user, 
            test__id=1,
            is_completed=True
        ).exists()
        
        test2_completed = TestSession.objects.filter(
            user=request.user, 
            test__id=2,
            is_completed=True
        ).exists()
        
        test3_completed = TestSession.objects.filter(
            user=request.user, 
            test__id=3,
            is_completed=True
        ).exists()
        
        test4_completed = TestSession.objects.filter(
            user=request.user, 
            test__id=4,
            is_completed=True
        ).exists()
        
        if test1_completed and test2_completed and test3_completed and test4_completed:
            all_tests_completed = True

        user = request.user
        try:
            # Retrieve the UserProfile for the logged-in user (create if not exists)
            user_profile, created = UserProfile.objects.get_or_create(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        try:
            # Retrieve the UserProfile for the logged-in user
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
            'user': request.user,
            'test_id': test_id,
            'all_tests_completed': all_tests_completed,
            'high_categories': high_categories,
            'low_category': low_category,
            'test_name': latest_session.test.title,
            'test_type': latest_session.test.title,
            'completed_at': latest_session.end_time,
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
                'low_trait': map_hexaco_code_to_trait(low_category) if low_category else None
            })

        elif latest_session.test.title == 'Career Interest Inventory' and high_categories:
            
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            context.update({
                'riasec_careers_to_opt': hexaco_recommendations['riasec_careers_to_opt'],
                'career_code_discription': hexaco_recommendations['career_code_discription'],
            })
        elif latest_session.test.title == 'Motivation Assessment' and high_categories:
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            
            context.update({
                'motivation_careers_to_opt': hexaco_recommendations['motivation_careers_to_opt'],
            })
        elif latest_session.test.title == 'Aptitude Assessment' and high_categories:
            
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            # breakpoint()
            context.update({
                'aptitude_improvement_plan': hexaco_recommendations['aptitude_improvement_plan'],
                'aptitude_strength_narrative': hexaco_recommendations['aptitude_strength_narrative'],
                'aptitude_Recommended_College_Courses': hexaco_recommendations['aptitude_Recommended_College_Courses'],
                'aptitude_roles_guidance': hexaco_recommendations['aptitude_roles_guidance'],
                'career_guidance_selected': hexaco_recommendations['career_guidance_selected'],
            })
        
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
                    if 'Aptitude' in title:
                        test_data['result_data'] = stored_data.copy()
                    else:
                        normalized_data = {}
                        for key, value in stored_data.items():
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
                        test_data['result_data'] = normalized_data
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
        
        # Use the new template for results display
        return render(request, "template20/app_post_matric/test_results.html", context)    
        
    except Exception as e:
        import json as _json
        return render(request, "template20/app_post_matric/test_results.html", {
            'error': f'An error occurred: {str(e)}',
            'no_results': True,
            'test_results_json': _json.dumps([])
        })


@login_required
def download_test_results_pdf(request, id):
    """Generate and download PDF for test results"""
    try:
        import weasyprint
        import ssl
        
        # Use id from URL as test_id
        test_id = id
        
        # Build the query
        query = {
            'user': request.user,
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
            'test_name': latest_session.test.title,
            'test_type': latest_session.test.title,
            'completed_at': latest_session.end_time,
            'user': request.user,
            'test_id': test_id,
            'now': datetime.now(),
        }
        
        # Get categories record and build context similar to Test_results
        categories_record = TestTopCategories.objects.filter(
            user=request.user,
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
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error parsing high_categories JSON: {e}")
                    high_categories = {}
            else:
                high_categories = categories_record.high_category
                high_categories = high_categories.strip("[]").strip()
            
            low_category = categories_record.low_category
        
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
            })
        elif latest_session.test.title == 'Career Interest Inventory' and high_categories:
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            context.update({
                'riasec_careers_to_opt': list(hexaco_recommendations.get('riasec_careers_to_opt', {}).values())[0] if hexaco_recommendations.get('riasec_careers_to_opt') else [],
                'career_code_discription': hexaco_recommendations.get('career_code_discription', ''),
            })
        elif latest_session.test.title == 'Motivation Assessment' and high_categories:
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            context.update({
                'motivation_careers_to_opt': list(hexaco_recommendations.get('motivation_careers_to_opt', {}).values())[0] if hexaco_recommendations.get('motivation_careers_to_opt') else [],
            })
        elif latest_session.test.title == 'Aptitude Assessment' and high_categories:
            hexaco_recommendations = get_hexaco_career_recommendations(high_categories, low_category, latest_session)
            context.update({
                'aptitude_improvement_plan': hexaco_recommendations.get('aptitude_improvement_plan', []),
                'aptitude_strength_narrative': hexaco_recommendations.get('aptitude_strength_narrative', []),
                'aptitude_Recommended_College_Courses': hexaco_recommendations.get('aptitude_Recommended_College_Courses', []),
                'aptitude_roles_guidance': hexaco_recommendations.get('aptitude_roles_guidance', []),
                'above_list': high_categories.get("Above Average", []) if isinstance(high_categories, dict) else [],
                'average_list': high_categories.get("Average", []) if isinstance(high_categories, dict) else [],
                'below_list': high_categories.get("Below Average", []) if isinstance(high_categories, dict) else [],
            })
        
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
    
    # Implementation for viewing test sections
    return render(request, 'template20/app_post_matric/test_sections.html', {
        'test': test_id,
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
def section_results(request,testId,result_id):
    # Add this new view for handling results
    
    return render(request, 'section_results.html', {
        'testId': testId,
        'result_id': result_id,
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
        
        # Get top 3 and lowest 1
        top_3_categories = [dim[0] for dim in sorted_dimensions[:3]]
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
            section_name = section_session.section.title
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
        return TestResult.objects.filter(session__user=self.request.user)

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