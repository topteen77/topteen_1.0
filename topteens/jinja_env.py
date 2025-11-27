from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse
from jinja2 import Environment
from django.conf import settings
from django.utils.safestring import mark_safe
from django.templatetags.static import static
from django.contrib.humanize.templatetags.humanize import intcomma
from datetime import datetime
from django.utils import timezone
from django.middleware.csrf import get_token
from django.utils.html import format_html
import re
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

def csrf_input(request=None):
    """Generate CSRF token input field for Jinja2 templates"""
    # If request is provided, use it; otherwise try to get from context
    if request:
        token = get_token(request)
        return format_html(
            '<input type="hidden" name="csrfmiddlewaretoken" value="{}">',
            token,
        )
    # Fallback: return empty string if no request
    return ''

def environment(**options):
    env = Environment(**options)
    
    env.globals.update({
        'static': staticfiles_storage.url,
        'url': reverse,
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
    })
    return env