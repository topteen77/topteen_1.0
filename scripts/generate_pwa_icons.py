#!/usr/bin/env python3
"""Generate TopTeen PWA / install icons (white canvas, centered logo)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parents[1]
ICON_DIR = BASE_DIR / 'static' / 'images_new' / 'fav-icon'
LOGO_SOURCE = ICON_DIR / 'favicon-96x96.png'


def _make_icon(size: int) -> Image.Image:
    canvas = Image.new('RGBA', (size, size), (255, 255, 255, 255))

    margin = int(size * 0.14)
    max_w = size - (margin * 2)
    max_h = size - (margin * 2)

    logo = Image.open(LOGO_SOURCE).convert('RGBA')
    scale = min(max_w / logo.width, max_h / logo.height)
    logo = logo.resize(
        (max(1, int(logo.width * scale)), max(1, int(logo.height * scale))),
        Image.Resampling.LANCZOS,
    )

    x = (size - logo.width) // 2
    y = (size - logo.height) // 2
    canvas.paste(logo, (x, y), logo)
    return canvas.convert('RGB')


def main() -> None:
    if not LOGO_SOURCE.is_file():
        raise SystemExit(f'Missing logo source: {LOGO_SOURCE}')

    outputs = {
        'pwa-icon-512x512.png': 512,
        'pwa-icon-192x192.png': 192,
        'android-chrome-512x512.png': 512,
        'android-chrome-192x192.png': 192,
        'web-app-manifest-512x512.png': 512,
        'web-app-manifest-192x192.png': 192,
        'apple-touch-icon.png': 180,
    }

    for filename, size in outputs.items():
        out = ICON_DIR / filename
        _make_icon(size).save(out, format='PNG', optimize=True)
        print(f'wrote {out} ({size}x{size})')


if __name__ == '__main__':
    main()
