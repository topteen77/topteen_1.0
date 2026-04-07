from datetime import datetime, date, timedelta
import json
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render
from django.core.paginator import Paginator
from app.models import Answer, Results
from institute.filters import StudentFilter
from institute.models import ClassAndSection, Institute, StudentManagement
from .models import (
    Counselor,
    Quiz,
    Chapter,
    Part,
    CaseStudy,
    QuizAnswers,
    QuizResults,
    VideoProgress,
    CounselorCourse,
    Notes,
    CounselorCertification,
    Question,
)
from .course_completion import is_course_fully_completed as _is_course_fully_completed
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from .models import Counselor, FollowUpStatus
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt

from django.http import JsonResponse, HttpResponse, HttpResponseRedirect


from django.urls import reverse_lazy, reverse
from core.breadcrumbs import get_breadcrumb
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

User = get_user_model()


def _note_timestamp_to_seconds(ts):
    """
    Parse clip time strings (M:SS, MM:SS, H:MM:SS, or bare seconds) to seconds.
    Matches parseNoteTimeToSeconds() in course_learning.html.
    """
    if ts is None:
        return None
    s = str(ts).strip()
    if not s:
        return None
    if ":" not in s:
        try:
            v = int(s, 10)
            return max(0, v)
        except ValueError:
            return None
    parts = s.split(":")
    try:
        nums = [int(p.strip(), 10) for p in parts]
    except ValueError:
        return None
    if any(n < 0 for n in nums):
        return None
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return None


def _counselor_course_access_for_user(user, counselor_course):
    """
    True if this user should be treated as having access to the counselor course:
    successful Payment (same as course detail), matching Invoice, certification,
    or existing video/quiz progress on the course.
    """
    from core import choices
    from payments.models import Payment
    from invoices.models import Invoice

    if not user:
        return False
    if Payment.objects.filter(
        user=user,
        obj_type=choices.PaymentObjectType.COUNSELOR,
        is_success=choices.YesNoChoices.YES,
    ).exists():
        return True
    if Invoice.objects.filter(
        payment__user=user,
        payment__obj_type=choices.PaymentObjectType.COUNSELOR,
    ).exists():
        return True
    if CounselorCertification.objects.filter(user=user).exists():
        return True
    if counselor_course:
        part_ids = list(
            Part.objects.filter(chapter__course=counselor_course).values_list("id", flat=True)
        )
        if part_ids:
            video_keys = [f"video-{pid}" for pid in part_ids]
            if VideoProgress.objects.filter(user=user, video_id__in=video_keys).exists():
                return True
        try:
            qr = QuizResults.objects.get(user=user)
            scores = qr.scores
            if isinstance(scores, str):
                scores = json.loads(scores) if (scores and scores.strip()) else []
            elif not isinstance(scores, list):
                scores = []
            if scores:
                return True
        except (QuizResults.DoesNotExist, ValueError, TypeError):
            pass
    return False


def _counselor_course_progress_percentage(user, counselor_course):
    """
    Overall course progress (0–100), matching CourseLearningView:
    completed parts / total parts. Parts with no video URL count as done for the
    video step (case studies / PDF-only shells). Quizzes still required when present.
    """
    if not user or not counselor_course:
        return 0
    course = (
        CounselorCourse.objects.prefetch_related("chapters__parts__quizzes")
        .filter(pk=counselor_course.pk)
        .first()
    )
    if not course:
        return 0
    chapters_list = list(course.chapters.all())
    total_parts = sum(ch.parts.count() for ch in chapters_list)
    if total_parts == 0:
        return 0

    part_ids = []
    for ch in chapters_list:
        part_ids.extend(ch.parts.values_list("id", flat=True))
    video_keys = [f"video-{pid}" for pid in part_ids]
    video_progress = {}
    if part_ids:
        for progress in VideoProgress.objects.filter(user=user, video_id__in=video_keys):
            video_progress[int(progress.video_id.split("-")[1])] = progress.completed

    quiz_completion_status = {}
    try:
        quiz_result = QuizResults.objects.get(user=user)
        raw_scores = quiz_result.scores
        if isinstance(raw_scores, str):
            scores = json.loads(raw_scores) if raw_scores and raw_scores.strip() else []
        elif isinstance(raw_scores, list):
            scores = raw_scores
        else:
            scores = []
        completed_quiz_ids = set()
        for score in scores:
            if not isinstance(score, dict):
                continue
            qid = score.get("quiz_id")
            if qid is not None:
                try:
                    completed_quiz_ids.add(int(qid))
                except (TypeError, ValueError):
                    pass
        for chapter in chapters_list:
            for part in chapter.parts.all():
                qids = list(part.quizzes.values_list("id", flat=True))
                if not qids:
                    continue
                quiz_completion_status[part.id] = all(int(q) in completed_quiz_ids for q in qids)
    except QuizResults.DoesNotExist:
        pass

    completed_parts = 0
    for chapter in chapters_list:
        for part in chapter.parts.all():
            # Match CourseLearningView: no video URL → nothing to watch (case studies / PDF shell).
            has_video = bool((getattr(part, "video_url", None) or "").strip())
            video_done = video_progress.get(part.id, False) or not has_video
            if not video_done:
                continue
            if part.quizzes.exists():
                if not quiz_completion_status.get(part.id, False):
                    continue
            completed_parts += 1

    return int((completed_parts / total_parts) * 100)


def _counselor_course_detail_cta(request, course):
    """
    Enroll vs Start/Resume for course detail, aligned with counselor dashboard.
    Returns (cta_label, cta_url, counselor_course_enrolled).
    """
    user = getattr(request, "user", None)
    enroll_url = reverse("counselor:CounselorCoursepayment") + "?auto_pay=1"
    if not user or not user.is_authenticated:
        return ("Enroll", enroll_url, False)

    counselor_course_enrolled = bool(course) and _counselor_course_access_for_user(user, course)
    if not counselor_course_enrolled:
        return ("Enroll", enroll_url, False)

    c = Counselor.objects.filter(coun_user=user).first()
    if not c:
        c = Counselor.objects.order_by("id").first()
    if c:
        learn_url = reverse("counselor:course_learning", args=[c.id])
    else:
        learn_url = reverse("counselor:counselor_enrolled_course")

    cta_label = "Start"
    if course:
        part_ids = list(
            Part.objects.filter(chapter__course=course).values_list("id", flat=True)
        )
        if part_ids:
            video_keys = [f"video-{pid}" for pid in part_ids]
            if VideoProgress.objects.filter(user=user, video_id__in=video_keys).exists():
                cta_label = "Resume"
        if cta_label == "Start":
            try:
                qr = QuizResults.objects.get(user=user)
                scores = qr.scores
                if isinstance(scores, str):
                    scores = json.loads(scores) if (scores and scores.strip()) else []
                elif not isinstance(scores, list):
                    scores = []
                if scores:
                    cta_label = "Resume"
            except (QuizResults.DoesNotExist, ValueError, TypeError):
                pass

    if _is_course_fully_completed(user):
        cta_label = "Completed"

    return (cta_label, learn_url, True)


# Create your views here.


class CounselorCourseCurriculumView(TemplateView):
    template_name = "template20/counselor/course_curriculum.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = (
            CounselorCourse.objects.prefetch_related("chapters__parts")
            .order_by("id")
            .first()
        )
        chapters = []
        if course:
            chapters = list(course.chapters.all().order_by("id"))
            for ch in chapters:
                ch._parts = list(ch.parts.all().order_by("id"))

        cta_label, cta_url, counselor_course_enrolled = _counselor_course_detail_cta(
            self.request, course
        )

        context.update(
            {
                "course": course,
                "chapters": chapters,
                "curriculum_cta_label": cta_label,
                "curriculum_cta_url": cta_url,
                "counselor_course_enrolled": counselor_course_enrolled,
            }
        )

        context["user_authenticated"] = bool(
            getattr(self.request, "user", None) and self.request.user.is_authenticated
        )

        from counselor.mindmap_json import (
            course_mindmap_available,
            course_mindmap_relpath,
            mindmap_static_url,
        )

        cm_url = None
        cm_full = None
        if course_mindmap_available(course):
            cm_url = mindmap_static_url(course_mindmap_relpath())
            cm_full = reverse("counselor:course_curriculum_mindmap_full")
        context["course_mindmap_json_url"] = cm_url
        context["course_mindmap_full_url"] = cm_full

        return context


class CounselorCourseCurriculumMindmapFullView(TemplateView):
    """Full-page course mindmap (JSON static file)."""

    template_name = "template20/counselor/mindmap_fullscreen.html"

    def dispatch(self, request, *args, **kwargs):
        from django.http import Http404

        from counselor.mindmap_json import course_mindmap_available
        from counselor.models import CounselorCourse

        course = CounselorCourse.objects.order_by("id").first()
        if not course_mindmap_available(course):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from counselor.mindmap_json import course_mindmap_relpath, mindmap_static_url
        from counselor.models import CounselorCourse

        course = CounselorCourse.objects.order_by("id").first()
        ctx["mindmap_json_url"] = mindmap_static_url(course_mindmap_relpath())
        ctx["page_title"] = "Course mindmap"
        if course and course.title:
            ctx["page_title"] = f"Course mindmap — {course.title}"
        ctx["back_url"] = reverse("counselor:counselor_course_curriculum")
        return ctx


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class CourseLearningChapterMindmapView(View):
    template_name = "template20/counselor/mindmap_fullscreen.html"

    def get(self, request, counselor_id, chapter_id):
        from django.http import Http404
        from core import choices
        from counselor.mindmap_json import chapter_mindmap_available, chapter_mindmap_relpath, mindmap_static_url

        counselor = get_object_or_404(Counselor, id=counselor_id)
        if request.user.user_type == choices.UserType.COUNSELOR:
            if counselor.coun_user != request.user:
                raise Http404("You don't have permission to access this counselor's course.")
        chapter = get_object_or_404(Chapter, pk=chapter_id)
        course = CounselorCourse.objects.order_by("id").first()
        if not course or chapter.course_id != course.id:
            raise Http404
        if not chapter_mindmap_available(chapter):
            raise Http404
        return render(
            request,
            self.template_name,
            {
                "mindmap_json_url": mindmap_static_url(chapter_mindmap_relpath(chapter.id)),
                "page_title": f"Chapter — {chapter.title}",
                "back_url": reverse("counselor:course_learning", args=[counselor_id]),
            },
        )


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class CourseLearningPartMindmapView(View):
    template_name = "template20/counselor/mindmap_fullscreen.html"

    def get(self, request, counselor_id, part_id):
        from django.http import Http404
        from core import choices
        from counselor.mindmap_json import part_mindmap_available, part_mindmap_relpath, mindmap_static_url

        counselor = get_object_or_404(Counselor, id=counselor_id)
        if request.user.user_type == choices.UserType.COUNSELOR:
            if counselor.coun_user != request.user:
                raise Http404("You don't have permission to access this counselor's course.")
        part = get_object_or_404(Part, pk=part_id)
        course = CounselorCourse.objects.order_by("id").first()
        if not course or not part.chapter or part.chapter.course_id != course.id:
            raise Http404
        if not part_mindmap_available(part):
            raise Http404
        return render(
            request,
            self.template_name,
            {
                "mindmap_json_url": mindmap_static_url(part_mindmap_relpath(part.id)),
                "page_title": f"Part — {part.title}",
                "back_url": reverse("counselor:course_learning", args=[counselor_id])
                + f"?type=part&id={part.id}",
            },
        )


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class CourseLearningCourseMindmapView(View):
    """Fullscreen course-wide mindmap (static course.json) from course learning."""

    template_name = "template20/counselor/mindmap_fullscreen.html"

    def get(self, request, counselor_id):
        from django.http import Http404
        from core import choices
        from counselor.mindmap_json import course_mindmap_available, course_mindmap_relpath, mindmap_static_url

        counselor = get_object_or_404(Counselor, id=counselor_id)
        if request.user.user_type == choices.UserType.COUNSELOR:
            if counselor.coun_user != request.user:
                raise Http404("You don't have permission to access this counselor's course.")
        course = CounselorCourse.objects.order_by("id").first()
        if not course:
            raise Http404
        if not course_mindmap_available(course):
            raise Http404
        return render(
            request,
            self.template_name,
            {
                "mindmap_json_url": mindmap_static_url(course_mindmap_relpath()),
                "page_title": course.title or "Course mindmap",
                "back_url": reverse("counselor:course_learning", args=[counselor_id]),
            },
        )


class CounselorCourseDetailView(TemplateView):
    """
    SkillLab-style course landing page (tabs + index accordion + sticky CTA),
    backed by CounselorCourse/Chapter/Part data and Payment state.
    """

    template_name = "template20/counselor/course_detail.html"

    def get_context_data(self, **kwargs):
        from core import choices
        from core.models import Configuration
        from payments.models import Payment

        ctx = super().get_context_data(**kwargs)

        course = (
            CounselorCourse.objects.prefetch_related("chapters__parts")
            .order_by("id")
            .first()
        )

        chapters = []
        part_count = 0
        if course:
            chapters = list(course.chapters.all().order_by("id"))
            for ch in chapters:
                ch._parts = list(ch.parts.all().order_by("id"))
                part_count += len(ch._parts)

        user_authenticated = bool(
            getattr(self.request, "user", None) and self.request.user.is_authenticated
        )
        has_successful_payment = False
        if user_authenticated:
            has_successful_payment = Payment.objects.filter(
                user=self.request.user,
                obj_type=choices.PaymentObjectType.COUNSELOR,
                is_success=choices.YesNoChoices.YES,
            ).exists()

        cta_label, cta_url, counselor_course_enrolled = _counselor_course_detail_cta(
            self.request, course
        )

        # Optional: show intro content from Configuration (keeps data in career_counselor app)
        # Admin can paste HTML into Configuration key: COUNSELOR_COURSE_INTRO_HTML
        course_intro_html = (Configuration.get("COUNSELOR_COURSE_INTRO_HTML", default="", editable=True) or "").strip()

        ctx.update(
            {
                "course": course,
                "chapters": chapters,
                "chapter_count": len(chapters),
                "part_count": part_count,
                "user_authenticated": user_authenticated,
                "has_successful_payment": has_successful_payment,
                "counselor_course_enrolled": counselor_course_enrolled,
                "cta_label": cta_label,
                "cta_url": cta_url,
                "course_intro_html": course_intro_html,
                "breadcrumb": get_breadcrumb(
                    [
                        {
                            "text": "Career Counseling Course",
                            "url": reverse("counselor:CounselorCoursepayment"),
                        },
                        {"text": "Course Detail", "url": ""},
                    ]
                ),
            }
        )
        return ctx

# def CounselorMainDashboard(request):
    
#     return render(request, 'topteenfrontend/user/app/counselor_dashboard.html')

def get_students_by_role(user, counselor=None, institute=None):
    """
    Centralized function to get students based on user role.
    
    Args:
        user: The User object (request.user)
        counselor: Counselor object (required if user is a counselor)
        institute: Institute object (if provided, filter by this specific institute regardless of role)
    
    Returns:
        QuerySet of StudentManagement objects based on role:
        - Counselor: Only assigned students
        - Institute: All students in their own institute
        - Institute Group Admin: All students in institutes within their group (or specific institute if provided)
        - Marketing Group Admin: All students in institutes within their marketing group (or specific institute if provided)
    """
    from core import choices
    from institute.models import InstituteGroup, InstituteMarketingGroup
    
    # If counselor is provided, always return only assigned students for that counselor
    # This takes priority over institute filtering to ensure correct data when viewing counselor dashboard
    if counselor:
        if not counselor.counselor_admin:
            return StudentManagement.objects.none()
        
        # If institute is also provided, verify it matches the counselor's institute
        if institute and counselor.counselor_admin.id != institute.id:
            return StudentManagement.objects.none()
        
        institute = counselor.counselor_admin
        # Return only assigned students (not unassigned) - matching production code
        students = counselor.get_students(institute=institute)
        # Optimize with select_related to avoid N+1 queries
        return students.select_related('student', 'class_and_section', 'institute')
    
    # If a specific institute is provided (but no counselor), filter by that institute regardless of role
    # This ensures that when viewing a specific institute page, only that institute's data is shown
    if institute:
        # Verify user has permission to view this institute
        user_type = user.user_type
        
        if user_type == choices.UserType.INSTITUTE:
            # Institute users can only see their own institute
            user_institute = Institute.objects.filter(created_by=user).first()
            # If user has an institute, it must match the provided institute
            # If user doesn't have an institute, they shouldn't see any students (unless decorator allows, but that's handled separately)
            if not user_institute or user_institute.id != institute.id:
                return StudentManagement.objects.none()
            # Use the user's own institute to ensure correct filtering
            institute = user_institute
        elif user_type == choices.UserType.INSTITUTEGROUPADMIN:
            # Institute Group Admin can see institutes in their group
            institute_group = InstituteGroup.objects.filter(institute_group_admin=user).first()
            if institute_group and institute.institute_group != institute_group:
                return StudentManagement.objects.none()
        elif user_type == choices.UserType.MARKETINGGROUPADMIN:
            # Marketing Group Admin can see institutes in their marketing group
            marketing_group = InstituteMarketingGroup.objects.filter(marketing_group_admin=user).first()
            if marketing_group and institute.marketing_group != marketing_group:
                return StudentManagement.objects.none()
        elif user_type == choices.UserType.COUNSELOR:
            # Counselor can see students from their assigned institute
            if not counselor:
                try:
                    counselor = Counselor.objects.select_related('counselor_admin', 'coun_user').get(coun_user=user)
                except Counselor.DoesNotExist:
                    return StudentManagement.objects.none()
            
            # If counselor is associated with an institute, they can only see that institute's students
            if counselor.counselor_admin:
                if institute and counselor.counselor_admin.id != institute.id:
                    return StudentManagement.objects.none()
            else:
                # If counselor is not associated with any institute, they can only see students with no institute
                if institute is not None:
                    return StudentManagement.objects.none()
        
        # Return students for the specific institute (or None if institute is None)
        if institute:
            return StudentManagement.objects.filter(institute=institute).select_related('student', 'class_and_section', 'institute')
        else:
            return StudentManagement.objects.filter(institute__isnull=True).select_related('student', 'class_and_section', 'institute')
    
    # If counselor is provided, always return only assigned students for that counselor
    # This ensures that when viewing a counselor dashboard (even by marketing/institute users),
    # only the counselor's assigned students are shown
    if counselor:
        if not counselor.counselor_admin:
            return StudentManagement.objects.none()
        
        institute = counselor.counselor_admin
        # Return only assigned students (not unassigned) - matching production code
        students = counselor.get_students(institute=institute)
        # Optimize with select_related to avoid N+1 queries
        return students.select_related('student', 'class_and_section', 'institute')
    
    # If counselor is explicitly provided, return only assigned students for that counselor
    # This ensures that when viewing a counselor dashboard (even as a marketing user),
    # we show only the counselor's assigned students, not all students in the marketing group
    if counselor:
        if not counselor.counselor_admin:
            return StudentManagement.objects.none()
        
        institute = counselor.counselor_admin
        # Return only assigned students (not unassigned) - matching production code
        students = counselor.get_students(institute=institute)
        # Optimize with select_related to avoid N+1 queries
        return students.select_related('student', 'class_and_section', 'institute')
    
    # If no specific institute provided, use role-based logic
    user_type = user.user_type
    
    if user_type == choices.UserType.COUNSELOR:
        # Counselor sees only their assigned students (matching production code)
        # Try to get counselor from user
        try:
            counselor = Counselor.objects.select_related('counselor_admin', 'coun_user').get(coun_user=user)
        except Counselor.DoesNotExist:
            return StudentManagement.objects.none()
        
        if not counselor.counselor_admin:
            return StudentManagement.objects.none()
        
        institute = counselor.counselor_admin
        # Return only assigned students (not unassigned) - matching production code
        students = counselor.get_students(institute=institute)
        # Optimize with select_related to avoid N+1 queries
        return students.select_related('student', 'class_and_section', 'institute')
    
    elif user_type == choices.UserType.INSTITUTE:
        # Institute sees all students in their own institute
        if not institute:
            # Try to get institute from user
            try:
                institute = Institute.objects.filter(created_by=user).first()
            except Institute.DoesNotExist:
                return StudentManagement.objects.none()
        
        if not institute:
            return StudentManagement.objects.none()
        
        return StudentManagement.objects.filter(institute=institute).select_related('student', 'class_and_section', 'institute')
    
    elif user_type == choices.UserType.INSTITUTEGROUPADMIN:
        # Institute Group Admin sees all students in institutes within their group
        institute_group = InstituteGroup.objects.filter(institute_group_admin=user).first()
        if not institute_group:
            return StudentManagement.objects.none()
        
        return StudentManagement.objects.filter(institute__institute_group=institute_group).select_related('student', 'class_and_section', 'institute')
    
    elif user_type == choices.UserType.MARKETINGGROUPADMIN:
        # Marketing Group Admin sees all students in institutes within their marketing group
        marketing_group = InstituteMarketingGroup.objects.filter(marketing_group_admin=user).first()
        if not marketing_group:
            return StudentManagement.objects.none()
        
        return StudentManagement.objects.filter(institute__marketing_group=marketing_group).select_related('student', 'class_and_section', 'institute')
    
    else:
        # Unknown role, return empty queryset
        return StudentManagement.objects.none()


def get_class_and_sections_by_role(user, students_queryset):
    """
    Get class_and_sections based on user role and the students they can see.
    Returns distinct class_and_sections for the students in the queryset.
    
    Args:
        user: The User object (request.user)
        students_queryset: QuerySet of StudentManagement objects
    
    Returns:
        QuerySet of ClassAndSection objects (distinct, ordered)
    """
    if not students_queryset.exists():
        return ClassAndSection.objects.none()
    
    # Get distinct class_and_sections from the students queryset
    class_and_sections = ClassAndSection.objects.filter(
        student_management__in=students_queryset
    ).distinct().order_by('class_and_section')
    
    return class_and_sections


def apply_student_filters(students_data, request, results_data=None):
    """
    Centralized function to apply common filters to student data.
    Works with both QuerySet and list of student dictionaries.
    
    Args:
        students_data: QuerySet of StudentManagement objects or list of student dicts
        request: Django request object with GET parameters
        results_data: Optional dict of test results (for test_taken filter)
                      Format: {student_user: {'test_status': 'completed'|'in_progress'|'no_tests', ...}}
    
    Returns:
        Filtered students_data (same type as input)
    """
    # Get filter parameters from request
    class_filter = request.GET.get('class_and_section', '').strip()
    name_filter = request.GET.get('student_name', '').strip()
    test_taken_filter = request.GET.get('test_taken', '').strip()
    
    # Handle QuerySet
    if hasattr(students_data, 'filter'):
        # It's a QuerySet
        queryset = students_data
        
        # Apply class filter
        if class_filter:
            queryset = queryset.filter(class_and_section__class_and_section=class_filter)
        
        # Apply name filter
        if name_filter:
            queryset = queryset.filter(student__name__icontains=name_filter)
        
        # Apply test_taken filter (requires results_data)
        if test_taken_filter and results_data:
            # We need to filter based on test_status in results_data
            # This is more complex for QuerySet, so we'll convert to list and filter
            student_list = list(queryset)
            filtered_list = []
            for student_mgmt in student_list:
                student_user = student_mgmt.student
                student_result = results_data.get(student_user, {})
                test_status = student_result.get('test_status', 'no_tests')
                
                if test_taken_filter == 'Yes' and test_status == 'completed':
                    filtered_list.append(student_mgmt)
                elif test_taken_filter == 'No' and test_status == 'no_tests':
                    filtered_list.append(student_mgmt)
                elif test_taken_filter == 'In Progress' and test_status == 'in_progress':
                    filtered_list.append(student_mgmt)
            
            return filtered_list
        
        return queryset
    
    # Handle list of dictionaries (merged_data format)
    else:
        # It's a list
        filtered_data = list(students_data)
        
        # Apply class filter
        if class_filter:
            filtered_data = [
                s for s in filtered_data
                if hasattr(s, 'get') and s.get('student') and 
                hasattr(s['student'], 'class_and_section') and
                s['student'].class_and_section and
                str(s['student'].class_and_section.class_and_section) == class_filter
            ]
        
        # Apply name filter
        if name_filter:
            filtered_data = [
                s for s in filtered_data
                if hasattr(s, 'get') and s.get('student') and
                hasattr(s['student'], 'student') and
                name_filter.lower() in s['student'].student.name.lower()
            ]
        
        # Apply test_taken filter
        if test_taken_filter and results_data:
            filtered_list = []
            for student_info in filtered_data:
                student = student_info.get('student')
                if student:
                    student_user = getattr(student, 'student', student)
                    student_result = results_data.get(student_user, {})
                    test_status = student_result.get('test_status', 'no_tests')
                    
                    if test_taken_filter == 'Yes' and test_status == 'completed':
                        filtered_list.append(student_info)
                    elif test_taken_filter == 'No' and test_status == 'no_tests':
                        filtered_list.append(student_info)
                    elif test_taken_filter == 'In Progress' and test_status == 'in_progress':
                        filtered_list.append(student_info)
            
            filtered_data = filtered_list
        
        return filtered_data


def get_class_counts(students_queryset):
    """
    Centralized function to get class counts for display in dropdown.
    
    Args:
        students_queryset: QuerySet or list of StudentManagement objects
    
    Returns:
        Dict with class names as keys and student counts as values
    """
    class_counts = {}
    
    # Handle QuerySet
    if hasattr(students_queryset, 'values_list'):
        for student in students_queryset:
            if student.class_and_section:
                class_name = student.class_and_section.class_and_section
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
    # Handle list
    else:
        for student_item in students_queryset:
            # Handle both StudentManagement objects and dict format
            if hasattr(student_item, 'class_and_section'):
                student = student_item
            elif isinstance(student_item, dict) and 'student' in student_item:
                student = student_item['student']
            else:
                continue
            
            if student.class_and_section:
                class_name = student.class_and_section.class_and_section
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
    
    return class_counts


def get_unique_streams_by_role(user, students_queryset):
    """
    Get unique streams based on user role and the students they can see.
    Returns distinct stream values for the students in the queryset.
    
    Args:
        user: The User object (request.user)
        students_queryset: QuerySet of StudentManagement objects
    
    Returns:
        List of unique stream values (distinct, ordered, excluding None/empty)
    """
    if not students_queryset.exists() if hasattr(students_queryset, 'exists') else not students_queryset:
        return []
    
    # Get distinct streams from the students queryset
    if hasattr(students_queryset, 'values_list'):
        # QuerySet - use database distinct
        streams = students_queryset.filter(
            class_and_section__stream__isnull=False
        ).exclude(
            class_and_section__stream=''
        ).values_list(
            'class_and_section__stream', flat=True
        ).distinct().order_by('class_and_section__stream')
        return list(streams)
    else:
        # List - use Python set
        streams_set = set()
        for student_item in students_queryset:
            if hasattr(student_item, 'class_and_section'):
                student = student_item
            elif isinstance(student_item, dict) and 'student' in student_item:
                student = student_item['student']
            else:
                continue
            
            if student.class_and_section and student.class_and_section.stream:
                streams_set.add(student.class_and_section.stream)
        
        return sorted(list(streams_set))


def get_students_in_institute(counselor):
    """
    Fetch assigned students for a given counselor.
    Note: This function is kept for backward compatibility but now only returns assigned students.
    Use get_students_by_role() for new code.
    """
    if not counselor or not counselor.counselor_admin:
        return StudentManagement.objects.none(), StudentManagement.objects.none(), StudentManagement.objects.none()
    
    institute = counselor.counselor_admin
    all_institute_students = StudentManagement.objects.filter(institute=institute)
    
    # Get assigned students only
    assigned_students = counselor.get_students(institute=institute)
    assigned_student_ids = assigned_students.values_list('id', flat=True)
    unassigned_students = all_institute_students.exclude(id__in=assigned_student_ids)

    # Counselor should only see assigned students, not unassigned
    students_to_display = assigned_students
    return students_to_display, assigned_students, unassigned_students

def get_results_data_for_students(students):
    """Prepare results data for a list of students using the same logic as institute dashboard."""
    from app.models import TestCompletion, Results
    from app_post_matric.models import TestSession
    from institute.models import StudentManagement
    from django.urls import reverse
    import re
    
    results_data = {}
    
    for student_management in students:
        student = student_management.student  # Access the student related to StudentManagement
        
        try:
            # Check student's class to determine which system to use
            student_mgmt = StudentManagement.objects.filter(student=student).first()
            
            if student_mgmt and student_mgmt.class_and_section:
                class_name = student_mgmt.class_and_section.class_and_section
                
                # Extract class number
                class_number = None
                try:
                    numbers = re.findall(r'\d+', class_name)
                    if numbers:
                        class_number = int(numbers[0])
                except (ValueError, IndexError):
                    pass
                
                # Determine system based on class
                if class_number and class_number >= 11:
                    # Class 11-12: Use post-matric system
                    post_matric_sessions = TestSession.objects.filter(user=student)
                    student_result = _get_post_matric_test_result(student, post_matric_sessions)
                else:
                    # Class 10 and below: Use psychometric system
                    student_result = _get_psychometric_test_result(student)
            else:
                # No class information, default to psychometric system
                student_result = _get_psychometric_test_result(student)
                
        except Exception as e:
            print(f"Error getting test result for student {student}: {e}")
            student_result = {
                "test_success": False,
                "test_link": None,
                "success_count": 0,
                "test_status": "no_tests",
                "tooltip": "Error loading test data"
            }
        
        if student_result:
            results_data[student] = student_result
        else:
            # Default values if no result
            results_data[student] = {
                "test_success": False,
                "test_link": None,
                "success_count": 0,
                "test_status": "no_tests",
                "tooltip": "No tests taken"
            }
        
    return results_data


def _get_psychometric_test_result(user):
    """Handle psychometric students (class 1-10) using TestCompletion/Results."""
    from app.models import TestCompletion, Results
    from django.urls import reverse
    
    try:
        # Check TestCompletion first to determine if student has completed tests
        test_completion = None
        try:
            test_completion = TestCompletion.objects.get(user=user)
        except TestCompletion.DoesNotExist:
            # If no TestCompletion record exists, student hasn't taken any tests
            return {
                "streams": {},
                "test_success": False,
                "test_link": reverse('app:test_buttons'),
                "success_count": 0,
                "test_status": "no_tests",
                "test_details": {
                    "test1": False,
                    "test2": False,
                    "test3": False
                },
                "tooltip": "No tests taken"
            }
        
        # Get individual test completion status
        test1_complete = test_completion.test1_complete
        test2_complete = test_completion.test2_complete
        
        # Verify test3_complete - only True if ALL subtests are complete
        all_test3_subtests_complete = (
            test_completion.numerical_complete and
            test_completion.verbal_complete and
            test_completion.logical_complete and
            test_completion.emotional_complete and
            test_completion.machanical_complete and
            test_completion.language_complete and
            test_completion.spatial_complete
        )
        
        test3_complete = test_completion.test3_complete if all_test3_subtests_complete else False
        
        # Count completed tests
        completed_tests = sum([test1_complete, test2_complete, test3_complete])
        
        # Create detailed tooltip showing all test statuses
        completed_list = []
        not_completed_list = []
        
        if test1_complete:
            completed_list.append("Career Interest")
        else:
            not_completed_list.append("Career Interest")
            
        if test2_complete:
            completed_list.append("Intelligence")
        else:
            not_completed_list.append("Intelligence")
            
        if test3_complete:
            completed_list.append("Personality")
        else:
            not_completed_list.append("Personality")
        
        # Create detailed tooltip showing all test statuses
        tooltip_parts = []
        if completed_list:
            tooltip_parts.append(f"Completed: {', '.join(completed_list)}")
        if not_completed_list:
            tooltip_parts.append(f"Not completed: {', '.join(not_completed_list)}")
        tooltip = " | ".join(tooltip_parts)
        
        # Determine overall status
        if completed_tests == 0:
            test_status = "no_tests"
        elif completed_tests == 3:
            test_status = "completed"
        else:
            test_status = "in_progress"
        
        # Get test link - only provide link if all tests are completed
        test_link = None
        if test_status == "completed":
            results = Results.objects.filter(user=user)
            if results.exists():
                latest_result = results.last()
                test_link = latest_result.get_test_report_or_test_link(user) if latest_result else None
        
        return {
            "streams": {},
            "test_success": completed_tests > 0,
            "test_link": test_link,
            "success_count": completed_tests,
            "test_status": test_status,
            "test_details": {
                "test1": test1_complete,
                "test2": test2_complete,
                "test3": test3_complete
            },
            "tooltip": tooltip
        }
        
    except Exception as e:
        print(f"Error in _get_psychometric_test_result: {e}")
        return {
            "streams": {},
            "test_success": False,
            "test_link": None,
            "success_count": 0,
            "test_status": "no_tests",
            "test_details": {
                "test1": False,
                "test2": False,
                "test3": False
            },
            "tooltip": "Error loading test data"
        }


def _get_post_matric_test_result(user, test_sessions):
    """Handle post-matric students (class 11-12) using TestSession/TestResult."""
    from app_post_matric.models import TestSession
    from django.urls import reverse
    
    try:
        # Initialize test completion status for 4 tests
        test_completion = {
            1: False,  # Personality Assessment
            2: False,  # Motivation Assessment
            3: False,  # Career Interest Inventory  
            4: False   # Aptitude Assessment
        }
        
        # Check completed sessions
        completed_sessions = test_sessions.filter(is_completed=True)
        for session in completed_sessions:
            test_id = session.test.id
            if test_id in test_completion:
                test_completion[test_id] = True
        
        # Count completed tests
        completed_tests = sum(test_completion.values())
        
        # Determine overall status and create detailed tooltip
        completed_list = []
        not_completed_list = []
        
        if test_completion[1]:
            completed_list.append("Personality")
        else:
            not_completed_list.append("Personality")
            
        if test_completion[2]:
            completed_list.append("Motivation")
        else:
            not_completed_list.append("Motivation")
            
        if test_completion[3]:
            completed_list.append("Career Interest")
        else:
            not_completed_list.append("Career Interest")
            
        if test_completion[4]:
            completed_list.append("Aptitude")
        else:
            not_completed_list.append("Aptitude")
        
        # Create detailed tooltip showing all test statuses
        tooltip_parts = []
        if completed_list:
            tooltip_parts.append(f"Completed: {', '.join(completed_list)}")
        if not_completed_list:
            tooltip_parts.append(f"Not completed: {', '.join(not_completed_list)}")
        tooltip = " | ".join(tooltip_parts)
        
        # Determine overall status
        if completed_tests == 0:
            test_status = "no_tests"
        elif completed_tests == 4:
            test_status = "completed"
        else:
            test_status = "in_progress"
        
        # Get test link - only provide link if all tests are completed
        test_link = None
        if test_status == "completed":
            test_link = reverse('post_matric:combined_report', args=[user.id])
        
        return {
            "streams": {},
            "test_success": completed_tests > 0,
            "test_link": test_link,
            "success_count": completed_tests,
            "test_status": test_status,
            "test_details": {
                "test1": test_completion[1],
                "test2": test_completion[2],
                "test3": test_completion[3],
                "test4": test_completion[4]
            },
            "tooltip": tooltip
        }
            
    except Exception as e:
        print(f"Error in _get_post_matric_test_result: {e}")
        return {
            "streams": {},
            "test_success": False,
            "test_link": None,
            "success_count": 0,
            "test_status": "no_tests",
            "test_details": {
                "test1": False,
                "test2": False,
                "test3": False,
                "test4": False
            },
            "tooltip": "Error loading test data"
        }


import logging
logger = logging.getLogger(__name__)



@login_required(login_url=reverse_lazy('users:login'))

def Students_follow_up(request, coun_id):
    from core import choices
    from django.http import Http404
    
    # Get the counselor and institute details
    counselor = get_object_or_404(Counselor, id=coun_id)
    
    # Security check: Ensure counselors can only access their own follow-up page
    if request.user.user_type == choices.UserType.COUNSELOR:
        # If user is a counselor, they must be the owner of this counselor record
        if counselor.coun_user != request.user:
            raise Http404("You don't have permission to access this counselor's follow-up page.")
    
    # Get counselor's associated institute
    counselor_institute = counselor.counselor_admin
    
    # Use centralized role-based function to get students - ALL students from counselor's institute (if associated)
    # Pass both counselor and institute to ensure correct filtering regardless of logged-in user's role
    students_to_display = get_students_by_role(request.user, counselor=counselor, institute=counselor_institute)
    
    # Get assigned student IDs separately for follow-up filtering
    # Follow-ups should only be shown for students actually assigned to this counselor
    if counselor.counselor_admin:
        # Get students assigned to this counselor from their institute
        assigned_students = counselor.get_students(institute=counselor.counselor_admin)
        assigned_student_ids = assigned_students.values_list('id', flat=True) if hasattr(assigned_students, 'values_list') else [s.id for s in assigned_students]
    else:
        # If no institute, get assigned students (though this might be empty)
        assigned_students = counselor.students.filter(institute__isnull=True)
        assigned_student_ids = assigned_students.values_list('id', flat=True) if hasattr(assigned_students, 'values_list') else [s.id for s in assigned_students]
    
    # Initialize follow_up_data as an empty list
    follow_up_data = []

    if request.method == 'POST':
        # Retrieve the student ID from the form
        student_id = request.POST.get('student_id')
        if student_id:
            logger.debug(f"Received student ID: {student_id}")
            try:
                # Only allow creating follow-ups for assigned students
                student_management_instance = assigned_students.get(id=student_id)
            except StudentManagement.DoesNotExist:
                logger.warning("Student not found or not assigned to counselor.")
                messages.error(request, 'Selected student is not assigned to you.')
                return redirect('counselor:Counselor_follow_up_page', coun_id=coun_id)

            # Create or update the follow-up instance
            follow_up_instance, created = FollowUpStatus.objects.update_or_create(
                counselor=counselor,
                student=student_management_instance,
                defaults={
                    'mode_of_follow_up': request.POST.get('mode_of_follow_up'),
                    'follow_up_status': request.POST.get('follow_up_status'),
                    'last_follow_up_date': request.POST.get('last_follow_up_date'),
                    'next_follow_up_date': request.POST.get('next_follow_up_date'),
                    'message': request.POST.get('message'),
                    'is_followed_up': request.POST.get('is_followed_up') == 'on'
                }
            )

            if not created:
                follow_up_instance.mode_of_follow_up = request.POST.get('mode_of_follow_up')
                follow_up_instance.follow_up_status = request.POST.get('follow_up_status')
                follow_up_instance.last_follow_up_date = request.POST.get('last_follow_up_date')
                follow_up_instance.next_follow_up_date = request.POST.get('next_follow_up_date')
                follow_up_instance.message = request.POST.get('message')
                follow_up_instance.is_followed_up = request.POST.get('is_followed_up') == 'on'
                follow_up_instance.save()

            logger.debug("Follow-up entry saved successfully.")
            messages.success(request, 'Follow-up created successfully!')
            return redirect('counselor:Counselor_follow_up_page', coun_id=coun_id)
        else:
            logger.warning("No student ID provided.")

    # Retrieve follow-up data only for assigned students
    follow_ups = FollowUpStatus.objects.filter(
        counselor=counselor,
        student_id__in=assigned_student_ids
    ).select_related('student', 'student__student')
    
    # Create a dictionary to hold follow-up data by student ID
    follow_up_data = {}
    total_is_followed_up_count = 0
    
    for follow_up in follow_ups:
        if follow_up.student.id not in follow_up_data:
            follow_up_data[follow_up.student.id] = {
                'follow_ups': []
            }
        follow_up_data[follow_up.student.id]['follow_ups'].append({
            'is_followed_up': follow_up.is_followed_up,
            'message': follow_up.message,
            'last_follow_up_date': follow_up.last_follow_up_date,
            'next_follow_up_date': follow_up.next_follow_up_date,
        })
        
        # Increment the count if this follow-up is marked as followed up
        if follow_up.is_followed_up:
            total_is_followed_up_count += 1

    # Merging the data
    merged_data = []
    for student in students_to_display:
        student_info = {
            'student': student,
            'follow_ups': follow_up_data.get(student.id, {'follow_ups': []})['follow_ups'],
        }
        merged_data.append(student_info)

    # Sorting merged data
    merged_data = sorted(merged_data, key=lambda x: x['student'].student.name.lower())
    
    # Apply filters using centralized function (no test_taken filter in follow-up page)
    merged_data = apply_student_filters(merged_data, request, results_data=None)

    
    # Setting up pagination
    paginator = Paginator(merged_data, 10)  # 10 students per page
    page_number = request.GET.get('page')
    students_page = paginator.get_page(page_number)

    # Get class counts for display in dropdown using centralized function
    class_counts = get_class_counts(students_to_display)

    # Render context
    context = {
        'counselors': counselor,
        'students': students_page,
        'class_and_sections': get_class_and_sections_by_role(request.user, students_to_display),
        'class_counts': class_counts,  # Add class counts for dropdown
        'students_count': students_to_display,
        'total_is_followed_up_count': total_is_followed_up_count,
        'coun_id' : coun_id
    }

    return render(request, 'template20/counselor/follow_up_page.html', context)

def CounselorCoursepayment(request):
    from django.conf import settings
    import razorpay
    from payments.models import Payment
    from core import choices
    import uuid
    
    # Get course statistics
    course_with_related_data = CounselorCourse.objects.prefetch_related(
        'chapters__parts__quizzes__questions'
    ).first()

    _currency_symbol = (
        course_with_related_data.get_currency_symbol()
        if course_with_related_data
        else '₹'
    )
    _razorpay_currency = (
        course_with_related_data.get_currency_code()
        if course_with_related_data
        else 'INR'
    )
    _payment_currency = (
        int(course_with_related_data.currency)
        if course_with_related_data
        else choices.Currency.IND
    )

    chapter_count = 0
    part_count = 0
    question_count = 0
    
    if course_with_related_data:
        chapter_count = course_with_related_data.chapters.count()
        for chapter in course_with_related_data.chapters.all():
            part_count += chapter.parts.count()
            for part in chapter.parts.all():
                question_count += part.quizzes.values('questions').count()

    counselor_course_enrolled = False
    counselor_payment_cta_label = "Book Now"
    counselor_payment_cta_url = ""
    if request.user.is_authenticated and course_with_related_data:
        counselor_course_enrolled = _counselor_course_access_for_user(
            request.user, course_with_related_data
        )
        if counselor_course_enrolled:
            _lbl, counselor_payment_cta_url, _ = _counselor_course_detail_cta(
                request, course_with_related_data
            )
            counselor_payment_cta_label = (
                "Start Now" if _lbl == "Start" else "Resume"
            )

    # Only create payment record and Razorpay order if user is authenticated and not already enrolled
    payment_record_id = None
    razorpay_order = None
    amount = (
        course_with_related_data.get_charge_amount_rupees()
        if course_with_related_data
        else 19999
    )

    def _inr_commas(n):
        try:
            return '{:,}'.format(int(n))
        except (TypeError, ValueError):
            return str(n)

    _charge = amount
    _actual = (
        int(course_with_related_data.actual_price)
        if course_with_related_data
        else 19999
    )
    _has_discount = bool(
        course_with_related_data
        and int(course_with_related_data.discount_percent) > 0
    )
    if _has_discount:
        _pct = int(course_with_related_data.discount_percent)
    else:
        _pct = None

    if request.user.is_authenticated and not counselor_course_enrolled:
        # Check for existing unpaid payment order
        existing_payment = Payment.objects.filter(
            user=request.user,
            obj_type=choices.PaymentObjectType.COUNSELOR,
            is_success=choices.YesNoChoices.NO,
            gateway_order_id__isnull=False
        ).exclude(gateway_order_id='').order_by('-created').first()
        
        if existing_payment and existing_payment.gateway_order_id:
            # Use existing payment order
            payment_record_id = existing_payment.id
            try:
                # Verify order still exists in Razorpay
                client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
                razorpay_order = client.order.fetch(existing_payment.gateway_order_id)
            except Exception as e:
                # Order doesn't exist or expired, create new one
                existing_payment = None
        
        if not existing_payment or not razorpay_order:
            # Create new Payment record
            gateway_receipt = f"counselor_course_{uuid.uuid4().hex[:12]}"
            
            payment_record = Payment.objects.create(
                user=request.user,
                amount=amount,
                currency=_payment_currency,
                gateway_receipt=gateway_receipt,
                obj_type=choices.PaymentObjectType.COUNSELOR,
                obj_id=course_with_related_data.id if course_with_related_data else 0,
                is_success=choices.YesNoChoices.NO
            )
            
            # Create Razorpay order
            client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
            data = { 
                "amount": amount * 100,  # minor units (paise for INR)
                "currency": _razorpay_currency,
                "receipt": gateway_receipt
            }
            razorpay_order = client.order.create(data=data)
            
            # Update payment record with Razorpay order ID
            payment_record.gateway_order_id = razorpay_order.get('id')
            payment_record.save()
            payment_record_id = payment_record.id
    
    # Build signed success/fail URLs for redirect after payment (like psychometric flow)
    success_url = None
    fail_url = None
    if payment_record_id:
        from django.core.signing import Signer
        from urllib.parse import quote, unquote
        sign = Signer()
        enc_id = sign.sign_object({'enc_id': payment_record_id})
        enc_id_quoted = quote(enc_id, safe='')
        success_url = request.build_absolute_uri(reverse('counselor:counselor_course_payment_success', kwargs={'enc_id': enc_id_quoted}))
        fail_url = request.build_absolute_uri(reverse('counselor:counselor_course_payment_fail', kwargs={'enc_id': enc_id_quoted}))
    
    # Dynamic content for Career Counseling Course page (can be moved to DB/CMS later)
    course_page = {
        'hero_heading': 'Transform Lives',
        'hero_subline': 'Career Counselling',
        'hero_description': "Master the art of guiding individuals to their perfect career paths with our comprehensive certification course",
        'about_heading': 'About the Course',
        'about_text': "Step into the world of career counselling with our comprehensive Certification Course. Designed by leading experts, this program equips you with cutting-edge techniques and foundational theories to effectively guide clients towards fulfilling career decisions. Whether you are starting your journey or seeking to deepen your expertise, our course offers a robust curriculum tailored to meet the demands of today's dynamic job market.",
        'why_choose_heading': "Why Choose Our Program?",
        'training_journey_heading': "Your 60-Hour Training Journey",
        'training_hours': 60,
        'certification_heading': "Certification & Career Advancement",
        'certification_intro': "Every student has unique emotional strengths and growth areas-our assessment reveals all six and gives clear steps to improve.",
        'refund_heading': "No Refund Policy",
        'faq_heading': "Got Questions? We've Got Answers!",
        'features': [
            {'title': 'Expert-Designed Curriculum', 'description': 'Created by experienced career counselling professionals using proven, real-world methods that deliver results.', 'icon': 'c-program-icon1.png'},
            {'title': 'Practical Skills Focus', 'description': 'Gain practical skills in psychometric assessments, career mapping, & real-world counselling.', 'icon': 'c-program-icon2.png'},
            {'title': 'Prestigious Certification', 'description': 'Earn an industry-recognized certification valued in education & corporate sectors worldwide.', 'icon': 'c-program-icon3.png'},
            {'title': 'Flexible Learning', 'description': 'Study at your own pace with flexible schedules while maintaining high learning standards.', 'icon': 'c-program-icon4.png'},
        ],
        'modules': [
            {'title': 'Foundation Building', 'description': 'Kick start your training with essential theories and history of career counseling, establishing a solid foundation for your expertise.'},
            {'title': 'Skill Development', 'description': 'Learn effective communication, ethical practice, and client relationship management through interactive modules and real-world scenarios.'},
            {'title': 'Advanced Assessment Techniques', 'description': 'Master contemporary assessment methods to help clients make informed career decisions based on scientific evaluation.'},
            {'title': 'Career Mapping Mastery', 'description': 'Learn to guide clients through comprehensive career mapping, integrating their unique skills, interests, and market opportunities.'},
            {'title': 'Real-World Applications', 'description': 'Apply your newly acquired skills under expert supervision in authentic counselling scenarios with real clients.'},
            {'title': 'Certification Preparation', 'description': "Complete comprehensive preparation for your certification exam, ensuring you're fully equipped to excel as a professional career counsellor."},
        ],
        'career_roles': [
            {'label': 'School Career Advisor', 'text': 'Guide students through educational and career decisions'},
            {'label': 'Corporate Career Coach', 'text': 'Help professionals navigate career transitions and growth'},
            {'label': 'Private Practice Consultant', 'text': 'Build your own successful counselling practice'},
            {'label': 'Educational Institution Counsellor', 'text': 'Work with colleges and universities'},
            {'label': 'HR Career Development Specialist', 'text': 'Support employee career progression'},
        ],
        'refund_items': [
            {'label': 'Refund Eligibility', 'text': 'Our career counselling certification course operates under a strict no refund policy to ensure commitment and resource allocation effectiveness. We understand that plans can change, which is why we offer a conditional refund.'},
            {'label': 'Conditional Refund', 'text': 'Refunds are only available if a student decides to withdraw from the course more than 7 days before the scheduled start date. To request a refund, students must notify the administration in writing within this time frame.'},
        ],
        'refund_non_refundable': 'Once the course has begun, or if the withdrawal request is received less than 7 days before the course start date, no refunds will be issued under any circumstances.',
    }

    # Watch Video: admin sets COUNSELOR_COURSE_VIDEO_URL in Django Admin > Configuration
    #   (e.g. YouTube URL or S3 video URL).
    # Thumbnail: set COUNSELOR_COURSE_VIDEO_THUMBNAIL in Configuration to the thumbnail image URL.
    #   - For S3 / non-YouTube: no auto-thumbnail; upload a thumbnail to S3 and set this to that image URL.
    #   - For YouTube: if empty, we use YouTube's default thumbnail; otherwise use this URL.
    from core.models import Configuration
    counselor_course_video_url = (Configuration.get('COUNSELOR_COURSE_VIDEO_URL', default='', editable=True) or '').strip()
    counselor_course_video_embed_url = ''
    counselor_course_video_thumbnail_url = (Configuration.get('COUNSELOR_COURSE_VIDEO_THUMBNAIL', default='', editable=True) or '').strip()
    counselor_course_video_yt_id = ''  # for YouTube thumbnail fallback in template
    if counselor_course_video_url:
        import re
        # Convert YouTube watch URL to embed URL if needed
        yt_match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', counselor_course_video_url)
        if yt_match:
            counselor_course_video_yt_id = yt_match.group(1)
            counselor_course_video_embed_url = 'https://www.youtube.com/embed/' + counselor_course_video_yt_id + '?autoplay=1'
            if not counselor_course_video_thumbnail_url:
                # Use YouTube default thumbnail (maxresdefault; fallback hqdefault in template)
                counselor_course_video_thumbnail_url = 'https://img.youtube.com/vi/' + counselor_course_video_yt_id + '/maxresdefault.jpg'
        else:
            counselor_course_video_embed_url = counselor_course_video_url

    context = {
        'key': settings.RAZORPAY_API_KEY,
        'payment': razorpay_order,
        'payment_record_id': payment_record_id,
        'counselor_course_payment_success_url': success_url,
        'counselor_course_payment_fail_url': fail_url,
        'chapter_count': chapter_count,
        'part_count': part_count,
        'question_count': question_count,
        'course': course_with_related_data,
        'course_price_charge': _charge,
        'course_price_charge_fmt': _inr_commas(_charge),
        'course_price_actual_fmt': _inr_commas(_actual),
        'course_has_discount': _has_discount,
        'course_discount_percent': _pct,
        'course_currency_symbol': _currency_symbol,
        'razorpay_currency': _razorpay_currency,
        'user_authenticated': request.user.is_authenticated,
        'counselor_course_enrolled': counselor_course_enrolled,
        'counselor_payment_cta_label': counselor_payment_cta_label,
        'counselor_payment_cta_url': counselor_payment_cta_url,
        'course_page': course_page,
        'counselor_course_video_url': counselor_course_video_url,
        'counselor_course_video_embed_url': counselor_course_video_embed_url,
        'counselor_course_video_thumbnail_url': counselor_course_video_thumbnail_url,
        'counselor_course_video_yt_id': counselor_course_video_yt_id,
        'breadcrumb': get_breadcrumb([
            {'text': 'Home', 'url': reverse('core:home')},
            {'text': 'Career Counseling Course', 'url': ''},
        ]),
    }
    return render(request, 'template20/counselor/course_payment.html', context)
def display_pdfs(request):
    return render(request, 'template20/counselor/display_pdfs.html')


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class CounselorCoursePaymentSuccess(TemplateView):
    """Payment success page: show summary, transaction ID, receipt link, and Start course button."""
    template_name = 'template20/counselor/course_payment_success.html'

    def get_context_data(self, **kwargs):
        from django.core.signing import Signer
        from urllib.parse import unquote
        from payments.models import Payment
        from core import choices
        from invoices.models import Invoice

        ctx = super().get_context_data(**kwargs)
        from core import choices as core_choices
        is_counselor_user = getattr(self.request.user, 'user_type', None) == core_choices.UserType.COUNSELOR
        ctx['is_counselor_user'] = is_counselor_user
        if is_counselor_user:
            _counselor = Counselor.objects.filter(coun_user=self.request.user).first()
        else:
            _counselor = Counselor.objects.first()
        ctx['counselor'] = _counselor
        ctx['coun_id'] = _counselor.id if _counselor else None
        ctx['start_course_url'] = reverse('counselor:course_learning', args=[_counselor.id]) if _counselor else reverse('counselor:counselor_enrolled_course')
        ctx['counselor_dashboard_url'] = reverse('counselor:CounselorDashboardView', args=[ctx['coun_id']]) if (is_counselor_user and ctx['coun_id']) else None

        enc_id = kwargs.get('enc_id')
        if not enc_id:
            return ctx
        try:
            enc_id = unquote(enc_id)
            sign = Signer()
            signobj = sign.unsign_object(enc_id)
            payment_id = signobj.get('enc_id')
        except Exception:
            return ctx
        payment = Payment.objects.filter(
            id=payment_id,
            user=self.request.user,
            obj_type=choices.PaymentObjectType.COUNSELOR,
            is_success=choices.YesNoChoices.YES,
        ).first()
        if not payment:
            payment = Payment.objects.filter(
                id=payment_id,
                user=self.request.user,
                obj_type=choices.PaymentObjectType.COUNSELOR,
            ).first()
        ctx['payment'] = payment
        try:
            ctx['invoice_id'] = payment.invoice.id if payment else None
        except Exception:
            ctx['invoice_id'] = None
        ctx['course'] = CounselorCourse.objects.first()
        return ctx


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class CounselorCoursePaymentFail(TemplateView):
    """Payment fail page: show message and link to try again."""
    template_name = 'template20/counselor/course_payment_fail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['payment_page_url'] = reverse('counselor:CounselorCoursepayment')
        return ctx


@login_required(login_url=reverse_lazy('users:login'))
def update_counselor_course_payment(request):
    """API endpoint to update payment details after Razorpay payment"""
    from payments.models import Payment
    from core import choices
    from django.http import JsonResponse
    import json
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
    
    try:
        data = json.loads(request.body)
        payment_id = data.get('payment_id')
        gateway_payment_id = data.get('gateway_payment_id')
        gateway_order_id = data.get('gateway_order_id')
        gateway_signature = data.get('gateway_signature')
        
        if not all([payment_id, gateway_payment_id, gateway_order_id, gateway_signature]):
            return JsonResponse({'success': False, 'error': 'Missing payment details'}, status=400)
        
        # Get payment record and verify it belongs to the user
        payment = get_object_or_404(Payment, id=payment_id, user=request.user, obj_type=choices.PaymentObjectType.COUNSELOR)
        
        # Check if payment is already successful
        if payment.is_success == choices.YesNoChoices.YES:
            return JsonResponse({
                'success': True, 
                'message': 'Payment already processed successfully',
                'already_paid': True
            })
        
        # Update payment with Razorpay details
        payment_status = payment.update_payment(gateway_payment_id, gateway_order_id, gateway_signature)
        
        if payment_status:
            return JsonResponse({'success': True, 'message': 'Payment verified and saved successfully'})
        else:
            return JsonResponse({'success': False, 'error': 'Payment verification failed'}, status=400)
            
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class CourseStartsView(View):
    """
    Old course view - redirects to new course learning page for better UX.
    """
    def get(self, request, counselor_id):
        # Redirect to new course learning page
        return redirect(reverse('counselor:course_learning', args=[counselor_id]))
    
    def get_old(self, request, counselor_id):
        """Old implementation - kept for reference but not used"""
        from core import choices
        from django.http import Http404
        
        # Retrieve the counselor using the provided ID
        counselor = get_object_or_404(Counselor, id=counselor_id)
        
        # Security check: Ensure counselors can only access their own course
        if request.user.user_type == choices.UserType.COUNSELOR:
            # If user is a counselor, they must be the owner of this counselor record
            if counselor.coun_user != request.user:
                raise Http404("You don't have permission to access this counselor's course.")
        
        user = request.user
        course_with_related_data = CounselorCourse.objects.prefetch_related(
                'chapters__parts__quizzes__questions__answers'
            ).first()

        # Initialize defaults
        part_ids = []
        video_progress = {}
        last_part = None
        chapter_count = 0
        part_count = 0
        question_count = 0
        completed_parts = 0

        if course_with_related_data:
            # Get part IDs and progress data only if course exists
            part_ids = course_with_related_data.chapters.all().values_list('parts__id', flat=True)
            if part_ids:
                progress_data = VideoProgress.objects.filter(user=user, video_id__in=[f"video-{part_id}" for part_id in part_ids])
                video_progress = {int(progress.video_id.split('-')[1]): progress.completed for progress in progress_data}

            last_part = Part.objects.filter(chapter__course=course_with_related_data).last()

            completed_parts = sum(1 for completed in video_progress.values() if completed)

            # Count chapters, parts, and questions
            chapter_count = course_with_related_data.chapters.count()
            for chapter in course_with_related_data.chapters.all():
                part_count += chapter.parts.count()
                for part in chapter.parts.all():
                    question_count += part.quizzes.values('questions').count()  # Count questions in quizzes

        # Calculate progress percentage
        progress_percentage = int((completed_parts / part_count * 100)) if part_count > 0 else 0
        # Prepare the context for the template

        

        # Get notes for the user
        notes = Notes.objects.filter(user=user) if user.is_authenticated else []
        
        # Get certification if exists
        certification = CounselorCertification.objects.filter(user=user).first()
        
        # Get quiz results and scores
        try:
            quiz_result = QuizResults.objects.get(user=user)
            scores = quiz_result.scores if isinstance(quiz_result.scores, list) else []
        except QuizResults.DoesNotExist:
            scores = []
        
        # Create a dictionary to track quiz completion status by part_id
        quiz_completion_status = {}
        for score in scores:
            part_id = score.get('part_id')
            if part_id:
                quiz_completion_status[part_id] = True

        # Get current chapter index from URL parameter (default to 0)
        current_chapter_index = int(request.GET.get('chapter', 0))
        
        # Get all chapters
        chapters_list = []
        if course_with_related_data:
            chapters_list = list(course_with_related_data.chapters.all())
            # Ensure index is within bounds
            if current_chapter_index >= len(chapters_list):
                current_chapter_index = len(chapters_list) - 1
            if current_chapter_index < 0:
                current_chapter_index = 0
        
        # Get current chapter
        current_chapter = chapters_list[current_chapter_index] if chapters_list and current_chapter_index < len(chapters_list) else None
        
        # Check if current chapter is completed
        is_chapter_completed = False
        if current_chapter and current_chapter.parts.exists():
            all_parts_completed = True
            for part in current_chapter.parts.all():
                if not video_progress.get(part.id, False):
                    all_parts_completed = False
                    break
            is_chapter_completed = all_parts_completed
        
        # Check if this is the last chapter
        is_last_chapter = current_chapter_index == len(chapters_list) - 1 if chapters_list else False
        
        # Check if next chapter exists
        has_next_chapter = current_chapter_index < len(chapters_list) - 1 if chapters_list else False

        context = {
            'counselors': counselor,
            'course': course_with_related_data,
            'chapter_count': chapter_count,
            'part_count': part_count,
            'question_count': question_count,
            'video_progress': video_progress,
            'last': last_part,
            'progress_percentage': progress_percentage,
            'notes': notes,
            'certification': certification,
            'scores': scores,
            'quiz_completion_status': quiz_completion_status,
            'current_chapter_index': current_chapter_index,
            'current_chapter': current_chapter,
            'chapters_list': chapters_list,
            'is_chapter_completed': is_chapter_completed,
            'is_last_chapter': is_last_chapter,
            'has_next_chapter': has_next_chapter,
            # Add other context variables as needed
        }

        # Render the template with the context
        return render(request, 'template20/counselor/course_information.html', context)

# @csrf_exempt  # Use this only if you need to bypass CSRF verification for testing. Not recommended for production.
def Counselorenrolledcourse(request):
    if request.method == 'POST':
        results = {}

        # Loop through each part in the submitted data
        for part_id in request.POST.getlist('part_id'):
            part = get_object_or_404(Part, id=part_id)
            results[part.id] = {
                'quiz_results': [],  # List to hold results for quizzes in this part
                'correct_count': 0,
                'incorrect_count': 0,
            }

            for quiz in part.quizzes.all():
                total_questions_each_quiz = quiz.questions.all().count()
                correct_answers_map = {}

                for question in quiz.questions.all():
                    user_answer_id = request.POST.get(f'question_{question.id}')
                    user_answer = None

                    if user_answer_id:
                        try:
                            user_answer = QuizAnswers.objects.get(id=user_answer_id)
                        except QuizAnswers.DoesNotExist:
                            pass

                    correct_answer = question.answers.filter(is_correct=True).first()
                    is_correct = user_answer == correct_answer if user_answer else False

                    # Increment counts based on whether the answer is correct
                    if is_correct:
                        results[part.id]['correct_count'] += 1
                    else:
                        results[part.id]['incorrect_count'] += 1
                    
                    # Fill correct_option based on user and correct answers
                    correct_answers_map[f'ques_{question.id}'] = {
                        'correct_ans': correct_answer.answer_text if correct_answer else None,
                        'selected_ans': user_answer.answer_text if user_answer else None,
                    }

                results[part.id]['quiz_results'].append({
                    'quiz_id': quiz.id,
                    'total_questions_in_quiz': total_questions_each_quiz,
                    'correct_option': correct_answers_map,
                    'quiz_result': {
                        'correct_answers': results[part.id]['correct_count'],
                        'incorrect_answers': results[part.id]['incorrect_count'],
                    }
                })

        # Prepare final data structure
        data = {
            "userId": request.user.id,
            "scores": []
        }

        for part_id, part_results in results.items():
            for quiz in part_results['quiz_results']:
                score_info = {
                    "part_id": part_id,
                    "quiz_id": quiz["quiz_id"],
                    "total_questions_in_quiz": quiz["total_questions_in_quiz"],
                    "correct_option": quiz["correct_option"],
                    "quiz_result": {
                        "correct_answers": quiz['quiz_result']['correct_answers'],
                        "incorrect_answers": quiz['quiz_result']['incorrect_answers'],
                    },
                }
                data['scores'].append(score_info)
        # Convert the dictionary to a JSON string

       
        json_data = json.dumps(data, indent=4)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get the existing QuizResults instance for the user
        user = get_object_or_404(User, id=data['userId'])
        quiz_results, created = QuizResults.objects.get_or_create(user=user)
     
        new_score_data = data["scores"]  # Directly use 'data' as it is a list of score data

        # Ensure scores is a list before modifying it
        if isinstance(quiz_results.scores, str):
            # If 'scores' is a string (e.g., JSON string), load it as a list
            quiz_results.scores = json.loads(quiz_results.scores)
        elif not isinstance(quiz_results.scores, list):
            # If it's neither a string nor a list, initialize it as an empty list
            quiz_results.scores = []

        # Loop through each new score in the data
        for new_score in new_score_data:
            part_id = new_score["part_id"]
            quiz_id = new_score["quiz_id"]
            # Check if the part_id and quiz_id exist in the current scores
            existing_score = None
            for score in quiz_results.scores:
                if score["part_id"] == part_id and score["quiz_id"] == quiz_id:
                    existing_score = score
                    break

            if existing_score:
                # If the score data exists, update it with the new data
                existing_score.update(new_score)
            else:
                # If no matching part_id and quiz_id, append the new data
                quiz_results.scores.append(new_score)  # Append new_score instead of new_score_data

        # Save the updated data
        
        quiz_results.save()
        return render(request, 'results.html', {'json_data': json_data})

    try:
        # Prefetch parts, their quizzes, questions, and answers
        chapters = Chapter.objects.prefetch_related(
            'parts__quizzes__questions__answers'
        ).all()
    except Chapter.DoesNotExist:
        chapters = []

    context = {
        'chapters': chapters
    }

    return render(request, 'topteenfrontend/user/app/counselor-enrolled-course.html', context)

@login_required(login_url=reverse_lazy('users:login'))
def CounselorDashboard(request, coun_id=None):
    from core import choices
    from django.http import Http404, JsonResponse
    
    counselor = get_object_or_404(Counselor, id=coun_id)
    
    # Security check: Ensure counselors can only access their own dashboard
    if request.user.user_type == choices.UserType.COUNSELOR:
        # If user is a counselor, they must be the owner of this counselor record
        if counselor.coun_user != request.user:
            raise Http404("You don't have permission to access this counselor's dashboard.")
    
    # Check if this is an AJAX request for specific data
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data_type = request.GET.get('data_type', '')
        
        if data_type == 'students':
            # Optimized AJAX handler for student table only
            return _get_counselor_student_table_ajax(request, counselor, coun_id)
        elif data_type == 'stats':
            # AJAX handler for statistics
            return _get_counselor_stats_ajax(counselor)
        elif data_type == 'sessions':
            # AJAX handler for session chart data
            return _get_counselor_sessions_ajax(counselor, coun_id)
    
    # Get counselor's associated institute
    counselor_institute = counselor.counselor_admin
    
    # Lightweight initial page load - only essential data
    # Use optimized queries with select_related and prefetch_related
    # Pass both counselor and institute to ensure correct filtering regardless of logged-in user's role
    # This returns ONLY assigned students (matching production code)
    students_to_display = get_students_by_role(request.user, counselor=counselor, institute=counselor_institute)
    
    # Get assigned student IDs for follow-up filtering (students_to_display already contains assigned students)
    assigned_student_ids = students_to_display.values_list('id', flat=True) if hasattr(students_to_display, 'values_list') else [s.id for s in students_to_display]
    
    # Retrieve follow-up data for assigned students (matching production code - filter only by counselor)
    follow_ups = FollowUpStatus.objects.filter(
        counselor=counselor,
        student_id__in=assigned_student_ids
    ).select_related('student', 'student__student')
    
    # Get basic counts efficiently - only for assigned students
    total_is_followed_up_count = follow_ups.filter(is_followed_up=True).count()
    
    # Get class counts and sections efficiently (only for filters)
    class_and_sections = get_class_and_sections_by_role(request.user, students_to_display)
    class_counts = get_class_counts(students_to_display)
    unique_streams = get_unique_streams_by_role(request.user, students_to_display)
    
    # For initial load, only get minimal data needed for filters
    # Heavy processing (results_data, merged_data) will be done via AJAX
    per_page = request.GET.get('per_page', '10')

    counselor_course = CounselorCourse.objects.only("title").first()
    counselor_course_title = (
        (counselor_course.title or "").strip() or "Career Counseling Course"
        if counselor_course
        else "Career Counseling Course"
    )
    counselor_user = counselor.coun_user
    # Same users as course detail / payment (request.user) and counselor profile (coun_user)
    _dashboard_course_users = []
    _seen_uid = set()
    for u in (
        request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
        counselor_user,
    ):
        if u and u.pk not in _seen_uid:
            _seen_uid.add(u.pk)
            _dashboard_course_users.append(u)

    counselor_course_enrolled = False
    for u in _dashboard_course_users:
        if _counselor_course_access_for_user(u, counselor_course):
            counselor_course_enrolled = True
            break

    counselor_course_start_url = reverse("counselor:course_learning", args=[coun_id])
    counselor_course_enroll_url = reverse("counselor:CounselorCoursepayment")
    counselor_course_curriculum_url = reverse("counselor:counselor_course_detail")
    show_counselor_course_on_dashboard = bool(counselor_course)

    counselor_course_cta = "Enroll"
    if counselor_course_enrolled and counselor_course:
        counselor_course_cta = "Start"
        part_ids = list(
            Part.objects.filter(chapter__course=counselor_course).values_list("id", flat=True)
        )
        if part_ids:
            video_keys = [f"video-{pid}" for pid in part_ids]
            for u in _dashboard_course_users:
                if VideoProgress.objects.filter(user=u, video_id__in=video_keys).exists():
                    counselor_course_cta = "Resume"
                    break
            if counselor_course_cta == "Start":
                for u in _dashboard_course_users:
                    try:
                        qr = QuizResults.objects.get(user=u)
                        scores = qr.scores
                        if isinstance(scores, str):
                            scores = json.loads(scores) if (scores and scores.strip()) else []
                        elif not isinstance(scores, list):
                            scores = []
                        if scores:
                            counselor_course_cta = "Resume"
                            break
                    except (QuizResults.DoesNotExist, ValueError, TypeError):
                        pass

        if any(_is_course_fully_completed(u) for u in _dashboard_course_users):
            counselor_course_cta = "Completed"

    counselor_course_progress_pct = 0
    counselor_course_certificate_url = None
    if counselor_course:
        _progress_user = None
        if (
            request.user.is_authenticated
            and _counselor_course_access_for_user(request.user, counselor_course)
        ):
            _progress_user = request.user
        elif counselor_user and _counselor_course_access_for_user(
            counselor_user, counselor_course
        ):
            _progress_user = counselor_user
        if _progress_user:
            counselor_course_progress_pct = _counselor_course_progress_percentage(
                _progress_user, counselor_course
            )
            if counselor_course_enrolled and _is_course_fully_completed(_progress_user):
                _check_and_issue_certificate(_progress_user, coun_id)
                if CounselorCertification.objects.filter(user=_progress_user).exists():
                    counselor_course_certificate_url = reverse(
                        "counselor:view_certificate", args=[coun_id]
                    )

    # Initialize lightweight context for initial page load
    context = {
        'counselors': counselor,
        'coun_id': coun_id,
        'counselor_institute': counselor_institute,  # Add institute to context for verification
        'per_page': per_page,
        'class_and_sections': class_and_sections,
        'class_counts': class_counts,
        'unique_streams': unique_streams,
        'total_is_followed_up_count': total_is_followed_up_count,
        'students_count': students_to_display.count() if hasattr(students_to_display, 'count') else len(students_to_display),
        'key': settings.RAZORPAY_API_KEY,
        'secrit': settings.RAZORPAY_API_SECRET,
        'counselor_course_enrolled': counselor_course_enrolled,
        'counselor_course_title': counselor_course_title,
        'counselor_course_start_url': counselor_course_start_url,
        'counselor_course_enroll_url': counselor_course_enroll_url,
        'counselor_course_curriculum_url': counselor_course_curriculum_url,
        'show_counselor_course_on_dashboard': show_counselor_course_on_dashboard,
        'counselor_course_cta': counselor_course_cta,
        'counselor_course_progress_pct': counselor_course_progress_pct,
        'counselor_course_certificate_url': counselor_course_certificate_url,
        'counselor_course_notes_count': (
            Notes.objects.filter(user=request.user, part__chapter__course=counselor_course).count()
            if counselor_course
            else 0
        ),
        'counselor_course_notes_url': (
            reverse("counselor:course_learning", args=[coun_id]) + "?open_notes=1"
            if counselor_course
            else ""
        ),
    }
    
    # Only load student table data if explicitly requested (not on initial page load)
    # This will be loaded via AJAX after page loads
    if request.GET.get('load_table', 'false') == 'true':
        # Load full table data
        context.update(_get_counselor_full_table_context(request, counselor, students_to_display, follow_ups, per_page))
    
    return render(request, 'template20/counselor/counselor_dashboard.html', context)


def _get_counselor_student_table_ajax(request, counselor, coun_id):
    """Optimized AJAX handler for student table with pagination."""
    from django.core.paginator import Paginator
    
    # Get counselor's associated institute
    counselor_institute = counselor.counselor_admin
    
    # Get students with optimized query - ONLY assigned students (matching production code)
    # Pass both counselor and institute to ensure correct filtering regardless of logged-in user's role
    students_to_display = get_students_by_role(request.user, counselor=counselor, institute=counselor_institute)
    
    # Get assigned student IDs for follow-up filtering (students_to_display already contains assigned students)
    assigned_student_ids = students_to_display.values_list('id', flat=True) if hasattr(students_to_display, 'values_list') else [s.id for s in students_to_display]
    
    # Retrieve follow-up data for assigned students (matching production code - filter only by counselor)
    follow_ups = FollowUpStatus.objects.filter(
        counselor=counselor,
        student_id__in=assigned_student_ids
    ).select_related('student', 'student__student')
    
    # Build follow_up_data efficiently
    follow_up_data = {}
    for follow_up in follow_ups:
        student_id = follow_up.student.id
        if student_id not in follow_up_data:
            follow_up_data[student_id] = {'follow_ups': []}
        follow_up_data[student_id]['follow_ups'].append({
            'is_followed_up': follow_up.is_followed_up,
            'message': follow_up.message,
            'last_follow_up_date': follow_up.last_follow_up_date,
            'next_follow_up_date': follow_up.next_follow_up_date,
        })
    
    # Build merged_data only for current page
    merged_data = []
    for student in students_to_display:
        merged_data.append({
            'student': student,
            'follow_ups': follow_up_data.get(student.id, {'follow_ups': []})['follow_ups'],
        })
    
    # Sort only once
    merged_data = sorted(merged_data, key=lambda x: x['student'].student.name.lower())
    
    # Get results_data only for filtered students (optimize this)
    # Limit to first 100 students for results_data to avoid N+1
    students_for_results = students_to_display[:100] if hasattr(students_to_display, '__getitem__') else list(students_to_display)[:100]
    results_data = get_results_data_for_students(students_for_results)
    
    # Apply filters
    merged_data = apply_student_filters(merged_data, request, results_data)
    
    # Pagination
    per_page = request.GET.get('per_page', '10')
    if per_page == 'all':
        students_page = merged_data
        paginator = None
    else:
        try:
            per_page_int = int(per_page)
            if per_page_int not in [10, 100]:
                per_page_int = 10
        except (ValueError, TypeError):
            per_page_int = 10
        
        paginator = Paginator(merged_data, per_page_int)
        page_number = request.GET.get('page', 1)
        students_page = paginator.get_page(page_number)
    
    # Get class counts and sections for filters
    class_and_sections = get_class_and_sections_by_role(request.user, students_to_display)
    class_counts = get_class_counts(students_to_display)
    unique_streams = get_unique_streams_by_role(request.user, students_to_display)
    
    context = {
        'counselors': counselor,
        'students': students_page,
        'paginator': paginator,
        'per_page': per_page,
        'results_data': results_data,
        'class_and_sections': class_and_sections,
        'class_counts': class_counts,
        'unique_streams': unique_streams,
        'coun_id': coun_id,
        'follow_up_data': follow_up_data,
        'merged_data': merged_data,
    }
    
    return render(request, 'template20/counselor/counselor_dashboard_table.html', context)


def _get_counselor_stats_ajax(counselor):
    """AJAX handler for statistics."""
    # Get counselor's associated institute
    counselor_institute = counselor.counselor_admin
    
    # Get ONLY assigned students (matching production code)
    # Pass both counselor and institute to ensure correct filtering regardless of logged-in user's role
    students_to_display = get_students_by_role(counselor.coun_user, counselor=counselor, institute=counselor_institute)
    
    # Get assigned student IDs for follow-up filtering (students_to_display already contains assigned students)
    assigned_student_ids = students_to_display.values_list('id', flat=True) if hasattr(students_to_display, 'values_list') else [s.id for s in students_to_display]
    
    # Count follow-ups only for assigned students (matching production code - filter only by counselor)
    total_is_followed_up_count = FollowUpStatus.objects.filter(
        counselor=counselor,
        student_id__in=assigned_student_ids,
        is_followed_up=True
    ).count()
    
    # Count counseled students (follow_up_status='completed') only for assigned students
    counseled_count = FollowUpStatus.objects.filter(
        counselor=counselor,
        student_id__in=assigned_student_ids,
        follow_up_status='completed'
    ).values('student_id').distinct().count()
    
    return JsonResponse({
        'total_students': students_to_display.count() if hasattr(students_to_display, 'count') else len(students_to_display),
        'total_followed_up': total_is_followed_up_count,
        'total_counseled': counseled_count,
    })


def _get_counselor_sessions_ajax(counselor, coun_id):
    """AJAX handler for session chart data."""
    from django.db.models import Count
    
    # Get counselor's associated institute
    counselor_institute = counselor.counselor_admin
    
    # Get ONLY assigned students (matching production code)
    # Pass both counselor and institute to ensure correct filtering regardless of logged-in user's role
    students_to_display = get_students_by_role(counselor.coun_user, counselor=counselor, institute=counselor_institute)
    
    # Get assigned student IDs for session filtering (students_to_display already contains assigned students)
    assigned_student_ids = students_to_display.values_list('id', flat=True) if hasattr(students_to_display, 'values_list') else [s.id for s in students_to_display]
    
    # Filter sessions only for assigned students (matching production code - filter only by counselor)
    sessions_data = (
        FollowUpStatus.objects
        .filter(counselor_id=coun_id, student_id__in=assigned_student_ids)
        .values('last_follow_up_date')
        .annotate(session_count=Count('id'))
    )
    
    week_data = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    reference_date = date.today()
    
    for session in sessions_data:
        try:
            session_date = session.get('last_follow_up_date')
            if session_date:
                if isinstance(session_date, str):
                    if 'T' in session_date:
                        session_date = datetime.fromisoformat(session_date.split('T')[0]).date()
                    else:
                        session_date = datetime.strptime(session_date, "%Y-%m-%d").date()
                
                day_of_week = session_date.weekday()
                if day_of_week < 6:
                    week_data[day_of_week] += session.get('session_count', 0)
        except (KeyError, ValueError, TypeError):
            continue
    
    days_since_monday = reference_date.weekday()
    week_start = reference_date - timedelta(days=days_since_monday)
    
    final_data = []
    for day, count in week_data.items():
        day_date = week_start + timedelta(days=day)
        final_data.append({
            "day": day_date.strftime("%Y-%m-%d"),
            "session_count": count
        })
    
    couns_sessions_data = [{
        'counselor_id': counselor.id,
        'counselor_name': counselor.counselor_name,
        'sessions': final_data
    }]
    
    return JsonResponse({'sessions_data': couns_sessions_data})


def _get_counselor_full_table_context(request, counselor, students_to_display, follow_ups, per_page):
    """Get full table context - used only when explicitly needed."""
    # This is the old heavy processing logic, but only called when needed
    follow_up_data = {}
    total_is_followed_up_count = 0
    
    for follow_up in follow_ups:
        if follow_up.student.id not in follow_up_data:
            follow_up_data[follow_up.student.id] = {'follow_ups': []}
        follow_up_data[follow_up.student.id]['follow_ups'].append({
            'is_followed_up': follow_up.is_followed_up,
            'message': follow_up.message,
            'last_follow_up_date': follow_up.last_follow_up_date,
            'next_follow_up_date': follow_up.next_follow_up_date,
        })
        if follow_up.is_followed_up:
            total_is_followed_up_count += 1
    
    merged_data = []
    for student in students_to_display:
        merged_data.append({
            'student': student,
            'follow_ups': follow_up_data.get(student.id, {'follow_ups': []})['follow_ups'],
        })
    
    merged_data = sorted(merged_data, key=lambda x: x['student'].student.name.lower())
    
    # Limit results_data processing
    students_for_results = students_to_display[:100] if hasattr(students_to_display, '__getitem__') else list(students_to_display)[:100]
    results_data = get_results_data_for_students(students_for_results)
    merged_data = apply_student_filters(merged_data, request, results_data)
    
    # Pagination
    if per_page == 'all':
        students_page = merged_data
        paginator = None
    else:
        try:
            per_page_int = int(per_page)
            if per_page_int not in [10, 100]:
                per_page_int = 10
        except (ValueError, TypeError):
            per_page_int = 10
        
        paginator = Paginator(merged_data, per_page_int)
        page_number = request.GET.get('page', 1)
        students_page = paginator.get_page(page_number)
    
    return {
        'students': students_page,
        'paginator': paginator,
        'results_data': results_data,
        'total_is_followed_up_count': total_is_followed_up_count,
        'follow_up_data': follow_up_data,
        'merged_data': merged_data,
    }


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class CounselorEnrolledCourseView(View):
    template_name = 'template20/counselor/enrolled_course.html'

    def post(self, request, *args, **kwargs):        

        results = {}
        # Ensure part_id is being processed correctly
        for part_id in request.POST.getlist('part_id'):
            part = get_object_or_404(Part, id=part_id)
            results[part.id] = {'quiz_results': [], 'correct_count': 0, 'incorrect_count': 0}
        
            for quiz in part.quizzes.all():
                total_questions_each_quiz = quiz.questions.count()
                correct_answers_map = {}

                for question in quiz.questions.all():
                    user_answer_id = request.POST.get(f'question_{question.id}')

                    user_answer = None
                    if user_answer_id:
                        try:
                            user_answer = QuizAnswers.objects.get(id=user_answer_id)
                        except QuizAnswers.DoesNotExist:
                            pass
                    
                    correct_answer = question.answers.filter(is_correct=True).first()
                    is_correct = user_answer == correct_answer if user_answer else False
                    if is_correct:
                        results[part.id]['correct_count'] += 1
                    else:
                        results[part.id]['incorrect_count'] += 1
                    
                    # Fill correct_option based on user and correct answers
                    correct_answers_map[f'ques_{question.id}'] = {
                        'correct_ans': correct_answer.answer_text if correct_answer else None,
                        'selected_ans': user_answer.answer_text if user_answer else None,
                    }


                results[part.id]['quiz_results'].append({
                    'quiz_id': quiz.id,
                    'total_questions_in_quiz': total_questions_each_quiz,
                    'correct_option': correct_answers_map,
                    'quiz_result': {
                        'correct_answers': results[part.id]['correct_count'],
                        'incorrect_answers': results[part.id]['incorrect_count'],
                    }
                })

        # Prepare final data structure
        data = {
            "userId": request.user.id,
            "scores": []
        }
        
        for part_id, part_results in results.items():
            for quiz in part_results['quiz_results']:
                score_info = {
                    "part_id": part_id,
                    "quiz_id": quiz["quiz_id"],
                    "total_questions_in_quiz": quiz["total_questions_in_quiz"],
                    "correct_option": quiz["correct_option"],
                    "quiz_result": {
                        "correct_answers": quiz['quiz_result']['correct_answers'],
                        "incorrect_answers": quiz['quiz_result']['incorrect_answers'],
                    },
                }
                data['scores'].append(score_info)
                
        user = get_object_or_404(User, id=data['userId'])
        quiz_results, created = QuizResults.objects.update_or_create(user=user)
        if isinstance(quiz_results.scores, str) or not isinstance(quiz_results.scores, list):
            quiz_results.scores = []
        for new_score in data["scores"]:
            part_id = new_score["part_id"]
            quiz_id = new_score["quiz_id"]
            existing_score = next((score for score in quiz_results.scores if score["part_id"] == part_id and score["quiz_id"] == quiz_id), None)

            
            if existing_score:
                existing_score.update(new_score)
                messages.success(request, "Thank you! Successfully updated data into db.")
            else:
                quiz_results.scores.append(new_score)
                messages.success(request, "Thank you! Successfully created data into db.")

        
        # Save the updated data
        quiz_results.save()
        # url = request.META.get('HTTP_REFERER'){{url ('counselor:counselor_enrolled_course')}}
        
        return redirect('counselor:counselor_enrolled_course')
    
    def get(self, request, *args, **kwargs):
        try:
            # Prefetch parts, their quizzes, questions, and answers
            course_with_related_data = CounselorCourse.objects.prefetch_related(
                'chapters__parts__quizzes__questions__answers'
            ).first()

            # chapter = Chapter.objects.prefetch_related('parts').get(id=chapter_id)
            user = request.user
            
            # Check if user is authenticated
            if not user.is_authenticated:
                from django.contrib.auth import redirect_to_login
                return redirect_to_login(request.get_full_path())
            
            # Check if course exists
            if not course_with_related_data:
                from django.http import Http404
                raise Http404("No course found.")

            # Prepare progress data
            # Prepare video progress
            video_progress = self.get_completed_status(user, course_with_related_data)

            # Fetch the last part based on its ID
            # c = Part.objects.last()

            # Get the last part of the course
            last_part = Part.objects.filter(chapter__course=course_with_related_data).last()

            certification = CounselorCertification.objects.filter(user=request.user).first()  # Assuming one certification per user
            if certification:
                # If a certificate already exists for the user, use the existing code
                certificate_code = certification.certificate_code
            else:
                # Generate a new certificate code
                latest_cert = CounselorCertification.objects.last()
                if latest_cert:
                    certificate_code = f"TPTC{latest_cert.id + 1:04d}"  # Increment last id by 1
                else:
                    certificate_code = "TPTC0001"         

            # Access the last part's details
            if last_part:
                # Check if video progress for the last part exists and is True
                if video_progress.get(last_part.id, False):  # Assuming last_part.id is used as last_id
                    try:

                        quiz_result = QuizResults.objects.get(user=request.user)
                        scores = quiz_result.scores if isinstance(quiz_result.scores, list) else []

                        # Initialize counters
                        total_questions = 0
                        total_correct_answers = 0

                        # Iterate through each quiz result
                        for quiz in scores:
                            total_questions += quiz.get("total_questions_in_quiz", 0)
                            total_correct_answers += quiz.get("quiz_result", {}).get("correct_answers", 0)

                        # Calculate score percentage
                        if total_questions > 0:
                            score_percentage = (total_correct_answers / total_questions) * 100
                        else:
                            score_percentage = 0

                        # Determine the grade based on the score percentage
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
                            grade = "D"  # Fail or below 50%

                        certification, created = CounselorCertification.objects.update_or_create(
                            user=user,
                            grade=grade,  # Fields to identify the record
                            defaults={  # Fields to update or create with
                                'certificate_code': certificate_code,
                            }
                        )

                        if created:
                            print("A new certification record was created.")
                        else:
                            print("An existing certification record was updated.")

                        # Output the results (for debugging purposes)
                        

                    except QuizResults.DoesNotExist:
                        print("No quiz results found for this user.")
                else:
                    print("Video progress for this part is not completed or doesn't exist.")

            else:
                print("No parts found for the course.")

            # video_progress = VideoProgress.objects.filter(user=request.user)
            notes = Notes.objects.filter(user=request.user)
        except Chapter.DoesNotExist:
            course_with_related_data = []
            notes = []
            video_progress = []
            last_part = []
            certification = []

        try: 

            quiz_result = QuizResults.objects.get(user=user)
            scores = quiz_result.scores if isinstance(quiz_result.scores, list) else []

            found = {}
            answers_data = {}  # To store correct and incorrect counts for each part
            correct_selected = {}
            correct_ans_selected={}

            for chapter in course_with_related_data.chapters.all():
                
                for part in chapter.parts.all():
                    part_scores = [score for score in scores if score.get('part_id') == part.id]

                    # Extract correct and incorrect counts from the scores
                    correct_count = sum(score['quiz_result']['correct_answers'] for score in part_scores)
                    incorrect_count = sum(score['quiz_result']['incorrect_answers'] for score in part_scores)
                    found[part.id] = bool(part_scores)  # Mark as found if there are scores for this part
                    answers_data[part.id] = {
                        'correct': correct_count,
                        'incorrect': incorrect_count
                    }
                    
                    # Lists to hold correct and incorrect answers
                    correct_answers = []
                    incorrect_answers = []

                    # Loop through the scores
                    for quiz in scores:
                        part_id = quiz['part_id']
                        for question_key, question_data in quiz['correct_option'].items():
                            selected_answer = question_data['selected_ans'] # Or question_data['answer_text'] if you have the text
                            correct_selected.setdefault(part_id, {})[question_key] = selected_answer

                            correct_ans = question_data['correct_ans'] # Or question_data['answer_text'] if you have the text
                            correct_ans_selected.setdefault(part_id, {})[question_key] = correct_ans

                            # if selected_answer == correct_answer:
                            #     correct_answers.append((part_id, question_key, correct_answer, selected_answer))
                            # else:
                            #     incorrect_answers.append((part_id, question_key, correct_answer, selected_answer))
            print("answers_data ",answers_data)
            print("correct_selected ",correct_selected)
            print("correct_ans_selected ",correct_ans_selected)
            print("found",found)
        except QuizResults.DoesNotExist:
            scores = []
            found = {}
            answers_data = {}
            part_scores = []
            correct_answers = []
            incorrect_answers = []
            correct_selected = []
            correct_ans_selected =[]

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            scores = []
            found = {}
            answers_data = {}
            part_scores = []
            correct_answers = []
            incorrect_answers = []
            correct_selected = []
            correct_ans_selected =[]

        resume_course_url = None
        if request.user.is_authenticated:
            _resume_counselor = Counselor.objects.filter(coun_user=request.user).first()
            if _resume_counselor:
                resume_course_url = reverse(
                    "counselor:course_learning", args=[_resume_counselor.id]
                )

        context = {
            'user': '336',
            'notes':notes,
            'last':last_part,
            'video_progress':video_progress,
            'course': course_with_related_data,
            'certification':certification,
            'scores':scores,
            'found' : found,
            'answers_data': answers_data,
            'part_scores': part_scores,
            'correct_answers':correct_answers,
            'incorrect_answers':incorrect_answers,
            'correct_selected':correct_selected,
            'correct_ans_selected':correct_ans_selected,
            'resume_course_url': resume_course_url,
        }

        return render(request, self.template_name, context)

    def get_completed_status(self, user, course):
        """
        Retrieve the `completed` status for all parts in the course for the given user.
        """
        if not user or not user.is_authenticated:
            return {}
        if not course:
            return {}
        part_ids = course.chapters.all().values_list('parts__id', flat=True)
        progress_data = VideoProgress.objects.filter(user=user, video_id__in=[f"video-{part_id}" for part_id in part_ids])
        video_progress = {int(progress.video_id.split('-')[1]): progress.completed for progress in progress_data}
        return video_progress



import traceback
from django.utils.decorators import method_decorator
from django.middleware.csrf import get_token
# <-- testing the form submission with the ajax-->
from django.views.decorators.csrf import csrf_protect
@csrf_protect

@csrf_exempt
def get_progress_and_duration(request, video_id):
    if request.method == 'GET':
        try:
            # Ensure the user is authenticated
            user = request.user
            if not user.is_authenticated:
                return JsonResponse({'status': 'fail', 'error': 'User not authenticated'}, status=403)

            # Retrieve the progress and duration for the specific user and video
            video_progress = VideoProgress.objects.filter(user=user, video_id=video_id).first()

            if video_progress:
                progress_data = {
                    'progress': video_progress.progress,
                    'duration': video_progress.duration
                }
                return JsonResponse({'status': 'success', **progress_data}, status=200)
            else:
                # Return success with default values instead of 404 to avoid console errors
                return JsonResponse({
                    'status': 'success', 
                    'progress': 0, 
                    'duration': None
                }, status=200)

        except Exception as e:
            logger.error(f"Error retrieving video progress: {e}")
            return JsonResponse({'status': 'fail', 'error': str(e)}, status=500)

    return JsonResponse({'status': 'fail', 'error': 'Invalid request method'}, status=400)


@login_required(login_url=reverse_lazy('users:login'))
def case_study_pdf(request, counselor_id, case_id):
    """
    Serve case study PDFs (local folder or remote URL) with auth.

    Behavior:
    - CaseStudy.pdf_url is a full https URL: fetched and served same-origin (avoids CORS for PDF.js).
    - CaseStudy.pdf_url is a filename/relative path:
      - If Part.case_study_folder_url starts with http(s): join and fetch.
      - Else treat Part.case_study_folder_url as a local directory path (absolute or relative to BASE_DIR).
      - If no folder is set: fall back to <BASE_DIR>/case_studies.
    """
    from core import choices
    from django.http import Http404, FileResponse, HttpResponse
    from pathlib import Path
    import urllib.error
    import urllib.request

    counselor = get_object_or_404(Counselor, id=counselor_id)
    if request.user.user_type == choices.UserType.COUNSELOR and counselor.coun_user != request.user:
        raise Http404("You don't have permission to access this counselor's course.")

    try:
        cs = CaseStudy.objects.select_related("part").get(pk=case_id)
    except CaseStudy.DoesNotExist:
        raise Http404("Case study not found.")

    part = cs.part
    if not part:
        raise Http404("Invalid case study.")

    raw = (cs.pdf_url or "").strip()
    if not raw:
        raise Http404("Missing PDF url.")

    def _serve_remote(url: str):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "TopTeen-case-study-proxy/1.0"},
            )
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
            raise Http404("PDF unavailable.")
        resp = HttpResponse(data, content_type="application/pdf")
        resp["Content-Disposition"] = 'inline; filename="case-study.pdf"'
        resp["Cache-Control"] = "private, max-age=0, no-store"
        return resp

    # Full URL
    if raw.startswith("http://") or raw.startswith("https://"):
        return _serve_remote(raw)

    # Prevent traversal for relative pdf_url
    safe_name = raw.replace("\\", "/").strip()
    if safe_name.startswith("/") or ".." in safe_name.split("/"):
        raise Http404("Invalid filename.")

    base = (getattr(part, "case_study_folder_url", None) or "").strip()
    if base.startswith("http://") or base.startswith("https://"):
        url = base.rstrip("/") + "/" + safe_name.lstrip("/")
        return _serve_remote(url)

    # Local file base directory
    if base:
        base_dir = Path(base)
        if not base_dir.is_absolute():
            base_dir = (Path(settings.BASE_DIR) / base_dir)
    else:
        base_dir = Path(settings.BASE_DIR) / "case_studies"
    base_dir = base_dir.resolve()

    pdf_path = (base_dir / safe_name).resolve()
    if (base_dir not in pdf_path.parents) and (pdf_path != base_dir):
        raise Http404("Invalid path.")
    if not pdf_path.exists() or not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise Http404("File not found.")

    resp = FileResponse(open(pdf_path, "rb"), content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{pdf_path.name}"'
    resp["Cache-Control"] = "private, max-age=0, no-store"
    return resp


@csrf_exempt
def update_progress(request):
    if request.method == 'POST':
        try:            
            data = json.loads(request.body)
            video_id = data.get('video_id')
            progress = data.get('progress')
            duration = data.get('duration')

            # Ensure user is authenticated
            user = request.user
            if not user.is_authenticated:
                return JsonResponse({'status': 'fail', 'error': 'User not authenticated'}, status=403)

            # Validate input data
            if video_id is None or progress is None:
                return JsonResponse({'status': 'fail', 'error': 'Missing video_id or progress'}, status=400)

            if not isinstance(progress, (int, float)) or progress < 0 or progress > 100:
                return JsonResponse({'status': 'fail', 'error': 'Progress must be a number between 0 and 100'}, status=400)

            # If already completed, do not update status/progress again (prevents churn + UI bugs when revisiting completed parts)
            existing = VideoProgress.objects.filter(user=user, video_id=video_id).first()
            if existing and getattr(existing, "completed", False):
                return JsonResponse({'status': 'success', 'progress': 100})

            # Update or create progress record
            video_progress, created = VideoProgress.objects.update_or_create(
                user=user,
                video_id=video_id,
                defaults={'progress': progress, 'duration': duration}
            )
            if progress >= 100:
                video_progress.progress = 100
                video_progress.completed = True
                video_progress.save()

            return JsonResponse({'status': 'success', 'progress': video_progress.progress})

        except json.JSONDecodeError:
            return JsonResponse({'status': 'fail', 'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'status': 'fail', 'error': str(e)}, status=500)

    return JsonResponse({'status': 'fail', 'error': 'Invalid request method'}, status=400)


@login_required(login_url=reverse_lazy('users:login'))
def add_note(request, part_id):
    if request.method == "POST":
        part = get_object_or_404(Part, id=part_id)
        content = (request.POST.get('content') or '').strip()
        video_timestamp = (request.POST.get('time') or '').strip() or None
        video_end_timestamp = (request.POST.get('time_end') or '').strip() or None

        note = Notes.objects.create(
            user=request.user,
            part=part,
            content=content,
            video_timestamp=video_timestamp,
            video_end_timestamp=video_end_timestamp,
        )
        # Return the note details in the response
        return JsonResponse({
            "id": note.id,
            "content": note.content,
            "time": note.video_timestamp,
            "time_end": note.video_end_timestamp,
        })
    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required(login_url=reverse_lazy('users:login'))
def edit_note(request, note_id, part_id):
    if request.method == "POST":
        note = get_object_or_404(Notes, id=note_id, user=request.user)
        note.content = request.POST.get('content')
        note.video_timestamp = (request.POST.get('time') or '').strip() or None
        note.video_end_timestamp = (request.POST.get('time_end') or '').strip() or None

        note.save()
        # Return updated note details
        return JsonResponse({
            "id": note.id,
            "content": note.content,
            "time": note.video_timestamp,
            "time_end": note.video_end_timestamp,
            "updated_at": note.updated_at if hasattr(note, 'updated_at') else None
        })
    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required(login_url=reverse_lazy('users:login'))
def delete_note(request, note_id):
    if request.method == "POST":
        note = get_object_or_404(Notes, id=note_id, user=request.user)
        note.delete()
        return JsonResponse({"success": True, "id": note_id})
    return JsonResponse({"error": "Method not allowed"}, status=405)


def TestVttVideo(request):
    return render(request, 'template20/counselor/test_vtt_video.html')


@login_required(login_url=reverse_lazy('users:login'))
def part_caption_vtt(request, counselor_id, part_id):
    """
    Same-origin WebVTT proxy for the course learning player.

    Serves captions without setting crossorigin on <video> (which forces CORS on the
    MP4 and often breaks playback on S3 when video objects are not CORS-enabled).
    """
    from core import choices
    from django.http import Http404
    import urllib.error
    import urllib.request

    counselor = get_object_or_404(Counselor, id=counselor_id)
    if request.user.user_type == choices.UserType.COUNSELOR:
        if counselor.coun_user != request.user:
            raise Http404("You don't have permission to access this counselor's course.")

    course = CounselorCourse.objects.first()
    if not course:
        raise Http404("No course found.")

    part = get_object_or_404(Part, id=part_id, chapter__course=course)

    vtt_url = part.get_caption_vtt_url()
    if not vtt_url:
        raise Http404("No captions for this part.")

    try:
        req = urllib.request.Request(
            vtt_url,
            headers={"User-Agent": "TopTeen-course-caption-proxy/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        raise Http404("Captions unavailable.")

    r = HttpResponse(data, content_type="text/vtt; charset=utf-8")
    r["Cache-Control"] = "private, max-age=3600"
    return r


# ============================================================================
# COURSE LEARNING MODULE - Separate dedicated learning interface
# ============================================================================

@method_decorator(never_cache, name='dispatch')
@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class CourseLearningView(View):
    """
    Main course learning interface with sidebar navigation.
    No user sidebar, no chatbot - just course content.
    """
    template_name = 'template20/counselor/course_learning.html'
    
    def get(self, request, counselor_id):
        from core import choices
        from django.http import Http404
        import re
        
        # Retrieve the counselor using the provided ID
        counselor = get_object_or_404(Counselor, id=counselor_id)
        
        # Security check: Ensure counselors can only access their own course
        if request.user.user_type == choices.UserType.COUNSELOR:
            if counselor.coun_user != request.user:
                raise Http404("You don't have permission to access this counselor's course.")
        
        user = request.user
        is_demo_account = bool(getattr(user, "is_demo_account", False))
        # Full course learning for every counselor. Previously non-demo counselors were stuck on the
        # first lesson with no navigation, quiz, or resume; that was only appropriate for a preview
        # mode, not for enrolled learning.
        is_restricted_view = False
        # Non-demo counselors: hide the video timeline scrubber (forward skip still blocked in JS).
        hide_video_scrubber = (
            request.user.user_type == choices.UserType.COUNSELOR and not is_demo_account
        )
        course_with_related_data = CounselorCourse.objects.prefetch_related(
            'chapters__parts__quizzes__questions__answers'
        ).first()
        
        if not course_with_related_data:
            from django.http import Http404
            raise Http404("No course found.")
        
        # Get video progress
        part_ids = course_with_related_data.chapters.all().values_list('parts__id', flat=True)
        video_progress = {}
        if part_ids:
            progress_data = VideoProgress.objects.filter(
                user=user, 
                video_id__in=[f"video-{part_id}" for part_id in part_ids]
            )
            video_progress = {
                int(progress.video_id.split('-')[1]): progress.completed 
                for progress in progress_data
            }

        # No video URL → nothing to watch; treat like PDF/case studies (optional for status).
        for _part in Part.objects.filter(chapter__course=course_with_related_data):
            if not (_part.video_url or "").strip():
                video_progress[_part.id] = True
        
        # Quiz scores: collect completed quiz IDs; per-part "all quizzes done" for navigation/sidebar
        quiz_completion_status = {}
        completed_quiz_ids = set()
        scores = []
        try:
            quiz_result = QuizResults.objects.get(user=user)
            raw_scores = quiz_result.scores
            if isinstance(raw_scores, str):
                import json

                scores = json.loads(raw_scores) if raw_scores and raw_scores.strip() else []
            elif isinstance(raw_scores, list):
                scores = raw_scores
            else:
                scores = []
            for score in scores:
                if not isinstance(score, dict):
                    continue
                qid = score.get("quiz_id")
                if qid is not None:
                    try:
                        completed_quiz_ids.add(int(qid))
                    except (TypeError, ValueError):
                        pass
            for chapter in course_with_related_data.chapters.all():
                for part in chapter.parts.all():
                    qids = list(part.quizzes.values_list("id", flat=True))
                    if not qids:
                        continue
                    quiz_completion_status[part.id] = all(
                        int(q) in completed_quiz_ids for q in qids
                    )
        except QuizResults.DoesNotExist:
            scores = []
        
        # Determine what content to show based on URL parameters
        content_type = request.GET.get('type', None)  # chapter, part, quiz
        content_id = request.GET.get('id', None)
        
        current_chapter = None
        current_part = None
        current_quiz = None
        current_question_index = 0
        
        chapters_list = list(course_with_related_data.chapters.all())

        # Case studies: driven by Admin rows under Part (CaseStudyInline)
        # Use the first part in the course that has case studies OR a folder URL set.
        case_study_host_part = None
        case_study_chapter_id = None
        case_studies = []
        try:
            for ch in chapters_list:
                for p in ch.parts.all():
                    if p.case_studies.exists() or (getattr(p, "case_study_folder_url", None) or "").strip():
                        case_study_host_part = p
                        case_study_chapter_id = getattr(ch, "id", None)
                        # Load DB rows (ordered)
                        qs = p.case_studies.all().order_by("sort_order", "id")
                        case_studies = [{"id": cs.id, "title": cs.title or "", "pdf_url": cs.pdf_url or ""} for cs in qs]
                        break
                if case_study_host_part:
                    break
        except Exception:
            case_study_host_part = None
            case_study_chapter_id = None
            case_studies = []
        has_chapter_17 = bool(case_study_host_part and case_study_chapter_id)

        # Sidebar: show Case Studies block after "Practical Training", not before all parts.
        # Hide the duplicate Part row whose title is "Case Studies" (host part with CaseStudy rows).
        case_study_host_part_id = getattr(case_study_host_part, "id", None)
        case_study_insert_after_part_id = None
        if case_study_host_part and case_study_chapter_id:
            ch = getattr(case_study_host_part, "chapter", None)
            if ch:
                for p in ch.parts.all():
                    t = (getattr(p, "title", "") or "").strip().lower()
                    if "practical training" in t or "practicle training" in t:
                        case_study_insert_after_part_id = p.id
                        break
                if case_study_insert_after_part_id is None:
                    for p in ch.parts.all():
                        if case_study_host_part_id and p.id != case_study_host_part_id:
                            case_study_insert_after_part_id = p.id
                            break

        # If no specific content requested, find the next pending part
        if not content_type and not content_id:
            # Find the first incomplete part
            for chapter in chapters_list:
                for part in chapter.parts.all():
                    part_id = part.id
                    is_video_completed = video_progress.get(part_id, False)
                    
                    # If video not completed, show this part
                    if not is_video_completed:
                        current_part = part
                        current_chapter = chapter
                        content_type = 'part'
                        break
                    
                    # If video completed, check if quiz needs to be done
                    if part.quizzes.exists():
                        is_quiz_completed = quiz_completion_status.get(part_id, False)
                        if not is_quiz_completed:
                            # Show the first quiz for this part
                            current_quiz = part.quizzes.first()
                            current_part = part
                            current_chapter = chapter
                            content_type = 'quiz'
                            current_question_index = 0
                            break
                
                if current_part or current_quiz:
                    break
            
            # If all parts are completed, show the last part
            if not current_part and not current_quiz and chapters_list:
                last_chapter = chapters_list[-1]
                last_part = last_chapter.parts.last()
                if last_part:
                    current_part = last_part
                    current_chapter = last_chapter
                    content_type = 'part'
        
        elif content_type in ('case_study', 'case_study_index'):
            # case_study (legacy) → case_study_index: Index tab + optional Case Study PDF tab
            content_type = 'case_study_index'
            cs_id = request.GET.get("cs")
            if cs_id:
                try:
                    cs_id_int = int(cs_id)
                except (TypeError, ValueError):
                    raise Http404("Case study not found.")
                if not any(int(cs.get("id")) == cs_id_int for cs in case_studies):
                    raise Http404("Case study not found.")
                case_study_current_id = cs_id_int
            else:
                case_study_current_id = None
            current_chapter = next((ch for ch in chapters_list if getattr(ch, "id", None) == case_study_chapter_id), None)
            current_part = None
            current_quiz = None
            current_question_index = 0

        elif content_type == 'chapter' and content_id:
            try:
                requested_chapter = Chapter.objects.get(id=content_id, course=course_with_related_data)
                chapter_index = list(chapters_list).index(requested_chapter) if requested_chapter in chapters_list else -1
                
                # Check if previous chapter is completed
                if chapter_index > 0:
                    prev_chapter = chapters_list[chapter_index - 1]
                    prev_chapter_complete = True
                    for prev_part in prev_chapter.parts.all():
                        prev_part_id = prev_part.id
                        prev_video_completed = video_progress.get(prev_part_id, False)
                        if not prev_video_completed:
                            prev_chapter_complete = False
                            break
                        if prev_part.quizzes.exists():
                            prev_quiz_completed = quiz_completion_status.get(prev_part_id, False)
                            if not prev_quiz_completed:
                                prev_chapter_complete = False
                                break
                    
                    if not prev_chapter_complete:
                        # Redirect to first incomplete part
                        for chapter in chapters_list[:chapter_index]:
                            for part in chapter.parts.all():
                                part_id = part.id
                                is_video_completed = video_progress.get(part_id, False)
                                if not is_video_completed:
                                    current_part = part
                                    current_chapter = chapter
                                    content_type = 'part'
                                    break
                                if part.quizzes.exists():
                                    is_quiz_completed = quiz_completion_status.get(part_id, False)
                                    if not is_quiz_completed:
                                        current_quiz = part.quizzes.first()
                                        current_part = part
                                        current_chapter = chapter
                                        content_type = 'quiz'
                                        current_question_index = 0
                                        break
                                if current_part or current_quiz:
                                    break
                            if current_part or current_quiz:
                                break
                
                if not current_part and not current_quiz:
                    current_chapter = requested_chapter
                # Navigate to first incomplete part of chapter, or first part if all complete
                for part in current_chapter.parts.all():
                    part_id = part.id
                    is_video_completed = video_progress.get(part_id, False)
                    if not is_video_completed:
                        current_part = part
                        content_type = 'part'
                        break
                
                # If all parts completed, show first part
                if not current_part:
                    first_part = current_chapter.parts.first()
                    if first_part:
                        current_part = first_part
                        content_type = 'part'
            except Chapter.DoesNotExist:
                pass
        
        elif content_type == 'part' and content_id:
            try:
                requested_part = Part.objects.get(id=content_id)
                current_chapter = requested_part.chapter
                
                # Check if previous part is completed
                chapter_parts = list(current_chapter.parts.all())
                part_index = chapter_parts.index(requested_part) if requested_part in chapter_parts else -1
                
                if part_index > 0:
                    prev_part = chapter_parts[part_index - 1]
                    prev_part_id = prev_part.id
                    prev_video_completed = video_progress.get(prev_part_id, False)
                    
                    if not prev_video_completed:
                        # Redirect to previous incomplete part
                        current_part = prev_part
                        content_type = 'part'
                    else:
                        # Check if quiz is completed
                        if prev_part.quizzes.exists():
                            prev_quiz_completed = quiz_completion_status.get(prev_part_id, False)
                            if not prev_quiz_completed:
                                # Redirect to quiz
                                current_quiz = prev_part.quizzes.first()
                                current_part = prev_part
                                content_type = 'quiz'
                                current_question_index = 0
                            else:
                                # Previous part complete, allow access
                                current_part = requested_part
                        else:
                            # No quiz, allow access
                            current_part = requested_part
                else:
                    # First part in chapter - check if previous chapter is completed
                    chapter_index = list(chapters_list).index(current_chapter) if current_chapter in chapters_list else -1
                    if chapter_index > 0:
                        prev_chapter = chapters_list[chapter_index - 1]
                        prev_chapter_complete = True
                        for prev_part in prev_chapter.parts.all():
                            prev_part_id = prev_part.id
                            prev_video_completed = video_progress.get(prev_part_id, False)
                            if not prev_video_completed:
                                prev_chapter_complete = False
                                break
                            if prev_part.quizzes.exists():
                                prev_quiz_completed = quiz_completion_status.get(prev_part_id, False)
                                if not prev_quiz_completed:
                                    prev_chapter_complete = False
                                    break
                        
                        if not prev_chapter_complete:
                            # Redirect to first incomplete part in previous chapter
                            for part in prev_chapter.parts.all():
                                part_id = part.id
                                is_video_completed = video_progress.get(part_id, False)
                                if not is_video_completed:
                                    current_part = part
                                    current_chapter = prev_chapter
                                    content_type = 'part'
                                    break
                                if part.quizzes.exists():
                                    is_quiz_completed = quiz_completion_status.get(part_id, False)
                                    if not is_quiz_completed:
                                        current_quiz = part.quizzes.first()
                                        current_part = part
                                        current_chapter = prev_chapter
                                        content_type = 'quiz'
                                        current_question_index = 0
                                        break
                                if current_part or current_quiz:
                                    break
                    
                    if not current_part and not current_quiz:
                        current_part = requested_part
            except Part.DoesNotExist:
                pass
        
        elif content_type == 'quiz' and content_id:
            try:
                requested_quiz = Quiz.objects.get(id=content_id)
                requested_part = requested_quiz.quiz_part
                current_chapter = requested_part.chapter if requested_part else None
                
                if requested_part:
                    # Check if video is completed
                    part_id = requested_part.id
                    is_video_completed = video_progress.get(part_id, False)
                    
                    if not is_video_completed:
                        # Redirect to video
                        current_part = requested_part
                        content_type = 'part'
                    else:
                        # Check if previous part is completed
                        chapter_parts = list(current_chapter.parts.all())
                        part_index = chapter_parts.index(requested_part) if requested_part in chapter_parts else -1
                        
                        if part_index > 0:
                            prev_part = chapter_parts[part_index - 1]
                            prev_part_id = prev_part.id
                            prev_video_completed = video_progress.get(prev_part_id, False)
                            
                            if not prev_video_completed:
                                current_part = prev_part
                                content_type = 'part'
                            else:
                                if prev_part.quizzes.exists():
                                    prev_quiz_completed = quiz_completion_status.get(prev_part_id, False)
                                    if not prev_quiz_completed:
                                        current_quiz = prev_part.quizzes.first()
                                        current_part = prev_part
                                        content_type = 'quiz'
                                        current_question_index = 0
                                    else:
                                        current_quiz = requested_quiz
                                        current_part = requested_part
                                        current_question_index = int(request.GET.get('q', 0))
                                else:
                                    current_quiz = requested_quiz
                                    current_part = requested_part
                                    current_question_index = int(request.GET.get('q', 0))
                        else:
                            # First part - check previous chapter
                            chapter_index = list(chapters_list).index(current_chapter) if current_chapter in chapters_list else -1
                            if chapter_index > 0:
                                prev_chapter = chapters_list[chapter_index - 1]
                                prev_chapter_complete = True
                                for prev_part in prev_chapter.parts.all():
                                    prev_part_id = prev_part.id
                                    prev_video_completed = video_progress.get(prev_part_id, False)
                                    if not prev_video_completed:
                                        prev_chapter_complete = False
                                        break
                                    if prev_part.quizzes.exists():
                                        prev_quiz_completed = quiz_completion_status.get(prev_part_id, False)
                                        if not prev_quiz_completed:
                                            prev_chapter_complete = False
                                            break
                                
                                if not prev_chapter_complete:
                                    # Redirect to incomplete part
                                    for part in prev_chapter.parts.all():
                                        part_id = part.id
                                        is_video_completed = video_progress.get(part_id, False)
                                        if not is_video_completed:
                                            current_part = part
                                            current_chapter = prev_chapter
                                            content_type = 'part'
                                            break
                                        if part.quizzes.exists():
                                            is_quiz_completed = quiz_completion_status.get(part_id, False)
                                            if not is_quiz_completed:
                                                current_quiz = part.quizzes.first()
                                                current_part = part
                                                current_chapter = prev_chapter
                                                content_type = 'quiz'
                                                current_question_index = 0
                                                break
                                        if current_part or current_quiz:
                                            break
                            
                            if not current_part and not current_quiz:
                                current_quiz = requested_quiz
                                current_part = requested_part
                current_question_index = int(request.GET.get('q', 0))
            except Quiz.DoesNotExist:
                pass
        
        # Fallback: show first chapter's first part if nothing found
        if not current_chapter and chapters_list:
            current_chapter = chapters_list[0]
            first_part = current_chapter.parts.first()
            if first_part:
                current_part = first_part
                content_type = 'part'

        # Suppress PDF Notes tab when requested in admin (e.g., case studies replace an index PDF)
        hide_practical_training_pdf = False
        if current_part and getattr(current_part, "suppress_pdf_notes_tab", False):
            hide_practical_training_pdf = True

        case_study_current_id = locals().get("case_study_current_id", None)
        case_study_pdf_url = None
        case_study_title = None
        if content_type == "case_study_index" and case_study_current_id:
            case_study_pdf_url = reverse("counselor:case_study_pdf", args=[counselor.id, case_study_current_id])
            case_study_title = next((cs["title"] for cs in case_studies if int(cs["id"]) == int(case_study_current_id)), str(case_study_current_id))
        
        # Calculate overall progress
        # A part is considered complete only if:
        # 1. Video is completed AND
        # 2. Quiz is completed (if quiz exists) OR no quiz exists
        total_parts = sum(chapter.parts.count() for chapter in chapters_list)
        completed_parts = 0
        
        # Build locked status for chapters and parts
        chapter_locked_status = {}
        part_locked_status = {}
        
        for chapter_idx, chapter in enumerate(chapters_list):
            # Check if previous chapter is completed
            is_chapter_locked = False
            if chapter_idx > 0:
                prev_chapter = chapters_list[chapter_idx - 1]
                prev_chapter_complete = True
                for prev_part in prev_chapter.parts.all():
                    prev_part_id = prev_part.id
                    prev_video_completed = video_progress.get(prev_part_id, False)
                    if not prev_video_completed:
                        prev_chapter_complete = False
                        break
                    if prev_part.quizzes.exists():
                        prev_quiz_completed = quiz_completion_status.get(prev_part_id, False)
                        if not prev_quiz_completed:
                            prev_chapter_complete = False
                            break
                if not prev_chapter_complete:
                    is_chapter_locked = True
            chapter_locked_status[chapter.id] = is_chapter_locked
            
            # Check locked status for parts
            chapter_parts = list(chapter.parts.all())
            for part_idx, part in enumerate(chapter_parts):
                part_id = part.id
                is_video_completed = video_progress.get(part_id, False)
                is_quiz_completed = quiz_completion_status.get(part_id, False)
                
                # Check if part is complete
                is_part_complete = False
                if is_video_completed:
                    if part.quizzes.exists():
                        if is_quiz_completed:
                            is_part_complete = True
                    else:
                        is_part_complete = True
                
                # Check if previous part is completed
                is_part_locked = False
                if part_idx > 0:
                    prev_part = chapter_parts[part_idx - 1]
                    prev_part_id = prev_part.id
                    prev_video_completed = video_progress.get(prev_part_id, False)
                    if not prev_video_completed:
                        is_part_locked = True
                    else:
                        if prev_part.quizzes.exists():
                            prev_quiz_completed = quiz_completion_status.get(prev_part_id, False)
                            if not prev_quiz_completed:
                                is_part_locked = True
                elif chapter_idx > 0:
                    # First part in chapter - check if previous chapter's last part is completed
                    prev_chapter = chapters_list[chapter_idx - 1]
                    if prev_chapter.parts.exists():
                        prev_chapter_parts = list(prev_chapter.parts.all())
                        if prev_chapter_parts:
                            last_prev_part = prev_chapter_parts[-1]
                            last_prev_part_id = last_prev_part.id
                            last_prev_video_completed = video_progress.get(last_prev_part_id, False)
                            if not last_prev_video_completed:
                                is_part_locked = True
                            else:
                                if last_prev_part.quizzes.exists():
                                    last_prev_quiz_completed = quiz_completion_status.get(last_prev_part_id, False)
                                    if not last_prev_quiz_completed:
                                        is_part_locked = True
                
                part_locked_status[part_id] = is_part_locked
                
                # Count completed parts for progress
                if is_part_complete:
                        completed_parts += 1
        
        progress_percentage = int((completed_parts / total_parts * 100)) if total_parts > 0 else 0
        
        # Certificate: create CounselorCertification on first load after completion (not only on quiz POST).
        is_course_complete = _is_course_fully_completed(user)
        if is_course_complete:
            _check_and_issue_certificate(user, counselor.id)
        certification = (
            CounselorCertification.objects.filter(user=user).first()
            if is_course_complete
            else None
        )
        
        # Prepare quiz questions for one-by-one display
        quiz_questions = []
        total_questions = 0
        quiz_score_data = None  # Store quiz score if already completed
        
        if current_quiz:
            quiz_questions = list(current_quiz.questions.all().prefetch_related('answers'))
            total_questions = len(quiz_questions)
            # Ensure question index is valid
            if current_question_index >= total_questions:
                current_question_index = total_questions - 1
            if current_question_index < 0:
                current_question_index = 0
            
            # Check if quiz is already completed and get score
            if current_part and quiz_completion_status.get(current_part.id, False):
                try:
                    quiz_result = QuizResults.objects.get(user=user)
                    # Handle both string (JSON) and list formats
                    if isinstance(quiz_result.scores, str):
                        import json
                        scores = json.loads(quiz_result.scores) if quiz_result.scores else []
                    elif isinstance(quiz_result.scores, list):
                        scores = quiz_result.scores
                    else:
                        scores = []
                    
                    # Find score for this quiz
                    for score in scores:
                        if isinstance(score, dict):
                            score_quiz_id = score.get('quiz_id')
                            score_part_id = score.get('part_id')
                            if score_quiz_id == current_quiz.id and score_part_id == current_part.id:
                                quiz_result_data = score.get('quiz_result', {})
                                correct_option = score.get('correct_option', {})
                                quiz_score_data = {
                                    'correct': quiz_result_data.get('correct_answers', 0) if isinstance(quiz_result_data, dict) else 0,
                                    'incorrect': quiz_result_data.get('incorrect_answers', 0) if isinstance(quiz_result_data, dict) else 0,
                                    'total': score.get('total_questions_in_quiz', total_questions),
                                    'correct_options': correct_option if isinstance(correct_option, dict) else {},
                                }
                                break
                except QuizResults.DoesNotExist:
                    pass
                except Exception as e:
                    import traceback
                    print(f"Error getting quiz score data: {e}")
                    print(traceback.format_exc())
                    quiz_score_data = None

        part_notes = []
        if current_part:
            part_notes = list(
                Notes.objects.filter(user=user, part=current_part).order_by("-updated_at")
            )

        video_preconnect_href = None
        if current_part and getattr(current_part, "video_url", None):
            from urllib.parse import urlparse

            try:
                p = urlparse(current_part.video_url)
                if p.scheme and p.netloc:
                    video_preconnect_href = f"{p.scheme}://{p.netloc}"
            except Exception:
                pass

        # True only for non-demo counselors: lock forward seek in JS + restricted UI.
        restrict_video_seek = bool(
            request.user.user_type == choices.UserType.COUNSELOR and not is_demo_account
        )

        # Same as globals context processor: quiz auto-forward + loader read Admin Configuration (not cached HTML).
        from core.models import Configuration

        try:
            _raw_af = Configuration.get(
                'ENABLE_AUTO_FORWARD',
                default=str(getattr(settings, 'ENABLE_AUTO_FORWARD', True)).lower(),
                editable=True,
            )
            enable_auto_forward = str(_raw_af).lower() in ('true', '1', 'yes', 'on')
        except Exception:
            enable_auto_forward = getattr(settings, 'ENABLE_AUTO_FORWARD', True)

        from counselor.mindmap_json import (
            cached_course_chapter_part_mindmap_flags,
            chapter_mindmap_relpath,
            course_mindmap_relpath,
            mindmap_static_url,
            part_mindmap_relpath,
        )

        _course_mm_ok, _ch_flags, _part_flags = cached_course_chapter_part_mindmap_flags(
            course_with_related_data, chapters_list
        )

        course_mindmap_info = None
        if _course_mm_ok:
            course_mindmap_info = {
                "json_url": mindmap_static_url(course_mindmap_relpath()),
                "fullscreen_url": reverse(
                    "counselor:course_learning_course_mindmap",
                    args=[counselor.id],
                ),
            }

        chapter_mindmap_by_id = {}
        part_mindmap_by_id = {}
        for ch in chapters_list:
            if _ch_flags.get(ch.id):
                chapter_mindmap_by_id[ch.id] = {
                    "json_url": mindmap_static_url(chapter_mindmap_relpath(ch.id)),
                    "fullscreen_url": reverse(
                        "counselor:course_learning_chapter_mindmap",
                        args=[counselor.id, ch.id],
                    ),
                }
            else:
                chapter_mindmap_by_id[ch.id] = None
            for p in ch.parts.all():
                if _part_flags.get(p.id):
                    part_mindmap_by_id[p.id] = {
                        "json_url": mindmap_static_url(part_mindmap_relpath(p.id)),
                        "fullscreen_url": reverse(
                            "counselor:course_learning_part_mindmap",
                            args=[counselor.id, p.id],
                        ),
                    }

        lesson_active_tab = "video"
        if content_type == "part" and current_part:
            has_video = bool((current_part.video_url or "").strip())
            has_pdf = bool((current_part.pdf_url or "").strip()) and not hide_practical_training_pdf
            has_mindmap = bool(part_mindmap_by_id.get(current_part.id))
            tab = (request.GET.get("tab") or "").lower()
            if has_mindmap and tab == "mindmap":
                lesson_active_tab = "mindmap"
            elif tab == "pdf" and has_pdf:
                lesson_active_tab = "pdf"
            elif tab == "video" and has_video:
                lesson_active_tab = "video"
            elif not has_video and has_pdf:
                lesson_active_tab = "pdf"
            elif has_video:
                lesson_active_tab = "video"
            elif has_mindmap:
                lesson_active_tab = "mindmap"
            else:
                lesson_active_tab = "video"

        course_notes_list = []
        for n in (
            Notes.objects.filter(user=user, part__chapter__course=course_with_related_data)
            .select_related("part", "part__chapter")
            .order_by("-updated_at")
        ):
            content = (n.content or "").strip()
            preview = content[:160] + ("…" if len(content) > 160 else "")
            course_notes_list.append(
                {
                    "id": n.id,
                    "part_id": n.part_id,
                    "part_title": (n.part.title or "")[:200],
                    "chapter_title": (getattr(n.part.chapter, "title", None) or "")[:200],
                    "preview": preview,
                    "seek_seconds": _note_timestamp_to_seconds(n.video_timestamp),
                    "updated_at_display": (
                        timezone.localtime(n.updated_at).strftime("%b %d, %Y %H:%M")
                        if n.updated_at
                        else ""
                    ),
                }
            )

        context = {
            'counselor': counselor,
            'course': course_with_related_data,
            'chapters_list': chapters_list,
            'current_chapter': current_chapter,
            'current_part': current_part,
            'current_quiz': current_quiz,
            'current_question_index': current_question_index,
            'quiz_questions': quiz_questions,
            'total_questions': total_questions,
            'quiz_score_data': quiz_score_data,  # Add quiz score data
            'content_type': content_type,
            'video_progress': video_progress,
            'quiz_completion_status': quiz_completion_status,
            'completed_quiz_ids': completed_quiz_ids,
            'progress_percentage': progress_percentage,
            'certification': certification,
            'is_course_complete': is_course_complete,
            'chapter_locked_status': chapter_locked_status,  # Locked status for chapters
            'part_locked_status': part_locked_status,  # Locked status for parts
            'part_notes': part_notes,
            'is_demo_account': is_demo_account,
            'is_restricted_view': is_restricted_view,
            'hide_video_scrubber': hide_video_scrubber,
            'video_preconnect_href': video_preconnect_href,
            'restrict_video_seek': restrict_video_seek,
            'enable_auto_forward': enable_auto_forward,
            'case_studies': case_studies,
            'has_chapter_17': has_chapter_17,
            'case_study_chapter_id': case_study_chapter_id,
            'case_study_host_part_id': case_study_host_part_id,
            'case_study_insert_after_part_id': case_study_insert_after_part_id,
            'case_study_count': len(case_studies) if case_studies else 0,
            'case_study_current_id': case_study_current_id,
            'case_study_pdf_url': case_study_pdf_url,
            'case_study_title': case_study_title,
            'hide_practical_training_pdf': hide_practical_training_pdf,
            'chapter_mindmap_by_id': chapter_mindmap_by_id,
            'part_mindmap_by_id': part_mindmap_by_id,
            'course_mindmap_info': course_mindmap_info,
            'lesson_active_tab': lesson_active_tab,
            'course_notes_list': course_notes_list,
        }

        return render(request, self.template_name, context)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class CourseResultsView(View):
    """
    Display quiz results after completion.
    """
    template_name = 'template20/counselor/course_results.html'
    
    def get(self, request, counselor_id):
        from core import choices
        from django.http import Http404
        
        counselor = get_object_or_404(Counselor, id=counselor_id)
        
        if request.user.user_type == choices.UserType.COUNSELOR:
            if counselor.coun_user != request.user:
                raise Http404("You don't have permission to access this counselor's course.")
        
        user = request.user
        course_with_related_data = CounselorCourse.objects.prefetch_related(
            'chapters__parts__quizzes__questions__answers'
        ).first()
        
        if not course_with_related_data:
            raise Http404("No course found.")
        
        # Get quiz results
        try:
            quiz_result = QuizResults.objects.get(user=user)
            scores = quiz_result.scores if isinstance(quiz_result.scores, list) else []
        except QuizResults.DoesNotExist:
            scores = []
        
        # Calculate overall statistics
        total_questions = 0
        total_correct = 0
        total_incorrect = 0
        
        results_by_part = {}
        
        for score in scores:
            part_id = score.get('part_id')
            quiz_id = score.get('quiz_id')
            correct_answers = score.get('quiz_result', {}).get('correct_answers', 0)
            incorrect_answers = score.get('quiz_result', {}).get('incorrect_answers', 0)
            total_q = score.get('total_questions_in_quiz', 0)
            
            total_questions += total_q
            total_correct += correct_answers
            total_incorrect += incorrect_answers
            
            if part_id not in results_by_part:
                try:
                    part = Part.objects.get(id=part_id)
                    results_by_part[part_id] = {
                        'part': part,
                        'quizzes': []
                    }
                except Part.DoesNotExist:
                    continue
            
            results_by_part[part_id]['quizzes'].append({
                'quiz_id': quiz_id,
                'correct': correct_answers,
                'incorrect': incorrect_answers,
                'total': total_q,
                'correct_options': score.get('correct_option', {}),
            })
        
        # Calculate score percentage and grade
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
        
        # Get certification
        certification = CounselorCertification.objects.filter(user=user).first()
        
        context = {
            'counselor': counselor,
            'course': course_with_related_data,
            'total_questions': total_questions,
            'total_correct': total_correct,
            'total_incorrect': total_incorrect,
            'score_percentage': round(score_percentage, 2),
            'grade': grade,
            'results_by_part': results_by_part,
            'certification': certification,
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class ViewCertificateView(View):
    """
    Display certificate for completed course.
    Only accessible after all videos and quizzes are completed.
    """
    template_name = 'template20/counselor/view_certificate.html'
    
    def get(self, request, counselor_id):
        from core import choices
        from django.http import Http404
        
        counselor = get_object_or_404(Counselor, id=counselor_id)
        
        if request.user.user_type == choices.UserType.COUNSELOR:
            if counselor.coun_user != request.user:
                raise Http404("You don't have permission to access this counselor's course.")
        
        user = request.user
        
        # Check if course is fully completed (all videos + all quizzes)
        is_complete = _is_course_fully_completed(user)
        
        certification = CounselorCertification.objects.filter(user=user).first()
        
        # For testing: allow viewing certificate even if course not complete (if certification exists)
        # In production, uncomment the checks below
        # if not is_complete:
        #     messages.warning(request, "You must complete all videos and quizzes before viewing your certificate.")
        #     return redirect('counselor:course_learning', counselor_id=counselor_id)
        
        if not certification:
            # Create a test certificate for preview if none exists (for testing only)
            if settings.DEBUG:
                from datetime import datetime
                certification = CounselorCertification.objects.create(
                    user=user,
                    certificate_code="123456",
                    grade="A+",
                    created_at=datetime.now()
                )
            else:
                messages.warning(request, "Certificate not found. Please complete the course first.")
                return redirect('counselor:course_learning', counselor_id=counselor_id)
        
        context = {
            'counselor': counselor,
            'certification': certification,
            'user': user,
        }
        
        return render(request, self.template_name, context)


@login_required(login_url=reverse_lazy('users:login'))
def submit_quiz_question(request, counselor_id):
    """
    Handle quiz question submission (one-by-one flow).
    """
    from core import choices
    from django.http import JsonResponse, Http404
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    counselor = get_object_or_404(Counselor, id=counselor_id)
    
    if request.user.user_type == choices.UserType.COUNSELOR:
        if counselor.coun_user != request.user:
            raise Http404("You don't have permission.")
    
    try:
        data = json.loads(request.body)
        quiz_id = data.get('quiz_id')
        question_id = data.get('question_id')
        answer_id = data.get('answer_id')
        question_index = data.get('question_index', 0)
        is_last_question = data.get('is_last_question', False)
        
        if not all([quiz_id, question_id, answer_id is not None]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'}, status=400)
        
        quiz = get_object_or_404(Quiz, id=quiz_id)
        question = get_object_or_404(Question, id=question_id, quiz=quiz)
        answer = get_object_or_404(QuizAnswers, id=answer_id, question=question)
        
        # Store answer temporarily in session or process immediately
        # For now, we'll process on last question submission
        
        if is_last_question:
            # Get all answers from session or process all at once
            # This is a simplified version - you may want to store answers in session
            # and process them all when submitting the last question
            
            # For now, redirect to the full quiz submission
            return JsonResponse({
                'success': True,
                'redirect': True,
                'url': reverse('counselor:submit_full_quiz', args=[counselor_id, quiz_id])
            })
        else:
            # Store answer and move to next question
            return JsonResponse({
                'success': True,
                'next_question': question_index + 1,
                'redirect': False
            })
            
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url=reverse_lazy('users:login'))
def submit_full_quiz(request, counselor_id, quiz_id):
    """
    Process full quiz submission after all questions answered.
    """
    from core import choices
    from django.http import Http404
    
    counselor = get_object_or_404(Counselor, id=counselor_id)
    
    if request.user.user_type == choices.UserType.COUNSELOR:
        if counselor.coun_user != request.user:
            raise Http404("You don't have permission.")
    
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('counselor:course_learning', counselor_id=counselor_id)
    
    quiz = get_object_or_404(Quiz, id=quiz_id)
    part = quiz.quiz_part
    
    # Process quiz submission (similar to existing logic)
    results = {}
    part_id = part.id
    results[part_id] = {'quiz_results': [], 'correct_count': 0, 'incorrect_count': 0}
    
    total_questions_each_quiz = quiz.questions.count()
    correct_answers_map = {}
    
    for question in quiz.questions.all():
        user_answer_id = request.POST.get(f'question_{question.id}')
        user_answer = None
        
        if user_answer_id:
            try:
                user_answer = QuizAnswers.objects.get(id=user_answer_id)
            except QuizAnswers.DoesNotExist:
                pass
        
        correct_answer = question.answers.filter(is_correct=True).first()
        is_correct = user_answer == correct_answer if user_answer else False
        
        if is_correct:
            results[part_id]['correct_count'] += 1
        else:
            results[part_id]['incorrect_count'] += 1
        
        correct_answers_map[f'ques_{question.id}'] = {
            'correct_ans': correct_answer.answer_text if correct_answer else None,
            'selected_ans': user_answer.answer_text if user_answer else None,
        }
    
    results[part_id]['quiz_results'].append({
        'quiz_id': quiz.id,
        'total_questions_in_quiz': total_questions_each_quiz,
        'correct_option': correct_answers_map,
        'quiz_result': {
            'correct_answers': results[part_id]['correct_count'],
            'incorrect_answers': results[part_id]['incorrect_count'],
        }
    })
    
    # Save to QuizResults
    user = request.user
    quiz_results, created = QuizResults.objects.get_or_create(user=user)
    
    if isinstance(quiz_results.scores, str):
        quiz_results.scores = json.loads(quiz_results.scores)
    elif not isinstance(quiz_results.scores, list):
        quiz_results.scores = []
    
    # Update or add score
    for part_result in results.values():
        for quiz_result_data in part_result['quiz_results']:
            score_info = {
                "part_id": part_id,
                "quiz_id": quiz_result_data['quiz_id'],
                "total_questions_in_quiz": quiz_result_data['total_questions_in_quiz'],
                "correct_option": quiz_result_data['correct_option'],
                "quiz_result": quiz_result_data['quiz_result'],
            }
            
            # Check if exists
            existing_score = None
            for score in quiz_results.scores:
                if score.get("part_id") == part_id and score.get("quiz_id") == quiz_result_data['quiz_id']:
                    existing_score = score
                    break
            
            if existing_score:
                existing_score.update(score_info)
            else:
                quiz_results.scores.append(score_info)
    
    quiz_results.save()
    
    messages.success(request, "Quiz submitted successfully!")
    
    # Check if course is complete and issue certificate
    _check_and_issue_certificate(user, counselor_id)
    
    # Redirect to course learning page - it will automatically find and show next pending part
    # This ensures proper navigation to incomplete videos/quizzes
    return redirect('counselor:course_learning', counselor_id=counselor_id)


@login_required(login_url=reverse_lazy('users:login'))
def autocomplete_course(request, counselor_id):
    """
    Autocomplete the entire course with 100% scores.
    Shows a password form on GET, processes autocomplete on POST if password is correct.
    Requires one-time password from .env file (autocompletepassword=shanti).
    """
    from core import choices
    from django.http import Http404
    from django.conf import settings
    from decouple import config
    
    counselor = get_object_or_404(Counselor, id=counselor_id)
    
    # Security check: Ensure counselors can only access their own course
    if request.user.user_type == choices.UserType.COUNSELOR:
        if counselor.coun_user != request.user:
            raise Http404("You don't have permission to access this counselor's course.")
    
    # Password verification - read from .env file (autocompletepassword=shanti)
    required_password = config('autocompletepassword', default='')
    
    if not required_password:
        messages.error(request, "Autocomplete feature is not configured. Please contact administrator.")
        return redirect('counselor:course_learning', counselor_id=counselor_id)
    
    # Handle GET request - show password form
    if request.method == 'GET':
        context = {
            'counselor': counselor,
            'counselor_id': counselor_id,
        }
        return render(request, 'template20/counselor/autocomplete_password.html', context)
    
    # Handle POST request - verify password and autocomplete
    provided_password = request.POST.get('password', '')
    
    if not provided_password or provided_password != required_password:
        messages.error(request, "Invalid password. Please try again.")
        context = {
            'counselor': counselor,
            'counselor_id': counselor_id,
        }
        return render(request, 'template20/counselor/autocomplete_password.html', context)
    
    # Password is correct - proceed with autocomplete
    user = request.user
    
    # Get the course
    course = CounselorCourse.objects.prefetch_related(
        'chapters__parts__quizzes__questions__answers'
    ).first()
    
    if not course:
        messages.error(request, "No course found.")
        return redirect('counselor:course_learning', counselor_id=counselor_id)
    
    # Get all parts
    all_parts = Part.objects.filter(chapter__course=course).prefetch_related('quizzes__questions__answers')
    
    # Mark all videos as completed (100% progress)
    for part in all_parts:
        video_id = f"video-{part.id}"
        VideoProgress.objects.update_or_create(
            user=user,
            video_id=video_id,
            defaults={
                'progress': 100,
                'completed': True,
                'duration': None  # Can be set if needed
            }
        )
    
    # Mark all quizzes as completed with 100% scores
    quiz_results, created = QuizResults.objects.get_or_create(user=user)
    
    if isinstance(quiz_results.scores, str):
        quiz_results.scores = json.loads(quiz_results.scores) if quiz_results.scores else []
    elif not isinstance(quiz_results.scores, list):
        quiz_results.scores = []
    
    # Process each part with quizzes
    for part in all_parts:
        part_id = part.id
        
        # Process each quiz for this part
        for quiz in part.quizzes.all():
            total_questions = quiz.questions.count()
            
            if total_questions == 0:
                continue
            
            # Create correct answers map with all correct answers
            correct_answers_map = {}
            for question in quiz.questions.all():
                correct_answer = question.answers.filter(is_correct=True).first()
                if correct_answer:
                    correct_answers_map[f'ques_{question.id}'] = {
                        'correct_ans': correct_answer.answer_text,
                        'selected_ans': correct_answer.answer_text,  # User selected correct answer
                    }
            
            # Create score info with 100% correct
            score_info = {
                "part_id": part_id,
                "quiz_id": quiz.id,
                "total_questions_in_quiz": total_questions,
                "correct_option": correct_answers_map,
                "quiz_result": {
                    'correct_answers': total_questions,  # All correct
                    'incorrect_answers': 0,  # None incorrect
                }
            }
            
            # Check if score already exists and update, otherwise append
            existing_score = None
            for idx, score in enumerate(quiz_results.scores):
                if score.get("part_id") == part_id and score.get("quiz_id") == quiz.id:
                    existing_score = idx
                    break
            
            if existing_score is not None:
                quiz_results.scores[existing_score] = score_info
            else:
                quiz_results.scores.append(score_info)
    
    quiz_results.save()
    
    # Check if course is complete and issue certificate
    _check_and_issue_certificate(user, counselor_id)
    
    messages.success(request, "Course autocompleted successfully with 100% scores!")
    
    # Redirect to course learning page
    return redirect('counselor:course_learning', counselor_id=counselor_id)


def _check_and_issue_certificate(user, counselor_id):
    """
    Check if course is complete and issue certificate if needed.
    Uses the comprehensive completion check function.
    """
    # Use the comprehensive completion check
    is_complete = _is_course_fully_completed(user)
    
    # Issue certificate if course is complete
    if is_complete:
        certification = CounselorCertification.objects.filter(user=user).first()
        
        if not certification:
            # Get quiz scores for grade calculation
            try:
                quiz_result = QuizResults.objects.get(user=user)
                if isinstance(quiz_result.scores, str):
                    import json
                    scores = json.loads(quiz_result.scores) if quiz_result.scores else []
                elif isinstance(quiz_result.scores, list):
                    scores = quiz_result.scores
                else:
                    scores = []
            except QuizResults.DoesNotExist:
                scores = []
            
            # Calculate grade
            total_questions = 0
            total_correct = 0
            
            for score in scores:
                total_questions += score.get('total_questions_in_quiz', 0)
                total_correct += score.get('quiz_result', {}).get('correct_answers', 0)
            
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
            
            # Generate certificate code
            latest_cert = CounselorCertification.objects.last()
            if latest_cert:
                certificate_code = f"TPTC{latest_cert.id + 1:04d}"
            else:
                certificate_code = "TPTC0001"
            
            CounselorCertification.objects.create(
                user=user,
                certificate_code=certificate_code,
                grade=grade
            )


from django.views.generic import TemplateView
from core.utils import build_html_head


class CounselorLoginView(TemplateView):
    """
    View to render counselor login page
    """
    template_name = 'counselor/login.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            from core.utils import build_html_head
            context['html_head'] = build_html_head(title='Counselor Login', description='Login to your counselor dashboard')
        except Exception:
            # Fallback if build_html_head is not available
            context['html_head'] = None
        from users.demo_accounts import get_demo_login_context
        from core import choices
        context.update(get_demo_login_context(
            self.request,
            user_types=[choices.UserType.COUNSELOR],
        ))
        return context