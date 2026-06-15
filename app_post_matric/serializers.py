from rest_framework import serializers
from .models import (
    TestCategory, Test, Question, Answer, 
    TestSession, UserResponse, TestResult, Sections, SectionSession
)
# from django.contrib.auth.models import User
from rest_framework.reverse import reverse
from rest_framework.response import Response
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = get_user_model()
        fields = ('id', 'name', 'password', 'email', 'mobile')
        read_only_fields = ['id']
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True},
            'name': {'required': True}
        }

    def create(self, validated_data):
        # Use the custom User model's create_user method
        user = get_user_model().objects.create_user(
            email=validated_data['email'],
            name=validated_data.get('name', ''),
            password=validated_data['password']
        )
        return user

# class UserSerializer(serializers.ModelSerializer):
#     password = serializers.CharField(
#         write_only=True, 
#         required=True, 
#         validators=[validate_password],
#         style={'input_type': 'password'}
#     )
#     password2 = serializers.CharField(
#         write_only=True, 
#         required=False,  # Only required for registration
#         style={'input_type': 'password'}
#     )

#     class Meta:
#         model = User
#         fields = ('id', 'username', 'password', 'password2', 'email', 'first_name', 'last_name')
#         read_only_fields = ['id']
#         extra_kwargs = {
#             'password': {'write_only': True},
#             'email': {'required': True},
#             'first_name': {'required': True},
#             'last_name': {'required': True}
#         }

#     def validate(self, attrs):
#         # Only validate passwords match if password2 is provided (registration)
#         if 'password2' in attrs:
#             if attrs.get('password') != attrs.get('password2'):
#                 raise serializers.ValidationError({"password": "Password fields didn't match."})
#             attrs.pop('password2')  # Remove password2 from attrs
#         return attrs

#     def create(self, validated_data):
#         # Remove password2 if it exists
#         validated_data.pop('password2', None)
        
#         # Create user with proper password hashing
#         user = User.objects.create(
#             username=validated_data['username'],
#             email=validated_data['email'],
#             first_name=validated_data['first_name'],
#             last_name=validated_data['last_name']
#         )
#         user.set_password(validated_data['password'])
#         user.save()
#         return user

#     def update(self, instance, validated_data):
#         # Handle password updates properly
#         password = validated_data.pop('password', None)
        
#         # Update other fields
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
        
#         # Update password if provided
#         if password:
#             instance.set_password(password)
            
#         instance.save()
#         return instance


# class AnswerSerializer(serializers.ModelSerializer):
#     image_url = serializers.SerializerMethodField()
#     question = serializers.PrimaryKeyRelatedField(read_only=True)

#     class Meta:
#         model = Answer
#         fields = ['id', 'question', 'text', 'image', 'image_url', 'is_correct', 'score','category']
#         read_only_fields = ['id']

#     def get_image_url(self, obj):
#         if obj.image:
#             request = self.context.get('request')
#             if request:
#                 return request.build_absolute_uri(obj.image.url)
#             return obj.image.url
#         return None

# class QuestionSerializer(serializers.ModelSerializer):
#     """Serializer for the Question model"""
#     image_url = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Question
#         fields = [
#             'id', 'test', 'section', 'text', 'image', 'image_url', 'order',
#             'question_dimension', 'parttern', 'question_type',
#             'question_level'
#         ]
#         read_only_fields = ['id']

#     def get_image_url(self, obj):
#         """Get the full URL for the image"""
#         if obj.image:
#             request = self.context.get('request')
#             if request:
#                 return request.build_absolute_uri(obj.image.url)
#             return obj.image.url
#         return None

#     def validate(self, data):
#         """
#         Check that if section is provided, it belongs to the same test
#         """
#         if data.get('section') and data.get('test'):
#             if data['section'].test != data['test']:
#                 raise serializers.ValidationError(
#                     "The section must belong to the specified test"
#                 )
#         return data


class QuestionSerializer(serializers.ModelSerializer):
    """Serializer for the Question model"""
    image_url = serializers.SerializerMethodField()
    answers = serializers.SerializerMethodField()  # Add this to include answers
    
    class Meta:
        model = Question
        fields = [
            'id', 'test', 'section', 'text', 'image', 'image_url', 'order',
            'question_dimension', 'parttern', 'question_type',
            'question_level', 'answers'  # Add answers to fields
        ]
        read_only_fields = ['id']

    def get_image_url(self, obj):
        """Get the full URL for the image"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

    def get_answers(self, obj):
        """Get serialized answers for this question"""
        answers = obj.answers.all()
        return AnswerSerializer(answers, many=True, context=self.context).data

class AnswerSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Answer
        fields = ['id', 'question', 'text', 'image', 'image_url', 'is_correct', 'score', 'category']
        read_only_fields = ['id']

    def get_image_url(self, obj):
        """Get the full URL for the image"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

class SectionsSerializer(serializers.ModelSerializer):
    """Serializer for the Sections model"""
    class Meta:
        model = Sections
        fields = ['id', 'test', 'title', 'description', 'order', 'time_limit']

class SectionSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SectionSession
        fields = ['id', 'session', 'section', 'start_time', 'end_time', 'is_completed']
        read_only_fields = ['start_time', 'end_time', 'is_completed']

class TestSerializer(serializers.ModelSerializer):
    questions_count = serializers.SerializerMethodField()
    display_title = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = ['id', 'category', 'title', 'display_title', 'description', 'time_limit', 'is_active', 'questions_count']
        read_only_fields = ['id']

    def get_questions_count(self, obj):
        return obj.questions.count()

    def get_display_title(self, obj):
        from .test_display_labels import test_display_title
        return test_display_title(obj.title)


class TestDetailSerializer(TestSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Test
        fields = ['id', 'category', 'title', 'display_title', 'description', 'time_limit', 'is_active', 'questions_count', 'questions']
        read_only_fields = ['id']


class TestCategorySerializer(serializers.ModelSerializer):
    tests_count = serializers.SerializerMethodField()

    class Meta:
        model = TestCategory
        fields = ['id', 'name', 'description', 'tests_count']
        read_only_fields = ['id']

    def get_tests_count(self, obj):
        return obj.tests.count()


class TestCategoryDetailSerializer(TestCategorySerializer):
    tests = TestSerializer(many=True, read_only=True)

    class Meta:
        model = TestCategory
        fields = ['id', 'name', 'description', 'tests_count', 'tests']
        read_only_fields = ['id']


class UserResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserResponse
        fields = [
            'id', 'session', 'session_section', 'test', 'selected_answer', 
            'attempt_number', 'created_at', 'updated_at'
        ]

    def create(self, validated_data):
        """Override create to handle both single and multi-section tests"""
        session = validated_data.get('session')
        session_section = validated_data.get('session_section')
        test = validated_data.get('test', session.test if session else None)
        
        # Get or create the response
        response, created = UserResponse.objects.get_or_create(
            session=session,
            session_section=session_section,
            test=test,
            attempt_number=session.attempt_count if session else 1,
            defaults={'selected_answer': validated_data.get('selected_answer', {})}
        )

        if not created:
            # Update existing response
            response.selected_answer = validated_data.get('selected_answer', {})
            response.save()

        return response
    

    # def create(self, request, *args, **kwargs):
    #     session_id = request.data.get('session')
    #     section_session_id = request.data.get('session_section')
    #     submitted_answers = request.data.get('submitted_answers', {})

    #     if not session_id:
    #         return Response({"error": "Session ID is required"}, status=400)

    #     try:
    #         session = TestSession.objects.get(id=session_id)
    #     except TestSession.DoesNotExist:
    #         return Response({"error": "Session not found"}, status=404)

    #     test = session.test

    #     # Conditionally validate session_section
    #     needs_section_session = test.id == 4 or test.title.strip().lower() == "aptitude assessment"
    #     session_section = None

    #     if needs_section_session:
    #         if not section_session_id:
    #             return Response({"error": "Session section ID is required for this test."}, status=400)
    #         try:
    #             session_section = SectionSession.objects.get(id=section_session_id)
    #         except SectionSession.DoesNotExist:
    #             return Response({"error": "Section session not found"}, status=404)

    #     response, created = UserResponse.objects.get_or_create(
    #         session=session,
    #         session_section=session_section,  # Can be None if not required
    #         test=test,
    #         attempt_number=session.attempt_count,
    #         defaults={'selected_answer': {'submitted_answers': submitted_answers}}
    #     )

    #     if not created:
    #         response.selected_answer = {'submitted_answers': submitted_answers}
    #         response.save()

    #     serializer = self.get_serializer(response)
    #     return Response(serializer.data, status=201 if created else 200)
    
# Response serializer for test results
class ResponseDetailSerializer(serializers.ModelSerializer):
    answers_summary = serializers.SerializerMethodField()

    class Meta:
        model = UserResponse
        fields = ['id', 'session', 'selected_answer', 'answers_summary']

    def get_answers_summary(self, obj):
        """Return a summary of the answers in the JSON data"""
        if not obj.selected_answer:
            return {

                'total_questions': 0,
                'answered_questions': 0
            }

        submitted_answers = obj.selected_answer.get('submitted_answers', {})
        return {
            'total_questions': len(submitted_answers),
            'answered_questions': sum(1 for value in submitted_answers.values() if value is not None),
            # 'answers': submitted_answers
        }
    
class TestResultSerializer(serializers.ModelSerializer):
    test_title = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    completed_at = serializers.SerializerMethodField()
    duration_minutes = serializers.SerializerMethodField()
    responses = serializers.SerializerMethodField()
    analysis = serializers.SerializerMethodField()
    category_counts = serializers.JSONField(required=False)  # New field for test2

    class Meta:
        model = TestResult
        fields = ['id', 'session', 'score', 'grade', 'feedback', 'result_data', 
                 'test_title', 'category_name', 'completed_at', 'duration_minutes', 
                 'responses', 'analysis', 'category_counts']
        read_only_fields = ['id']

    def get_test_title(self, obj):
        from .test_display_labels import test_display_title
        raw = obj.session.test.title if obj.session and obj.session.test else ''
        return test_display_title(raw)

    def get_category_name(self, obj):
        if obj.session and obj.session.test and obj.session.test.category:
            return obj.session.test.category.name
        return ''

    def get_completed_at(self, obj):
        return obj.session.end_time if obj.session and obj.session.end_time else obj.created_at

    def get_duration_minutes(self, obj):
        if obj.session and obj.session.start_time and obj.session.end_time:
            duration = obj.session.end_time - obj.session.start_time
            return round(duration.total_seconds() / 60)
        return 0

    def get_responses(self, obj):
        if not obj.session:
            return []

        user_responses = obj.session.responses.all()
        return ResponseDetailSerializer(user_responses, many=True, context=self.context).data

    def get_analysis(self, obj):
        if obj.feedback:
            return obj.feedback

        if obj.result_data and isinstance(obj.result_data, dict):
            analysis = "Test Analysis:\n"

            for key, data in obj.result_data.items():
                # If data is a dictionary with 'average', it's personality/career
                if isinstance(data, dict) and 'average' in data:
                    analysis += f"- {key.replace('_', ' ').title()}: {data['average']:.2f}\n"
                # If it's a float/int, assume it's a subsection score (aptitude test)
                elif isinstance(data, (int, float)):
                    analysis += f"- {key.replace('_', ' ').title()} Score: {data:.2f}\n"

            return analysis

        return "No detailed analysis available for this test."

class TestSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestSession
        fields = [
            'id', 'user', 'test', 'start_time', 'end_time',
            'is_completed', 'attempt_count'
        ]

    def create(self, validated_data):
        # Automatically set the user to the current user
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class TestSessionDetailSerializer(TestSessionSerializer):
    responses = UserResponseSerializer(many=True, read_only=True)
    result = TestResultSerializer(read_only=True)
    test = TestSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    section_sessions = SectionSessionSerializer(many=True, read_only=True)  # Add this line

    class Meta:
        model = TestSession
        fields = ['id', 'user', 'test', 'start_time', 'end_time', 'is_completed', 
                'responses', 'result', 'section_sessions', 'attempt_count']  # Add section_sessions and attempt_count
        read_only_fields = ['id', 'user', 'start_time']