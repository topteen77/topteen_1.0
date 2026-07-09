#!/usr/bin/env python3
"""Generate TopTeen PWA icons and splash screens (logo + tagline)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parents[1]
ICON_DIR = BASE_DIR / 'static' / 'images_new' / 'fav-icon'
LOGO_SOURCE = ICON_DIR / 'favicon-96x96.png'
TAGLINE = 'Explore Careers. Discover Your Strengths. Shape Your Future.'

# Portrait splash sizes for iOS startup images (width x height).
SPLASH_SIZES = {
    'pwa-splash-1170x2532.png': (1170, 2532),   # iPhone 14/15
    'pwa-splash-1284x2778.png': (1284, 2778),   # iPhone 14 Pro Max
    'pwa-splash-1080x1920.png': (1080, 1920),   # Android / generic
}


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    )
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = ' '.join(current + [word])
        if draw.textlength(trial, font=font) <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(' '.join(current))
            current = [word]
    if current:
        lines.append(' '.join(current))
    return lines


def _make_icon(size: int) -> Image.Image:
    """Home-screen icon: logo only on white."""
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


def _make_splash(width: int, height: int) -> Image.Image:
    """Full splash: logo + tagline (for system startup + in-app launch)."""
    canvas = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    logo_max_w = int(width * 0.62)
    logo = Image.open(LOGO_SOURCE).convert('RGBA')
    scale = logo_max_w / logo.width
    logo = logo.resize(
        (max(1, int(logo.width * scale)), max(1, int(logo.height * scale))),
        Image.Resampling.LANCZOS,
    )

    font_size = max(28, int(width * 0.052))
    font = _load_font(font_size)
    text_max_w = int(width * 0.82)
    lines = _wrap_text(draw, TAGLINE, font, text_max_w)
    line_height = int(font_size * 1.45)
    text_block_h = line_height * len(lines)
    gap = int(height * 0.045)
    block_h = logo.height + gap + text_block_h
    top_y = (height - block_h) // 2

    logo_x = (width - logo.width) // 2
    canvas.paste(logo, (logo_x, top_y), logo)

    text_y = top_y + logo.height + gap
    for line in lines:
        line_w = draw.textlength(line, font=font)
        draw.text(
            ((width - line_w) // 2, text_y),
            line,
            fill=(26, 35, 126),
            font=font,
        )
        text_y += line_height

    return canvas


def main() -> None:
    if not LOGO_SOURCE.is_file():
        raise SystemExit(f'Missing logo source: {LOGO_SOURCE}')

    icon_outputs = {
        'pwa-icon-512x512.png': 512,
        'pwa-icon-192x192.png': 192,
        'android-chrome-512x512.png': 512,
        'android-chrome-192x192.png': 192,
        'web-app-manifest-512x512.png': 512,
        'web-app-manifest-192x192.png': 192,
        'apple-touch-icon.png': 180,
    }

    for filename, size in icon_outputs.items():
        out = ICON_DIR / filename
        _make_icon(size).save(out, format='PNG', optimize=True)
        print(f'wrote {out} ({size}x{size})')

    for filename, (w, h) in SPLASH_SIZES.items():
        out = ICON_DIR / filename
        _make_splash(w, h).save(out, format='PNG', optimize=True)
        print(f'wrote {out} ({w}x{h})')


if __name__ == '__main__':
    main()
