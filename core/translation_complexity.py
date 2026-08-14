"""
Language complexity levels for site-wide Google Translate adjustments.

Google Translate tends to produce formal / Sanskrit-heavy Hindi. These levels
let students pick simpler or more formal wording after the page is translated.
"""

TRANSLATION_COMPLEXITY_LEVELS = (
    ('easy', 'Easy'),
    ('medium', 'Medium'),
    ('hard', 'Hard'),
)

DEFAULT_TRANSLATION_COMPLEXITY = 'easy'

# Max characters per API batch (keep responses fast).
TRANSLATION_BATCH_CHAR_LIMIT = 2800

# Max text segments per request.
TRANSLATION_MAX_SEGMENTS = 24

_LEVEL_INSTRUCTIONS = {
    'easy': (
        'Rewrite in very simple, everyday language suitable for school students '
        'in classes 6–10 (ages 11–16). Use short sentences and common words. '
        'For Hindi: prefer simple बोलचाल की हिंदी; avoid heavy Sanskrit words '
        '(e.g. use "काम" not "कार्य", "सोच" not "चिंतन"). Keep the same meaning.'
    ),
    'medium': (
        'Keep the wording clear and balanced — understandable for teenagers '
        'without being overly simple or overly formal.'
    ),
    'hard': (
        'Rewrite in formal, academic language. For Hindi: use शुद्ध हिंदी with '
        'precise vocabulary suitable for reports and official documents. '
        'Keep the same meaning.'
    ),
}

_LANGUAGE_NAMES = {
    'hi': 'Hindi',
    'bn': 'Bengali',
    'ta': 'Tamil',
    'te': 'Telugu',
    'mr': 'Marathi',
    'gu': 'Gujarati',
    'kn': 'Kannada',
    'ml': 'Malayalam',
    'pa': 'Punjabi',
    'ur': 'Urdu',
    'or': 'Odia',
    'as': 'Assamese',
}


def is_valid_complexity(level):
    return level in {code for code, _ in TRANSLATION_COMPLEXITY_LEVELS}


def complexity_needs_adjustment(level):
    """Medium uses Google Translate output as-is."""
    return level in ('easy', 'hard')


def build_adjustment_prompt(texts, target_lang, level):
    lang_label = _LANGUAGE_NAMES.get(target_lang, target_lang)
    instruction = _LEVEL_INSTRUCTIONS[level]
    segments = [segment.strip() for segment in texts if segment and segment.strip()]
    numbered = '\n\n'.join(
        f'[{index + 1}]\n{segment}'
        for index, segment in enumerate(segments)
    )
    return (
        f'You adjust translated web page text for reading difficulty.\n'
        f'Target language: {lang_label} ({target_lang}).\n'
        f'Level: {level}.\n'
        f'Instruction: {instruction}\n\n'
        f'Return ONLY valid JSON in this exact shape (no markdown fences, no commentary):\n'
        f'{{"texts": ["adjusted block 1", "adjusted block 2", ...]}}\n'
        f'The "texts" array must have exactly {len(segments)} strings, same order as input blocks.\n\n'
        f'Input blocks:\n{numbered}'
    )
