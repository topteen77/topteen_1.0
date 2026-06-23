"""Load built-in mail HTML files and normalize them for admin {placeholder} editing."""

import re
from datetime import datetime
from pathlib import Path

from django.conf import settings

from .email_template_registry import EMAIL_TEMPLATE_REGISTRY, get_email_template_meta

STATIC_BASE_URL = 'https://www.topteen.in/static/'

# Django/Jinja variable names in source files -> admin str.format placeholders.
SLUG_PLACEHOLDER_ALIASES = {
    'refer_friend': {
        'user': 'inviter_name',
        'refral_url': 'referral_url_full',
    },
    'institute_homepage_welcome': {
        'Ins_name': 'ins_name',
        'Address': 'address',
    },
    'institute_marketing_notify': {
        'Ins_name': 'ins_name',
        'Address': 'address',
    },
    'psychometric_payment_success': {
        'candidate_test.test_link': 'test_link',
    },
    'skilllab_payment_success': {
        'course_payment.skilllab_course.name': 'course_name',
    },
    'test_popup_answers': {
        'user.username': 'user_username',
        'user.email': 'user_email',
        'user.name': 'user_name',
    },
}


def _read_template_source(template_path):
    if not template_path:
        return ''

    candidate_roots = []
    for templates_cfg in settings.TEMPLATES:
        candidate_roots.extend(templates_cfg.get('DIRS', []))

    base_dir = Path(settings.BASE_DIR)
    candidate_roots.extend([
        base_dir / 'templates',
        base_dir / 'templates1',
    ])

    seen = set()
    for root in candidate_roots:
        root_path = Path(root)
        key = str(root_path.resolve()) if root_path.exists() else str(root_path)
        if key in seen:
            continue
        seen.add(key)
        file_path = root_path / template_path
        if file_path.is_file():
            return file_path.read_text(encoding='utf-8')

    return ''


def _resolve_placeholder(slug, raw_name):
    aliases = SLUG_PLACEHOLDER_ALIASES.get(slug, {})
    return aliases.get(raw_name, raw_name)


def normalize_builtin_html_for_admin(html, slug):
    """Convert Django/Jinja mail templates to admin {placeholder} format."""
    if not html:
        return ''

    content = html

    # Jinja static('path') and Django {% static 'path' %}
    content = re.sub(
        r"\{\{\s*static\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}",
        STATIC_BASE_URL + r'\1',
        content,
    )
    content = re.sub(
        r"\{%\s*static\s+['\"]([^'\"]+)['\"]\s*%\}",
        STATIC_BASE_URL + r'\1',
        content,
    )

    # SkillLab course detail URL in href.
    content = re.sub(
        r'href="https://topteen\.in\{\{url\(\'skilllabcourse:skilllabcoursedetail\',args=\[course_payment\.skilllab_course\.slug\]\)\}\}"',
        'href="{course_url}"',
        content,
    )

    # Optional career country block — keep inner HTML.
    content = re.sub(
        r'\{%\s*if\s+career_country\s*%\}(.*?)\{%\s*endif\s*%\}',
        r'\1',
        content,
        flags=re.DOTALL,
    )

    # Current year.
    content = re.sub(
        r'\{%\s*now\s+[\'"]Y[\'"]\s*%\}',
        str(datetime.now().year),
        content,
    )

    # Remove remaining template tags (url(), etc.) that cannot become placeholders.
    content = re.sub(r'\{%[^%]*%\}', '', content)

    def replace_var(match):
        raw = match.group(1).strip()
        # Strip default filters: user.name|default('N/A') -> user.name
        raw = re.sub(r'\|.*$', '', raw).strip()
        name = _resolve_placeholder(slug, raw)
        return '{' + name + '}'

    content = re.sub(
        r'\{\{\s*([^}]+?)\s*\}\}',
        replace_var,
        content,
    )

    return content.strip()


def load_builtin_body_html(slug):
    meta = get_email_template_meta(slug)
    template_path = meta.get('template_path')
    source = _read_template_source(template_path)
    if source:
        return normalize_builtin_html_for_admin(source, slug)
    return (meta.get('sample_body_html') or '').strip()


def get_builtin_defaults(slug):
    meta = get_email_template_meta(slug)
    subject = (meta.get('default_subject') or '').strip()
    body = load_builtin_body_html(slug)
    return subject, body


def populate_template_defaults(template_obj, force=False):
    """
    Fill empty subject/body on an EmailMessageTemplate from built-in files.

    Returns True if the instance was updated.
    """
    slug = template_obj.slug
    if slug not in EMAIL_TEMPLATE_REGISTRY:
        return False

    subject, body = get_builtin_defaults(slug)
    updates = {}

    if force or not (template_obj.subject_template or '').strip():
        if subject:
            updates['subject_template'] = subject

    if force or not (template_obj.body_html_template or '').strip():
        if body:
            updates['body_html_template'] = body

    if not updates:
        return False

    for field, value in updates.items():
        setattr(template_obj, field, value)
    template_obj.save(update_fields=list(updates.keys()) + ['modified'])
    return True
