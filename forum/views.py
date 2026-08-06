from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response as DRFResponse
from rest_framework.views import APIView
from django.shortcuts import render
from django.template.loader import get_template
from django.http import HttpResponse
from django.utils import timezone
from django.conf import settings
from datetime import date
from forum.models import Query, Response, Category, Country, PerformanceMetrics, AIFeature, AICapability
from forum.serializers import (
    QuerySerializer, ResponseSerializer, CategorySerializer,
    CountrySerializer, QueryWithResponseSerializer, AIFeatureSerializer, AICapabilitySerializer
)
from forum.services.ai_service import (
    generate_ai_response,
    extract_entities,
    is_non_answer_response,
)
import time
import re


def _paywall_html(payload: dict) -> str:
    pay = payload or {}
    cta = pay.get("cta_url") or "/ai-tokens/"
    label = pay.get("cta_label") or "Recharge AI tokens"
    headline = pay.get("headline") or pay.get("message") or "AI token limit reached"
    body = pay.get("body") or pay.get("detail") or ""
    return (
        f"<h4>{headline}</h4>"
        f"<p>{body}</p>"
        f"<p><a href=\"{cta}\">{label}</a></p>"
    )


def _quota_exceeded_payload(exc, forum_user=None, request=None) -> dict:
    """Build API payload for quota paywall (HTTP 200 so browsers/JS always parse JSON)."""
    pay = getattr(exc, "payload", None) or {}
    forum_quota = None
    try:
        from core.llm_quota import forum_question_limit_status

        forum_quota = forum_question_limit_status(forum_user, request=request)
    except Exception:
        pass
    return {
        "quota_exceeded": True,
        "error": pay.get("headline") or pay.get("message") or "AI token limit reached",
        "detail": pay.get("body") or pay.get("detail") or "",
        "paywall": pay,
        "forum_quota": forum_quota,
        "response": {"response_text": _paywall_html(pay)},
    }


def _can_moderate_forum(user) -> bool:
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
    )


def _update_performance_metrics(ai_generated=True, response_time_ms=0, cost=0.0):
    """Update daily performance metrics"""
    today = date.today()
    metrics, created = PerformanceMetrics.objects.get_or_create(date=today)
    
    metrics.total_queries += 1
    if ai_generated:
        metrics.ai_generated += 1
        metrics.total_cost_usd += cost
        if response_time_ms > 0:
            # Update average response time (weighted average)
            if metrics.average_response_time_ms == 0:
                metrics.average_response_time_ms = response_time_ms
            else:
                metrics.average_response_time_ms = (
                    (metrics.average_response_time_ms * (metrics.ai_generated - 1) + response_time_ms) 
                    / metrics.ai_generated
                )
    else:
        metrics.database_cached += 1
    
    metrics.save()


def index(request):
    """Render the main forum page using Django templates"""
    from django.template import engines
    django_engine = engines['django']
    
    context = {}
    
    # Get user profile data if user is logged in
    if request.user.is_authenticated:
        user = request.user
        # Get user name - custom User model uses 'name' field
        user_name = None
        try:
            # Try name field first (custom User model uses 'name')
            if hasattr(user, 'name') and user.name:
                user_name = user.name.strip()
        except Exception:
            pass
        
        # Fallback to username property (returns email without @) or email
        if not user_name:
            try:
                # Custom User model has username property that returns email without @
                if hasattr(user, 'username'):
                    user_name = str(user.username)
                elif hasattr(user, 'email') and user.email:
                    user_name = user.email.split('@')[0]
                else:
                    user_name = 'User'
            except Exception:
                user_name = 'User'
        
        user_data = {
            'name': user_name,
            'grade': None,
            'school': None,
            'age': None,
            'stream': None,
            'psychometric_score': None,
            'career_readiness': 0,
            'top_matches': []
        }
        
        try:
            # Get user profile
            if hasattr(user, 'user_profile') and user.user_profile:
                profile = user.user_profile
                user_data['grade'] = profile.grade
                user_data['school'] = getattr(profile, 'schoolname', None) or getattr(profile, 'school_name', None)
                
                # Calculate age from date of birth if available
                if hasattr(profile, 'date_of_birth') and profile.date_of_birth:
                    from datetime import date
                    today = date.today()
                    age = today.year - profile.date_of_birth.year - ((today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day))
                    user_data['age'] = age
                
                # Get stream if available
                if hasattr(profile, 'stream'):
                    user_data['stream'] = str(profile.stream) if profile.stream else None
        except Exception:
            pass
        
        # Check StudentManagement for additional data (Age, Stream, Grade)
        try:
            from institute.models import StudentManagement
            student_management = StudentManagement.objects.filter(student=user).select_related('class_and_section').first()
            if student_management:
                # Get grade from class_and_section
                if not user_data['grade'] and student_management.class_and_section:
                    class_name = student_management.class_and_section.class_and_section
                    if class_name:
                        import re
                        numbers = re.findall(r'\d+', class_name)
                        if numbers:
                            user_data['grade'] = int(numbers[0])
                
                # Get stream from class_and_section
                if not user_data['stream'] and student_management.class_and_section:
                    stream = student_management.class_and_section.stream
                    if stream:
                        user_data['stream'] = stream.strip()
        except Exception:
            pass
        
        # Get psychometric score
        try:
            from app.models import Results
            test1_result = Results.objects.filter(user=user, test_paper='test1').first()
            if test1_result and test1_result.results:
                # Calculate average score from results
                scores = [v for v in test1_result.results.values() if isinstance(v, (int, float))]
                if scores:
                    user_data['psychometric_score'] = int(sum(scores) / len(scores))
        except Exception:
            pass
        
        # Get career readiness and top matches from UserProgressView logic
        try:
            from app_post_matric.models import CareerShortlist, TestSession
            from user_analytics.models import UserActivity
            from core.models import UserProfile as CoreUserProfile
            
            # Get career readiness
            careers_explored = CareerShortlist.objects.filter(user=user).count()
            test_complete = TestSession.objects.filter(user=user, is_completed=True).exists()
            profile_complete = 0
            
            if hasattr(user, 'user_profile') and user.user_profile:
                profile = user.user_profile
                if profile.grade:
                    profile_complete += 25
                if hasattr(profile, 'hobbies') and profile.hobbies.exists():
                    profile_complete += 25
                if hasattr(profile, 'subject') and profile.subject.exists():
                    profile_complete += 25
                if hasattr(profile, 'figure_out') and profile.figure_out.exists():
                    profile_complete += 25
            
            test_complete_score = 30 if test_complete else 0
            career_exploration = min(careers_explored * 2, 30)
            skills_score = min(careers_explored * 5, 20)
            
            user_data['career_readiness'] = min(profile_complete + test_complete_score + career_exploration + skills_score, 100)
            
            # Get top career matches from CareerShortlist
            top_careers = CareerShortlist.objects.filter(user=user).select_related('career').order_by('-created')[:3]
            top_matches_list = []
            for career_shortlist in top_careers:
                if hasattr(career_shortlist, 'career') and career_shortlist.career:
                    career_name = getattr(career_shortlist.career, 'name', None) or str(career_shortlist.career)
                    if career_name:
                        top_matches_list.append(career_name)
            
            # If no matches from CareerShortlist, try to get from test results or recommendations
            if not top_matches_list:
                try:
                    # Try to get from psychometric test results
                    from app.models import Results
                    test_result = Results.objects.filter(user=user, test_paper='test2').first()
                    if test_result and hasattr(test_result, 'scores') and test_result.scores:
                        # Get top interest categories
                        sorted_interests = sorted(test_result.scores.items(), key=lambda x: x[1], reverse=True)[:2]
                        top_matches_list = [interest[0].replace('_', ' ').title() for interest in sorted_interests]
                except Exception:
                    pass
            
            user_data['top_matches'] = top_matches_list
        except Exception:
            pass
        
        context['user_data'] = user_data
        
        # Debug logging when DEBUG is True
        if getattr(settings, 'DEBUG', False):
            print("\n" + "="*80)
            print("🔍 FORUM USER DATA DEBUG INFO")
            print("="*80)
            print(f"User: {user.email if hasattr(user, 'email') else 'N/A'}")
            print(f"User ID: {user.id}")
            print(f"Name: {user_data.get('name', 'N/A')}")
            print(f"Grade: {user_data.get('grade', 'N/A')}")
            print(f"School: {user_data.get('school', 'N/A')}")
            print(f"Age: {user_data.get('age', 'N/A')}")
            print(f"Stream: {user_data.get('stream', 'N/A')}")
            print(f"Psychometric Score: {user_data.get('psychometric_score', 'N/A')}")
            print(f"Career Readiness: {user_data.get('career_readiness', 0)}%")
            print(f"Top Matches: {', '.join(user_data.get('top_matches', [])) if user_data.get('top_matches') else 'N/A'}")
            print("="*80 + "\n")
    else:
        context['user_data'] = None

    # AI question post limit (weekly + token estimate) for profile card
    try:
        from core.llm_quota import forum_question_limit_status
        context['forum_quota'] = forum_question_limit_status(
            request.user if request.user.is_authenticated else None,
            request=request,
        )
    except Exception:
        context['forum_quota'] = {
            'is_authenticated': request.user.is_authenticated,
            'unlimited': False,
            'weekly_limit': 5,
            'posted_this_week': 0,
            'remaining_this_week': 5,
            'approx_questions_left': 0,
            'balance_tokens': 0,
            'balance_display': '0',
            'tone': 'ok',
            'meter_percent': 0,
            'label': 'AI guidance unavailable',
            'detail': '',
            'weekly_headline': 'Limit unavailable',
            'weekly_sub': 'Please refresh the page',
            'answers_headline': '—',
            'answers_sub': '',
        }

    # Student display ID for profile card
    display_id = None
    if request.user.is_authenticated:
        try:
            display_id = (
                getattr(request.user, 'get_display_student_id', lambda: None)()
                or getattr(request.user, 'get_student_display_id', lambda: None)()
            )
        except Exception:
            display_id = None
        if not display_id:
            display_id = f"UID{str(request.user.id).zfill(6)}"
    context['display_student_id'] = display_id

    try:
        features = AIFeature.objects.filter(is_active=True).order_by('order', 'name')
        
        # Dynamically set Psychometric Assessment Link based on user's class
        user_class = None
        if request.user.is_authenticated:
            try:
                # Check UserProfile.grade first
                if hasattr(request.user, 'user_profile') and request.user.user_profile:
                    profile = request.user.user_profile
                    if profile.grade:
                        try:
                            user_class = int(profile.grade)
                        except (ValueError, TypeError):
                            import re
                            numbers = re.findall(r'\d+', str(profile.grade))
                            if numbers:
                                user_class = int(numbers[0])
                
                # If no grade from UserProfile, check StudentManagement
                if user_class is None:
                    from institute.models import StudentManagement
                    student_management = StudentManagement.objects.filter(student=request.user).first()
                    if student_management and student_management.class_and_section:
                        class_name = student_management.class_and_section.class_and_section
                        if class_name:
                            import re
                            numbers = re.findall(r'\d+', class_name)
                            if numbers:
                                user_class = int(numbers[0])
            except Exception:
                pass
        
        # Prepare features data for template
        features_data = []
        for feature in features:
            feature_dict = {
                'id': feature.id,
                'name': feature.name,
                'icon': feature.icon,
                'description': feature.description,
                'link_url': feature.link_url,
                'order': feature.order
            }
            
            # Update Psychometric Assessment Link based on class
            if feature.name == 'Psychometric Assessment Link':
                if user_class is not None and user_class <= 10:
                    feature_dict['link_url'] = '/psychometrictest/stream-sorter/'
                else:
                    feature_dict['link_url'] = '/psychometrictest/career-direction/'
            
            features_data.append(feature_dict)
        
        context['ai_features'] = features_data
    except Exception as e:
        if getattr(settings, 'DEBUG', False):
            print(f"[DEBUG] Error loading AI Features: {e}")
        context['ai_features'] = []
    
    # Load AI Capabilities server-side for immediate display
    try:
        capabilities = AICapability.objects.filter(is_active=True).order_by('order', 'name')
        capabilities_data = [{
            'id': c.id,
            'name': c.name,
            'icon': c.icon,
            'description': c.description,
            'link_url': c.link_url,
            'order': c.order
        } for c in capabilities]
        context['ai_capabilities'] = capabilities_data
    except Exception as e:
        if getattr(settings, 'DEBUG', False):
            print(f"[DEBUG] Error loading AI Capabilities: {e}")
        context['ai_capabilities'] = []

    from django.urls import reverse
    context['logout_url'] = reverse('users:logout')
    context['dashboard_url'] = reverse('users:userdashboard')
    context['can_moderate_forum'] = _can_moderate_forum(request.user)
    try:
        context['forum_admin_url'] = reverse('admin:forum_query_changelist')
    except Exception:
        context['forum_admin_url'] = '/admin/forum/query/'

    try:
        jinja2_engine = engines['jinja2']
        popup_tpl = jinja2_engine.get_template('template20/includes/student_login_popup.html')
        context['login_popup_html'] = popup_tpl.render({}, request)
    except Exception:
        context['login_popup_html'] = ''
    
    template = django_engine.get_template('forum/index.html')
    return HttpResponse(template.render(context, request))


class QueryViewSet(viewsets.ModelViewSet):
    """API endpoint for queries"""
    queryset = Query.objects.all()
    serializer_class = QuerySerializer
    permission_classes = [permissions.AllowAny]  # Allow anonymous users to ask questions
    
    def create(self, request, *args, **kwargs):
        """Create a new query and generate AI response"""
        # Handle both 'question' and 'question_text' for flexibility
        question = request.data.get('question') or request.data.get('question_text', '')
        if not question:
            return DRFResponse(
                {'error': 'Question is required. Use "question" or "question_text" field.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate question length
        if len(question) < 10:
            return DRFResponse(
                {'error': 'Please provide a more detailed question (at least 10 characters).'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(question) > 1000:
            return DRFResponse(
                {'error': 'Question is too long. Please limit to 1000 characters.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Extract entities
        country, category = extract_entities(question)
        
        # Track start time for performance metrics
        start_time = time.time()
        
        # Check if database caching is enabled
        use_db_cache = getattr(settings, 'USE_DATABASE_CACHE', True)
        
        # Check if similar query already exists in database (before creating new one)
        # Only if database caching is enabled
        if use_db_cache:
            from forum.services.ai_service import find_similar_query
            similarity_threshold = getattr(settings, 'SEMANTIC_SIMILARITY_THRESHOLD', 0.85)
            existing_response, _ = find_similar_query(question, similarity_threshold=similarity_threshold)
            
            if existing_response and not is_non_answer_response(existing_response):
                # Similar query found - create query record but reuse existing response
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Log query to console
                print("\n" + "="*80)
                print("📝 NEW QUERY RECEIVED (CACHED)")
                print("="*80)
                print(f"Question: {question}")
                print(f"Category: {category.name if category else 'None'}")
                print(f"Country: {country.name if country else 'None'}")
                print("-"*80)
                
                query = Query.objects.create(
                    question_text=question,
                    category=category,
                    country_context=country.name if country else None,
                    status='completed',
                    response_time_ms=response_time_ms,
                    source='database'
                )
                
                # Log cached response to console
                print("\n💾 CACHED RESPONSE FOUND")
                print("-"*80)
                print(f"Query ID: {query.id}")
                print(f"Response Length: {len(existing_response)} characters")
                print(f"Response Time: {response_time_ms}ms (from cache)")
                print(f"Cost: $0.00 (cached)")
                print(f"Source: Database Cache")
                print("\nResponse Preview (first 200 chars):")
                print(existing_response[:200] + "..." if len(existing_response) > 200 else existing_response)
                print("="*80 + "\n")
                
                # Create response using existing response text
                response_obj = Response.objects.create(
                    query=query,
                    response_text=existing_response,
                    confidence_score=0.95,
                    sources=[]
                )
                
                query.mark_completed()

                # Reward + track weekly question post limit for authenticated users.
                forum_user = request.user if getattr(request.user, "is_authenticated", False) else None
                if forum_user:
                    try:
                        from core.llm_quota import (
                            credit_forum_relevant_question,
                            forum_question_limit_status,
                            record_forum_question_post,
                        )
                        credit_forum_relevant_question(
                            forum_user,
                            query_id=query.id,
                            question_text=question,
                        )
                        record_forum_question_post(forum_user, query_id=query.id)
                    except Exception:
                        pass
                
                # Update performance metrics
                _update_performance_metrics(ai_generated=False)
                
                serializer = QueryWithResponseSerializer(query)
                payload = serializer.data
                payload['tokens_charged'] = False  # Cached answer — no AI tokens used
                try:
                    from core.llm_quota import forum_question_limit_status
                    payload['forum_quota'] = forum_question_limit_status(forum_user, request=request)
                except Exception:
                    pass
                return DRFResponse(payload, status=status.HTTP_201_CREATED)
        
        # No similar query found (or database cache disabled) - create new query and generate AI response
        query = Query.objects.create(
            question_text=question,
            category=category,
            country_context=country.name if country else None,
            status='processing',
            source='ai'
        )
        
        # Generate AI response (with domain validation and database check)
        try:
            # Log query to console
            print("\n" + "="*80)
            print("📝 NEW QUERY RECEIVED")
            print("="*80)
            print(f"Question: {question}")
            print(f"Category: {category.name if category else 'None'}")
            print(f"Country: {country.name if country else 'None'}")
            print(f"Query ID: {query.id}")
            print("-"*80)
            
            forum_user = request.user if getattr(request.user, "is_authenticated", False) else None
            try:
                ai_response, cost = generate_ai_response(
                    question,
                    country,
                    category,
                    user=forum_user,
                    request=request,
                )
            except Exception as gen_exc:
                from core.llm_quota import LLMQuotaExceeded

                if isinstance(gen_exc, LLMQuotaExceeded):
                    # Quota / paywall: show to the user only — never save as an answered post.
                    query.status = 'failed'
                    query.save(update_fields=['status'])
                    try:
                        query.delete()
                    except Exception:
                        pass
                    return DRFResponse(
                        _quota_exceeded_payload(gen_exc, forum_user, request),
                        status=status.HTTP_200_OK,
                    )
                raise
            
            # Never persist paywall / error text as a completed forum answer
            if is_non_answer_response(ai_response):
                query.status = 'failed'
                query.save(update_fields=['status'])
                try:
                    query.delete()
                except Exception:
                    pass
                # If the model returned paywall-like text, show recharge UI not a generic error
                lower = (ai_response or "").lower()
                if any(
                    m in lower
                    for m in (
                        "sign in to keep using ai",
                        "free guest ai allowance",
                        "ai token limit reached",
                        "free ai boost just ran out",
                        "recharge ai tokens",
                    )
                ):
                    from core.llm_quota import LLMQuotaExceeded, ensure_can_use_llm

                    try:
                        ensure_can_use_llm(forum_user, feature="forum", request=request)
                    except LLMQuotaExceeded as qexc:
                        return DRFResponse(
                            _quota_exceeded_payload(qexc, forum_user, request),
                            status=status.HTTP_200_OK,
                        )
                return DRFResponse(
                    {
                        "error": (
                            "AI could not generate an answer right now. "
                            "No tokens were used — please try again."
                        ),
                        "tokens_charged": False,
                        "response": {"response_text": ai_response or ""},
                    },
                    status=status.HTTP_200_OK,
                )
            
            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Log response to console
            print("\n🤖 AI RESPONSE GENERATED")
            print("-"*80)
            print(f"Response Length: {len(ai_response)} characters")
            print(f"Response Time: {response_time_ms}ms")
            print(f"Cost: ${cost:.6f}")
            print(f"Source: {'AI Generated' if cost > 0 else 'Database Cache'}")
            print("\nResponse Preview (first 200 chars):")
            print(ai_response[:200] + "..." if len(ai_response) > 200 else ai_response)
            print("="*80 + "\n")
            
            # Create response (save to database for future reuse)
            response_obj = Response.objects.create(
                query=query,
                response_text=ai_response,
                confidence_score=0.95,  # Can be calculated based on AI response
                sources=[]
            )
            
            query.response_time_ms = response_time_ms
            query.mark_completed()

            # Only track/reward when we have a real answer. Tokens are debited
            # inside generate_ai_response only after a successful OpenAI call
            # (cost > 0). Cached answers (cost == 0) do not consume tokens.
            ai_tokens_used = cost > 0
            if forum_user:
                try:
                    from core.llm_quota import (
                        credit_forum_relevant_question,
                        record_forum_question_post,
                    )
                    record_forum_question_post(forum_user, query_id=query.id)
                    # Posting reward is fine for both AI and cached real answers
                    credit_forum_relevant_question(
                        forum_user,
                        query_id=query.id,
                        question_text=question,
                    )
                except Exception:
                    pass
            
            # Update performance metrics
            _update_performance_metrics(
                ai_generated=ai_tokens_used,
                response_time_ms=response_time_ms,
                cost=cost,
            )
            
            serializer = QueryWithResponseSerializer(query)
            payload = serializer.data
            payload["tokens_charged"] = ai_tokens_used
            try:
                from core.llm_quota import forum_question_limit_status
                payload['forum_quota'] = forum_question_limit_status(forum_user, request=request)
            except Exception:
                pass
            return DRFResponse(payload, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            query.status = 'failed'
            query.save()
            
            # Import traceback for detailed error logging
            import traceback
            
            # Enhanced error logging to console
            print("\n" + "="*80)
            print("❌ AI RESPONSE GENERATION FAILED")
            print("="*80)
            print(f"Query ID: {query.id}")
            print(f"Question: {question}")
            print(f"Category: {category.name if category else 'None'}")
            print(f"Country: {country.name if country else 'None'}")
            print(f"Error Type: {type(e).__name__}")
            print(f"Error Message: {str(e)}")
            
            # Check for specific error types and provide guidance
            error_str = str(e).lower()
            error_type = type(e).__name__
            
            if 'api key' in error_str or 'authentication' in error_str or 'invalid' in error_str:
                print("\n🔑 API KEY ERROR DETECTED")
                print("Possible causes:")
                print("  - OPENAI_API_KEY is missing or incorrect in .env file")
                print("  - API key has been revoked or expired")
                print("  - API key doesn't have required permissions")
                print("\nTo fix:")
                print("1. Check your .env file for OPENAI_API_KEY")
                print("2. Verify the key is correct at: https://platform.openai.com/api-keys")
                print("3. Ensure the key has access to the model you're using")
                print("4. Restart your Django development server")
            elif 'network' in error_str or 'connection' in error_str or 'timeout' in error_str:
                print("\n🌐 NETWORK ERROR DETECTED")
                print("Possible causes:")
                print("  - Internet connection issue")
                print("  - OpenAI API service is down")
                print("  - Request timeout")
                print("\nTo fix:")
                print("1. Check your internet connection")
                print("2. Verify OpenAI service status")
                print("3. Try again after a few moments")
            elif 'rate limit' in error_str or 'quota' in error_str:
                print("\n⏱️  RATE LIMIT ERROR DETECTED")
                print("Possible causes:")
                print("  - API rate limit exceeded")
                print("  - Monthly quota exhausted")
                print("  - Too many requests in short time")
                print("\nTo fix:")
                print("1. Wait a few minutes before retrying")
                print("2. Check your OpenAI account usage/limits")
                print("3. Consider upgrading your OpenAI plan")
            elif 'model' in error_str or 'invalid model' in error_str:
                print("\n🤖 MODEL ERROR DETECTED")
                print("Possible causes:")
                print("  - Invalid model name in settings")
                print("  - Model not available in your API plan")
                print("  - Model name typo in OPENAI_MODEL setting")
                print("\nTo fix:")
                print("1. Check OPENAI_MODEL in settings.py or .env")
                print("2. Verify model name is correct (e.g., 'gpt-4o-mini')")
                print("3. Ensure model is available in your OpenAI account")
            else:
                print("\n⚠️  UNEXPECTED ERROR")
                print("This is an unexpected error. Full traceback below:")
            
            # Print full traceback when DEBUG is True
            if getattr(settings, 'DEBUG', False):
                print("\n" + "-"*80)
                print("FULL TRACEBACK:")
                print("-"*80)
                print(traceback.format_exc())
                print("-"*80)
            
            print("="*80 + "\n")
            
            # Return user-friendly error message
            user_error_message = "Failed to get response. Please try again."
            if getattr(settings, 'DEBUG', False):
                # In debug mode, include more details
                user_error_message = f"Failed to get response: {str(e)}. Please try again."
            
            return DRFResponse(
                {'error': user_error_message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def response(self, request, pk=None):
        """Get response for a query"""
        query = self.get_object()
        
        try:
            response_obj = query.response
            serializer = ResponseSerializer(response_obj)
            return DRFResponse(serializer.data)
        except Response.DoesNotExist:
            return DRFResponse(
                {'error': 'Response not ready yet'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def hide(self, request, pk=None):
        """Staff: hide post from public forum display."""
        if not _can_moderate_forum(request.user):
            return DRFResponse({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)
        query = self.get_object()
        query.hide(request.user)
        return DRFResponse({'ok': True, 'id': query.id, 'is_hidden': True})

    @action(detail=True, methods=['post'])
    def unhide(self, request, pk=None):
        """Staff: show a previously hidden post again."""
        if not _can_moderate_forum(request.user):
            return DRFResponse({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)
        query = self.get_object()
        query.unhide()
        return DRFResponse({'ok': True, 'id': query.id, 'is_hidden': False})

    @action(detail=True, methods=['post'])
    def moderate(self, request, pk=None):
        """
        Staff: edit question and/or answer text, optionally hide.
        Body: { question_text?, response_text?, is_hidden? }
        """
        if not _can_moderate_forum(request.user):
            return DRFResponse({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)

        query = self.get_object()
        question_text = request.data.get('question_text')
        response_text = request.data.get('response_text')
        is_hidden = request.data.get('is_hidden')
        updated = []

        if question_text is not None:
            text = str(question_text).strip()
            if len(text) < 10:
                return DRFResponse(
                    {'error': 'Question must be at least 10 characters.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            query.question_text = text[:2000]
            query.save(update_fields=['question_text', 'updated_at'])
            updated.append('question_text')

        if is_hidden is not None:
            hide_flag = str(is_hidden).lower() in ('1', 'true', 'yes')
            if hide_flag and not query.is_hidden:
                query.hide(request.user)
            elif not hide_flag and query.is_hidden:
                query.unhide()
            updated.append('is_hidden')

        if response_text is not None:
            text = str(response_text).strip()
            if not text:
                return DRFResponse(
                    {'error': 'Answer cannot be empty.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if is_non_answer_response(text):
                return DRFResponse(
                    {'error': 'That text looks like a paywall/error message, not an answer.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            resp_obj, created = Response.objects.get_or_create(
                query=query,
                defaults={'response_text': text, 'confidence_score': 1.0},
            )
            if not created and resp_obj.response_text != text:
                resp_obj.response_text = text
                resp_obj.save(update_fields=['response_text'])
            if query.status != 'completed':
                query.mark_completed()
            updated.append('response_text')

        # Refresh response text for payload
        answer = ''
        try:
            answer = query.response.response_text
        except Response.DoesNotExist:
            answer = ''

        return DRFResponse(
            {
                'ok': True,
                'id': query.id,
                'updated': updated,
                'question': query.question_text,
                'is_hidden': query.is_hidden,
                'response_text': answer,
            }
        )

    def destroy(self, request, *args, **kwargs):
        """Staff: permanently delete a forum post (+ answer)."""
        if not _can_moderate_forum(request.user):
            return DRFResponse({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)
        query = self.get_object()
        qid = query.id
        query.delete()
        return DRFResponse({'ok': True, 'id': qid, 'deleted': True}, status=status.HTTP_200_OK)


class CategoryListView(APIView):
    """List all categories"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return DRFResponse(serializer.data)


class CountryListView(APIView):
    """List all countries"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        countries = Country.objects.all()
        serializer = CountrySerializer(countries, many=True)
        return DRFResponse(serializer.data)


class StatisticsView(APIView):
    """Get platform statistics - all from database"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        total_queries = Query.objects.filter(status='completed').count()
        
        # Get today's metrics
        today = date.today()
        try:
            today_metrics = PerformanceMetrics.objects.get(date=today)
            accuracy_rate = today_metrics.accuracy_rate if today_metrics.accuracy_rate > 0 else 0.0
            avg_response_time = today_metrics.average_response_time_ms / 1000 if today_metrics.average_response_time_ms > 0 else 0.0
        except PerformanceMetrics.DoesNotExist:
            accuracy_rate = 0.0
            avg_response_time = 0.0
        
        # Count unique countries (for study abroad context)
        countries_covered = Country.objects.count()
        
        # Calculate cache hit rate
        db_cached = Query.objects.filter(source='database', status='completed').count()
        cache_hit_rate = (db_cached / total_queries * 100) if total_queries > 0 else 0
        
        # Format numbers for display
        def format_number(num):
            if num >= 1_000_000:
                return f"{(num / 1_000_000):.1f}M"
            elif num >= 1_000:
                return f"{(num / 1_000):.1f}K"
            return str(num)
        
        # Always use actual database values, no defaults
        total_queries_formatted = format_number(total_queries) if total_queries > 0 else '0'
        
        return DRFResponse({
            'total_queries': total_queries,
            'total_queries_formatted': total_queries_formatted,
            'completed_queries': total_queries,
            'accuracy_rate': round(accuracy_rate, 1) if accuracy_rate > 0 else 0.0,
            'countries_covered': countries_covered,
            'categories': Category.objects.count(),
            'response_time': f'<{avg_response_time:.1f}s' if avg_response_time > 0 else '<1s',
            'cache_hit_rate': round(cache_hit_rate, 1),
            'ai_generated': Query.objects.filter(source='ai', status='completed').count(),
            'database_cached': db_cached
        })


class UserProgressView(APIView):
    """Get user-specific progress statistics from database"""
    permission_classes = [permissions.AllowAny]  # Allow anonymous (will return default values)
    
    def get(self, request):
        if not request.user.is_authenticated:
            # Return default/empty values for anonymous users with is_authenticated flag
            try:
                from core.llm_quota import forum_question_limit_status
                forum_quota = forum_question_limit_status(None, request=request)
            except Exception:
                forum_quota = None
            return DRFResponse({
                'is_authenticated': False,
                'careers_explored': 0,
                'stream_match': 0,
                'skills_identified': 0,
                'universities_viewed': 0,
                'career_readiness': 0,
                'forum_quota': forum_quota,
            })
        
        # Get user's career shortlists (careers explored/bookmarked)
        try:
            from careers.models import CareerShortlist
            careers_explored = CareerShortlist.objects.filter(user=request.user).count()
        except Exception:
            careers_explored = 0
        
        # Get user's unique forum queries (as additional career exploration)
        user_forum_queries = Query.objects.filter(status='completed').count()
        # Combine both metrics
        careers_explored = careers_explored + user_forum_queries
        
        # Calculate stream match based on user profile and career interests
        stream_match = 0
        try:
            if hasattr(request.user, 'user_profile') and request.user.user_profile:
                profile = request.user.user_profile
                # Get user's career interests
                from careers.models import CareerShortlist
                user_careers = CareerShortlist.objects.filter(user=request.user).select_related('career')
                
                if user_careers.exists():
                    # Analyze career streams and calculate match percentage
                    # This is a simplified calculation - can be enhanced
                    stream_match = 75  # Base match
                    # Can be enhanced to calculate based on actual career stream requirements
        except Exception:
            pass
        
        # Get skills identified from user's career shortlists
        skills_identified = 0
        try:
            from careers.models import CareerShortlist, Career
            user_career_ids = CareerShortlist.objects.filter(user=request.user).values_list('career_id', flat=True)
            if user_career_ids:
                # Count unique skills from user's shortlisted careers
                skills_identified = Career.objects.filter(
                    id__in=user_career_ids
                ).values_list('skills', flat=True).distinct().count()
        except Exception:
            pass
        
        # Get universities/colleges viewed (from user activity or bookmarks)
        universities_viewed = 0
        try:
            from colleges.models import College
            # Check if user has viewed college pages (from user_analytics or bookmarks)
            # For now, use a placeholder that can be enhanced
            # You can track this via UserActivity model filtering by college-related paths
            from user_analytics.models import UserActivity
            college_views = UserActivity.objects.filter(
                user=request.user,
                page_path__icontains='college'
            ).values('page_path').distinct().count()
            universities_viewed = college_views
        except Exception:
            pass
        
        # Calculate career readiness percentage
        # Based on: careers explored, profile completeness, test completion
        career_readiness = 0
        try:
            profile_complete = 0
            if hasattr(request.user, 'user_profile') and request.user.user_profile:
                profile = request.user.user_profile
                # Check profile completeness
                if profile.grade:
                    profile_complete += 25
                if hasattr(profile, 'hobbies') and profile.hobbies.exists():
                    profile_complete += 25
                if hasattr(profile, 'subject') and profile.subject.exists():
                    profile_complete += 25
                if hasattr(profile, 'figure_out') and profile.figure_out.exists():
                    profile_complete += 25
            
            # Check if user has completed psychometric tests
            test_complete = 0
            try:
                from app_post_matric.models import TestSession
                if TestSession.objects.filter(user=request.user, is_completed=True).exists():
                    test_complete = 30
            except Exception:
                pass
            
            # Career exploration score
            career_exploration = min(careers_explored * 2, 30)  # Max 30 points for exploring careers
            
            # Skills development score
            skills_score = min(skills_identified * 5, 20)  # Max 20 points for skills
            
            career_readiness = profile_complete + test_complete + career_exploration + skills_score
            career_readiness = min(career_readiness, 100)  # Cap at 100%
        except Exception:
            pass
        
        forum_quota = None
        try:
            from core.llm_quota import forum_question_limit_status
            forum_quota = forum_question_limit_status(request.user, request=request)
        except Exception:
            forum_quota = None

        return DRFResponse({
            'is_authenticated': True,
            'careers_explored': careers_explored,
            'stream_match': stream_match,
            'skills_identified': skills_identified,
            'universities_viewed': universities_viewed,
            'career_readiness': career_readiness,
            'forum_quota': forum_quota,
        })


class AIFeaturesView(APIView):
    """Get AI Features list from database"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        features = AIFeature.objects.filter(is_active=True).order_by('order', 'name')
        serializer = AIFeatureSerializer(features, many=True)
        features_data = serializer.data
        
        # Dynamically set Psychometric Assessment Link based on user's class
        user_class = None
        if request.user.is_authenticated:
            try:
                # Check UserProfile.grade first
                if hasattr(request.user, 'user_profile') and request.user.user_profile:
                    profile = request.user.user_profile
                    if profile.grade:
                        try:
                            user_class = int(profile.grade)
                        except (ValueError, TypeError):
                            import re
                            numbers = re.findall(r'\d+', str(profile.grade))
                            if numbers:
                                user_class = int(numbers[0])
                
                # If no grade from UserProfile, check StudentManagement
                if user_class is None:
                    from institute.models import StudentManagement
                    student_management = StudentManagement.objects.filter(student=request.user).first()
                    if student_management and student_management.class_and_section:
                        class_name = student_management.class_and_section.class_and_section
                        if class_name:
                            import re
                            numbers = re.findall(r'\d+', class_name)
                            if numbers:
                                user_class = int(numbers[0])
            except Exception:
                pass
        
        # Update Psychometric Assessment Link based on class
        for feature in features_data:
            if feature.get('name') == 'Psychometric Assessment Link':
                if user_class is not None and user_class <= 10:
                    # Class 10 or below -> Stream Sorter
                    feature['link_url'] = '/psychometrictest/stream-sorter/'
                else:
                    # Class 11-12 or not logged in -> Career Direction (default)
                    feature['link_url'] = '/psychometrictest/career-direction/'
                break
        
        return DRFResponse(features_data)


class AICapabilitiesView(APIView):
    """Get AI Capabilities list from database"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        capabilities = AICapability.objects.filter(is_active=True).order_by('order', 'name')
        serializer = AICapabilitySerializer(capabilities, many=True)
        return DRFResponse(serializer.data)


class PopularQueriesView(APIView):
    """Get popular queries - no duplicates, optionally filtered by category"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        # Get category filter from query parameter
        category_slug = request.GET.get('category', None)
        
        # Get recent completed queries with responses, grouped by question text to avoid duplicates
        from django.db.models import Max
        
        # Base queryset - filter by category if provided
        base_queryset = Query.objects.filter(status='completed', is_hidden=False)
        if category_slug and category_slug != 'all':
            try:
                category_obj = Category.objects.get(slug=category_slug)
                base_queryset = base_queryset.filter(category=category_obj)
            except Category.DoesNotExist:
                pass  # If category doesn't exist, show all
        
        # Get unique questions (grouped by normalized question text)
        unique_queries = base_queryset.values('question_text').annotate(
            latest_id=Max('id'),
            latest_created=Max('created_at')
        ).order_by('-latest_created')[:40]
        
        # Get the actual query objects for the unique questions
        query_ids = [q['latest_id'] for q in unique_queries]
        popular_queries = Query.objects.filter(
            id__in=query_ids
        ).select_related('category', 'response').order_by('-created_at')
        
        queries_data = []
        seen_questions = set()  # Track normalized questions to avoid duplicates
        
        for query in popular_queries:
            # Normalize question for comparison (more aggressive normalization)
            normalized_question = query.question_text.lower().strip()
            # Remove extra whitespace
            normalized_question = re.sub(r'\s+', ' ', normalized_question)
            # Remove trailing punctuation
            normalized_question = re.sub(r'[.,!?;:]$', '', normalized_question)
            
            # Skip if we've already seen this question
            if normalized_question in seen_questions:
                continue
            
            seen_questions.add(normalized_question)
            
            country_emoji = ''
            if query.country_context:
                try:
                    country = Country.objects.get(name=query.country_context)
                    country_emoji = country.flag_emoji
                except Country.DoesNotExist:
                    pass
            
            # Get response text if available — skip paywall / non-answers
            response_text = ''
            try:
                if query.response:
                    response_text = query.response.response_text or ''
                    if is_non_answer_response(response_text):
                        continue
            except Response.DoesNotExist:
                continue

            if not str(response_text).strip():
                continue
            
            queries_data.append({
                'id': query.id,
                'question': query.question_text,
                'category': query.category.name if query.category else 'General',
                'category_slug': query.category.slug if query.category else '',
                'country': query.country_context or '',
                'country_emoji': country_emoji,
                'created_at': query.created_at.isoformat(),
                'response_text': response_text  # Include response text
            })
            
            # Stop when we have 5 unique queries
            if len(queries_data) >= 5:
                break
        
        # Return empty list if no queries - all data from database
        # No sample/fallback data - admin should seed database if needed
        
        return DRFResponse(queries_data)


class TrendingQueriesView(APIView):
    """Get trending queries"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        # Get recent queries (last 24 hours) ordered by creation
        from datetime import timedelta
        recent_time = timezone.now() - timedelta(days=1)
        
        # Get unique questions from recent queries
        from django.db.models import Max
        
        # Get unique questions from recent queries - improved deduplication
        unique_trending = Query.objects.filter(
            created_at__gte=recent_time,
            status='completed',
            is_hidden=False,
        ).values('question_text').annotate(
            latest_id=Max('id'),
            latest_created=Max('created_at')
        ).order_by('-latest_created')
        
        # Get the actual query objects for unique questions only
        query_ids = [q['latest_id'] for q in unique_trending]
        trending = Query.objects.filter(
            id__in=query_ids
        ).select_related('response').order_by('-created_at')
        
        trending_data = []
        seen_questions = set()  # Track normalized questions to avoid duplicates
        
        for query in trending:
            # Normalize question for comparison (more aggressive normalization)
            normalized_question = query.question_text.lower().strip()
            # Remove extra whitespace
            normalized_question = re.sub(r'\s+', ' ', normalized_question)
            # Remove trailing punctuation
            normalized_question = re.sub(r'[.,!?;:]$', '', normalized_question)
            
            # Skip if we've already seen this question
            if normalized_question in seen_questions:
                continue
            
            seen_questions.add(normalized_question)
            
            # Get response text if available — skip paywall / non-answers
            response_text = ''
            try:
                if query.response:
                    response_text = query.response.response_text or ''
                    if is_non_answer_response(response_text):
                        continue
            except Response.DoesNotExist:
                continue

            if not str(response_text).strip():
                continue
            
            trending_data.append({
                'id': query.id,
                'question': query.question_text,
                'tag': 'Hot Topic',
                'created_at': query.created_at.isoformat(),
                'response_text': response_text  # Include response text
            })
            
            # Stop when we have 4 unique queries
            if len(trending_data) >= 4:
                break
        
        # Return empty list if no trending queries - all data from database
        # No sample/fallback data - will populate as users ask questions
        
        return DRFResponse(trending_data)
