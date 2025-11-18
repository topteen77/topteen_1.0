from django.db.models import Q
from core import choices
from django.conf import settings

from threading import local
import time
import os
from datetime import datetime
from bs4 import BeautifulSoup
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

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def sort_colleges(colleges,request):
    return colleges

def build_breadcrumb(list_of_dict):
	lst = []
	home={}
	home['title']="Home"
	home['url'] = '/'
	home['text'] = "Home"
	lst.append(home)
	lst.extend(list_of_dict)
	return lst

def build_html_head(**kwargs):
	return kwargs

def wait_for_db():
    """Handle the command"""
    from django import db
    import time
    print('Waiting for database...')
    db.close_old_connections()
    db_conn = None
    while not db_conn:
        try:
            db.connection.ensure_connection()
            db_conn = True
        except:
            print('Database unavailable, waiting 1 second...')
            time.sleep(1)

    print('Database available!')

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
    
    print(f"[Gateway Selection] PAYMENT_GATEWAY_PREFERENCE from settings: {preference}")
    print(f"[Gateway Selection] ICICI_EAZYPAY_ENVIRONMENT: {icici_environment}")
    
    # Check if ICICI Eazypay is preferred (preference = 1 means ICICI Eazypay)
    if preference == 1:  # ICICI Eazypay preference
        merchant_id = getattr(settings, 'ICICI_EAZYPAY_MERCHANT_ID', '')
        encryption_key = getattr(settings, 'ICICI_EAZYPAY_ENCRYPTION_KEY', '')
        
        print(f"[Gateway Selection] ICICI Eazypay ({icici_environment} mode) - Merchant ID: {'SET' if merchant_id else 'EMPTY'}, Encryption Key: {'SET' if encryption_key else 'EMPTY'}")
        
        # If ICICI Eazypay is properly configured, use it
        if merchant_id and encryption_key:
            print("[Gateway Selection] Using ICICI Eazypay (credentials configured)")
            return choices.GatewayChoices.ICICIEAZYPAY
        else:
            print("[Gateway Selection] ICICI Eazypay preferred but credentials not configured, falling back to Razorpay")
    
    # Fallback to Razorpay (either preference is 2, or ICICI Eazypay is not configured)
    razorpay_key = getattr(settings, 'RAZORPAY_KEY', '')
    razorpay_secret = getattr(settings, 'RAZORPAY_SECRET', '')
    
    print(f"[Gateway Selection] Razorpay - Key: {'SET' if razorpay_key else 'EMPTY'}, Secret: {'SET' if razorpay_secret else 'EMPTY'}")
    
    if razorpay_key and razorpay_secret:
        print("[Gateway Selection] Using Razorpay")
        return choices.GatewayChoices.RAZORPAY
    
    # If neither is configured, default to Razorpay
    print("[Gateway Selection] Defaulting to Razorpay (no gateway configured)")
    return choices.GatewayChoices.RAZORPAY

def is_gateway_available(gateway_choice):
    """
    Check if a specific payment gateway is available and properly configured.
    """
    if gateway_choice == choices.GatewayChoices.ICICIEAZYPAY:
        merchant_id = getattr(settings, 'ICICI_EAZYPAY_MERCHANT_ID', '')
        encryption_key = getattr(settings, 'ICICI_EAZYPAY_ENCRYPTION_KEY', '')
        return bool(merchant_id and encryption_key)
    
    elif gateway_choice == choices.GatewayChoices.RAZORPAY:
        razorpay_key = getattr(settings, 'RAZORPAY_KEY', '')
        razorpay_secret = getattr(settings, 'RAZORPAY_SECRET', '')
        return bool(razorpay_key and razorpay_secret)
    
    return False