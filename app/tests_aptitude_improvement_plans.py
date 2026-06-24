from django.test import TestCase

from app.aptitude_improvement_plans import (
    CLASS_10,
    CLASS_12,
    build_improvement_plans_for_below_areas,
    parse_improvement_plan_docx,
    resolve_improvement_plan_area_key,
    seed_class_10_plans_from_class_12,
    upsert_class_12_plans_from_docx,
)
from app.models import AptitudeImprovementPlan

DOCX_PATH = (
    '/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/'
    'improvement plan- 12.docx'
)


class AptitudeImprovementPlanTests(TestCase):
    def test_parse_class_12_docx_has_eight_areas(self):
        rows = parse_improvement_plan_docx(DOCX_PATH)
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]['area_key'], 'language_skills')
        self.assertGreaterEqual(len(rows[0]['improvement_plan_items']), 4)

    def test_seed_and_lookup_class_12_below_areas(self):
        upsert_class_12_plans_from_docx(DOCX_PATH)
        seed_class_10_plans_from_class_12()
        self.assertEqual(
            AptitudeImprovementPlan.objects.filter(education_level=CLASS_12).count(),
            8,
        )
        self.assertEqual(
            AptitudeImprovementPlan.objects.filter(education_level=CLASS_10).count(),
            7,
        )
        plans = build_improvement_plans_for_below_areas(
            ['Language and Verbal Reasoning', 'Spatial Reasoning'],
            education_level=CLASS_12,
        )
        self.assertEqual(len(plans), 2)
        self.assertIn('Language & Verbal Reasoning', plans[0]['Area'])

    def test_resolve_class_10_reasoning_codes(self):
        self.assertEqual(resolve_improvement_plan_area_key('VERBAL', CLASS_10), 'verbal')
        self.assertEqual(resolve_improvement_plan_area_key('MECHANICAL', CLASS_10), 'mechanical')
