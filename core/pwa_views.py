import json
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpResponse

from core.pwa_version import get_pwa_cache_version


def _pwa_enabled():
    return getattr(settings, 'PWA_ENABLED', True)


def _icon_url(request, path):
    return request.build_absolute_uri(staticfiles_storage.url(path))


def manifest_json(request):
    if not _pwa_enabled():
        return HttpResponse(status=404)

    manifest = {
        'name': 'TopTeen — Explore Careers. Discover Your Strengths. Shape Your Future.',
        'short_name': 'TopTeen',
        'description': (
            'Explore Careers. Discover Your Strengths. Shape Your Future.'
        ),
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'orientation': 'portrait-primary',
        'background_color': '#ffffff',
        'theme_color': '#ffffff',
        'icons': [
            {
                'src': _icon_url(request, 'images_new/fav-icon/pwa-icon-192x192.png'),
                'sizes': '192x192',
                'type': 'image/png',
                'purpose': 'any',
            },
            {
                'src': _icon_url(request, 'images_new/fav-icon/pwa-icon-512x512.png'),
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'any',
            },
            {
                'src': _icon_url(request, 'images_new/fav-icon/pwa-icon-192x192.png'),
                'sizes': '192x192',
                'type': 'image/png',
                'purpose': 'maskable',
            },
            {
                'src': _icon_url(request, 'images_new/fav-icon/pwa-icon-512x512.png'),
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'maskable',
            },
        ],
    }
    return HttpResponse(
        json.dumps(manifest, indent=2),
        content_type='application/manifest+json',
    )


def service_worker_js(request):
    if not _pwa_enabled():
        return HttpResponse(status=404)

    sw_path = Path(settings.BASE_DIR) / 'static' / 'js_new' / 'pwa-service-worker.js'
    content = sw_path.read_text(encoding='utf-8')
    version = get_pwa_cache_version()
    content = content.replace('__PWA_CACHE_VERSION__', version)

    response = HttpResponse(content, content_type='application/javascript')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Service-Worker-Allowed'] = '/'
    return response
