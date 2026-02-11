from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import OlympiadExam, OlympiadQuestion, OlympiadRegistration, OlympiadSession

User = get_user_model()


class OlympiadModelsTestCase(TestCase):
    def test_create_exam(self):
        exam = OlympiadExam.objects.create(
            name="Class 8 Mock",
            level=1,
            class_level=8,
            duration_minutes=60,
            total_marks=60,
            is_published=True,
            status='published',
        )
        self.assertEqual(exam.name, "Class 8 Mock")
        self.assertEqual(exam.level, 1)
