from rest_framework import viewsets, permissions, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    TestCategory, Test, Question, Answer,
    TestSession, UserResponse, TestResult, Sections, SectionSession
)
from .serializers import (
    TestCategorySerializer, TestCategoryDetailSerializer,
    TestSerializer, TestDetailSerializer,
    QuestionSerializer, AnswerSerializer,
    TestSessionSerializer, TestSessionDetailSerializer,
    UserResponseSerializer, TestResultSerializer,
    UserSerializer, ResponseDetailSerializer, SectionsSerializer, SectionSessionSerializer
)

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

def Home(request):
    return render(request, "home.html")

def Tests(request):
    return render(request, "tests.html")

def Results(request):
    return render(request, "results.html")

def Results_details(request):
    return render(request, "result-details.html")

def Take_test(request, id):
    return render(request, "take-test.html", {"test_id": id})

def Test_details(request, id):
    return render(request, "test-details.html", {"test_id": id})

def Test_results(request, id):
    return render(request, "results.html", {"result_id": id})


def test_sections(request, test_id):

    print("kahkahfkjhf", test_id)
    # Implementation for viewing test sections
    return render(request, 'test_sections.html', {
        'test': test_id,
    })

# @login_required
def section_details(request,testId, section_id, session_id):
    # Get the test and section objects
    # test = get_object_or_404(Test, id=test_id)
    section = get_object_or_404(Sections, id=section_id)
    print(f"Sectiondflsjflksdjflksdjfkjsa: {section.title}")
    print(f"session_id: {session_id}, {testId}")
    
    context = {
        'section_id': section_id,
        'session_id': session_id,
        'test_id': testId,  # Add this

    }
    
    return render(request, 'section_details.html', context)

@login_required
def section_results(request,testId,result_id):
    # Add this new view for handling results
    
    return render(request, 'section_results.html', {
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
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            auth_login(request, user)
            return redirect("home")
        else:
            return render(request, "login.html", {"error": "Invalid credentials"})
    return render(request, "login.html")

def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        if User.objects.filter(username=username).exists():
            return render(request, "register.html", {"error": "Username already exists"})
        if User.objects.filter(email=email).exists():
            return render(request, "register.html", {"error": "Email already exists"})
        user = User.objects.create_user(username=username, email=email, password=password)
        auth_login(request, user)
        return redirect("home")
    return render(request, "register.html")

# class AnswerViewSet(viewsets.ModelViewSet):
#     queryset = Answer.objects.all()
#     serializer_class = AnswerSerializer

#     def get_serializer_context(self):
#         context = super().get_serializer_context()
#         context['request'] = self.request
#         return context

#     def get_queryset(self):
#         queryset = Answer.objects.all()
#         question_id = self.request.query_params.get('question', None)
#         if question_id is not None:
#             queryset = queryset.filter(question_id=question_id)
#         return queryset
    
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


# class AnswerViewSet(viewsets.ModelViewSet):
#     queryset = Answer.objects.all()
#     serializer_class = AnswerSerializer

    # def get_queryset(self):
    #     queryset = Answer.objects.all()
    #     question_id = self.request.query_params.get('question', None)
    #     if question_id is not None:
    #         queryset = queryset.filter(question_id=question_id)
    #     return queryset

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

    
    # @action(detail=True, methods=['post'])
    # def submit(self, request, pk=None):
    #     """Submit and complete a test session"""
    #     try:
    #         session = self.get_object()

    #         if session.is_completed:
    #             return Response(
    #                 {"detail": "This test session is already completed."},
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )

    #         # Mark session as completed
    #         session.is_completed = True
    #         session.end_time = timezone.now()
    #         session.save()

    #         # Get user responses
    #         user_response = session.responses.first()
    #         # submitted_answers = user_response.selected_answer.get('submitted_answers', {}) if user_response else {}
    #         if not user_response or not user_response.selected_answer:
    #             return Response(
    #                 {"detail": "No responses found for this session."},
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )

    #         submitted_answers = user_response.selected_answer.get('submitted_answers', {})

    #         if not submitted_answers:
    #             return Response(
    #                 {"detail": "No submitted answers found."},
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )

    #         test_title = session.test.title.lower().strip()

    #         # Initialize result_data and category_counts
    #         result_data = {}
    #         category_counts = {}

    #         questions = session.test.questions.all()
    #         question_dict = {f"Question_{q.order}": q for q in questions}

    #         breakpoint()

    #         if 'personality assessment' in test_title:
    #             # Personality assessment logic (uses score + dimension)
    #             for question_key, answer_obj in submitted_answers.items():
    #                 question = question_dict.get(question_key)
    #                 if not question:
    #                     continue

    #                 dimension = question.question_dimension
    #                 pattern = question.parttern  # assuming typo is consistent in model

    #                 # Safely extract score
    #                 if isinstance(answer_obj, dict):
    #                     raw_score = answer_obj.get('score', 0)
    #                 else:
    #                     raw_score = answer_obj

    #                 # Apply scoring logic
    #                 if pattern == 'Reverse':
    #                     score = 6 - raw_score
    #                 else:
    #                     score = raw_score

                    
    #                 if dimension not in result_data:
    #                     result_data[dimension] = {
    #                         'score': 0,
    #                         'count': 0
    #                     }

    #                 result_data[dimension]['score'] += score
    #                 result_data[dimension]['count'] += 1

    #             # Calculate average
    #             for dim in result_data:
    #                 count = result_data[dim]['count']
    #                 score = result_data[dim]['score']
    #                 result_data[dim]['average'] = score / count if count > 0 else 0

    #             # Get top 3 dimensions by total score
    #             top_3_dimensions = sorted(
    #                 result_data.items(),
    #                 key=lambda item: item[1]['score'],
    #                 reverse=True
    #             )[:3]

    #             # Print results
    #             print("\nTop 3 Dimensions by Score:")
    #             for dim, data in top_3_dimensions:
    #                 print(f"Dimension {dim}: Score = {data['score']}, Average = {data['average']:.2f}")


    #         elif 'motivation assessment' in test_title:
    #             # Motivation assessment logic (uses category)
    #             for question_key, answer_obj in submitted_answers.items():
    #                 question = question_dict.get(question_key)
    #                 if not question:
    #                     continue

    #                 answer_text = answer_obj.get('text')
    #                 category_value = answer_obj.get('category')

    #                 print(f"✅ Question: {question.text}, Answer: {answer_text}, Submitted Category: {category_value}")

    #                 # Validate category
    #                 valid_categories = question.answers.values_list('category', flat=True)
    #                 if category_value not in valid_categories:
    #                     print(f"❌ Invalid category '{category_value}' for question {question.id}")
    #                     continue

    #                 # Count category
    #                 category_counts[category_value] = category_counts.get(category_value, 0) + 1

    #         elif 'career intrest inventory' in test_title:
    #             # Personality assessment logic (uses score + dimension)
                
    #             for question_key, answer_obj in submitted_answers.items():
    #                 question = question_dict.get(question_key)
    #                 if not question:
    #                     continue

    #                 dimension = question.question_dimension
    #                 print("dimension", answer_obj)

    #                 if dimension not in result_data:
    #                     result_data[dimension] = {
    #                         'score': 0,
    #                         'count': 0
    #                     }
                    
    #                 # Safely get score
    #                 if isinstance(answer_obj, dict):
    #                     score = answer_obj.get('score', 0)
    #                 else:
    #                     score = answer_obj

    #                 result_data[dimension]['score'] += score
    #                 result_data[dimension]['count'] += 1
            
    #         elif 'aptitude assessment' in test_title:
    #             print("🧠 Processing Aptitude Test")
    #             section_sessions = session.section_sessions.all()
                
    #             if not section_sessions.exists():
    #                 return Response(
    #                     {"detail": "No section sessions found for this test."},
    #                     status=status.HTTP_400_BAD_REQUEST
    #                 )

    #             total_score = 0  # ✅ Initialize before accumulation
    #             for section_session in section_sessions:
    #                 section_name = section_session.section.title
                    
    #                 # Get responses for this section session
    #                 section_response = UserResponse.objects.filter(
    #                     session=session,
    #                     session_section=section_session
    #                 ).first()
                    
    #                 if not section_response:
    #                     print(f"No responses found for section: {section_name}")
    #                     result_data[section_name] = 0
    #                     continue

    #                 section_answers = section_response.selected_answer.get('submitted_answers', {})
    #                 correct_count = 0
    #                 total = 0

    #                 for answer_obj in section_answers.values():
    #                     if not isinstance(answer_obj, dict):
    #                         continue

    #                     correct_answer = answer_obj.get('correct_answer')
    #                     selected_answer = answer_obj.get('selected_answer')

    #                     if correct_answer and selected_answer and correct_answer.strip().lower() == selected_answer.strip().lower():
    #                         correct_count += 1
    #                     total += 1

    #                 if total > 0:
    #                     section_score = round((correct_count / total) * 10, 2)  # Scale to 10
    #                 else:
    #                     section_score = 0

    #                 result_data[section_name] = section_score
    #                 total_score += section_score
    #                 print(f"Section {section_name}: Score = {section_score} ({correct_count}/{total})")

    #             # Calculate average score across all sections
    #             if section_sessions.count() > 0:
    #                 total_score = total_score / section_sessions.count()

    #         else:
    #             # Handle other test types...
    #             return Response(
    #                 {"detail": "Unknown test type."},
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )

    #         # Create or update test result
    #         try:
    #             result = TestResult.objects.get(session=session)
    #             result.result_data = result_data
    #             result.score = total_score
    #             result.category_counts = category_counts
    #             result.feedback = f"Thank you for completing {test_title}. Your results have been processed."
    #             result.save()
    #         except TestResult.DoesNotExist:
    #             result = TestResult.objects.create(
    #                 session=session,
    #                 result_data=result_data,
    #                 score=total_score,
    #                 category_counts=category_counts,
    #                 feedback=f"Thank you for completing {test_title}. Your results have been processed."
    #             )

    #         serializer = TestResultSerializer(result, context={'request': request})
    #         return Response(serializer.data)

    #     except Exception as e:
    #         print(f"Error in submit: {str(e)}")
    #         return Response(
    #             {"detail": f"An error occurred: {str(e)}"},
    #             status=status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )

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
            user_response = session.responses.last()  # Use last() instead of first()
            if not user_response:
                return Response(
                    {"detail": "No responses found for this session."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Extract submitted answers from the response
            response_data = user_response.selected_answer
            if not response_data or 'submitted_answers' not in response_data:
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

            # Default: session is completed unless aptitude (handled below)
            session_completed = True

            if 'personality assessment' in test_title:
                result_data, total_score = self._process_personality_test(submitted_answers, session)
            elif 'motivation assessment' in test_title:
                result_data, category_counts = self._process_motivation_test(submitted_answers, session)
            elif 'career intrest inventory' in test_title or str(session.test.id) == '3':
                result_data = self._process_career_test(submitted_answers, session)
            elif 'aptitude assessment' in test_title:
                result_data, total_score, completed_count = self._process_aptitude_test(session)
                # Mark all section_sessions as completed if not already
                for section_session in session.section_sessions.all():
                    if not section_session.is_completed:
                        section_session.is_completed = True
                        section_session.end_time = timezone.now()
                        section_session.save()
                # Mark session as completed only if all sections are completed
                if completed_count == session.section_sessions.count() and completed_count > 0:
                    session_completed = True
                else:
                    session_completed = False
            else:
                return Response(
                    {"detail": "Unknown test type."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Mark session as completed or not
            session.is_completed = session_completed
            session.end_time = timezone.now() if session_completed else None
            session.save()


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
        
        for question_key, answer_obj in submitted_answers.items():
            question = session.test.questions.filter(order=int(question_key.split('_')[1])).first()
            if not question:
                continue

            dimension = question.question_dimension
            pattern = question.parttern
            
            if isinstance(answer_obj, dict):
                raw_score = answer_obj.get('score', 0)
            else:
                raw_score = answer_obj

            score = 6 - raw_score if pattern == 'Reverse' else raw_score
            
            if dimension not in result_data:
                result_data[dimension] = {'score': 0, 'count': 0}
                
            result_data[dimension]['score'] += score
            result_data[dimension]['count'] += 1
            total_score += score

        # Calculate averages
        for dim in result_data:
            count = result_data[dim]['count']
            if count > 0:
                result_data[dim]['average'] = result_data[dim]['score'] / count
                
        return result_data, total_score

    def _process_motivation_test(self, submitted_answers, session):
        category_counts = {}
        result_data = {}
        
        for question_key, answer_obj in submitted_answers.items():
            if isinstance(answer_obj, dict):
                category = answer_obj.get('category')
                if category:
                    category_counts[category] = category_counts.get(category, 0) + 1
                    
        result_data['category_distribution'] = category_counts
        return result_data, category_counts

    def _process_career_test(self, submitted_answers, session):
        # Initialize dimensions dictionary to store scores
        result_data = {}
        
        # Process each answer
        for question_key, answer_obj in submitted_answers.items():
            # Get the question
            question = session.test.questions.filter(order=int(question_key.split('_')[1])).first()
            if not question:
                continue

            # Get dimension from question (R, I, A, S, E, C)
            dimension = question.question_dimension
            print("Ddimension",dimension)
            
            # Get score from answer
            if isinstance(answer_obj, dict):
                score = float(answer_obj.get('score', 0))
            else:
                score = float(answer_obj)

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
        section_sessions = session.section_sessions.all()
        
        completed_count = 0

        for section_session in section_sessions:
            section_name = section_session.section.title

            # Count completed sections
            if section_session.is_completed:
                completed_count += 1

            section_response = UserResponse.objects.filter(
                session=session,
                session_section=section_session
            ).first()
            
            if not section_response:
                result_data[section_name] = 0
                continue
                
            section_answers = section_response.selected_answer.get('submitted_answers', {})
            correct_count = sum(
                1 for ans in section_answers.values()
                if isinstance(ans, dict) and 
                ans.get('correct_answer') and 
                ans.get('selected_answer') and 
                ans.get('correct_answer').strip().lower() == ans.get('selected_answer').strip().lower()
            )
            
            total_questions = len(section_answers)
            section_score = round((correct_count / total_questions) * 10, 2) if total_questions > 0 else 0
            
            result_data[section_name] = section_score
            total_score += section_score
            
        if section_sessions.count() > 0:
            total_score = total_score / section_sessions.count()
            
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
        try:
            # Get required data from request
            submitted_answers = request.data.get('submitted_answers', {})
            section_session_id = request.data.get('section_session')
            
            # Get the session
            session = TestSession.objects.get(id=pk)
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
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')

        # Validate data
        if not username or not email or not password:
            return Response(
                {"detail": "Username, email, and password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            return Response(
                {"username": ["A user with that username already exists."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return Response(
                {"email": ["A user with that email already exists."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # Generate token
        refresh = RefreshToken.for_user(user)

        return Response({
            "user": UserSerializer(user).data,
            "token": str(refresh.access_token),
            "refresh": str(refresh)
        }, status=status.HTTP_201_CREATED)

class CurrentUserView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for current user profile
    """
    serializer_class = UserSerializer
    # permission_classes = [permissions.IsAuthenticated]
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        return self.request.user