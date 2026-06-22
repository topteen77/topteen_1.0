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
  {invitee_email}   — Friend email / recipient (same as To address)
  {referral_url}    — Unique sign-up link for the friend

Legacy aliases: {user} = inviter name, {refral_url} = referral link

Correct example opening:
  Hello,
  {inviter_name} has invited you to join TopTeen.
  This invitation was sent to {invitee_email}.

Do NOT greet the inviter in the email body (wrong: "Hi {inviter_name}," as the opening
line — that addresses the sender, not the friend receiving the mail).
""".strip()

REFERRAL_SAMPLE_SUBJECT = '{inviter_name} invited you to join TopTeen'

REFERRAL_SAMPLE_BODY_HTML = """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
  <p style="font-size: 16px;">Hello,</p>
  <p style="font-size: 16px; line-height: 1.5;">
    <strong>{inviter_name}</strong> has invited you to use TopTeen for career guidance,
    psychometric tests, and college planning.
  </p>
  <p style="margin: 24px 0;">
    <a href="{referral_url}"
       style="background: #3f37c9; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
      Join TopTeen
    </a>
  </p>
  <p style="font-size: 14px; color: #666; line-height: 1.5;">
    This invitation was sent to <strong>{invitee_email}</strong>.
    We send one invitation email only — no marketing lists or spam.
  </p>
  <p style="font-size: 14px; color: #666;">Thank you,<br>Team TopTeen</p>
</div>"""


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
    inviter_name = (getattr(user, 'name', None) or getattr(user, 'email', None) or 'A TopTeen user').strip()
    inviter_email = (getattr(user, 'email', None) or '').strip()
    context = {
        'inviter_name': inviter_name,
        'inviter_email': inviter_email,
        'user': inviter_name,
        'referral_url': referral_url,
        'refral_url': referral_url,
        'invitee_email': invitee_email,
    }

    def default_html():
        return render_to_string(
            'mail/user/referral.html',
            {'refral_url': referral_url, 'user': inviter_name},
        )

    return format_email_message(
        REFERRAL_EMAIL_SLUG,
        context,
        DEFAULT_REFERRAL_SUBJECT,
        default_html,
    )
