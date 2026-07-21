import re
import logging
from django.db.models import Q
from core import choices
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from threading import local
import time
import os

logger = logging.getLogger(__name__)
from datetime import datetime
from bs4 import BeautifulSoup

# Pages that use rich layout (highlighter, hero sections). We only strip breadcrumb; keep full content.
RICH_LAYOUT_STATIC_PAGES = frozenset([
    "about", "career_planning", "career_planning_4_year",
    "career_planning_class_9", "career_planning_class_10", "career_planning_class_11", "career_planning_class_12",
    "emotional_intelligences", "multiple_intelligences", "four_pillars",
])
_thread_locals = local()


def set_current_user(user):
    _thread_locals.user=user

def get_current_user():
    return getattr(_thread_locals, 'user', None)


def get_gcd(p, q):
    if q == 0:
        return p
    else:
        return get_gcd(q, p % q)

def ratio(p,q):
    if p > q:
        return round(p/q),1
    return round(q/p),1

def expand_eq_band_percentile(label):
    """Replace legacy '%ile' abbreviation with the full word 'percentile' for display."""
    if label is None:
        return label
    s = str(label)
    if not s:
        return s
    return re.sub(r"%ile", "percentile", s, flags=re.IGNORECASE)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def ensure_user_pdf_folder(user_id):
    """
    Ensure media/users_pdfs/<user_id> folder exists for storing user PDFs
    (e.g. psychometric reports). Safe to call on every request; creates only if missing.
    Returns the directory path if successful, None on error.
    """
    if user_id is None:
        return None
    try:
        user_pdf_dir = os.path.join(settings.MEDIA_ROOT, 'users_pdfs', str(user_id))
        if not os.path.exists(user_pdf_dir):
            os.makedirs(user_pdf_dir, exist_ok=True)
        return user_pdf_dir
    except OSError as e:
        logger.warning("ensure_user_pdf_folder failed for user_id=%s (MEDIA_ROOT=%s): %s", user_id, getattr(settings, 'MEDIA_ROOT', None), e)
        return None


def user_pdf_key(user_id, filename):
    """Storage key (relative to the media location) for a user's report PDF."""
    return f"users_pdfs/{user_id}/{filename}"


def save_user_pdf(user_id, filename, content):
    """
    Persist a generated report PDF through the default media storage backend.

    When USE_S3_FOR_MEDIA is on, this uploads to S3 (key: <media>/users_pdfs/<id>/<file>)
    instead of the local disk, so hosts/containers don't accumulate PDF copies that
    already live on S3. Overwrites any existing file with the same name.

    Best-effort: never raises. `content` may be raw bytes or a file-like object.
    Returns the stored key on success, or None on failure.
    """
    if not user_id or not filename:
        return None
    key = user_pdf_key(user_id, filename)
    try:
        if isinstance(content, (bytes, bytearray)):
            content = ContentFile(bytes(content))
        # Guarantee overwrite on regeneration. delete() is idempotent (a no-op for a
        # missing key on both S3 and local storage), and we avoid default_storage.exists()
        # which is unreliable with this S3 configuration.
        default_storage.delete(key)
        saved = default_storage.save(key, content)
        mark_user_pdf_ready(user_id, filename, True)
        return saved
    except Exception as e:
        logger.warning("save_user_pdf failed for user_id=%s file=%s: %s", user_id, filename, e)
        return None


def class10_assessment_pdf_filename(user, test_paper):
    """Stable PDF filename used by Class 10 download_pdf / Celery generation."""
    raw_name = getattr(user, 'name', None) or getattr(user, 'email', None) or str(user)
    safe_name = re.sub(r'[^\w\s-]', '', str(raw_name)).strip()[:50] or 'user'
    if test_paper == 'test1':
        return f"{safe_name}-Personality_Assessment_report.pdf"
    if test_paper == 'test2':
        return f"{safe_name}-Interest_Assessment_report.pdf"
    if test_paper == 'test3':
        return f"{safe_name}-Aptitude_Assessment_report.pdf"
    return f"{safe_name}-Final_Assessment_report.pdf"


def class10_combined_report_pdf_filename(user):
    """Stable filename for Stream Sorter combined report PDF downloads."""
    raw_name = getattr(user, 'name', None) or getattr(user, 'email', None) or str(user)
    safe_name = re.sub(r'[^\w\s-]', '', str(raw_name)).strip()[:50] or 'user'
    return f"{safe_name}-Stream_Sorter_Combined_Report.pdf"


def class10_web_report_pdf_filename(user, report_kind):
    """
    Filename for web report PDF buttons.

    report_kind: 'combined' | 'test1' | 'test2' | 'test3'
    """
    kind = (report_kind or '').strip().lower()
    if kind == 'combined':
        return class10_combined_report_pdf_filename(user)
    return class10_assessment_pdf_filename(user, kind)


def delete_user_pdf(user_id, filename):
    """Best-effort delete of a stored user PDF (local or S3)."""
    if not user_id or not filename:
        return False
    key = user_pdf_key(user_id, filename)
    try:
        default_storage.delete(key)
        mark_user_pdf_ready(user_id, filename, False)
        return True
    except Exception as e:
        logger.warning("delete_user_pdf failed for user_id=%s file=%s: %s", user_id, filename, e)
        return False


def _user_pdf_s3_object_key(storage_relative_key: str) -> str:
    """Full S3 object key including the media location prefix."""
    from storages.utils import clean_name

    relative = clean_name(storage_relative_key)
    normalize = getattr(default_storage, "_normalize_name", None)
    if callable(normalize):
        return normalize(relative).lstrip("/")
    location = (getattr(settings, "S3_MEDIA_LOCATION", None) or getattr(default_storage, "location", "") or "").strip("/")
    if location:
        return f"{location}/{relative.lstrip('/')}"
    return relative.lstrip("/")


def user_pdf_presigned_download_url(user_id, filename, download_name=None, expires_in=600, inline=True):
    """
    Short-lived S3 GET URL for a stored report PDF.

    ``inline=True`` (default) opens in the browser tab; ``False`` forces download.
    Works even when S3_MEDIA_ACCESS_MODE=proxy. Returns None when not on S3 or signing fails.
    """
    if not user_id or not filename:
        return None
    if not getattr(settings, "USE_S3_FOR_MEDIA", False):
        return None
    if not getattr(default_storage, "bucket_name", None):
        return None

    name = download_name or filename
    safe_name = re.sub(r"[^\w.\- ]+", "", str(name)).strip()[:120] or "report.pdf"
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"
    disposition = "inline" if inline else "attachment"

    try:
        s3_key = _user_pdf_s3_object_key(user_pdf_key(user_id, filename))
        client = default_storage.connection.meta.client
        return client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": default_storage.bucket_name,
                "Key": s3_key,
                "ResponseContentType": "application/pdf",
                "ResponseContentDisposition": f'{disposition}; filename="{safe_name}"',
            },
            ExpiresIn=int(expires_in),
        )
    except Exception as e:
        logger.warning(
            "user_pdf_presigned_download_url failed user_id=%s file=%s: %s",
            user_id,
            filename,
            e,
        )
        return None


def serve_user_pdf_response(user_id, filename, download_name=None, inline=True):
    """
    Deliver a stored report PDF without streaming bytes through Gunicorn.

    Prefer a 302 redirect to a short-lived S3 signed URL. Fall back to
    FileResponse only for local (non-S3) storage.

    ``inline=True`` (default) opens the PDF in the browser tab so a
    "Preparing…" wait page is replaced by the viewer instead of a download.
    """
    if not user_id or not filename:
        return None

    name = download_name or filename
    signed = user_pdf_presigned_download_url(
        user_id, filename, download_name=name, inline=inline
    )
    if signed:
        from django.http import HttpResponseRedirect

        response = HttpResponseRedirect(signed)
        response["Cache-Control"] = "no-store"
        return response

    # Local filesystem / non-S3 fallback
    key = user_pdf_key(user_id, filename)
    try:
        from django.http import FileResponse

        handle = default_storage.open(key, "rb")
        response = FileResponse(handle, content_type="application/pdf")
        safe_name = re.sub(r"[^\w.\- ]+", "", str(name)).strip()[:120] or "report.pdf"
        disposition = "inline" if inline else "attachment"
        response["Content-Disposition"] = f'{disposition}; filename="{safe_name}"'
        response["Cache-Control"] = "private, max-age=300"
        return response
    except Exception as e:
        logger.warning("serve_user_pdf_response failed for user_id=%s file=%s: %s", user_id, filename, e)
        mark_user_pdf_ready(user_id, filename, False)
        return None


def mark_user_pdf_ready(user_id, filename, ready=True):
    """Redis flag — S3 exists() is unreliable in this project's storage config."""
    if not user_id or not filename:
        return
    try:
        from django.core.cache import cache

        key = f"user_pdf_ready:v1:{user_id}:{filename}"
        if ready:
            cache.set(key, 1, 60 * 60 * 24 * 14)
        else:
            cache.delete(key)
    except Exception:
        pass


def user_pdf_exists(user_id, filename):
    """
    True if a previously generated report PDF is already in media storage.

    Prefer Redis ready-flag only on the hot path. Do NOT probe S3 with open()/exists()
    when the flag is missing — missing-key probes are slow and block Gunicorn under load.
    """
    if not user_id or not filename:
        return False
    try:
        from django.core.cache import cache

        return bool(cache.get(f"user_pdf_ready:v1:{user_id}:{filename}"))
    except Exception:
        return False


def class10_pdf_lock_key(user_id, test_paper):
    return f"class10_pdf_gen:{user_id}:{test_paper}"


def sort_colleges(colleges,request):
    return colleges

def build_breadcrumb(list_of_dict):
	lst = []
	home = {'title': 'Home', 'url': '/', 'text': 'Home'}
	if not list_of_dict:
		return [home]
	first = list_of_dict[0] if list_of_dict else {}
	first_text = (first.get('text') or first.get('title') or '').strip()
	first_url = (first.get('url') or '').strip().rstrip('/')
	# Avoid duplicate Home when caller already passed Home as first item
	if first_text.lower() == 'home' and (not first_url or first_url == '/' or first_url.endswith('/home')):
		return list(list_of_dict)
	lst.append(home)
	lst.extend(list_of_dict)
	return lst

def build_html_head(**kwargs):
	"""
	Build context dict for page <head> (title, description, optional SEO/social).
	Views pass e.g. build_html_head(title='...', description='...').
	Optional keys for social/SEO (used by base templates): image (absolute URL),
	url (canonical/og:url), og_type (default 'website').
	"""
	return kwargs


def strip_leading_h1_html(html):
	"""Remove the first <h1>...</h1> from HTML so the page title is not duplicated in content."""
	if not html or not isinstance(html, str):
		return html
	pattern = re.compile(r'^\s*<h1\b[^>]*>.*?</h1>\s*', re.IGNORECASE | re.DOTALL)
	return pattern.sub('', html, count=1).strip()


def strip_breadcrumb_html(html):
	"""Remove leading breadcrumb markup so breadcrumbs come only from the template."""
	if not html or not isinstance(html, str):
		return html
	out = html
	while True:
		m = re.match(
			r'^\s*(?:<div[^>]*>\s*)?<nav\s[^>]*aria-label\s*=\s*["\']breadcrumb["\'][^>]*>.*?</nav>\s*(?:</div>)?\s*',
			out, re.IGNORECASE | re.DOTALL,
		)
		if not m:
			break
		out = out[m.end():].strip()
	return out


def get_static_page_content_display(html, url_key):
	"""Return HTML for display: strip breadcrumb for all; strip leading h1 only for simple pages."""
	if not html or not isinstance(html, str):
		return html or ""
	html = strip_breadcrumb_html(html)
	if url_key not in RICH_LAYOUT_STATIC_PAGES:
		html = strip_leading_h1_html(html)
	return html


def get_static_page(url_key):
	"""Return StaticPage for url_key if active, else None."""
	from core.models import StaticPage
	return StaticPage.objects.filter(url_key=url_key, is_active=True).prefetch_related("sections").first()


# Map dashboard url_key to frontend path (no leading slash) for "Visit page" links and middleware path->key lookup.
# Path-style url_keys (e.g. blogs/slug, careers/career/slug-1-detail) use the key as path.
URL_KEY_TO_FRONTEND_PATH = {
	"about": "about-us",
	"terms": "terms-and-condition",
	"contact": "contact-us",
	"privacy": "privacy-policy",
	"career_planning": "career-planning",
	"career_planning_4_year": "career-planning/4-year-course-plan",
	"career_planning_class_9": "career-planning/class-9",
	"career_planning_class_10": "career-planning/class-10",
	"career_planning_class_11": "career-planning/class-11",
	"career_planning_class_12": "career-planning/class-12",
	"emotional_intelligences": "assessments/emotional-intelligences",
	"multiple_intelligences": "assessments/multiple-intelligences",
	"four_pillars": "four-pillars-of-learning",
	"searchand-explore": "searchand-explore",
	"all-faq": "all-faq",
	"extracurricular-activities": "extracurricular-activities",
	"vocational-courses": "vocational-courses",
	"entrance-test-prep": "entrance-test-prep",
	"ebooks": "ebooks",
}

# Default OG image: hero section image by page (static path), then site logo. Used when PageSEO.og_image is empty.
OG_HERO_IMAGE_BY_URL_KEY = {
	"about": "images_new/general/about-banner.svg",
	"career_planning": "images_new/careers/career-planning-banner.svg",
	"career_planning_4_year": "images_new/careers/career-planning-banner.svg",
	"career_planning_class_9": "images_new/careers/career-planning-banner.svg",
	"career_planning_class_10": "images_new/careers/career-planning-banner.svg",
	"career_planning_class_11": "images_new/careers/career-planning-banner.svg",
	"career_planning_class_12": "images_new/careers/career-planning-banner.svg",
	"emotional_intelligences": "images_new/general/career-direction-hero.png",
	"multiple_intelligences": "images_new/general/career-direction-hero.png",
	"four_pillars": "images_new/general/visinory-goal.svg",
	"all-faq": "images_new/general/faqs-img.svg",
	"extracurricular-activities": "images_new/general/visinory-goal.svg",
	"vocational-courses": "images_new/general/vocational-course.svg",
	"entrance-test-prep": "images_new/general/visinory-goal.svg",
	"ebooks": "images_new/ebook-hero-img.png",
	"searchand-explore": "images_new/careers/career-track.svg",
}
OG_SITE_LOGO_STATIC = "images_new/fav-icon/apple-icon-114x114.png"


def get_frontend_path_for_url_key(url_key):
	"""Return frontend path with leading slash for a given url_key (for Visit page link). Path-style keys (e.g. blogs/slug) use key as path."""
	if not url_key:
		return "/"
	if "/" in url_key:
		return "/" + url_key.strip("/")
	path = URL_KEY_TO_FRONTEND_PATH.get(url_key, url_key.replace("_", "-"))
	return "/" + path.strip("/")


def get_static_page_html_head(url_key, default_title, default_description, request=None):
	"""Build html_head for a static page: merge PageSEO if exists, else use defaults. Sets image and url for OG."""
	return get_page_seo_html_head(url_key, default_title, default_description, default_image=None, request=request)


def _get_default_og_image(url_key, request):
	"""Return absolute URL for default OG image: hero for url_key if mapped, else blog image for blogs/slug, else site logo."""
	if not request or not hasattr(request, "build_absolute_uri"):
		return None
	from django.templatetags.static import static
	# 1) Hero section image by url_key
	static_path = OG_HERO_IMAGE_BY_URL_KEY.get(url_key)
	if static_path:
		return request.build_absolute_uri(static(static_path))
	# 2) Blog post image for blogs/<slug>
	if url_key and url_key.startswith("blogs/"):
		try:
			from blog.models import Blog
			slug = url_key[6:].strip("/")
			blog = Blog.objects.filter(slug=slug).first()
			if blog and getattr(blog, "image", None) and blog.image:
				return request.build_absolute_uri(blog.image.url)
		except Exception:
			pass
	# 3) Site logo
	return request.build_absolute_uri(static(OG_SITE_LOGO_STATIC))


def get_page_seo_html_head(url_key, default_title, default_description, default_image=None, request=None):
	"""
	Build html_head for any page by url_key (e.g. static 'terms' or path 'blogs/24-jobs-that-will-never-disappear').
	If PageSEO exists for url_key, its title/description/keywords/og_image override defaults.
	When og_image is not set: use hero section image for page if mapped, else blog image for blogs/slug, else site logo.
	Sets url for OG when request is provided.
	"""
	from core.models import PageSEO
	head = build_html_head(title=default_title or "", description=default_description or "")
	if default_image:
		head["image"] = default_image
	try:
		seo = PageSEO.objects.filter(url_key=url_key).first()
		if seo:
			if seo.title:
				head["title"] = seo.title
			if seo.description:
				head["description"] = seo.description
			if seo.keywords:
				head["keywords"] = seo.keywords
			if seo.og_image:
				head["image"] = seo.og_image
	except Exception:
		pass
	if request and hasattr(request, "build_absolute_uri"):
		head["url"] = request.build_absolute_uri(request.path)
		if not head.get("image"):
			head["image"] = _get_default_og_image(url_key, request)
	return head

def wait_for_db():
    """Handle the command"""
    from django import db
    import time
    logger.info('Waiting for database...')
    db.close_old_connections()
    db_conn = None
    while not db_conn:
        try:
            db.connection.ensure_connection()
            db_conn = True
        except:
            logger.info('Database unavailable, waiting 1 second...')
            time.sleep(1)

    logger.info('Database available!')

def reformat_filename(filename):
    filename, file_extension = os.path.splitext(filename)
    timestr = time.strftime("%Y%m%d-%H%M%S")
    return 'cve{}{}'.format(timestr,file_extension)

def date_format(date):
    date = date.strftime("%d %b, %Y")
    return date

def clean_html(html):
    soup = BeautifulSoup(html, "html.parser") # create a new bs4 object from the html data loaded
    for script in soup(["script", "style"]): # remove all javascript and stylesheet code
        script.extract()
    # get text
    text = soup.get_text()
    # break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())
    # break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    return text

def remove_script_tag(html):
    soup = BeautifulSoup(html, "html.parser") # create a new bs4 object from the html data loaded
    soup.script.unwrap()
    return soup

def get_preferred_payment_gateway():
    """
    Get the preferred payment gateway based on environment configuration.
    Returns gateway choice with fallback logic:
    1. First tries ICICI Eazypay if configured and preference is set to 1 (ICICI_EAZYPAY)
    2. Falls back to Razorpay if ICICI Eazypay is not available/configured
    
    Note: PAYMENT_GATEWAY_PREFERENCE values:
    - 1 = ICICI_EAZYPAY (first preference)
    - 2 = RAZORPAY (fallback)
    """
    preference = getattr(settings, 'PAYMENT_GATEWAY_PREFERENCE', 1)
    icici_environment = getattr(settings, 'ICICI_EAZYPAY_ENVIRONMENT', 'sandbox')
    
    logger.debug("[Gateway Selection] PAYMENT_GATEWAY_PREFERENCE from settings: %s", preference)
    logger.debug("[Gateway Selection] ICICI_EAZYPAY_ENVIRONMENT: %s", icici_environment)
    
    # Check if ICICI Eazypay is preferred (preference = 1 means ICICI Eazypay)
    if preference == 1:  # ICICI Eazypay preference
        # Use the improved is_gateway_available function for consistent validation
        if is_gateway_available(choices.GatewayChoices.ICICIEAZYPAY):
            logger.debug("[Gateway Selection] Using ICICI Eazypay (credentials configured)")
            return choices.GatewayChoices.ICICIEAZYPAY
        else:
            merchant_id = getattr(settings, 'ICICI_EAZYPAY_MERCHANT_ID', '')
            encryption_key = getattr(settings, 'ICICI_EAZYPAY_ENCRYPTION_KEY', '')
            logger.debug(
                "[Gateway Selection] ICICI Eazypay (%s mode) - Merchant ID: %s, Encryption Key: %s",
                icici_environment,
                'SET' if merchant_id else 'EMPTY',
                'SET' if encryption_key else 'EMPTY',
            )
            logger.debug(
                "[Gateway Selection] ICICI Eazypay preferred but credentials not configured, falling back to Razorpay"
            )
    
    # Fallback to Razorpay (either preference is 2, or ICICI Eazypay is not configured)
    if is_gateway_available(choices.GatewayChoices.RAZORPAY):
        logger.debug("[Gateway Selection] Using Razorpay")
        return choices.GatewayChoices.RAZORPAY
    
    # If neither is configured, default to Razorpay (even if not configured)
    logger.warning("[Gateway Selection] No payment gateway properly configured, defaulting to Razorpay")
    return choices.GatewayChoices.RAZORPAY

def is_gateway_available(gateway_choice):
    """
    Check if a specific payment gateway is available and properly configured.
    """
    if gateway_choice == choices.GatewayChoices.ICICIEAZYPAY:
        merchant_id = getattr(settings, 'ICICI_EAZYPAY_MERCHANT_ID', '')
        encryption_key = getattr(settings, 'ICICI_EAZYPAY_ENCRYPTION_KEY', '')
        
        # Check that both are non-empty strings (after stripping whitespace)
        merchant_id = str(merchant_id).strip() if merchant_id else ''
        encryption_key = str(encryption_key).strip() if encryption_key else ''
        
        # AES keys must be 16, 24, or 32 bytes long
        if encryption_key:
            key_length = len(encryption_key.encode('utf-8'))
            valid_key_length = key_length in [16, 24, 32]
        else:
            valid_key_length = False
        
        return bool(merchant_id and encryption_key and valid_key_length)
    
    elif gateway_choice == choices.GatewayChoices.RAZORPAY:
        razorpay_key = getattr(settings, 'RAZORPAY_KEY', '')
        razorpay_secret = getattr(settings, 'RAZORPAY_SECRET', '')
        
        # Check that both are non-empty strings (after stripping whitespace)
        razorpay_key = str(razorpay_key).strip() if razorpay_key else ''
        razorpay_secret = str(razorpay_secret).strip() if razorpay_secret else ''
        
        return bool(razorpay_key and razorpay_secret)
    
    return False