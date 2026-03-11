from careers.models import Career, CareerTags, Videos, CareerCluster
from core.models import Configuration
from core.seo_schema import get_organization_schema, get_website_schema
from blog.models import Blog, BlogCategory
from django.db.models import Count
from core.utils import build_html_head
from colleges.models import College
from courses.models import Course
from users.models import UserSearchHistory
from entrance_exams.models import EntranceExam
from users.models import User
from core import choices
from core.choices import MINDMAP_TYPE_CHOICES
from django.db.models import Q, Count, Q as DjangoQ
from functools import reduce
from operator import or_
from django.conf import settings
import json
import logging

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
    """
    data = _student_localstorage_data(request)
    if data is None:
        return {"student_localstorage_enc": None, "student_localstorage": None}
    enc = _encrypt_student_data(data)
    if enc:
        return {"student_localstorage_enc": enc, "student_localstorage": None}
    return {"student_localstorage_enc": None, "student_localstorage": data}


def _should_show_ai_counsellor_bot(request):
    """
    Show floating AI Career Counsellor bot for logged-in students/parents on dashboard-like pages.
    Excluded: career-counselling (full page), institute, counselor, admin.
    Respects admin configuration counselling_engine: when disabled, bot is hidden on student dashboard.
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return False
    if not _config_bool('counselling_engine', True):
        return False
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
            exam_list=EntranceExam.objects.filter(q_object)[:5]

        
    popular_categories = Blog.objects.values("category").annotate(count=Count('category')).order_by("-count").values_list('category')
    popular_tags = Career.objects.values("career_tags").annotate(count=Count('career_tags')).order_by("-count").values_list('career_tags')
    # for p in popular_tags:
        # popular_tag_count=Career.objects.filter(career_tags=p).count()
    # Freetrail: seconds guest can view gated content before login popup (used by ebook/vocational/extracurricular detail and any freetrail-gated page)
    kwargs = {
        "allow_search_engine_index": getattr(settings, 'ALLOW_SEARCH_ENGINE_INDEX', False),
        "freetrail_seconds": getattr(settings, 'FREETRAIL_TIME_SECONDS', 5),
        "show_chatbot": _should_show_chatbot(request),
        "show_ai_counsellor_bot": _should_show_ai_counsellor_bot(request),
        "enable_answering_carefully_widget": _config_bool('ENABLE_ANSWERING_CAREFULLY_WIDGET', getattr(settings, 'ENABLE_ANSWERING_CAREFULLY_WIDGET', True)),
        "enable_auto_forward": _config_bool('ENABLE_AUTO_FORWARD', getattr(settings, 'ENABLE_AUTO_FORWARD', True)),
        "show_missing_answers_validation": _config_bool('SHOW_MISSING_ANSWERS_VALIDATION', getattr(settings, 'SHOW_MISSING_ANSWERS_VALIDATION', True)),
        "enable_career_mindmap": _config_bool('ENABLE_CAREER_MINDMAP', True),
        "default_mindmap_type": str(Configuration.get('DEFAULT_MINDMAP_TYPE', '6', editable=True) or '6').strip() or '6',
        "mindmap_type_choices": MINDMAP_TYPE_CHOICES,
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