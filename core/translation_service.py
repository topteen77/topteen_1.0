"""
Adjust translated page text to easy / medium / hard reading levels via Gemini or OpenAI.
"""

import hashlib
import json
import logging
import re

from django.conf import settings
from django.core.cache import cache

from core.translation_complexity import (
    TRANSLATION_BATCH_CHAR_LIMIT,
    TRANSLATION_MAX_SEGMENTS,
    build_adjustment_prompt,
    complexity_needs_adjustment,
    is_valid_complexity,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = 60 * 60 * 24 * 7  # 7 days


def translation_complexity_available():
    provider = getattr(settings, 'AI_PROVIDER', 'none')
    if provider == 'gemini' and getattr(settings, 'GOOGLE_API_KEY', ''):
        return True
    if provider == 'openai' and getattr(settings, 'OPENAI_API_KEY', ''):
        return True
    return bool(getattr(settings, 'GOOGLE_API_KEY', '') or getattr(settings, 'OPENAI_API_KEY', ''))


def _cache_key(text, target_lang, level):
    digest = hashlib.sha256(f'{level}|{target_lang}|{text}'.encode('utf-8')).hexdigest()
    return f'tt_translate_complexity:{digest}'


def _parse_json_array(raw):
    raw = (raw or '').strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError('Expected JSON array')
    return [str(item) if item is not None else '' for item in data]


def _call_gemini(prompt):
    import google.generativeai as genai

    api_key = getattr(settings, 'GOOGLE_API_KEY', '')
    genai.configure(api_key=api_key)
    model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-1.5-flash')
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        prompt,
        generation_config={
            'temperature': 0.2,
            'max_output_tokens': 4096,
        },
    )
    return (response.text or '').strip()


def _call_openai(prompt):
    import openai

    client = openai.OpenAI(api_key=getattr(settings, 'OPENAI_API_KEY', ''))
    model_name = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')
    response = client.chat.completions.create(
        model=model_name,
        temperature=0.2,
        messages=[
            {
                'role': 'system',
                'content': 'You return only valid JSON arrays of strings.',
            },
            {'role': 'user', 'content': prompt},
        ],
    )
    return (response.choices[0].message.content or '').strip()


def _call_model(prompt):
    provider = getattr(settings, 'AI_PROVIDER', 'none')
    if provider == 'openai' and getattr(settings, 'OPENAI_API_KEY', ''):
        return _call_openai(prompt)
    if getattr(settings, 'GOOGLE_API_KEY', ''):
        return _call_gemini(prompt)
    if getattr(settings, 'OPENAI_API_KEY', ''):
        return _call_openai(prompt)
    raise RuntimeError('No AI provider configured for translation complexity')


def _batch_indices(items):
    """Group (index, text) tuples into API batches."""
    batches = []
    current = []
    current_len = 0
    for index, text in items:
        piece_len = len(text)
        if (
            current
            and (
                len(current) >= TRANSLATION_MAX_SEGMENTS
                or current_len + piece_len > TRANSLATION_BATCH_CHAR_LIMIT
            )
        ):
            batches.append(current)
            current = [(index, text)]
            current_len = piece_len
        else:
            current.append((index, text))
            current_len += piece_len
    if current:
        batches.append(current)
    return batches


def adjust_text_complexity(texts, target_lang, level):
    """
    Return adjusted text segments for the given complexity level.
    Medium returns inputs unchanged.
    """
    if not texts:
        return []
    if not is_valid_complexity(level):
        raise ValueError('Invalid complexity level')
    if not complexity_needs_adjustment(level):
        return list(texts)

    if not translation_complexity_available():
        raise RuntimeError('Translation complexity is not configured')

    normalized = [(text or '').strip() for text in texts]
    results = list(normalized)
    uncached = []

    for index, text in enumerate(normalized):
        if not text:
            continue
        cache_key = _cache_key(text, target_lang, level)
        cached = cache.get(cache_key)
        if cached is not None:
            results[index] = cached
        else:
            uncached.append((index, text, cache_key))

    for batch in _batch_indices([(i, t) for i, t, _ in uncached]):
        batch_texts = [text for _, text in batch]
        prompt = build_adjustment_prompt(batch_texts, target_lang, level)
        try:
            raw = _call_model(prompt)
            adjusted = _parse_json_array(raw)
        except Exception as exc:
            logger.exception('Translation complexity adjustment failed: %s', exc)
            raise

        if len(adjusted) != len(batch_texts):
            raise ValueError(
                f'Expected {len(batch_texts)} segments, got {len(adjusted)}'
            )

        for (index, _), value in zip(batch, adjusted):
            results[index] = value
            cache_key = _cache_key(normalized[index], target_lang, level)
            cache.set(cache_key, value, _CACHE_TTL)

    return results
