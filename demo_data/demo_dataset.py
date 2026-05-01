"""
Shared logic for creating the fixed demo dataset.
Only this module sets is_system_demo on User and Institute.
Uses DemoDatasetConfig (singleton) for: student counts per class, psychometric options, result type.
"""
from django.db import transaction

from core import choices
from users.models import User, UserProfile, ParentStudentLink
from institute.models import Institute, ClassAndSection, StudentManagement
from app.models import TestCompletion, Results
from app_post_matric.models import (
    TestSession,
    TestResult,
    SectionSession,
    UserResponse,
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


def _get_or_create_class_sections():
    c10, _ = ClassAndSection.objects.get_or_create(
        class_and_section="Class 10",
        defaults={"stream": "General"},
    )
    c12, _ = ClassAndSection.objects.get_or_create(
        class_and_section="Class 12",
        defaults={"stream": "General"},
    )
    return c10, c12


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
        inst_user = User.objects.create_user(
            email=f"demo_institute@{DEMO_EMAIL_DOMAIN}",
            name="Demo Institute",
            password=DEMO_PASSWORD,
        )
        inst_user.user_type = choices.UserType.INSTITUTE
        inst_user.is_demo_account = True
        inst_user.is_system_demo = True
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
                grade_class, grade_label = c10, "Class 10"
            else:
                grade_class, grade_label = c12, "Class 12"
            # Unique 10-digit demo mobile per student (e.g. 9999900001, 9999900002, ...)
            demo_mobile = str(9999900000 + i)
            stu = User.objects.create_user(
                email=f"demo_student_{i}@{DEMO_EMAIL_DOMAIN}",
                name=f"Demo Student {i}",
                password=DEMO_PASSWORD,
            )
            stu.user_type = choices.UserType.STUDENT
            stu.mobile = demo_mobile
            stu.is_demo_account = True
            stu.is_system_demo = True
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
        parent = User.objects.create_user(
            email=f"demo_parent@{DEMO_EMAIL_DOMAIN}",
            name="Demo Parent",
            password=DEMO_PASSWORD,
        )
        parent.user_type = choices.UserType.PARENT
        parent.is_demo_account = True
        parent.is_system_demo = True
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

    # Counselor course: payments (soft-delete model — hard_delete), progress, profile
    for pay in Payment.objects.complete().filter(user_id__in=demo_user_ids):
        pay.delete(hard_delete=True)
    VideoProgress.objects.filter(user_id__in=demo_user_ids).delete()
    QuizResults.objects.filter(user_id__in=demo_user_ids).delete()
    CounselorCertification.objects.filter(user_id__in=demo_user_ids).delete()
    Counselor.objects.filter(coun_user_id__in=demo_user_ids).delete()

    # Post-matric: TestResult -> TestSession; SectionSession -> TestSession; UserResponse -> section_session/session
    TestResult.objects.filter(session__user_id__in=demo_user_ids).delete()
    UserResponse.objects.filter(session__user_id__in=demo_user_ids).delete()
    SectionSession.objects.filter(session__user_id__in=demo_user_ids).delete()
    TestSession.objects.filter(user_id__in=demo_user_ids).delete()

    # Psychometric
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

        cw = User.objects.create_user(
            email=DEMO_COUNSELOR_EMAIL,
            name="Demo Counselor",
            password=DEMO_PASSWORD,
        )
        cw.user_type = choices.UserType.COUNSELOR
        cw.is_demo_account = True
        cw.is_system_demo = False
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
