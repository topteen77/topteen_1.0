"""Tests for student/parent AI feature quotas."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from core import choices
from core.ai_feature_quota import (
    FEATURE_COUNSELLOR,
    FEATURE_PAGE_CHAT,
    FEATURE_RESUME_AI,
    FEATURE_RESUME_CREATE,
    AIFeatureQuotaExceeded,
    consume_feature,
    ensure_can_use_feature,
    feature_status,
    grant_purchase_bonuses,
    quota_applies,
)
from core.models import AIFeatureQuotaSettings


User = get_user_model()


class AIFeatureQuotaTests(TestCase):
    def setUp(self):
        self.settings_row = AIFeatureQuotaSettings.load()
        self.settings_row.resume_free_creates = 1
        self.settings_row.resume_free_ai_edits = 2
        self.settings_row.counsellor_message_limit = None
        self.settings_row.page_chat_message_limit = None
        self.settings_row.purchase_bonus_resume_creates = 1
        self.settings_row.purchase_bonus_resume_ai = 10
        self.settings_row.purchase_bonus_counsellor = 100
        self.settings_row.purchase_bonus_page_chat = 100
        self.settings_row.save()

        self.student = User.objects.create_user(
            email="student_quota@example.com",
            name="Student Quota",
            password="pass12345",
        )
        self.student.user_type = choices.UserType.STUDENT
        self.student.save(update_fields=["user_type"])

        self.parent = User.objects.create_user(
            email="parent_quota@example.com",
            name="Parent Quota",
            password="pass12345",
        )
        self.parent.user_type = choices.UserType.PARENT
        self.parent.save(update_fields=["user_type"])

        self.counselor = User.objects.create_user(
            email="counselor_quota@example.com",
            name="Counselor Quota",
            password="pass12345",
        )
        self.counselor.user_type = choices.UserType.COUNSELOR
        self.counselor.save(update_fields=["user_type"])

    def test_quota_applies_only_student_parent(self):
        self.assertTrue(quota_applies(self.student))
        self.assertTrue(quota_applies(self.parent))
        self.assertFalse(quota_applies(self.counselor))

    def test_counselor_never_locked(self):
        for feature in (
            FEATURE_RESUME_CREATE,
            FEATURE_RESUME_AI,
            FEATURE_COUNSELLOR,
            FEATURE_PAGE_CHAT,
        ):
            st = feature_status(self.counselor, feature)
            self.assertFalse(st["locked"])
            self.assertTrue(st["unlimited"])
            ensure_can_use_feature(self.counselor, feature)
            consume_feature(self.counselor, feature)

    def test_resume_free_ai_edits(self):
        ensure_can_use_feature(self.student, FEATURE_RESUME_AI)
        consume_feature(self.student, FEATURE_RESUME_AI)
        ensure_can_use_feature(self.student, FEATURE_RESUME_AI)
        consume_feature(self.student, FEATURE_RESUME_AI)
        st = feature_status(self.student, FEATURE_RESUME_AI)
        self.assertTrue(st["locked"])
        self.assertEqual(st["remaining"], 0)
        with self.assertRaises(AIFeatureQuotaExceeded):
            ensure_can_use_feature(self.student, FEATURE_RESUME_AI)

    def test_counsellor_unlimited_by_default(self):
        st = feature_status(self.student, FEATURE_COUNSELLOR)
        self.assertTrue(st["unlimited"])
        self.assertFalse(st["locked"])
        for _ in range(5):
            consume_feature(self.student, FEATURE_COUNSELLOR)

    def test_counsellor_limit_when_admin_sets(self):
        self.settings_row.counsellor_message_limit = 2
        self.settings_row.save()
        consume_feature(self.student, FEATURE_COUNSELLOR)
        consume_feature(self.student, FEATURE_COUNSELLOR)
        with self.assertRaises(AIFeatureQuotaExceeded):
            consume_feature(self.student, FEATURE_COUNSELLOR)

    def test_page_chat_limit_when_admin_sets(self):
        self.settings_row.page_chat_message_limit = 1
        self.settings_row.save()
        consume_feature(self.parent, FEATURE_PAGE_CHAT)
        with self.assertRaises(AIFeatureQuotaExceeded):
            consume_feature(self.parent, FEATURE_PAGE_CHAT)

    def test_purchase_bonus_unlocks_resume_ai(self):
        consume_feature(self.student, FEATURE_RESUME_AI)
        consume_feature(self.student, FEATURE_RESUME_AI)
        with self.assertRaises(AIFeatureQuotaExceeded):
            ensure_can_use_feature(self.student, FEATURE_RESUME_AI)
        grant_purchase_bonuses(self.student, reference="test")
        st = feature_status(self.student, FEATURE_RESUME_AI)
        self.assertFalse(st["locked"])
        self.assertEqual(st["remaining"], 10)
