from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .email_layout import wrap_email_layout
from .email_template_registry import EMAIL_TEMPLATE_REGISTRY, get_email_template_meta
from .models import EmailMessageTemplate

REFERRAL_EMAIL_SLUG = 'refer_friend'

DEFAULT_REFERRAL_SUBJECT = EMAIL_TEMPLATE_REGISTRY[REFERRAL_EMAIL_SLUG]['default_subject']

REFERRAL_PLACEHOLDER_HELP = EMAIL_TEMPLATE_REGISTRY[REFERRAL_EMAIL_SLUG]['placeholder_help']

REFERRAL_SAMPLE_SUBJECT = EMAIL_TEMPLATE_REGISTRY[REFERRAL_EMAIL_SLUG]['sample_subject']

REFERRAL_SAMPLE_BODY_HTML = EMAIL_TEMPLATE_REGISTRY[REFERRAL_EMAIL_SLUG]['sample_body_html']


class _SafeFormatDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'


def ensure_all_email_templates():
    from .builtin_email_content import get_builtin_defaults

    for slug, meta in EMAIL_TEMPLATE_REGISTRY.items():
        default_subject, default_body = get_builtin_defaults(slug)
        EmailMessageTemplate.objects.get_or_create(
            slug=slug,
            defaults={
                'name': meta['name'],
                'subject_template': default_subject,
                'body_html_template': default_body,
                'is_active': True,
            },
        )


def ensure_default_email_templates():
    """Backward-compatible alias."""
    ensure_all_email_templates()


def format_email_message(slug, context, default_subject, default_html_renderer):
    """
    Resolve subject and HTML body for a transactional email.

    ``default_html_renderer`` is a callable returning the fallback HTML string.
    """
    ensure_all_email_templates()
    ctx = _SafeFormatDict(context or {})
    try:
        subject = (default_subject or '').format_map(ctx)
    except Exception:
        subject = default_subject or ''

    tpl = EmailMessageTemplate.objects.filter(slug=slug, is_active=True).first()
    if tpl and (tpl.subject_template or '').strip():
        try:
            subject = (tpl.subject_template or '').strip().format_map(ctx)
        except Exception:
            pass

    if tpl and (tpl.body_html_template or '').strip():
        try:
            inner_html = (tpl.body_html_template or '').strip().format_map(ctx)
        except Exception:
            inner_html = default_html_renderer()
    else:
        inner_html = default_html_renderer()

    html_content = wrap_email_layout(inner_html, preheader=subject)
    text_content = strip_tags(html_content) or html_content
    return subject, text_content, html_content


def render_transactional_email(
    slug,
    format_context=None,
    django_template_path=None,
    django_context=None,
    default_subject=None,
):
    """
    Render subject/HTML for a slug, using admin override when configured.

    ``format_context`` supplies ``str.format`` placeholders for admin templates.
    ``django_context`` is passed to the built-in Django HTML file fallback.
    """
    meta = get_email_template_meta(slug)
    if django_template_path is None:
        django_template_path = meta.get('template_path')
    if default_subject is None:
        default_subject = meta.get('default_subject', '')
    if django_context is None:
        django_context = format_context or {}
    if format_context is None:
        format_context = {}

    def default_html():
        return render_to_string(django_template_path, django_context)

    return format_email_message(slug, format_context, default_subject, default_html)


def format_referral_email(user, referral_url, invitee_email=''):
    from communication.utils import invitee_name_from_email, referral_url_without_scheme

    inviter_name = (getattr(user, 'name', None) or getattr(user, 'email', None) or 'A TopTeen user').strip()
    inviter_email = (getattr(user, 'email', None) or '').strip()
    invitee_name = invitee_name_from_email(invitee_email)
    referral_url_full = (referral_url or '').strip()
    referral_url_path = referral_url_without_scheme(referral_url_full)
    context = {
        'inviter_name': inviter_name,
        'inviter_email': inviter_email,
        'invitee_name': invitee_name,
        'invitee_email': invitee_email,
        'user': inviter_name,
        'referral_url': referral_url_path,
        'referral_url_full': referral_url_full,
        'refral_url': referral_url_full,
    }

    def default_html():
        return render_to_string(
            'mail/content/refer_friend.html',
            {'refral_url': referral_url_full, 'user': inviter_name},
        )

    return format_email_message(
        REFERRAL_EMAIL_SLUG,
        context,
        DEFAULT_REFERRAL_SUBJECT,
        default_html,
    )
