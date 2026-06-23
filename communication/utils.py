"""Helpers for communication app."""

import re


def mysql_text_safe(value):
    """
    Encode characters outside the MySQL utf8mb3 range as HTML entities.

    Legacy utf8 columns reject 4-byte UTF-8 (e.g. emojis). utf8mb4 columns
    accept the original string unchanged.
    """
    if value is None:
        return value
    if not isinstance(value, str):
        value = str(value)
    parts = []
    for char in value:
        if ord(char) <= 0xFFFF:
            parts.append(char)
        else:
            parts.append('&#{};'.format(ord(char)))
    return ''.join(parts)


def invitee_name_from_email(email):
    """Derive a friendly greeting name from the invitee email local part."""
    email = (email or '').strip()
    if not email or '@' not in email:
        return 'there'
    local = email.split('@', 1)[0]
    local = re.sub(r'[._+\-]+', ' ', local).strip()
    if not local:
        return 'there'
    return local.title()


def referral_url_without_scheme(url):
    """Strip http/https so CKEditor links like http://{referral_url} work correctly."""
    url = (url or '').strip()
    lower = url.lower()
    if lower.startswith('https://'):
        return url[8:]
    if lower.startswith('http://'):
        return url[7:]
    return url
