from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import EmailMessageTemplate

REFERRAL_EMAIL_SLUG = 'refer_friend'

DEFAULT_REFERRAL_SUBJECT = '{inviter_name} has invited you to explore careers in TopTeen'

REFERRAL_PLACEHOLDER_HELP = """
Who is who (important):
  INVITER  = logged-in user clicking "Send invitation" on the dashboard
  INVITEE  = friend email entered in the form (also the person who RECEIVES this email)

Placeholders (type exactly as shown, including curly braces):

  {inviter_name}    — Inviter display name (or email if name is empty)
  {inviter_email}   — Inviter account email
  {invitee_name}    — Friend greeting name (from email, e.g. john from john@gmail.com)
  {invitee_email}   — Friend email / recipient (same as To address)
  {referral_url}    — Join link WITHOUT http:// (for CKEditor link tool: http://{referral_url})
  {referral_url_full} — Full join link with https:// (use in href="{referral_url_full}")

Legacy aliases: {user} = inviter name, {refral_url} = full referral link

Link examples (CKEditor adds http:// by default):
  <a href="http://{referral_url}">Join Now</a>
  <a href="{referral_url_full}">Join Now</a>
""".strip()

REFERRAL_SAMPLE_SUBJECT = '{inviter_name} invited you to join TopTeen'

REFERRAL_SAMPLE_BODY_HTML = """<p>Hi {invitee_name},</p>
<p>Your friend (<strong>{inviter_name}</strong>) wants to help you build an amazing future! They have invited you to join TopTeen.in, the ultimate platform designed to help you explore, discover, and choose the absolute best career paths for you.</p>
<p>Whether you are figuring out your next steps or looking for the perfect industry that matches your passions, TopTeen has everything you need to get started.</p>
<p><a href="http://{referral_url}">Join TopTeen</a></p>
<p>Thank you,<br>Team TopTeen</p>"""


class _SafeFormatDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'


def ensure_default_email_templates():
    EmailMessageTemplate.objects.get_or_create(
        slug=REFERRAL_EMAIL_SLUG,
        defaults={
            'name': 'Refer a friend invitation',
            'subject_template': '',
            'body_html_template': '',
            'is_active': True,
        },
    )


def format_email_message(slug, context, default_subject, default_html_renderer):
    """
    Resolve subject and HTML body for a transactional email.

    ``default_html_renderer`` is a callable returning the fallback HTML string.
    """
    ensure_default_email_templates()
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
            html_content = (tpl.body_html_template or '').strip().format_map(ctx)
        except Exception:
            html_content = default_html_renderer()
    else:
        html_content = default_html_renderer()

    text_content = strip_tags(html_content) or html_content
    return subject, text_content, html_content


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
            'mail/user/referral.html',
            {'refral_url': referral_url_full, 'user': inviter_name},
        )

    return format_email_message(
        REFERRAL_EMAIL_SLUG,
        context,
        DEFAULT_REFERRAL_SUBJECT,
        default_html,
    )
