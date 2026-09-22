"""Institute / group / counselor in-app alerts for student roster events."""
from notifications.models import NotificationCategory
from notifications.services import emit_notification


def institute_alert_recipients(institute):
    """Institute owner plus that institute's group admin only (deduped)."""
    seen = set()
    out = []
    group = getattr(institute, 'institute_group', None)
    for user in (
        getattr(institute, 'created_by', None),
        getattr(group, 'institute_group_admin', None) if group is not None else None,
    ):
        uid = getattr(user, 'id', None)
        if not uid or uid in seen:
            continue
        if getattr(user, 'is_active', True) is False:
            continue
        seen.add(uid)
        out.append(user)
    return out


def _student_fields(sm):
    student = getattr(sm, 'student', None)
    name = (getattr(student, 'name', None) or '').strip()
    email = (getattr(student, 'email', None) or '').strip()
    return student, name, email


def student_event_payload(sm, institute, extra=None):
    student, name, email = _student_fields(sm)
    payload = {
        'student_id': getattr(sm, 'student_id', None) or getattr(student, 'id', None),
        'institute_id': getattr(institute, 'id', None) or getattr(sm, 'institute_id', None),
        'institute_slug': getattr(institute, 'slug', None) or '',
        'institute_name': getattr(institute, 'name', None) or '',
        'student_name': name,
        'student_email': email,
        'student_management_id': getattr(sm, 'id', None),
    }
    if extra:
        payload.update(extra)
    return payload


def notify_student_registered(sm, institute):
    recipients = institute_alert_recipients(institute)
    if not recipients:
        return
    _, name, email = _student_fields(sm)
    inst_name = (getattr(institute, 'name', None) or 'your institute').strip()
    who = name or email or 'A student'
    detail = email if (name and email) else ''
    body = '{0} registered at {1}.'.format(who, inst_name)
    if detail:
        body = '{0} ({1}) registered at {2}.'.format(name, email, inst_name)
    emit_notification(
        event_type='institute.student_registered',
        title='New student registered',
        body=body,
        recipients=recipients,
        category=NotificationCategory.INSTITUTE,
        source_obj=sm,
        payload=student_event_payload(sm, institute),
        dedupe_key='institute_student_registered_{}'.format(sm.id),
    )


def notify_student_assigned(sm, counselor, institute):
    """Alert the assigned counselor and the institute / group owners of that school only."""
    student, name, email = _student_fields(sm)
    student_label = name or email or 'Student'
    inst_name = (getattr(institute, 'name', None) or 'Institute').strip()
    counselor_name = (
        getattr(counselor, 'counselor_name', None)
        or getattr(getattr(counselor, 'coun_user', None), 'name', None)
        or 'counselor'
    )
    extra = {
        'counselor_id': getattr(counselor, 'id', None),
        'counselor_name': counselor_name,
    }
    payload = student_event_payload(sm, institute, extra)

    counselor_user = getattr(counselor, 'coun_user', None)
    if counselor_user and getattr(counselor_user, 'id', None):
        emit_notification(
            event_type='institute.student_assigned',
            title='New student assigned',
            body='A new student {0} ({1}) was assigned to you by {2}.'.format(
                student_label, email or '-', inst_name
            ),
            recipients=[counselor_user],
            category=NotificationCategory.INSTITUTE,
            payload=payload,
            source_obj=sm,
            dedupe_key='institute.student_assigned:sm{0}:u{1}'.format(
                sm.id, counselor_user.id
            ),
        )

    owners = [
        u
        for u in institute_alert_recipients(institute)
        if getattr(u, 'id', None) != getattr(counselor_user, 'id', None)
    ]
    if owners:
        emit_notification(
            event_type='institute.student_assigned',
            title='New student assigned',
            body='{0} was assigned to {1} at {2}.'.format(
                student_label, counselor_name, inst_name
            ),
            recipients=owners,
            category=NotificationCategory.INSTITUTE,
            payload=payload,
            source_obj=sm,
            dedupe_key='institute.student_assigned:sm{0}:owners'.format(sm.id),
        )
    return counselor_user, student_label, email
