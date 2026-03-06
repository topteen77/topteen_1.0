"""
Utility functions for user analytics.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Traffic source categories for reporting (search, social, referral, direct)
TRAFFIC_SOURCE_SEARCH = 'search'
TRAFFIC_SOURCE_SOCIAL = 'social'
TRAFFIC_SOURCE_REFERRAL = 'referral'
TRAFFIC_SOURCE_DIRECT = 'direct'
TRAFFIC_SOURCE_INTERNAL = 'internal'


def get_traffic_source_category(utm_source, referrer):
    """
    Categorize traffic source for reporting: search, social, referral, direct.
    
    Args:
        utm_source: UTM source (or derived source from referrer)
        referrer: HTTP referrer string
        
    Returns:
        str: One of 'search', 'social', 'referral', 'direct', 'internal'
    """
    source = (utm_source or '').lower().strip()
    ref = (referrer or '').lower()
    
    if not source and not referrer:
        return TRAFFIC_SOURCE_DIRECT
    if 'internal' in source or (referrer and 'topteen' in ref):
        return TRAFFIC_SOURCE_INTERNAL
    
    # Search engines
    search_sources = ('google', 'bing', 'yahoo', 'duckduckgo', 'baidu', 'yandex', 'ecosia')
    if any(s in source for s in search_sources):
        return TRAFFIC_SOURCE_SEARCH
    
    # Social media (by source name or referrer)
    social_sources = ('facebook', 'twitter', 'instagram', 'linkedin', 'youtube', 'pinterest', 'tiktok', 'whatsapp', 'telegram', 'reddit', 'x.com')
    if any(s in source for s in social_sources):
        return TRAFFIC_SOURCE_SOCIAL
    if referrer and any(s in ref for s in social_sources):
        return TRAFFIC_SOURCE_SOCIAL
    
    if not referrer or not source:
        return TRAFFIC_SOURCE_DIRECT
    return TRAFFIC_SOURCE_REFERRAL


def get_geolocation_from_ip(ip_address, timeout=2):
    """
    Resolve country and city from IP using a free API (ip-api.com).
    Used in async/sync tracking tasks; never blocks the HTTP request.
    
    ip-api.com: 45 req/min free, no key required. Returns country, regionName, city.
    
    Args:
        ip_address: Client IP (e.g. from REMOTE_ADDR or X-Forwarded-For)
        timeout: Request timeout in seconds
        
    Returns:
        dict: {'country': str, 'city': str} or empty dict on failure/invalid IP
    """
    if not ip_address or str(ip_address).strip() in ('', '127.0.0.1', '::1'):
        return {}
    ip = str(ip_address).strip()
    try:
        import requests
        r = requests.get(
            f'http://ip-api.com/json/{ip}?fields=status,country,regionName,city',
            timeout=timeout
        )
        if r.status_code != 200:
            return {}
        data = r.json()
        if data.get('status') != 'success':
            return {}
        return {
            'country': (data.get('country') or '').strip() or None,
            'city': (data.get('city') or data.get('regionName') or '').strip() or None,
        }
    except Exception as e:
        logger.debug("Geolocation lookup failed for %s: %s", ip, e)
        return {}


def parse_user_agent_info(user_agent_string):
    """
    Parse user agent string to extract device, browser, and OS information.
    
    Args:
        user_agent_string: User agent string from request
        
    Returns:
        dict: Contains device_type, browser, os
    """
    if not user_agent_string:
        return {
            'device_type': 'unknown',
            'browser': 'unknown',
            'os': 'unknown'
        }
    
    # Simple user agent parsing without external library
    # Check tablet before mobile (e.g. iPad has "Mobile" in UA but is tablet)
    user_agent_lower = user_agent_string.lower()
    
    device_type = 'desktop'
    if 'tablet' in user_agent_lower or 'ipad' in user_agent_lower or 'playbook' in user_agent_lower or 'kindle' in user_agent_lower:
        device_type = 'tablet'
    elif 'mobile' in user_agent_lower or 'android' in user_agent_lower:
        device_type = 'mobile'
    elif 'iphone' in user_agent_lower or 'ipod' in user_agent_lower:
        device_type = 'mobile'
    
    browser = 'unknown'
    if 'chrome' in user_agent_lower:
        browser = 'Chrome'
    elif 'firefox' in user_agent_lower:
        browser = 'Firefox'
    elif 'safari' in user_agent_lower:
        browser = 'Safari'
    elif 'edge' in user_agent_lower:
        browser = 'Edge'
    
    os = 'unknown'
    if 'windows' in user_agent_lower:
        os = 'Windows'
    elif 'mac' in user_agent_lower or 'darwin' in user_agent_lower:
        os = 'macOS'
    elif 'linux' in user_agent_lower:
        os = 'Linux'
    elif 'android' in user_agent_lower:
        os = 'Android'
    elif 'ios' in user_agent_lower or 'iphone' in user_agent_lower:
        os = 'iOS'
    
    return {
        'device_type': device_type,
        'browser': browser,
        'os': os
    }


def extract_utm_params(request):
    """
    Extract UTM parameters from request.
    
    Args:
        request: Django request object
        
    Returns:
        dict: UTM parameters
    """
    return {
        'utm_source': request.GET.get('utm_source', ''),
        'utm_medium': request.GET.get('utm_medium', ''),
        'utm_campaign': request.GET.get('utm_campaign', ''),
        'utm_term': request.GET.get('utm_term', ''),
        'utm_content': request.GET.get('utm_content', ''),
    }


def get_referrer_source(referrer):
    """
    Determine traffic source from referrer.
    
    Args:
        referrer: HTTP referrer string
        
    Returns:
        str: Source name (e.g., 'google', 'facebook', 'direct')
    """
    if not referrer:
        return 'direct'
    
    referrer_lower = referrer.lower()
    
    # Search engines
    if 'google' in referrer_lower:
        return 'google'
    elif 'bing' in referrer_lower:
        return 'bing'
    elif 'yahoo' in referrer_lower:
        return 'yahoo'
    elif 'duckduckgo' in referrer_lower:
        return 'duckduckgo'
    
    # Social media
    elif 'facebook' in referrer_lower:
        return 'facebook'
    elif 'twitter' in referrer_lower or 'x.com' in referrer_lower:
        return 'twitter'
    elif 'linkedin' in referrer_lower:
        return 'linkedin'
    elif 'instagram' in referrer_lower:
        return 'instagram'
    elif 'youtube' in referrer_lower:
        return 'youtube'
    
    # Partner / other known sites
    elif 'iapply.io' in referrer_lower or 'iapply.' in referrer_lower:
        return 'iapply'
    elif 'topteen' in referrer_lower:
        return 'internal'
    else:
        # Extract domain from referrer
        match = re.search(r'https?://([^/]+)', referrer)
        if match:
            return match.group(1)
        return 'other'


def referrer_source_q(source):
    """
    Return a Django Q object to filter UserActivity or UserJourney by referrer source.
    Use: UserActivity.objects.filter(referrer_source_q('google'))

    Supported sources: 'google', 'facebook', 'iapply' (or 'iapply.io').
    Other sources match utm_source or referrer containing the string.
    """
    from django.db.models import Q
    source = (source or '').strip().lower()
    if source == 'google':
        return Q(utm_source__iexact='google') | Q(referrer__icontains='google')
    if source == 'facebook':
        return Q(utm_source__iexact='facebook') | Q(referrer__icontains='facebook')
    if source in ('iapply', 'iapply.io'):
        return Q(utm_source__iexact='iapply') | Q(referrer__icontains='iapply.io')
    return Q(utm_source__iexact=source) | Q(utm_source__icontains=source) | Q(referrer__icontains=source)


def calculate_session_duration(start_time, end_time):
    """
    Calculate session duration in seconds.
    
    Args:
        start_time: Session start datetime
        end_time: Session end datetime
        
    Returns:
        int: Duration in seconds
    """
    if not start_time or not end_time:
        return 0
    
    delta = end_time - start_time
    return int(delta.total_seconds())


def format_currency(amount, currency='INR'):
    """
    Format currency amount for display.
    
    Args:
        amount: Decimal amount
        currency: Currency code (default: INR)
        
    Returns:
        str: Formatted currency string
    """
    if currency == 'INR':
        return f"₹{amount:,.2f}"
    else:
        return f"${amount:,.2f}"
