#!/usr/bin/env python3
"""Verify voice-to-text mode changes are visible immediately via live API."""
import os
import sys

import django

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

from django.test import Client

from core.models import Configuration
from core.voice_to_text import (
    ENABLE_VOICE_TO_TEXT_KEY,
    VOICE_TO_TEXT_MODE_KEY,
    get_voice_to_text_mode_live,
    voice_settings_payload,
)


def set_mode(mode: str) -> None:
    Configuration.objects.update_or_create(
        key=VOICE_TO_TEXT_MODE_KEY,
        defaults={'value': mode, 'editable': True},
    )
    legacy = 'false' if mode == 'off' else 'true'
    Configuration.objects.update_or_create(
        key=ENABLE_VOICE_TO_TEXT_KEY,
        defaults={'value': legacy, 'editable': True},
    )
    Configuration.clear_cache()


def main() -> int:
    client = Client()
    failed = 0

    def check(label, cond):
        nonlocal failed
        if cond:
            print('OK:', label)
        else:
            failed += 1
            print('FAIL:', label)

    original = get_voice_to_text_mode_live()

    try:
        set_mode('off')
        check('live helper reads off', get_voice_to_text_mode_live() == 'off')
        payload = voice_settings_payload()
        check('payload disabled', payload['mode'] == 'off' and payload['enabled'] is False)

        resp = client.get('/api/voice/settings/')
        check('API status 200 for off', resp.status_code == 200)
        data = resp.json()
        check('API mode off', data.get('mode') == 'off' and data.get('enabled') is False)

        set_mode('browser')
        resp2 = client.get('/api/voice/settings/')
        data2 = resp2.json()
        check('API flips to browser immediately', data2.get('mode') == 'browser' and data2.get('enabled') is True)

        set_mode('openai')
        resp3 = client.get('/api/voice/settings/')
        data3 = resp3.json()
        check('API flips to openai immediately', data3.get('mode') == 'openai' and data3.get('enabled') is True)

        # Simulate stale process cache still holding old value — live API must ignore it.
        Configuration._local_cache = {
            'data': {VOICE_TO_TEXT_MODE_KEY: 'browser', ENABLE_VOICE_TO_TEXT_KEY: 'true'},
            'ts': 10**12,
        }
        set_mode('off')
        # Intentionally poison local cache again after save
        Configuration._local_cache = {
            'data': {VOICE_TO_TEXT_MODE_KEY: 'browser', ENABLE_VOICE_TO_TEXT_KEY: 'true'},
            'ts': 10**12,
        }
        live = get_voice_to_text_mode_live()
        api = client.get('/api/voice/settings/').json()
        check('live bypasses stale local cache', live == 'off')
        check('API bypasses stale local cache', api.get('mode') == 'off')

        # Cloud transcribe must reject when not openai
        set_mode('off')
        deny = client.post('/api/voice/transcribe/')
        check('transcribe blocked when off', deny.status_code in (403, 400))
    finally:
        set_mode(original if original in ('off', 'browser', 'openai') else 'browser')

    if failed:
        print(f'\n{failed} check(s) failed')
        return 1
    print('\nAll live voice-settings checks passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
