"""
Shared logic for creating the fixed demo dataset.
Only this module sets is_system_demo on User and Institute.
Uses DemoDatasetConfig (singleton) for: student counts per class, psychometric options, result type.

Remove/reset hard-deletes system-demo users and related Skill Lab, package personality,
psychometric payments, analytics tracking, counseling follow-ups, and legacy test results.
"""
from django.db import transaction

from core import choices
from users.models import User, UserProfile, ParentStudentLink
from institute.models import Institute, ClassAndSection, StudentManagement
from app.models import TestCompletion, Results
from app_post_matric.models import (
    Test,
    TestSession,
    TestResult,
    SectionSession,
    UserResponse,
    TestTopCategories,
)
from demo_data.models import DemoCounselorCourseState, DemoDatasetConfig, ResultType
from counselor.models import (
    Counselor,
    CounselorCertification,
    CounselorCourse,
    QuizResults,
    VideoProgress,
)
from counselor.demo_course_state import (
    apply_demo_counselor_course_state,
    create_counselor_course_payment,
)
from payments.models import Payment

DEMO_PASSWORD = "demo123"
DEMO_EMAIL_DOMAIN = "topteen.demo"
INSTITUTE_SLUG = "demo-institute"
DEMO_COUNSELOR_EMAIL = f"demo_counselor@{DEMO_EMAIL_DOMAIN}"

# RIASEC order used by report views and gernate_graph for test1/test2
RIASEC = ["Realistic", "Investigative", "Artistic", "Social", "Enterprising", "Conventional"]

# Test3 intelligence score keys (must match app/views gernate_graph and db_results_inst_user)
TEST3_SCORE_KEYS = [
    "logical_score", "verbal_score", "numerical_score", "critical_score",
    "language_score", "spatial_score", "mechanical_score",
]


def _personality_results_for_result_type(result_type, student_index):
    """
    Return test1 Results.results: dict of RIASEC category -> percentage (0-100).
    Used by db_results_inst_user (top_categories, top_category_code) and gernate_graph (personality chart).
    """
    if result_type == ResultType.HIGH:
        # All high percentages
        base = 82 + (student_index % 3) * 2
        return {c: min(100, base + i) for i, c in enumerate(RIASEC)}
    elif result_type == ResultType.MEDIUM:
        base = 55 + (student_index % 2)
        return {c: min(100, base + i) for i, c in enumerate(RIASEC)}
    elif result_type == ResultType.LOW:
        base = 28 + (student_index % 2)
        return {c: min(100, base + i) for i, c in enumerate(RIASEC)}
    elif result_type == ResultType.MIXED:
        high = student_index % 2 == 0
        base = 75 if high else 35
        return {c: min(100, base + i) for i, c in enumerate(RIASEC)}
    else:
        # VARIED: rotate which category is top
        which = student_index % 4
        out = {c: 40 + (student_index % 5) for c in RIASEC}
        # Boost top 3 for a valid-looking profile
        for j in range(3):
            out[RIASEC[(which + j) % 6]] = 85 - j * 5
        return out


def _interest_scores_for_result_type(result_type, student_index):
    """
    Return test2 Results.scores: dict of RIASEC category -> score (0-39 scale for interest chart).
    Used by db_results_inst_user (max_length, min_length) and gernate_graph (interest chart).
    """
    if result_type == ResultType.HIGH:
        base = 30 + (student_index % 3)
        return {c: min(36, base + (i % 2)) for i, c in enumerate(RIASEC)}
    elif result_type == ResultType.MEDIUM:
        base = 18 + (student_index % 2)
        return {c: min(36, base + i % 3) for i, c in enumerate(RIASEC)}
    elif result_type == ResultType.LOW:
        base = 6 + (student_index % 2)
        return {c: min(36, base + i % 2) for i, c in enumerate(RIASEC)}
    elif result_type == ResultType.MIXED:
        high = student_index % 2 == 0
        base = 26 if high else 10
        return {c: min(36, base + (i % 2)) for i, c in enumerate(RIASEC)}
    else:
        which = student_index % 4
        base = [28, 18, 10, 22][which]
        return {c: min(36, base + (i % 3)) for i, c in enumerate(RIASEC)}


def _intelligence_scores_for_result_type(result_type, student_index):
    """
    Return test3 Results.scores: dict of *_score keys -> value (0-15).
    Used by db_results_inst_user (below, avg, above_avg) and gernate_graph (intelligence chart).
    """
    if result_type == ResultType.HIGH:
        base = 12
        return {k: min(15, base + (student_index + i) % 4) for i, k in enumerate(TEST3_SCORE_KEYS)}
    elif result_type == ResultType.MEDIUM:
        base = 7
        return {k: min(15, base + (student_index + i) % 4) for i, k in enumerate(TEST3_SCORE_KEYS)}
    elif result_type == ResultType.LOW:
        base = 3
        return {k: min(15, base + (student_index + i) % 3) for i, k in enumerate(TEST3_SCORE_KEYS)}
    elif result_type == ResultType.MIXED:
        high = student_index % 2 == 0
        base = 11 if high else 4
        return {k: min(15, base + (i % 3)) for i, k in enumerate(TEST3_SCORE_KEYS)}
    else:
        which = student_index % 4
        base = [12, 7, 4, 10][which]
        return {k: min(15, base + (i % 3)) for i, k in enumerate(TEST3_SCORE_KEYS)}


def _delete_demo_student_psychometric_only(user_id):
    """Remove only psychometric / post-matric attempt data for one user (not the User row)."""
    uid = int(user_id)
    TestTopCategories.objects.filter(user_id=uid).delete()
    TestResult.objects.filter(session__user_id=uid).delete()
    UserResponse.objects.filter(session__user_id=uid).delete()
    SectionSession.objects.filter(session__user_id=uid).delete()
    TestSession.objects.filter(user_id=uid).delete()
    TestCompletion.objects.filter(user_id=uid).delete()
    Results.objects.filter(user_id=uid).delete()


def _hexaco_post_matric_result_data(result_type, seed_index):
    """
    HEXACO dimension scores for post-matric Personality Assessment TestResult.

    Combined report UI (pdf-results.js) treats raw totals as out of 50 per dimension
    and maps bands: low 1–17, medium 18–33, high 34+.
    """
    letters = ["H", "E", "X", "A", "C", "O"]

    if result_type == ResultType.HIGH:
        vals = {L: 38 + ((seed_index + i * 2) % 9) for i, L in enumerate(letters)}
        vals["C"] = min(49, vals.get("C", 40) + 2)
    elif result_type == ResultType.LOW:
        vals = {L: 10 + ((seed_index + i) % 6) for i, L in enumerate(letters)}
    elif result_type == ResultType.MEDIUM:
        vals = {L: 22 + ((seed_index + i * 3) % 9) for i, L in enumerate(letters)}
    elif result_type == ResultType.MIXED:
        if seed_index % 2 == 0:
            vals = {"H": 40, "E": 14, "X": 42, "A": 16, "C": 44, "O": 12}
        else:
            vals = {"H": 15, "E": 38, "X": 14, "A": 36, "C": 12, "O": 40}
    else:
        vals = {L: 20 + ((seed_index + i) % 8) for i, L in enumerate(letters)}
        which = seed_index % 6
        for j in range(3):
            vals[letters[(which + j) % 6]] = min(48, 36 + j * 3)
    return {k: {"score": int(min(50, max(0, v)))} for k, v in vals.items()}


def _hexaco_top_three_codes(result_data):
    pairs = []
    for code, raw in (result_data or {}).items():
        if isinstance(raw, dict) and "score" in raw:
            pairs.append((code, int(raw["score"])))
        elif isinstance(raw, (int, float)):
            pairs.append((code, int(raw)))
    pairs.sort(key=lambda x: -x[1])
    top = [p[0] for p in pairs[:3]]
    return top if len(top) == 3 else ["H", "E", "X"]


def _riasec_post_matric_letter_scores(result_type, seed_index):
    """
    Per-letter RIASEC scores for post-matric career chart (pdf-results.js assumes max ~25 per letter).
    Do not reuse matric test2 scores (0–36); they break HIGH/MEDIUM scaling in the combined report.
    """
    letters = ["R", "I", "A", "S", "E", "C"]

    def spread(low, high):
        span = max(1, high - low)
        return {
            L: min(24, max(1, low + ((seed_index + i * 5) % (span + 1))))
            for i, L in enumerate(letters)
        }

    if result_type == ResultType.HIGH:
        return spread(18, 24)
    if result_type == ResultType.LOW:
        return spread(3, 9)
    if result_type == ResultType.MEDIUM:
        return spread(11, 17)
    if result_type == ResultType.MIXED:
        if seed_index % 2 == 0:
            vals = {"R": 21, "I": 20, "A": 9, "S": 8, "E": 10, "C": 7}
        else:
            vals = {"R": 8, "I": 9, "S": 20, "E": 21, "A": 10, "C": 7}
        return vals
    which = seed_index % 6
    vals = {L: 10 + ((seed_index + i) % 6) for i, L in enumerate(letters)}
    for j in range(3):
        vals[letters[(which + j) % 6]] = 20 - j
    return vals


def _career_interest_post_matric_result_data(result_type, seed_index):
    """RIASEC R/I/A/S/E/C scores for Career Interest Inventory (combined report chart scale)."""
    scores = _riasec_post_matric_letter_scores(result_type, seed_index)
    return {L: {"score": int(scores[L])} for L in ["R", "I", "A", "S", "E", "C"]}


def _riasec_code_for_top_three(result_data):
    pairs = []
    for letter, raw in (result_data or {}).items():
        sc = raw.get("score") if isinstance(raw, dict) else raw
        if sc is not None:
            try:
                pairs.append((letter, int(sc)))
            except (TypeError, ValueError):
                pass
    pairs.sort(key=lambda x: -x[1])
    return "".join(p[0] for p in pairs[:3]) if len(pairs) >= 3 else "RIA"


def _aptitude_post_matric_result_data(result_type, seed_index):
    base = {
        "Abstract Reasoning": 11,
        "Numerical Reasoning": 10,
        "Logical Reasoning": 9,
        "Language & Verbal Reasoning": 10,
        "Mechanical Reasoning": 7,
        "Spatial Reasoning": 8,
        "Clerical Speed & Accuracy": 9,
    }
    bump = (seed_index % 3) - 1
    mult = 1.0
    if result_type == ResultType.HIGH:
        mult = 1.15
    elif result_type == ResultType.LOW:
        # populateAverageCards uses (score/15)*100; keep most sections under 40% for clear "Below" demos
        mult = 0.48
    elif result_type == ResultType.MEDIUM:
        mult = 0.78
    elif result_type == ResultType.MIXED:
        mult = 1.05 if seed_index % 2 == 0 else 0.85
    out = {}
    for i, (k, v) in enumerate(base.items()):
        s = int(round((v + bump + (i % 2)) * mult))
        out[k] = {"score": max(1, min(15, s))}
    return out


def _aptitude_bands_json_from_result_data(result_data):
    """
    Build TestTopCategories.high_category JSON for aptitude (band -> subtest names).

    Must match static/js/pdf-results.js populateAverageCards():
    accuracy = (score / 15) * 100 with >= 70 Above, >= 40 Average, else Below.
    """
    import json

    above, mid, below = [], [], []
    for k, raw in (result_data or {}).items():
        sc = raw.get("score") if isinstance(raw, dict) else raw
        if sc is None:
            continue
        try:
            score = int(sc)
        except (TypeError, ValueError):
            continue
        acc = (score / 15.0) * 100.0
        if acc >= 70:
            above.append(k)
        elif acc >= 40:
            mid.append(k)
        else:
            below.append(k)

    if not (above or mid or below):
        return json.dumps(
            {
                "Above Average": ["Abstract Reasoning", "Numerical Reasoning"],
                "Average": ["Logical Reasoning"],
                "Below Average": ["Mechanical Reasoning", "Spatial Reasoning"],
            }
        )
    return json.dumps(
        {
            "Above Average": above,
            "Average": mid,
            "Below Average": below,
        }
    )


def _motivation_counts_for_result_type(result_type, seed_index):
    ach = 12 + (seed_index % 6)
    pwr = 7 + (seed_index % 5)
    aff = 6 + (seed_index % 4)
    if result_type == ResultType.HIGH:
        ach, pwr, aff = ach + 4, pwr + 3, aff + 2
    elif result_type == ResultType.LOW:
        ach, pwr, aff = max(3, ach - 4), max(3, pwr - 3), max(3, aff - 2)
    elif result_type == ResultType.MEDIUM:
        ach, pwr, aff = ach + 1, pwr, aff
    elif result_type == ResultType.MIXED:
        if seed_index % 2 == 0:
            ach += 3
        else:
            pwr += 3
    return {"Achievement": ach, "Power": pwr, "Affiliation": aff}


def _apply_class10_psychometric_for_user(user, student_index, result_type, psychometric_tests_complete):
    """Recreate matric (test1/test2/test3) Results + optional TestCompletion for one demo student."""
    TestCompletion.objects.filter(user=user).delete()
    Results.objects.filter(user=user, test_paper__in=["test1", "test2", "test3"]).delete()
    if psychometric_tests_complete:
        tc, _ = TestCompletion.objects.get_or_create(user=user)
        tc.test1_complete = True
        tc.test2_complete = True
        tc.test3_complete = True
        tc.numerical_complete = True
        tc.verbal_complete = True
        tc.logical_complete = True
        tc.emotional_complete = True
        tc.machanical_complete = True
        tc.language_complete = True
        tc.spatial_complete = True
        tc.save()
    personality_results = _personality_results_for_result_type(result_type, student_index)
    Results.objects.update_or_create(
        user=user,
        test_paper="test1",
        defaults={"results": personality_results, "scores": {}, "selected_answers": {}},
    )
    interest_scores = _interest_scores_for_result_type(result_type, student_index)
    Results.objects.update_or_create(
        user=user,
        test_paper="test2",
        defaults={"scores": interest_scores, "results": {}, "selected_answers": {}},
    )
    intelligence_scores = _intelligence_scores_for_result_type(result_type, student_index)
    Results.objects.update_or_create(
        user=user,
        test_paper="test3",
        defaults={"scores": intelligence_scores, "results": {}, "selected_answers": {}},
    )


def _get_or_create_class_sections():
    # Be tolerant to existing DB rows like "class 10" vs "Class 10"
    c10 = ClassAndSection.objects.filter(class_and_section__iexact="Class 10").first()
    if c10 is None:
        c10 = ClassAndSection.objects.create(class_and_section="Class 10", stream="General")

    c12 = ClassAndSection.objects.filter(class_and_section__iexact="Class 12").first()
    if c12 is None:
        c12 = ClassAndSection.objects.create(class_and_section="Class 12", stream="General")
    return c10, c12


def _create_completed_post_matric_tests_for_user(user, *, seed_index=0, result_type=None):
    """
    Class 12 flow uses app_post_matric models (TestSession/TestResult/SectionSession/TestTopCategories).

    DB test order (see app_post_matric.Test): 1=Personality, 2=Motivation, 3=Career Interest, 4=Aptitude.

    Populates shapes expected by CombinedReport + combined_report.html charts:
    - TestResult.result_data / category_counts (client-side test_results_json)
    - TestTopCategories (server-side RIASEC / motivation / aptitude bands)
    - Non-zero session duration (total minutes in report)
    """
    import json
    from datetime import timedelta

    from django.utils import timezone

    if result_type is None:
        result_type = ResultType.HIGH

    now = timezone.now()
    # Clear prior top-category rows (not tied to session cascade).
    TestTopCategories.objects.filter(user=user).delete()

    # Valid RIASEC keys from static/data/interest_riasec.json "code" + merged career path JSON.
    riasec_codes = ["RIA", "RIS", "RIE", "RIC", "RAS", "RAE"]
    # TestTopCategories for server-side motivation narrative (Motivation_Career.json domains).
    motivation_domains = ["Business", "Engineer", "Social", "Medical"]
    motivation_primary = motivation_domains[seed_index % len(motivation_domains)]
    motivation_secondary = motivation_domains[(seed_index + 1) % len(motivation_domains)]

    # DB pk order: 1 Personality, 2 Motivation, 3 Career, 4 Aptitude
    for test_pk in (1, 2, 3, 4):
        test = Test.objects.filter(pk=test_pk).first()
        if not test:
            continue

        TestSession.objects.filter(user=user, test_id=test_pk).delete()

        duration_minutes = 28 + (seed_index % 8) + test_pk * 6
        start_time = now - timedelta(minutes=duration_minutes)
        session = TestSession.objects.create(
            user=user,
            test=test,
            start_time=start_time,
            end_time=now,
            is_completed=True,
            attempt_count=1,
        )

        try:
            for section in test.sections.all():
                SectionSession.objects.update_or_create(
                    session=session,
                    section=section,
                    defaults={
                        "start_time": start_time,
                        "end_time": now,
                        "is_completed": True,
                    },
                )
        except Exception:
            pass

        title = (test.title or "").strip()
        result_data = {}
        category_counts = {}
        ttc_high = None
        ttc_low = ""

        if title == "Personality Assessment":
            result_data = _hexaco_post_matric_result_data(result_type, seed_index)
            ttc_high = json.dumps(_hexaco_top_three_codes(result_data))
            pairs = []
            for code, raw in result_data.items():
                sc = raw.get("score") if isinstance(raw, dict) else raw
                if sc is not None:
                    try:
                        pairs.append((code, int(sc)))
                    except (TypeError, ValueError):
                        pass
            pairs.sort(key=lambda x: x[1])
            ttc_low = pairs[0][0] if pairs else "O"
        elif title == "Motivation Assessment":
            # CombinedReport builds test_results_json from TestResult only when result_data is
            # truthy; otherwise it aggregates UserResponse rows into Achievement/Power/Affiliation
            # (see app_post_matric.views.CombinedReport). Demo users have no UserResponse rows, so
            # we must store non-zero Achievement/Power/Affiliation here (do not change report code).
            counts = _motivation_counts_for_result_type(result_type, seed_index)
            result_data = dict(counts)
            category_counts = dict(counts)
            ttc_high = motivation_primary
            ttc_low = motivation_secondary
        elif title == "Career Interest Inventory":
            result_data = _career_interest_post_matric_result_data(result_type, seed_index)
            career_try = _riasec_code_for_top_three(result_data)
            career_code = (
                career_try
                if career_try in riasec_codes
                else riasec_codes[seed_index % len(riasec_codes)]
            )
            ttc_high = career_code
            low_pairs = []
            for letter, raw in result_data.items():
                sc = raw.get("score") if isinstance(raw, dict) else raw
                if sc is not None:
                    try:
                        low_pairs.append((letter, int(sc)))
                    except (TypeError, ValueError):
                        pass
            low_pairs.sort(key=lambda x: x[1])
            ttc_low = low_pairs[0][0] if low_pairs else "S"
        elif title == "Aptitude Assessment":
            result_data = _aptitude_post_matric_result_data(result_type, seed_index)
            ttc_high = _aptitude_bands_json_from_result_data(result_data)
            ttc_low = ""

        TestResult.objects.update_or_create(
            session=session,
            defaults={
                "score": float(68 + (seed_index % 12) + test_pk * 2),
                "grade": "A",
                "feedback": "Demo result (system-generated)",
                "result_data": result_data,
                "category_counts": category_counts,
            },
        )

        if ttc_high is not None:
            TestTopCategories.objects.create(
                user=user,
                test_paper=test,
                high_category=ttc_high,
                low_category=ttc_low or "",
            )


def _demo_student_matric_grade(user):
    """
    Return canonical grade string for psychometric routing ('10' or '12'), or None.
    Prefer UserProfile.grade; fall back to StudentManagement.class_and_section label.
    """
    import re

    prof = UserProfile.objects.filter(user=user).first()
    if prof and prof.grade:
        g = str(prof.grade).strip()
        g = re.sub(r"^class\s*", "", g, flags=re.I).strip()
        if g.isdigit():
            return g
    sm = (
        StudentManagement.objects.filter(student=user)
        .select_related("class_and_section")
        .first()
    )
    if sm and sm.class_and_section:
        raw = (sm.class_and_section.class_and_section or "").strip()
        m = re.search(r"(\d+)", raw)
        if m:
            return m.group(1)
    return None


def reseed_demo_student_psychometric(student_user_id, result_type, config=None):
    """
    Staff/admin utility: wipe psychometric data for one system-demo student and recreate it
    using the given ResultType. Class 10 -> app Results/TestCompletion; Class 12 -> post-matric sessions.
    Does not recreate users, institute, or parent links.
    """
    if config is None:
        config = DemoDatasetConfig.get_singleton()

    allowed = {c[0] for c in ResultType.CHOICES}
    if result_type not in allowed:
        raise ValueError("Invalid result type")

    sid = int(student_user_id)
    sids = list(config.student_user_ids or [])
    if sid not in sids:
        raise ValueError("That user id is not in the configured demo student list")

    user = User.objects.filter(id=sid).first()
    if not user:
        raise ValueError("User not found")
    if not getattr(user, "is_system_demo", False):
        raise ValueError("Only system demo students can be reseeded this way")
    if user.user_type != choices.UserType.STUDENT:
        raise ValueError("Only student accounts can be reseeded")

    try:
        seed_index = sids.index(sid)
    except ValueError:
        seed_index = 0

    grade = _demo_student_matric_grade(user)
    if grade is None:
        raise ValueError("Could not determine class (set UserProfile.grade or StudentManagement class)")

    g_norm = "".join(ch for ch in str(grade) if ch.isdigit())
    g_int = int(g_norm) if g_norm else 0
    is_class_12 = g_int >= 12

    with transaction.atomic():
        _delete_demo_student_psychometric_only(sid)
        if is_class_12:
            _create_completed_post_matric_tests_for_user(
                user, seed_index=seed_index, result_type=result_type
            )
            if config.psychometric_tests_complete:
                tc, _ = TestCompletion.objects.get_or_create(user=user)
                tc.test1_complete = True
                tc.test2_complete = True
                tc.test3_complete = True
                tc.numerical_complete = True
                tc.verbal_complete = True
                tc.logical_complete = True
                tc.emotional_complete = True
                tc.machanical_complete = True
                tc.language_complete = True
                tc.spatial_complete = True
                tc.save()
        else:
            _apply_class10_psychometric_for_user(
                user,
                seed_index,
                result_type,
                config.psychometric_tests_complete,
            )

    return {"user_id": sid, "grade": grade, "result_type": result_type}


def create_demo_dataset(config=None):
    """
    Create the fixed demo dataset from config: 1 institute + institute user,
    num_students_class_10 + num_students_class_12 students, 1 parent, links,
    and psychometric results for the first num_students_with_psychometric students
    (with completion flags if psychometric_tests_complete). Uses result_type for scores.
    Sets is_system_demo=True on every created User and Institute.
    Returns the created IDs for storing in DemoDatasetConfig.
    """
    if config is None:
        config = DemoDatasetConfig.get_singleton()

    n10 = max(0, config.num_students_class_10)
    n12 = max(0, config.num_students_class_12)
    total_students = n10 + n12
    if total_students == 0:
        total_students = 10
        n10, n12 = 5, 5
    n10_psych = min(getattr(config, "num_psychometric_class_10", 0), n10)
    n12_psych = min(getattr(config, "num_psychometric_class_12", 0), n12)
    result_type_10 = getattr(config, "result_type_class_10", None) or ResultType.VARIED
    result_type_12 = getattr(config, "result_type_class_12", None) or ResultType.HIGH

    c10, c12 = _get_or_create_class_sections()

    with transaction.atomic():
        _delete_system_demo_data()

        # 1. Institute user
        inst_user = User(
            email=f"demo_institute@{DEMO_EMAIL_DOMAIN}",
            name="Demo Institute",
            user_type=choices.UserType.INSTITUTE,
            is_demo_account=True,
            is_system_demo=True,
        )
        inst_user.set_password(DEMO_PASSWORD)
        inst_user.save()

        # 2. Institute (credit_counts >= total students)
        institute = Institute(
            name="Demo Institute",
            slug=INSTITUTE_SLUG,
            created_by=inst_user,
            is_demo_institute=True,
            is_system_demo=True,
            institute_status=choices.InstituteStatus.APPROVED,
            credit_counts=max(total_students, 10),
        )
        institute.save()

        # 3. Students: first n10 Class 10, then n12 Class 12 (each with unique demo mobile)
        student_users = []
        for i in range(1, total_students + 1):
            if i <= n10:
                grade_class, grade_label = c10, "10"
            else:
                grade_class, grade_label = c12, "12"
            # Unique 10-digit demo mobile per student (e.g. 9999900001, 9999900002, ...)
            demo_mobile = str(9999900000 + i)
            stu = User(
                email=f"demo_student_{i}@{DEMO_EMAIL_DOMAIN}",
                name=f"Demo Student {i}",
                user_type=choices.UserType.STUDENT,
                mobile=demo_mobile,
                is_demo_account=True,
                is_system_demo=True,
            )
            stu.set_password(DEMO_PASSWORD)
            stu.save()
            UserProfile.objects.get_or_create(
                user=stu,
                defaults={"grade": grade_label, "schoolname": "Demo School"},
            )
            StudentManagement.objects.create(
                institute=institute,
                student=stu,
                class_and_section=grade_class,
            )
            student_users.append(stu)

        # 4. Parent
        parent = User(
            email=f"demo_parent@{DEMO_EMAIL_DOMAIN}",
            name="Demo Parent",
            user_type=choices.UserType.PARENT,
            is_demo_account=True,
            is_system_demo=True,
        )
        parent.set_password(DEMO_PASSWORD)
        parent.save()

        # 5. ParentStudentLink
        for stu in student_users:
            ParentStudentLink.objects.get_or_create(parent=parent, student=stu)

        # Demo counselor is created only via setup_demo_counselor_data() (separate admin action).

        # 6. Psychometric: first n10_psych Class 10 students, then n12_psych Class 12 students
        def gets_psychometric(idx):
            if idx < n10:
                return idx < n10_psych
            return (idx - n10) < n12_psych

        for idx, stu in enumerate(student_users):
            if not gets_psychometric(idx):
                continue
            result_type = result_type_10 if idx < n10 else result_type_12
            # Class 10 (matric) uses app.models Results/TestCompletion.
            # Class 12 (post-matric) dashboards use app_post_matric TestSession/TestResult.
            if config.psychometric_tests_complete and idx >= n10:
                _create_completed_post_matric_tests_for_user(
                    stu, seed_index=idx, result_type=result_type_12
                )
                # Also mark old-style flags as complete for compatibility with any shared UI pieces.
                tc, _ = TestCompletion.objects.get_or_create(user=stu)
                tc.test1_complete = True
                tc.test2_complete = True
                tc.test3_complete = True
                tc.numerical_complete = True
                tc.verbal_complete = True
                tc.logical_complete = True
                tc.emotional_complete = True
                tc.machanical_complete = True
                tc.language_complete = True
                tc.spatial_complete = True
                tc.save()
                continue

            if config.psychometric_tests_complete:
                tc, _ = TestCompletion.objects.get_or_create(
                    user=stu,
                    defaults={
                        "test1_complete": True,
                        "test2_complete": True,
                        "test3_complete": True,
                        "numerical_complete": True,
                        "verbal_complete": True,
                        "logical_complete": True,
                        "emotional_complete": True,
                        "machanical_complete": True,
                        "language_complete": True,
                        "spatial_complete": True,
                    },
                )
                tc.test1_complete = True
                tc.test2_complete = True
                tc.test3_complete = True
                tc.numerical_complete = True
                tc.verbal_complete = True
                tc.logical_complete = True
                tc.emotional_complete = True
                tc.machanical_complete = True
                tc.language_complete = True
                tc.spatial_complete = True
                tc.save()
            # Test1 (Personality): results = RIASEC percentages for report + gernate_graph
            personality_results = _personality_results_for_result_type(result_type, idx)
            Results.objects.get_or_create(
                user=stu,
                test_paper="test1",
                defaults={
                    "results": personality_results,
                    "scores": {},
                    "selected_answers": {},
                },
            )
            # Test2 (Interest): scores = RIASEC scores (0-39) for report + gernate_graph
            interest_scores = _interest_scores_for_result_type(result_type, idx)
            Results.objects.get_or_create(
                user=stu,
                test_paper="test2",
                defaults={
                    "scores": interest_scores,
                    "results": {},
                    "selected_answers": {},
                },
            )
            # Test3 (Intelligence): scores = *_score keys (0-15) for report + gernate_graph
            intelligence_scores = _intelligence_scores_for_result_type(result_type, idx)
            Results.objects.get_or_create(
                user=stu,
                test_paper="test3",
                defaults={
                    "scores": intelligence_scores,
                    "results": {},
                    "selected_answers": {},
                },
            )

        # Save run output to config
        config.institute_id = institute.id
        config.institute_user_id = inst_user.id
        config.parent_user_id = parent.id
        config.student_user_ids = [u.id for u in student_users]
        config.save(
            update_fields=[
                "institute_id",
                "institute_user_id",
                "parent_user_id",
                "student_user_ids",
                "updated_at",
            ]
        )

        return {
            "institute_id": institute.id,
            "institute_user_id": inst_user.id,
            "parent_user_id": parent.id,
            "student_user_ids": [u.id for u in student_users],
        }


def _qs_hard_delete(qs):
    """Physically remove rows (soft-delete managers expose .hard_delete())."""
    if hasattr(qs, "hard_delete"):
        return qs.hard_delete()
    return qs.delete()


def _delete_skilllab_for_users(demo_user_ids):
    """Skill Lab enrollment + progress for demo users (payments, chapters, quizzes, certs)."""
    if not demo_user_ids:
        return
    try:
        from skilllab.models import (
            SkilllabCoursePayment,
            SkillLabCourseProgress,
            SkillLabCourseProgressSummary,
            SkillLabCourseResume,
            SkillLabWorksheetProgress,
            SkillLabMCQAttempt,
            SkillLabUserHighlight,
            SkillLabUserNote,
            SkillLabUserBookmark,
            SkillLabCertification,
        )
    except Exception:
        return

    for Model in (
        SkillLabCourseProgress,
        SkillLabCourseProgressSummary,
        SkillLabCourseResume,
        SkillLabWorksheetProgress,
        SkillLabMCQAttempt,
        SkillLabUserHighlight,
        SkillLabUserNote,
        SkillLabUserBookmark,
        SkillLabCertification,
    ):
        _qs_hard_delete(Model.objects.complete().filter(user_id__in=demo_user_ids))

    for pay in SkilllabCoursePayment.objects.complete().filter(user_id__in=demo_user_ids):
        pay.delete(hard_delete=True)


def _delete_psychometric_packages_and_payments_for_users(demo_user_ids):
    """
    Single-package personality assignments/entitlements + legacy PsychometricTestPayment /
    CentralTestCandidate (and CandidateTest / PsychometricTestResult).
    """
    if not demo_user_ids:
        return
    try:
        from django.db.models import Q
        from psychometric_tests.models import (
            StudentAssessmentEntitlement,
            StudentPackageAssignment,
            PsychometricTestPayment,
            CentralTestCandidate,
            CandidateTest,
            PsychometricTestResult,
        )
    except Exception:
        return

    _qs_hard_delete(
        StudentAssessmentEntitlement.objects.complete().filter(user_id__in=demo_user_ids)
    )
    _qs_hard_delete(
        StudentPackageAssignment.objects.complete().filter(student_id__in=demo_user_ids)
    )

    payment_ids = list(
        PsychometricTestPayment.objects.complete()
        .filter(user_id__in=demo_user_ids)
        .values_list("id", flat=True)
    )
    ctc_ids = list(
        CentralTestCandidate.objects.complete()
        .filter(user_id__in=demo_user_ids)
        .values_list("id", flat=True)
    )
    ct_ids = list(
        CandidateTest.objects.complete()
        .filter(
            Q(pyschometric_test_payment_id__in=payment_ids)
            | Q(central_test_candidate_id__in=ctc_ids)
        )
        .values_list("id", flat=True)
    )
    if ct_ids:
        _qs_hard_delete(
            PsychometricTestResult.objects.complete().filter(assessment_id__in=ct_ids)
        )
        _qs_hard_delete(CandidateTest.objects.complete().filter(id__in=ct_ids))

    for pay in PsychometricTestPayment.objects.complete().filter(user_id__in=demo_user_ids):
        pay.delete(hard_delete=True)
    for ctc in CentralTestCandidate.objects.complete().filter(user_id__in=demo_user_ids):
        ctc.delete(hard_delete=True)


def _delete_analytics_for_users(demo_user_ids):
    """Hard-delete analytics tracking rows (FK is SET_NULL — User delete alone leaves orphans)."""
    if not demo_user_ids:
        return
    try:
        from user_analytics.models import (
            UserActivity,
            UserEvent,
            UserJourney,
            Lead,
            GA4Session,
        )
    except Exception:
        return

    for Model in (UserActivity, UserEvent, UserJourney, Lead, GA4Session):
        _qs_hard_delete(Model.objects.complete().filter(user_id__in=demo_user_ids))


def _delete_misc_student_extras(demo_user_ids, demo_institute_ids):
    """Counseling follow-ups, career shortlists, resumes if present."""
    if demo_user_ids:
        try:
            from careers.models import CareerShortlist

            _qs_hard_delete(
                CareerShortlist.objects.complete().filter(user_id__in=demo_user_ids)
            )
        except Exception:
            pass
        try:
            from users.models import UserResume, UserFolder, UserNote, UserCalender

            for Model in (UserResume, UserFolder, UserNote, UserCalender):
                _qs_hard_delete(Model.objects.complete().filter(user_id__in=demo_user_ids))
        except Exception:
            pass

    try:
        from django.db.models import Q
        from counselor.models import FollowUpStatus
        from institute.models import StudentManagement

        sm_filter = Q(student_id__in=demo_user_ids)
        if demo_institute_ids:
            sm_filter |= Q(institute_id__in=demo_institute_ids)
        sm_ids = list(
            StudentManagement.objects.complete().filter(sm_filter).values_list("id", flat=True)
        )
        if sm_ids:
            _qs_hard_delete(
                FollowUpStatus.objects.complete().filter(student_id__in=sm_ids)
            )
    except Exception:
        pass


def _delete_system_demo_data():
    """Delete all data that has is_system_demo=True (and related FKs). Uses hard_delete for User and Institute so they can be recreated."""
    demo_user_ids = list(
        User.objects.complete().filter(is_system_demo=True).values_list("id", flat=True)
    )
    demo_institute_ids = list(
        Institute.objects.complete()
        .filter(is_system_demo=True)
        .values_list("id", flat=True)
    )

    if not demo_user_ids and not demo_institute_ids:
        return

    # Skill Lab + single-package personality + analytics (must run before User hard_delete)
    _delete_skilllab_for_users(demo_user_ids)
    _delete_psychometric_packages_and_payments_for_users(demo_user_ids)
    _delete_analytics_for_users(demo_user_ids)
    _delete_misc_student_extras(demo_user_ids, demo_institute_ids)

    # Counselor course: payments (soft-delete model — hard_delete), progress, profile
    for pay in Payment.objects.complete().filter(user_id__in=demo_user_ids):
        pay.delete(hard_delete=True)
    VideoProgress.objects.filter(user_id__in=demo_user_ids).delete()
    QuizResults.objects.filter(user_id__in=demo_user_ids).delete()
    CounselorCertification.objects.filter(user_id__in=demo_user_ids).delete()
    Counselor.objects.filter(coun_user_id__in=demo_user_ids).delete()

    # Post-matric: TestResult -> TestSession; SectionSession -> TestSession; UserResponse -> section_session/session
    TestTopCategories.objects.filter(user_id__in=demo_user_ids).delete()
    TestResult.objects.filter(session__user_id__in=demo_user_ids).delete()
    UserResponse.objects.filter(session__user_id__in=demo_user_ids).delete()
    SectionSession.objects.filter(session__user_id__in=demo_user_ids).delete()
    TestSession.objects.filter(user_id__in=demo_user_ids).delete()

    # Psychometric (legacy app Results / TestCompletion)
    TestCompletion.objects.filter(user_id__in=demo_user_ids).delete()
    Results.objects.filter(user_id__in=demo_user_ids).delete()

    # ParentStudentLink, StudentManagement
    ParentStudentLink.objects.filter(parent_id__in=demo_user_ids).delete()
    ParentStudentLink.objects.filter(student_id__in=demo_user_ids).delete()
    StudentManagement.objects.filter(student_id__in=demo_user_ids).delete()
    StudentManagement.objects.filter(institute_id__in=demo_institute_ids).delete()

    # UserProfile
    UserProfile.objects.filter(user_id__in=demo_user_ids).delete()

    # Users and Institutes: hard_delete so rows are removed and can be recreated with same email/slug
    for u in User.objects.complete().filter(id__in=demo_user_ids):
        u.delete(hard_delete=True)
    for inst in Institute.objects.complete().filter(id__in=demo_institute_ids):
        inst.delete(hard_delete=True)


def reset_demo_data():
    """
    Delete only system-demo data, then recreate the fixed dataset.
    """
    _delete_system_demo_data()
    return create_demo_dataset()


def _delete_demo_counselor_only():
    """
    Remove only the demo counselor account (by email). Does not touch student/institute demo.
    Uses is_demo_account + counselor email; not is_system_demo so student reset does not delete this user.
    """
    u = User.objects.complete().filter(email=DEMO_COUNSELOR_EMAIL).first()
    if not u:
        return
    uid = u.id
    for pay in Payment.objects.complete().filter(user_id=uid):
        pay.delete(hard_delete=True)
    VideoProgress.objects.filter(user_id=uid).delete()
    QuizResults.objects.filter(user_id=uid).delete()
    CounselorCertification.objects.filter(user_id=uid).delete()
    Counselor.objects.filter(coun_user_id=uid).delete()
    u.delete(hard_delete=True)


def setup_demo_counselor_data(config=None):
    """
    Create demo counselor user + Counselor profile + successful payment + course progress.
    Separate from student demo data. Links to demo institute if it exists (slug demo-institute).
    """
    if config is None:
        config = DemoDatasetConfig.get_singleton()

    course_c = CounselorCourse.objects.first()
    if not course_c:
        raise ValueError(
            "No CounselorCourse found. Create a course in admin before setting up demo counselor."
        )

    institute = Institute.objects.complete().filter(slug=INSTITUTE_SLUG).first()

    with transaction.atomic():
        _delete_demo_counselor_only()

        cw = User(
            email=DEMO_COUNSELOR_EMAIL,
            name="Demo Counselor",
            user_type=choices.UserType.COUNSELOR,
            is_demo_account=True,
            is_system_demo=False,
        )
        cw.set_password(DEMO_PASSWORD)
        cw.save()

        counselor_obj = Counselor.objects.create(
            counselor_name="Demo Counselor",
            coun_user=cw,
            counselor_admin=institute,
        )
        # Assign demo students (if present) to the demo counselor so counselor dashboards show non-zero students.
        try:
            from institute.models import StudentManagement

            sids = list(getattr(config, "student_user_ids", []) or [])
            if institute and sids:
                sms = list(
                    StudentManagement.objects.filter(institute=institute, student_id__in=sids).values_list("id", flat=True)
                )
                if sms:
                    counselor_obj.students.set(sms)
        except Exception:
            pass
        create_counselor_course_payment(cw, course_c)
        state = getattr(config, "demo_counselor_course_state", None) or DemoCounselorCourseState.PASSED
        apply_demo_counselor_course_state(cw, state)

        config.counselor_user_id = cw.id
        config.counselor_id = counselor_obj.id
        config.save(
            update_fields=["counselor_user_id", "counselor_id", "updated_at"]
        )

    return {
        "counselor_user_id": cw.id,
        "counselor_id": counselor_obj.id,
    }


def remove_demo_counselor_data():
    """Remove demo counselor only; clear counselor IDs in config."""
    _delete_demo_counselor_only()
    config = DemoDatasetConfig.get_singleton()
    config.counselor_user_id = None
    config.counselor_id = None
    config.save(update_fields=["counselor_user_id", "counselor_id", "updated_at"])


def reset_demo_counselor_data():
    """Delete and recreate demo counselor from current config."""
    return setup_demo_counselor_data()


def remove_demo_data():
    """
    Delete only system-flagged demo data (no recreate). Clears the config's
    last-run IDs so the admin shows no demo data present.
    """
    _delete_system_demo_data()
    config = DemoDatasetConfig.get_singleton()
    config.institute_id = None
    config.institute_user_id = None
    config.parent_user_id = None
    config.student_user_ids = []
    # Demo counselor is managed separately; do not clear counselor_user_id / counselor_id here.
    config.save(
        update_fields=[
            "institute_id",
            "institute_user_id",
            "parent_user_id",
            "student_user_ids",
            "updated_at",
        ]
    )
