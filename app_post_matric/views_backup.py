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
    TestSession, UserResponse, TestResult
)
from .serializers import (
    TestCategorySerializer, TestCategoryDetailSerializer,
    TestSerializer, TestDetailSerializer,
    QuestionSerializer, AnswerSerializer,
    TestSessionSerializer, TestSessionDetailSerializer,
    UserResponseSerializer, TestResultSerializer,
    UserSerializer, ResponseDetailSerializer
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
        """Start a new test session"""
        test = self.get_object()

        # Check if user has an incomplete session for this test
        existing_session = TestSession.objects.filter(
            user=request.user,
            test=test,
            is_completed=False
        ).first()

        if existing_session:
            serializer = TestSessionDetailSerializer(existing_session, context={'request': request})
            return Response(serializer.data)

        # Create a new session
        session = TestSession.objects.create(
            user=request.user,
            test=test,
            start_time=timezone.now()
        )

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
        question_dimension = self.request.query_params.get('dimension', None)
        question_level = self.request.query_params.get('level', None)

        if test_id:
            queryset = queryset.filter(test_id=test_id)
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
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TestSession.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ['retrieve', 'list']:
            return TestSessionDetailSerializer
        return TestSessionSerializer

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit and complete a test session"""
        session = self.get_object()

        if session.is_completed:
            return Response(
                {"detail": "This test session is already completed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark session as completed
        session.is_completed = True
        session.end_time = timezone.now()
        session.save()

        # Get user responses
        user_response = session.responses.first()
        if not user_response or not user_response.selected_answer:
            return Response(
                {"detail": "No responses found for this session."},
                status=status.HTTP_400_BAD_REQUEST
            )

        submitted_answers = user_response.selected_answer.get('submitted_answers', {})

        # Calculate results based on test type
        test_type = session.test.category.name.lower()

        if test_type == 'aptitude':
            # For aptitude tests, calculate score based on correct answers
            total_questions = len(submitted_answers)
            correct_answers = 0

            # Get all questions for this test
            questions = session.test.questions.all()
            question_dict = {f"Question_{q.order}": q for q in questions}

            for question_key, answer_value in submitted_answers.items():
                # Find the corresponding question
                question = question_dict.get(question_key)
                if not question:
                    continue

                # Find the correct answer for this question
                correct_answer = question.answers.filter(is_correct=True).first()
                if correct_answer:
                    if question.parttern == 'Straight' and correct_answer.score == answer_value:
                        correct_answers += 1
                    elif question.parttern == 'Reverse' and correct_answer.score == -answer_value:
                        correct_answers += 1

            score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0

            # Determine grade
            if score >= 90:
                grade = 'A'
            elif score >= 80:
                grade = 'B'
            elif score >= 70:
                grade = 'C'
            elif score >= 60:
                grade = 'D'
            else:
                grade = 'F'

            # Create result
            result = TestResult.objects.create(
                session=session,
                score=score,
                grade=grade,
                feedback=f"You answered {correct_answers} out of {total_questions} questions correctly."
            )

        else:
            # For personality, motivation, career tests, aggregate scores by dimension
            result_data = {}

            # Get all questions for this test
            questions = session.test.questions.all()
            question_dict = {f"Question_{q.order}": q for q in questions}

            for question_key, answer_value in submitted_answers.items():
                # Find the corresponding question
                question = question_dict.get(question_key)
                if not question:
                    continue

                dimension = question.question_dimension

                if dimension not in result_data:
                    result_data[dimension] = {
                        'score': 0,
                        'count': 0
                    }

                result_data[dimension]['score'] += answer_value
                result_data[dimension]['count'] += 1

            # Calculate averages
            for dim in result_data:
                if result_data[dim]['count'] > 0:
                    result_data[dim]['average'] = result_data[dim]['score'] / result_data[dim]['count']
                else:
                    result_data[dim]['average'] = 0

            # Create result
            result = TestResult.objects.create(
                session=session,
                result_data=result_data,
                feedback="Thank you for completing the assessment. Your results have been processed."
            )

        serializer = TestResultSerializer(result, context={'request': request})
        return Response(serializer.data)


class UserResponseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling user responses
    """
    queryset = UserResponse.objects.all()
    serializer_class = UserResponseSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new user response or update if one exists
        """
        # Extract data from request
        session_id = request.data.get('session')
        submitted_answers = request.data.get('submitted_answers', {})

        # Validate required fields
        if not session_id:
            return Response(
                {"error": "Session ID is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get session object
            session = TestSession.objects.get(id=session_id)

            # Check if a response already exists for this session
            existing_response = UserResponse.objects.filter(
                session_id=session_id
            ).first()
            if existing_response:
                # Update existing response
                existing_response.selected_answer = submitted_answers
                existing_response.save()
                serializer = self.get_serializer(existing_response)
                return Response(serializer.data)
            else:
                # Create new response
                new_response = UserResponse.objects.create(
                    session=session,
                    selected_answer=submitted_answers
                )
                serializer = self.get_serializer(new_response)
                return Response(serializer.data, status=status.HTTP_201_CREATED)

        except TestSession.DoesNotExist:
            return Response(
                {"error": f"Session with ID {session_id} does not exist"}, 
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
    permission_classes = [permissions.IsAuthenticated]

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
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user