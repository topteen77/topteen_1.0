"""Tests for local graph image media URLs and serving."""

import os
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from app.graph_media_utils import (
    graph_image_filename,
    graph_image_media_url,
    graph_image_path,
    graph_images_directory,
)


class GraphMediaUtilsTest(SimpleTestCase):
    def test_filename_replaces_spaces_with_underscores(self):
        name = graph_image_filename('Gagandeep Toor', 2964, 'intelligence')
        self.assertEqual(name, 'Gagandeep_Toor-2964_intelligence_Assessment.png')

    def test_media_url_uses_underscores_not_spaces(self):
        url = graph_image_media_url('Gagandeep Toor', 2964, 'personality')
        self.assertEqual(
            url,
            '/media/graph_images/Gagandeep_Toor-2964_personality_Assessment.png',
        )

    def test_media_url_encodes_email_at_sign(self):
        url = graph_image_media_url('student@yopmail.com', 42, 'interest')
        self.assertIn('%40', url)
        self.assertTrue(url.endswith('_interest_Assessment.png'))

    def test_graph_path_uses_media_root(self):
        path = graph_image_path('Test User', 1, 'personality')
        self.assertTrue(path.startswith(str(settings.MEDIA_ROOT)))
        self.assertTrue(path.endswith('Test_User-1_personality_Assessment.png'))


class GraphMediaServingTest(SimpleTestCase):
    def test_serve_graph_image_via_static_view(self):
        """Static serve resolves underscore-based graph filenames."""
        from django.http import HttpRequest
        from django.views.static import serve

        path = graph_image_path('Test Encode User', 9999, 'personality')
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        path_obj.write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 64)
        self.addCleanup(lambda: path_obj.unlink(missing_ok=True))

        request = HttpRequest()
        request.method = 'GET'
        relative = os.path.join('graph_images', graph_image_filename('Test Encode User', 9999, 'personality'))
        response = serve(request, relative, document_root=settings.MEDIA_ROOT)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')

    def test_existing_gagandeep_graph_file_readable(self):
        """Sanity check against real dev data if present."""
        directory = graph_images_directory()
        sample = directory / 'Gagandeep_Toor-2964_intelligence_Assessment.png'
        if sample.is_file():
            url = graph_image_media_url('Gagandeep Toor', 2964, 'intelligence')
            encoded_name = url.split('/')[-1]
            self.assertEqual(encoded_name, 'Gagandeep_Toor-2964_intelligence_Assessment.png')
            self.assertTrue(os.path.isfile(graph_image_path('Gagandeep Toor', 2964, 'intelligence')))
