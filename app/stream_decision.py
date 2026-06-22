"""Stream decision questionnaire storage helpers."""

QUESTION_KEYS = (
    'reports_reviewed',
    'preferred_stream',
)

REPORTS_REVIEWED_YES = 'Yes, I have reviewed them thoroughly'
REPORTS_REVIEWED_NO = 'No, not yet'

VALID_STREAMS = frozenset({
    'PCM',
    'PCB',
    'CWM',
    'CWOM',
    'HUM-L',
    'HUM',
})

STREAM_DECISION_STREAM_OPTIONS = (
    {
        'code': 'PCM',
        'label': 'PCM - Engineering (Physics, Chemistry, Mathematics)',
    },
    {
        'code': 'PCB',
        'label': 'PCB - Medical (Physics, Chemistry, Biology)',
    },
    {
        'code': 'CWM',
        'label': 'CWM - Commerce (Commerce with Mathematics)',
    },
    {
        'code': 'CWOM',
        'label': 'CWOM - Commerce (Commerce without Mathematics)',
    },
    {
        'code': 'HUM-L',
        'label': 'HUM-L - Humanities (Humanities with Languages)',
    },
    {
        'code': 'HUM',
        'label': 'HUM - Humanities (Humanities)',
    },
)

QUESTIONNAIRE_KEY = 'stream_decision_questionnaire'


def stream_decision_display_label(stream_code):
    code = str(stream_code or '').strip().upper()
    for option in STREAM_DECISION_STREAM_OPTIONS:
        if option['code'] == code:
            return option['label']
    return code


def get_questionnaire_data(results_dict):
    if not isinstance(results_dict, dict):
        return {}
    return results_dict.get(QUESTIONNAIRE_KEY) or {}


def is_questionnaire_completed(results_dict):
    return bool(get_questionnaire_data(results_dict).get('completed'))


def validate_answers(answers):
    if not isinstance(answers, dict):
        return 'Invalid answers payload'
    missing = [key for key in QUESTION_KEYS if not str(answers.get(key, '')).strip()]
    if missing:
        return 'Please answer all questions before submitting.'
    reports_reviewed = str(answers.get('reports_reviewed', '')).strip()
    if reports_reviewed != REPORTS_REVIEWED_YES:
        return 'Please review your reports before submitting your stream decision.'
    stream = str(answers.get('preferred_stream', '')).strip()
    if stream not in VALID_STREAMS:
        return 'Please select a stream.'
    return None


def build_saved_answers(answers):
    return {key: str(answers.get(key, '')).strip() for key in QUESTION_KEYS}


def save_questionnaire(test3_result, answers, completed_at=None):
    from django.utils import timezone

    results = test3_result.results or {}
    completed_at = completed_at or timezone.now()
    results[QUESTIONNAIRE_KEY] = {
        'completed': True,
        'answers': build_saved_answers(answers),
        'completed_at': completed_at.isoformat(),
    }
    test3_result.results = results
    test3_result.save(update_fields=['results', 'modified'])


def clear_questionnaire(user):
    from app.models import Results

    try:
        test3_result = Results.objects.get(user=user, test_paper='test3')
    except Results.DoesNotExist:
        return False
    results = test3_result.results or {}
    if QUESTIONNAIRE_KEY not in results:
        return False
    del results[QUESTIONNAIRE_KEY]
    test3_result.results = results
    test3_result.save(update_fields=['results', 'modified'])
    return True


def user_has_completed_questionnaire(user):
    from app.models import Results

    try:
        test3_result = Results.objects.get(user=user, test_paper='test3')
    except Results.DoesNotExist:
        return False
    return is_questionnaire_completed(test3_result.results)
