"""
Utility functions for user analytics.
"""
import re


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
    user_agent_lower = user_agent_string.lower()
    
    device_type = 'desktop'
    if 'mobile' in user_agent_lower or 'android' in user_agent_lower:
        device_type = 'mobile'
    elif 'tablet' in user_agent_lower or 'ipad' in user_agent_lower:
        device_type = 'tablet'
    
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
    
    # Other
    elif 'topteen' in referrer_lower:
        return 'internal'
    else:
        # Extract domain from referrer
        match = re.search(r'https?://([^/]+)', referrer)
        if match:
            return match.group(1)
        return 'other'


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
