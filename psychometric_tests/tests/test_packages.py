from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core import choices
from core.assessment_access import (
    build_class10_psychometric_page_context,
    can_access_psychometric_dashboard,
    get_student_custom_package_names,
    get_student_entitled_assessment_codes,
    get_student_psychometric_dashboard_cta,
    has_assessment_access,
    has_class10_test_access,
    has_legacy_full_bundle_access,
)
from core.psychometric_grade import CLASS10_TRACK
from institute.models import ClassAndSection, Institute, StudentManagement
from psychometric_tests.models import (
    Assessment,
    PsychometricPackage,
    StudentAssessmentEntitlement,
)
from psychometric_tests.package_assignment import (
    PackageAssignmentError,
    add_assignment_credits,
    assign_package_by_code,
)
from psychometric_tests.package_catalog import DEFAULT_PACKAGES


User = get_user_model()


@override_settings(ENABLE_PSYCHOMETRIC_PACKAGES=True)
class PsychometricPackageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command('seed_psychometric_packages')

    def setUp(self):
        self.institute = Institute.objects.create(
            name='Package Test School',
            psychometric_access_mode=choices.PsychometricAccessMode.PACKAGE,
            credit_counts=10,
            assignment_credits=10,
        )
        self.cas = ClassAndSection.objects.create(class_and_section='10 A')
        self.admin = User.objects.create_user(
            email='admin@package.test',
            password='pass1234',
        )
        self.student = User.objects.create_user(
            email='student@package.test',
            password='pass1234',
        )
        StudentManagement.objects.create(
            institute=self.institute,
            student=self.student,
            class_and_section=self.cas,
        )

    def test_seed_creates_packages_with_credit_costs(self):
        personality = PsychometricPackage.objects.get(code='pkg_c10_personality')
        full_bundle = PsychometricPackage.objects.get(code='pkg_stream_sorter_full')
        self.assertEqual(personality.credit_cost, 1)
        self.assertEqual(full_bundle.credit_cost, 4)

    def test_assign_package_deducts_credits_and_grants_entitlement(self):
        assign_package_by_code(
            self.student,
            'pkg_c10_personality',
            self.institute,
            assigned_by=self.admin,
        )
        self.institute.refresh_from_db()
        self.assertEqual(self.institute.assignment_credits, 9)
        self.assertTrue(
            has_assessment_access(self.student, 'class10_personality')
        )
        self.assertFalse(
            has_assessment_access(self.student, 'class10_interest')
        )

    def test_combo_package_grants_multiple_entitlements(self):
        assign_package_by_code(
            self.student,
            'pkg_c10_pers_interest',
            self.institute,
            assigned_by=self.admin,
        )
        entitled = get_student_entitled_assessment_codes(self.student)
        self.assertIn('class10_personality', entitled)
        self.assertIn('class10_interest', entitled)
        self.assertNotIn('class10_aptitude', entitled)
        self.institute.refresh_from_db()
        self.assertEqual(self.institute.assignment_credits, 8)

    def test_insufficient_credits_raises(self):
        self.institute.assignment_credits = 0
        self.institute.save(update_fields=['assignment_credits'])
        with self.assertRaises(PackageAssignmentError):
            assign_package_by_code(
                self.student,
                'pkg_c10_personality',
                self.institute,
            )

    def test_legacy_full_bundle_institute_student_has_full_access(self):
        legacy_institute = Institute.objects.create(
            name='Legacy School',
            psychometric_access_mode=choices.PsychometricAccessMode.FULL_BUNDLE,
            credit_counts=5,
        )
        legacy_student = User.objects.create_user(
            email='legacy@package.test',
            password='pass1234',
        )
        StudentManagement.objects.create(
            institute=legacy_institute,
            student=legacy_student,
            class_and_section=self.cas,
        )
        self.assertTrue(has_legacy_full_bundle_access(legacy_student))
        self.assertTrue(has_class10_test_access(legacy_student, 'test1'))
        self.assertTrue(has_class10_test_access(legacy_student, 'test3'))

    def test_package_student_can_access_dashboard_with_entitlement(self):
        assign_package_by_code(
            self.student,
            'pkg_c10_personality',
            self.institute,
        )
        self.assertTrue(can_access_psychometric_dashboard(self.student))

    def test_package_student_without_assignment_cannot_access_dashboard(self):
        self.assertFalse(can_access_psychometric_dashboard(self.student))

    def test_package_student_login_redirects_to_psychometric_home(self):
        from users.views import _compute_student_destination

        assign_package_by_code(
            self.student,
            'pkg_c10_personality',
            self.institute,
        )
        dest = _compute_student_destination(self.student)
        self.assertEqual(dest, reverse('app:test_buttons'))

    def test_package_student_login_uses_dashboard_when_all_entitled_tests_done(self):
        from app.models import TestCompletion
        from users.views import _compute_student_destination

        assign_package_by_code(
            self.student,
            'pkg_c10_personality',
            self.institute,
        )
        tc, _ = TestCompletion.objects.get_or_create(user=self.student)
        tc.test1_complete = True
        tc.save(update_fields=['test1_complete'])
        dest = _compute_student_destination(self.student)
        self.assertEqual(dest, reverse('users:userdashboard'))

    def test_package_student_dashboard_shows_view_report_after_personality_complete(self):
        from app.models import TestCompletion

        assign_package_by_code(
            self.student,
            'pkg_c10_personality',
            self.institute,
        )
        tc, _ = TestCompletion.objects.get_or_create(user=self.student)
        tc.test1_complete = True
        tc.save(update_fields=['test1_complete'])

        cta = get_student_psychometric_dashboard_cta(self.student)
        self.assertEqual(cta['action_label'], 'View report')
        self.assertEqual(cta['action_variant'], 'report')
        self.assertEqual(cta['url'], reverse('app:test1_report_html'))
        self.assertEqual(cta['subtitle'], 'Class 10 Personality')

    def test_custom_package_name_visible_for_single_test_assignment(self):
        assign_package_by_code(
            self.student,
            'pkg_c10_personality',
            self.institute,
        )
        names = get_student_custom_package_names(self.student)
        self.assertEqual(names, ['Class 10 Personality'])

    def test_custom_package_name_hidden_for_legacy_bundle_assignment(self):
        assign_package_by_code(
            self.student,
            'pkg_stream_sorter_full',
            self.institute,
        )
        self.assertEqual(get_student_custom_package_names(self.student), [])

    def test_submit_page_context_hides_non_entitled_tests(self):
        assign_package_by_code(
            self.student,
            'pkg_c10_personality',
            self.institute,
        )
        page_ctx = build_class10_psychometric_page_context(self.student)
        self.assertFalse(page_ctx['show_all_psychometric_tests'])
        self.assertTrue(page_ctx['test_access']['test1'])
        self.assertFalse(page_ctx['test_access']['test2'])
        self.assertFalse(page_ctx['test_access']['test3'])

    def test_institute_roster_shows_only_entitled_assessments(self):
        from app.models import TestCompletion
        from institute.psychometric_packages import build_student_roster_assessment_display

        assign_package_by_code(
            self.student,
            'pkg_c10_personality',
            self.institute,
        )
        tc, _ = TestCompletion.objects.get_or_create(user=self.student)
        tc.test1_complete = True
        tc.save(update_fields=['test1_complete'])
        display = build_student_roster_assessment_display(
            self.student,
            {'test_details': {'test1': True, 'test2': False, 'test3': False}},
            is_senior=False,
        )
        self.assertEqual(len(display['rows']), 1)
        self.assertEqual(display['rows'][0]['label'], 'Personality Assessment')
        self.assertTrue(display['rows'][0]['attempted'])
        self.assertEqual(display['package_labels'], ['Class 10 Personality'])
        self.assertFalse(display['report_ready'])
        self.assertEqual(display['report_url'], '')

    def test_institute_roster_report_disabled_until_entitled_tests_complete(self):
        from institute.psychometric_packages import build_student_roster_assessment_display

        assign_package_by_code(
            self.student,
            'pkg_c10_pers_interest',
            self.institute,
        )
        display = build_student_roster_assessment_display(
            self.student,
            {'test_details': {'test1': True, 'test2': False, 'test3': False}},
            is_senior=False,
        )
        self.assertEqual(len(display['rows']), 2)
        self.assertFalse(display['report_ready'])
        self.assertEqual(display['report_url'], '')

    def test_package_student_dashboard_shows_resume_while_entitled_tests_incomplete(self):
        from app.models import TestCompletion

        assign_package_by_code(
            self.student,
            'pkg_c10_pers_interest',
            self.institute,
        )
        tc, _ = TestCompletion.objects.get_or_create(user=self.student)
        tc.test1_complete = True
        tc.save(update_fields=['test1_complete'])

        cta = get_student_psychometric_dashboard_cta(self.student)
        self.assertEqual(cta['action_label'], 'Resume')
        self.assertEqual(cta['action_variant'], 'start')
        self.assertEqual(cta['url'], reverse('app:test_buttons'))

    def test_add_assignment_credits_from_tieup(self):
        add_assignment_credits(self.institute, 25)
        self.institute.refresh_from_db()
        self.assertEqual(self.institute.assignment_credits, 35)


@override_settings(ENABLE_PSYCHOMETRIC_PACKAGES=False)
class PsychometricPackageDisabledTests(TestCase):
    def test_institute_student_still_has_legacy_access_when_disabled(self):
        institute = Institute.objects.create(
            name='Disabled Flag School',
            psychometric_access_mode=choices.PsychometricAccessMode.PACKAGE,
            credit_counts=5,
        )
        student = User.objects.create_user(
            email='disabled@package.test',
            password='pass1234',
        )
        StudentManagement.objects.create(
            institute=institute,
            student=student,
            class_and_section=ClassAndSection.objects.create(class_and_section='10 B'),
        )
        self.assertTrue(has_legacy_full_bundle_access(student))
