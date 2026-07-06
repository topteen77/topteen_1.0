from django.test import SimpleTestCase, override_settings

from core.pwa_version import get_pwa_cache_version


class PWACacheVersionTests(SimpleTestCase):
    def test_manual_override(self):
        with override_settings(PWA_CACHE_VERSION='manual-99'):
            self.assertEqual(get_pwa_cache_version(), 'manual-99')

    def test_auto_returns_non_empty_string(self):
        with override_settings(PWA_CACHE_VERSION='auto'):
            version = get_pwa_cache_version()
        self.assertTrue(version)
        self.assertNotEqual(version, 'auto')
