import time
from django.shortcuts import redirect, render
from core.breadcrumbs import get_breadcrumb
from core.utils import ensure_user_pdf_folder
from core.utils import ensure_user_pdf_folder
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from .forms import UploadFileForm
from .models import Question
from django.http import HttpResponse
from django.template.loader import get_template
import json
from django.contrib import messages

import os
import matplotlib.pyplot as plt
import shutil

import weasyprint
from django.conf import settings
import csv
from django.contrib.staticfiles import finders
import re
import logging
from django.shortcuts import get_object_or_404
# from django.contrib.auth.models import User
from .models import TestCompletion,Answer,Results

logger = logging.getLogger(__name__)

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.models import Category, Course, Stream

from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.core.cache import cache
final_score = None

from .forms import UserRegisterForm
from users.models import UserProfile
from django.middleware.csrf import get_token
from django.core.exceptions import ObjectDoesNotExist

from django.contrib.auth import get_user_model
from institute.decorators import (
    institute_user_only,
    institute_authenticated_user_only,
    institute_block_student_only,
    institute_update_delete_student_only,
    institute_change_student_password_only,
    institute_profile_update_delete,
    only_superuser,
    institute_group_user_only
)
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator


User = get_user_model()

# Define a custom exception for handling the case where the user hasn't attempted the test
class UserHasNotAttemptedTestException(Exception):
    pass


@csrf_exempt
@require_http_methods(['POST'])
def speed_test(request):
    """Dummy endpoint for instruction-page internet speed meter upload test. Returns 200."""
    return HttpResponse(status=200)


def custom_logout(request):
    print('Logging out {}'.format(request.user))  # Logging the user who is logging out
    logout(request)
    return redirect('/')

def career_tree1(request):
    return render(request, 'sub.html')

def career_tree(request):
    return render(request, 'topteenfrontend/user/app/career_tree.html')

def quick_link(request):
    return render(request, 'topteenfrontend/user/app/quick_link.html')

def db_results(request):

    user = request.user
    if not has_attempted_test(user):
        raise UserHasNotAttemptedTestException("User hasn't attempted the test yet.")
    
    top_3_categories = ""
    top_categories = []
    questions= Question.objects.all()
    # Get the data from the database fro the Personality test
    try:
        if questions is not None:
            test1_result = Results.objects.get(user = request.user, test_paper='test1')
            sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
            
            for i, (category, score) in enumerate(sorted_results, start=1):
                if i > 3:
                    break
                top_categories.append({
                    'rank': i,
                    'category': category,
                    'score': f"{score:.2f}%"
                })
                top_3_categories += category[0]

            top_3_categories_str = "".join(top_3_categories)

        top_3 = top_3_categories_str.split(',')
        top_category_code = top_3[0]
    except:
        top_categories = ''
        top_category_code = ''


    # Get the data from the database for the Career interest test
    try:
        test2_result = Results.objects.get(user=request.user, test_paper='test2')
        lengths = test2_result.scores
        max_length = max(lengths, key=lengths.get)
        min_length = min(lengths, key=lengths.get)
    except Results.DoesNotExist:
        max_length = ''
        min_length = ''

    # Get the data from the database for the Intelligence test
    try:
        test3_result = Results.objects.get(user=request.user, test_paper='test3')
        personality_res = test3_result.scores
        scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
        below = []
        avg = []
        above_avg = []
        for key in scores:
            if scores[key] <= 5:
                below.append(key)
            elif scores[key] <= 10:
                avg.append(key)
            else:
                above_avg.append(key)
    except Results.DoesNotExist:
        below = ''
        avg = ''
        above_avg = ''

    # Get the top category using the code
    top_category = Category.objects.filter(category=top_category_code).first()
    streamsubject = set()
    courseName = set()
    if top_category:
        category_id = top_category.id
        # Get streams related to this category using the category ID
        streams = Stream.objects.filter(category_id=category_id)
        # Print the details of each stream
        for stream in streams:
            streamsubject.add((stream.stream_name, stream.subjects))

        # Get courses related to this category using the category ID
        courses = Course.objects.filter(category_id=category_id)
        for course in courses:
            # Print the details of each courses
            courseName.add(course.course_name)

    else:
        print("No category found with the code:", top_category_code)

    return top_category, streamsubject,courseName, max_length, min_length, below, avg, above_avg, top_categories
# Example implementation of has_attempted_test function

def has_attempted_test(user):
    return TestCompletion.objects.filter(user=user).exists()

from django.shortcuts import render, redirect, get_object_or_404

@login_required(login_url=reverse_lazy('users:login'))
def dashboard(request, student_id=None):
    
    try:
        top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results(request)
        
        
        test1_result = Results.objects.get(user=request.user, test_paper='test1')
        sorted_result = test1_result.results

        # Find the highest value and its corresponding category
        personality_results = max(sorted_result, key=sorted_result.get, default=None)
        personality_highest_value = sorted_result.get(personality_results, 0)
        
        '''Interest: Find the highest value and its corresponding category'''
        test2_result = Results.objects.get(user=request.user, test_paper='test2')
        sorted_test2_result = test2_result.scores
        interest_results = max(sorted_test2_result, key=sorted_test2_result.get)
        interest_highest_value = sorted_test2_result[interest_results]

        '''Intelligence: Find the highest value and its corresponding category'''
        test3_result = Results.objects.get(user=request.user, test_paper='test3')
        sorted_test3_result = test3_result.scores
        intelligence_results = max(sorted_test3_result, key=sorted_test3_result.get)
        avg_intelligence = intelligence_results.split('_')[0]  # This will split the string into a list
        above_avg_score = avg_intelligence.upper()
        intelligence_highest_value = sorted_test3_result[intelligence_results]


        # User profile data
        user = request.user
        user_profile = None
        try:
            user_profile, created = UserProfile.objects.get_or_create(user=user)
        except UserProfile.DoesNotExist:
            pass

        # Handle 'intelligence' based on above_avg
        if above_avg_score in above_avg:
            intelligence_entry = {}
            if 'NUMERICAL' in above_avg_score:
                intelligence_entry = {'streams': ['PCM', 'CWM']}
            elif 'VERBAL' in above_avg_score:
                intelligence_entry = {'streams': ['HUM', 'CWM']}
            elif 'LOGICAL' in above_avg_score:
                intelligence_entry = {'streams': ['PCM', 'PCB']}
            elif 'MECHANICAL' in above_avg_score:
                intelligence_entry = {'streams': ['PCM', 'CS']}
            elif 'SPATIAL' in above_avg_score:
                intelligence_entry = {'streams': ['PCM', 'Fine Arts']}
            elif 'LANGUAGE' in above_avg_score:
                intelligence_entry = {'streams': ['HUM', 'HWL']}
            elif 'CRITICAL' in above_avg_score:
                intelligence_entry = {'streams': ['PCM', 'HUM']}

            test3_result.results['intelligence'] = intelligence_entry

        # Initialize or ensure personality is a list
        if not isinstance(test3_result.results.get('personality'), list):
            test3_result.results['personality'] = []

        # Iterate through streamsubject and add stream/subject pairs to 'personality'
        for stream, subject in streamsubject:
            personality_entry = {'stream': stream, 'subject': subject}
            if personality_entry not in test3_result.results['personality']:
                test3_result.results['personality'].append(personality_entry)

        # Save the updated test3_result to the database
        test3_result.save()

        context = {
            'user_profile': user_profile,
            'top_category': top_category,
            'streamsubject': streamsubject,
            'courseName': courseName,
            'max_length': max_length,
            'min_length': min_length,
            'below': below,
            'avg': avg,
            'above_avg': above_avg,
            'above_avg_score':above_avg_score,
            'highest_value': personality_highest_value,
            'interest_highest_value': interest_highest_value,
            'intelligence_highest_value': intelligence_highest_value,
        }

        return render(request, 'topteenfrontend/user/app/dashboard.html', context)

    except Exception as e:
        # Log the error for debugging purposes (optional)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in dashboard: {str(e)}")
        messages.error(request, "Please start your test. Then you can access the dashboard.")
        # Redirect to home without displaying any error on the frontend
        return redirect('/psychometric/home')

def final_assessment_pdf(request):

    top_category, streamsubject,courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results(request)
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None

    user_name = request.user
    user_ID = request.user.id
    # Prepare context dictionary
    context = {
        'user_name':user_name,
        'user_ID':user_ID,
        'user_profile': user_profile,
        'top_category':top_category,
        'streamsubject': streamsubject,
        'courseName':courseName,
        'max_length':max_length,
        'min_length':min_length,
        'below':below,
        'avg':avg,
        'above_avg':above_avg,
        'top_categories':top_categories,
    }
    return render(request, 'Asessment_report.html',context)


def db_results_inst_user(user):

    if not has_attempted_test(user):
        raise UserHasNotAttemptedTestException("User hasn't attempted the test yet.")
    top_3_categories_str = ""
    top_categories = []
    questions= Question.objects.all()
    # Get the data from the database fro the Personality test
    try:
        if questions is not None:
            test1_result = Results.objects.get(user = user, test_paper='test1')
            # Check if results dict exists and has data
            if test1_result.results and isinstance(test1_result.results, dict):
                sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
                for i, (category, score) in enumerate(sorted_results, start=1):
                    if i > 3:
                        break
                    top_categories.append({
                        'rank': i,
                        'category': category,
                        'score': f"{score:.2f}%"
                    })
                    # Get first letter of category name (e.g., "Realistic" -> "R")
                    top_3_categories_str += category[0] if category else ''

        # Extract category code (first 3 letters)
        top_category_code = top_3_categories_str[:3] if top_3_categories_str else ''
    except Results.DoesNotExist:
        top_categories = []
        top_category_code = ''
    except Exception as e:
        print(f"Error processing test1 results for user {user.id}: {str(e)}")
        top_categories = []
        top_category_code = ''


    # Get the data from the database for the Career interest test
    try:
        test2_result = Results.objects.get(user=user, test_paper='test2')
        lengths = test2_result.scores
        min_length = min(lengths, key=lengths.get)
        max_length = max(lengths, key=lengths.get)
    except Results.DoesNotExist:
        max_length = ''
        min_length = ''

    # Get the data from the database for the Intelligence test
    try:
        test3_result = Results.objects.get(user=user, test_paper='test3')
        personality_res = test3_result.scores
        scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
        below = []
        avg = []
        above_avg = []
        for key in scores:
            if scores[key] <= 5:
                below.append(key)
            elif scores[key] <= 10:
                avg.append(key)
            else:
                above_avg.append(key)
    except Results.DoesNotExist:
        below = ''
        avg = ''
        above_avg = ''

    # Get the top category using the code
    top_category = Category.objects.filter(category=top_category_code).first()
    streamsubject = set()
    courseName = set()
    if top_category:
        category_id = top_category.id
        # Get streams related to this category using the category ID
        streams = Stream.objects.filter(category_id=category_id)
        # Print the details of each stream
        for stream in streams:
            streamsubject.add((stream.stream_name, stream.subjects))

        # Get courses related to this category using the category ID
        courses = Course.objects.filter(category_id=category_id)
        for course in courses:
            # Print the details of each courses
            courseName.add(course.course_name)

    else:
        print("No category found with the code:", top_category_code)

    return top_category, streamsubject,courseName, max_length, min_length, below, avg, above_avg, top_categories


def Assessment_pdf_inst_user(request, user_id=None):

    """
    View to generate and display the final assessment report for the logged-in user.
    """
    
    # Fetch the user based on the provided user_id parameter or fallback to the current user
    user = get_object_or_404(User, id=user_id) if user_id else request.user

    # top_category, streamsubject,courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(user)
    
    # Call your function and check for issues
    try:
        top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(user)
    except UserHasNotAttemptedTestException as e:
        # User hasn't attempted test - return error page or redirect
        from django.http import HttpResponse
        return HttpResponse(f"User {user.name} hasn't attempted the test yet. Please complete the test first.", status=400)
    except Exception as e:
        # Log the error but don't crash - return with empty data
        import traceback
        print(f"Error in db_results_inst_user for user {user.id}: {str(e)}")
        print(traceback.format_exc())
        # Set default values to prevent template errors
        top_category = None
        streamsubject = set()
        courseName = set()
        max_length = ''
        min_length = ''
        below = []
        avg = []
        above_avg = []
        top_categories = []
    
    
    user_name = user
    user_ID = user.id if user_id is None else user_id
    # Ensure graph images exist for the report (personality, interest, intelligence)
    graph_dir = os.path.join(settings.BASE_DIR, 'media', 'graph_images')
    if not os.path.isdir(graph_dir):
        try:
            os.makedirs(graph_dir, exist_ok=True)
        except OSError:
            pass
    graph_basename = f"{user_name}-{user_ID}"
    graph_files = [
        f"{graph_basename}_personality_Assessment.png",
        f"{graph_basename}_interest_Assessment.png",
        f"{graph_basename}_intelligence_Assessment.png",
    ]
    need_graphs = any(not os.path.exists(os.path.join(graph_dir, f)) for f in graph_files)
    if need_graphs:
        original_user = request.user
        try:
            request.user = user
            gernate_graph(request)
        except Exception as e:
            import traceback
            print(f"Assessment_pdf_inst_user: could not generate graphs for user {user.id}: {e}")
            print(traceback.format_exc())
        finally:
            request.user = original_user
    # Prepare context dictionary
    context = {
        'user_name': user_name,
        'user_ID': user_ID,
        'top_category': top_category,
        'streamsubject': streamsubject,
        'courseName': courseName,
        'max_length': max_length,
        'min_length': min_length,
        'below': below,
        'avg': avg,
        'above_avg': above_avg,
        'top_categories': top_categories,
    }
    return render(request, 'Asessment_report.html', context)


def _add_no_cache_headers(response):
    """Set headers so the report is not cached (fixes view result in normal browser mode)."""
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@login_required(login_url=reverse_lazy('users:login'))
def class10_combined_report(request, user_id=None):
    """
    View to generate and display the combined assessment report for Class 10 students.
    Similar to Class 12's CombinedReport but adapted for Class 10 structure.
    """
    try:
        # Get the target user (student) whose report we want to view
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists (for later download)
        ensure_user_pdf_folder(target_user.id)
        
        # Check if user has attempted tests
        if not has_attempted_test(target_user):
            resp = render(request, 'template20/app/class10_combined_report.html', {
                'error': 'No completed test found. Please complete all tests first.',
                'no_results': True,
                'user': target_user,
                'breadcrumb': get_breadcrumb([
                    {'text': 'Dashboard', 'url': reverse('app:dashboard')},
                    {'text': 'Combined Report', 'url': ''},
                ]),
            })
            return _add_no_cache_headers(resp)
        
        # Get test completion status
        try:
            test_completion = TestCompletion.objects.get(user=target_user)
        except TestCompletion.DoesNotExist:
            test_completion = None
        
        # Check if all 3 tests are completed
        test1_completed = Results.objects.filter(user=target_user, test_paper='test1').exists()
        test2_completed = Results.objects.filter(user=target_user, test_paper='test2').exists()
        test3_completed = Results.objects.filter(user=target_user, test_paper='test3').exists()
        
        all_tests_completed = test1_completed and test2_completed and test3_completed
        
        if not all_tests_completed:
            resp = render(request, 'template20/app/class10_combined_report_new.html', {
                'error': 'Please complete all three tests (Personality, Interest, and Intelligence) to view your combined report.',
                'no_results': True,
                'user': target_user,
                'test1_completed': test1_completed,
                'test2_completed': test2_completed,
                'test3_completed': test3_completed
            })
            return _add_no_cache_headers(resp)
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get test results using db_results_inst_user function
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except UserHasNotAttemptedTestException:
            resp = render(request, 'template20/app/class10_combined_report_new.html', {
                'error': 'User hasn\'t attempted the test yet. Please complete the test first.',
                'no_results': True,
                'user': target_user
            })
            return _add_no_cache_headers(resp)
        except Exception as e:
            import traceback
            print(f"Error in db_results_inst_user for user {target_user.id}: {str(e)}")
            print(traceback.format_exc())
            top_category = None
            streamsubject = set()
            courseName = set()
            max_length = ''
            min_length = ''
            below = []
            avg = []
            above_avg = []
            top_categories = []
        
        # Get individual test results
        test1_result = None
        test2_result = None
        test3_result = None
        
        try:
            test1_result = Results.objects.get(user=target_user, test_paper='test1')
        except Results.DoesNotExist:
            pass
        
        try:
            test2_result = Results.objects.get(user=target_user, test_paper='test2')
        except Results.DoesNotExist:
            pass
        
        try:
            test3_result = Results.objects.get(user=target_user, test_paper='test3')
        except Results.DoesNotExist:
            pass
        
        # Process personality test data (test1)
        personality_data = {}
        if test1_result and test1_result.results:
            sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
            personality_data = {
                'results': dict(sorted_results),
                'top_categories': top_categories,
                'top_category': top_category
            }
        
        # Process interest test data (test2)
        interest_data = {}
        if test2_result and test2_result.scores:
            interest_data = {
                'scores': test2_result.scores,
                'max_category': max_length,
                'min_category': min_length
            }
        
        # Process intelligence test data (test3)
        intelligence_data = {}
        if test3_result and test3_result.scores:
            scores = {label.split("_")[0].upper(): value for label, value in test3_result.scores.items()}
            intelligence_data = {
                'scores': scores,
                'below_avg': below,
                'average': avg,
                'above_avg': above_avg
            }
        
        # Build context
        context = {
            'user': target_user,
            'user_profile': user_profile,
            'all_tests_completed': all_tests_completed,
            'test1_completed': test1_completed,
            'test2_completed': test2_completed,
            'test3_completed': test3_completed,
            
            # Test results
            'test1_result': test1_result,
            'test2_result': test2_result,
            'test3_result': test3_result,
            
            # Processed data
            'personality_data': personality_data,
            'interest_data': interest_data,
            'intelligence_data': intelligence_data,
            
            # Recommendations
            'top_category': top_category,
            'streamsubject': streamsubject,
            'courseName': courseName,
            'top_categories': top_categories,
            
            # Additional data
            'max_length': max_length,
            'min_length': min_length,
            'below': below,
            'avg': avg,
            'above_avg': above_avg,
            
            'no_results': False,
            'viewing_as_admin': user_id is not None and user_id != request.user.id,
            'user_id': user_id if user_id else target_user.id
        }
        
        resp = render(request, 'template20/app/class10_combined_report_new.html', context)
        return _add_no_cache_headers(resp)
        
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.exception("Error in class10_combined_report: %s", e)
        resp = render(request, 'template20/app/class10_combined_report_new.html', {
            'error': f'An error occurred: {str(e)}',
            'traceback': trace,
            'no_results': True
        })
        return _add_no_cache_headers(resp)


@login_required(login_url=reverse_lazy('users:login'))
def class10_report_download_pdf(request, user_id=None):
    """
    Generate and download PDF for Class 10 combined report.
    """
    target_user = None
    try:
        import weasyprint
        import ssl
        from datetime import datetime
        
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists
        ensure_user_pdf_folder(target_user.id)
        
        # Check if user has attempted tests
        if not has_attempted_test(target_user):
            return HttpResponse('No completed test found. Please complete all tests first.', status=404)
        
        # Check if all tests are completed
        test1_completed = Results.objects.filter(user=target_user, test_paper='test1').exists()
        test2_completed = Results.objects.filter(user=target_user, test_paper='test2').exists()
        test3_completed = Results.objects.filter(user=target_user, test_paper='test3').exists()
        
        if not (test1_completed and test2_completed and test3_completed):
            return HttpResponse('Please complete all three tests to download the report.', status=400)
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get test results
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            print(f"Error getting results: {e}")
            print(traceback.format_exc())
            return HttpResponse('Error generating report data.', status=500)
        
        # Get individual test results
        test1_result = Results.objects.filter(user=target_user, test_paper='test1').first()
        test2_result = Results.objects.filter(user=target_user, test_paper='test2').first()
        test3_result = Results.objects.filter(user=target_user, test_paper='test3').first()
        
        # Process personality data
        personality_data = {}
        if test1_result and test1_result.results:
            sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
            personality_data = {
                'results': dict(sorted_results),
                'top_categories': top_categories,
                'top_category': top_category
            }
        
        # Process interest data
        interest_data = {}
        if test2_result and test2_result.scores:
            interest_data = {
                'scores': test2_result.scores,
                'max_category': max_length,
                'min_category': min_length
            }
        
        # Process intelligence data
        intelligence_data = {}
        if test3_result and test3_result.scores:
            scores = {label.split("_")[0].upper(): value for label, value in test3_result.scores.items()}
            intelligence_data = {
                'scores': scores,
                'below_avg': below,
                'average': avg,
                'above_avg': above_avg
            }
        
        # Build context for PDF
        context = {
            'user': target_user,
            'user_profile': user_profile,
            'personality_data': personality_data,
            'interest_data': interest_data,
            'intelligence_data': intelligence_data,
            'top_category': top_category,
            'streamsubject': streamsubject,
            'courseName': courseName,
            'top_categories': top_categories,
            'max_length': max_length,
            'min_length': min_length,
            'below': below,
            'avg': avg,
            'above_avg': above_avg,
            'now': datetime.now(),
        }
        
        # Render HTML template
        template = get_template('template20/app/class10_combined_report_pdf.html')
        html = template.render(context)
        
        # Configure SSL to disable verification for WeasyPrint
        original_ssl_context = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context
        
        try:
            # Generate PDF
            pdf_file = weasyprint.HTML(
                string=html,
                base_url=request.build_absolute_uri('/')
            ).write_pdf()
        finally:
            # Restore original SSL context
            ssl._create_default_https_context = original_ssl_context
        
        # Create response
        response = HttpResponse(content_type='application/pdf')
        user_name = getattr(target_user, 'name', None) or getattr(target_user, 'email', 'user')
        safe_name = re.sub(r'[^\w\s-]', '', str(user_name)).strip()[:50] or 'user'
        filename = f"{safe_name}-Stream_Sorter_Combined_Report.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response['Pragma'] = 'no-cache'
        response.write(pdf_file)
        
        # Save copy to user PDF folder (for production debugging and consistency)
        user_directory = ensure_user_pdf_folder(target_user.id)
        if user_directory:
            try:
                pdf_path = os.path.join(user_directory, filename)
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_file)
            except OSError as e:
                logger.warning("class10_report_download_pdf: could not save PDF to user folder user_id=%s: %s", target_user.id, e)
        
        return response
        
    except Exception as e:
        uid = getattr(target_user, 'id', None) if target_user else getattr(request.user, 'id', None)
        logger.exception("class10_report_download_pdf failed for user_id=%s: %s", uid, e)
        return HttpResponse(f'Error generating PDF: {str(e)}', status=500)


def upload_file(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            # Process uploaded file
            handle_uploaded_file(request.FILES['file'])
            return HttpResponseRedirect('/psychometric/home')
    else:
        form = UploadFileForm()
    return render(request, 'topteenfrontend/user/app/upload.html', {'form': form})

@login_required(login_url=reverse_lazy('users:login'))
def test_buttons(request):
    # Import redirect and reverse at the top
    from django.shortcuts import redirect
    from django.urls import reverse
    from psychometric_tests.models import PsychometricTestPayment
    from core import choices
    
    # Initialize variables with default values
    user_profile = None
    created_date = None
    gender = None
    schoolname = None
    grade = None
    student_class = None  # Will be "10" or "12"

    if request.user.is_authenticated:
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
            created_date = user.created
            gender = user_profile.gender if user_profile else None
            schoolname = user_profile.schoolname if user_profile else None
            student_name = user.email  # Assuming email is used as student name
            
            # Determine student class: First check StudentManagement (for institute students)
            # Then fallback to UserProfile.grade (for direct signups)
            from institute.models import StudentManagement
            student_management = StudentManagement.objects.filter(student=user).first()
            
            if student_management and student_management.class_and_section:
                # Get class from StudentManagement (institute students)
                class_name = student_management.class_and_section.class_and_section
                if class_name:
                    # Extract first 2 characters to get class number
                    import re
                    numbers = re.findall(r'\d+', class_name)
                    if numbers:
                        class_number = int(numbers[0])
                        if class_number >= 11:
                            student_class = "12"  # Class 11-12
                        else:
                            student_class = "10"  # Class 10 and below
                    grade = class_name  # Use full class name for display
            elif user_profile and user_profile.grade:
                # Fallback to UserProfile.grade (direct signups)
                student_class = str(user_profile.grade)
                grade = f"Class {user_profile.grade}"
            else:
                # Default to class 10 if nothing is set
                student_class = "10"
                grade = "Class 10"

        except (UserProfile.DoesNotExist, AttributeError):
            print("UserProfile does not exist.")
            user_profile = None
            student_class = "10"  # Default
            grade = "Class 10"

    else:
        print("User is not authenticated.")
        # Redirect to login if not authenticated
        return redirect(reverse('users:login'))
    
    # Check if user is an institute-registered student (exempt from payment check)
    is_institute_student = StudentManagement.objects.filter(student=request.user).exists()

    # UPDATED: After completing all psychometric tests, institute students must add/verify mobile to continue.
    # Allow login, but block this dashboard/action until mobile is present.
    try:
        if is_institute_student and (not request.user.mobile or not str(request.user.mobile).strip()):
            tc = TestCompletion.objects.filter(user=request.user).first()
            is_completed = bool(
                tc and
                tc.test1_complete and
                tc.test2_complete and
                tc.test3_complete and
                tc.numerical_complete and
                tc.verbal_complete and
                tc.logical_complete and
                tc.emotional_complete and
                tc.machanical_complete and
                tc.language_complete and
                tc.spatial_complete
            )
            if is_completed:
                request.session['force_mobile_popup'] = True
                request.session['post_mobile_redirect'] = reverse('app:test_buttons')
                return redirect(reverse('users:userdashboard'))
    except Exception:
        pass
    
    # Only check payment for non-institute students
    if not is_institute_student:
        # Check if user has purchased test for their class - protect test dashboard access
        has_payment = False
        if student_class == "10":
            # Class 10 should have BASIC test (Stream Sorter)
            has_payment = PsychometricTestPayment.objects.filter(
                user=request.user,
                test_type=choices.PsychometricTestType.BASIC,
                is_success=choices.YesNoChoices.YES
            ).exists()
            if not has_payment:
                # Redirect to Stream Sorter buy page
                return redirect(reverse('psychometrictests:psychometrictest'))
        elif student_class == "12":
            # Class 12 should have ADVANCED test (Career Direction)
            has_payment = PsychometricTestPayment.objects.filter(
                user=request.user,
                test_type=choices.PsychometricTestType.ADVANCED,
                is_success=choices.YesNoChoices.YES
            ).exists()
            if not has_payment:
                # Redirect to Career Direction buy page
                return redirect(reverse('psychometrictests:PsychometricTest12'))
        else:
            # Default to class 10 if class not determined
            has_payment = PsychometricTestPayment.objects.filter(
                user=request.user,
                test_type=choices.PsychometricTestType.BASIC,
                is_success=choices.YesNoChoices.YES
            ).exists()
            if not has_payment:
                # Redirect to Stream Sorter buy page
                return redirect(reverse('psychometrictests:psychometrictest'))

    try:
        test_completion = TestCompletion.objects.get(user=request.user)
    except TestCompletion.DoesNotExist:
        # Create a new TestCompletion object if it doesn't exist
        test_completion = TestCompletion.objects.create(user=request.user)
        pass

    # Check if tests have been started but not completed
    test_started_status = {
        'test1_started': Results.objects.filter(user=request.user, test_paper='test1').exists(),
        'test2_started': Results.objects.filter(user=request.user, test_paper='test2').exists(),
        'test3_started': Results.objects.filter(user=request.user, test_paper='test3').exists(),
    }

    # Check if all test3 subtests are complete (same logic as app_submit)
    all_test3_subtests_complete = False
    if test_completion:
        # Check if all subtests are complete using TestCompletion fields
        all_test3_subtests_complete = (
            test_completion.numerical_complete and
            test_completion.verbal_complete and
            test_completion.logical_complete and
            test_completion.emotional_complete and
            test_completion.machanical_complete and
            test_completion.language_complete and
            test_completion.spatial_complete
        )
        
        # Verify and correct test3_complete status if needed
        if test_completion.test3_complete and not all_test3_subtests_complete:
            test_completion.test3_complete = False
            test_completion.save()
        elif not test_completion.test3_complete and all_test3_subtests_complete:
            test_completion.test3_complete = True
            test_completion.save()
    
    context = {
        'user_profile': user_profile,
        'test_completion': test_completion,
        'test_started_status': test_started_status,
        "School_Name:": schoolname,
        'created_date': created_date,
        "Gender:": gender,
        "Grade:": grade,
        'student_class': student_class,  # "10" or "12" for filtering tests
        'all_test3_subtests_complete': all_test3_subtests_complete,
    }
    return render(request, 'template20/psychometric/home.html', context)

def handle_uploaded_file(file):
    decoded_file = file.read().decode('utf-8').splitlines()
    reader = csv.reader(decoded_file)
    next(reader) # Skip the header row

    for row in reader:
        question_text = row[0].strip()
        category = row[1].strip()
        test_paper = row[2].strip() # Assuming the third column is test_paper

        question_obj, created = Question.objects.get_or_create(
            question_text=question_text,
            category=category,
            test_paper=test_paper,
   
        )

@login_required(login_url=reverse_lazy('users:login'))
def test1_intro(request):
    # Ensure user PDF folder exists before starting test
    ensure_user_pdf_folder(request.user.id)
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    context = {
        'user_profile': user_profile,
    }
    return render(request, 'template20/psychometric/test1_intro.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test2_intro(request):
    # Ensure user PDF folder exists before starting test
    ensure_user_pdf_folder(request.user.id)
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    context = {
        'user_profile': user_profile,
    }
    return render(request, 'template20/psychometric/test2_intro.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_intro(request):
    # Ensure user PDF folder exists before starting test
    ensure_user_pdf_folder(request.user.id)
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    context = {
        'user_profile': user_profile,
    }
    return render(request, 'template20/psychometric/test3_intro.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test1_view(request):
    questions = Question.objects.filter(test_paper='test1')
    csrf_token = get_token(request)
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    context = {
        'user_profile': user_profile,
        'questions': questions,
        'test_paper': 'test1',
        'csrf_token':csrf_token,
    }
    test_completion, created = TestCompletion.objects.get_or_create(user=request.user)
    return render(request, 'template20/psychometric/test1_view.html',context)

@login_required(login_url=reverse_lazy('users:login'))
def test2_view(request):
    questions = list(Question.objects.filter(test_paper='test2'))
    csrf_token = get_token(request)
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
    except TestCompletion.DoesNotExist:
        test_completion = TestCompletion.objects.create(user=request.user)
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    context = {
        'user_profile': user_profile,
        'questions': questions,
        'test_paper': 'test2',
        'csrf_token':csrf_token,
    }
    # return render(request, 'topteenfrontend/user/app/interest-assessment-test2.html', context)
    return render(request, 'template20/psychometric/test2_view.html', context)


@login_required(login_url=reverse_lazy('users:login'))
def test3_view(request):
    context = {}
    if request.method == 'POST':
        test_paper = request.POST.get('test_paper')
        questions = Question.objects.filter(test_paper=test_paper)       

        if not questions.exists():
            return render(request, 'topteenfrontend/404page.html', status=404)
        
        from collections import defaultdict
        score = 0
        selected_options = {}
        submitted_answer = []
        selected_answers_by_category = defaultdict(list)
        processed_questions = defaultdict(set)

        if test_paper == 'test3':
            # Get existing scores to preserve other sections
            try:
                test3_result = Results.objects.get(user=request.user, test_paper='test3')
                existing_scores = test3_result.scores or {}
                existing_selected_answers = test3_result.selected_answers or {}
            except Results.DoesNotExist:
                existing_scores = {}
                existing_selected_answers = {}

            # Initialize scores with existing values (preserve other sections)
            logical_score = existing_scores.get('logical_score', 0)
            verbal_score = existing_scores.get('verbal_score', 0)
            numerical_score = existing_scores.get('numerical_score', 0)
            emotional_score = existing_scores.get('critical_score', 0)
            language_score = existing_scores.get('language_score', 0)
            spatial_score = existing_scores.get('spatial_score', 0)
            mechanical_score = existing_scores.get('mechanical_score', 0)

            # Track which categories are being attempted in this submission
            attempted_categories = set()

            for question in questions:
                answer = request.POST.get(f'question_{question.id}', None)
                if answer:
                    attempted_categories.add(question.category)
                    selected_answer = get_object_or_404(Answer, pk=answer)
                    correct_answer = question.answer_set.filter(is_correct=True).first()

                    # Build the full image URL
                    image_url = None
                    if question.question_image:
                        image_url = request.build_absolute_uri(question.question_image.url)
                    
                    selected_answer_dict = {
                        "question_image_url": image_url if image_url else '-',
                        "question_text": question.question_text if question.question_text else "-",
                        "selected_answer": selected_answer.answer_text,
                        "correct_answer": correct_answer.answer_text if correct_answer else "-",
                        "category": question.category,
                    }
                    
                    # Add to the current category
                    if question.id not in processed_questions[question.category]:
                        selected_answers_by_category[question.category].append(selected_answer_dict)
                        processed_questions[question.category].add(question.id)

                    if selected_answer.is_correct:
                        score += 1

            # Reset scores only for attempted categories, then recalculate
            for category in attempted_categories:
                if category == 'Logical':
                    logical_score = 0
                elif category == 'Verbal':
                    verbal_score = 0
                elif category == 'Numerical':
                    numerical_score = 0
                elif category == 'Emotional':
                    emotional_score = 0
                elif category == 'Language':
                    language_score = 0
                elif category == 'Spatial':
                    spatial_score = 0
                elif category == 'Mechanical':
                    mechanical_score = 0

            # Now calculate fresh scores for attempted categories only
            for question in questions:
                answer = request.POST.get(f'question_{question.id}', None)
                if answer:
                    selected_answer = get_object_or_404(Answer, pk=answer)
                    if selected_answer.is_correct:
                        if question.category == 'Logical':
                            logical_score += 1
                        elif question.category == 'Verbal':
                            verbal_score += 1
                        elif question.category == 'Numerical':
                            numerical_score += 1
                        elif question.category == 'Emotional':
                            emotional_score += 1
                        elif question.category == 'Language':
                            language_score += 1
                        elif question.category == 'Spatial':
                            spatial_score += 1
                        elif question.category == 'Mechanical':
                            mechanical_score += 1

            # Merge existing selected_answers with new data
            for category, answers in selected_answers_by_category.items():
                # Replace the category data completely if it's being attempted
                existing_selected_answers[category] = answers

            # Update or create the result with preserved + updated scores
            test3_result, created = Results.objects.update_or_create(
                user=request.user,
                test_paper='test3',
                defaults={
                    'scores': {
                        'logical_score': logical_score,
                        'verbal_score': verbal_score,
                        'numerical_score': numerical_score,
                        'critical_score': emotional_score,
                        'language_score': language_score,
                        'spatial_score': spatial_score,
                        'mechanical_score': mechanical_score,
                    }, 
                    'results': {}, 
                    'selected_answers': existing_selected_answers
                }
            )
    
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
            
    test_completion, created = TestCompletion.objects.get_or_create(user=request.user)
    
    # Check if all subtests are completed before marking test3 as complete
    all_subtests_complete = (
        test_completion.numerical_complete and
        test_completion.verbal_complete and
        test_completion.logical_complete and
        test_completion.emotional_complete and
        test_completion.machanical_complete and
        test_completion.language_complete and
        test_completion.spatial_complete
    )
    
    # Only mark test3 as complete if all subtests are completed
    if all_subtests_complete:
        test_completion.test3_complete = True
        test_completion.save()

    context = {
        'user_profile': user_profile,
        # 'questions': questions,
        'test_paper': 'test3',
        'test_completion': test_completion,
        'all_subtests_complete': all_subtests_complete
    }
    
    return render(request, 'template20/psychometric/test3_view.html', context)


@login_required(login_url=reverse_lazy('users:login'))
def test3_numerical(request):
    questions = list(Question.objects.filter(test_paper='test3', category='Numerical'))
    user = 'unique_identifier_for_test11'  # This should be dynamically determined
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.numerical_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        # Handle case where the TestCompletion object does not exist
        test_completion = None
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Numerical',
        'user_profile': user_profile
    }
    
    return render(request, 'template20/psychometric/test3_numerical.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_logical(request):
    questions = list(Question.objects.filter(test_paper='test3', category ='Logical'))
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.logical_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        test_completion = None
    
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Logical',
        'user_profile': user_profile
    }
    
    return render(request, 'template20/psychometric/test3_logical.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_verbal(request):
    
    questions = list(Question.objects.filter(test_paper='test3', category ='Verbal'))
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.verbal_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        test_completion = None

    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Verbal',
        'user_profile': user_profile
    }
    
    return render(request, 'template20/psychometric/test3_verbal.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_emotional(request):
    questions = Question.objects.filter(test_paper='test3', category ='Emotional')
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.emotional_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        test_completion = None

    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Emotional',
        'user_profile': user_profile
    }
    
    return render(request, 'template20/psychometric/test3_emotional.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_language(request):
    questions = Question.objects.filter(test_paper='test3', category ='Language')
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.language_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        test_completion = None
    
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Language',
        'user_profile': user_profile
    }

    return render(request, 'template20/psychometric/test3_language.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_machanical(request):
    questions = Question.objects.filter(test_paper='test3', category ='Mechanical')
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.machanical_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        test_completion = None

    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Mechanical',
        'user_profile': user_profile
    }
    
    return render(request, 'template20/psychometric/test3_machanical.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_spatial(request):
    questions = Question.objects.filter(test_paper='test3', category ='Spatial')
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
        test_completion.spatial_complete = True
        test_completion.save()
    except TestCompletion.DoesNotExist:
        test_completion = None

    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    
    context = {
        'questions': questions,
        'test_paper': 'test3',
        'category':'Spatial',
        'user_profile': user_profile
    }
    
    return render(request, 'template20/psychometric/test3_spatial.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def generate_pdf(request):

    try:
    
        if request.method == 'POST':
            test_paper = request.POST.get('test_paper')
            questions = Question.objects.filter(test_paper=test_paper)

            if not questions:
                return HttpResponse("No questions found for this test.", status=404)
            
            score = 0
            selected_options = {}
            submitted_answer = []
            if test_paper == 'test1':
                categories = {
                    'R': 'Realistic',
                    'I': 'Investigative',
                    'A': 'Artistic',
                    'S': 'Social',
                    'E': 'Enterprising',
                    'C': 'Conventional'
                }
                results = {
                    'Realistic': 0,
                    'Investigative': 0,
                    'Artistic': 0,
                    'Social': 0,
                    'Enterprising': 0,
                    'Conventional': 0
                }
            
                for idx, question in enumerate(questions):
                    answer = request.POST.get(f"question_{idx + 1}", None)
                    if answer is not None:
                        selected_options[question.id] = answer
                        submitted_answer.append(int(answer))
                        score += 1
                total_score = sum(submitted_answer) if submitted_answer else 0

                variable_indices = {
                'R': [1, 7, 13, 19, 25, 31, 37, 43, 49, 55],
                'I': [2, 8, 14, 20, 26, 32, 38, 44, 50, 56],
                'A': [3, 9, 15, 21, 27, 33, 39, 45, 51, 57],
                'S': [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
                'E': [5, 11, 17, 23, 29, 35, 41, 47, 53, 59],
                'C': [6, 12, 18, 24, 30, 36, 42, 48, 54, 60],
                }

                # Calculate sums
                sum_R = sum(submitted_answer[i-1] for i in variable_indices['R'])
                sum_I = sum(submitted_answer[i-1] for i in variable_indices['I'])
                sum_A = sum(submitted_answer[i-1] for i in variable_indices['A'])
                sum_S = sum(submitted_answer[i-1] for i in variable_indices['S'])
                sum_E = sum(submitted_answer[i-1] for i in variable_indices['E'])
                sum_C = sum(submitted_answer[i-1] for i in variable_indices['C'])

                
                # Calculate percentages
                results['Realistic'] = round((sum_R / 50) * 100, 2)
                results['Investigative'] = round((sum_I / 50) * 100, 2)
                results['Artistic'] = round((sum_A / 50) * 100, 2)
                results['Social'] = round((sum_S / 50) * 100, 2)
                results['Enterprising'] = round((sum_E / 50) * 100, 2)
                results['Conventional'] = round((sum_C / 50) * 100, 2)
                # user = User.objects.get(username=request.user.username)
                user = request.user
                test1_result, created = Results.objects.update_or_create(
                user=user,  # Use the ForeignKey field
                test_paper='test1',  # Lookup field
                defaults={
                    'scores': {
                        'sum_R': sum_R,
                        'sum_I': sum_I,
                        'sum_A': sum_A,
                        'sum_S': sum_S,
                        'sum_E': sum_E,
                        'sum_C': sum_C
                    },
                    'results': results
                    }
                )
                # Add submitted_answer to the results dictionary
                submitted_answers_dict = {
                    f'Question_{i + 1}': ans for i, ans in enumerate(submitted_answer)
                }
                # Add to the results dictionary
                test1_result.selected_answers['submitted_answers'] = submitted_answers_dict

                # Save updated results back to the database
                test1_result.save()        

            # return score, selected_options
            
        else:
            return JsonResponse({'message': 'Invalid request'}, status=400)
        
    except Exception as e:
       return HttpResponse("No pdf gerenated for the new changes", status=404)
        
 
def read_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            # for item in data:
            #     category_obj, created = Category.objects.update_or_create(
            #         category=item['category'],
            #         fullname=item['fullname'],
            #         summary=item['summary'],
            #         fields=item['fields'],
            #         best_colleges=item.get('best_colleges', '')
            #     )
                
            #     for course in item['courses']:
            #         Course.objects.create(category=category_obj, course_name=course)
                
            #     for stream, subjects in item['streams'].items():
            #         Stream.objects.create(category=category_obj, stream_name=stream, subjects=', '.join(subjects))
        
        if isinstance(data, list):
            dictionary_array = []
            for data_set in data:
                dictionary = dict(data_set)
                dictionary_array.append(dictionary)
            return dictionary_array
        else:
            messages.error("Error: The JSON data is not a list.")
    except FileNotFoundError:
        messages.error(f"Error: {file_path} file not found.")
    except json.JSONDecodeError:
        messages.error(f"Error: Invalid JSON format in {file_path}.")
    except Exception as e:
        messages.error(f"Error: {e}")

@csrf_exempt
@login_required(login_url=reverse_lazy('users:login'))
def submit_clicks(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            clicks = data.get('clicks', {})
            question1_clicks = clicks.get('question1', [])
            question2_clicks = clicks.get('question2', [])
            question3_clicks = clicks.get('question3', [])
            question4_clicks = clicks.get('question4', [])
            question5_clicks = clicks.get('question5', [])
            question6_clicks = clicks.get('question6', [])
            # Process the clicks data as needed
            
            question1_clicks = len(question1_clicks)            
            question2_clicks = len(question2_clicks)            
            question3_clicks = len(question3_clicks)            
            question4_clicks = len(question4_clicks)
            question5_clicks = len(question5_clicks)
            question6_clicks = len(question6_clicks)

            # save to the database
            user = request.user
            test2_result, created = Results.objects.update_or_create(
                    user = user,
                    test_paper='test2',
                    defaults={
                        'scores': {
                            'Realistic': question1_clicks,
                            'Investigative': question2_clicks,
                            'Artistic': question3_clicks,
                            'Social': question4_clicks,
                            'Enterprising': question5_clicks,
                            'Conventional': question6_clicks,
                        }
                    }
                )
            test2_result.save()
            test_completion= TestCompletion.objects.get(user=request.user)
            test_completion.test2_complete = True
            test_completion.save()          
            
            return JsonResponse({'message': 'Success'}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({'message': 'Invalid JSON data'}, status=400)
    return JsonResponse({'message': 'Invalid request'}, status=400)
    
@login_required(login_url=reverse_lazy('users:login'))
def app_submit(request):
    cache.clear()
    if request.method == 'POST':
        test_paper = request.POST.get('test_paper')
        test_completion = TestCompletion.objects.get(user=request.user)

        # Update test completion status based on the test_paper value
        if test_paper == 'test1':
            test_completion.test1_complete = True
            test_completion.save()
        elif test_paper == 'test2':            
            test_completion.test2_complete = True
            test_completion.save()         
        elif test_paper == 'test3':
            # Check if all subtests are completed before marking test3 as complete
            all_subtests_complete = (
                test_completion.numerical_complete and
                test_completion.verbal_complete and
                test_completion.logical_complete and
                test_completion.emotional_complete and
                test_completion.machanical_complete and
                test_completion.language_complete and
                test_completion.spatial_complete
            )
            
            if all_subtests_complete:
                test_completion.test3_complete = True
                test_completion.save()

    # Load analysis content from a JSON file
    # analysis_content = read_json_file('RIASEC.json')
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    test_completion = TestCompletion.objects.get(user=request.user)
    
    # Verify and correct test3_complete status - only True if ALL subtests are complete
    all_subtests_complete = (
        test_completion.numerical_complete and
        test_completion.verbal_complete and
        test_completion.logical_complete and
        test_completion.emotional_complete and
        test_completion.machanical_complete and
        test_completion.language_complete and
        test_completion.spatial_complete
    )
    
    # Correct test3_complete if it's incorrectly set
    if test_completion.test3_complete and not all_subtests_complete:
        test_completion.test3_complete = False
        test_completion.save()
        print(f"Corrected test3_complete for user {request.user.id}: was True but not all subtests complete")
    elif not test_completion.test3_complete and all_subtests_complete:
        test_completion.test3_complete = True
        test_completion.save()
    
    # Check if tests have been started but not completed
    test_started_status = {
        'test1_started': Results.objects.filter(user=request.user, test_paper='test1').exists(),
        'test2_started': Results.objects.filter(user=request.user, test_paper='test2').exists(),
        'test3_started': Results.objects.filter(user=request.user, test_paper='test3').exists(),
    }
    
    # Prepare context for rendering the template
    context = {
        # 'analysis_content': analysis_content,
        'test_completion': test_completion,
        'test_started_status': test_started_status,
        'user_profile': user_profile,
        'all_test3_subtests_complete': all_subtests_complete,  # Add this for template check
    }
    generate_pdf(request)
    return render(request, 'template20/psychometric/test_submit.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def gernate_graph(request):
    # Get the data for the personality test
    test1_result = Results.objects.get(user=request.user, test_paper='test1')
    sorted_result = test1_result.results

    # Get the data for the Career interest test
    try:
        test2_result = Results.objects.get(user=request.user, test_paper='test2')
        lengths = test2_result.scores
        max_length = max(lengths, key=lengths.get)
        min_length = min(lengths, key=lengths.get)
    except Results.DoesNotExist:
        max_length = ''
        min_length = ''

    # Get the data for the Intelligence test
    try:
        test3_result = Results.objects.get(user=request.user, test_paper='test3')
        personality_res = test3_result.scores
        scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
        below = []
        avg = []
        above_avg = []
        for key in scores:
            if scores[key] <= 5:
                below.append(key)
            elif scores[key] <= 10:
                avg.append(key)
            else:
                above_avg.append(key)
    except Results.DoesNotExist:
        below = ''
        avg = ''
        above_avg = ''

    # Define the graph images folder for the user
    from pathlib import Path

     # Define the graph images folder for the user
    BASE_DIR = settings.BASE_DIR
    user_name = request.user
    user_ID = request.user.id
    graph_images_folder = BASE_DIR / 'media' / 'graph_images'
    if not os.path.exists(graph_images_folder):
        os.makedirs(graph_images_folder)

    graph_images = []

    # Assuming sorted_result contains scores between 0 and 100.
    if sorted_result:
        # Define RIASEC order: Realistic, Investigative, Artistic, Social, Enterprising, Conventional
        riasec_order = ['Realistic', 'Investigative', 'Artistic', 'Social', 'Enterprising', 'Conventional']
        
        # Reorder labels and values according to RIASEC order
        labels = []
        values = []
        for category in riasec_order:
            if category in sorted_result:
                labels.append(category.upper())
                values.append(sorted_result[category])

        # Define figure and axis
        fig, ax = plt.subplots(figsize=(20, 10))
        
        # Colors for the bars (matching RIASEC order)
        colors = ['#53BAD8', '#D17DD6', '#67BA48', '#BBA63A', '#CC4230', '#5999D1']
        
        # Create bar plot
        bars = ax.bar(labels, values, color=colors)
        
        # Title and labels
        plt.title('PERSONALITY ASSESSMENT', fontsize=25, fontweight='bold')
        ax.set_xlabel('')
        ax.set_ylabel('Score (%)', fontsize=25, fontweight='bold')
        
        # Setting ticks and labels size
        ax.tick_params(axis='x', labelsize=20)
        ax.tick_params(axis='y', labelsize=20)
        
        # Set y-axis limits and scale to 0-100 with intervals of 10
        ax.set_ylim(0, 105)
        ax.set_yticks(range(0, 105, 10))
        
        # Highlighting the bar with a specific value like 74%
        highlight_value = 100
        for bar, value in zip(bars, values):
            if value == highlight_value:
                bar.set_edgecolor('red')
                bar.set_linewidth(3)
            
            # Annotate bars with their values
            ax.annotate(f'{value}%', xy=(bar.get_x() + bar.get_width() / 2, value), 
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points", 
                        ha='center', va='bottom', fontsize=15, fontweight='bold')
        
        # Save the image
        image_path = os.path.join(graph_images_folder, f"{user_name}-{user_ID}_personality_Assessment.png")
        graph_images.append(image_path)
        plt.savefig(image_path, bbox_inches='tight')  # Save image with tight layout
        plt.close()

    try:
        if lengths:
            # Define RIASEC order: Realistic, Investigative, Artistic, Social, Enterprising, Conventional
            riasec_order = ['Realistic', 'Investigative', 'Artistic', 'Social', 'Enterprising', 'Conventional']
            
            # Reorder labels and values according to RIASEC order
            labels = []
            values = []
            for category in riasec_order:
                if category in lengths:
                    labels.append(category.upper())
                    values.append(lengths[category])
            
            # Create the figure and axis
            fig, ax = plt.subplots(figsize=(24, 12))
            
            # Define colors for the bars (matching RIASEC order)
            colors = ['#53BAD8', '#D17DD6', '#67BA48', '#BBA63A', '#CC4230', '#5999D1']
            
            # Create bar plot
            bars = ax.bar(labels, values, color=colors)
            
            # Set title and labels
            ax.set_title('INTEREST ASSESSMENT', fontsize=25, fontweight='bold')
            ax.set_xlabel('')
            ax.set_ylabel('Score', fontsize=29, fontweight='bold')
            
            # Adjust tick parameters
            ax.tick_params(axis='x', labelsize=24)
            ax.tick_params(axis='y', labelsize=24)
            
            # Set y-axis limits and scale to 0-60 with intervals of 6
            ax.set_ylim(0, 39)
            ax.set_yticks(range(0, 39, 6))
            
            # Highlight the bar with a specific value, like 36
            highlight_value = 36
            for bar, value in zip(bars, values):
                # Highlighting the bar with the score of 36
                if value == highlight_value:
                    bar.set_edgecolor('red')
                    bar.set_linewidth(3)
                
                # Annotate bars with their values
                ax.annotate(f'{value}', xy=(bar.get_x() + bar.get_width() / 2, value), 
                            xytext=(0, 3),  # 3 points vertical offset
                            textcoords="offset points", 
                            ha='center', va='bottom', fontsize=15, fontweight='bold')
            
            # Save the image
            image_path = os.path.join(graph_images_folder, f"{user_name}-{user_ID}_interest_Assessment.png")
            graph_images.append(image_path)
            plt.savefig(image_path, bbox_inches='tight')  # Save image with tight layout
            plt.close()

    except Exception as e:
        print(f"Error creating interest assessment graph: {e}")

    try:
        personality = test3_result.scores

        if personality:
            original_labels = list(personality.keys())
            labels = [label.split("_")[0].upper() for label in original_labels]
            values = list(personality.values())
            
            # Create the figure and axis
            fig, ax = plt.subplots(figsize=(21, 10))
            
            # Define colors for the bars
            colors = ['#53BAD8', '#D17DD6', '#67BA48', '#BBA63A', '#CC4230']
            
            # Create bar plot
            bars = ax.bar(labels, values, color=colors)
            
            # Set title and labels
            ax.set_title('INTELLIGENCE ASSESSMENT', fontsize=29, fontweight='bold')
            ax.set_xlabel('')
            ax.set_ylabel('', fontsize=29, fontweight='bold')
            
            # Adjust tick parameters
            ax.tick_params(axis='x', labelsize=24)
            ax.tick_params(axis='y', labelsize=24)
            
            # Set y-axis limits and scale to 0-15 with increments of 3
            ax.set_ylim(0, 18)  # Set limit to 20 to create a gap above the highest tick
            ax.set_yticks(range(0, 19, 5))  # Tick marks at 0, 5, 10, 15

            # Add labels for score ranges outside the graph on the left side
            ax.text(-0.8, 2.5, 'Below Average\n(0-5)', fontsize=25, color='black', ha='right', va='center')
            ax.text(-0.8, 8, 'Average\n(6-10)', fontsize=25, color='black', ha='right', va='center')
            ax.text(-0.8, 13, 'Above Average\n(11-15)', fontsize=25, color='black', ha='right', va='center')

            # Highlight specific bars if needed
            highlight_value = 15  # Example value to highlight
            for bar, value in zip(bars, values):
                if value == highlight_value:
                    bar.set_edgecolor('red')
                    bar.set_linewidth(3)
                
                # Annotate bars with their values
                ax.annotate(f'{value}', xy=(bar.get_x() + bar.get_width() / 2, value), 
                            xytext=(0, 3),  # 3 points vertical offset
                            textcoords="offset points", 
                            ha='center', va='bottom', fontsize=15, fontweight='bold')
            
            # Save the image
            image_path = os.path.join(graph_images_folder, f"{user_name}-{user_ID}_intelligence_Assessment.png")
            graph_images.append(image_path)
            plt.savefig(image_path, bbox_inches='tight')  # Save image with tight layout
            plt.close()

    except Exception as e:
        print(f"Error creating intelligence assessment graph: {e}")
        personality = ''

    return below, avg, above_avg, personality, min_length, max_length
     

def download_pdf(request,test_paper):
    if request.method == 'POST':
        test_paper = request.POST.get('test_paper')
        questions = Question.objects.filter(test_paper=test_paper)      

        if not questions:
            return HttpResponse("No questions found for this test.", status=404)
        
    top_3_categories = ""
    top_categories = []
    questions= Question.objects.all()
    
    if questions is not None:
        test1_result = Results.objects.get(user = request.user, test_paper='test1')
        sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
        for i, (category, score) in enumerate(sorted_results, start=1):
            if i > 3:
                break
            top_categories.append({
                'rank': i,
                'category': category,
                'score': f"{score:.2f}%"
            })
            
            top_3_categories += category[0]

        top_3_categories_str = "".join(top_3_categories)
        
        analysis_content = read_json_file('RIASEC.json')

        # Assume `request.user` is your user object

        below, avg, above_avg, personality, min_length, max_length = gernate_graph(request)
        # print('################## ',test_paper)
        if test_paper == 'test1':            
            template_path = 'personality-assessment-pdf.html'
        elif test_paper == 'test2':
            template_path = 'interest-assessment-pdf.html'
        elif test_paper == 'test3':            
            template_path = 'intelligence-assessment-pdf.html'
            
        else:
            template_path = 'pdf_template_final.html'
        # print('################## template_path',template_path)
        ''' ################ test complection logic###################'''
        # current_user = request.user
        # # Fetch or create TestCompletion instance for the current user
        # test_completion, created = TestCompletion.objects.get_or_create(user=current_user)
        try:
            test_completion= TestCompletion.objects.get(user=request.user)
        except:
            return HttpResponse("No User please Signup First")

        ''' ############## Ploygram Graphs #########################'''

        '''         Getting the data from the json file table Category   '''

        top_3 = top_3_categories_str.split(',')
        top_category_code = top_3[0]

        # Get the top category using the code
        top_category = Category.objects.filter(category=top_category_code).first()
        streamsubject = set()
        courseName = set()
        if top_category:
            category_id = top_category.id
            # Get streams related to this category using the category ID
            streams = Stream.objects.filter(category_id=category_id)
            # Print the details of each stream
            for stream in streams:
                streamsubject.add((stream.stream_name, stream.subjects))

            # Get courses related to this category using the category ID
            courses = Course.objects.filter(category_id=category_id)
            for course in courses:
                # Print the details of each courses
                courseName.add(course.course_name)

        else:
            print("No category found with the code:", top_category_code)
        
        if request.user.is_authenticated:
            user = request.user

            try:
                # Retrieve the UserProfile for the logged-in user (create if not exists)
                user_profile, created = UserProfile.objects.get_or_create(user=user)
                
            except UserProfile.DoesNotExist:
                user_profile = None

            # Get all fields from the User model for the current user
            student_name = User.objects.get(pk=user.id) 

            try:
                # Retrieve the UserProfile for the logged-in user
                user_profile = user.user_profile
                # Access attributes from the User object
                created_date = user.created

                # Access attributes from the UserProfile object
                gender = user_profile.gender
                schoolname = user_profile.schoolname
                grade = user_profile.grade

                

            except UserProfile.DoesNotExist:
                print("UserProfile does not exist.")

        else:
            print("User is not authenticated.")

        user_name = request.user
        user_ID = request.user.id

        context = {
            'score': score,
            'user_name':user_name,
            'user_ID':user_ID,
            'user_profile':user_profile,
            'student_name':student_name,
            "School_Name:": schoolname,
            'created_date':created_date,
            "Gender:": gender,
            "Grade:": grade,
            'intelligence_score':personality,
            'questions': questions,
            'top_categories':top_categories,
            'top_3_categories_str':top_3_categories_str,
            'top_category': top_category,
            'streamsubject':streamsubject,
            'courseName':courseName,
            'top_3_categories':top_3_categories,
            'test_completion': test_completion,
            'max_length': max_length,
            'min_length':min_length,
            'below':below,
            'avg':avg,
            'above_avg': above_avg,
        }

        try:
            template = get_template(template_path)
            html = template.render(context)
            # print()
            # print()
            # print("################## html", html)


            # print("HTML content generated successfully. ###################################")
            # print("Context:", html)
            # print("HTML content generated successfully Ends @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@.")

            # Configure SSL to disable verification for WeasyPrint image loading
            # This is needed because WeasyPrint tries to fetch images via HTTPS
            # and SSL certificate verification fails on the server
            # This is safe for internal requests to the same server
            import ssl
            
            # Disable SSL verification for urllib (used by WeasyPrint internally)
            original_ssl_context = ssl._create_default_https_context
            ssl._create_default_https_context = ssl._create_unverified_context
            
            try:
                # Use HTTPS with SSL verification disabled
                pdf_file = weasyprint.HTML(
                    string=html, 
                    base_url=request.build_absolute_uri('/')
                ).write_pdf()
            finally:
                # Restore original SSL context
                ssl._create_default_https_context = original_ssl_context
            response = HttpResponse(content_type='application/pdf')
            # Safe filename for Gmail/email usernames (no @, . or other chars that break on some filesystems)
            raw_name = getattr(request.user, 'name', None) or getattr(request.user, 'email', None) or str(request.user)
            safe_name = re.sub(r'[^\w\s-]', '', str(raw_name)).strip()[:50] or 'user'
            # Define the filename based on the test_paper value
            if test_paper == 'test1':
                filename = f"{safe_name}-Personality_Assessment_report.pdf"
            elif test_paper == 'test2':
                filename = f"{safe_name}-Interest_Assessment_report.pdf"
            elif test_paper == 'test3':
                filename = f"{safe_name}-Intelligence_Assessment_report.pdf"
            else:
                filename = f"{safe_name}-Final_Assessment_report.pdf"

            # Ensure user PDF folder exists (works for all users including Gmail/Google login)
            user_directory = ensure_user_pdf_folder(request.user.id)
            if not user_directory:
                import traceback
                print(f"download_pdf: ensure_user_pdf_folder failed for user_id={request.user.id}")
                traceback.print_exc()
                messages.error(request, 'Error creating download folder')
                return redirect('app:app_submit')

            # Save the PDF file
            pdf_path = os.path.join(user_directory, filename)
            with open(pdf_path, 'wb') as pdf_file_handle:
                pdf_file_handle.write(pdf_file)

            return redirect('app:app_submit')
            
        except Exception as e:
            import traceback
            print(f"Error generating PDF: {e}")
            traceback.print_exc()
            messages.error(request, 'Error generating PDF')
            return redirect('app:app_submit')
    else:
        messages.error(request, 'Error generating PDF')
        return redirect('app:quiz_questions')

from django.http import HttpResponse, Http404
@login_required(login_url=reverse_lazy('users:login'))
def test_1(request, test_paper):
    """
    Legacy view - redirects to new HTML report views
    """
    if test_paper == 'test1':
        return redirect('app:test1_report_html')
    elif test_paper == 'test2':
        return redirect('app:test2_report_html')
    elif test_paper == 'test3':
        return redirect('app:test3_report_html')
    else:
        return HttpResponse("Invalid test paper.", status=404)


@login_required(login_url=reverse_lazy('users:login'))
def test1_report_html(request, user_id=None):
    """
    HTML report view for Test 1 (Personality Assessment)
    """
    try:
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists (for later download/save)
        ensure_user_pdf_folder(target_user.id)
        
        # Check if test1 is completed
        try:
            test1_result = Results.objects.get(user=target_user, test_paper='test1')
        except Results.DoesNotExist:
            return render(request, 'template20/app/test1_report.html', {
                'error': 'Please complete the Personality Assessment test first.',
                'no_results': True,
                'user': target_user,
                'user_ID': target_user.id if target_user else None,
                'viewing_as_admin': False
            })
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get personality data
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            print(f"Error in db_results_inst_user: {e}")
            print(traceback.format_exc())
            top_category = None
            streamsubject = set()
            courseName = set()
            top_categories = []
        
        # Process personality test data
        personality_data = {}
        if test1_result and test1_result.results:
            sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
            personality_data = {
                'results': dict(sorted_results),
                'top_categories': top_categories,
                'top_category': top_category
            }
        
        # Generate graph only if it doesn't exist (optimization)
        user_name = target_user.name if target_user.name else target_user.email
        user_ID = target_user.id
        graph_filename = f"{user_name}-{user_ID}_personality_Assessment.png"
        graph_path = os.path.join(settings.MEDIA_ROOT, 'graph_images', graph_filename)
        
        if not os.path.exists(graph_path):
            try:
                # Temporarily set request.user for graph generation
                original_user = request.user
                request.user = target_user
                gernate_graph(request)
                request.user = original_user
            except Exception as e:
                print(f"Error generating graph: {e}")
                pass
        
        context = {
            'user': target_user,
            'user_profile': user_profile,
            'personality_data': personality_data,
            'top_category': top_category,
            'streamsubject': streamsubject,
            'courseName': courseName,
            'top_categories': top_categories,
            'user_name': target_user.name if target_user.name else target_user.email,
            'user_ID': target_user.id,
            'no_results': False,
            'viewing_as_admin': user_id is not None and user_id != request.user.id
        }
        
        return render(request, 'template20/app/test1_report.html', context)
        
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        print(f"Error in test1_report_html: {str(e)}")
        print(trace)
        return render(request, 'template20/app/test1_report.html', {
            'error': f'An error occurred: {str(e)}',
            'no_results': True,
            'user': request.user,
            'user_ID': request.user.id if request.user.is_authenticated else None,
            'viewing_as_admin': False
        })


@login_required(login_url=reverse_lazy('users:login'))
def test2_report_html(request, user_id=None):
    """
    HTML report view for Test 2 (Interest Assessment)
    """
    try:
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists (for later download/save)
        ensure_user_pdf_folder(target_user.id)
        
        # Check if test2 is completed
        try:
            test2_result = Results.objects.get(user=target_user, test_paper='test2')
        except Results.DoesNotExist:
            return render(request, 'template20/app/test2_report.html', {
                'error': 'Please complete the Career Interest Assessment test first.',
                'no_results': True,
                'user': target_user,
                'user_ID': target_user.id if target_user else None,
                'viewing_as_admin': False
            })
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get interest data
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            print(f"Error in db_results_inst_user: {e}")
            print(traceback.format_exc())
            max_length = ''
            min_length = ''
        
        # Process interest test data
        interest_data = {}
        if test2_result and test2_result.scores:
            interest_data = {
                'scores': test2_result.scores,
                'max_category': max_length,
                'min_category': min_length
            }
        
        # Generate graph only if it doesn't exist (optimization)
        user_name = target_user.name if target_user.name else target_user.email
        user_ID = target_user.id
        graph_filename = f"{user_name}-{user_ID}_interest_Assessment.png"
        graph_path = os.path.join(settings.MEDIA_ROOT, 'graph_images', graph_filename)
        
        if not os.path.exists(graph_path):
            try:
                # Temporarily set request.user for graph generation
                original_user = request.user
                request.user = target_user
                gernate_graph(request)
                request.user = original_user
            except Exception as e:
                print(f"Error generating graph: {e}")
                pass
        
        context = {
            'user': target_user,
            'user_profile': user_profile,
            'interest_data': interest_data,
            'max_length': max_length,
            'min_length': min_length,
            'user_name': target_user.name if target_user.name else target_user.email,
            'user_ID': target_user.id,
            'no_results': False,
            'viewing_as_admin': user_id is not None and user_id != request.user.id
        }
        
        return render(request, 'template20/app/test2_report.html', context)
        
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        print(f"Error in test2_report_html: {str(e)}")
        print(trace)
        return render(request, 'template20/app/test2_report.html', {
            'error': f'An error occurred: {str(e)}',
            'no_results': True,
            'user': request.user,
            'user_ID': request.user.id if request.user.is_authenticated else None,
            'viewing_as_admin': False
        })


@login_required(login_url=reverse_lazy('users:login'))
def test3_report_html(request, user_id=None):
    """
    HTML report view for Test 3 (Intelligence Assessment)
    """
    try:
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists (for later download/save)
        ensure_user_pdf_folder(target_user.id)
        
        # Check if test3 is completed
        try:
            test3_result = Results.objects.get(user=target_user, test_paper='test3')
        except Results.DoesNotExist:
            return render(request, 'template20/app/test3_report.html', {
                'error': 'Please complete the Intelligence Assessment test first.',
                'no_results': True,
                'user': target_user,
                'user_ID': target_user.id if target_user else None,
                'viewing_as_admin': False
            })
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get intelligence data
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            print(f"Error in db_results_inst_user: {e}")
            print(traceback.format_exc())
            below = []
            avg = []
            above_avg = []
        
        # Process intelligence test data
        intelligence_data = {}
        if test3_result and test3_result.scores:
            scores = {label.split("_")[0].upper(): value for label, value in test3_result.scores.items()}
            intelligence_data = {
                'scores': scores,
                'below_avg': below,
                'average': avg,
                'above_avg': above_avg
            }
        
        # Generate graph only if it doesn't exist (optimization)
        user_name = target_user.name if target_user.name else target_user.email
        user_ID = target_user.id
        graph_filename = f"{user_name}-{user_ID}_intelligence_Assessment.png"
        graph_path = os.path.join(settings.MEDIA_ROOT, 'graph_images', graph_filename)
        
        if not os.path.exists(graph_path):
            try:
                # Temporarily set request.user for graph generation
                original_user = request.user
                request.user = target_user
                gernate_graph(request)
                request.user = original_user
            except Exception as e:
                print(f"Error generating graph: {e}")
                pass
        
        context = {
            'user': target_user,
            'user_profile': user_profile,
            'intelligence_data': intelligence_data,
            'below': below,
            'avg': avg,
            'above_avg': above_avg,
            'user_name': target_user.name if target_user.name else target_user.email,
            'user_ID': target_user.id,
            'no_results': False,
            'viewing_as_admin': user_id is not None and user_id != request.user.id
        }
        
        return render(request, 'template20/app/test3_report.html', context)
        
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        print(f"Error in test3_report_html: {str(e)}")
        print(trace)
        return render(request, 'template20/app/test3_report.html', {
            'error': f'An error occurred: {str(e)}',
            'no_results': True,
            'user': request.user,
            'user_ID': request.user.id if request.user.is_authenticated else None,
            'viewing_as_admin': False
        })


def _resolve_static_urls_to_local_paths(html_content, base_url):
    """
    Replace /static/ and /media/ URLs in HTML with local file paths
    to avoid HTTP requests during PDF generation.
    This significantly speeds up PDF generation by eliminating network requests.
    """
    def replace_static(match):
        quote_char = match.group(1)  # Captured quote character (" or ')
        static_path = match.group(2)  # Path after /static/
        # Try to find the static file using Django's staticfiles finder
        found_path = finders.find(static_path)
        if found_path:
            # Normalize path separators for file:// URLs (use forward slashes)
            normalized_path = found_path.replace('\\', '/')
            # Convert to file:// URL with proper formatting
            return f'{match.group(0)[:match.start(2)-match.start()]}file:///{normalized_path}{quote_char}'
        # If not found, return original
        return match.group(0)
    
    def replace_media(match):
        quote_char = match.group(1)  # Captured quote character (" or ')
        media_path = match.group(2)  # Path after /media/
        # Construct full media file path
        media_file_path = os.path.join(settings.MEDIA_ROOT, media_path)
        if os.path.exists(media_file_path):
            # Normalize path separators for file:// URLs (use forward slashes)
            normalized_path = media_file_path.replace('\\', '/')
            # Convert to file:// URL with proper formatting
            return f'{match.group(0)[:match.start(2)-match.start()]}file:///{normalized_path}{quote_char}'
        # If not found, return original
        return match.group(0)
    
    # Replace /static/ URLs in src and href attributes (capture quote and path separately)
    html_content = re.sub(
        r'(src|href)=(["\'])/static/([^"\']+)\2',
        lambda m: f'{m.group(1)}={m.group(2)}file:///{finders.find(m.group(3)).replace(chr(92), "/")}{m.group(2)}' if finders.find(m.group(3)) else m.group(0),
        html_content
    )
    
    # Replace /media/ URLs in src and href attributes (capture quote and path separately)
    html_content = re.sub(
        r'(src|href)=(["\'])/media/([^"\']+)\2',
        lambda m: (lambda path, quote: f'{m.group(1)}={quote}file:///{path.replace(chr(92), "/")}{quote}' if os.path.exists(path) else m.group(0))(os.path.join(settings.MEDIA_ROOT, m.group(3)), m.group(2)),
        html_content
    )
    
    return html_content


@login_required(login_url=reverse_lazy('users:login'))
def test1_report_pdf(request, user_id=None):
    """
    PDF download view for Test 1 (Personality Assessment)
    """
    try:
        import weasyprint
        from django.template.loader import get_template
        from datetime import datetime
        
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists
        ensure_user_pdf_folder(target_user.id)
        
        # Check if test1 is completed
        try:
            test1_result = Results.objects.get(user=target_user, test_paper='test1')
        except Results.DoesNotExist:
            return HttpResponse('Please complete the Personality Assessment test first.', status=404)
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get personality data
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            print(f"Error in db_results_inst_user: {e}")
            print(traceback.format_exc())
            top_category = None
            streamsubject = set()
            courseName = set()
            top_categories = []
        
        # Process personality test data
        personality_data = {}
        if test1_result and test1_result.results:
            sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
            personality_data = {
                'results': dict(sorted_results),
                'top_categories': top_categories,
                'top_category': top_category
            }
        
        # Generate graph only if it doesn't exist (optimization)
        user_name = target_user.name if target_user.name else target_user.email
        user_ID = target_user.id
        graph_filename = f"{user_name}-{user_ID}_personality_Assessment.png"
        graph_path = os.path.join(settings.MEDIA_ROOT, 'graph_images', graph_filename)
        
        if not os.path.exists(graph_path):
            try:
                # Temporarily set request.user for graph generation
                original_user = request.user
                request.user = target_user
                gernate_graph(request)
                request.user = original_user
            except Exception as e:
                print(f"Error generating graph: {e}")
                pass
        
        # Get created_date and student_name
        created_date = test1_result.created if hasattr(test1_result, 'created') else target_user.created
        student_name = target_user.name if target_user.name else target_user.email
        
        context = {
            'user': target_user,
            'user_profile': user_profile,
            'personality_data': personality_data,
            'top_category': top_category,
            'streamsubject': streamsubject,
            'courseName': courseName,
            'top_categories': top_categories,
            'user_name': target_user.name if target_user.name else target_user.email,
            'user_ID': target_user.id,
            'student_name': student_name,
            'created_date': created_date,
            'now': datetime.now(),
        }
        
        # Render HTML template
        template = get_template('template20/app/test1_report_pdf.html')
        html = template.render(context)
        
        # Generate PDF with optimizations
        # Keep HTTP base_url for proper static/media resolution
        # The main optimization is graph generation check (skip if exists)
        # and image optimization for smaller file size
        import ssl
        original_ssl_context = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context
        
        try:
            pdf_file = weasyprint.HTML(
                string=html,
                base_url=request.build_absolute_uri('/')
            ).write_pdf(optimize_images=True)
        finally:
            ssl._create_default_https_context = original_ssl_context
        
        # Create response (safe filename for Gmail/email users)
        response = HttpResponse(pdf_file, content_type='application/pdf')
        raw_name = getattr(target_user, 'name', None) or getattr(target_user, 'email', 'user')
        safe_name = re.sub(r'[^\w\s-]', '', str(raw_name)).strip()[:50] or 'user'
        filename = f"{safe_name}-Personality_Assessment_report.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Save copy to user PDF folder (production and debugging)
        user_directory = ensure_user_pdf_folder(target_user.id)
        if user_directory:
            try:
                pdf_path = os.path.join(user_directory, filename)
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_file)
            except OSError as err:
                logger.warning("test1_report_pdf: could not save to user folder user_id=%s: %s", target_user.id, err)
        
        return response
        
    except Exception as e:
        logger.exception("test1_report_pdf failed: %s", e)
        return HttpResponse(f'Error generating PDF: {str(e)}', status=500)


@login_required(login_url=reverse_lazy('users:login'))
def test2_report_pdf(request, user_id=None):
    """
    PDF download view for Test 2 (Interest Assessment)
    """
    try:
        import weasyprint
        from django.template.loader import get_template
        from datetime import datetime
        
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists
        ensure_user_pdf_folder(target_user.id)
        
        # Check if test2 is completed
        try:
            test2_result = Results.objects.get(user=target_user, test_paper='test2')
        except Results.DoesNotExist:
            return HttpResponse('Please complete the Career Interest Assessment test first.', status=404)
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get interest data
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            print(f"Error in db_results_inst_user: {e}")
            print(traceback.format_exc())
            max_length = ''
            min_length = ''
        
        # Process interest test data
        interest_data = {}
        if test2_result and test2_result.scores:
            interest_data = {
                'scores': test2_result.scores,
                'max_category': max_length,
                'min_category': min_length
            }
        
        # Generate graph only if it doesn't exist (optimization)
        user_name = target_user.name if target_user.name else target_user.email
        user_ID = target_user.id
        graph_filename = f"{user_name}-{user_ID}_interest_Assessment.png"
        graph_path = os.path.join(settings.MEDIA_ROOT, 'graph_images', graph_filename)
        
        if not os.path.exists(graph_path):
            try:
                # Temporarily set request.user for graph generation
                original_user = request.user
                request.user = target_user
                gernate_graph(request)
                request.user = original_user
            except Exception as e:
                print(f"Error generating graph: {e}")
                pass
        
        # Get created_date and student_name
        created_date = test2_result.created if hasattr(test2_result, 'created') else target_user.created
        student_name = target_user.name if target_user.name else target_user.email
        
        context = {
            'user': target_user,
            'user_profile': user_profile,
            'interest_data': interest_data,
            'max_length': max_length,
            'min_length': min_length,
            'user_name': target_user.name if target_user.name else target_user.email,
            'user_ID': target_user.id,
            'student_name': student_name,
            'created_date': created_date,
            'now': datetime.now(),
        }
        
        # Render HTML template
        template = get_template('template20/app/test2_report_pdf.html')
        html = template.render(context)
        
        # Generate PDF with optimizations
        # Keep HTTP base_url for proper static/media resolution
        # The main optimization is graph generation check (skip if exists)
        # and image optimization for smaller file size
        import ssl
        original_ssl_context = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context
        
        try:
            pdf_file = weasyprint.HTML(
                string=html,
                base_url=request.build_absolute_uri('/')
            ).write_pdf(optimize_images=True)
        finally:
            ssl._create_default_https_context = original_ssl_context
        
        # Create response (safe filename for Gmail/email users)
        raw_name = getattr(target_user, 'name', None) or getattr(target_user, 'email', 'user')
        safe_name = re.sub(r'[^\w\s-]', '', str(raw_name)).strip()[:50] or 'user'
        filename = f"{safe_name}-Interest_Assessment_report.pdf"
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        user_directory = ensure_user_pdf_folder(target_user.id)
        if user_directory:
            try:
                with open(os.path.join(user_directory, filename), 'wb') as f:
                    f.write(pdf_file)
            except OSError as err:
                logger.warning("test2_report_pdf: could not save to user folder user_id=%s: %s", target_user.id, err)
        return response

    except Exception as e:
        logger.exception("test2_report_pdf failed: %s", e)
        return HttpResponse(f'Error generating PDF: {str(e)}', status=500)


@login_required(login_url=reverse_lazy('users:login'))
def test3_report_pdf(request, user_id=None):
    """
    PDF download view for Test 3 (Intelligence Assessment)
    """
    try:
        import weasyprint
        from django.template.loader import get_template
        from datetime import datetime
        
        # Get the target user
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
        else:
            target_user = request.user

        # Ensure user PDF folder exists
        ensure_user_pdf_folder(target_user.id)
        
        # Check if test3 is completed
        try:
            test3_result = Results.objects.get(user=target_user, test_paper='test3')
        except Results.DoesNotExist:
            return HttpResponse('Please complete the Intelligence Assessment test first.', status=404)
        
        # Get user profile
        try:
            user_profile = target_user.user_profile
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get intelligence data
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
        except Exception as e:
            import traceback
            print(f"Error in db_results_inst_user: {e}")
            print(traceback.format_exc())
            below = []
            avg = []
            above_avg = []
        
        # Process intelligence test data
        intelligence_data = {}
        if test3_result and test3_result.scores:
            scores = {label.split("_")[0].upper(): value for label, value in test3_result.scores.items()}
            intelligence_data = {
                'scores': scores,
                'below_avg': below,
                'average': avg,
                'above_avg': above_avg
            }
        
        # Generate graph only if it doesn't exist (optimization)
        user_name = target_user.name if target_user.name else target_user.email
        user_ID = target_user.id
        graph_filename = f"{user_name}-{user_ID}_intelligence_Assessment.png"
        graph_path = os.path.join(settings.MEDIA_ROOT, 'graph_images', graph_filename)
        
        if not os.path.exists(graph_path):
            try:
                # Temporarily set request.user for graph generation
                original_user = request.user
                request.user = target_user
                gernate_graph(request)
                request.user = original_user
            except Exception as e:
                print(f"Error generating graph: {e}")
                pass
        
        # Get created_date and student_name
        created_date = test3_result.created if hasattr(test3_result, 'created') else target_user.created
        student_name = target_user.name if target_user.name else target_user.email
        
        context = {
            'user': target_user,
            'user_profile': user_profile,
            'intelligence_data': intelligence_data,
            'below': below,
            'avg': avg,
            'above_avg': above_avg,
            'user_name': target_user.name if target_user.name else target_user.email,
            'user_ID': target_user.id,
            'student_name': student_name,
            'created_date': created_date,
            'now': datetime.now(),
        }
        
        # Render HTML template
        template = get_template('template20/app/test3_report_pdf.html')
        html = template.render(context)
        
        # Generate PDF with optimizations
        # Keep HTTP base_url for proper static/media resolution
        # The main optimization is graph generation check (skip if exists)
        # and image optimization for smaller file size
        import ssl
        original_ssl_context = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context
        
        try:
            pdf_file = weasyprint.HTML(
                string=html,
                base_url=request.build_absolute_uri('/')
            ).write_pdf(optimize_images=True)
        finally:
            ssl._create_default_https_context = original_ssl_context
        
        # Create response (safe filename for Gmail/email users)
        raw_name = getattr(target_user, 'name', None) or getattr(target_user, 'email', 'user')
        safe_name = re.sub(r'[^\w\s-]', '', str(raw_name)).strip()[:50] or 'user'
        filename = f"{safe_name}-Intelligence_Assessment_report.pdf"
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        user_directory = ensure_user_pdf_folder(target_user.id)
        if user_directory:
            try:
                with open(os.path.join(user_directory, filename), 'wb') as f:
                    f.write(pdf_file)
            except OSError as err:
                logger.warning("test3_report_pdf: could not save to user folder user_id=%s: %s", target_user.id, err)
        return response

    except Exception as e:
        logger.exception("test3_report_pdf failed: %s", e)
        return HttpResponse(f'Error generating PDF: {str(e)}', status=500)


import json
import openpyxl
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from users.models import UserProfile
from app.models import Results, TestCompletion
from openpyxl.styles import Alignment
from openpyxl import Workbook
from .models import Results
from django.http import HttpResponse

def export_to_excel(request, email):
    # Fetch the desired number of users' data
    # results = Results.objects.all()[:num_users]

    # institute = Institute.objects.get(slug='terii-public-school-kurukshetra')
    # # institute = Institute.objects.get(slug='sggs-c-p-school')
    # stu_manage = StudentManagement.objects.filter(institute=institute)[:10]

    # user = get_object_or_404(User, email=email)

    # Create a workbook and add a worksheet
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "User Results"

    # Add headers for the columns (Including test1_scores)
    headers = [
        'User',
        'Test1_Scores', 'Test1_Results', 'Test1_Selected_Answers',
        'Test2_Scores', 'Test2_Results', 'Test2_Selected_Answers',
        'Test3_Scores', 'Test3_Results', 'Test3_Selected_Answers'
    ]
    ws.append(headers)

    # Dictionary to hold users' data
    users = {}

    # all_results = Results.objects.filter(user__in=[stu.student for stu in stu_manage])
    all_results = Results.objects.filter(user__email=email)
    # Populate users dictionary with test data
    for result in all_results:
        user = result.user.email

        # Initialize data structure for a new user
        if user not in users:
            users[user] = {
                'test1_scores': '',
                'test1_results': '',
                'test1_selected_answers': '',
                'test2_scores': '',
                'test2_results': '',
                'test2_selected_answers': '',
                'test3_scores': '',
                'test3_results': '',
                'test3_selected_answers': ''
            }

        # Update data based on the test paper

        if result.test_paper == 'test1':
            users[user]['test1_scores'] = json.dumps(result.scores)  # Convert dict to string
            users[user]['test1_results'] = json.dumps(result.results)
            users[user]['test1_selected_answers'] = json.dumps(result.selected_answers)
        elif result.test_paper == 'test2':
            users[user]['test2_scores'] = json.dumps(result.scores)            
            users[user]['test2_results'] = json.dumps(result.results)
            users[user]['test2_selected_answers'] = json.dumps(result.selected_answers)
        elif result.test_paper == 'test3':
            users[user]['test3_scores'] = json.dumps(result.scores)
            users[user]['test3_results'] = json.dumps(result.results)
            users[user]['test3_selected_answers'] = json.dumps(result.selected_answers)

    # Add rows to the Excel sheet
    for user, data in users.items():
        row = [user]

        # Add Test 1 data
        row += [
            data['test1_scores'],
            data['test1_results'],
            data['test1_selected_answers']
        ]

        # Add Test 2 data
        row += [
            data['test2_scores'],
            data['test2_results'],
            data['test2_selected_answers']
        ]

        # Add Test 3 data
        row += [
            data['test3_scores'],
            data['test3_results'],
            data['test3_selected_answers']
        ]

        ws.append(row)

    # Save the workbook to the response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=student_results.xlsx'
    wb.save(response)
    return response
from django.contrib.staticfiles import finders
from weasyprint import HTML
def pdf_checker(request):
    # Your HTML content
    template = get_template('test1.html')
    html = template.render()
    
    # path = finders.find('images/pcm-icon.png')
    path = finders.find('graph_images/Manishwar Singh-138_personality_Assessment.png')
    

    # Configure SSL to disable verification for WeasyPrint image loading
    import ssl
    
    # Disable SSL verification for urllib (used by WeasyPrint internally)
    original_ssl_context = ssl._create_default_https_context
    ssl._create_default_https_context = ssl._create_unverified_context
    
    try:
        # Use HTTPS with SSL verification disabled
        pdf_file = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
    finally:
        # Restore original SSL context
        ssl._create_default_https_context = original_ssl_context
    
    # Create HTTP response
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="your_filename.pdf"'  # Use 'inline' to open in browser
    
    return response


@login_required(login_url=reverse_lazy('users:login'))
def test_pdf_preview(request, test_number=1, user_id=None):
    """
    Preview PDF templates in browser for testing header and layout
    Note: @page CSS rules won't render in browser, but header structure will be visible
    """
    from django.template.loader import get_template
    from datetime import datetime
    
    # Get the target user
    if user_id:
        target_user = get_object_or_404(User, id=user_id)
    else:
        target_user = request.user
    
    # Select template based on test number
    template_map = {
        1: 'template20/app/test1_report_pdf.html',
        2: 'template20/app/test2_report_pdf.html',
        3: 'template20/app/test3_report_pdf.html',
    }
    
    template_name = template_map.get(test_number, template_map[1])
    
    # Get test result if exists
    try:
        test_result = Results.objects.get(user=target_user, test_paper=f'test{test_number}')
    except Results.DoesNotExist:
        test_result = None
    
    # Get user profile
    try:
        user_profile = target_user.user_profile
    except UserProfile.DoesNotExist:
        user_profile = None
    
    # Create minimal context for preview
    context = {
        'user': target_user,
        'user_profile': user_profile,
        'user_name': target_user.name if target_user.name else target_user.email,
        'user_ID': target_user.id,
        'student_name': target_user.name if target_user.name else target_user.email,
        'created_date': datetime.now(),
        'now': datetime.now(),
    }
    
    # Add test-specific context
    if test_number == 1:
        try:
            top_category, streamsubject, courseName, max_length, min_length, below, avg, above_avg, top_categories = db_results_inst_user(target_user)
            context.update({
                'personality_data': {'results': {}, 'top_categories': top_categories, 'top_category': top_category},
                'top_category': top_category,
                'streamsubject': streamsubject,
                'courseName': courseName,
                'top_categories': top_categories,
            })
        except:
            context.update({
                'personality_data': {'results': {}, 'top_categories': [], 'top_category': None},
                'top_category': None,
                'streamsubject': set(),
                'courseName': set(),
                'top_categories': [],
            })
    elif test_number == 2:
        context.update({
            'interest_data': {},
            'max_length': None,
            'min_length': None,
        })
    elif test_number == 3:
        context.update({
            'intelligence_data': {},
        })
    
    # Render template
    template = get_template(template_name)
    html = template.render(context)
    
    # Return HTML response (for browser preview)
    return HttpResponse(html, content_type='text/html')
