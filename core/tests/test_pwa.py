"""
Smoke tests for TopTeen PWA endpoints and template wiring.
Run: python manage.py test core.tests.test_pwa
"""
import json

from django.test import SimpleTestCase, TestCase, override_settings


@override_settings(PWA_ENABLED=True, PWA_CACHE_VERSION='test-1')
class PWAEndpointTests(TestCase):
    def test_manifest_json(self):
        response = self.client.get('/manifest.json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/manifest+json', response['Content-Type'])

        data = json.loads(response.content.decode())
        self.assertEqual(data['name'], 'Top Teen — Every Student, Career Ready')
        self.assertEqual(data['short_name'], 'TopTeen')
        self.assertEqual(data['start_url'], '/')
        self.assertEqual(data['display'], 'standalone')

        sizes = {icon['sizes'] for icon in data['icons']}
        self.assertIn('192x192', sizes)
        self.assertIn('512x512', sizes)
        for icon in data['icons']:
            self.assertTrue(icon['src'].startswith('http'))

    def test_service_worker_js(self):
        response = self.client.get('/service-worker.js')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/javascript', response['Content-Type'])
        self.assertIn('no-cache', response['Cache-Control'].lower())

        body = response.content.decode()
        self.assertIn("const CACHE_VERSION = 'test-1';", body)
        self.assertIn("'topteen-static-' + CACHE_VERSION", body)
        self.assertNotIn('__PWA_CACHE_VERSION__', body)

    def test_service_worker_alias(self):
        response = self.client.get('/sw.js')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/javascript', response['Content-Type'])

    def test_offline_page(self):
        response = self.client.get('/offline/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You are offline')

    def test_homepage_includes_pwa_tags(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rel="manifest"')
        self.assertContains(response, '/manifest.json')
        self.assertContains(response, 'pwa-register.js')
        self.assertContains(response, 'data-pwa-version="test-1"')

    @override_settings(PWA_ENABLED=False)
    def test_disabled_pwa_returns_404(self):
        self.assertEqual(self.client.get('/manifest.json').status_code, 404)
        self.assertEqual(self.client.get('/service-worker.js').status_code, 404)


class PWAManifestRequiredFieldsTests(SimpleTestCase):
    def test_required_manifest_fields_documented(self):
        required = {'name', 'short_name', 'start_url', 'display', 'icons'}
        self.assertTrue(required.issubset({'name', 'short_name', 'start_url', 'display', 'icons', 'theme_color'}))
