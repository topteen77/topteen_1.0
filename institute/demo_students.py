"""
Marketing-controlled Class 10 / Class 12 demo students for institutes.

Limits (per institute):
- Max 5 demo students per class (10 and 12).
- Max 3 seed runs (demo_seed_count).

Demo students use User.is_demo_account=True and do not consume paid exam credits
or assignment_credits.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.utils.text import slugify

from core import choices
from core.psychometric_grade import CLASS10_TRACK, POST_MATRIC_TRACK, get_student_psychometric_track
from institute.models import ClassAndSection, Institute, StudentManagement
from users.models import User, UserProfile

MAX_DEMO_PER_CLASS = 5
MAX_DEMO_SEED_RUNS = 3
DEMO_EMAIL_DOMAIN = "demostudent.topteen.local"


class DemoStudentError(Exception):
    """User-facing validation / seed failure."""


def _get_or_create_class_section(label: str) -> ClassAndSection:
    obj = ClassAndSection.objects.filter(class_and_section__iexact=label).first()
    if obj:
        return obj
    return ClassAndSection.objects.create(class_and_section=label, stream="General")


def demo_count_for_class(institute: Institute, class_label: str) -> int:
    return (
        StudentManagement.objects.filter(
            institute=institute,
            student__is_demo_account=True,
            class_and_section__class_and_section__iexact=class_label,
        ).count()
    )


def remaining_demo_slots(institute: Institute) -> Dict[str, int]:
    return {
        "class10": max(0, MAX_DEMO_PER_CLASS - demo_count_for_class(institute, "Class 10")),
        "class12": max(0, MAX_DEMO_PER_CLASS - demo_count_for_class(institute, "Class 12")),
        "seed_runs_left": max(0, MAX_DEMO_SEED_RUNS - int(institute.demo_seed_count or 0)),
    }


def parse_demo_seed_counts(post) -> Tuple[int, int]:
    """Always read Class 10 / Class 12 demo counts from POST (0–MAX_DEMO_PER_CLASS)."""

    def _n(key: str) -> int:
        raw = (post.get(key) or "0").strip()
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            return 0

    return (
        min(MAX_DEMO_PER_CLASS, _n("demo_class10_count")),
        min(MAX_DEMO_PER_CLASS, _n("demo_class12_count")),
    )


def parse_demo_counts_from_post(post) -> Tuple[int, int, bool]:
    """
    Returns (class10_count, class12_count, create_as_demo_flag).

    Demo mode when ``institute_account_type=demo`` (preferred), or legacy
    ``create_as_demo`` / ``is_demo_institute`` flags.

    Counts are only returned when demo mode is on (create/edit account type).
    For dedicated seed endpoints, use ``parse_demo_seed_counts`` instead.
    """
    account_type = (post.get("institute_account_type") or "").strip().lower()
    if account_type in ("demo", "paid", "actual"):
        create_as_demo = account_type == "demo"
    else:
        flag = (post.get("create_as_demo") or post.get("is_demo_institute") or "").strip().lower()
        create_as_demo = flag in ("1", "true", "on", "yes")

    if create_as_demo:
        n10, n12 = parse_demo_seed_counts(post)
    else:
        n10, n12 = 0, 0
    return n10, n12, create_as_demo


def _unique_demo_email(institute: Institute, grade: str, index: int) -> str:
    base = slugify(institute.slug or institute.name or f"ins{institute.pk}")[:40] or f"ins{institute.pk}"
    for attempt in range(50):
        suffix = index if attempt == 0 else f"{index}{attempt}"
        email = f"demo.{base}.c{grade}.{suffix}@{DEMO_EMAIL_DOMAIN}"
        if not User.objects.filter(email__iexact=email).exists():
            return email
    return f"demo.{base}.c{grade}.{index}.{random.randint(1000, 9999)}@{DEMO_EMAIL_DOMAIN}"


def _unique_demo_mobile(seed: int) -> str:
    for i in range(200):
        mobile = str(9800000000 + (seed + i) % 100000000)
        if not User.objects.filter(mobile=mobile).exists():
            return mobile
    return str(9800000000 + random.randint(0, 99999999))


def _default_package_for_track(institute: Institute, track: str):
    from psychometric_tests.models import PsychometricPackage

    preferred = (
        "pkg_stream_sorter_full"
        if track == CLASS10_TRACK
        else "pkg_career_direction_full"
    )
    pkg_track = (
        choices.PsychometricTrack.CLASS10
        if track == CLASS10_TRACK
        else choices.PsychometricTrack.POST_MATRIC
    )
    enabled = institute.get_enabled_psychometric_package_codes()
    qs = PsychometricPackage.objects.filter(is_active=True, track=pkg_track)
    if enabled:
        qs = qs.filter(code__in=enabled)
    pkg = qs.filter(code=preferred).first()
    if pkg:
        return pkg
    return qs.order_by("-is_legacy_bundle", "-credit_cost", "id").first()


def grant_demo_psychometric_access(student, institute, assigned_by=None) -> None:
    """
    Activate psychometric access for a demo student without burning assignment_credits.
    full_bundle institutes rely on legacy access; package mode gets a zero-charge assignment.
    """
    if not institute.uses_package_psychometric_mode():
        # Legacy / full_bundle: institute students already have access via
        # has_legacy_full_bundle_access. Optionally mark a successful payment
        # so older code paths that check PsychometricTestPayment still pass.
        try:
            from psychometric_tests.models import PsychometricTestPayment
            from core.models import Configuration

            track = get_student_psychometric_track(student)
            test_type = (
                choices.PsychometricTestType.ADVANCED
                if track == POST_MATRIC_TRACK
                else choices.PsychometricTestType.BASIC
            )
            amount = Configuration.get("EAZYPAY_PSYCHOMETRIC_TEST_AMOUNT", 10, editable=True)
            receipt = f"demo_psych_{institute.pk}_{student.pk}"
            pay, _ = PsychometricTestPayment.objects.get_or_create(
                user=student,
                gateway_receipt=receipt,
                defaults={
                    "test_type": test_type,
                    "is_success": choices.YesNoChoices.YES,
                    "amount": amount,
                    "currency": choices.Currency.IND,
                },
            )
            if pay.is_success != choices.YesNoChoices.YES:
                pay.is_success = choices.YesNoChoices.YES
                pay.save(update_fields=["is_success", "modified"])
        except Exception:
            pass
        return

    from psychometric_tests.models import (
        StudentAssessmentEntitlement,
        StudentPackageAssignment,
    )

    track = get_student_psychometric_track(student)
    package = _default_package_for_track(institute, track)
    if not package:
        return

    assignment = StudentPackageAssignment.objects.create(
        student=student,
        package=package,
        institute=institute,
        assigned_by=assigned_by,
        credits_charged=0,
    )
    assessment_ids = list(
        package.package_assessments.select_related("assessment")
        .order_by("sort_order", "id")
        .values_list("assessment_id", flat=True)
    )
    for assessment_id in assessment_ids:
        StudentAssessmentEntitlement.objects.update_or_create(
            user=student,
            assessment_id=assessment_id,
            defaults={
                "source": choices.EntitlementSource.ADMIN_GRANT,
                "package_assignment": assignment,
                "is_active": True,
                "revoked_at": None,
            },
        )


@transaction.atomic
def seed_institute_demo_students(
    institute: Institute,
    marketing_user,
    class10_count: int = 0,
    class12_count: int = 0,
) -> Dict[str, Any]:
    """
    Create demo Class 10 / Class 12 students. Raises DemoStudentError on validation failure.
    """
    institute = Institute.objects.select_for_update().get(pk=institute.pk)
    if getattr(institute, "is_system_demo", False):
        raise DemoStudentError("System demo institutes cannot receive marketing demo seeds.")

    seed_count = int(institute.demo_seed_count or 0)
    if seed_count >= MAX_DEMO_SEED_RUNS:
        raise DemoStudentError(
            f"This institute already used all {MAX_DEMO_SEED_RUNS} demo seed runs."
        )

    try:
        n10 = max(0, int(class10_count or 0))
        n12 = max(0, int(class12_count or 0))
    except (TypeError, ValueError):
        raise DemoStudentError("Invalid demo student counts.")

    n10 = min(n10, MAX_DEMO_PER_CLASS)
    n12 = min(n12, MAX_DEMO_PER_CLASS)
    if n10 <= 0 and n12 <= 0:
        raise DemoStudentError("Select at least one Class 10 or Class 12 demo student.")

    slots = remaining_demo_slots(institute)
    n10 = min(n10, slots["class10"])
    n12 = min(n12, slots["class12"])
    if n10 <= 0 and n12 <= 0:
        raise DemoStudentError(
            f"Demo roster is full (max {MAX_DEMO_PER_CLASS} per class for this institute)."
        )

    c10 = _get_or_create_class_section("Class 10")
    c12 = _get_or_create_class_section("Class 12")
    created: List[User] = []
    base_seed = institute.pk * 100 + seed_count * 10

    plans = [("10", c10, n10), ("12", c12, n12)]
    for grade, section, count in plans:
        for i in range(1, count + 1):
            email = _unique_demo_email(institute, grade, i + seed_count * MAX_DEMO_PER_CLASS)
            mobile = _unique_demo_mobile(base_seed + int(grade) * 20 + i)
            password = institute.get_demo_student_password()
            user = User(
                email=email,
                name=f"Demo Student {grade}-{i}",
                user_type=choices.UserType.STUDENT,
                mobile=mobile,
                is_demo_account=True,
                is_system_demo=False,
            )
            user.set_password(password)
            user.save()
            UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "grade": grade,
                    "schoolname": (institute.name or "Demo School")[:100],
                },
            )
            sm = StudentManagement(
                institute=institute,
                student=user,
                class_and_section=section,
            )
            sm._skip_demo_mktg_student_added_notify = True
            sm.save()
            grant_demo_psychometric_access(user, institute, assigned_by=marketing_user)
            created.append(user)

    institute.demo_seed_count = seed_count + 1
    institute.is_demo_institute = True
    institute.save(update_fields=["demo_seed_count", "is_demo_institute", "modified"])

    if created:
        try:
            from institute.demo_institute_notifications import notify_demo_institute_students_added

            notify_demo_institute_students_added(
                institute,
                count=len(created),
                source="demo_seed",
            )
        except Exception:
            pass

    return {
        "created_count": len(created),
        "class10": n10,
        "class12": n12,
        "demo_seed_count": institute.demo_seed_count,
        "user_ids": [u.pk for u in created],
    }


def _hard_delete_student_users(user_ids: List[int]) -> int:
    """Hard-delete student users and related test/psych data. Skips is_system_demo."""
    if not user_ids:
        return 0
    user_ids = list(
        User.objects.filter(pk__in=user_ids, is_system_demo=False).values_list("pk", flat=True)
    )
    if not user_ids:
        return 0

    try:
        from demo_data.demo_dataset import _delete_psychometric_packages_and_payments_for_users
        from app.models import Results, TestCompletion

        _delete_psychometric_packages_and_payments_for_users(user_ids)
        Results.objects.filter(user_id__in=user_ids).delete()
        TestCompletion.objects.filter(user_id__in=user_ids).delete()
    except Exception:
        pass

    try:
        from app_post_matric.models import TestSession, UserResponse, TestResult, TestTopCategories

        TestSession.objects.filter(user_id__in=user_ids).delete()
        UserResponse.objects.filter(user_id__in=user_ids).delete()
        TestResult.objects.filter(user_id__in=user_ids).delete()
        TestTopCategories.objects.filter(user_id__in=user_ids).delete()
    except Exception:
        pass

    UserProfile.objects.filter(user_id__in=user_ids).delete()
    for sm in StudentManagement.objects.complete().filter(student_id__in=user_ids):
        try:
            sm.delete(hard_delete=True)
        except Exception:
            sm.delete()

    deleted = 0
    for user in User.objects.filter(pk__in=user_ids, is_system_demo=False):
        try:
            user.delete(hard_delete=True)
            deleted += 1
        except Exception:
            try:
                user.delete()
                deleted += 1
            except Exception:
                pass
    return deleted


def _hard_delete_demo_users(user_ids: List[int]) -> None:
    """Backward-compatible wrapper: only marketing demo accounts."""
    demo_ids = list(
        User.objects.filter(
            pk__in=user_ids, is_demo_account=True, is_system_demo=False
        ).values_list("pk", flat=True)
    )
    _hard_delete_student_users(demo_ids)


@transaction.atomic
def purge_institute_demo_students(institute: Institute) -> int:
    """Remove all marketing demo students for an institute. Never touches is_system_demo users."""
    sms = StudentManagement.objects.complete().filter(
        institute=institute,
        student__is_demo_account=True,
        student__is_system_demo=False,
    ).select_related("student")
    user_ids = [sm.student_id for sm in sms if sm.student_id]
    count = len(user_ids)
    _hard_delete_student_users(user_ids)
    return count


@transaction.atomic
def hard_delete_demo_institute(institute: Institute) -> Dict[str, Any]:
    """
    Permanently delete a demo institute, all enrolled students (non system-demo),
    counselors tied only to this institute, and the institute login user.
    """
    institute = Institute.objects.select_for_update().get(pk=institute.pk)
    if getattr(institute, "is_system_demo", False):
        raise DemoStudentError("System demo institutes cannot be deleted.")
    if not getattr(institute, "is_demo_institute", False):
        raise DemoStudentError("Only demo institutes can be deleted with students.")

    name = institute.name
    institute_id = institute.pk

    student_ids = list(
        StudentManagement.objects.complete()
        .filter(institute_id=institute_id)
        .values_list("student_id", flat=True)
    )
    removed_students = _hard_delete_student_users(student_ids)

    # Remove any leftover StudentManagement rows for this institute.
    for sm in StudentManagement.objects.complete().filter(institute_id=institute_id):
        try:
            sm.delete(hard_delete=True)
        except Exception:
            sm.delete()

    # Counselors primarily owned by this institute.
    try:
        from counselor.models import Counselor

        for c in Counselor.objects.complete().filter(counselor_admin_id=institute_id):
            coun_user = getattr(c, "coun_user", None)
            try:
                c.institute_placements.clear()
            except Exception:
                pass
            try:
                c.students.clear()
            except Exception:
                pass
            try:
                c.delete(hard_delete=True)
            except Exception:
                c.delete()
            if coun_user and not getattr(coun_user, "is_system_demo", False):
                still = Counselor.objects.complete().filter(coun_user_id=coun_user.pk).exists()
                if not still:
                    try:
                        coun_user.delete(hard_delete=True)
                    except Exception:
                        try:
                            coun_user.delete()
                        except Exception:
                            pass
    except Exception:
        pass

    # Tie-up orders + package price rows (best-effort).
    try:
        from institute.models import InstituteTieUpOrder

        for order in InstituteTieUpOrder.objects.complete().filter(institute_id=institute_id):
            try:
                order.delete(hard_delete=True)
            except Exception:
                order.delete()
    except Exception:
        pass
    try:
        from psychometric_tests.models import InstitutePackagePrice

        for row in InstitutePackagePrice.objects.complete().filter(institute_id=institute_id):
            try:
                row.delete(hard_delete=True)
            except Exception:
                row.delete()
    except Exception:
        pass

    inst_user = getattr(institute, "created_by", None)
    try:
        institute.delete(hard_delete=True)
    except Exception:
        institute.delete()

    if inst_user and not getattr(inst_user, "is_system_demo", False):
        # Only delete institute login if no other institute still points at them.
        still_used = Institute.objects.complete().filter(created_by_id=inst_user.pk).exists()
        if not still_used:
            try:
                inst_user.delete(hard_delete=True)
            except Exception:
                try:
                    inst_user.delete()
                except Exception:
                    pass

    return {
        "institute_id": institute_id,
        "institute_name": name,
        "removed_students": removed_students,
    }


@transaction.atomic
def convert_demo_institute_to_paid(
    institute: Institute,
    marketing_user,
    *,
    credit_counts: Optional[int] = None,
    assignment_credits: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Purge demo students, clear is_demo_institute, optionally set paid credit pools.
    Keeps demo_seed_count for audit history.
    """
    institute = Institute.objects.select_for_update().get(pk=institute.pk)
    if getattr(institute, "is_system_demo", False):
        raise DemoStudentError("System demo institutes cannot be converted.")

    removed = purge_institute_demo_students(institute)

    update_fields = ["is_demo_institute", "modified"]
    institute.is_demo_institute = False

    if credit_counts is not None:
        if int(credit_counts) < 0:
            raise DemoStudentError("Exam credits cannot be negative.")
        institute.credit_counts = int(credit_counts)
        update_fields.append("credit_counts")

    if assignment_credits is not None:
        if int(assignment_credits) < 0:
            raise DemoStudentError("Assignment credits cannot be negative.")
        institute.assignment_credits = int(assignment_credits)
        update_fields.append("assignment_credits")

    institute.save(update_fields=update_fields)
    return {
        "removed_demo_students": removed,
        "credit_counts": institute.credit_counts,
        "assignment_credits": institute.assignment_credits,
        "converted_by": getattr(marketing_user, "pk", None),
    }


def marketing_can_manage_institute(user, institute: Institute) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    ut = getattr(user, "user_type", None)
    if ut == choices.UserType.MARKETINGGROUPADMIN:
        return Institute.objects.filter(
            pk=institute.pk,
            marketing_group__marketing_group_admin=user,
        ).exists()
    if ut == choices.UserType.INSTITUTEGROUPADMIN:
        return Institute.objects.filter(
            pk=institute.pk,
            institute_group__institute_group_admin=user,
        ).exists()
    return False
