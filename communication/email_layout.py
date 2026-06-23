"""Shared header/footer wrapper for all transactional emails."""

import logging
import re
from datetime import datetime

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

BASE_LAYOUT_MARKER = 'data-topteen-email-layout="1"'
BASE_EMAIL_TEMPLATE = 'mail/base_email.html'

DEFAULT_SITE_URL = 'https://www.topteen.in'
DEFAULT_LOGO_URL = 'https://www.topteen.in/static/images_new/logos/logo.svg'
DEFAULT_SUPPORT_EMAIL = 'support@topteen.careers'


def is_email_layout_wrapped(html):
    return BASE_LAYOUT_MARKER in (html or '')


def _email_logo_url():
    return (
        getattr(settings, 'TOPTEEN_EMAIL_LOGO_URL', None)
        or getattr(settings, 'LOGO_URL', None)
        or DEFAULT_LOGO_URL
    )


def _email_site_url():
    return (
        getattr(settings, 'TOPTEEN_SITE_URL', None)
        or getattr(settings, 'SITE_URL', None)
        or DEFAULT_SITE_URL
    ).rstrip('/')


def normalize_email_inner_body(html):
    """
    Reduce legacy full-document mail templates to content-only HTML.

    Admin rows or old built-in files may still store complete HTML documents
    with their own header/footer. Strip those so the shared base layout applies.
    """
    content = (html or '').strip()
    if not content or is_email_layout_wrapped(content):
        return content

    lowered = content.lower()
    if '<!doctype' in lowered or '<html' in lowered or 'class="body"' in lowered:
        marker_match = re.search(
            r'<!--\s*begin:Email content\s*-->(.*?)<!--\s*end:Email content\s*-->',
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if marker_match:
            content = marker_match.group(1).strip()
        else:
            main_match = re.search(
                r'<!--\s*START MAIN CONTENT AREA\s*-->(.*?)<!--\s*END MAIN CONTENT AREA\s*-->',
                content,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if main_match:
                block = main_match.group(1)
                td_match = re.search(
                    r'<td[^>]*style="[^"]*font-family:\s*sans-serif[^"]*"[^>]*>(.*)</td>',
                    block,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                content = (td_match.group(1) if td_match else block).strip()

    # Remove legacy per-template footers/headers if they remain.
    content = re.sub(
        r'<div[^>]*class="footer"[^>]*>.*?</div>',
        '',
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    content = re.sub(
        r'<tr>\s*<td[^>]*>\s*<p>\s*Copyright.*?</tr>',
        '',
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    content = re.sub(
        r'<span[^>]*class="apple-link"[^>]*>.*?</span>',
        '',
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    content = re.sub(r'Kind regards,.*?TOPTEEN Team\.?', '', content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r'©\s*Top\s*Teen.*', '', content, flags=re.IGNORECASE | re.DOTALL)

    # Drop outer legacy layout wrappers when content was pasted from an old invite mail.
    if '<table align="center"' in content and 'background-color:#edf2f7' in content.replace(' ', ''):
        inner_div = re.search(
            r'<div style="[^"]*background-color:#ffffff[^"]*"[^>]*>(.*)</div>\s*</td>',
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if inner_div:
            content = inner_div.group(1).strip()

    return content.strip()


def wrap_email_layout(email_body, preheader=''):
    """Wrap inner email HTML with the shared TopTeen header and footer."""
    inner = normalize_email_inner_body(email_body)
    if not inner:
        return inner
    if is_email_layout_wrapped(inner):
        return inner

    site_url = _email_site_url()
    logo_url = _email_logo_url()
    support_email = getattr(settings, 'TOPTEEN_SUPPORT_EMAIL', DEFAULT_SUPPORT_EMAIL)
    preheader_text = strip_tags(preheader or '')[:140]
    context = {
        'email_body': inner,
        'preheader': preheader_text,
        'site_url': site_url,
        'logo_url': logo_url,
        'support_email': support_email,
        'year': datetime.now().year,
    }

    for engine in ('django', None):
        try:
            if engine:
                html = render_to_string(BASE_EMAIL_TEMPLATE, context, using=engine)
            else:
                html = render_to_string(BASE_EMAIL_TEMPLATE, context)
            if html and is_email_layout_wrapped(html):
                return html
        except Exception as exc:
            logger.warning('Email base layout render failed (engine=%s): %s', engine, exc)

    logger.error('Email base layout could not be rendered; sending content without wrapper.')
    return inner


def ensure_email_html_wrapped(html_content, preheader=''):
    """Final safety net used by ComService.send_mail."""
    content = (html_content or '').strip()
    if not content:
        return content
    if is_email_layout_wrapped(content):
        return content
    return wrap_email_layout(content, preheader=preheader)
