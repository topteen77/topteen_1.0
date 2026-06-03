"""Dashboard career chip links — only published, active careers from the catalog."""

import re
from urllib.parse import urlencode

from django.urls import reverse

from core import choices

_MATCH_STOPWORDS = frozenset({'and', 'or', 'the', 'of', 'a', 'an'})


def _normalize_career_label(name):
    return ' '.join(str(name or '').split()).strip()


def _tokens(text):
    normalized = re.sub(r'[&/,+()\-–—]', ' ', str(text or '').lower())
    return [t for t in normalized.split() if len(t) > 1 and t not in _MATCH_STOPWORDS]


def _name_variants(name):
    n = _normalize_career_label(name)
    if not n:
        return []
    variants = {n, n.lower()}
    lower = n.lower()
    if ' and ' in lower:
        variants.add(re.sub(r'\s+and\s+', ' & ', n, flags=re.IGNORECASE))
    if ' & ' in n:
        variants.add(n.replace(' & ', ' and '))
        variants.add(n.replace(' & ', ' And '))
    return list(variants)


def published_active_careers_qs():
    from careers.models import Career

    return Career.objects.filter(
        publish_status=choices.PublishStatus.PUBLISHED,
        object_status=choices.ObjectStatus.ACTIVE,
    ).only('id', 'name', 'slug')


def _career_detail_url(career):
    return reverse('careers:careerdetail', args=[career.slug, career.id])


def resolve_published_career(label):
    """
    Map a dashboard suggestion label to a published, active Career row.
    Returns None when no suitable catalog career exists (chip should be hidden).
    """
    name = _normalize_career_label(label)
    if not name:
        return None

    qs = published_active_careers_qs()

    for variant in _name_variants(name):
        career = qs.filter(name__iexact=variant).first()
        if career:
            return career

    label_tokens = _tokens(name)
    if not label_tokens:
        return None

    for token in label_tokens:
        if len(token) >= 4:
            career = qs.filter(name__iexact=token).first()
            if career:
                return career

    if len(label_tokens) >= 2:
        token_set = set(label_tokens)
        pair_candidates = [label_tokens[:2]]
        if 'science' in token_set:
            pair_candidates.append(['data', 'scientist'])
        if 'engineering' in token_set:
            pair_candidates.append([label_tokens[0], 'engineer'])
        if 'design' in token_set and 'interior' in token_set:
            pair_candidates.append(['interior', 'design'])

        seen_pairs = set()
        for pair in pair_candidates:
            key = tuple(pair)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            phrase_qs = qs.filter(name__istartswith=pair[0].capitalize())
            for token in pair[1:]:
                phrase_qs = phrase_qs.filter(name__icontains=token)
            career = (
                phrase_qs.exclude(name__icontains='technician')
                .order_by('name')
                .first()
            )
            if not career and pair[0] != pair[0].capitalize():
                phrase_qs = qs.filter(name__icontains=pair[0])
                for token in pair[1:]:
                    phrase_qs = phrase_qs.filter(name__icontains=token)
                career = (
                    phrase_qs.exclude(name__icontains='technician')
                    .order_by('name')
                    .first()
                )
            if career:
                return career

    norm_label = name.lower()
    prefix_matches = []
    first_token = label_tokens[0]
    if len(first_token) >= 4:
        for career in qs.filter(name__istartswith=first_token):
            cn_lower = (career.name or '').strip().lower()
            if cn_lower and (norm_label.startswith(cn_lower) or cn_lower in norm_label):
                prefix_matches.append(career)
    if prefix_matches:
        return min(prefix_matches, key=lambda c: len(c.name or ''))

    candidates = []
    seen_ids = set()
    for token in label_tokens:
        if len(token) < 4:
            continue
        for career in qs.filter(name__icontains=token).order_by('name')[:40]:
            if career.id not in seen_ids:
                seen_ids.add(career.id)
                candidates.append(career)

    label_token_set = set(label_tokens)
    ranked = []
    for career in candidates:
        career_tokens = set(_tokens(career.name))
        if not career_tokens:
            continue
        score = len(label_token_set & career_tokens)
        if score < 1:
            continue
        name_lower = (career.name or '').lower()
        penalty = sum(
            1 for term in ('technician', 'trainee', 'helper', 'assistant', 'operator')
            if term in name_lower
        )
        ranked.append((score, penalty, len(career.name or ''), career))

    if not ranked:
        return None
    ranked.sort(key=lambda row: (-row[0], row[1], row[2]))
    return ranked[0][3]


def resolve_career_items_for_labels(labels):
    """
    Build chip items {name, url} for labels that resolve to published active careers.
    Uses catalog career name on the chip; skips unresolved / inactive careers.
    """
    items = []
    seen_career_ids = set()
    for label in labels or []:
        display = _normalize_career_label(label)
        if not display:
            continue
        career = resolve_published_career(display)
        if not career or career.id in seen_career_ids:
            continue
        seen_career_ids.add(career.id)
        items.append({
            'name': career.name,
            'url': _career_detail_url(career),
        })
    return items


def enrich_career_groups_chip_urls(groups):
    """Keep only enabled catalog careers; attach detail URLs (no report/search fallbacks)."""
    kept = []
    for group in groups or []:
        items = resolve_career_items_for_labels(group.get('careers') or [])
        if not items:
            continue
        group['career_items'] = items
        group['careers'] = [item['name'] for item in items]
        group.pop('page_url', None)
        group.pop('page_label', None)
        kept.append(group)
    return kept
