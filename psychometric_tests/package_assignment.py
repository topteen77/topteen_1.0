"""Assign psychometric packages to students and grant entitlements."""

from __future__ import annotations

from typing import Optional, Tuple

from django.db import transaction
from django.utils import timezone

from core import choices
from core.psychometric_grade import get_student_psychometric_track, CLASS10_TRACK, POST_MATRIC_TRACK
from psychometric_tests.models import (
    PsychometricPackage,
    StudentAssessmentEntitlement,
    StudentPackageAssignment,
)


class PackageAssignmentError(Exception):
    pass


def _track_for_package(package: PsychometricPackage) -> str:
    if package.track == choices.PsychometricTrack.POST_MATRIC:
        return POST_MATRIC_TRACK
    return CLASS10_TRACK


def student_has_started_psychometric(user) -> bool:
    """
    True when the student has any psychometric attempt on their grade track.
    Assign / change package is only allowed before the first attempt.
    """
    if not user or not getattr(user, 'id', None):
        return False
    track = get_student_psychometric_track(user)
    if track == POST_MATRIC_TRACK:
        from app_post_matric.models import TestSession

        return TestSession.objects.filter(user=user).exists()

    from app.models import Results, TestCompletion

    if Results.objects.filter(user=user).exists():
        return True
    tc = TestCompletion.objects.filter(user=user).first()
    if not tc:
        return False
    return bool(
        tc.test1_complete
        or tc.test2_complete
        or tc.test3_complete
        or tc.numerical_complete
        or tc.verbal_complete
        or tc.logical_complete
        or tc.emotional_complete
        or tc.machanical_complete
        or tc.language_complete
        or tc.spatial_complete
    )


def institute_can_assign_package(institute, package: PsychometricPackage, student) -> Tuple[bool, str]:
    if not institute:
        return False, 'Institute not found.'
    if not package or not package.is_active:
        return False, 'Package is not available.'
    if not institute.uses_package_psychometric_mode():
        return False, 'Institute is not in package assignment mode.'
    if not institute.has_assignment_credits(package.credit_cost):
        return False, (
            f'Insufficient assignment credits. Need {package.credit_cost}, '
            f'have {institute.assignment_credits}.'
        )
    student_track = get_student_psychometric_track(student)
    package_track = _track_for_package(package)
    if student_track != package_track:
        return False, 'Package track does not match student grade track.'
    return True, ''


def _revoke_active_package_assignments(student, institute) -> int:
    """
    Revoke non-legacy package assignments for this student at the institute.
    Returns credits to refund into the institute pool.
    """
    rows = list(
        StudentPackageAssignment.objects.select_related('package').filter(
            student=student,
            institute=institute,
            package__is_legacy_bundle=False,
        )
    )
    refund = 0
    now = timezone.now()
    for row in rows:
        refund += int(row.credits_charged or getattr(row.package, 'credit_cost', 0) or 0)
        StudentAssessmentEntitlement.objects.filter(package_assignment=row).update(
            is_active=False,
            revoked_at=now,
        )
        # Soft-delete assignment when BaseModel supports it; hard-delete otherwise.
        delete = getattr(row, 'delete', None)
        if callable(delete):
            try:
                row.delete(hard_delete=True)
            except TypeError:
                row.delete()
    # Clear any leftover active package entitlements for this user.
    StudentAssessmentEntitlement.objects.filter(
        user=student,
        is_active=True,
        source=choices.EntitlementSource.PACKAGE_ASSIGNMENT,
    ).update(is_active=False, revoked_at=now)
    return refund


@transaction.atomic
def assign_package_to_student(
    student,
    package: PsychometricPackage,
    institute,
    assigned_by=None,
    *,
    allow_replace: bool = False,
) -> StudentPackageAssignment:
    institute = institute.__class__.objects.select_for_update().get(pk=institute.pk)

    if student_has_started_psychometric(student):
        raise PackageAssignmentError(
            'Cannot assign or change package after the student has started a psychometric test.'
        )

    if allow_replace:
        refund = _revoke_active_package_assignments(student, institute)
        if refund:
            institute.assignment_credits = int(institute.assignment_credits or 0) + int(refund)
            institute.save(update_fields=['assignment_credits', 'modified'])

    ok, message = institute_can_assign_package(institute, package, student)
    if not ok:
        raise PackageAssignmentError(message)

    institute.assignment_credits = int(institute.assignment_credits or 0) - int(package.credit_cost)
    institute.save(update_fields=['assignment_credits', 'modified'])

    assignment = StudentPackageAssignment.objects.create(
        student=student,
        package=package,
        institute=institute,
        assigned_by=assigned_by,
        credits_charged=package.credit_cost,
    )

    assessment_ids = list(
        package.package_assessments.select_related('assessment')
        .order_by('sort_order', 'id')
        .values_list('assessment_id', flat=True)
    )
    for assessment_id in assessment_ids:
        StudentAssessmentEntitlement.objects.update_or_create(
            user=student,
            assessment_id=assessment_id,
            defaults={
                'source': choices.EntitlementSource.PACKAGE_ASSIGNMENT,
                'package_assignment': assignment,
                'is_active': True,
                'revoked_at': None,
            },
        )

    return assignment


def assign_package_by_code(
    student,
    package_code: str,
    institute,
    assigned_by=None,
    *,
    allow_replace: bool = False,
) -> Optional[StudentPackageAssignment]:
    if not package_code:
        return None
    package = PsychometricPackage.objects.filter(code=package_code, is_active=True).first()
    if not package:
        raise PackageAssignmentError(f'Unknown package: {package_code}')
    return assign_package_to_student(
        student,
        package,
        institute,
        assigned_by=assigned_by,
        allow_replace=allow_replace,
    )


def add_assignment_credits(institute, quantity: int) -> int:
    quantity = int(quantity or 0)
    if quantity <= 0:
        return int(institute.assignment_credits or 0)
    institute.assignment_credits = int(institute.assignment_credits or 0) + quantity
    institute.save(update_fields=['assignment_credits', 'modified'])
    return institute.assignment_credits
