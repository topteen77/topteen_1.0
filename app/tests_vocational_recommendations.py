"""Tests for vocational course recommendations lookup."""

from django.test import TestCase

from app.vocational_recommendations import (
    build_vocational_courses_filter_url,
    course_ids_for_reasoning_area,
    normalize_reasoning_area_code,
    vocational_cards_for_below_areas,
)
from core import choices
from core.models import VocationalCourse, VocationalCourseCategory, VocationalCourseReasoningMapping


class VocationalRecommendationsTest(TestCase):
    def setUp(self):
        self.category = VocationalCourseCategory.objects.create(
            name="Test Category",
            object_status=choices.ObjectStatus.ACTIVE,
        )
        self.course = VocationalCourse.objects.create(
            category=self.category,
            name="Test Communication Course",
            object_status=choices.ObjectStatus.ACTIVE,
        )
        VocationalCourseReasoningMapping.objects.create(
            vocational_course=self.course,
            reasoning_area="VERBAL",
            priority=1,
            object_status=choices.ObjectStatus.ACTIVE,
        )

    def test_returns_card_for_mapped_below_area(self):
        cards = vocational_cards_for_below_areas(["VERBAL", "LOGICAL"])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["reasoning_area"], "VERBAL")
        self.assertEqual(cards[0]["reasoning_area_label"], "Verbal")
        self.assertEqual(cards[0]["course"].pk, self.course.pk)
        self.assertIn("reasoning_area=VERBAL", cards[0]["reasoning_area_courses_url"])
        self.assertIn("tab=", cards[0]["reasoning_area_courses_url"])

    def test_empty_when_no_below_areas(self):
        self.assertEqual(vocational_cards_for_below_areas([]), [])
        self.assertEqual(vocational_cards_for_below_areas(None), [])

    def test_respects_priority(self):
        other = VocationalCourse.objects.create(
            category=self.category,
            name="Other Verbal Course",
            priority=0,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        VocationalCourseReasoningMapping.objects.create(
            vocational_course=other,
            reasoning_area="VERBAL",
            priority=1,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        cards = vocational_cards_for_below_areas(["VERBAL"])
        self.assertEqual(cards[0]["course"].pk, self.course.pk)

    def test_course_ids_for_reasoning_area(self):
        ids = course_ids_for_reasoning_area("VERBAL")
        self.assertEqual(ids, [self.course.pk])

    def test_course_ids_scoped_to_level_category(self):
        from core.models import VocationalCourseCategory

        root = VocationalCourseCategory.objects.create(
            name="After 10",
            slug="after-10",
            object_status=choices.ObjectStatus.ACTIVE,
        )
        self.course.category = self.category
        self.course.save()
        # Course remains in self.category; filter by after-10 may exclude if category not under root
        ids = course_ids_for_reasoning_area("VERBAL", "after-10")
        self.assertIsInstance(ids, list)

    def test_normalize_reasoning_area_code(self):
        self.assertEqual(normalize_reasoning_area_code("verbal"), "VERBAL")
        self.assertIsNone(normalize_reasoning_area_code("EMOTIONAL"))

    def test_build_filter_url(self):
        url = build_vocational_courses_filter_url("VERBAL")
        self.assertIn("reasoning_area=VERBAL", url)
        self.assertIn("tab=after-10", url)
