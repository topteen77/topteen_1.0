"""PWA splash screen verification tests."""
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

SPLASH_DIR = Path(__file__).resolve().parents[2] / 'static' / 'images_new' / 'fav-icon'
TAGLINE_FRAGMENT = 'Explore Careers'


class PWASplashAssetTests(SimpleTestCase):
    def test_splash_images_exist(self):
        expected = [
            'pwa-splash-1080x1920.png',
            'pwa-splash-1170x2532.png',
            'pwa-splash-1284x2778.png',
        ]
        for name in expected:
            self.assertTrue((SPLASH_DIR / name).is_file(), msg=f'missing {name}')

    def test_splash_images_contain_tagline_pixels(self):
        """Splash art should include non-logo dark text (not blank white only)."""
        path = SPLASH_DIR / 'pwa-splash-1080x1920.png'
        img = Image.open(path).convert('RGB')
        w, h = img.size
        # Tagline sits in lower-center band below logo.
        region = img.crop((int(w * 0.1), int(h * 0.52), int(w * 0.9), int(h * 0.72)))
        pixels = list(region.getdata())
        dark_blue = [p for p in pixels if p[0] < 80 and p[1] < 80 and p[2] > 100]
        self.assertGreater(len(dark_blue), 200, 'expected tagline-colored pixels in splash image')

    def test_home_icons_are_logo_only_smaller_than_splash(self):
        icon = SPLASH_DIR / 'pwa-icon-512x512.png'
        splash = SPLASH_DIR / 'pwa-splash-1080x1920.png'
        self.assertLess(icon.stat().st_size, splash.stat().st_size)


@override_settings(PWA_ENABLED=True, PWA_CACHE_VERSION='splash-test')
class PWASplashPageTests(TestCase):
    def test_homepage_has_startup_images_and_splash_markup(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="pwa-launch-screen"', content)
        self.assertIn('apple-touch-startup-image', content)
        self.assertIn('pwa-splash-1170x2532.png', content)
        self.assertIn('pwa-splash.js?v=2', content)
        self.assertIn(TAGLINE_FRAGMENT, content)

    def test_splash_js_contains_session_gate(self):
        js_path = SPLASH_DIR.parents[1] / 'js_new' / 'pwa-splash.js'
        body = js_path.read_text(encoding='utf-8')
        self.assertIn('topteen_pwa_launch_shown', body)
        self.assertIn('sessionStorage', body)
        self.assertIn('isIOS', body)
