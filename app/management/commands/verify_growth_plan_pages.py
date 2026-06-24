"""Verify growth-area improvement plan wiring across dashboards and reports."""

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.test import Client
from django.urls import reverse

from app.aptitude_improvement_plans import CLASS_10, CLASS_12, build_improvement_plans_for_below_areas
from app.models import AptitudeImprovementPlan, Results

User = get_user_model()


def _below_areas_class10(user):
    try:
        from app.views import db_results_inst_user

        *_, below, avg, above_avg, _ = db_results_inst_user(user)
        return list(below or []), list(avg or []), list(above_avg or [])
    except Exception:
        return [], [], []


def _below_areas_class12(user):
    try:
        from app_post_matric.aptitude_area_labels import normalize_aptitude_categories
        from app_post_matric.models import Test, TestSession, TestTopCategories

        aptitude_test = Test.objects.filter(title='Aptitude Assessment').first()
        if not aptitude_test:
            return []
        session = (
            TestSession.objects.filter(user=user, test=aptitude_test, end_time__isnull=False)
            .order_by('-end_time')
            .first()
        )
        if not session:
            return []
        record = TestTopCategories.objects.filter(user=user, test_paper=aptitude_test).first()
        if not record or not record.high_category:
            return []
        data = json.loads(record.high_category)
        if not isinstance(data, dict):
            return []
        data = normalize_aptitude_categories(data)
        return list(data.get('Below Average', []) or [])
    except Exception:
        return []


def run_verification(stdout=None):
    def log(msg):
        if stdout:
            stdout.write(msg)
        else:
            print(msg)

    log('=== Growth plan page verification ===\n')
    log(
        f'Seeded admin plans — Class 10: '
        f'{AptitudeImprovementPlan.objects.filter(education_level=CLASS_10, is_active=True).count()}, '
        f'Class 12: '
        f'{AptitudeImprovementPlan.objects.filter(education_level=CLASS_12, is_active=True).count()}\n'
    )

    client = Client()
    results = []

    class10_user = None
    class10_below = []
    for row in Results.objects.filter(test_paper='test3').select_related('user').order_by('-modified')[:150]:
        user = row.user
        if not user or not user.is_active:
            continue
        below, _, _ = _below_areas_class10(user)
        if below and build_improvement_plans_for_below_areas(below, CLASS_10):
            class10_user = user
            class10_below = below
            break

    class12_user = None
    class12_below = []
    for user in User.objects.filter(is_active=True).order_by('-id')[:500]:
        below = _below_areas_class12(user)
        if below and build_improvement_plans_for_below_areas(below, CLASS_12):
            class12_user = user
            class12_below = below
            break

    def check_page(name, url, user, needles=None, check_vocational_plain=False):
        if not user:
            results.append((name, 'SKIP', 'no user with growth areas + admin plans'))
            return
        client.force_login(user)
        response = client.get(url, follow=True)
        body = response.content.decode('utf-8', errors='ignore')
        ok = response.status_code == 200
        detail_parts = [f'status={response.status_code}']
        for needle in needles or []:
            has_needle = needle in body
            ok = ok and has_needle
            detail_parts.append(f"contains '{needle}'={has_needle}")
        if check_vocational_plain:
            linked = 'Vocational guidance for skill development</a>' in body
            ok = ok and not linked
            detail_parts.append(f'vocational title not linked={not linked}')
        results.append((name, 'PASS' if ok else 'FAIL', ', '.join(detail_parts)))

    growth_plan_needles = [
        'Strategic Plan for Growth Area',
        'Development Goal',
        'Practice Frequency',
        'Expected Improvement Timeline',
        'Suggested Improvement Plan',
    ]

    if class10_user:
        log(f'Class 10 sample: {class10_user.email} growth areas={class10_below}')
    else:
        log('Class 10 sample: none found')

    if class12_user:
        log(f'Class 12 sample: {class12_user.email} growth areas={class12_below}')
    else:
        log('Class 12 sample: none found')
    log('')

    check_page(
        '1_psychometric_dashboard',
        '/psychometric/dashboard/',
        class10_user,
        growth_plan_needles,
        check_vocational_plain=True,
    )
    check_page(
        '2_class10_aptitude_report',
        '/psychometric/web/test3_report/',
        class10_user,
        growth_plan_needles,
    )
    check_page(
        '3_class10_combined_report',
        '/psychometric/web/combined_report/',
        class10_user,
        growth_plan_needles,
    )
    check_page(
        '4_class12_dashboard',
        '/api/web/tests/',
        class12_user,
    )
    check_page(
        '5_class12_aptitude_report',
        '/api/web/results/?test_id=4',
        class12_user,
        growth_plan_needles,
    )
    if class12_user:
        combined_url = reverse('post_matric:combined_report', kwargs={'user_id': class12_user.id})
        check_page(
            '6_class12_combined_report',
            combined_url,
            class12_user,
            growth_plan_needles,
        )
    else:
        results.append(('6_class12_combined_report', 'SKIP', 'no class 12 user'))

    log('--- Results ---')
    all_pass = True
    for name, status, detail in results:
        log(f'{status:4} {name}: {detail}')
        if status == 'FAIL':
            all_pass = False
    log('')
    return all_pass, results


class Command(BaseCommand):
    help = 'Verify growth plan sections on dashboards and reports'

    def handle(self, *args, **options):
        ok, _ = run_verification(stdout=self.stdout)
        if not ok:
            raise SystemExit(1)
