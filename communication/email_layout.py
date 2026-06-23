"""Shared header/footer wrapper for all transactional emails."""

from datetime import datetime

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

BASE_LAYOUT_MARKER = 'data-topteen-email-layout="1"'
BASE_EMAIL_TEMPLATE = 'mail/base_email.html'

DEFAULT_SITE_URL = 'https://www.topteen.in'
DEFAULT_LOGO_URL = 'https://www.topteen.in/static/images/logos/topteen-logo-with-text.png'


def is_email_layout_wrapped(html):
    return BASE_LAYOUT_MARKER in (html or '')


def wrap_email_layout(email_body, preheader=''):
    """Wrap inner email HTML with the shared TopTeen header and footer."""
    inner = (email_body or '').strip()
    if not inner or is_email_layout_wrapped(inner):
        return inner

    site_url = getattr(settings, 'TOPTEEN_SITE_URL', None) or DEFAULT_SITE_URL
    logo_url = getattr(settings, 'TOPTEEN_EMAIL_LOGO_URL', None) or DEFAULT_LOGO_URL
    preheader_text = strip_tags(preheader or '')[:140]

    return render_to_string(
        BASE_EMAIL_TEMPLATE,
        {
            'email_body': inner,
            'preheader': preheader_text,
            'site_url': site_url.rstrip('/'),
            'logo_url': logo_url,
            'year': datetime.now().year,
        },
    )
