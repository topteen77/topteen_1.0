"""Loan Desk PWA endpoints — separate installable app scoped to /loan-desk/."""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpResponse


def _ops_pwa_enabled() -> bool:
    try:
        from users.models import EducationLoanOpsSettings

        return bool(EducationLoanOpsSettings.load().pwa_enabled)
    except Exception:
        return True


def _icon_url(request, path: str) -> str:
    return request.build_absolute_uri(staticfiles_storage.url(path))


def loan_desk_manifest_response(request):
    if not _ops_pwa_enabled():
        return HttpResponse(status=404)

    manifest = {
        "name": "TopTeen Loan Desk",
        "short_name": "Loan Desk",
        "description": "Follow up education loan enquiries for TopTeen.",
        "start_url": "/loan-desk/login/",
        "scope": "/loan-desk/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#eef3f4",
        "theme_color": "#0b3d4a",
        "icons": [
            {
                "src": _icon_url(request, "images_new/fav-icon/pwa-icon-192x192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": _icon_url(request, "images_new/fav-icon/pwa-icon-512x512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": _icon_url(request, "images_new/fav-icon/pwa-icon-192x192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "maskable",
            },
            {
                "src": _icon_url(request, "images_new/fav-icon/pwa-icon-512x512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    return HttpResponse(
        json.dumps(manifest, indent=2),
        content_type="application/manifest+json",
    )


def loan_desk_service_worker_response(request):
    if not _ops_pwa_enabled():
        return HttpResponse(status=404)

    sw_path = Path(settings.BASE_DIR) / "static" / "js_new" / "loan-desk-service-worker.js"
    if not sw_path.exists():
        return HttpResponse("// missing loan-desk SW", content_type="application/javascript")
    content = sw_path.read_text(encoding="utf-8")
    try:
        from core.pwa_version import get_pwa_cache_version

        version = get_pwa_cache_version()
    except Exception:
        version = "1"
    content = content.replace("__PWA_CACHE_VERSION__", version)
    response = HttpResponse(content, content_type="application/javascript")
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Service-Worker-Allowed"] = "/loan-desk/"
    return response
