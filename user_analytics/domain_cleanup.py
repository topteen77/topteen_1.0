"""
Delete UserActivity / UserJourney / UserEvent rows that match one specific URL host / pattern / client IP.
Each option is independent (e.g. localhost only, 127.0.0.1 in URL only, demo.topteen.in only).
"""
from django.db import transaction
from django.db.models import Q

from user_analytics.models import UserActivity, UserJourney, UserEvent


def _journey_fields_icontains(text):
    q = Q()
    for field in ('entry_page', 'exit_page', 'referrer'):
        q |= Q(**{f'{field}__icontains': text})
    return q


def _activity_private_172():
    q = Q()
    for i in range(16, 32):
        q |= Q(page_url__icontains='172.%d.' % i)
    return q


def _journey_private_172():
    q = Q()
    for i in range(16, 32):
        frag = '172.%d.' % i
        for field in ('entry_page', 'exit_page', 'referrer'):
            q |= Q(**{f'{field}__icontains': frag})
    return q


def _activity_private_10():
    return Q(page_url__icontains='http://10.') | Q(page_url__icontains='https://10.')


def _journey_private_10():
    q = Q()
    for field in ('entry_page', 'exit_page', 'referrer'):
        q |= (
            Q(**{f'{field}__icontains': 'http://10.'})
            | Q(**{f'{field}__icontains': 'https://10.'})
        )
    return q


def _build_specs():
    """Return dict key -> spec with label, activity_q, journey_extra_q (optional), event_ip_q (optional)."""
    return {
        'localhost': {
            'label': 'localhost (in page URL or path)',
            'activity_q': lambda: Q(page_url__icontains='localhost') | Q(page_path__icontains='localhost'),
            'journey_extra_q': lambda: _journey_fields_icontains('localhost'),
        },
        '127.0.0.1': {
            'label': '127.0.0.1 (in page URL)',
            'activity_q': lambda: Q(page_url__icontains='127.0.0.1'),
            'journey_extra_q': lambda: _journey_fields_icontains('127.0.0.1'),
        },
        'testserver': {
            'label': 'testserver (Django test client host)',
            'activity_q': lambda: Q(page_url__icontains='testserver'),
            'journey_extra_q': lambda: _journey_fields_icontains('testserver'),
        },
        '0.0.0.0': {
            'label': '0.0.0.0 (in page URL)',
            'activity_q': lambda: Q(page_url__icontains='0.0.0.0'),
            'journey_extra_q': lambda: _journey_fields_icontains('0.0.0.0'),
        },
        'ipv6_loopback': {
            'label': 'IPv6 loopback [::1] (in page URL)',
            'activity_q': lambda: Q(page_url__icontains='[::1]'),
            'journey_extra_q': lambda: _journey_fields_icontains('[::1]'),
        },
        'private_192_168': {
            'label': 'Private 192.168.x (in page URL)',
            'activity_q': lambda: Q(page_url__icontains='192.168.'),
            'journey_extra_q': lambda: _journey_fields_icontains('192.168.'),
        },
        'private_10': {
            'label': 'Private 10.x (http/https://10.… in page URL)',
            'activity_q': _activity_private_10,
            'journey_extra_q': _journey_private_10,
        },
        'private_172': {
            'label': 'Private 172.16–31.x (in page URL)',
            'activity_q': _activity_private_172,
            'journey_extra_q': _journey_private_172,
        },
        'ref_landing': {
            'label': 'Path /ref-landing/…',
            'activity_q': lambda: Q(page_path__istartswith='/ref-landing/'),
            'journey_extra_q': lambda: (
                Q(entry_page__istartswith='/ref-landing/')
                | Q(exit_page__istartswith='/ref-landing/')
                | Q(referrer__icontains='/ref-landing/')
            ),
        },
        'client_ip_loopback': {
            'label': 'Client IP: loopback (127.x / ::1)',
            'activity_q': lambda: Q(ip_address__startswith='127.') | Q(ip_address__startswith='::1'),
            'journey_extra_q': None,
            'event_ip_q': lambda: Q(ip_address__startswith='127.') | Q(ip_address__startswith='::1'),
        },
        'client_ip_private': {
            'label': 'Client IP: private (10/172.16–31/192.168)',
            'activity_q': lambda: (
                Q(ip_address__startswith='192.168.')
                | Q(ip_address__startswith='10.')
                | Q(ip_address__istartswith='172.')
            ),
            'journey_extra_q': None,
            'event_ip_q': lambda: (
                Q(ip_address__startswith='192.168.')
                | Q(ip_address__startswith='10.')
                | Q(ip_address__istartswith='172.')
            ),
        },
        'demo.topteen.in': {
            'label': 'demo.topteen.in',
            'activity_q': lambda: Q(page_url__icontains='demo.topteen.in'),
            'journey_extra_q': lambda: _journey_fields_icontains('demo.topteen.in'),
        },
        'www.topteen.in': {
            'label': 'www.topteen.in',
            'activity_q': lambda: Q(page_url__icontains='www.topteen.in'),
            'journey_extra_q': lambda: _journey_fields_icontains('www.topteen.in'),
        },
        'production_topteen': {
            'label': 'topteen.in (production, excludes demo subdomain)',
            'activity_q': lambda: Q(page_url__icontains='topteen.in') & ~Q(page_url__icontains='demo.topteen.in'),
            'journey_extra_q': lambda: (
                (Q(entry_page__icontains='topteen.in') & ~Q(entry_page__icontains='demo.topteen.in'))
                | (Q(exit_page__icontains='topteen.in') & ~Q(exit_page__icontains='demo.topteen.in'))
                | (Q(referrer__icontains='topteen.in') & ~Q(referrer__icontains='demo.topteen.in'))
            ),
        },
    }


DOMAIN_SPECS = _build_specs()

DOMAIN_CLEANUP_CHOICES = [(k, DOMAIN_SPECS[k]['label']) for k in DOMAIN_SPECS.keys()]

VALID_DOMAINS = frozenset(DOMAIN_SPECS.keys())


def run_domain_cleanup(domain_key: str, dry_run: bool = False):
    """
    Delete analytics rows for one specific domain/pattern key.
    Order: UserJourney, UserEvent, UserActivity.
    Returns (text_report, counts_dict).
    """
    if domain_key not in DOMAIN_SPECS:
        raise ValueError('invalid domain')

    spec = DOMAIN_SPECS[domain_key]
    activity_q = spec['activity_q']()
    activities = UserActivity.objects.filter(activity_q)
    act_session_ids = {x for x in activities.values_list('session_id', flat=True).distinct() if x}

    journey_extra = spec.get('journey_extra_q')
    if journey_extra:
        journey_q = journey_extra() | Q(session_id__in=act_session_ids)
    else:
        journey_q = Q(session_id__in=act_session_ids)

    journeys = UserJourney.objects.filter(journey_q)
    j_session_ids = {x for x in journeys.values_list('session_id', flat=True).distinct() if x}

    all_session_ids = act_session_ids | j_session_ids

    event_q = Q(session_id__in=all_session_ids)
    event_ip = spec.get('event_ip_q')
    if event_ip:
        event_q |= event_ip()
    events = UserEvent.objects.filter(event_q)

    counts = {
        'activities': activities.count(),
        'journeys': journeys.count(),
        'events': events.count(),
    }

    label = spec['label']
    lines = [
        '=' * 60,
        'Domain cleanup: %s (%s)' % (domain_key, label),
        'DRY RUN – no data deleted' if dry_run else 'Deleting…',
        '=' * 60,
        'UserActivity: %s' % counts['activities'],
        'UserJourney: %s' % counts['journeys'],
        'UserEvent: %s' % counts['events'],
        '=' * 60,
    ]
    out = '\n'.join(lines) + '\n'

    total = counts['activities'] + counts['journeys'] + counts['events']
    if dry_run or total == 0:
        return out, counts

    with transaction.atomic():
        journeys.delete()
        events.delete()
        activities.delete()

    return out, counts


# Backwards compatibility for imports (deprecated bucket names)
DOMAIN_LOCAL = 'localhost'
DOMAIN_DEMO = 'demo.topteen.in'
DOMAIN_PRODUCTION = 'production_topteen'
DOMAIN_LABELS = {k: v['label'] for k, v in DOMAIN_SPECS.items()}


def activity_q_for_domain(domain_key: str) -> Q:
    """domain_key must be a DOMAIN_SPECS key."""
    if domain_key not in DOMAIN_SPECS:
        raise ValueError('invalid domain')
    return DOMAIN_SPECS[domain_key]['activity_q']()
