"""
Centralized breadcrumb service.
Contract: breadcrumb is always a list of dicts with keys: text, url, title (optional).
First item is always Home; last item is current page (url may be empty for current).
"""
from core.utils import build_breadcrumb as _build_breadcrumb


def get_breadcrumb(segments, home_url='/'):
    """
    Build a full breadcrumb list (Home + segments). Normalized for templates.

    Args:
        segments: List of dicts, each with at least 'text'; 'url' and 'title' optional.
                  For current page, pass url='' or omit url.
        home_url: URL for Home (default '/').

    Returns:
        List of dicts: [{"text": "Home", "url": home_url, "title": "Home"}, ...].
        Each segment is normalized to have keys: text, url, title.
    """
    if segments is None:
        segments = []
    normalized = []
    for s in segments:
        if isinstance(s, dict):
            normalized.append({
                'text': s.get('text', s.get('title', '')),
                'url': s.get('url', ''),
                'title': s.get('title', s.get('text', '')),
            })
        else:
            normalized.append({'text': str(s), 'url': '', 'title': str(s)})
    if home_url != '/':
        # Admin or custom home
        lst = [{'title': 'Home', 'text': 'Home', 'url': home_url}]
        lst.extend(normalized)
        return lst
    return _build_breadcrumb(normalized)


def build_breadcrumb(list_of_dict):
    """
    Backward-compatible alias: same as core.utils.build_breadcrumb.
    Prepends Home (/) and returns list. Use get_breadcrumb() for new code.
    """
    return _build_breadcrumb(list_of_dict)
