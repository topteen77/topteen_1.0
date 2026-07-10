"""Constants and mappings for psychometric package catalog."""

from core import choices

CLASS10_ASSESSMENTS = [
    {
        'code': 'class10_personality',
        'name': 'Class 10 Personality',
        'engine_key': 'test1',
    },
    {
        'code': 'class10_interest',
        'name': 'Class 10 Career Interest',
        'engine_key': 'test2',
    },
    {
        'code': 'class10_aptitude',
        'name': 'Class 10 Aptitude',
        'engine_key': 'test3',
    },
]

POST_MATRIC_ASSESSMENTS = [
    {
        'code': 'class12_personality',
        'name': 'Class 12 Personality',
        'engine_key': '1',
    },
    {
        'code': 'class12_motivation',
        'name': 'Class 12 Motivation',
        'engine_key': '2',
    },
    {
        'code': 'class12_interest',
        'name': 'Class 12 Career Interest',
        'engine_key': '3',
    },
    {
        'code': 'class12_aptitude',
        'name': 'Class 12 Aptitude',
        'engine_key': '4',
    },
]

CLASS10_ENGINE_TO_CODE = {
    item['engine_key']: item['code'] for item in CLASS10_ASSESSMENTS
}

POST_MATRIC_ENGINE_TO_CODE = {
    item['engine_key']: item['code'] for item in POST_MATRIC_ASSESSMENTS
}


def post_matric_test_id_to_code(test_id) -> str:
    return POST_MATRIC_ENGINE_TO_CODE.get(str(test_id), '')


DEFAULT_PACKAGES = [
    {
        'code': 'pkg_c10_personality',
        'name': 'Class 10 Personality',
        'track': choices.PsychometricTrack.CLASS10,
        'credit_cost': 1,
        'list_price': '299.00',
        'assessment_codes': ['class10_personality'],
    },
    {
        'code': 'pkg_c10_interest',
        'name': 'Class 10 Career Interest',
        'track': choices.PsychometricTrack.CLASS10,
        'credit_cost': 1,
        'list_price': '299.00',
        'assessment_codes': ['class10_interest'],
    },
    {
        'code': 'pkg_c10_pers_interest',
        'name': 'Class 10 Personality + Interest',
        'track': choices.PsychometricTrack.CLASS10,
        'credit_cost': 2,
        'list_price': '499.00',
        'assessment_codes': ['class10_personality', 'class10_interest'],
    },
    {
        'code': 'pkg_c10_aptitude',
        'name': 'Class 10 Aptitude',
        'track': choices.PsychometricTrack.CLASS10,
        'credit_cost': 1,
        'list_price': '299.00',
        'assessment_codes': ['class10_aptitude'],
    },
    {
        'code': 'pkg_stream_sorter_full',
        'name': 'Stream Sorter Full Bundle',
        'track': choices.PsychometricTrack.CLASS10,
        'credit_cost': 4,
        'list_price': '999.00',
        'is_legacy_bundle': True,
        'assessment_codes': [
            'class10_personality',
            'class10_interest',
            'class10_aptitude',
        ],
    },
    {
        'code': 'pkg_c12_personality',
        'name': 'Class 12 Personality',
        'track': choices.PsychometricTrack.POST_MATRIC,
        'credit_cost': 1,
        'list_price': '299.00',
        'assessment_codes': ['class12_personality'],
    },
    {
        'code': 'pkg_c12_interest',
        'name': 'Class 12 Career Interest',
        'track': choices.PsychometricTrack.POST_MATRIC,
        'credit_cost': 1,
        'list_price': '299.00',
        'assessment_codes': ['class12_interest'],
    },
    {
        'code': 'pkg_c12_aptitude',
        'name': 'Class 12 Aptitude',
        'track': choices.PsychometricTrack.POST_MATRIC,
        'credit_cost': 1,
        'list_price': '299.00',
        'assessment_codes': ['class12_aptitude'],
    },
    {
        'code': 'pkg_career_direction_full',
        'name': 'Career Direction Full Bundle',
        'track': choices.PsychometricTrack.POST_MATRIC,
        'credit_cost': 3,
        'list_price': '999.00',
        'is_legacy_bundle': True,
        'assessment_codes': [
            'class12_personality',
            'class12_motivation',
            'class12_interest',
            'class12_aptitude',
        ],
    },
]
