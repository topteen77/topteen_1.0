"""
Apply demo counselor course progress for a user (used by demo_data app).
States: passed (100% + certificate), failed (videos done, quizzes not passed),
not_completed (paid only, no progress).
"""
import json
import uuid

from django.db import transaction

from core import choices
from counselor.course_completion import is_course_fully_completed as _is_course_fully_completed
from counselor.models import (
    CounselorCertification,
    CounselorCourse,
    Part,
    QuizResults,
    VideoProgress,
)
from payments.models import Payment


class DemoCounselorCourseState:
    PASSED = "passed"
    FAILED = "failed"
    NOT_COMPLETED = "not_completed"
    CHOICES = (
        (PASSED, "Passed (course completed, certificate if eligible)"),
        (FAILED, "Failed (videos done; quizzes incomplete — workable)"),
        (NOT_COMPLETED, "Not completed (payment only; no progress)"),
    )


def _issue_certificate_if_eligible(user):
    """Mirror counselor.views._check_and_issue_certificate logic without request."""
    if not _is_course_fully_completed(user):
        return
    certification = CounselorCertification.objects.filter(user=user).first()
    if certification:
        return
    try:
        quiz_result = QuizResults.objects.get(user=user)
        if isinstance(quiz_result.scores, str):
            scores = json.loads(quiz_result.scores) if quiz_result.scores else []
        elif isinstance(quiz_result.scores, list):
            scores = quiz_result.scores
        else:
            scores = []
    except QuizResults.DoesNotExist:
        scores = []
    total_questions = 0
    total_correct = 0
    for score in scores:
        total_questions += score.get("total_questions_in_quiz", 0)
        total_correct += score.get("quiz_result", {}).get("correct_answers", 0)
    score_percentage = (total_correct / total_questions * 100) if total_questions > 0 else 0
    if score_percentage >= 80:
        grade = "A+"
    elif score_percentage >= 70:
        grade = "A"
    elif score_percentage >= 60:
        grade = "B+"
    elif score_percentage >= 50:
        grade = "B"
    elif score_percentage >= 40:
        grade = "C"
    else:
        grade = "D"
    latest_cert = CounselorCertification.objects.last()
    if latest_cert:
        certificate_code = f"TPTC{latest_cert.id + 1:04d}"
    else:
        certificate_code = "TPTC0001"
    CounselorCertification.objects.create(
        user=user,
        certificate_code=certificate_code,
        grade=grade,
    )


def create_counselor_course_payment(user, course):
    """Successful test payment so the account can access the course."""
    amount = course.get_charge_amount_rupees()
    gateway_receipt = f"demo_counselor_{uuid.uuid4().hex[:16]}"
    return Payment.objects.create(
        user=user,
        amount=amount,
        currency=int(course.currency),
        gateway_receipt=gateway_receipt,
        obj_type=choices.PaymentObjectType.COUNSELOR,
        obj_id=course.id,
        is_success=choices.YesNoChoices.YES,
        is_test_payment=True,
    )


def _clear_counselor_progress(user):
    VideoProgress.objects.filter(user=user).delete()
    QuizResults.objects.filter(user=user).delete()
    CounselorCertification.objects.filter(user=user).delete()


def apply_demo_counselor_course_state(user, state):
    """
    Apply progress for demo counselor user. Assumes payment already created if needed.
    Returns True if a CounselorCourse exists and state was applied.
    """
    course = CounselorCourse.objects.prefetch_related(
        "chapters__parts__quizzes__questions__answers"
    ).first()
    if not course:
        return False

    with transaction.atomic():
        _clear_counselor_progress(user)

        all_parts = Part.objects.filter(chapter__course=course).prefetch_related(
            "quizzes__questions__answers"
        )

        if state == DemoCounselorCourseState.NOT_COMPLETED:
            return True

        if state == DemoCounselorCourseState.FAILED:
            for part in all_parts:
                VideoProgress.objects.update_or_create(
                    user=user,
                    video_id=f"video-{part.id}",
                    defaults={
                        "progress": 100,
                        "completed": True,
                        "duration": None,
                    },
                )
            return True

        if state == DemoCounselorCourseState.PASSED:
            for part in all_parts:
                video_id = f"video-{part.id}"
                VideoProgress.objects.update_or_create(
                    user=user,
                    video_id=video_id,
                    defaults={
                        "progress": 100,
                        "completed": True,
                        "duration": None,
                    },
                )
            quiz_results, _ = QuizResults.objects.get_or_create(user=user)
            if isinstance(quiz_results.scores, str):
                quiz_results.scores = (
                    json.loads(quiz_results.scores) if quiz_results.scores else []
                )
            elif not isinstance(quiz_results.scores, list):
                quiz_results.scores = []
            for part in all_parts:
                part_id = part.id
                for quiz in part.quizzes.all():
                    total_questions = quiz.questions.count()
                    if total_questions == 0:
                        continue
                    correct_answers_map = {}
                    for question in quiz.questions.all():
                        correct_answer = question.answers.filter(is_correct=True).first()
                        if correct_answer:
                            correct_answers_map[f"ques_{question.id}"] = {
                                "correct_ans": correct_answer.answer_text,
                                "selected_ans": correct_answer.answer_text,
                            }
                    score_info = {
                        "part_id": part_id,
                        "quiz_id": quiz.id,
                        "total_questions_in_quiz": total_questions,
                        "correct_option": correct_answers_map,
                        "quiz_result": {
                            "correct_answers": total_questions,
                            "incorrect_answers": 0,
                        },
                    }
                    existing_score = None
                    for idx, score in enumerate(quiz_results.scores):
                        if (
                            score.get("part_id") == part_id
                            and score.get("quiz_id") == quiz.id
                        ):
                            existing_score = idx
                            break
                    if existing_score is not None:
                        quiz_results.scores[existing_score] = score_info
                    else:
                        quiz_results.scores.append(score_info)
            quiz_results.save()
            _issue_certificate_if_eligible(user)
            return True

    return False
