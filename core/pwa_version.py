import hashlib
import subprocess
from pathlib import Path

from django.conf import settings


def _git_short_sha(base_dir: Path) -> str | None:
    try:
        return (
            subprocess.check_output(
                ['git', 'rev-parse', '--short', 'HEAD'],
                cwd=base_dir,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            .strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return None


def _static_bundle_fingerprint(base_dir: Path) -> str:
    """Hash key PWA-cached assets when git metadata is unavailable."""
    paths = [
        base_dir / 'static' / 'js_new' / 'pwa-service-worker.js',
        base_dir / 'static' / 'js_new' / 'main.js',
        base_dir / 'static' / 'css_new' / 'custom-min.css',
        base_dir / 'static' / 'js_new' / 'pwa-register.js',
    ]
    digest = hashlib.sha256()
    for path in paths:
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def get_pwa_cache_version() -> str:
    """
    Service-worker cache busting id.

    Manual override: PWA_CACHE_VERSION=20260706 in .env
    Automatic (default): PWA_CACHE_VERSION=auto
      - git short SHA on deploy machines with .git
      - otherwise fingerprint of core static bundle files
    """
    configured = str(getattr(settings, 'PWA_CACHE_VERSION', 'auto')).strip()
    if configured and configured.lower() != 'auto':
        return configured

    base_dir = Path(settings.BASE_DIR)
    git_sha = _git_short_sha(base_dir)
    if git_sha:
        return git_sha
    return _static_bundle_fingerprint(base_dir)
