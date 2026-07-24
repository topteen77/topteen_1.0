"""Helpers for institute psychometric package assignment during enrollment."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

from django.contrib import messages

from core import choices
from core.assessment_access import (
    get_active_packages_for_institute,
    get_institute_roster_report_url,
    get_roster_assessment_report_url,
    get_student_custom_package_names,
    get_student_entitled_assessment_codes,
    has_legacy_full_bundle_access,
    packages_enabled,
    roster_combined_report_url,
)
from core.psychometric_grade import get_student_psychometric_track
from psychometric_tests.models import InstitutePackagePrice, PsychometricPackage, StudentPackageAssignment
from psychometric_tests.package_assignment import PackageAssignmentError, assign_package_by_code

logger = logging.getLogger(__name__)

CLASS10_ROSTER_ASSESSMENTS = [
    {
        'code': 'class10_personality',
        'label': 'Personality Assessment',
        'engine_key': 'test1',
        'detail_keys': ('personality_assessment', 'test1'),
    },
    {
        'code': 'class10_interest',
        'label': 'Career Interest assessment',
        'engine_key': 'test2',
        'detail_keys': ('career_interest_assessment', 'test2'),
    },
    {
        'code': 'class10_aptitude',
        'label': 'Comprehensive Aptitude assessment',
        'engine_key': 'test3',
        'detail_keys': ('comprehensive_aptitude_assessment', 'test3'),
    },
]

POST_MATRIC_ROSTER_ASSESSMENTS = [
    {
        'code': 'class12_personality',
        'label': 'Personality Assessment',
        'engine_key': '1',
        'detail_keys': ('personality_assessment', 'career_assessment', 'test1'),
    },
    {
        'code': 'class12_motivation',
        'label': 'Motivation Assessment',
        'engine_key': '2',
        'detail_keys': ('motivation_assessment', 'test2'),
    },
    {
        'code': 'class12_interest',
        'label': 'Career Interest Inventory',
        'engine_key': '3',
        'detail_keys': ('career_interest_inventory', 'test3'),
    },
    {
        'code': 'class12_aptitude',
        'label': 'Aptitude Assessment',
        'engine_key': '4',
        'detail_keys': ('aptitude_assessment', 'test4'),
    },
]

_ATTEMPTED_VALUES = frozenset(
    {'1', 'true', 'yes', 'y', 'completed', 'complete', 'done', 'attempted'}
)


def institute_package_mode_active(institute) -> bool:
    if not institute:
        return False
    if not packages_enabled():
        return False
    return institute.psychometric_access_mode == choices.PsychometricAccessMode.PACKAGE


def get_marketing_psychometric_catalog():
    """Active packages marketing can assign to an institute."""
    if not packages_enabled():
        return []
    return list(
        PsychometricPackage.objects.filter(is_active=True, is_legacy_bundle=False)
        .order_by('track', 'name')
    )


def apply_institute_psychometric_settings_from_post(institute, post, *, save=True):
    """Apply access mode and assignment credit pool from marketing create/edit forms."""
    if not institute or not packages_enabled():
        return

    mode = (post.get('psychometric_access_mode') or '').strip()
    if mode in (
        choices.PsychometricAccessMode.FULL_BUNDLE,
        choices.PsychometricAccessMode.PACKAGE,
    ):
        institute.psychometric_access_mode = mode

    raw_assign_credits = (post.get('assignment_credits') or '').strip()
    if raw_assign_credits != '':
        try:
            institute.assignment_credits = max(0, int(raw_assign_credits))
        except (TypeError, ValueError):
            pass

    if save:
        institute.save(update_fields=['psychometric_access_mode', 'assignment_credits', 'modified'])


def sync_institute_packages_from_post(institute, post):
    """
    Persist marketing-selected packages for an institute (InstitutePackagePrice rows).
    When mode is full_bundle, clears the allowlist.
    """
    if not institute or not packages_enabled():
        return

    mode = (post.get('psychometric_access_mode') or institute.psychometric_access_mode or '').strip()
    if mode != choices.PsychometricAccessMode.PACKAGE:
        for row in InstitutePackagePrice.objects.complete().filter(institute=institute):
            row.delete(hard_delete=True)
        return

    selected_codes = [c.strip() for c in post.getlist('institute_package_codes') if c and c.strip()]
    valid = {
        pkg.code: pkg
        for pkg in PsychometricPackage.objects.filter(
            is_active=True,
            is_legacy_bundle=False,
            code__in=selected_codes,
        )
    }

    stale = InstitutePackagePrice.objects.complete().filter(institute=institute).exclude(
        package__code__in=valid.keys()
    )
    for row in stale:
        row.delete(hard_delete=True)

    for pkg in valid.values():
        InstitutePackagePrice.objects.complete().update_or_create(
            institute=institute,
            package=pkg,
            defaults={
                'unit_price': pkg.list_price,
                'object_status': choices.ObjectStatus.ACTIVE,
            },
        )


def get_package_choices_for_institute(institute, track=None):
    if not institute or not institute_package_mode_active(institute):
        return []
    packages = get_active_packages_for_institute(institute, track=track)
    return [
        {
            'code': pkg.code,
            'name': pkg.name,
            'credit_cost': pkg.credit_cost,
            'track': pkg.track,
        }
        for pkg in packages
    ]


def build_institute_package_dashboard_ctx(institute) -> dict:
    active = institute_package_mode_active(institute)
    return {
        'psychometric_packages_enabled': packages_enabled(),
        'institute_package_mode': active,
        'institute_assignment_credits': int(getattr(institute, 'assignment_credits', 0) or 0),
        'psychometric_package_choices': get_package_choices_for_institute(institute) if active else [],
    }


def build_marketing_psychometric_form_ctx():
    return {
        'psychometric_packages_enabled': packages_enabled(),
        'psychometric_catalog_packages': get_marketing_psychometric_catalog(),
    }


def get_student_package_labels_for_institute(institute) -> Dict[int, List[str]]:
    if not institute:
        return {}
    rows = (
        StudentPackageAssignment.objects.filter(institute=institute)
        .select_related('package', 'student')
        .order_by('-created')
    )
    out: Dict[int, List[str]] = {}
    for row in rows:
        if not row.package_id or row.package.is_legacy_bundle:
            continue
        sid = row.student_id
        label = row.package.name
        if sid not in out:
            out[sid] = []
        if label not in out[sid]:
            out[sid].append(label)
    return out


def get_student_package_labels_for_user_ids(student_ids) -> Dict[int, List[str]]:
    if not student_ids:
        return {}
    rows = (
        StudentPackageAssignment.objects.filter(student_id__in=student_ids)
        .select_related('package')
        .order_by('-created')
    )
    out: Dict[int, List[str]] = {}
    for row in rows:
        if not row.package_id or row.package.is_legacy_bundle:
            continue
        sid = int(row.student_id)
        label = row.package.name
        bucket = out.setdefault(sid, [])
        if label not in bucket:
            bucket.append(label)
    return out


def _detail_attempted(test_details: dict, keys) -> bool:
    for key in keys:
        value = (test_details or {}).get(key)
        if value is True:
            return True
        try:
            normalized = (str(value or '')).strip().lower()
        except Exception:
            normalized = ''
        if normalized in _ATTEMPTED_VALUES:
            return True
    return False


def build_student_roster_assessment_display(
    user,
    result_dict: Optional[dict],
    *,
    is_senior: bool,
    legacy_full: Optional[bool] = None,
    entitled_codes: Optional[Set[str]] = None,
    package_labels: Optional[List[str]] = None,
) -> dict:
    """
    Assessment rows for institute roster cards/list.

    Package students see only entitled tests; custom package names are included
    for manual verification. Full-bundle / legacy students keep all track tests.

    Optional precomputed flags avoid per-student DB hits on roster pages.
    """
    td = (result_dict or {}).get('test_details') or {}
    catalog = POST_MATRIC_ROSTER_ASSESSMENTS if is_senior else CLASS10_ROSTER_ASSESSMENTS
    if package_labels is None:
        package_labels = get_student_custom_package_names(user)
    else:
        package_labels = list(package_labels or [])

    if legacy_full is None:
        legacy_full = has_legacy_full_bundle_access(user)
    if entitled_codes is None and not legacy_full:
        entitled_codes = get_student_entitled_assessment_codes(user)
    elif entitled_codes is None:
        entitled_codes = set()

    def _row_for(item):
        attempted = _detail_attempted(td, item['detail_keys'])
        row_report = ''
        if attempted:
            row_report = get_roster_assessment_report_url(
                user,
                is_senior=is_senior,
                engine_key=item.get('engine_key') or '',
            )
        return {
            'label': item['label'],
            'engine_key': item.get('engine_key') or '',
            'attempted': attempted,
            'report_url': row_report or '',
        }

    if legacy_full:
        rows = [_row_for(item) for item in catalog]
    else:
        rows = [_row_for(item) for item in catalog if item['code'] in entitled_codes]

    # Prefer already-built roster status (no extra completion queries / reverse()).
    status = ((result_dict or {}).get('test_status') or '').strip().lower()
    report_ready = status == 'completed'
    report_url = ''
    if report_ready:
        uid = int(getattr(user, 'id', 0) or 0)
        if uid:
            report_url = roster_combined_report_url(user_id=uid, is_senior=is_senior)
        # Fallback for callers without status in result_dict.
        if not report_url:
            report_ready, report_url = get_institute_roster_report_url(
                user, is_senior=is_senior
            )
    elif not result_dict:
        report_ready, report_url = get_institute_roster_report_url(
            user, is_senior=is_senior
        )

    return {
        'rows': rows,
        'package_labels': package_labels,
        'show_all_tests': bool(legacy_full),
        'report_ready': bool(report_ready),
        'report_url': report_url or '',
        'is_custom_package': bool(package_labels),
    }


def build_roster_assessment_map(page_list, results_data) -> Dict[int, dict]:
    """Keyed by student user id for roster card/table templates."""
    out: Dict[int, dict] = {}
    page_student_ids = [
        int(sm.student_id)
        for sm in (page_list or [])
        if getattr(sm, 'student_id', None)
    ]
    labels_by_uid = get_student_package_labels_for_user_ids(page_student_ids)

    # Resolve institute package mode once (avoid N× StudentManagement / entitlement queries).
    institute = None
    for sm in page_list or []:
        institute = getattr(sm, 'institute', None)
        if institute:
            break
    package_mode = bool(
        packages_enabled()
        and institute
        and getattr(institute, 'uses_package_psychometric_mode', lambda: False)()
    )
    legacy_default = not package_mode

    entitled_by_uid: Dict[int, Set[str]] = {}
    if package_mode and page_student_ids:
        from psychometric_tests.models import StudentAssessmentEntitlement

        for row in (
            StudentAssessmentEntitlement.objects.filter(
                user_id__in=page_student_ids,
                is_active=True,
                assessment__is_active=True,
            )
            .values_list('user_id', 'assessment__code')
        ):
            entitled_by_uid.setdefault(int(row[0]), set()).add(row[1])

    for sm in page_list or []:
        uid = getattr(sm, 'student_id', None)
        student = getattr(sm, 'student', None)
        if not uid or not student:
            continue
        class_label = ''
        cas = getattr(sm, 'class_and_section', None)
        if cas and getattr(cas, 'class_and_section', None):
            class_label = str(cas.class_and_section).lower()
        is_senior = ('11' in class_label) or ('12' in class_label)
        result = results_data.get(uid) if isinstance(results_data, dict) else None
        assignment_labels = labels_by_uid.get(int(uid)) or []
        display = build_student_roster_assessment_display(
            student,
            result,
            is_senior=is_senior,
            legacy_full=legacy_default,
            entitled_codes=entitled_by_uid.get(int(uid), set()),
            package_labels=assignment_labels,
        )
        if assignment_labels:
            display['package_labels'] = assignment_labels
            display['is_custom_package'] = True
        out[int(uid)] = display
    return out


def try_assign_package_on_enroll(request, institute, student, package_code):
    """
    Assign a package after student enrollment when institute uses package mode.
    Returns (success, message).
    """
    if not packages_enabled() or not institute.uses_package_psychometric_mode():
        return True, ''
    if not package_code:
        return False, 'Select a psychometric package for this student.'
    try:
        assign_package_by_code(
            student,
            package_code,
            institute,
            assigned_by=getattr(request, 'user', None),
        )
        return True, ''
    except PackageAssignmentError as exc:
        logger.warning('Package assignment failed: %s', exc)
        return False, str(exc)


def try_assign_package_code(institute, student, package_code, assigned_by=None):
    if not packages_enabled() or not institute.uses_package_psychometric_mode():
        return True, ''
    if not package_code:
        return False, 'Select a psychometric package for this student.'
    try:
        assign_package_by_code(student, package_code, institute, assigned_by=assigned_by)
        return True, ''
    except PackageAssignmentError as exc:
        logger.warning('Package assignment failed: %s', exc)
        return False, str(exc)


def maybe_assign_package_from_post(request, institute, student):
    package_code = (request.POST.get('psychometric_package') or '').strip()
    ok, message = try_assign_package_on_enroll(request, institute, student, package_code)
    if not ok and message:
        messages.error(request, message)
    return ok
