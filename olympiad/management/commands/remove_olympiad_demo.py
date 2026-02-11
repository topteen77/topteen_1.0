"""
Remove Olympiad demo data created by load_olympiad_demo: demo exam, its questions/sets,
registrations, sessions, responses; optionally remove the demo user.

Usage:
  python manage.py remove_olympiad_demo
  python manage.py remove_olympiad_demo --keep-user   # keep demo user, remove only exam data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from olympiad.models import (
    OlympiadExam,
    OlympiadQuestion,
    OlympiadExamQuestionSet,
    OlympiadRegistration,
    OlympiadSession,
    OlympiadResponse,
)

from olympiad.management.commands.load_olympiad_demo import DEMO_USER_EMAIL, DEMO_EXAM_NAME


def hard_delete_queryset(qs):
    """Call delete(hard_delete=True) on each object (BaseModel soft-delete)."""
    for obj in qs:
        obj.delete(hard_delete=True)


class Command(BaseCommand):
    help = "Remove Olympiad demo data (and optionally the demo user)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-user",
            action="store_true",
            help="Keep the demo user; remove only exam, questions, registrations, sessions, responses.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        keep_user = options["keep_user"]

        with transaction.atomic():
            # Find demo exam by name (use complete() to include soft-deleted)
            exam = OlympiadExam.objects.complete().filter(name=DEMO_EXAM_NAME).first()

            if not exam:
                self.stdout.write("No demo exam found. Nothing to remove.")
                if not keep_user:
                    self._remove_demo_user(User)
                return

            # Question IDs linked only to this exam (we will delete these questions after sets)
            set_question_ids = list(
                OlympiadExamQuestionSet.objects.filter(exam=exam).values_list("question_id", flat=True)
            )

            # Order of deletion (respect FK: responses -> sessions; registrations; sets -> questions; exam)
            # Use complete() to include soft-deleted records so we remove everything
            responses = OlympiadResponse.objects.complete().filter(session__exam=exam)
            count_r = responses.count()
            hard_delete_queryset(responses)
            self.stdout.write(f"Removed {count_r} response(s).")

            sessions = OlympiadSession.objects.complete().filter(exam=exam)
            count_s = sessions.count()
            hard_delete_queryset(sessions)
            self.stdout.write(f"Removed {count_s} session(s).")

            regs = OlympiadRegistration.objects.complete().filter(exam=exam)
            count_reg = regs.count()
            hard_delete_queryset(regs)
            self.stdout.write(f"Removed {count_reg} registration(s).")

            sets = OlympiadExamQuestionSet.objects.complete().filter(exam=exam)
            count_set = sets.count()
            hard_delete_queryset(sets)
            self.stdout.write(f"Removed {count_set} exam-question set(s).")

            # Delete questions that were only used by this demo exam
            for qid in set_question_ids:
                q = OlympiadQuestion.objects.complete().filter(id=qid).first()
                if q:
                    # Only delete if not linked to any other exam
                    other = OlympiadExamQuestionSet.objects.complete().filter(question_id=qid).exists()
                    if not other:
                        q.delete(hard_delete=True)
            self.stdout.write(f"Removed demo question(s).")

            exam.delete(hard_delete=True)
            self.stdout.write(self.style.SUCCESS(f"Removed demo exam: {DEMO_EXAM_NAME}."))

            if not keep_user:
                self._remove_demo_user(User)
            else:
                self.stdout.write("Demo user kept (--keep-user).")

    def _remove_demo_user(self, User):
        demo_user = User.objects.complete().filter(email=DEMO_USER_EMAIL).first()
        if not demo_user:
            self.stdout.write("No demo user found.")
            return
        # Delete any remaining olympiad data for this user (in case exam was already removed)
        for resp in OlympiadResponse.objects.complete().filter(session__user=demo_user):
            resp.delete(hard_delete=True)
        for sess in OlympiadSession.objects.complete().filter(user=demo_user):
            sess.delete(hard_delete=True)
        for reg in OlympiadRegistration.objects.complete().filter(user=demo_user):
            reg.delete(hard_delete=True)
        demo_user.delete(hard_delete=True)
        self.stdout.write(self.style.SUCCESS(f"Removed demo user: {DEMO_USER_EMAIL}."))
