"""Central access control for psychometric assessments and packages."""

from __future__ import annotations

from typing import Optional, Set

from django.conf import settings

from core import choices
from core.psychometric_grade import CLASS10_TRACK, POST_MATRIC_TRACK, get_student_psychometric_track


def packages_enabled() -> bool:
    return bool(getattr(settings, 'ENABLE_PSYCHOMETRIC_PACKAGES', False))


def _get_institute_for_user(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    try:
        from institute.models import get_cached_student_management

        sm = get_cached_student_management(user)
        return sm.institute if sm else None
    except Exception:
        return None


def has_successful_bundle_payment(user, track: str) -> bool:
    from psychometric_tests.models import PsychometricTestPayment

    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if track == POST_MATRIC_TRACK:
        test_type = choices.PsychometricTestType.ADVANCED
    else:
        test_type = choices.PsychometricTestType.BASIC
    return PsychometricTestPayment.objects.filter(
        user=user,
        test_type=test_type,
        is_success=choices.YesNoChoices.YES,
    ).exists()


def has_legacy_full_bundle_access(user) -> bool:
    """
  True when user should see the full track bundle (legacy behavior).
  """
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    if not packages_enabled():
        try:
            from institute.models import StudentManagement

            if StudentManagement.objects.filter(student=user).exists():
                return True
        except Exception:
            pass

    institute = _get_institute_for_user(user)
    if institute and not institute.uses_package_psychometric_mode():
        return True

    track = get_student_psychometric_track(user)
    if has_successful_bundle_payment(user, track):
        return True

    if packages_enabled() and institute and institute.uses_package_psychometric_mode():
        return False

    if not packages_enabled():
        return has_successful_bundle_payment(user, track)

    return False


def get_track_assessment_codes(track: str) -> Set[str]:
    from psychometric_tests.models import Assessment

    return set(
        Assessment.objects.filter(track=track, is_active=True).values_list('code', flat=True)
    )


def get_student_entitled_assessment_codes(user) -> Set[str]:
    if not user or not getattr(user, 'is_authenticated', False):
        return set()

    if has_legacy_full_bundle_access(user):
        track = get_student_psychometric_track(user)
        return get_track_assessment_codes(track)

    from psychometric_tests.models import StudentAssessmentEntitlement

    return set(
        StudentAssessmentEntitlement.objects.filter(
            user=user,
            is_active=True,
            assessment__is_active=True,
        ).values_list('assessment__code', flat=True)
    )


def has_assessment_access(user, assessment_code: str) -> bool:
    if has_legacy_full_bundle_access(user):
        return True
    return assessment_code in get_student_entitled_assessment_codes(user)


def has_class10_test_access(user, test_paper: str) -> bool:
    from psychometric_tests.package_catalog import CLASS10_ENGINE_TO_CODE

    code = CLASS10_ENGINE_TO_CODE.get(test_paper)
    if not code:
        return has_legacy_full_bundle_access(user)
    return has_assessment_access(user, code)


def has_post_matric_test_access(user, test_id) -> bool:
    from psychometric_tests.package_catalog import post_matric_test_id_to_code

    code = post_matric_test_id_to_code(test_id)
    if not code:
        return has_legacy_full_bundle_access(user)
    return has_assessment_access(user, code)


def can_view_combined_report(user) -> bool:
    if has_legacy_full_bundle_access(user):
        return True
    track = get_student_psychometric_track(user)
    entitled = get_student_entitled_assessment_codes(user)
    required = get_track_assessment_codes(track)
    return required and required.issubset(entitled)


def institute_student_exempt_from_payment(user) -> bool:
    """Replacement for blanket is_institute_student payment bypass."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if not packages_enabled():
        try:
            from institute.models import StudentManagement

            return StudentManagement.objects.filter(student=user).exists()
        except Exception:
            return False
    return has_legacy_full_bundle_access(user)


def can_access_psychometric_dashboard(user) -> bool:
    """Whether the student may open the psychometric test dashboard."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if has_legacy_full_bundle_access(user):
        return True
    if packages_enabled() and get_student_entitled_assessment_codes(user):
        return True
    track = get_student_psychometric_track(user)
    return has_successful_bundle_payment(user, track)


def redirect_if_no_class10_test_access(request, test_paper: str):
    from django.shortcuts import redirect
    from django.urls import reverse

    if not has_class10_test_access(request.user, test_paper):
        return redirect(reverse('app:test_buttons'))
    return None


def redirect_if_no_post_matric_test_access(request, test_id):
    from django.shortcuts import redirect
    from django.urls import reverse

    if not has_post_matric_test_access(request.user, test_id):
        return redirect(reverse('post_matric:tests'))
    return None


def get_active_packages_for_institute(institute, track: Optional[str] = None):
    from psychometric_tests.models import PsychometricPackage

    qs = PsychometricPackage.objects.filter(is_active=True).prefetch_related(
        'package_assessments__assessment'
    )
    if track:
        qs = qs.filter(track=track)
    if institute and institute.uses_package_psychometric_mode():
        from psychometric_tests.models import InstitutePackagePrice

        allowed_ids = list(
            InstitutePackagePrice.objects.filter(institute=institute).values_list(
                'package_id', flat=True
            )
        )
        if allowed_ids:
            qs = qs.filter(id__in=allowed_ids)
        return qs
    return qs.filter(is_legacy_bundle=True)


def _class10_engine_complete(user, engine_key: str) -> bool:
    from app.models import TestCompletion

    tc = TestCompletion.objects.filter(user=user).first()
    if not tc:
        return False
    if engine_key == 'test1':
        return bool(tc.test1_complete)
    if engine_key == 'test2':
        return bool(tc.test2_complete)
    if engine_key == 'test3':
        return bool(tc.test3_complete)
    return False


def _post_matric_engine_complete(user, engine_key: str) -> bool:
    from app_post_matric.models import TestSession

    try:
        test_id = int(engine_key)
    except (TypeError, ValueError):
        return False
    return TestSession.objects.filter(user=user, test_id=test_id, is_completed=True).exists()


def student_has_incomplete_entitled_psychometric(user) -> bool:
    """True when a package student still has entitled assessments to complete."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if has_legacy_full_bundle_access(user):
        return False
    if not can_access_psychometric_dashboard(user):
        return False

    entitled = get_student_entitled_assessment_codes(user)
    if not entitled:
        return False

    track = get_student_psychometric_track(user)
    if track == POST_MATRIC_TRACK:
        from psychometric_tests.package_catalog import POST_MATRIC_ASSESSMENTS

        for item in POST_MATRIC_ASSESSMENTS:
            if item['code'] not in entitled:
                continue
            if not _post_matric_engine_complete(user, item['engine_key']):
                return True
        return False

    from psychometric_tests.package_catalog import CLASS10_ASSESSMENTS

    for item in CLASS10_ASSESSMENTS:
        if item['code'] not in entitled:
            continue
        if not _class10_engine_complete(user, item['engine_key']):
            return True
    return False


CLASS10_ENGINE_REPORT_URL = {
    'test1': 'app:test1_report_html',
    'test2': 'app:test2_report_html',
    'test3': 'app:test3_report_html',
}


def _class10_report_url_for_user_id(user_id: int, engine_key: str) -> str:
    from django.urls import reverse

    route = CLASS10_ENGINE_REPORT_URL.get(engine_key)
    if not route:
        return ''
    return reverse(route, args=[user_id])


def get_institute_roster_report_url(user, *, is_senior: bool) -> tuple:
    """
    Report URL for institute roster embed modal (scoped to the student user id).

    Institute Report opens only for full-track / legacy bundle completion.
    Single-test custom packages show status on the card but do not enable Report.

    Returns (report_ready, report_url).
    """
    from django.urls import reverse

    uid = int(getattr(user, 'id', 0) or 0)
    if not uid:
        return False, ''

    if has_legacy_full_bundle_access(user):
        if is_senior:
            from psychometric_tests.package_catalog import POST_MATRIC_ASSESSMENTS

            if all(
                _post_matric_engine_complete(user, item['engine_key'])
                for item in POST_MATRIC_ASSESSMENTS
            ):
                return True, reverse('post_matric:combined_report', kwargs={'user_id': uid})
            return False, ''
        if _class10_legacy_all_complete(user):
            return True, reverse('app:dashboard_for_user', args=[uid])
        return False, ''

    entitled = get_student_entitled_assessment_codes(user)
    if not entitled:
        return False, ''

    track = POST_MATRIC_TRACK if is_senior else CLASS10_TRACK
    required = get_track_assessment_codes(track)
    # Custom / partial packages: no roster Report button.
    if not required or not required.issubset(entitled):
        return False, ''

    if is_senior:
        from psychometric_tests.package_catalog import POST_MATRIC_ASSESSMENTS

        if not all(
            _post_matric_engine_complete(user, item['engine_key'])
            for item in POST_MATRIC_ASSESSMENTS
            if item['code'] in entitled
        ):
            return False, ''
        return True, reverse('post_matric:combined_report', kwargs={'user_id': uid})

    if not _class10_legacy_all_complete(user):
        return False, ''
    return True, reverse('app:dashboard_for_user', args=[uid])


def _class10_has_any_attempt(user) -> bool:
    from app.models import Results, TestCompletion

    tc = TestCompletion.objects.filter(user=user).first()
    if tc and any(
        [
            bool(tc.test1_complete),
            bool(tc.test2_complete),
            bool(tc.test3_complete),
            bool(tc.numerical_complete),
            bool(tc.verbal_complete),
            bool(tc.logical_complete),
            bool(tc.emotional_complete),
            bool(tc.machanical_complete),
            bool(tc.language_complete),
            bool(tc.spatial_complete),
        ]
    ):
        return True
    return Results.objects.filter(user=user).exists()


def _class10_legacy_all_complete(user) -> bool:
    from app.models import TestCompletion

    tc = TestCompletion.objects.filter(user=user).first()
    if not tc or not (tc.test1_complete and tc.test2_complete and tc.test3_complete):
        return False
    return bool(
        tc.numerical_complete
        and tc.verbal_complete
        and tc.logical_complete
        and tc.emotional_complete
        and tc.machanical_complete
        and tc.language_complete
        and tc.spatial_complete
    )


def _post_matric_has_any_attempt(user) -> bool:
    from app_post_matric.models import TestSession

    return TestSession.objects.filter(user=user).exists()


def _post_matric_all_entitled_complete(user, entitled: Set[str]) -> bool:
    from psychometric_tests.package_catalog import POST_MATRIC_ASSESSMENTS

    for item in POST_MATRIC_ASSESSMENTS:
        if item['code'] not in entitled:
            continue
        if not _post_matric_engine_complete(user, item['engine_key']):
            return False
    return bool(entitled)


def get_student_psychometric_dashboard_cta(user) -> dict:
    """
    CTA for the student dashboard "My courses & tests" psychometric card.

    Returns action_label, action_variant ('start' | 'report'), and url.
    Cached briefly — progress changes infrequently relative to dashboard refresh.
    """
    from django.core.cache import cache

    uid = int(getattr(user, "id", 0) or 0)
    cache_key = f"psych:dash_cta:v1:{uid}" if uid else None
    if cache_key:
        try:
            cached = cache.get(cache_key)
            if isinstance(cached, dict) and "url" in cached:
                return cached
        except Exception:
            pass
    result = _compute_student_psychometric_dashboard_cta(user)
    if cache_key and isinstance(result, dict):
        try:
            cache.set(cache_key, result, 90)
        except Exception:
            pass
    return result


def _compute_student_psychometric_dashboard_cta(user) -> dict:
    from django.urls import reverse

    track = get_student_psychometric_track(user)
    custom_packages = get_student_custom_package_names(user)
    if custom_packages:
        subtitle = ', '.join(custom_packages)
    else:
        subtitle = 'Assessment'
    if track == POST_MATRIC_TRACK:
        default_url = reverse('post_matric:tests')
        test_name = 'Career Direction'
    else:
        default_url = reverse('app:test_buttons')
        test_name = 'Stream Sorter'

    if has_legacy_full_bundle_access(user):
        if track == POST_MATRIC_TRACK:
            try:
                from app_post_matric.models import TestSession

                all_four = all(
                    TestSession.objects.filter(
                        user=user, test__id=test_id, is_completed=True
                    ).exists()
                    for test_id in (1, 2, 3, 4)
                )
                if all_four:
                    report_url = reverse(
                        'post_matric:combined_report', kwargs={'user_id': user.id}
                    )
                    return {
                        'test_name': test_name,
                        'subtitle': subtitle,
                        'action_label': 'View combined report',
                        'action_variant': 'report',
                        'url': report_url,
                    }
            except Exception:
                pass
            if _post_matric_has_any_attempt(user):
                return {
                    'test_name': test_name,
                    'subtitle': subtitle,
                    'action_label': 'Resume',
                    'action_variant': 'start',
                    'url': default_url,
                }
            return {
                'test_name': test_name,
                'subtitle': subtitle,
                'action_label': 'Start',
                'action_variant': 'start',
                'url': default_url,
            }

        if _class10_legacy_all_complete(user):
            return {
                'test_name': test_name,
                'subtitle': subtitle,
                'action_label': 'View report',
                'action_variant': 'report',
                'url': reverse('app:dashboard'),
            }
        if _class10_has_any_attempt(user):
            return {
                'test_name': test_name,
                'subtitle': subtitle,
                'action_label': 'Resume',
                'action_variant': 'start',
                'url': default_url,
            }
        return {
            'test_name': test_name,
            'subtitle': subtitle,
            'action_label': 'Start',
            'action_variant': 'start',
            'url': default_url,
        }

    entitled = get_student_entitled_assessment_codes(user)
    if not entitled:
        return {
            'test_name': test_name,
            'subtitle': subtitle,
            'action_label': 'Start',
            'action_variant': 'start',
            'url': default_url,
        }

    if track == POST_MATRIC_TRACK:
        if _post_matric_all_entitled_complete(user, entitled):
            if len(entitled) == len(get_track_assessment_codes(track)):
                report_url = reverse(
                    'post_matric:combined_report', kwargs={'user_id': user.id}
                )
                return {
                    'test_name': test_name,
                    'subtitle': subtitle,
                    'action_label': 'View combined report',
                    'action_variant': 'report',
                    'url': report_url,
                }
            return {
                'test_name': test_name,
                'subtitle': subtitle,
                'action_label': 'View report',
                'action_variant': 'report',
                'url': default_url,
            }
        if _post_matric_has_any_attempt(user):
            return {
                'test_name': test_name,
                'subtitle': subtitle,
                'action_label': 'Resume',
                'action_variant': 'start',
                'url': default_url,
            }
        return {
            'test_name': test_name,
            'subtitle': subtitle,
            'action_label': 'Start',
            'action_variant': 'start',
            'url': default_url,
        }

    from psychometric_tests.package_catalog import CLASS10_ASSESSMENTS

    entitled_items = [item for item in CLASS10_ASSESSMENTS if item['code'] in entitled]
    all_entitled_done = all(
        _class10_engine_complete(user, item['engine_key']) for item in entitled_items
    )
    if all_entitled_done:
        if len(entitled_items) == 1:
            engine_key = entitled_items[0]['engine_key']
            report_route = CLASS10_ENGINE_REPORT_URL.get(engine_key)
            report_url = reverse(report_route) if report_route else default_url
            return {
                'test_name': test_name,
                'subtitle': subtitle,
                'action_label': 'View report',
                'action_variant': 'report',
                'url': report_url,
            }
        return {
            'test_name': test_name,
            'subtitle': subtitle,
            'action_label': 'View report',
            'action_variant': 'report',
            'url': default_url,
        }
    if _class10_has_any_attempt(user):
        return {
            'test_name': test_name,
            'subtitle': subtitle,
            'action_label': 'Resume',
            'action_variant': 'start',
            'url': default_url,
        }
    return {
        'test_name': test_name,
        'subtitle': subtitle,
        'action_label': 'Start',
        'action_variant': 'start',
        'url': default_url,
    }


def get_student_custom_package_names(user) -> list:
    """Non-legacy package names assigned to the student (for verification UI)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    if has_legacy_full_bundle_access(user) or not packages_enabled():
        return []

    from psychometric_tests.models import StudentPackageAssignment

    seen = set()
    names = []
    for row in (
        StudentPackageAssignment.objects.filter(student=user)
        .select_related('package')
        .order_by('-created')
    ):
        pkg = row.package
        if not pkg or pkg.is_legacy_bundle:
            continue
        if pkg.name in seen:
            continue
        seen.add(pkg.name)
        names.append(pkg.name)
    return names


def build_class10_psychometric_page_context(user) -> dict:
    """Shared template context for Class 10 psychometric home / submit pages."""
    return {
        'test_access': {
            'test1': has_class10_test_access(user, 'test1'),
            'test2': has_class10_test_access(user, 'test2'),
            'test3': has_class10_test_access(user, 'test3'),
        },
        'entitled_assessments': sorted(get_student_entitled_assessment_codes(user)),
        'packages_enabled': packages_enabled(),
        'show_all_psychometric_tests': has_legacy_full_bundle_access(user),
        'psychometric_custom_package_names': get_student_custom_package_names(user),
    }


def get_package_student_login_redirect(user) -> Optional[str]:
    """
    Landing page for institute students with package entitlements after login.
    Returns None to keep the default student dashboard route.
    """
    if not student_has_incomplete_entitled_psychometric(user):
        return None

    from django.urls import reverse

    if get_student_psychometric_track(user) == POST_MATRIC_TRACK:
        return reverse('post_matric:tests')
    return reverse('app:test_buttons')
