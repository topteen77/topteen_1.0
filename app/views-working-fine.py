import time
from django.shortcuts import redirect, render
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
from django.shortcuts import get_object_or_404
# from django.contrib.auth.models import User
from .models import TestCompletion,Answer,Results

from django.views.decorators.csrf import csrf_exempt

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

def custom_logout(request):
    print('Logging out {}'.format(request.user))  # Logging the user who is logging out
    logout(request)
    return redirect('/')

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
                print(f"{i}. {category}: {score:.2f}%")
                top_3_categories += category[0]

            top_3_categories_str = "".join(top_3_categories)

        top_3 = top_3_categories_str.split(',')
        top_category_code = top_3[0]

        print("top_category_code",top_category_code,'\n')
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
        print('test3_result.scores', scores)
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

        # breakpoint()

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
    print("user",user)
    top_3_categories = ""
    top_categories = []
    questions= Question.objects.all()
    # Get the data from the database fro the Personality test
    try:
        if questions is not None:
            test1_result = Results.objects.get(user = user, test_paper='test1')
            print('test1_result.results',test1_result.results)
            sorted_results = sorted(test1_result.results.items(), key=lambda x: x[1], reverse=True)
            for i, (category, score) in enumerate(sorted_results, start=1):
                if i > 3:
                    break
                top_categories.append({
                    'rank': i,
                    'category': category,
                    'score': f"{score:.2f}%"
                })
                print(f"{i}. {category}: {score:.2f}%")
                top_3_categories += category[0]

            top_3_categories_str = "".join(top_3_categories)

        top_3 = top_3_categories_str.split(',')
        top_category_code = top_3[0]

        print("top_category_code",top_category_code,'\n')
    except:
        top_categories = ''
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
        print('test3_result.scores', scores)
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
    except Exception as e:
        print("Error in db_results_inst_user:", str(e))
        raise
    
    
    user_name = user
    user_ID = user_id
    # Prepare context dictionary
    context = {
        'user_name':user_name,
        'user_ID':user_ID,
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
    # try:
    
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
            gender = user_profile.gender
            schoolname = user_profile.schoolname
            student_name = user.email  # Assuming email is used as student name
            grade = user_profile.grade

        except UserProfile.DoesNotExist:
            print("UserProfile does not exist.")

    else:
        print("User is not authenticated.")

    try:
        test_completion = TestCompletion.objects.get(user=request.user)
    except TestCompletion.DoesNotExist:
        # Create a new TestCompletion object if it doesn't exist
        test_completion = TestCompletion.objects.create(user=request.user)

    context = {
        'user_profile':user_profile,
        'test_completion':test_completion,
        "School_Name:": schoolname,
        'created_date':created_date,
        "Gender:": gender,
        "Grade:": grade


    }
    return render(request, 'topteenfrontend/user/app/psychometric-test-view.html', context)

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
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    context = {
        'user_profile': user_profile,
    }
    return render(request, 'topteenfrontend/user/app/psychometric-test-instruction-1.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test2_intro(request):
    
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    context = {
        'user_profile': user_profile,
    }
    return render(request, 'topteenfrontend/user/app/psychometric-test-instruction-2.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_intro(request):
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    # Prepare context dictionary
    context = {
        'user_profile': user_profile,
    }
    return render(request, 'topteenfrontend/user/app/psychometric-test-instruction-3.html', context)

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
    return render(request, 'topteenfrontend/user/app/personality-test-form-test1.html',context)

@login_required(login_url=reverse_lazy('users:login'))
def test2_view(request):
    questions = Question.objects.filter(test_paper='test2')
    csrf_token = get_token(request)
    try:
        test_completion = TestCompletion.objects.get(user=request.user)
    except TestCompletion.DoesNotExist:
        # Create a new TestCompletion object if it doesn't exist
        test_completion = TestCompletion.objects.create(user=request.user)
    # Fetch or create the Results object for the user and test3
    # test3_result, created = Results.objects.update_or_create(
    #     user=request.user,
    #     test_paper='test3',
    #     defaults={
    #         'scores': {
    #             'logical_score': 0,
    #             'verbal_score': 0,
    #             'numerical_score': 0,
    #             'critical_score': 0,
    #             'language_score': 0,
    #             'spatial_score': 0,
    #             'mechanical_score': 0,
    #         },
    #         'results': {},  # Add any default for 'results' here if needed
    #     }
    # )
    # # Save the result object if it was modified
    # if created:
    #     test3_result.save()
    # print('test3_result',test3_result)
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    context = {
        'user_profile': user_profile,
        'questions': questions,
        'test_paper': 'test1',
        'csrf_token':csrf_token,
    }
    return render(request, 'topteenfrontend/user/app/interest-assessment-test2.html', context)


@login_required(login_url=reverse_lazy('users:login'))
def test3_view(request):
    context = {}
    if request.method == 'POST':
        test_paper = request.POST.get('test_paper')
        questions = Question.objects.filter(test_paper=test_paper)
        test_completion, created = TestCompletion.objects.get_or_create(user=request.user)

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

        context = {
            'user_profile': user_profile,
            'questions': questions,
            'test_paper': 'test3',
            'test_completion': test_completion
        }
    
    return render(request, 'topteenfrontend/user/app/psychometric-third-test-screen.html', context)


@login_required(login_url=reverse_lazy('users:login'))
def test3_numerical(request):
    questions = Question.objects.filter(test_paper='test3', category='Numerical')
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
    
    return render(request, 'topteenfrontend/user/app/Intelligence-test3-logical.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_logical(request):
    questions = Question.objects.filter(test_paper='test3', category ='Logical')
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
    
    return render(request, 'topteenfrontend/user/app/Intelligence-test3-logical.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def test3_verbal(request):
    
    questions = Question.objects.filter(test_paper='test3', category ='Verbal')
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
    
    return render(request, 'topteenfrontend/user/app/Intelligence-test3-logical.html', context)

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
    
    return render(request, 'topteenfrontend/user/app/Intelligence-test3-logical.html', context)

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

    return render(request, 'topteenfrontend/user/app/Intelligence-test3-logical.html', context)

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
    
    return render(request, 'topteenfrontend/user/app/Intelligence-test3-logical.html', context)

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
    
    return render(request, 'topteenfrontend/user/app/Intelligence-test3-logical.html', context)

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
                #print('submitted_answer--###',submitted_answer,'\n','selected_options',selected_options,'\n','total_score',total_score)
                # if total_score > 0:
                #     for i, category in enumerate(categories.keys()):
                #             if i < len(submitted_answer):
                #                 results[categories[category]] += submitted_answer[i] / total_score * 100
                #             else:
                #                 results[categories[category]] = 0

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

                # Print the result
                
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
        # elif test_paper == 'test3':
        #     test_completion.test3_complete = True
        #     test_completion.save()
        else:
            test_completion.test3_complete = True
            test_completion.save()

    # Load analysis content from a JSON file
    # analysis_content = read_json_file('RIASEC.json')
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None
    test_completion = TestCompletion.objects.get(user=request.user)
    # Prepare context for rendering the template
    context = {
        # 'analysis_content': analysis_content,
        'test_completion': test_completion,
        'user_profile': user_profile
    }
    generate_pdf(request)
    return render(request, 'topteenfrontend/user/app/psychometric-test-view.html', context)

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
    # breakpoint()
    graph_images_folder = BASE_DIR / 'media' / 'graph_images'
    if not os.path.exists(graph_images_folder):
        os.makedirs(graph_images_folder)

    graph_images = []

    # Assuming sorted_result contains scores between 0 and 100.
    if sorted_result:
        original_labels = list(sorted_result.keys())
        labels = [label.upper() for label in original_labels]
        values = list(sorted_result.values())

        # Define figure and axis
        fig, ax = plt.subplots(figsize=(20, 10))
        
        # Colors for the bars
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
            original_labels = list(lengths.keys())
            labels = [label.split("_")[0].upper() for label in original_labels]
            values = list(lengths.values())
            
            # Create the figure and axis
            fig, ax = plt.subplots(figsize=(24, 12))
            
            # Define colors for the bars
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
            print("labels", labels, original_labels)
            
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

        if test_paper == 'test1':            
            template_path = 'personality-assessment-pdf.html'
        elif test_paper == 'test2':
            template_path = 'interest-assessment-pdf.html'
        elif test_paper == 'test3':            
            template_path = 'intelligence-assessment-pdf.html'
            
        else:
            template_path = 'pdf_template_final.html'

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

            pdf_file = weasyprint.HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()
            response = HttpResponse(content_type='application/pdf')
            # Define the filename based on the test_paper value
            if test_paper == 'test1':
                filename = f"{user_name}-Personality_Assessment_report.pdf"
            elif test_paper == 'test2':
                filename = f"{user_name}-Interest_Assessment_report.pdf"
            elif test_paper == 'test3':
                filename = f"{user_name}-Intelligence_Assessment_report.pdf"
            else:
                filename = f"{user_name}-Final_Assessment_report.pdf"

            # return response

            # Create the directory if it doesn't exist
            user_directory = os.path.join(settings.MEDIA_ROOT, 'users_pdfs',  str(request.user.id))
            if not os.path.exists(user_directory):
                os.makedirs(user_directory)

            # Save the PDF file
            pdf_path = os.path.join(user_directory, filename)
            with open(pdf_path, 'wb') as pdf_file_handle:
                pdf_file_handle.write(pdf_file)

            return redirect('app:app_submit')
            
        except Exception as e:
            print(f"Error generating PDF: {e}")  # Log the error
            messages.error(request, 'Error generating PDF')
            return redirect('app:app_submit')
    else:
        messages.error(request, 'Error generating PDF')
        return redirect('app:quiz_questions')

from django.http import HttpResponse, Http404
@login_required(login_url=reverse_lazy('users:login'))
def test_1(request, test_paper):
        
    if request.method == 'GET':
        
        user_name = request.user  # Use username for filename
        user_ID = request.user.id

        #generate_pdf(request)

        # Define the filename based on the test_paper value
        if test_paper == 'test1':
            filename = f"{user_name}-Personality_Assessment_report.pdf"
        elif test_paper == 'test2':
            filename = f"{user_name}-Interest_Assessment_report.pdf"
        elif test_paper == 'test3':
            filename = f"{user_name}-Intelligence_Assessment_report.pdf"
        else:
            filename = f"{user_name}-Final_Assessment_report.pdf"

        # Construct the full path to the PDF file
        pdf_path = os.path.join(settings.MEDIA_ROOT, 'users_pdfs', str(user_ID), filename)

        # print("pdf_path",pdf_path)

        # Check if the file exists
        if os.path.exists(pdf_path):
            # Open the PDF file and return it as a response
            with open(pdf_path, 'rb') as pdf_file:
                response = HttpResponse(pdf_file.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'inline; filename="{filename}"'  # Use 'inline' to open in browser
                return response
        else:
            download_pdf(request,test_paper)
            messages.success(request, message="Pdf Gernated Successfully! \n Please Click on View Report.")
            return redirect('app:app_submit')

    return HttpResponse("Invalid request method.", status=405)


import json
import openpyxl
from django.shortcuts import render
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
    

    # Generate PDF
    pdf_file = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()
    
    # Create HTTP response
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="your_filename.pdf"'  # Use 'inline' to open in browser
    
    return response
