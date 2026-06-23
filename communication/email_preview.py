"""Render admin email template previews with sample placeholder data."""

from communication.email_layout import wrap_email_layout
from communication.email_template_registry import get_email_template_meta
from communication.email_templates import _SafeFormatDict
from communication.builtin_email_content import load_builtin_body_html


PREVIEW_SAMPLE_CONTEXT = {
    'refer_friend': {
        'inviter_name': 'Alex Kumar',
        'inviter_email': 'alex@example.com',
        'invitee_name': 'Sam',
        'invitee_email': 'sam@example.com',
        'referral_url': 'www.topteen.in/user/signup/?ref=sample',
        'referral_url_full': 'https://www.topteen.in/user/signup/?ref=sample',
        'user': 'Alex Kumar',
        'refral_url': 'https://www.topteen.in/user/signup/?ref=sample',
    },
    'email_otp': {'otp': '123456'},
    'psychometric_payment_success': {'test_link': 'https://www.topteen.in/psychometric/sample-test/'},
    'skilllab_payment_success': {
        'course_name': 'Career Discovery Workshop',
        'course_url': 'https://www.topteen.in/skilllab/sample-course/',
    },
    'student_invite': {
        'email': 'student@example.com',
        'password': 'TempPass123',
        'url': 'https://www.topteen.in/user/login/',
        'url_no_scheme': 'www.topteen.in/user/login/',
        'ins_name': 'Sample Institute',
        'ins_logo_url': 'https://www.topteen.in/static/images_new/logos/logo.svg',
        'psychometric_test_url': 'https://www.topteen.in/psychometric/sample-test/',
    },
    'institute_invite': {
        'email': 'institute@example.com',
        'password': 'TempPass123',
        'url': 'https://www.topteen.in/user/login/',
        'url_no_scheme': 'www.topteen.in/user/login/',
    },
    'institute_homepage_welcome': {
        'email': 'principal@example.com',
        'password': 'TempPass123',
        'url': 'https://www.topteen.in/user/login/',
        'url_no_scheme': 'www.topteen.in/user/login/',
        'Ins_name': 'Sample Public School',
        'ins_name': 'Sample Public School',
        'principal_name': 'Dr. Meera Shah',
        'contact_number': '+91 98765 43210',
        'Address': 'Delhi, India',
        'address': 'Delhi, India',
        'institute_type': 'Senior Secondary School',
    },
    'institute_marketing_notify': {
        'user_email': 'registrar@example.com',
        'email': 'marketing@topteen.in',
        'password': 'TempPass123',
        'url': 'https://www.topteen.in/user/login/',
        'url_no_scheme': 'www.topteen.in/user/login/',
        'Ins_name': 'Sample Public School',
        'ins_name': 'Sample Public School',
        'principal_name': 'Dr. Meera Shah',
        'contact_number': '+91 98765 43210',
        'Address': 'Delhi, India',
        'address': 'Delhi, India',
        'institute_type': 'Senior Secondary School',
    },
    'counselor_invite': {
        'email': 'counselor@example.com',
        'password': 'TempPass123',
        'url': 'https://www.topteen.in/user/login/',
        'url_no_scheme': 'www.topteen.in/user/login/',
    },
    'institute_group_invite': {
        'group_name': 'North Zone Schools',
        'email': 'group@example.com',
        'password': 'TempPass123',
        'url': 'https://www.topteen.in/user/login/',
        'url_no_scheme': 'www.topteen.in/user/login/',
    },
    'student_password_notify': {
        'email': 'student@example.com',
        'password': 'NewPass456',
        'url': 'https://www.topteen.in/user/login/',
        'url_no_scheme': 'www.topteen.in/user/login/',
    },
    'registration_success': {
        'name': 'Priya Sharma',
        'did': 'TT-2026-001',
        'email': 'priya@example.com',
        'mobile': '9876543210',
    },
    'institute_deletion_request': {
        'institute_id': '42',
        'institute_name': 'Sample Institute',
        'reason': 'Requested by institute admin',
    },
    'resume_builder': {},
    'test_popup_answers': {
        'user_email': 'student@example.com',
        'user_name': 'Priya Sharma',
        'user_username': 'priya_s',
        'personality_answer': 'Curious and collaborative',
        'motivation_answer': 'Making a positive impact',
        'career_answer': 'Technology and design',
        'career_country': 'India',
    },
    'password_reset': {
        'email': 'user@example.com',
        'url': 'https://www.topteen.in/topteenadmin/changepassword/sample/token/',
    },
}


def render_admin_email_preview(slug, subject_template='', body_html_template=''):
    """Return (subject, full_wrapped_html) using sample placeholder values."""
    meta = get_email_template_meta(slug)
    ctx = _SafeFormatDict(PREVIEW_SAMPLE_CONTEXT.get(slug, {}))

    subject_default = meta.get('default_subject') or 'TopTeen notification'
    subject_src = (subject_template or '').strip() or subject_default
    try:
        subject = subject_src.format_map(ctx)
    except Exception:
        subject = subject_default

    body_src = (body_html_template or '').strip()
    if not body_src:
        body_src = load_builtin_body_html(slug) or meta.get('sample_body_html') or ''

    try:
        inner_html = body_src.format_map(ctx)
    except Exception:
        inner_html = body_src

    html_content = wrap_email_layout(inner_html, preheader=subject)
    return subject, html_content
