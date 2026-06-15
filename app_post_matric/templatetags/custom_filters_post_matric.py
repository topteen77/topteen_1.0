import re

from django import template

register = template.Library()

_APTITUDE_REMARK_PHRASE_FIXES = (
    (re.compile(r'—with\s+ease\b', re.I), '—with\u00a0ease'),
    (re.compile(r'\bwith\s+ease\b', re.I), 'with\u00a0ease'),
)


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def starts_with_bullet(value):
    return value.startswith('•')


@register.filter
def aptitude_remark_text(value):
    """Keep short trailing phrases (e.g. 'with ease') on the same line in aptitude narratives."""
    text = str(value or '')
    for pattern, replacement in _APTITUDE_REMARK_PHRASE_FIXES:
        text = pattern.sub(replacement, text)
    return text


@register.filter
def test_display_title(value):
    from app_post_matric.test_display_labels import test_display_title as _display
    return _display(value)