from careers.models import Career, CareerTags, Videos, CareerCluster
from core.models import Configuration
from core.seo_schema import get_organization_schema, get_website_schema
from blog.models import Blog, BlogCategory
from django.db.models import Count
from core.utils import build_html_head
from colleges.models import College
from courses.models import Course
from users.models import UserSearchHistory
from core.models import EntranceTestPrepExam
from users.models import User
from core import choices
from core.choices import MINDMAP_TYPE_CHOICES, coerce_default_mindmap_type
from counselor.mindmap_config import get_counselor_mindmap_map_type
from django.db.models import Q, Count, Q as DjangoQ
from functools import reduce
from operator import or_
from django.conf import settings
from django.db import connection
import json
import logging
import re
from urllib.parse import parse_qs
from django.db.utils import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)


def _encrypt_student_data(data_dict):
    """
    Encrypt student localStorage payload with Fernet (AES-128-CBC + HMAC).
    Returns base64-encoded ciphertext string, or None if key is missing/invalid.
    Use the same key and Fernet in your chatbot to decrypt.
    """
    key = getattr(settings, 'STUDENT_DATA_ENCRYPTION_KEY', None) or ''
    key = (key or '').strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        f = Fernet(key.encode() if isinstance(key, str) else key)
        payload = json.dumps(data_dict, sort_keys=True).encode('utf-8')
        return f.encrypt(payload).decode('ascii')
    except Exception as e:
        logger.warning("Student data encryption failed: %s", e)
        return None


def _footer_career_clusters():
    """Same clusters as careers page grid: active, with at least one published career, ordered by name. Links use /careers/cluster/<slug>-<id>/."""
    try:
        clusters_qs = CareerCluster.objects.filter(
            career_clusters__publish_status=1,
            object_status=1,
        ).distinct().annotate(
            career_count=Count('career_clusters', filter=DjangoQ(career_clusters__publish_status=1), distinct=True)
        ).filter(career_count__gt=0).order_by('name')
        return [{'id': c.id, 'name': c.name or '', 'slug': c.slug or ''} for c in clusters_qs]
    except Exception:
        return []


def _seo_organization_schema():
    """SEO Organization JSON-LD schema (site-wide)."""
    base = getattr(settings, "ENQUIRY_SOURCE_BASE_URL", "https://www.topteen.in").rstrip("/")
    return get_organization_schema(base, site_name="Top Teen")


def _seo_website_schema():
    """SEO WebSite JSON-LD schema with optional search URL."""
    base = getattr(settings, "ENQUIRY_SOURCE_BASE_URL", "https://www.topteen.in").rstrip("/")
    search_url = getattr(settings, "SEO_WEBSITE_SEARCH_URL", None)  # e.g. "/search/?q={search_term_string}"
    return get_website_schema(base, site_name="Top Teen", search_url=search_url)


def _config_bool(key, settings_default=True):
    """Get boolean from Configuration (Admin-managed), fallback to settings."""
    try:
        val = Configuration.get(key, default=str(settings_default).lower(), editable=True)
        return str(val).lower() in ('true', '1', 'yes', 'on')
    except Exception:
        return getattr(settings, key, settings_default)


def _should_show_chatbot(request):
    """
    Determine if chatbot should be shown based on CHATBOT_VISIBILITY and request path.
    Options: home-only | students-parents | institutes | counselors
    """
    visibility = getattr(settings, 'CHATBOT_VISIBILITY', 'home-only')
    path = (request.path or '/').rstrip('/') or '/'

    # Excluded paths (never show chatbot)
    excluded_prefixes = (
        '/user/login', '/student/login', '/student/signup', '/parents/login',
        '/institute/auth/login', '/counselor/auth/login',
        '/contact-us', '/psychometric', '/psychometrictest',
        '/topteenadmin', '/admin', '/api', '/oauth',
        '/career-battle',  # game page with iframe; keep UI clean
        '/career-counselling',  # AI counselling chat page
    )
    for prefix in excluded_prefixes:
        if path == prefix or path.startswith(prefix + '/'):
            return False

    if visibility == 'home-only':
        return path == '/'

    if visibility == 'students-parents':
        return (
            path == '/' or
            path.startswith('/student') or path.startswith('/parents') or
            (path.startswith('/user') and 'dashboard' in path)
        )

    if visibility == 'institutes':
        return (
            path == '/' or
            path.startswith('/student') or path.startswith('/parents') or
            path.startswith('/institute') or
            (path.startswith('/user') and 'dashboard' in path)
        )

    if visibility == 'counselors':
        return True  # Show everywhere except excluded (already checked above)

    return False


def _student_localstorage_data(request):
    """
    For students only: return dict to store in localStorage (student_id, student_class,
    psychometric_class10_status, psychometric_class12_status as pending/inprocess/completed).
    Works for institute students, direct signups, and Google/Facebook (OAuth) students.
    Returns None for non-students.
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return None
    if getattr(request.user, 'user_type', None) != choices.UserType.STUDENT:
        return None
    try:
        from app.models import Results
        from institute.models import StudentManagement
        from psychometric_tests.models import CandidateTest
        import re
        user = request.user
        student_class = "10"
        if hasattr(user, 'user_profile') and user.user_profile and getattr(user.user_profile, 'grade', None):
            student_class = str(user.user_profile.grade).strip() or "10"
        else:
            try:
                sm = StudentManagement.objects.filter(student=user).first()
                if sm and sm.class_and_section and getattr(sm.class_and_section, 'class_and_section', None):
                    class_name = sm.class_and_section.class_and_section
                    nums = re.findall(r'\d+', class_name)
                    if nums:
                        n = int(nums[0])
                        student_class = "12" if n >= 11 else "10"
            except Exception:
                pass
        # Class 10 psychometric (test1, test2, test3): pending / inprocess / completed
        class10_count = Results.objects.filter(user=user, test_paper__in=['test1', 'test2', 'test3']).count()
        if class10_count == 0:
            psychometric_class10_status = "pending"
        elif class10_count < 3:
            psychometric_class10_status = "inprocess"
        else:
            psychometric_class10_status = "completed"
        # Class 12 psychometric (stream sorter / paid test): pending / inprocess / completed
        class12_tests = CandidateTest.objects.filter(central_test_candidate__user=user).order_by('-modified')
        class12_completed = class12_tests.filter(is_success=choices.YesNoChoices.YES).exists()
        class12_any = class12_tests.exists()
        if not class12_any:
            psychometric_class12_status = "pending"
        elif class12_completed:
            psychometric_class12_status = "completed"
        else:
            psychometric_class12_status = "inprocess"
        return {
            "student_id": user.id,
            "student_class": student_class,
            "psychometric_class10_status": psychometric_class10_status,
            "psychometric_class12_status": psychometric_class12_status,
        }
    except Exception:
        return None


def _student_localstorage_context(request):
    """
    Returns context for student localStorage: encrypted payload when
    STUDENT_DATA_ENCRYPTION_KEY is set, else plain dict. For students only.
    chatbot_student_localstorage is always plain (four keys for Career Counsellor bot).
    """
    data = _student_localstorage_data(request)
    if data is None:
        return {
            "student_localstorage_enc": None,
            "student_localstorage": None,
            "chatbot_student_localstorage": None,
        }
    enc = _encrypt_student_data(data)
    if enc:
        return {
            "student_localstorage_enc": enc,
            "student_localstorage": None,
            "chatbot_student_localstorage": data,
        }
    return {
        "student_localstorage_enc": None,
        "student_localstorage": data,
        "chatbot_student_localstorage": data,
    }


def _should_show_ai_counsellor_bot(request):
    """
    Show floating AI Career Counsellor bot for logged-in students/parents on dashboard-like pages.
    Excluded: career-counselling (full page), institute, counselor, admin.
    Respects admin configuration counselling_engine: when disabled, bot is hidden on student dashboard.
    """
    path = (request.path or '/').rstrip('/') or '/'
    excluded = (
        '/career-counselling',
        '/institute',
        '/counselor',
        '/topteenadmin',
        '/admin',
    )
    for prefix in excluded:
        if path == prefix or path.startswith(prefix + '/'):
            return False
    return True


def _get_chatbot_page_mode(request):
    """
    Return chatbot mode for current path from admin-managed JSON rules.
    Modes: default | none | chat_this_page | career_counsellor | both

    Config key: CHATBOT_PAGE_RULES (JSON array), example:
    [
      {"match": "exact", "pattern": "/", "mode": "career_counsellor"},
      {"match": "prefix", "pattern": "/four-pillars-of-learning/", "mode": "chat_this_page"}
    ]
    """
    valid_modes = {"default", "none", "chat_this_page", "career_counsellor", "both"}
    path = request.path or "/"
    default_mode = str(Configuration.get('CHATBOT_DEFAULT_MODE', 'default', editable=True) or 'default').strip().lower()
    if default_mode not in valid_modes:
        default_mode = "default"
    raw = Configuration.get('CHATBOT_PAGE_RULES', '[]', editable=True) or '[]'
    try:
        rules = json.loads(raw)
    except Exception:
        return default_mode
    if not isinstance(rules, list):
        return default_mode
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        mode = str(rule.get("mode", "default")).strip().lower()
        if mode not in valid_modes:
            continue
        match = str(rule.get("match", "prefix")).strip().lower()
        pattern = str(rule.get("pattern", "")).strip()
        if not pattern:
            continue
        hit = False
        if match == "exact":
            hit = (path == pattern)
        elif match == "regex":
            try:
                hit = re.search(pattern, path) is not None
            except re.error:
                hit = False
        else:
            hit = path.startswith(pattern)
        if hit:
            return mode
    return default_mode


def _normalize_chatbot_path(raw):
    """Normalize URL path for chatbot rule matching (strip query string and trailing slash)."""
    value = (raw or '/').strip() or '/'
    if '?' in value:
        value = value.split('?', 1)[0]
    if not value.startswith('/'):
        value = '/' + value
    if value != '/' and value.endswith('/'):
        value = value.rstrip('/')
    return value


def _rule_query_params(raw):
    raw = (raw or '').strip()
    if '?' not in raw:
        return {}
    parsed = parse_qs(raw.split('?', 1)[1], keep_blank_values=True)
    return parsed


def _query_params_match(rule_raw, request):
    expected = _rule_query_params(rule_raw)
    if not expected:
        return True
    if request is None:
        return False
    for key, values in expected.items():
        actual = request.GET.getlist(key)
        if not actual and request.GET.get(key) is not None:
            actual = [request.GET.get(key)]
        if not values:
            continue
        if not any(str(v) in [str(a) for a in actual] for v in values):
            return False
    return True


def _match_chatbot_rule(path, base_path, include_subpages=False, request=None):
    base = _normalize_chatbot_path(base_path)
    current = _normalize_chatbot_path(path)

    path_hit = False
    if current == base:
        path_hit = True
    elif include_subpages:
        # include_subpages=True means this rule applies to the listing/base page
        # (already handled above) and all nested paths beneath it.
        if base == '/':
            # base + '/' would be '//' which never matches — treat "/" as "whole site"
            path_hit = current != '/'
        else:
            path_hit = current.startswith(base + '/')

    if not path_hit:
        return False
    return _query_params_match(base_path, request)


def _apply_user_analytics_chatbot_rules(
    request,
    show_page_chat_widget,
    show_ai_counsellor_bot,
    page_chat_enabled=True,
    ai_counsellor_enabled=True,
    page_chat_position='left',
    ai_counsellor_position='right',
):
    """
    Apply per-page chatbot rules managed from User Analytics dashboard.

    Behavior per bot:
    - disabled: hide everywhere (caller already enforces this too)
    - enabled + no rules: show everywhere (keep incoming default True)
    - enabled + has rules: only matched rules control visibility
    """
    matched_any_rule = False
    try:
        from user_analytics.models import ChatbotPageRule
        path = request.path or '/'
        # Apply lower priority numbers last so they win; within same priority, newer modified wins.
        rules = list(
            ChatbotPageRule.objects.filter(object_status=choices.ObjectStatus.ACTIVE).order_by(
                '-priority', 'modified', 'id'
            )
        )

        has_page_chat_rules = any(r.bot_name == 'chat_this_page' for r in rules)
        has_career_rules = any(r.bot_name == 'career_counsellor' for r in rules)

        # If rules exist for an enabled bot, visibility is rule-driven only.
        if page_chat_enabled and has_page_chat_rules:
            show_page_chat_widget = False
        if ai_counsellor_enabled and has_career_rules:
            show_ai_counsellor_bot = False

        for rule in rules:
            if not _match_chatbot_rule(
                path,
                rule.page_url,
                include_subpages=bool(rule.include_subpages),
                request=request,
            ):
                continue
            matched_any_rule = True
            if rule.bot_name == 'chat_this_page':
                if not page_chat_enabled:
                    continue
                show_page_chat_widget = bool(rule.is_visible)
                page_chat_position = rule.position or page_chat_position
            elif rule.bot_name == 'career_counsellor':
                if not ai_counsellor_enabled:
                    continue
                show_ai_counsellor_bot = bool(rule.is_visible)
                ai_counsellor_position = rule.position or ai_counsellor_position
    except (ProgrammingError, OperationalError):
        # Rule table may not exist before migrations.
        pass
    except Exception:
        pass
    return (
        show_page_chat_widget,
        show_ai_counsellor_bot,
        page_chat_position,
        ai_counsellor_position,
        matched_any_rule,
    )


def globals(request): 
    career_list=[]
    college_list=[]
    exam_list=[] 
    input=request.GET.get('search')
    login_user=request.user
    if login_user.is_authenticated:
        try:
            usersearch,_=UserSearchHistory.objects.get_or_create(user=login_user,search=input)
        except UserSearchHistory.MultipleObjectsReturned:
            # If multiple objects exist, get the first one
            usersearch = UserSearchHistory.objects.filter(user=login_user,search=input).first()
            if not usersearch:
                usersearch = UserSearchHistory.objects.create(user=login_user,search=input)

        user_search_hisotry=UserSearchHistory.objects.filter(user=login_user.id,search__isnull=False).order_by('-modified').values_list('search',flat=True)
        if user_search_hisotry.exists():
            q_object = reduce(or_,(Q(name__icontains=sh) for sh in user_search_hisotry))
            career_list=Career.objects.filter(q_object)[:5]
            college_list=College.objects.filter(q_object)[:5]
            # Build exam_list via raw SQL so modeltranslation cannot rewrite 'name' to 'name_en' (EntranceTestPrepExam has no translated fields).
            search_terms = list(user_search_hisotry[:10])
            try:
                with connection.cursor() as cursor:
                    if search_terms:
                        placeholders = " OR ".join(["name LIKE %s"] * len(search_terms))
                        params = ["%" + str(t) + "%" for t in search_terms] + [choices.ObjectStatus.ACTIVE]
                        cursor.execute(
                            f"""
                            SELECT id FROM core_entrancetestprepexam
                            WHERE ({placeholders}) AND object_status = %s
                            ORDER BY name
                            LIMIT 5
                            """,
                            params,
                        )
                        pks = [row[0] for row in cursor.fetchall()]
                    else:
                        pks = []
                if pks:
                    exam_list = list(EntranceTestPrepExam._base_manager.filter(pk__in=pks).order_by("name")[:5])
                else:
                    exam_list = []
            except Exception as e:
                logger.warning("Context processor exam_list raw SQL failed: %s", e)
                exam_list = []

        
    popular_categories = Blog.objects.values("category").annotate(count=Count('category')).order_by("-count").values_list('category')
    popular_tags = Career.objects.values("career_tags").annotate(count=Count('career_tags')).order_by("-count").values_list('career_tags')
    # for p in popular_tags:
        # popular_tag_count=Career.objects.filter(career_tags=p).count()
    # Freetrail: seconds guest can view gated content before login popup (used by ebook/vocational/extracurricular detail and any freetrail-gated page)
    legacy_chatbot_enabled = _config_bool('legacy_chatbot_engine', False)
    page_chat_enabled = _config_bool('chat_this_page_engine', True)
    ai_counsellor_enabled = legacy_chatbot_enabled
    # Default behavior:
    # - If bot is globally enabled and there is no matching rule, show everywhere.
    # - Rules can override visibility on matched paths.
    # - If bot is globally disabled, hide everywhere.
    show_page_chat_widget = page_chat_enabled
    show_ai_counsellor_bot = legacy_chatbot_enabled
    page_chat_position = 'left'
    ai_counsellor_position = 'right'
    # Legacy chatbot (chatbot.html/chatbot.js) is retired; keep disabled everywhere.
    show_chatbot = False
    # NOTE:
    # Legacy CHATBOT_DEFAULT_MODE / CHATBOT_PAGE_RULES config is intentionally not
    # used to drive these two bot widgets anymore. User Analytics rules are the
    # source of truth for per-page behavior.

    # Highest-precedence: User Analytics Bot Rules page
    show_page_chat_widget, show_ai_counsellor_bot, page_chat_position, ai_counsellor_position, ua_rule_matched = _apply_user_analytics_chatbot_rules(
        request,
        show_page_chat_widget,
        show_ai_counsellor_bot,
        page_chat_enabled,
        ai_counsellor_enabled,
        page_chat_position,
        ai_counsellor_position,
    )
    if not page_chat_enabled:
        show_page_chat_widget = False
    if not legacy_chatbot_enabled:
        show_ai_counsellor_bot = False
    if ua_rule_matched:
        # User Analytics per-page rules take precedence over legacy floating chatbot.
        show_chatbot = False

    chatbot_widget_body_class = ''
    body_class_parts = []
    if show_page_chat_widget and str(page_chat_position or 'left').lower() == 'right':
        body_class_parts.append('cb-page-chat-right')
    if show_ai_counsellor_bot and str(ai_counsellor_position or 'right').lower() == 'left':
        body_class_parts.append('cb-ai-pos-left')
    if (
        show_ai_counsellor_bot
        and show_page_chat_widget
        and str(page_chat_position or 'left').lower() == str(ai_counsellor_position or 'right').lower()
    ):
        body_class_parts.append('cb-bots-stack')
    if body_class_parts:
        chatbot_widget_body_class = ' '.join(body_class_parts)

    kwargs = {
        "allow_search_engine_index": getattr(settings, 'ALLOW_SEARCH_ENGINE_INDEX', False),
        "freetrail_seconds": getattr(settings, 'FREETRAIL_TIME_SECONDS', 5),
        "show_chatbot": show_chatbot,
        "show_ai_counsellor_bot": show_ai_counsellor_bot,
        "show_page_chat_widget": show_page_chat_widget,
        "legacy_chatbot_enabled": legacy_chatbot_enabled,
        "page_chat_position": page_chat_position,
        "ai_counsellor_position": ai_counsellor_position,
        "chatbot_widget_body_class": chatbot_widget_body_class,
        "enable_answering_carefully_widget": _config_bool('ENABLE_ANSWERING_CAREFULLY_WIDGET', getattr(settings, 'ENABLE_ANSWERING_CAREFULLY_WIDGET', True)),
        "enable_auto_forward": _config_bool('ENABLE_AUTO_FORWARD', getattr(settings, 'ENABLE_AUTO_FORWARD', True)),
        "show_missing_answers_validation": _config_bool('SHOW_MISSING_ANSWERS_VALIDATION', getattr(settings, 'SHOW_MISSING_ANSWERS_VALIDATION', True)),
        "enable_career_mindmap": _config_bool('ENABLE_CAREER_MINDMAP', True),
        "default_mindmap_type": coerce_default_mindmap_type(
            Configuration.get('DEFAULT_MINDMAP_TYPE', '6', editable=True) or '6'
        ),
        "mindmap_type_choices": MINDMAP_TYPE_CHOICES,
        "counselor_mindmap_map_type": get_counselor_mindmap_map_type(),
        "popular_categories":BlogCategory.objects.filter(id__in=popular_categories),
        "popular_tags":CareerTags.objects.filter(id__in=popular_tags),
        "blogs":Blog.get_published_objects().all(),
        "seo_year":"2025",
        "recentcareer":career_list,
        "recentcollege":college_list,
        "recentexam":exam_list,
        "most_searchcareers":Career.objects.filter(publish_status=choices.PublishStatus.PUBLISHED).order_by('?')[:8],
        'most_searchcolleges':College.objects.all().order_by('id')[:5],
        'tranding_content':Blog.objects.all(),
        "careervideos_count":Videos.objects.count(),
        # Footer: top-level career clusters for "Trending Career Paths" (links to /careers/cluster/<slug>-<id>/)
        "footer_career_clusters": _footer_career_clusters(),
        # SEO: absolute site base URL for canonical/og:image when request is not available
        "site_base_url": getattr(settings, "ENQUIRY_SOURCE_BASE_URL", "https://www.topteen.in").rstrip("/"),
        # SEO: JSON-LD schema for Organization and WebSite (included on every page)
        "seo_organization": _seo_organization_schema(),
        "seo_website": _seo_website_schema(),
        # Student-only: encrypted or plain payload for localStorage (see STUDENT_DATA_ENCRYPTION_KEY)
        **_student_localstorage_context(request),
        # "popular_tag_count":popular_tag_count
    }
    return kwargs