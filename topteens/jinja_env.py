from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse
from jinja2 import Environment, pass_context
from django.conf import settings
from django.utils.safestring import mark_safe
from django.templatetags.static import static
from django.contrib.humanize.templatetags.humanize import intcomma
from datetime import datetime
from django.utils import timezone
from django.middleware.csrf import get_token
from django.utils.html import format_html
import re
import json
from app.templatetags.myfilters_extras import my_url
# from shop.models import Category
from django.utils.timezone import template_localtime

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
def checkinstance(obj,cls):
    
    try:
        print(obj.__dict__)
    except:
        pass
    return True
    print(obj.field.__dict__)
    return isinstance(obj,cls)

def seo_year(request):
    abv= globals(request)
    return abv['seo_year']
def custom_reverse(viewname, *args, **kwargs):
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

def environment(**options):
    # Import custom loader that skips admin templates
    from topteens.jinja2_loader import get_jinja2_loader
    
    # Always use our custom loader that skips admin templates
    # This ensures admin templates are never loaded by Jinja2
    options['loader'] = get_jinja2_loader()
    
    env = Environment(**options)
    
    # Add filters
    env.filters['tojson'] = tojson_filter
    env.filters['urlencode'] = urlencode_filter
    from core.templatetags.activity_tags import inject_activity_ids, get_all_sections
    env.filters['inject_activity_ids'] = inject_activity_ids
    env.filters['get_all_sections'] = get_all_sections
    
    env.globals.update({
        'static': staticfiles_storage.url,
        'url': jinja_url,
        'url_':custom_reverse,
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
        'csrf_token': csrf_token_value,
        'get_url': get_url,
    })
    return env