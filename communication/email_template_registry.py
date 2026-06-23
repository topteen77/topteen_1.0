"""
Registry of transactional email templates used across the platform.

Each entry appears as a row in admin (Communication → Email message templates).
Content templates live under ``mail/content/`` (body only). All sent emails are
automatically wrapped with ``mail/base_email.html`` (shared header + footer).
"""

from core import email_strings

COMMON_INVITE_PLACEHOLDER_HELP = """
Placeholders (type exactly, including curly braces):

  {email}         — Recipient login email
  {password}      — Temporary or assigned password
  {url}           — Full login URL (https://…)
  {url_no_scheme} — Login URL without http/https (for CKEditor link tool)
""".strip()

REFERRAL_PLACEHOLDER_HELP = """
Who is who (important):
  INVITER  = logged-in user clicking "Send invitation" on the dashboard
  INVITEE  = friend email entered in the form (also the person who RECEIVES this email)

Placeholders:

  {inviter_name}      — Inviter display name (or email if name is empty)
  {inviter_email}     — Inviter account email
  {invitee_name}      — Friend greeting name (from email local part)
  {invitee_email}     — Friend email / recipient
  {referral_url}      — Join link WITHOUT http:// (CKEditor: http://{referral_url})
  {referral_url_full} — Full join link with https://

Legacy: {user} = inviter name, {refral_url} = full referral link
""".strip()

EMAIL_TEMPLATE_REGISTRY = {
    'refer_friend': {
        'name': 'Refer a friend invitation',
        'default_subject': '{inviter_name} has invited you to explore careers in TopTeen',
        'template_path': 'mail/content/refer_friend.html',
        'placeholder_help': REFERRAL_PLACEHOLDER_HELP,
        'sample_subject': '{inviter_name} invited you to join TopTeen',
        'sample_body_html': (
            '<p>Hi {invitee_name},</p>'
            '<p>Your friend (<strong>{inviter_name}</strong>) has invited you to join TopTeen.</p>'
            '<p><a href="http://{referral_url}">Join TopTeen</a></p>'
        ),
    },
    'email_otp': {
        'name': 'Email verification OTP',
        'default_subject': email_strings.EMAIL_OTP_SUBJECT,
        'template_path': 'mail/content/email_otp.html',
        'placeholder_help': 'Placeholders:\n\n  {otp} — One-time verification code',
        'sample_subject': email_strings.EMAIL_OTP_SUBJECT,
        'sample_body_html': '<p>Your verification code is: <strong>{otp}</strong></p>',
    },
    'psychometric_payment_success': {
        'name': 'Psychometric test payment success',
        'default_subject': email_strings.EMAIL_PYSCHOMETRIC_TEST_PAYMENT_SUCCESS,
        'template_path': 'mail/content/psychometric_payment_success.html',
        'placeholder_help': 'Placeholders:\n\n  {test_link} — Psychometric test start URL',
    },
    'skilllab_payment_success': {
        'name': 'SkillLab course payment success',
        'default_subject': email_strings.EMAIL_SKILLABCOURSE_PAYMENT_SUCCESS,
        'template_path': 'mail/content/skilllab_payment_success.html',
        'placeholder_help': 'Placeholders:\n\n  {course_name} — Course name\n  {course_url} — Course detail URL',
    },
    'student_invite': {
        'name': 'Student account invitation',
        'default_subject': 'You have been invited to join Topteen',
        'template_path': 'mail/content/student_invite.html',
        'placeholder_help': COMMON_INVITE_PLACEHOLDER_HELP + """

  {ins_name}              — Institute name
  {ins_logo_url}          — Institute logo URL
  {psychometric_test_url} — Psychometric test link
""",
        'sample_subject': 'You have been invited to join Topteen',
        'sample_body_html': (
            '<p>Hello!</p>'
            '<p>You have been invited to join Topteen at <strong>{ins_name}</strong>.</p>'
            '<p>Email: {email}<br>Password: {password}</p>'
            '<p><a href="{url}">Join Topteen</a></p>'
        ),
    },
    'institute_invite': {
        'name': 'Institute account invitation',
        'default_subject': 'You have been invited to join Topteen',
        'template_path': 'mail/content/institute_invite.html',
        'placeholder_help': COMMON_INVITE_PLACEHOLDER_HELP,
        'sample_subject': 'You have been invited to join Topteen',
        'sample_body_html': (
            '<p>Hello!</p>'
            '<p>Email: {email}<br>Password: {password}</p>'
            '<p><a href="{url}">Join Topteen</a></p>'
        ),
    },
    'institute_homepage_welcome': {
        'name': 'Institute homepage welcome (principal)',
        'default_subject': 'Welcome aboard! Your Institute is Now Part of the TOPTEEN Journey',
        'template_path': 'mail/content/institute_homepage_welcome.html',
        'placeholder_help': COMMON_INVITE_PLACEHOLDER_HELP + """

  {ins_name}        — Institute name
  {principal_name}  — Principal contact name
  {contact_number}  — Institute phone
  {address}         — Institute address
  {institute_type}  — Institute type label
""",
    },
    'institute_marketing_notify': {
        'name': 'New institute registration (marketing)',
        'default_subject': 'New Institute Registered on TOPTEEN – {institute_type}, {address}',
        'template_path': 'mail/content/institute_marketing_notify.html',
        'placeholder_help': COMMON_INVITE_PLACEHOLDER_HELP + """

  {user_email}      — Submitter email
  {ins_name}        — Institute name
  {principal_name}  — Principal contact name
  {contact_number}  — Institute phone
  {address}         — Institute address
  {institute_type}  — Institute type label
""",
    },
    'counselor_invite': {
        'name': 'Counselor account invitation',
        'default_subject': 'You have been invited to join Topteen',
        'template_path': 'mail/content/counselor_invite.html',
        'placeholder_help': COMMON_INVITE_PLACEHOLDER_HELP,
        'sample_subject': 'You have been invited to join Topteen',
        'sample_body_html': (
            '<p>Hello!</p>'
            '<p>Email: {email}<br>Password: {password}</p>'
            '<p><a href="{url}">Join Topteen</a></p>'
        ),
    },
    'institute_group_invite': {
        'name': 'Institute group account invitation',
        'default_subject': 'You have been invited to join Topteen',
        'template_path': 'mail/content/institute_group_invite.html',
        'placeholder_help': COMMON_INVITE_PLACEHOLDER_HELP + """

  {group_name} — Institute group name
""",
    },
    'student_password_notify': {
        'name': 'Student password reset notification',
        'default_subject': 'You have been invited to join Topteen',
        'template_path': 'mail/content/student_password_notify.html',
        'placeholder_help': COMMON_INVITE_PLACEHOLDER_HELP,
    },
    'registration_success': {
        'name': 'User registration success',
        'default_subject': email_strings.EMAIL_REGISTRATION_SUCCESS,
        'template_path': 'mail/content/registration_success.html',
        'placeholder_help': """
Placeholders:

  {name}   — User display name
  {did}    — User DID / reference id
  {email}  — User email
  {mobile} — User mobile number
""".strip(),
        'sample_body_html': (
            '<p>Hello {name},</p>'
            '<p>Welcome to TopTeen! Your registration was successful.</p>'
            '<p>Reference ID: {did}<br>Email: {email}<br>Mobile: {mobile}</p>'
        ),
    },
    'institute_deletion_request': {
        'name': 'Institute deletion request (to support)',
        'default_subject': 'Institute Deletion Request',
        'template_path': 'mail/content/institute_deletion_request.html',
        'placeholder_help': """
Placeholders:

  {institute_id}   — Institute database id
  {institute_name} — Institute name
  {reason}         — Deletion reason text
""".strip(),
    },
    'resume_builder': {
        'name': 'Resume builder delivery',
        'default_subject': email_strings.EMAIL_RESUME_BUILDER_RESUME,
        'template_path': 'mail/content/resume_builder.html',
        'placeholder_help': 'Built-in email has a fixed body; attachment is added separately when sent.',
    },
    'test_popup_answers': {
        'name': 'Test completion popup answers (admin)',
        'default_subject': 'Test Completion Popup Answers - {user_name}',
        'template_path': 'mail/content/test_popup_answers.html',
        'placeholder_help': """
Placeholders:

  {user_email}         — Student email
  {user_name}          — Student username or email
  {personality_answer} — Personality question answer
  {motivation_answer}  — Motivation question answer
  {career_answer}      — Career interest answer
  {career_country}     — Career country preference
""".strip(),
    },
    'password_reset': {
        'name': 'Admin password reset',
        'default_subject': 'Password Reset Requested',
        'template_path': 'mail/content/password_reset.html',
        'placeholder_help': """
Placeholders:

  {email} — User account email
  {url}   — Password reset link
""".strip(),
        'sample_subject': 'Password Reset Requested',
        'sample_body_html': (
            '<p>Hello!</p>'
            '<p>Click below to reset your password:</p>'
            '<p><a href="{url}">Reset Password</a></p>'
        ),
    },
}


def get_email_template_meta(slug):
    return EMAIL_TEMPLATE_REGISTRY.get(slug, {})
