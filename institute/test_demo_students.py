"""Tests for marketing institute demo student seeding and conversion."""
from django.test import TestCase, override_settings

from core import choices
from core.assessment_access import has_legacy_full_bundle_access
from core.ttv2_institute_credits import institute_credits_remaining_for_institute
from institute.demo_students import (
    DemoStudentError,
    MAX_DEMO_PER_CLASS,
    MAX_DEMO_SEED_RUNS,
    convert_demo_institute_to_paid,
    remaining_demo_slots,
    seed_institute_demo_students,
)
from institute.models import Institute, StudentManagement
from users.models import User


class MarketingDemoStudentsTests(TestCase):
    def setUp(self):
        self.marketing = User.objects.create_user(
            email="mktg_demo_test@example.com",
            password="pass123",
            name="Marketing",
            user_type=choices.UserType.MARKETINGGROUPADMIN,
        )
        self.inst_user = User.objects.create_user(
            email="inst_demo_test@example.com",
            password="pass123",
            name="Institute Admin",
            user_type=choices.UserType.INSTITUTE,
        )
        self.institute = Institute.objects.create(
            name="Demo Seed School",
            created_by=self.inst_user,
            address="Test Address",
            contact_info="9876543210",
            administrator_contact="9876543211",
            credit_counts=10,
            assignment_credits=20,
            psychometric_access_mode=choices.PsychometricAccessMode.FULL_BUNDLE,
        )

    def test_seed_respects_per_class_cap_and_excludes_from_paid_credits(self):
        before = self.institute.get_current_credits_count()
        result = seed_institute_demo_students(
            self.institute, self.marketing, class10_count=5, class12_count=3
        )
        self.institute.refresh_from_db()
        self.assertEqual(result["class10"], 5)
        self.assertEqual(result["class12"], 3)
        self.assertEqual(self.institute.demo_seed_count, 1)
        self.assertTrue(self.institute.is_demo_institute)
        self.assertEqual(self.institute.get_current_credits_count(), before)
        self.assertEqual(
            institute_credits_remaining_for_institute(self.institute), before
        )
        self.assertEqual(
            StudentManagement.objects.filter(
                institute=self.institute, student__is_demo_account=True
            ).count(),
            8,
        )
        slots = remaining_demo_slots(self.institute)
        self.assertEqual(slots["class10"], 0)
        self.assertEqual(slots["class12"], 2)

    def test_fourth_seed_run_rejected(self):
        for _ in range(MAX_DEMO_SEED_RUNS):
            seed_institute_demo_students(
                self.institute, self.marketing, class10_count=1, class12_count=0
            )
        self.institute.refresh_from_db()
        self.assertEqual(self.institute.demo_seed_count, MAX_DEMO_SEED_RUNS)
        with self.assertRaises(DemoStudentError):
            seed_institute_demo_students(
                self.institute, self.marketing, class10_count=1, class12_count=0
            )

    def test_cannot_exceed_five_per_class_across_seeds(self):
        seed_institute_demo_students(
            self.institute, self.marketing, class10_count=MAX_DEMO_PER_CLASS, class12_count=0
        )
        with self.assertRaises(DemoStudentError):
            seed_institute_demo_students(
                self.institute, self.marketing, class10_count=1, class12_count=0
            )

    @override_settings(ENABLE_PSYCHOMETRIC_PACKAGES=True)
    def test_full_bundle_demo_has_psych_access_without_burning_assignment_credits(self):
        before_assign = self.institute.assignment_credits
        seed_institute_demo_students(
            self.institute, self.marketing, class10_count=1, class12_count=0
        )
        self.institute.refresh_from_db()
        self.assertEqual(self.institute.assignment_credits, before_assign)
        demo = (
            StudentManagement.objects.filter(
                institute=self.institute, student__is_demo_account=True
            )
            .select_related("student")
            .first()
        )
        self.assertIsNotNone(demo)
        self.assertTrue(has_legacy_full_bundle_access(demo.student))

    def test_convert_purges_demos_and_sets_paid_credits(self):
        seed_institute_demo_students(
            self.institute, self.marketing, class10_count=2, class12_count=2
        )
        self.institute.refresh_from_db()
        result = convert_demo_institute_to_paid(
            self.institute,
            self.marketing,
            credit_counts=15,
            assignment_credits=5,
        )
        self.institute.refresh_from_db()
        self.assertEqual(result["removed_demo_students"], 4)
        self.assertFalse(self.institute.is_demo_institute)
        self.assertEqual(self.institute.credit_counts, 15)
        self.assertEqual(self.institute.assignment_credits, 5)
        self.assertEqual(
            StudentManagement.objects.filter(
                institute=self.institute, student__is_demo_account=True
            ).count(),
            0,
        )
        self.assertEqual(self.institute.get_current_credits_count(), 15)
        # Seed history retained
        self.assertGreaterEqual(self.institute.demo_seed_count, 1)

    def test_paid_student_still_consumes_credits(self):
        paid = User.objects.create_user(
            email="paid_stu@example.com",
            password="pass123",
            name="Paid Student",
            user_type=choices.UserType.STUDENT,
            is_demo_account=False,
        )
        StudentManagement.objects.create(institute=self.institute, student=paid)
        self.assertEqual(self.institute.get_current_credits_count(), 9)
        seed_institute_demo_students(
            self.institute, self.marketing, class10_count=2, class12_count=0
        )
        self.assertEqual(self.institute.get_current_credits_count(), 9)
