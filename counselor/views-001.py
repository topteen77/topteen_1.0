from datetime import datetime, date, timedelta
import json
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render
from django.core.paginator import Paginator
from app.models import Answer, Results
from institute.filters import StudentFilter
from institute.models import ClassAndSection, Institute, StudentManagement
from .models import Counselor, Quiz, Chapter, Part, QuizAnswers, QuizResults
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count
from django.utils import timezone
from django.views import View
from .models import Counselor, FollowUpStatus
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt
User = get_user_model()

# Create your views here.

# def CounselorMainDashboard(request):
    
#     return render(request, 'topteenfrontend/user/app/counselor_dashboard.html')

def get_students_in_institute(counselor):
    """Fetch assigned and unassigned students for a given counselor."""
    inst_coun = counselor.counselor_admin
    institute = get_object_or_404(Institute, id=inst_coun.id)
    all_institute_students = StudentManagement.objects.filter(institute=institute)
    
    # Get assigned and unassigned students
    assigned_students = counselor.get_students(institute=institute)
    assigned_student_ids = assigned_students.values_list('id', flat=True)
    unassigned_students = all_institute_students.exclude(id__in=assigned_student_ids)

    # Return assigned or unassigned students based on availability
    students_to_display = assigned_students if assigned_student_ids else unassigned_students
    return students_to_display, assigned_students, unassigned_students

def get_results_data_for_students(students):
    """Prepare results data for a list of students."""
    results_data = {}
    
    for student_management in students:
        student = student_management.student  # Access the student related to StudentManagement
        results = Results.objects.filter(user=student)
        success_count = sum(1 for result in results if result.is_test_successful)
        if results.exists():
            latest_result = results.last()

            results_data[student] = {
                "test_success": success_count > 0,
                "test_link": latest_result.get_test_report_or_test_link(student) if latest_result else None,
                "success_count": success_count,
            }
        
    return results_data


import logging
logger = logging.getLogger(__name__)

def Students_follow_up(request, coun_id):
    # Get the counselor and institute details
    counselor = get_object_or_404(Counselor, id=coun_id)
    inst_coun = counselor.counselor_admin
    institute = get_object_or_404(Institute, id=inst_coun.id)

    # Get all students in the institute and filter by the counselor
    all_institute_students = StudentManagement.objects.filter(institute=institute)
    students_to_display, _, _ = get_students_in_institute(counselor)
    
    # Initialize follow_up_data as an empty list
    follow_up_data = []

    if request.method == 'POST':
        # Retrieve the student ID from the form
        student_id = request.POST.get('student_id')
        if student_id:
            logger.debug(f"Received student ID: {student_id}")
            try:
                student_management_instance = all_institute_students.get(student=student_id)
            except StudentManagement.DoesNotExist:
                logger.warning("Student not found.")
                messages.error(request, 'Selected student not found in the specified institute.')
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

    # Retrieve follow-up data for all students associated with the counselor
    follow_ups = FollowUpStatus.objects.filter(counselor=counselor)
    
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
    
    # Apply filters based on GET parameters
    class_filter = request.GET.get('class_and_section')
    name_filter = request.GET.get('student_name')

    # Filter merged_data based on class_filter
    if class_filter:
        merged_data = [student for student in merged_data if student['student'].class_and_section.class_and_section == class_filter]

    # Filter merged_data based on name_filter
    if name_filter:
        merged_data = [student for student in merged_data if name_filter.lower() in student['student'].student.name.lower()]

    print("filtered_students:", merged_data)
    
    # Setting up pagination
    paginator = Paginator(merged_data, 10)  # 10 students per page
    page_number = request.GET.get('page')
    students_page = paginator.get_page(page_number)

    # Render context
    context = {
        'counselors': counselor,
        'students': students_page,
        'class_and_sections': ClassAndSection.objects.all(),
        'students_count': students_to_display,
        'total_is_followed_up_count': total_is_followed_up_count,
        'coun_id' : coun_id
    }

    return render(request, 'topteenfrontend/user/app/coun_follow_up_page.html', context)

def CounselorCoursepayment(request):    
    return render(request, 'topteenfrontend/user/app/counselor-course.html')

def CounselorCourse(request):    
    return render(request, 'topteenfrontend/user/app/counselor-course-information.html')

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

# def CounselorDashboard(request, coun_id=None):

    counselor = get_object_or_404(Counselor, id=coun_id)
    students_to_display, _, _ = get_students_in_institute(counselor)
    results_data = get_results_data_for_students(students_to_display)

    # Retrieve follow-up data for all students associated with the counselor
    follow_ups = FollowUpStatus.objects.filter(counselor=counselor)
    
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
    
    # Apply filters based on GET parameters
    class_filter = request.GET.get('class_and_section')
    name_filter = request.GET.get('student_name')

    # Filter merged_data based on class_filter
    if class_filter:
        merged_data = [student for student in merged_data if student['student'].class_and_section.class_and_section == class_filter]

    # Filter merged_data based on name_filter
    if name_filter:
        merged_data = [student for student in merged_data if name_filter.lower() in student['student'].student.name.lower()]
    
    # Setting up pagination
    paginator = Paginator(merged_data, 10)  # 10 students per page
    page_number = request.GET.get('page')
    students_page = paginator.get_page(page_number)

    # Render context
    context = {
        'counselors': counselor,
        'students': students_page,
        'results_data': results_data,
        'class_and_sections': ClassAndSection.objects.all(),
        'students_count': students_to_display,
        'total_is_followed_up_count': total_is_followed_up_count,
        'coun_id' : coun_id
    }

    return render(request, 'topteenfrontend/user/app/counselor_dashboard.html', context)

def CounselorDashboard(request, coun_id=None):

    counselor = get_object_or_404(Counselor, id=coun_id)
    students_to_display, _, _ = get_students_in_institute(counselor)
    results_data = get_results_data_for_students(students_to_display)

    # Retrieve follow-up data for all students associated with the counselor
    follow_ups = FollowUpStatus.objects.filter(counselor=counselor)
    
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
    couns_sessions_data = []
    for student in students_to_display:
        student_info = {
            'student': student,
            'follow_ups': follow_up_data.get(student.id, {'follow_ups': []})['follow_ups'],
        }
        merged_data.append(student_info)

    # Sorting merged data
    merged_data = sorted(merged_data, key=lambda x: x['student'].student.name.lower())
    
    # Apply filters based on GET parameters
    class_filter = request.GET.get('class_and_section')
    name_filter = request.GET.get('student_name')

    # Filter merged_data based on class_filter
    if class_filter:
        merged_data = [student for student in merged_data if student['student'].class_and_section.class_and_section == class_filter]

    # Filter merged_data based on name_filter
    if name_filter:
        merged_data = [student for student in merged_data if name_filter.lower() in student['student'].student.name.lower()]

    sessions_data = (
        FollowUpStatus.objects
        .filter(counselor_id=coun_id)
        .values('last_follow_up_date', 'counselor__counselor_name')
        .annotate(session_count=Count('id'))
    )

    # Convert the queryset to a list, and convert date to string
    sessions_data_list = list(sessions_data)  # Convert queryset to list
    for session in sessions_data_list:
        session['last_follow_up_date'] = session['last_follow_up_date'].isoformat()  # Convert date to ISO format

    week_data = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}  # Monday to Saturday

    # Process the session data to aggregate session counts by day of the week
    for session in sessions_data_list:
        try:
            session_date = datetime.strptime(session['last_follow_up_date'], "%Y-%m-%d")
            day_of_week = session_date.weekday()  # Monday is 0

            if day_of_week < 6:  # Only consider Monday to Saturday
                week_data[day_of_week] += session['session_count']

        except KeyError as e:
            print(f"KeyError: {e} in session data: {session}")

    # Prepare the final list for rendering
    # Prepare the final list for rendering
    final_data = []
    for day, count in week_data.items():
        # Calculate the correct date for each day in the week
        try:
            final_data.append({
                "day": (session_date - timedelta(days=session_date.weekday() - day)).strftime("%Y-%m-%d"),
                "session_count": count
            })
        except:
            final_data =[]
            pass

    # Append the sessions data for the current counselor to the main list
    couns_sessions_data.append({
        'counselor_id': counselor.id,
        'counselor_name':counselor.counselor_name,
        'sessions': final_data  # Add sessions data for this counselor
    })
    # Convert to JSON
    try:
        sessions_data_json = json.dumps(couns_sessions_data)
        print("sessions_data_json",sessions_data_json)
    except Exception as e:
        print(f"Error serializing sessions data: {e}")
        sessions_data_json = '[]'

    # breakpoint()
    import razorpay
    client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))

    data = { "amount": 500*100, "currency": "INR", "receipt": "order_rcptid_11" }
    payment = client.order.create(data=data)


    # Setting up pagination
    paginator = Paginator(merged_data, 10)  # 10 students per page
    page_number = request.GET.get('page')
    students_page = paginator.get_page(page_number)
    # breakpoint()
    

    # Render context
    context = {
        'counselors': counselor,
        'students': students_page,
        'results_data': results_data,
        'class_and_sections': ClassAndSection.objects.all(),
        'students_count': students_to_display,
        'total_is_followed_up_count': total_is_followed_up_count,
        'coun_id' : coun_id,
        'sessions_data_json': sessions_data_json,
        'key':settings.RAZORPAY_API_KEY,
        'secrit':settings.RAZORPAY_API_SECRET,
        'payment':payment
        
    }

    return render(request, 'topteenfrontend/user/app/counselor_dashboard.html', context)



from django.http import JsonResponse
import json

def content_view(request):
    """
    View to display all chapters and their respective parts.
    """
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
        user = get_object_or_404(User, id=176)  # Use actual user ID
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

    return render(request, "content.html", context)




