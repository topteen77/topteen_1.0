import io
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core import choices
from core.assessment_access import has_assessment_access
from core.psychometric_grade import CLASS10_TRACK, POST_MATRIC_TRACK, get_student_psychometric_track
from institute.models import StudentManagement
from users.models import User


@override_settings(ENABLE_PSYCHOMETRIC_PACKAGES=True)
class HigherEdCsvUploadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command('seed_psychometric_packages')

    def setUp(self):
        from institute.models import Institute

        self.institute = Institute.objects.create(
            name='Higher Ed College',
            psychometric_access_mode=choices.PsychometricAccessMode.PACKAGE,
            credit_counts=10,
            assignment_credits=10,
        )
        self.user = User.objects.create_superuser(
            email='upload-admin@higher.test',
            name='Upload Admin',
            password='pass1234',
        )
        self.client.force_login(self.user)

    def _post_csv(self, content, package='', education_level='graduate'):
        upload = SimpleUploadedFile('students.csv', content.encode('utf-8'), content_type='text/csv')
        data = {'institute': str(self.institute.id), 'stu_file': upload}
        if education_level is not None:
            data['education_level'] = education_level
        if package:
            data['psychometric_package'] = package
        with patch('institute.task.update_student_data.delay'), \
                patch('institute.task.create_student_and_send_mail.delay'), \
                patch('institute.task.create_institute_log.delay'):
            return self.client.post(
                reverse('institute:institutehigheredcsvstudentcreate'),
                data,
            )

    def test_graduate_row_has_no_class_and_one_package(self):
        response = self._post_csv(
            'name,mobile,email\n'
            'Asha Rao,9876543210,asha.grad@higher.test\n',
            package='pkg_c12_personality',
            education_level='graduate',
        )
        self.assertEqual(response.status_code, 302)
        student = User.objects.get(email='asha.grad@higher.test')
        sm = StudentManagement.objects.get(student=student)
        self.assertIsNone(sm.class_and_section_id)
        self.assertEqual(sm.education_audience, choices.EducationAudience.GRADUATE)
        self.assertEqual(student.user_profile.schoolname, 'Higher Ed College')
        self.assertEqual(get_student_psychometric_track(student), POST_MATRIC_TRACK)
        self.assertTrue(has_assessment_access(student, 'class12_personality'))
        self.assertFalse(has_assessment_access(student, 'class12_interest'))

    def test_missing_education_level_is_rejected(self):
        self._post_csv(
            'name,mobile,email\n'
            'No Level,9876543212,nolevel@higher.test\n',
            package='pkg_c12_personality',
            education_level=None,
        )
        self.assertFalse(User.objects.filter(email='nolevel@higher.test').exists())

    def test_class10_package_is_rejected(self):
        self._post_csv(
            'name,mobile,email\n'
            'Class Ten,9876543213,classten@higher.test\n',
            package='pkg_c10_personality',
            education_level='graduate',
        )
        self.assertFalse(User.objects.filter(email='classten@higher.test').exists())

    def test_full_bundle_is_rejected(self):
        self._post_csv(
            'name,mobile,email\n'
            'Bundle,9876543214,bundle@higher.test\n',
            package='pkg_career_direction_full',
            education_level='professional',
        )
        self.assertFalse(User.objects.filter(email='bundle@higher.test').exists())

    def test_school_empty_class_track_stays_class10(self):
        school = User.objects.create_user(email='school.empty@higher.test', password='pass1234')
        StudentManagement.objects.create(
            institute=self.institute,
            student=school,
            class_and_section=None,
            education_audience=choices.EducationAudience.SCHOOL,
        )
        self.assertEqual(get_student_psychometric_track(school), CLASS10_TRACK)

    def test_graduate_dashboard_card_uses_assigned_test_not_stream_sorter(self):
        from django.urls import reverse

        from core.assessment_access import get_student_psychometric_dashboard_cta
        from psychometric_tests.package_assignment import assign_package_by_code

        student = User.objects.create_user(
            email='dash.grad@higher.test',
            password='pass1234',
        )
        StudentManagement.objects.create(
            institute=self.institute,
            student=student,
            class_and_section=None,
            education_audience=choices.EducationAudience.GRADUATE,
        )
        assign_package_by_code(student, 'pkg_c12_personality', self.institute)
        cta = get_student_psychometric_dashboard_cta(student)
        self.assertEqual(cta['test_name'], 'Class 12 Personality')
        self.assertEqual(cta['url'], reverse('post_matric:tests'))
        self.assertNotEqual(cta['url'], reverse('app:test_buttons'))

    def test_personality_only_hides_class10_upload(self):
        from psychometric_tests.models import InstitutePackagePrice, PsychometricPackage

        from institute.psychometric_packages import institute_csv_upload_kinds

        package = PsychometricPackage.objects.get(code='pkg_c12_personality')
        InstitutePackagePrice.objects.create(
            institute=self.institute,
            package=package,
            unit_price=package.list_price,
        )
        kinds = institute_csv_upload_kinds(self.institute)
        self.assertFalse(kinds['matric'])
        self.assertTrue(kinds['postmatric'])
        self.assertTrue(kinds['higher_ed'])

    def test_full_bundle_school_keeps_class_uploads_only(self):
        from institute.models import Institute
        from institute.psychometric_packages import institute_csv_upload_kinds

        school = Institute.objects.create(
            name='Full Bundle School',
            psychometric_access_mode=choices.PsychometricAccessMode.FULL_BUNDLE,
            credit_counts=5,
        )
        kinds = institute_csv_upload_kinds(school)
        self.assertEqual(
            kinds,
            {'matric': True, 'postmatric': True, 'higher_ed': False},
        )

    def test_college_professional_sample_csv_lists_class12_plus_levels(self):
        response = self.client.get(reverse('institute:higher_ed_student_sample_csv'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('name,mobile,email', body)
        self.assertNotIn('education_level', body)
        self.assertNotIn('package_code', body)
        self.assertIn('College professional student sample.csv', response['Content-Disposition'])
