from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse
from jinja2 import Environment, pass_context
from urllib.parse import urlencode
from django.conf import settings
from django.utils.safestring import mark_safe
from django.templatetags.static import static
from django.contrib.humanize.templatetags.humanize import intcomma
from datetime import datetime
from django.utils import timezone
from django.middleware.csrf import get_token
from django.utils.html import format_html, escapejs
import re
import json
from app.templatetags.myfilters_extras import my_url
# from shop.models import Category
from django.utils.timezone import template_localtime
from core.seo_schema import get_breadcrumb_schema, get_webpage_schema, get_faq_schema

def get_item(dictionary, key):
    try:
        return dictionary.get(key)
    except Exception:
        return None


def starts_with_bullet(value):
    try:
        return str(value).startswith('•')
    except Exception:
        return False


_APTITUDE_REMARK_PHRASE_FIXES = (
    (re.compile(r'—with\s+ease\b', re.I), '—with\u00a0ease'),
    (re.compile(r'\bwith\s+ease\b', re.I), 'with\u00a0ease'),
)


def aptitude_remark_text(value):
    text = str(value or '')
    for pattern, replacement in _APTITUDE_REMARK_PHRASE_FIXES:
        text = pattern.sub(replacement, text)
    return text


def test_display_title_filter(value):
    from app_post_matric.test_display_labels import test_display_title
    return test_display_title(value)

def img_tag(*args,**kwargs):
    src = kwargs['src']
    # print("src",type(src))
    size = kwargs['size']
    width=size.split('/')[0]
    height=size.split('/')[1]
    url_only=False

    url =""
    if settings.DEBUG:
        url = src
    else:
        url = src
    if 'url_only' in kwargs and kwargs['url_only']:
        return url

    class_name=kwargs.get('class_name',"")
    alt = kwargs.get('alt','Photo')
    
    full_tag= "<img alt='{}' src='{}' class='{}' width='{}px' height='{}px' style='width:{}px;' >".format(alt,url,class_name,width,height,width)
    return mark_safe(full_tag)


def staticv(path: str) -> str:
    """
    Static URL with a per-request cache buster.
    Use sparingly (e.g., dashboards) when StaticFilesStorage is used and browsers cache aggressively.
    """
    try:
        base = staticfiles_storage.url(path)
    except Exception:
        base = static(path)
    try:
        v = str(int(timezone.now().timestamp()))
    except Exception:
        v = str(int(datetime.now().timestamp()))
    sep = "&" if ("?" in base) else "?"
    return f"{base}{sep}v={v}"


one = ["", "one ", "two ", "three ", "four ",
       "five ", "six ", "seven ", "eight ",
       "nine ", "ten ", "eleven ", "twelve ",
       "thirteen ", "fourteen ", "fifteen ",
       "sixteen ", "seventeen ", "eighteen ",
       "nineteen "];

# strings at index 0 and 1 are not used,
# they is to make array indexing simple
ten = ["", "", "twenty ", "thirty ", "forty ",
       "fifty ", "sixty ", "seventy ", "eighty ",
       "ninety "];
# n is 1- or 2-digit number
def numToWords(n, s):
    str = "";

    # if n is more than 19, divide it
    if (n > 19):
        str += ten[n // 10] + one[n % 10];
    else:
        str += one[n];

        # if n is non-zero
    if (n):
        str += s;

    return str;


def convertToWords(n):
    # stores word representation of given
    # number n
    import math
    n = math.floor(n)
    out = "";

    # handles digits at ten millions and
    # hundred millions places (if any)
    out += numToWords((n // 10000000),
                      "crore ");

    # handles digits at hundred thousands
    # and one millions places (if any)
    out += numToWords(((n // 100000) % 100),
                      "lakh ");

    # handles digits at thousands and tens
    # thousands places (if any)
    out += numToWords(((n // 1000) % 100),
                      "thousand ");

    # handles digit at hundreds places (if any)
    out += numToWords(((n // 100) % 10),
                      "hundred ");

    if (n > 100 and n % 100):
        out += "and ";

        # handles digits at ones and tens
    # places (if any)
    out += numToWords((n % 100), "");

    return out;

def currency_format(price,inr=True):
    if inr:
        return "{} {}".format('₹',intcomma(price))
    return "{} {}".format(settings.CURRENCY_SYMBOL,intcomma(price))

def date_format(date_obj):
    return date_obj.strftime('%b %d, %Y')

def time_format(time_obj):
    return time_obj.strftime("%I:%M:%S %p")

def localtime(time):
    return timezone.localtime(time).strftime("%b %d, %Y %I:%M %p")

def format_duration(string): 
    try:
        if not string:
            return '-'
        dur=int(string)
        if dur==1:
            return '1 Year'
        elif dur<=5:
            return str(dur)+' Years'
        else:
            return str(dur)+' Months'
    except:
        dur=int(re.search(r'\d+', string).group())
        if dur==1:
            return string.strip('s')
        else:
            return string
def checkinstance(obj, cls):
    try:
        return isinstance(obj, cls)
    except Exception:
        return False

def seo_year(request):
    abv= globals(request)
    return abv['seo_year']
def custom_reverse(viewname, *args, **kwargs):
    """
    Backwards-compatible reverse helper used by older templates as `url_()`.
    Historically some templates call: url_('view', args=[...]) which is NOT a valid
    `django.urls.reverse()` signature. Normalize those inputs here.
    """
    # Old style: url_('view', args=[...])
    if 'args' in kwargs:
        args_value = kwargs.pop('args')
        if isinstance(args_value, (list, tuple)):
            args = tuple(args_value)
        elif args_value is None:
            args = tuple(args)
        else:
            args = tuple([args_value])
    # Old style: url_('view', kwargs={...})
    if 'kwargs' in kwargs:
        kw = kwargs.pop('kwargs') or {}
        if isinstance(kw, dict):
            # Don't clobber explicit kwargs passed alongside
            for k, v in kw.items():
                kwargs.setdefault(k, v)
    return reverse(viewname, args=args, kwargs=kwargs)

def jinja_url(viewname, *args, **kwargs):
    """Jinja2-compatible URL function that accepts args and kwargs like Django's url tag
    
    Supports multiple calling styles:
    - url('viewname', slug='value')  # Keyword arguments directly
    - url('viewname', 'arg1', 'arg2')  # Positional arguments
    - url('viewname', args=['arg1'])  # Old style with args as keyword
    - url('viewname', kwargs={'slug': 'value'})  # Old style with kwargs as keyword
    - url('viewname', ['arg1'], {'slug': 'value'})  # Old style with args and kwargs as positional
    """
    url_kwargs = {}
    url_args = []
    
    # Handle old style: args and kwargs passed as keyword arguments
    # e.g., url('viewname', args=['slug'], kwargs={'key': 'value'})
    if 'args' in kwargs:
        args_value = kwargs.pop('args')
        url_args = list(args_value) if isinstance(args_value, (list, tuple)) else [args_value]
    if 'kwargs' in kwargs:
        kwargs_value = kwargs.pop('kwargs')
        url_kwargs = kwargs_value.copy() if isinstance(kwargs_value, dict) else {}
    
    # Check if this is the old style call with args and kwargs as separate positional parameters
    if len(args) == 2:
        first_arg, second_arg = args
        # Old style: url('viewname', [], {'slug': 'value'})
        if isinstance(first_arg, (list, tuple)) and isinstance(second_arg, dict):
            url_args = list(first_arg)
            url_kwargs = second_arg.copy()
        # Old style: url('viewname', {'slug': 'value'})
        elif isinstance(first_arg, dict):
            url_kwargs = first_arg.copy()
        else:
            # Positional arguments
            url_args = list(args)
    elif len(args) == 1:
        first_arg = args[0]
        # Old style: url('viewname', {'slug': 'value'})
        if isinstance(first_arg, dict):
            url_kwargs = first_arg.copy()
        elif isinstance(first_arg, (list, tuple)):
            # Old style: url('viewname', ['arg1'])
            url_args = list(first_arg)
        else:
            # Single positional argument
            url_args = [first_arg]
    elif args:
        # Multiple positional arguments
        url_args = list(args)
    
    # Merge any remaining keyword arguments passed directly (new style)
    url_kwargs.update(kwargs)
    
    return reverse(viewname, args=url_args, kwargs=url_kwargs)

@pass_context
def csrf_input(context):
    """Generate CSRF token input field for Jinja2 templates"""
    # Try multiple ways to access request from context
    request = None
    if hasattr(context, 'get'):
        request = context.get('request')
    elif hasattr(context, 'request'):
        request = context.request
    elif 'request' in context:
        request = context['request']
    
    if request:
        token = get_token(request)
        return format_html(
            '<input type="hidden" name="csrfmiddlewaretoken" value="{}">',
            token,
        )
    return ''

@pass_context  
def csrf_token_value(context):
    """Get CSRF token value for Jinja2 templates (for JavaScript usage)"""
    # Try multiple ways to access request from context
    request = None
    if hasattr(context, 'get'):
        request = context.get('request')
    elif hasattr(context, 'request'):
        request = context.request
    elif 'request' in context:
        request = context['request']
    
    if request:
        return get_token(request)
    return ''

def tojson_filter(value):
    """Convert Python object to JSON string"""
    return mark_safe(json.dumps(value))


def tojson_for_script(value):
    """JSON safe inside <script> tags (avoids premature </script> / markup issues)."""
    s = json.dumps(value, ensure_ascii=False, default=str)
    s = s.translate(str.maketrans({"<": "\\u003c", ">": "\\u003e"}))
    return mark_safe(s)


def tojson_pretty(value, indent=2):
    """Convert Python object to well-formatted JSON (for JSON-LD schema in HTML)."""
    return mark_safe(json.dumps(value, indent=indent, ensure_ascii=False))

def urlencode_filter(value):
    """URL encode a string"""
    from urllib.parse import quote
    return quote(str(value), safe='')

def get_url(obj):
    """Get URL from object - handles both Elasticsearch documents (url attribute) and Django models (url() method)"""
    if hasattr(obj, 'url'):
        url_attr = getattr(obj, 'url')
        if callable(url_attr):
            return url_attr()
        else:
            return url_attr
    return '#'


def paginate_url(request, page=None, per_page=None):
    """Build URL with GET params, applying page/per_page overrides. Used for pagination links."""
    params = request.GET.copy()
    if page is not None:
        params['page'] = str(page)
    if per_page is not None:
        params['per_page'] = str(per_page)
    qs = urlencode(params)
    return request.path + ('?' + qs if qs else '')


def blog_category_display(name):
    """Display label for blog category: 'Blogs for Parents' / 'Blogs for Students'."""
    if not name:
        return name
    s = (name or '').strip()
    if s in ('Blogs in For Parents', 'For Parents'):
        return 'Blogs for Parents'
    if s in ('Blogs in For Students', 'For Students'):
        return 'Blogs for Students'
    return name


def blog_category_short(name):
    """Short form for 'Explore blogs X category': 'For Parents' / 'For Students'."""
    if not name:
        return name
    s = (name or '').strip()
    if s in ('Blogs in For Parents', 'For Parents'):
        return 'For Parents'
    if s in ('Blogs in For Students', 'For Students'):
        return 'For Students'
    return name


def environment(**options):
    from django.utils.html import escapejs as _escapejs
    # Import custom loader that skips admin templates
    from topteens.jinja2_loader import get_jinja2_loader

    # Always use our custom loader that skips admin templates
    # This ensures admin templates are never loaded by Jinja2
    options['loader'] = get_jinja2_loader()

    env = Environment(**options)
    # Register escapejs first (required by course_learning.html and other Jinja templates)
    env.filters['escapejs'] = _escapejs
    env.filters['get_item'] = get_item
    env.filters['starts_with_bullet'] = starts_with_bullet
    env.filters['aptitude_remark_text'] = aptitude_remark_text
    env.filters['test_display_title'] = test_display_title_filter
    env.filters['tojson'] = tojson_filter
    env.filters['tojson_for_script'] = tojson_for_script
    env.filters['tojson_pretty'] = tojson_pretty
    env.filters['urlencode'] = urlencode_filter
    env.filters['blog_category_display'] = blog_category_display
    env.filters['blog_category_short'] = blog_category_short
    from core.templatetags.activity_tags import inject_activity_ids, get_all_sections
    env.filters['inject_activity_ids'] = inject_activity_ids
    env.filters['get_all_sections'] = get_all_sections
    # changes required by management (01-Jun-2025): Below Average → Development Areas (aptitude_tier_label filter)
    from app_post_matric.aptitude_area_labels import (
        aptitude_tier_label,
        aptitude_development_alert_body,
        APTITUDE_DEVELOPMENT_ALERT_TITLE,
        APTITUDE_VOCATIONAL_SECTION_TITLE,
        APTITUDE_NO_DEVELOPMENT_AREAS,
        APTITUDE_EMPTY_STATE_SKILL_AREAS,
        APTITUDE_IMPROVEMENT_NOTE,
    )
    env.filters['aptitude_tier_label'] = aptitude_tier_label
    env.filters['aptitude_development_alert_body'] = aptitude_development_alert_body
    # expose master_classes() helper (returns list of {'value','label'}) to Jinja templates
    try:
        from core.context_processors import master_classes as _master_classes_fn
    except Exception:
        _master_classes_fn = lambda request=None: [{"value": v, "label": f"Class {v}"} for v in range(12, 5, -1)]

    env.globals.update({
        'master_classes': _master_classes_fn,
        'static': staticfiles_storage.url,
        'staticv': staticv,
        'url': jinja_url,
        'url_': custom_reverse,
        'img_tag':img_tag,
        'MEDIA_URL': settings.MEDIA_URL,
        'now':datetime.now(),
        'convert_to_words':convertToWords,
        'currency_format':currency_format,
        'date_format':date_format,
        'intcomma': intcomma,
        'time_format':time_format,
        'localtime': localtime,
        'format_duration':format_duration,
        'DEBUG':settings.DEBUG,
        'checkinstance':checkinstance,
        'seo_year':seo_year,
        'my_url': my_url,
        'csrf_input': csrf_input,
        'csrf_input_tag': csrf_input,  # alias to avoid context shadowing (e.g. __proxy__)
        'csrf_token': csrf_token_value,
        'get_url': get_url,
        'paginate_url': paginate_url,
        # SEO JSON-LD schema builders (for use in templates)
        'get_breadcrumb_schema': get_breadcrumb_schema,
        'get_webpage_schema': get_webpage_schema,
        'get_faq_schema': get_faq_schema,
        # changes required by management (01-Jun-2025): Below Average → professional aptitude copy
        'aptitude_development_alert_title': APTITUDE_DEVELOPMENT_ALERT_TITLE,
        'aptitude_vocational_section_title': APTITUDE_VOCATIONAL_SECTION_TITLE,
        'aptitude_no_development_areas': APTITUDE_NO_DEVELOPMENT_AREAS,
        'aptitude_empty_state_skill_areas': APTITUDE_EMPTY_STATE_SKILL_AREAS,
        'aptitude_improvement_note': APTITUDE_IMPROVEMENT_NOTE,
    })
    return env