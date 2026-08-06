from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.llm_quota import (
    UNLIMITED_BALANCE_DISPLAY,
    credit_forum_relevant_question,
    ensure_can_use_llm,
    get_balance,
    is_unlimited_llm_user,
    resolve_role_key,
)
from core.models import LLMWalletLedger, UserLLMWallet


User = get_user_model()


class LLMQuotaStaffUnlimitedTests(TestCase):
    def test_staff_and_superuser_are_unlimited(self):
        staff = User.objects.create_user(
            email="staff-quota@example.com",
            name="Staff Quota",
            password="pass12345",
        )
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])

        admin = User.objects.create_superuser(
            email="admin-quota@example.com",
            name="Admin Quota",
            password="pass12345",
        )
        student = User.objects.create_user(
            email="student-quota@example.com",
            name="Student Quota",
            password="pass12345",
        )

        self.assertTrue(is_unlimited_llm_user(staff))
        self.assertTrue(is_unlimited_llm_user(admin))
        self.assertFalse(is_unlimited_llm_user(student))
        self.assertEqual(resolve_role_key(staff), "staff")
        self.assertEqual(resolve_role_key(admin), "staff")

        status = ensure_can_use_llm(staff, feature="forum", raise_exception=False)
        self.assertTrue(status.allowed)
        self.assertEqual(status.balance, UNLIMITED_BALANCE_DISPLAY)
        self.assertEqual(get_balance(staff), UNLIMITED_BALANCE_DISPLAY)


@override_settings(
    FORUM_RELEVANT_QUESTION_REWARD_TOKENS=3000,
    FORUM_RELEVANT_QUESTION_REWARD_DAILY_CAP=5,
)
class ForumRewardTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="forum-reward@example.com",
            name="Forum Reward",
            password="pass12345",
        )

    def test_relevant_question_credits_tokens(self):
        before = get_balance(self.student)
        credited = credit_forum_relevant_question(
            self.student,
            query_id=101,
            question_text="How do I know which career is right for me?",
        )
        self.assertEqual(credited, 3000)
        wallet = UserLLMWallet.objects.get(user=self.student)
        self.assertEqual(wallet.balance_tokens, before + 3000)
        entry = LLMWalletLedger.objects.get(reference="forum_q:101")
        self.assertEqual(entry.tokens, 3000)
        self.assertEqual(entry.source, LLMWalletLedger.SOURCE_ADJUSTMENT)

    def test_reward_is_idempotent_per_query(self):
        before = get_balance(self.student)
        credit_forum_relevant_question(
            self.student,
            query_id=202,
            question_text="What careers are good after 10th in science?",
        )
        again = credit_forum_relevant_question(
            self.student,
            query_id=202,
            question_text="What careers are good after 10th in science?",
        )
        self.assertEqual(again, 0)
        wallet = UserLLMWallet.objects.get(user=self.student)
        self.assertEqual(wallet.balance_tokens, before + 3000)

    def test_student_monthly_covers_five_forum_questions_per_week(self):
        from core.llm_quota import (
            STUDENT_AVG_FORUM_ANSWER_TOKENS,
            STUDENT_FORUM_QUESTIONS_PER_WEEK,
            STUDENT_MONTHLY_FREE_TOKENS,
            estimate_tokens_for_feature,
            get_role_default,
        )

        weekly_need = STUDENT_FORUM_QUESTIONS_PER_WEEK * STUDENT_AVG_FORUM_ANSWER_TOKENS
        monthly_need = int(weekly_need * 4.5)
        self.assertGreaterEqual(STUDENT_MONTHLY_FREE_TOKENS, monthly_need)
        role = get_role_default("student")
        self.assertGreaterEqual(int(role.monthly_free_tokens), monthly_need)
        # Pre-check reserve must not exceed one average answer budget.
        self.assertLessEqual(
            estimate_tokens_for_feature("forum", "student"),
            STUDENT_AVG_FORUM_ANSWER_TOKENS,
        )
        # Five weekly questions must fit in monthly free.
        self.assertGreaterEqual(
            int(role.monthly_free_tokens) // estimate_tokens_for_feature("forum", "student"),
            int(STUDENT_FORUM_QUESTIONS_PER_WEEK * 4.5),
        )

    def test_off_topic_question_gets_no_credit(self):
        credited = credit_forum_relevant_question(
            self.student,
            query_id=303,
            question_text="How do I beat the final boss in this video game?",
        )
        self.assertEqual(credited, 0)
        self.assertFalse(UserLLMWallet.objects.filter(user=self.student).exists())

    def test_staff_not_credited(self):
        staff = User.objects.create_user(
            email="staff-forum@example.com",
            name="Staff Forum",
            password="pass12345",
        )
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])
        credited = credit_forum_relevant_question(
            staff,
            query_id=404,
            question_text="How do I prepare for JEE?",
        )
        self.assertEqual(credited, 0)
