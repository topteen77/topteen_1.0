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

    # Assignment credit pool matches exam credits entered on the same form.
    from institute.tieup_billing import parse_exam_credits_qty_from_post

    exam_qty, _exam_err = parse_exam_credits_qty_from_post(post)
    if exam_qty is not None:
        institute.assignment_credits = exam_qty
    else:
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


def institute_csv_upload_kinds(institute) -> dict:
    """Which bulk-upload buttons this institute may use.

    Full-bundle schools keep Class 10 and Class 12 uploads.
    Package mode shows a button only when the allowlist includes that track.
    """
    legacy = {'matric': True, 'postmatric': True, 'higher_ed': False}
    if not institute or not institute_package_mode_active(institute):
        return legacy
    flags = upload_kind_flags_by_institute_ids([institute.id])
    return flags.get(institute.id, legacy)


def upload_kind_flags_by_institute_ids(institute_ids) -> dict:
    """Batch version of institute_csv_upload_kinds. Empty package allowlist means every active package."""
    from collections import defaultdict

    from institute.higher_ed_csv import HIGHER_ED_PACKAGE_CODES
    from institute.models import Institute
    from psychometric_tests.models import InstitutePackagePrice, PsychometricPackage

    legacy = {'matric': True, 'postmatric': True, 'higher_ed': False}
    ids = []
    for raw in institute_ids or []:
        try:
            iid = int(raw)
        except (TypeError, ValueError):
            continue
        if iid not in ids:
            ids.append(iid)
    if not ids:
        return {}
    if not packages_enabled():
        return {iid: dict(legacy) for iid in ids}

    modes = dict(
        Institute.objects.filter(id__in=ids).values_list('id', 'psychometric_access_mode')
    )
    codes = defaultdict(set)
    tracks = defaultdict(set)
    for row in (
        InstitutePackagePrice.objects.filter(institute_id__in=ids)
        .select_related('package')
    ):
        package = row.package
        if not package or not package.is_active:
            continue
        codes[row.institute_id].add(package.code)
        tracks[row.institute_id].add(package.track)

    catalog_tracks = None
    catalog_higher = False
    out = {}
    for iid in ids:
        if modes.get(iid) != choices.PsychometricAccessMode.PACKAGE:
            out[iid] = dict(legacy)
            continue
        if not codes.get(iid):
            if catalog_tracks is None:
                active = PsychometricPackage.objects.filter(is_active=True)
                catalog_tracks = set(active.values_list('track', flat=True))
                catalog_codes = set(active.values_list('code', flat=True))
                catalog_higher = bool(catalog_codes & HIGHER_ED_PACKAGE_CODES)
            out[iid] = {
                'matric': choices.PsychometricTrack.CLASS10 in catalog_tracks,
                'postmatric': choices.PsychometricTrack.POST_MATRIC in catalog_tracks,
                'higher_ed': catalog_higher,
            }
            continue
        out[iid] = {
            'matric': choices.PsychometricTrack.CLASS10 in tracks[iid],
            'postmatric': choices.PsychometricTrack.POST_MATRIC in tracks[iid],
            'higher_ed': bool(codes[iid] & HIGHER_ED_PACKAGE_CODES),
        }
    return out


def upload_kinds_for_managed_institutes(user) -> dict:
    """Union of upload buttons across institutes this marketing or group admin manages."""
    from institute.models import Institute

    empty = {'matric': False, 'postmatric': False, 'higher_ed': False}
    if not user or not getattr(user, 'is_authenticated', False):
        return empty
    try:
        user_type = int(getattr(user, 'user_type', 0) or 0)
    except (TypeError, ValueError):
        return empty
    if user_type == choices.UserType.MARKETINGGROUPADMIN:
        ids = Institute.objects.filter(
            marketing_group__marketing_group_admin=user
        ).values_list('id', flat=True)
    elif user_type == choices.UserType.INSTITUTEGROUPADMIN:
        ids = Institute.objects.filter(
            institute_group__institute_group_admin=user
        ).values_list('id', flat=True)
    else:
        return empty
    flags = upload_kind_flags_by_institute_ids(list(ids))
    merged = dict(empty)
    for kind in flags.values():
        merged['matric'] = merged['matric'] or kind['matric']
        merged['postmatric'] = merged['postmatric'] or kind['postmatric']
        merged['higher_ed'] = merged['higher_ed'] or kind['higher_ed']
    return merged


def higher_ed_package_choices_by_institute_ids(institute_ids) -> dict:
    """Single-test packages each institute may assign on the College/Professional upload."""
    from collections import defaultdict

    from institute.higher_ed_csv import HIGHER_ED_PACKAGE_CODES
    from institute.models import Institute

    ids = []
    for raw in institute_ids or []:
        try:
            iid = int(raw)
        except (TypeError, ValueError):
            continue
        if iid not in ids:
            ids.append(iid)
    if not ids:
        return {}

    catalog = [
        {'code': pkg.code, 'name': pkg.name, 'credit_cost': pkg.credit_cost}
        for pkg in PsychometricPackage.objects.filter(
            is_active=True, code__in=HIGHER_ED_PACKAGE_CODES
        ).order_by('name')
    ]
    modes = dict(
        Institute.objects.filter(id__in=ids).values_list('id', 'psychometric_access_mode')
    )
    allowed = defaultdict(set)
    has_allowlist = set()
    for row in InstitutePackagePrice.objects.filter(institute_id__in=ids).select_related('package'):
        package = row.package
        if not package or not package.is_active:
            continue
        has_allowlist.add(row.institute_id)
        if package.code in HIGHER_ED_PACKAGE_CODES:
            allowed[row.institute_id].add(package.code)

    out = {}
    for iid in ids:
        if modes.get(iid) != choices.PsychometricAccessMode.PACKAGE:
            out[iid] = []
            continue
        if iid not in has_allowlist:
            out[iid] = list(catalog)
            continue
        out[iid] = [row for row in catalog if row['code'] in allowed[iid]]
    return out


def annotate_quicklink_upload_flags(rows) -> None:
    """Add can_upload_* keys used by marketing and institute-group upload buttons."""
    if not rows:
        return
    row_ids = [row.get('id') for row in rows if isinstance(row, dict)]
    flags = upload_kind_flags_by_institute_ids(row_ids)
    packages = higher_ed_package_choices_by_institute_ids(row_ids)
    legacy = {'matric': True, 'postmatric': True, 'higher_ed': False}
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = flags.get(row.get('id'), legacy)
        row['can_upload_matric'] = kind['matric']
        row['can_upload_postmatric'] = kind['postmatric']
        row['can_upload_higher_ed'] = kind['higher_ed']
        row['higher_ed_packages'] = packages.get(row.get('id'), [])


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
    from django.urls import reverse

    from psychometric_tests.package_assignment import student_has_started_psychometric

    out: Dict[int, dict] = {}
    page_student_ids = [
        int(sm.student_id)
        for sm in (page_list or [])
        if getattr(sm, 'student_id', None)
    ]
    labels_by_uid = get_student_package_labels_for_user_ids(page_student_ids)

    started_ids: Set[int] = set()
    if page_student_ids:
        try:
            from app_post_matric.models import TestSession

            started_ids.update(
                int(uid)
                for uid in TestSession.objects.filter(user_id__in=page_student_ids)
                .values_list('user_id', flat=True)
                .distinct()
            )
        except Exception:
            pass
        try:
            from app.models import Results, TestCompletion

            started_ids.update(
                int(uid)
                for uid in Results.objects.filter(user_id__in=page_student_ids)
                .values_list('user_id', flat=True)
                .distinct()
            )
            for tc in TestCompletion.objects.filter(user_id__in=page_student_ids).only(
                'user_id',
                'test1_complete',
                'test2_complete',
                'test3_complete',
                'numerical_complete',
                'verbal_complete',
                'logical_complete',
                'emotional_complete',
                'machanical_complete',
                'language_complete',
                'spatial_complete',
            ):
                if any(
                    [
                        tc.test1_complete,
                        tc.test2_complete,
                        tc.test3_complete,
                        tc.numerical_complete,
                        tc.verbal_complete,
                        tc.logical_complete,
                        tc.emotional_complete,
                        tc.machanical_complete,
                        tc.language_complete,
                        tc.spatial_complete,
                    ]
                ):
                    started_ids.add(int(tc.user_id))
        except Exception:
            pass

    entitled_by_uid: Dict[int, Set[str]] = {}
    if packages_enabled() and page_student_ids:
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
        student_institute = getattr(sm, 'institute', None)
        package_mode = institute_package_mode_active(student_institute)
        legacy_full = not package_mode
        display = build_student_roster_assessment_display(
            student,
            result,
            is_senior=is_senior,
            legacy_full=legacy_full,
            entitled_codes=entitled_by_uid.get(int(uid), set()),
            package_labels=assignment_labels,
        )
        if assignment_labels:
            display['package_labels'] = assignment_labels
            display['is_custom_package'] = True
        tests_started = int(uid) in started_ids
        # Fallback single-student check if batch missed (should be rare).
        if not tests_started and package_mode:
            try:
                tests_started = student_has_started_psychometric(student)
            except Exception:
                tests_started = False
        display['tests_started'] = bool(tests_started)
        display['can_assign_or_change_package'] = bool(package_mode and not tests_started)
        display['assign_package_url'] = ''
        if display['can_assign_or_change_package'] and student_institute and getattr(student_institute, 'slug', None):
            try:
                display['assign_package_url'] = reverse(
                    'institute:assign_student_package',
                    args=[student_institute.slug],
                )
            except Exception:
                display['assign_package_url'] = ''
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
            allow_replace=True,
        )
        return True, ''
    except PackageAssignmentError as exc:
        logger.warning('Package assignment failed: %s', exc)
        return False, str(exc)


def try_assign_package_code(institute, student, package_code, assigned_by=None):
    """
    Assign or replace package for an existing student (not started only).
    Wrong / missing package can be fixed until the student starts a test.
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
            assigned_by=assigned_by,
            allow_replace=True,
        )
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
