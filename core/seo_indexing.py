from django.conf import settings


def resolve_allow_search_engine_index(request=None):
    """Whether pages should be indexable (meta robots + robots.txt allow rules)."""
    if getattr(settings, 'ALLOW_SEARCH_ENGINE_INDEX', False):
        return True
    if not request:
        return False
    if not getattr(settings, 'ALLOW_DEMO_SEARCH_INDEX', True):
        return False
    host = request.get_host().split(':')[0].lower()
    return host in ('demo.topteen.in', 'localhost', '127.0.0.1', 'testserver')
