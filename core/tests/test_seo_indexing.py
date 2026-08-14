from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from core.seo_indexing import resolve_allow_search_engine_index
from core.seo_views import robots_txt


class SEOIndexingTests(SimpleTestCase):
    def test_demo_host_allows_index_when_enabled(self):
        request = RequestFactory().get('/', HTTP_HOST='demo.topteen.in')
        with override_settings(ALLOW_SEARCH_ENGINE_INDEX=False, ALLOW_DEMO_SEARCH_INDEX=True):
            self.assertTrue(resolve_allow_search_engine_index(request))

    def test_demo_host_blocked_when_disabled(self):
        request = RequestFactory().get('/', HTTP_HOST='demo.topteen.in')
        with override_settings(ALLOW_SEARCH_ENGINE_INDEX=False, ALLOW_DEMO_SEARCH_INDEX=False):
            self.assertFalse(resolve_allow_search_engine_index(request))


class SEOIndexingRobotsTests(TestCase):
    def test_robots_txt_valid_when_not_indexable(self):
        request = RequestFactory().get('/robots.txt', HTTP_HOST='staging.example.com')
        with override_settings(ALLOW_SEARCH_ENGINE_INDEX=False, ALLOW_DEMO_SEARCH_INDEX=False):
            response = robots_txt(request)
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/plain', response['Content-Type'])
        self.assertIn('User-agent: facebookexternalhit', body)
        self.assertIn('User-agent: Facebot', body)
        self.assertIn('Disallow: /', body)
        # Meta bots must be allowed before the catch-all Disallow.
        self.assertLess(body.index('facebookexternalhit'), body.index('User-agent: *'))

    def test_robots_txt_allows_when_demo_indexable(self):
        request = RequestFactory().get('/robots.txt', HTTP_HOST='demo.topteen.in')
        with override_settings(ALLOW_SEARCH_ENGINE_INDEX=False, ALLOW_DEMO_SEARCH_INDEX=True):
            response = robots_txt(request)
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('Allow: /', body)
        self.assertIn('Sitemap:', body)
