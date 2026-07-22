"""
Adjust translated page text to easy / medium / hard reading levels via Gemini or OpenAI.

Successful LLM results are stored in Redis (cache alias ``translations``) and
checked before any model call so repeated page/language/level combinations skip the LLM.
"""

import hashlib
import json
import logging
import re

from django.conf import settings
from django.core.cache import caches

from core.translation_complexity import (
    TRANSLATION_BATCH_CHAR_LIMIT,
    TRANSLATION_MAX_SEGMENTS,
    build_adjustment_prompt,
    complexity_needs_adjustment,
    is_valid_complexity,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = 60 * 60 * 24 * 30  # 30 days
_TRANSLATION_CACHE_ALIAS = 'translations'


def translation_complexity_available():
    provider = getattr(settings, 'AI_PROVIDER', 'none')
    if provider == 'gemini' and getattr(settings, 'GOOGLE_API_KEY', ''):
        return True
    if provider == 'openai' and getattr(settings, 'OPENAI_API_KEY', ''):
        return True
    return bool(getattr(settings, 'GOOGLE_API_KEY', '') or getattr(settings, 'OPENAI_API_KEY', ''))


def _translation_cache():
    """Prefer dedicated Redis translations alias; fall back to default cache."""
    try:
        return caches[_TRANSLATION_CACHE_ALIAS]
    except Exception:
        return caches['default']


def _cache_key(text, target_lang, level):
    digest = hashlib.sha256(f'{level}|{target_lang}|{text}'.encode('utf-8')).hexdigest()
    return f'tt_translate_complexity:{digest}'


def _cache_get(key):
    try:
        return _translation_cache().get(key)
    except Exception as exc:
        logger.warning('Translation Redis get failed: %s', exc)
        return None


def _cache_set(key, value):
    try:
        _translation_cache().set(key, value, _CACHE_TTL)
        return True
    except Exception as exc:
        logger.warning('Translation Redis set failed: %s', exc)
        return False


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


def _call_gemini(prompt, user=None, request=None):
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
    try:
        from core.llm_billing import log_gemini_response
        log_gemini_response(
            feature='translation',
            response=response,
            model=model_name,
            call_type='chat',
            user=user,
            consume=True,
            request=request,
            metadata={'source': 'core.translation_service._call_gemini'},
        )
    except Exception:
        pass
    return (response.text or '').strip()


def _call_openai(prompt, user=None, request=None):
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
    try:
        from core.llm_billing import log_openai_response
        log_openai_response(
            feature='translation',
            response=response,
            model=model_name,
            call_type='chat',
            user=user,
            consume=True,
            request=request,
            metadata={'source': 'core.translation_service._call_openai'},
        )
    except Exception:
        pass
    return (response.choices[0].message.content or '').strip()


def _call_model(prompt, user=None, request=None):
    provider = getattr(settings, 'AI_PROVIDER', 'none')
    if provider == 'openai' and getattr(settings, 'OPENAI_API_KEY', ''):
        return _call_openai(prompt, user=user, request=request)
    if getattr(settings, 'GOOGLE_API_KEY', ''):
        return _call_gemini(prompt, user=user, request=request)
    if getattr(settings, 'OPENAI_API_KEY', ''):
        return _call_openai(prompt, user=user, request=request)
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


def _adjust_batch_with_retry(batch_texts, target_lang, level, user=None, request=None):
    """
    Call the model (retry once).
    Returns (texts, from_llm) where from_llm is True only on a successful parse.
    On persistent failure return originals so the page keeps Google Translate output.
    """
    prompt = build_adjustment_prompt(batch_texts, target_lang, level)
    last_error = None
    for attempt in range(2):
        try:
            raw = _call_model(prompt, user=user, request=request)
            return _parse_adjusted_texts(raw, len(batch_texts)), True
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
    return list(batch_texts), False


def adjust_text_complexity(texts, target_lang, level, user=None, request=None):
    """
    Return (adjusted_texts, stats) for the given complexity level.
    Medium returns inputs unchanged. Model/parse failures keep originals.

    Flow: Redis lookup per segment → LLM only for misses → store every successful
    LLM translation back into Redis.

    stats: {cache_hits, cache_misses, llm_calls, stored}
    """
    empty_stats = {
        'cache_hits': 0,
        'cache_misses': 0,
        'llm_calls': 0,
        'stored': 0,
        'from_cache': False,
    }
    if not texts:
        return [], empty_stats
    if not is_valid_complexity(level):
        raise ValueError('Invalid complexity level')
    if not complexity_needs_adjustment(level):
        return list(texts), empty_stats

    if not translation_complexity_available():
        raise RuntimeError('Translation complexity is not configured')

    normalized = [(text or '').strip() for text in texts]
    results = list(normalized)
    uncached = []
    cache_hits = 0

    for index, text in enumerate(normalized):
        if not text:
            continue
        cache_key = _cache_key(text, target_lang, level)
        cached = _cache_get(cache_key)
        if cached is not None:
            results[index] = cached
            cache_hits += 1
            logger.info(
                'Translation Redis HIT lang=%s level=%s key=%s…',
                target_lang,
                level,
                cache_key[-12:],
            )
        else:
            uncached.append((index, text, cache_key))

    cache_misses = len(uncached)
    stored = 0
    llm_calls = 0

    if not uncached:
        logger.info(
            'Translation all from Redis cache hits=%s lang=%s level=%s',
            cache_hits,
            target_lang,
            level,
        )
        return results, {
            'cache_hits': cache_hits,
            'cache_misses': 0,
            'llm_calls': 0,
            'stored': 0,
            'from_cache': cache_hits > 0,
        }

    from core.llm_quota import ensure_can_use_llm

    ensure_can_use_llm(user, feature='translation', request=request)

    for batch in _batch_indices([(i, t) for i, t, _ in uncached]):
        batch_texts = [text for _, text in batch]
        llm_calls += 1
        adjusted, from_llm = _adjust_batch_with_retry(
            batch_texts, target_lang, level, user=user, request=request
        )

        for (index, _original), value in zip(batch, adjusted):
            results[index] = value
            # Store any successful LLM translation in Redis (skip silent fallbacks).
            if from_llm and value:
                cache_key = _cache_key(normalized[index], target_lang, level)
                if _cache_set(cache_key, value):
                    stored += 1

    logger.info(
        'Translation Redis hits=%s misses=%s llm_calls=%s stored=%s lang=%s level=%s',
        cache_hits,
        cache_misses,
        llm_calls,
        stored,
        target_lang,
        level,
    )
    return results, {
        'cache_hits': cache_hits,
        'cache_misses': cache_misses,
        'llm_calls': llm_calls,
        'stored': stored,
        'from_cache': cache_hits > 0 and cache_misses == 0,
    }
