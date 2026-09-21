"""
Inject the shared Google Analytics (gtag.js) snippet into HTML responses.

The snippet lives in templates/includes/google_analytics.html. Middleware
strips any previous gtag.js blocks (old IDs or duplicates), then inserts
exactly one copy of the current tag before </head>.
"""
import re
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, StreamingHttpResponse

DEFAULT_MEASUREMENT_ID = 'G-SX0WYWTMS5'
LEGACY_MEASUREMENT_IDS = ('G-SLK3YZB0SG',)
SNIPPET_RELATIVE_PATH = Path('templates') / 'includes' / 'google_analytics.html'

# Optional HTML comment Google ships with the snippet, plus the loader script
# and the inline dataLayer/gtag('config') block.
_GTAG_COMMENT_RE = re.compile(
    br'<!--\s*Google tag\s*\(gtag\.js\)\s*-->\s*',
    re.I,
)
_GTAG_LOADER_RE = re.compile(
    br'<script\b[^>]*\bsrc=["\']https://www\.googletagmanager\.com/gtag/js\?id=[^"\']+["\'][^>]*>\s*</script>\s*',
    re.I,
)
_GTAG_INLINE_RE = re.compile(
    br'<script\b[^>]*>[^<]*\bdataLayer\b[^<]*\bfunction gtag\s*\([^<]*gtag\s*\(\s*[\'"]config[\'"][^<]*</script>\s*',
    re.I,
)

_SKIP_PATH_PREFIXES = (
    '/static/',
    '/media/',
    '/api/',
    '/__debug__/',
    '/ws/',
    '/socket.io/',
    '/health/',
    '/metrics/',
    '/.well-known/',
)


def _measurement_id():
    return getattr(settings, 'GA_MEASUREMENT_ID', DEFAULT_MEASUREMENT_ID) or DEFAULT_MEASUREMENT_ID


def _default_snippet(measurement_id):
    return (
        '<!-- Google tag (gtag.js) -->\n'
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>\n'
        '<script>\n'
        '  window.dataLayer = window.dataLayer || [];\n'
        '  function gtag(){dataLayer.push(arguments);}\n'
        "  gtag('js', new Date());\n"
        '\n'
        f"  gtag('config', '{measurement_id}');\n"
        '</script>\n'
    )


def load_gtag_snippet():
    measurement_id = _measurement_id()
    snippet_path = Path(settings.BASE_DIR) / SNIPPET_RELATIVE_PATH
    try:
        snippet = snippet_path.read_text(encoding='utf-8').strip()
        if snippet:
            return snippet + '\n'
    except OSError:
        pass
    return _default_snippet(measurement_id)


class GtagMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.snippet = load_gtag_snippet()
        self.measurement_id = _measurement_id()

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(settings, 'ENABLE_GOOGLE_ANALYTICS', True):
            return response
        return self._inject(request, response)

    def _should_skip(self, request, response):
        if request.method == 'HEAD':
            return True
        if isinstance(response, (StreamingHttpResponse, FileResponse)):
            return True
        if response.status_code < 200 or response.status_code >= 300:
            if response.status_code not in (400, 403, 404):
                return True
        path = request.path or ''
        for prefix in _SKIP_PATH_PREFIXES:
            if path.startswith(prefix):
                return True
        content_type = (response.get('Content-Type') or '').lower()
        if content_type and 'text/html' not in content_type:
            return True
        if not hasattr(response, 'content'):
            return True
        return False

    def _inject(self, request, response):
        if self._should_skip(request, response):
            return response
        try:
            content = response.content
        except Exception:
            return response
        if not content:
            return response

        content = _strip_gtag_blocks(content)
        charset = getattr(response, 'charset', None) or 'utf-8'
        try:
            snippet = self.snippet.encode(charset)
        except LookupError:
            snippet = self.snippet.encode('utf-8')

        lower = content.lower()
        insert_at = lower.find(b'</head>')
        if insert_at == -1:
            insert_at = lower.find(b'<body')
        if insert_at == -1:
            return response

        response.content = content[:insert_at] + snippet + content[insert_at:]
        if response.has_header('Content-Length'):
            response['Content-Length'] = str(len(response.content))
        return response


def _strip_gtag_blocks(content):
    """Remove every gtag.js loader/config block so only one canonical tag remains."""
    content = _GTAG_COMMENT_RE.sub(b'', content)
    content = _GTAG_LOADER_RE.sub(b'', content)
    content = _GTAG_INLINE_RE.sub(b'', content)
    for old_id in LEGACY_MEASUREMENT_IDS:
        old = re.escape(old_id).encode('utf-8')
        content = re.sub(
            br'<script\b[^>]*>[^<]*' + old + br'[^<]*</script>\s*',
            b'',
            content,
            flags=re.I,
        )
    return content
