"""
Site-wide voice-to-text mode
(Admin → Configuration hub → Voice to text settings).

Modes:
  off      — hide mic / voice UI everywhere
  browser  — Web Speech API (free; Chrome/Edge; not Safari iOS)
  openai   — OpenAI gpt-4o-mini-transcribe via server proxy
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


def get_voice_to_text_mode() -> str:
    """Resolve mode from Configuration, with ENABLE_VOICE_TO_TEXT / settings fallback."""
    default = normalize_voice_to_text_mode(
        getattr(settings, 'VOICE_TO_TEXT_MODE', None)
    ) or VOICE_TO_TEXT_BROWSER
    try:
        from core.models import Configuration

        raw = Configuration.get(VOICE_TO_TEXT_MODE_KEY, default='', editable=True)
        mode = normalize_voice_to_text_mode(raw)
        if mode:
            return mode
        # Legacy boolean toggle
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


def voice_to_text_enabled(mode: str | None = None) -> bool:
    return (mode or get_voice_to_text_mode()) != VOICE_TO_TEXT_OFF


def openai_transcribe_available() -> bool:
    return bool((getattr(settings, 'OPENAI_API_KEY', None) or '').strip())
