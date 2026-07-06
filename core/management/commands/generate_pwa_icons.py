"""
Generate PWA / favicon PNGs from the TopTeen wordmark SVG.

Usage:
    python manage.py generate_pwa_icons
"""
from io import BytesIO
from pathlib import Path

import cairosvg
from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image


ICON_DIR = Path(settings.BASE_DIR) / 'static' / 'images_new' / 'fav-icon'
LOGO_SVG = Path(settings.BASE_DIR) / 'static' / 'images_new' / 'logos' / 'logo.svg'
BRAND_BG = '#ffffff'
MASKABLE_BG = '#3F37C9'  # TopTeen purple from logo mark


def _render_logo(max_width: int) -> Image.Image:
    logo_png = cairosvg.svg2png(
        url=str(LOGO_SVG),
        output_width=max_width,
        output_height=int(max_width * 46 / 156),
    )
    return Image.open(BytesIO(logo_png)).convert('RGBA')


def _solid_canvas(size: int, hex_color: str) -> Image.Image:
    hex_color = hex_color.lstrip('#')
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return Image.new('RGBA', (size, size), (r, g, b, 255))


def _paste_centered(canvas: Image.Image, logo: Image.Image, width_ratio: float) -> Image.Image:
    size = canvas.width
    max_w = int(size * width_ratio)
    ratio = max_w / logo.width
    new_h = max(1, int(logo.height * ratio))
    resized = logo.resize((max_w, new_h), Image.Resampling.LANCZOS)
    x = (size - max_w) // 2
    y = (size - new_h) // 2
    canvas.paste(resized, (x, y), resized)
    return canvas


def _icon_on_background(size: int, bg: str, width_ratio: float) -> Image.Image:
    logo = _render_logo(max_width=900)
    canvas = _solid_canvas(size, bg)
    return _paste_centered(canvas, logo, width_ratio)


def _maskable_icon(size: int) -> Image.Image:
    """Logo centered in the maskable safe zone (~72% of canvas)."""
    logo = _render_logo(max_width=900)
    canvas = _solid_canvas(size, MASKABLE_BG)
    # White wordmark on purple for maskable splash/icon visibility
    white_logo = Image.new('RGBA', logo.size, (0, 0, 0, 0))
    pixels = logo.load()
    wpx = white_logo.load()
    for y in range(logo.height):
        for x in range(logo.width):
            r, g, b, a = pixels[x, y]
            if a < 16:
                continue
            # Keep purple mark; lighten dark text to white on purple bg
            if r + g + b < 380:
                wpx[x, y] = (255, 255, 255, a)
            else:
                wpx[x, y] = (r, g, b, a)
    return _paste_centered(canvas, white_logo, 0.62)


class Command(BaseCommand):
    help = 'Regenerate PWA launcher icons from static/images_new/logos/logo.svg'

    def handle(self, *args, **options):
        if not LOGO_SVG.is_file():
            self.stderr.write(self.style.ERROR(f'Missing logo: {LOGO_SVG}'))
            return

        ICON_DIR.mkdir(parents=True, exist_ok=True)
        targets = {
            'android-chrome-192x192.png': _icon_on_background(192, BRAND_BG, 0.78),
            'android-chrome-512x512.png': _icon_on_background(512, BRAND_BG, 0.78),
            'web-app-manifest-192x192.png': _maskable_icon(192),
            'web-app-manifest-512x512.png': _maskable_icon(512),
            'apple-touch-icon.png': _icon_on_background(180, BRAND_BG, 0.76),
            'favicon-96x96.png': _icon_on_background(96, BRAND_BG, 0.72),
        }
        for name, image in targets.items():
            path = ICON_DIR / name
            image.convert('RGB').save(path, format='PNG', optimize=True)
            self.stdout.write(self.style.SUCCESS(f'Wrote {path}'))

        self.stdout.write(self.style.SUCCESS('PWA icons generated. Redeploy static files.'))
