"""Stream decision questionnaire storage helpers."""

QUESTION_KEYS = (
    'preferred_stream',
    'confidence_level',
    'biggest_concern',
    'discussed_with_adult',
    'decision_readiness',
)

QUESTIONNAIRE_KEY = 'stream_decision_questionnaire'


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
    source = str(answers.get('preferred_stream_source', '')).strip()
    stream = str(answers.get('preferred_stream', '')).strip()
    if source == 'not_sure' or stream == 'Not sure yet':
        return 'Please select a stream.'
    return None


def build_saved_answers(answers):
    saved = {key: str(answers.get(key, '')).strip() for key in QUESTION_KEYS}
    if answers.get('preferred_stream_source'):
        saved['preferred_stream_source'] = str(answers.get('preferred_stream_source')).strip()
    if answers.get('preferred_stream_match_score'):
        saved['preferred_stream_match_score'] = str(answers.get('preferred_stream_match_score')).strip()
    return saved


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
