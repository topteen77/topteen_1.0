"""Tests for stream decision questionnaire storage and admin reset."""

import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from app.models import Results, TestCompletion
from app.stream_decision import (
    clear_questionnaire,
    is_questionnaire_completed,
    save_questionnaire,
    user_has_completed_questionnaire,
    validate_answers,
)
from core import choices
from users.admin import _reset_stream_decision_questionnaire, _reset_student_tests
from users.models import User


def _make_student(email='stream-student@example.com'):
    img = SimpleUploadedFile('u.jpg', b'fake-image-bytes', content_type='image/jpeg')
    user = User(
        email=email,
        name='Stream Student',
        user_type=choices.UserType.STUDENT,
        image=img,
    )
    user.set_password('pass1234')
    user.save()
    return user


def _mark_all_tests_complete(user):
    tc, _ = TestCompletion.objects.get_or_create(user=user)
    tc.test1_complete = True
    tc.test2_complete = True
    tc.test3_complete = True
    tc.numerical_complete = True
    tc.verbal_complete = True
    tc.logical_complete = True
    tc.emotional_complete = True
    tc.machanical_complete = True
    tc.language_complete = True
    tc.spatial_complete = True
    tc.save()
    return tc


def _sample_answers(**overrides):
    answers = {
        'preferred_stream': 'PCM',
        'preferred_stream_source': 'suggested',
        'preferred_stream_match_score': '40',
        'confidence_level': 'Very confident',
        'biggest_concern': 'Matching my interests',
        'discussed_with_adult': 'Yes, already discussed',
        'decision_readiness': 'Yes, I am ready',
    }
    answers.update(overrides)
    return answers


class StreamDecisionHelpersTest(TestCase):
    def setUp(self):
        self.user = _make_student()
        self.test3_result = Results.objects.create(
            user=self.user,
            test_paper='test3',
            scores={'Spatial': 80},
            results={},
        )

    def test_validate_answers_requires_all_fields(self):
        answers = _sample_answers()
        answers.pop('confidence_level')
        self.assertEqual(
            validate_answers(answers),
            'Please answer all questions before submitting.',
        )

    def test_validate_answers_rejects_not_sure(self):
        self.assertEqual(
            validate_answers(_sample_answers(
                preferred_stream='Not sure yet',
                preferred_stream_source='not_sure',
            )),
            'Please select a stream.',
        )

    def test_save_and_clear_questionnaire(self):
        save_questionnaire(self.test3_result, _sample_answers())
        self.test3_result.refresh_from_db()
        self.assertTrue(is_questionnaire_completed(self.test3_result.results))
        self.assertEqual(
            self.test3_result.results['stream_decision_questionnaire']['answers']['preferred_stream'],
            'PCM',
        )
        self.assertTrue(user_has_completed_questionnaire(self.user))

        self.assertTrue(clear_questionnaire(self.user))
        self.test3_result.refresh_from_db()
        self.assertFalse(is_questionnaire_completed(self.test3_result.results))
        self.assertFalse(user_has_completed_questionnaire(self.user))


class StreamDecisionSubmitViewTest(TestCase):
    def setUp(self):
        self.user = _make_student('stream-submit@example.com')
        _mark_all_tests_complete(self.user)
        self.test3_result = Results.objects.create(
            user=self.user,
            test_paper='test3',
            scores={'Spatial': 80},
            results={},
        )
        self.client = Client()
        self.client.force_login(self.user, backend='users.backends.CustomUserBackend')
        self.url = reverse('app:stream_decision_questionnaire_submit')

    def test_submit_saves_questionnaire(self):
        response = self.client.post(
            self.url,
            data=json.dumps({'answers': _sample_answers()}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.test3_result.refresh_from_db()
        self.assertTrue(is_questionnaire_completed(self.test3_result.results))

    def test_submit_rejects_missing_answers(self):
        answers = _sample_answers()
        answers.pop('confidence_level')
        response = self.client.post(
            self.url,
            data=json.dumps({'answers': answers}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn('Please answer all questions', payload['message'])

    def test_submit_rejects_not_sure(self):
        response = self.client.post(
            self.url,
            data=json.dumps({'answers': _sample_answers(
                preferred_stream='Not sure yet',
                preferred_stream_source='not_sure',
            )}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['message'], 'Please select a stream.')

    def test_submit_rejects_duplicate_submission(self):
        save_questionnaire(self.test3_result, _sample_answers())
        response = self.client.post(
            self.url,
            data=json.dumps({'answers': _sample_answers(preferred_stream='Fine Arts')}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('already submitted', response.json()['message'])


class StreamDecisionAdminResetTest(TestCase):
    def setUp(self):
        self.user = _make_student('stream-reset@example.com')
        self.test3_result = Results.objects.create(
            user=self.user,
            test_paper='test3',
            scores={'Spatial': 80},
            results={},
        )
        save_questionnaire(self.test3_result, _sample_answers())

    def test_admin_reset_clears_questionnaire_only(self):
        self.assertTrue(_reset_stream_decision_questionnaire(self.user))
        self.test3_result.refresh_from_db()
        self.assertFalse(is_questionnaire_completed(self.test3_result.results))
        self.assertEqual(self.test3_result.test_paper, 'test3')

    def test_partial_reset_handles_stream_decision_test_id(self):
        _reset_student_tests(self.user, test_ids=['stream_decision_questionnaire'])
        self.test3_result.refresh_from_db()
        self.assertFalse(is_questionnaire_completed(self.test3_result.results))


class StreamDecisionHardDeleteTest(TestCase):
    def test_results_delete_removes_questionnaire(self):
        user = _make_student('stream-delete@example.com')
        test3_result = Results.objects.create(
            user=user,
            test_paper='test3',
            scores={'Spatial': 80},
            results={},
        )
        save_questionnaire(test3_result, _sample_answers())
        self.assertTrue(user_has_completed_questionnaire(user))

        Results.objects.filter(user=user).delete()
        self.assertFalse(Results.objects.filter(user=user).exists())
        self.assertFalse(user_has_completed_questionnaire(user))
