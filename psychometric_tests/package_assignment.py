"""Assign psychometric packages to students and grant entitlements."""

from __future__ import annotations

from typing import Optional, Tuple

from django.db import transaction

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


@transaction.atomic
def assign_package_to_student(
    student,
    package: PsychometricPackage,
    institute,
    assigned_by=None,
) -> StudentPackageAssignment:
    institute = institute.__class__.objects.select_for_update().get(pk=institute.pk)
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
) -> Optional[StudentPackageAssignment]:
    if not package_code:
        return None
    package = PsychometricPackage.objects.filter(code=package_code, is_active=True).first()
    if not package:
        raise PackageAssignmentError(f'Unknown package: {package_code}')
    return assign_package_to_student(student, package, institute, assigned_by=assigned_by)


def add_assignment_credits(institute, quantity: int) -> int:
    quantity = int(quantity or 0)
    if quantity <= 0:
        return int(institute.assignment_credits or 0)
    institute.assignment_credits = int(institute.assignment_credits or 0) + quantity
    institute.save(update_fields=['assignment_credits', 'modified'])
    return institute.assignment_credits
