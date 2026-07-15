"""
Site header Google Translate languages — catalog, defaults, and helpers.
"""

from django.core.cache import cache
from django.db.utils import OperationalError, ProgrammingError

TRANSLATE_ENABLED_LANGUAGES_KEY = 'TRANSLATE_ENABLED_LANGUAGES'

# Enabled language codes are read on every request (site header translate bar) via
# a template context processor, so the result is cached to avoid hitting the DB
# repeatedly. Cache is cleared when languages are toggled in the admin.
ENABLED_LANGUAGE_CODES_CACHE_KEY = 'translate:enabled_language_codes:v1'
ENABLED_LANGUAGE_CODES_CACHE_TTL = 600  # 10 minutes

# All languages available in admin (code, display name). English is always enabled on the site.
TRANSLATE_LANGUAGE_CATALOG = [
    ('en', 'English'),
    ('ar', 'Arabic'),
    ('as', 'Assamese'),
    ('awa', 'Awadhi'),
    ('bn', 'Bengali'),
    ('bho', 'Bhojpuri'),
    ('zh-CN', 'Chinese (Simplified)'),
    ('zh-TW', 'Chinese (Traditional)'),
    ('cs', 'Czech'),
    ('dog', 'Dogri'),
    ('nl', 'Dutch'),
    ('fr', 'French'),
    ('fr-CA', 'French (Canada)'),
    ('de', 'German'),
    ('el', 'Greek'),
    ('gu', 'Gujarati'),
    ('hi', 'Hindi'),
    ('it', 'Italian'),
    ('ja', 'Japanese'),
    ('kn', 'Kannada'),
    ('ks', 'Kashmiri'),
    ('kok', 'Konkani'),
    ('ko', 'Korean'),
    ('mai', 'Maithili'),
    ('ms', 'Malay'),
    ('ml', 'Malayalam'),
    ('mr', 'Marathi'),
    ('mwr', 'Marwari'),
    ('mni', 'Manipuri'),
    ('ne', 'Nepali'),
    ('np', 'Nepali (np)'),
    ('or', 'Odia'),
    ('pa', 'Punjabi'),
    ('pt', 'Portuguese'),
    ('pt-BR', 'Portuguese (Brazil)'),
    ('ru', 'Russian'),
    ('sat', 'Santali'),
    ('sd', 'Sindhi'),
    ('es', 'Spanish'),
    ('sw', 'Swahili'),
    ('ta', 'Tamil'),
    ('te', 'Telugu'),
    ('tr', 'Turkish'),
    ('ur', 'Urdu'),
    ('vi', 'Vietnamese'),
    ('si', 'Sinhala'),
    ('tl', 'Filipino'),
    ('th', 'Thai'),
    ('kk', 'Kazakh'),
    ('uz', 'Uzbek'),
    ('af', 'Afrikaans'),
    ('sq', 'Albanian'),
    ('am', 'Amharic'),
    ('hy', 'Armenian'),
    ('az', 'Azerbaijani'),
    ('eu', 'Basque'),
    ('be', 'Belarusian'),
    ('bs', 'Bosnian'),
    ('bg', 'Bulgarian'),
    ('ca', 'Catalan'),
    ('hr', 'Croatian'),
    ('da', 'Danish'),
    ('et', 'Estonian'),
    ('fi', 'Finnish'),
    ('ka', 'Georgian'),
    ('he', 'Hebrew'),
    ('hu', 'Hungarian'),
    ('id', 'Indonesian'),
    ('ga', 'Irish'),
    ('jv', 'Javanese'),
    ('lv', 'Latvian'),
    ('lt', 'Lithuanian'),
    ('mk', 'Macedonian'),
    ('no', 'Norwegian'),
    ('fa', 'Persian'),
    ('pl', 'Polish'),
    ('ro', 'Romanian'),
    ('sr', 'Serbian'),
    ('sk', 'Slovak'),
    ('sl', 'Slovenian'),
    ('sv', 'Swedish'),
    ('uk', 'Ukrainian'),
    ('cy', 'Welsh'),
]

DEFAULT_ENABLED_LANGUAGE_CODES = frozenset({
    'ar', 'as', 'awa', 'bn', 'bho', 'zh-CN', 'cs', 'dog', 'nl', 'en', 'fr', 'fr-CA',
    'de', 'el', 'gu', 'hi', 'it', 'ja', 'kn', 'ks', 'kok', 'ko', 'mai', 'ms', 'ml',
    'mr', 'mwr', 'mni', 'np', 'or', 'pa', 'pt', 'pt-BR', 'ru', 'sat', 'sd', 'es',
    'sw', 'ta', 'te', 'tr', 'ur', 'vi', 'si', 'ne', 'tl', 'th', 'kk', 'uz',
})

CATALOG_CODES = frozenset(code for code, _ in TRANSLATE_LANGUAGE_CATALOG)


def _catalog_sort_order():
    order = {}
    for index, (code, _) in enumerate(TRANSLATE_LANGUAGE_CATALOG):
        order[code] = 0 if code == 'en' else index + 1
    return order


def ensure_language_catalog():
    """Create catalog rows in DB if missing (safe before/after migrations)."""
    try:
        from core.models import TranslateLanguage
    except Exception:
        return False

    sort_order = _catalog_sort_order()
    for code, name in TRANSLATE_LANGUAGE_CATALOG:
        defaults = {
            'name': name,
            'sort_order': sort_order.get(code, 999),
            'enabled': code in DEFAULT_ENABLED_LANGUAGE_CODES,
        }
        TranslateLanguage.objects.get_or_create(code=code, defaults=defaults)
    return True


def get_enabled_language_codes():
    """Return enabled language codes with English always first.

    Cached because this runs on every request via the template context processor.
    Previously it called ensure_language_catalog() on every read, issuing one
    query per catalog language (80+ DB queries on every page load).
    """
    fallback = ','.join(
        ['en'] + sorted(DEFAULT_ENABLED_LANGUAGE_CODES - {'en'})
    ).split(',')
    try:
        cached = cache.get(ENABLED_LANGUAGE_CODES_CACHE_KEY)
    except Exception:
        cached = None
    if cached is not None:
        return cached
    try:
        from core.models import TranslateLanguage
        codes = list(
            TranslateLanguage.objects.filter(enabled=True)
            .order_by('sort_order', 'name')
            .values_list('code', flat=True)
        )
        if not codes:
            # Table not yet populated (e.g. fresh DB): build the catalog once, then retry.
            ensure_language_catalog()
            codes = list(
                TranslateLanguage.objects.filter(enabled=True)
                .order_by('sort_order', 'name')
                .values_list('code', flat=True)
            )
        result = _normalize_codes(codes) if codes else _normalize_codes(fallback)
    except (ProgrammingError, OperationalError):
        return _normalize_codes(fallback)
    except Exception:
        return _normalize_codes(fallback)
    try:
        cache.set(ENABLED_LANGUAGE_CODES_CACHE_KEY, result, ENABLED_LANGUAGE_CODES_CACHE_TTL)
    except Exception:
        pass
    return result


def clear_enabled_language_codes_cache():
    """Invalidate the cached enabled-language codes (call after admin toggles languages)."""
    try:
        cache.delete(ENABLED_LANGUAGE_CODES_CACHE_KEY)
    except Exception:
        pass


def _normalize_codes(codes):
    valid = [code for code in codes if code in CATALOG_CODES]
    if 'en' not in valid:
        valid.insert(0, 'en')
    else:
        valid = ['en'] + [code for code in valid if code != 'en']
    return valid


def get_enabled_languages_csv():
    return ','.join(get_enabled_language_codes())


def get_language_choices_for_admin():
    """Rows for admin checkbox UI: list of dicts with code, name, enabled, required."""
    try:
        from core.models import TranslateLanguage
        ensure_language_catalog()
        rows = list(TranslateLanguage.objects.all().order_by('sort_order', 'name'))
        return [
            {
                'code': row.code,
                'name': row.name,
                'enabled': row.enabled or row.code == 'en',
                'required': row.code == 'en',
            }
            for row in rows
        ]
    except (ProgrammingError, OperationalError):
        return [
            {
                'code': code,
                'name': name,
                'enabled': code in DEFAULT_ENABLED_LANGUAGE_CODES,
                'required': code == 'en',
            }
            for code, name in TRANSLATE_LANGUAGE_CATALOG
        ]
    except Exception:
        return []
