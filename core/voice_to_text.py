"""
Site-wide voice-to-text + voice widget settings
(Admin → Configuration hub → Voice to text settings).

Modes:
  off      — hide mic / voice UI everywhere
  browser  — Web Speech API (free; Chrome/Edge; not Safari iOS)
  openai   — OpenAI gpt-4o-mini-transcribe via server proxy

Widget flags are stored as Configuration keys and exposed live via
GET /api/voice/settings/ (DB read — no service restart).
"""
from __future__ import annotations

from django.conf import settings

VOICE_TO_TEXT_OFF = 'off'
VOICE_TO_TEXT_BROWSER = 'browser'
VOICE_TO_TEXT_OPENAI = 'openai'

VOICE_TO_TEXT_MODES = (
    VOICE_TO_TEXT_OFF,
    VOICE_TO_TEXT_BROWSER,
    VOICE_TO_TEXT_OPENAI,
)

VOICE_TO_TEXT_MODE_CHOICES = [
    (VOICE_TO_TEXT_OFF, 'Disabled'),
    (VOICE_TO_TEXT_BROWSER, 'Browser speech (free — Chrome / Edge)'),
    (VOICE_TO_TEXT_OPENAI, 'OpenAI gpt-4o-mini-transcribe (cloud — works on iPhone)'),
]

OPENAI_TRANSCRIBE_MODEL = 'gpt-4o-mini-transcribe'
VOICE_TO_TEXT_MODE_KEY = 'VOICE_TO_TEXT_MODE'
ENABLE_VOICE_TO_TEXT_KEY = 'ENABLE_VOICE_TO_TEXT'

# Widget feature flags (Admin → Voice to text settings)
VOICE_WIDGET_ENABLED_KEY = 'VOICE_WIDGET_ENABLED'
VOICE_NAV_ENABLED_KEY = 'VOICE_NAV_ENABLED'
VOICE_TALK_TYPE_ENABLED_KEY = 'VOICE_TALK_TYPE_ENABLED'
VOICE_LINK_NUMBERS_ENABLED_KEY = 'VOICE_LINK_NUMBERS_ENABLED'
VOICE_NAV_DEFAULT_ON_KEY = 'VOICE_NAV_DEFAULT_ON'
VOICE_TALK_TYPE_DEFAULT_ON_KEY = 'VOICE_TALK_TYPE_DEFAULT_ON'

VOICE_WIDGET_BOOL_KEYS = (
    VOICE_WIDGET_ENABLED_KEY,
    VOICE_NAV_ENABLED_KEY,
    VOICE_TALK_TYPE_ENABLED_KEY,
    VOICE_LINK_NUMBERS_ENABLED_KEY,
    VOICE_NAV_DEFAULT_ON_KEY,
    VOICE_TALK_TYPE_DEFAULT_ON_KEY,
)

# Defaults when key missing
_VOICE_WIDGET_BOOL_DEFAULTS = {
    VOICE_WIDGET_ENABLED_KEY: True,
    VOICE_NAV_ENABLED_KEY: True,
    VOICE_TALK_TYPE_ENABLED_KEY: True,
    VOICE_LINK_NUMBERS_ENABLED_KEY: True,
    VOICE_NAV_DEFAULT_ON_KEY: False,
    VOICE_TALK_TYPE_DEFAULT_ON_KEY: True,
}


def normalize_voice_to_text_mode(raw) -> str:
    mode = str(raw or '').strip().lower()
    if mode in VOICE_TO_TEXT_MODES:
        return mode
    if mode in ('true', '1', 'yes', 'on', 'enabled'):
        return VOICE_TO_TEXT_BROWSER
    if mode in ('false', '0', 'no', 'off', 'disabled'):
        return VOICE_TO_TEXT_OFF
    if mode in ('openai_mini', 'gpt-4o-mini-transcribe', 'whisper', 'cloud'):
        return VOICE_TO_TEXT_OPENAI
    return ''


def _parse_bool(raw, default: bool = True) -> bool:
    if raw is None or raw == '':
        return default
    return str(raw).strip().lower() in ('true', '1', 'yes', 'on')


def _default_voice_mode() -> str:
    default = normalize_voice_to_text_mode(
        getattr(settings, 'VOICE_TO_TEXT_MODE', None)
    ) or VOICE_TO_TEXT_BROWSER
    return default


def get_voice_to_text_mode() -> str:
    """Resolve mode from Configuration, with ENABLE_VOICE_TO_TEXT / settings fallback."""
    default = _default_voice_mode()
    try:
        from core.models import Configuration

        raw = Configuration.get(VOICE_TO_TEXT_MODE_KEY, default='', editable=True)
        mode = normalize_voice_to_text_mode(raw)
        if mode:
            return mode
        legacy = Configuration.get(
            ENABLE_VOICE_TO_TEXT_KEY,
            default=str(getattr(settings, 'ENABLE_VOICE_TO_TEXT', True)).lower(),
            editable=True,
        )
        if str(legacy).lower() in ('false', '0', 'no', 'off'):
            return VOICE_TO_TEXT_OFF
        return default if default != VOICE_TO_TEXT_OFF else VOICE_TO_TEXT_BROWSER
    except Exception:
        if not getattr(settings, 'ENABLE_VOICE_TO_TEXT', True):
            return VOICE_TO_TEXT_OFF
        return default


def get_voice_to_text_mode_live() -> str:
    """
    Read mode directly from DB (bypass process-local / Redis config snapshot).
    """
    default = _default_voice_mode()
    try:
        from core.models import Configuration

        row = (
            Configuration.objects.filter(key=VOICE_TO_TEXT_MODE_KEY)
            .only('value')
            .first()
        )
        mode = normalize_voice_to_text_mode(row.value if row else '')
        if mode:
            return mode
        legacy = (
            Configuration.objects.filter(key=ENABLE_VOICE_TO_TEXT_KEY)
            .only('value')
            .first()
        )
        if legacy and str(legacy.value).lower() in ('false', '0', 'no', 'off'):
            return VOICE_TO_TEXT_OFF
        return default if default != VOICE_TO_TEXT_OFF else VOICE_TO_TEXT_BROWSER
    except Exception:
        return get_voice_to_text_mode()


def _read_bool_live(key: str, default: bool) -> bool:
    try:
        from core.models import Configuration

        row = Configuration.objects.filter(key=key).only('value').first()
        if row is None:
            return default
        return _parse_bool(row.value, default)
    except Exception:
        return default


def get_voice_widget_settings_live() -> dict:
    """All widget flags from DB (no config cache)."""
    flags = {}
    for key in VOICE_WIDGET_BOOL_KEYS:
        flags[key] = _read_bool_live(key, _VOICE_WIDGET_BOOL_DEFAULTS[key])
    return flags


def voice_to_text_enabled(mode: str | None = None) -> bool:
    return (mode or get_voice_to_text_mode()) != VOICE_TO_TEXT_OFF


def openai_transcribe_available() -> bool:
    return bool((getattr(settings, 'OPENAI_API_KEY', None) or '').strip())


def voice_settings_payload() -> dict:
    """Live payload for open tabs — admin changes apply without restart."""
    mode = get_voice_to_text_mode_live()
    stt_on = mode != VOICE_TO_TEXT_OFF
    flags = get_voice_widget_settings_live()
    widget_enabled = bool(flags[VOICE_WIDGET_ENABLED_KEY]) and stt_on
    nav_enabled = bool(flags[VOICE_NAV_ENABLED_KEY]) and widget_enabled
    talk_enabled = bool(flags[VOICE_TALK_TYPE_ENABLED_KEY]) and widget_enabled
    link_numbers = bool(flags[VOICE_LINK_NUMBERS_ENABLED_KEY]) and nav_enabled
    return {
        'ok': True,
        'mode': mode,
        'enabled': stt_on,
        'widget_enabled': widget_enabled,
        'nav_enabled': nav_enabled,
        'talk_type_enabled': talk_enabled,
        'link_numbers_enabled': link_numbers,
        'nav_default_on': bool(flags[VOICE_NAV_DEFAULT_ON_KEY]) and nav_enabled,
        'talk_type_default_on': bool(flags[VOICE_TALK_TYPE_DEFAULT_ON_KEY]) and talk_enabled,
        'openai_configured': openai_transcribe_available(),
    }


def save_voice_bool(key: str, value: bool) -> None:
    from core.models import Configuration

    val = 'true' if value else 'false'
    config, _ = Configuration.objects.get_or_create(
        key=key, defaults={'value': val, 'editable': True}
    )
    config.value = val
    config.save()
