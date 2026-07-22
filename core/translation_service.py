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


def _strip_code_fences(raw):
    raw = (raw or '').strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.IGNORECASE)
        raw = re.sub(r'\s*```$', '', raw)
    return raw.strip()


def _extract_json_blob(raw):
    """Pull the first JSON object or array from messy model output."""
    raw = _strip_code_fences(raw)
    if not raw:
        raise ValueError('Empty model response')

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    for opener, closer in (('{', '}'), ('[', ']')):
        start = raw.find(opener)
        end = raw.rfind(closer)
        if start == -1 or end <= start:
            continue
        candidate = raw[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise ValueError('Model response was not valid JSON')


def _coerce_texts_list(data, expected_len):
    if isinstance(data, dict):
        if isinstance(data.get('texts'), list):
            data = data['texts']
        else:
            raise ValueError('Expected JSON object with a "texts" array')
    if not isinstance(data, list):
        raise ValueError('Expected JSON array of strings')
    items = [str(item) if item is not None else '' for item in data]
    if len(items) != expected_len:
        raise ValueError(f'Expected {expected_len} segments, got {len(items)}')
    return items


def _parse_adjusted_texts(raw, expected_len):
    return _coerce_texts_list(_extract_json_blob(raw), expected_len)


def _call_gemini(prompt):
    import google.generativeai as genai

    api_key = getattr(settings, 'GOOGLE_API_KEY', '')
    genai.configure(api_key=api_key)
    model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-1.5-flash')
    model = genai.GenerativeModel(model_name)
    generation_config = {
        'temperature': 0.2,
        'max_output_tokens': 4096,
        'response_mime_type': 'application/json',
    }
    try:
        response = model.generate_content(prompt, generation_config=generation_config)
    except Exception as exc:
        logger.warning('Gemini JSON mime type unavailable, retrying plain: %s', exc)
        generation_config.pop('response_mime_type', None)
        response = model.generate_content(prompt, generation_config=generation_config)
    return (response.text or '').strip()


def _call_openai(prompt):
    import openai

    client = openai.OpenAI(api_key=getattr(settings, 'OPENAI_API_KEY', ''))
    model_name = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')
    kwargs = {
        'model': model_name,
        'temperature': 0.2,
        'messages': [
            {
                'role': 'system',
                'content': (
                    'You return only valid JSON objects shaped like '
                    '{"texts": ["...", "..."]} with no markdown or commentary.'
                ),
            },
            {'role': 'user', 'content': prompt},
        ],
    }
    # Prefer JSON object mode when the model supports it; fall back if not.
    try:
        response = client.chat.completions.create(
            response_format={'type': 'json_object'},
            **kwargs,
        )
    except Exception as exc:
        logger.warning('OpenAI json_object mode unavailable, retrying plain: %s', exc)
        response = client.chat.completions.create(**kwargs)
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


def _adjust_batch_with_retry(batch_texts, target_lang, level):
    """
    Call the model (retry once). On persistent failure return originals so the
    page keeps Google Translate output instead of surfacing a JSON error.
    """
    prompt = build_adjustment_prompt(batch_texts, target_lang, level)
    last_error = None
    for attempt in range(2):
        try:
            raw = _call_model(prompt)
            return _parse_adjusted_texts(raw, len(batch_texts))
        except Exception as exc:
            last_error = exc
            logger.warning(
                'Translation complexity attempt %s failed: %s',
                attempt + 1,
                exc,
            )
    logger.exception(
        'Translation complexity adjustment failed after retries; keeping originals: %s',
        last_error,
    )
    return list(batch_texts)


def adjust_text_complexity(texts, target_lang, level):
    """
    Return adjusted text segments for the given complexity level.
    Medium returns inputs unchanged. Model/parse failures keep originals.
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
        adjusted = _adjust_batch_with_retry(batch_texts, target_lang, level)

        for (index, original), value in zip(batch, adjusted):
            results[index] = value
            # Only cache successful rewrites (not silent fallbacks).
            if value and value != original:
                cache_key = _cache_key(normalized[index], target_lang, level)
                cache.set(cache_key, value, _CACHE_TTL)

    return results
