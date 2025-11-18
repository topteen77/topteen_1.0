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

from django.http import JsonResponse


from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

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



@login_required(login_url=reverse_lazy('users:login'))

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
def display_pdfs(request):
    return render(request, 'topteenfrontend/user/app/99pdfs.html')

class CourseStartsView(View):
    def get(self, request, counselor_id):
        # Retrieve the counselor using the provided ID
        counselor = get_object_or_404(Counselor, id=counselor_id)
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
        return render(request, 'topteenfrontend/user/app/counselor-course-information.html',context)

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
    except Exception as e:
        print(f"Error serializing sessions data: {e}")
        sessions_data_json = '[]'

    # breakpoint()
    import razorpay
    client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))

    data = { "amount": 500*100, "currency": "INR", "receipt": "order_rcptid_11" }
    payment = client.order.create(data=data)


    # Setting up pagination
    paginator = Paginator(merged_data, 3)  # 10 students per page
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


# @login_required(login_url=reverse_lazy('users:login'))
class CounselorEnrolledCourseView(View):
    template_name = 'topteenfrontend/user/app/counselor-enrolled-course.html'

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
    return render(request, 'topteenfrontend/user/app/test_vvt_vedio.html')