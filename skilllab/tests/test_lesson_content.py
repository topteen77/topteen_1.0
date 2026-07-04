from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from skilllab.models import SkillLabChapterSection, SkillLabCourse
from skilllab.views import _prepare_lesson_content_html, _strip_empty_content_breaks


class LessonContentHtmlTests(TestCase):
    def test_strip_empty_nbsp_paragraph(self):
        html = '<p>Students guess the career.</p><p>&nbsp;</p><h3>Sample</h3>'
        cleaned = _strip_empty_content_breaks(html)
        self.assertNotIn('&nbsp;', cleaned)
        self.assertIn('Students guess the career.', cleaned)
        self.assertIn('<h3>Sample</h3>', cleaned)

    def test_prepare_lesson_content_trims_list_whitespace(self):
        html = '<ul>\n<li> First item </li>\n<li>Second</li>\n</ul>'
        cleaned = _prepare_lesson_content_html(html)
        self.assertIn('<li>First item</li>', cleaned)
        self.assertIn('<li>Second</li>', cleaned)


class SkillLabSectionContentViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.course = SkillLabCourse.objects.filter(slug='career-awareness').first()
        cls.section = None
        if cls.course:
            cls.section = SkillLabChapterSection.objects.filter(
                chapter__skilllab=cls.course,
                title__icontains='Guess the Career',
            ).first()
        User = get_user_model()
        cls.user = User.objects.filter(is_active=True).first()
        if cls.user is None:
            cls.user = User.objects.create_user(
                email='skilllab_lesson_test@example.com',
                name='Lesson Test User',
                password='test-pass-123',
            )

    def test_section_content_renders_lesson_prose_markup(self):
        if not self.course or not self.section:
            self.skipTest('career-awareness course or Guess the Career section not in DB')

        self.client.force_login(self.user)
        url = reverse('skilllabcourse:section_content')
        response = self.client.get(url, {
            'section_type': 'intro',
            'section_id': self.section.id,
            'course_slug': self.course.slug,
        })
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('skilllab-lesson-prose', html)
        self.assertNotIn('ckeditorStyles', html)
        self.assertNotIn('<p>&nbsp;</p>', html)
        self.assertNotIn('<p>\xa0</p>', html)
        self.assertIn('<ul>', html)
        self.assertIn('Sample Clues', html)
