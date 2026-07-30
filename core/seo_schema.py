"""
Dynamic SEO schema (JSON-LD) builders for all pages.
Supports: Organization, WebSite, BreadcrumbList, WebPage, Article, FAQPage.
"""
from datetime import datetime


def _ensure_absolute_url(url, base_url):
    """If url is relative, make it absolute using base_url."""
    if not url:
        return base_url.rstrip('/') if base_url else ''
    if url.startswith(('http://', 'https://')):
        return url
    base = (base_url or '').rstrip('/')
    return base + ('/' + url.lstrip('/') if url else '')


def get_organization_schema(site_base_url, site_name='TopTeen', logo_url=None):
    """
    Build Organization schema (schema.org) for the site.
    Used once per site; include on every page for brand recognition.
    """
    base = (site_base_url or '').rstrip('/')
    schema = {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        'name': site_name or 'TopTeen',
        'url': base or 'https://www.topteen.in',
        'description': (
            'TopTeen helps students find their perfect career path with confidence. '
            'Join 10k+ students working towards figuring out their ideal streams and colleges.'
        ),
        'logo': logo_url or (base + '/static/images_new/fav-icon/apple-icon-114x114.png' if base else None),
    }
    if schema['logo']:
        schema['logo'] = _ensure_absolute_url(schema['logo'], base)
    return schema


def get_website_schema(site_base_url, site_name='TopTeen', search_url=None):
    """
    Build WebSite schema with optional SearchAction (for sitelinks search box).
    """
    base = (site_base_url or '').rstrip('/') or 'https://www.topteen.in'
    schema = {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': site_name or 'TopTeen',
        'url': base,
        'description': (
            'TopTeen helps students find their perfect career path with confidence. '
            'Join 10k+ students working towards figuring out their ideal streams and colleges.'
        ),
        'publisher': {
            '@type': 'Organization',
            'name': site_name or 'TopTeen',
            'url': base,
        },
    }
    if search_url:
        schema['potentialAction'] = {
            '@type': 'SearchAction',
            'target': {
                '@type': 'EntryPoint',
                'urlTemplate': search_url if search_url.startswith('http') else (base + search_url),
            },
            'query-input': 'required name=search_term_string',
        }
    return schema


def get_breadcrumb_schema(breadcrumb_list, base_url, current_page_url=None):
    """
    Build BreadcrumbList schema from list of {text, url, title}.
    breadcrumb_list: first item is Home, last is current page (url may be '').
    current_page_url: full URL of current page; used for last item when segment url is empty.
    """
    if not breadcrumb_list:
        return None
    base = (base_url or '').rstrip('/') or 'https://www.topteen.in'
    items = []
    for i, seg in enumerate(breadcrumb_list):
        name = seg.get('title') or seg.get('text') or ''
        url = seg.get('url') or ''
        if url and not url.startswith(('http://', 'https://')):
            url = _ensure_absolute_url(url, base)
        elif not url and i == len(breadcrumb_list) - 1 and current_page_url:
            url = current_page_url
        items.append({
            '@type': 'ListItem',
            'position': i + 1,
            'name': name,
            'item': url or current_page_url if (i == len(breadcrumb_list) - 1) else url,
        })
    # Schema requires 'item' for each ListItem; keep only non-empty
    for it in items:
        if not it.get('item'):
            del it['item']
    if not items:
        return None
    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': items,
    }


def get_webpage_schema(html_head, page_url, site_name='TopTeen', schema_type='WebPage', extra=None):
    """
    Build WebPage or Article schema from html_head and current page URL.
    html_head: dict with title, description, image, url (optional).
    schema_type: 'WebPage' or 'Article'.
    extra: dict for Article - date_published (ISO), date_modified (ISO), author (str or dict).
    """
    extra = extra or {}
    if not html_head and not page_url:
        return None
    base = (page_url or '').split('/')[0] + '//' + (page_url or '').split('/')[2] if page_url else 'https://www.topteen.in'
    title = (html_head or {}).get('title') or 'Every Student, Career Ready'
    description = (html_head or {}).get('description') or (
        'TopTeen helps students find their perfect career path with confidence.'
    )
    image = (html_head or {}).get('image')
    if image and not image.startswith(('http://', 'https://')):
        image = _ensure_absolute_url(image, base)
    canonical = (html_head or {}).get('url') or page_url

    schema = {
        '@context': 'https://schema.org',
        '@type': schema_type,
        'name': title if schema_type == 'WebPage' else None,
        'headline': title if schema_type == 'Article' else None,
        'description': description,
        'url': canonical,
    }
    if schema_type == 'WebPage':
        if schema.get('name') is None:
            schema['name'] = title
    else:
        if 'name' in schema:
            del schema['name']
        if schema.get('headline') is None:
            schema['headline'] = title
    if image:
        schema['image'] = image
    if schema_type == 'Article':
        if extra.get('date_published'):
            schema['datePublished'] = extra['date_published']
        if extra.get('date_modified'):
            schema['dateModified'] = extra['date_modified']
        if extra.get('author'):
            a = extra['author']
            if isinstance(a, dict):
                schema['author'] = {'@type': 'Person', **a}
            else:
                schema['author'] = {'@type': 'Organization', 'name': a}
        if extra.get('publisher'):
            schema['publisher'] = extra['publisher']
        else:
            schema['publisher'] = {'@type': 'Organization', 'name': site_name or 'TopTeen', 'url': base}
    # Remove None values
    schema = {k: v for k, v in schema.items() if v is not None}
    return schema


def get_faq_schema(faq_items, base_url=None):
    """
    Build FAQPage schema from list of {question, answer}.
    faq_items: list of dicts with 'question' and 'answer' keys.
    """
    if not faq_items:
        return None
    base = (base_url or '').rstrip('/') or 'https://www.topteen.in'
    main_entity = []
    for item in faq_items:
        q = item.get('question') or item.get('name') or ''
        a = item.get('answer') or item.get('content') or ''
        if q:
            main_entity.append({
                '@type': 'Question',
                'name': q,
                'acceptedAnswer': {'@type': 'Answer', 'text': a},
            })
    if not main_entity:
        return None
    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': main_entity,
    }
