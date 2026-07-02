from django.db import IntegrityError
from django.shortcuts import render
from .models import (
    SkillLabCourse, SkillLabCourseActivity, SkillLabCourseChapter, SkillLabCourseProgress,
    SkillLabCourseProgressSummary, SkillLabCourseResume, SkillLabWorksheetProgress, SkillLabMCQAttempt,
    SkillLabMCQ, SkillLabMCQQuestion, SkillLabMCQAnswer, SkillLabChapterSection,
    SkillLabUserHighlight, SkillLabUserNote, SkillLabUserBookmark, InternationalOnlineCourse,
)
from django.views.generic import TemplateView,View
from django.urls import reverse_lazy
from core.utils import build_html_head, get_preferred_payment_gateway, is_gateway_available
from core.breadcrumbs import get_breadcrumb
from .document_filters import SkillLabCourseDocumentFilter
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.core.signing import Signer
from django.shortcuts import get_object_or_404
from .models import SkilllabCoursePayment
from django.http import Http404, HttpResponse, JsonResponse
import re
from payments.payment.icicieazypay import IciciEazyPayService
from payments.models import Payment
from core import choices
from django.shortcuts import redirect,HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from .task import send_skillabcourse_payment_success_mail
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from core.s3_utils import get_s3_upload_service
import logging

logger = logging.getLogger(__name__)
# Create your views here.

class SkillLabCourseList(TemplateView):
    template_name = "template20/skilllab_course_list.html"
    def html_head(self):
        name='Skill Lab Courses'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args, **kwargs):
        from django.urls import reverse
        from django.core.paginator import Paginator
        
        try:
            skl=SkillLabCourseDocumentFilter()
            ctx=skl.get_skilllab_list_context(request)
        except (KeyError, Exception) as e:
            # Fallback to Django ORM when Elasticsearch is not available
            logger.warning("Elasticsearch not available, using Django ORM fallback: %s", e)
            ctx = self.get_fallback_context(request)
        
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb'] = get_breadcrumb([{'text': 'Skill Lab Course', 'url': ''}])
        ctx['course_count'] = SkillLabCourse.objects.count()
        ctx['intl_courses'] = InternationalOnlineCourse.objects.all()[:4]
        return ctx
    
    def get_fallback_context(self, request):
        """Fallback method using Django ORM when Elasticsearch is unavailable"""
        from django.core.paginator import Paginator
        
        ctx = {}
        
        # Get all skilllab courses ordered by modified date (newest first)
        courses = SkillLabCourse.objects.all().order_by('-modified')
        
        # Pagination
        paginator = Paginator(courses, 9)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        ctx['skilllab'] = page_obj
        ctx['course_count'] = courses.count()

        return ctx
    
    def get(self, request,*args, **kwargs):      
        return render(request, self.template_name, self.get_context(request,args, kwargs))


class InternationalOnlineCourseList(TemplateView):
    template_name = "template20/international_online_courses.html"
    per_page = 8

    def html_head(self):
        name = 'Free International Online Courses'
        return build_html_head(title=name, description=name)

    def get_context(self, request, *args, **kwargs):
        from django.urls import reverse
        from django.core.paginator import Paginator

        selected_subject = request.GET.get('subject', '').strip()
        selected_institute = request.GET.get('institute', '').strip()

        courses = InternationalOnlineCourse.objects.all()
        if selected_subject:
            courses = courses.filter(subject=selected_subject)
        if selected_institute:
            courses = courses.filter(institute=selected_institute)

        paginator = Paginator(courses, self.per_page)
        page_obj = paginator.get_page(request.GET.get('page'))

        query_params = request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')

        return {
            'html_head': self.html_head(),
            'breadcrumb': get_breadcrumb([
                {'text': 'Skill Lab Courses', 'url': reverse('skilllabcourse:skilllabcourselist')},
                {'text': 'International Online Courses', 'url': ''},
            ]),
            'courses': page_obj,
            'subjects': InternationalOnlineCourse.objects.values_list('subject', flat=True).distinct().order_by('subject'),
            'institutes': InternationalOnlineCourse.objects.values_list('institute', flat=True).distinct().order_by('institute'),
            'selected_subject': selected_subject,
            'selected_institute': selected_institute,
            'filter_query': query_params.urlencode(),
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))
             
class SkillLabCourseDetail(TemplateView):
    template_name = "template20/skilllab_course_detail.html"
    def html_head(self,skilllab):
        clean=re.compile('<.*?>')
        t= skilllab.name 
        des = skilllab.description
        d=re.sub(clean,'',des)
        return build_html_head(title=t, description=d)
    
    def get_context(self,request,skil_slug,*args,**kwargs):
        ctx={}
        skillab=get_object_or_404(SkillLabCourse, slug=skil_slug)
        ctx['skilllab']=skillab
        ctx['first_chapter']=skillab.skilllabcoursechapter.order_by('created').first()
        ctx['activecourses']=SkillLabCourse.objects.filter(category=skillab.category).exclude(id=skillab.id)
        ctx['breadcrumb'] = self._breadcrumb(skillab)
        ctx["html_head"] = self.html_head(skillab)
        ctx['user_authenticated'] = request.user.is_authenticated
        ctx['skilllab_course_started'] = (
            skillab.user_has_started(request.user)
            if request.user.is_authenticated
            else False
        )
        return ctx

    def _breadcrumb(self, skilllab):
        from django.urls import reverse
        return get_breadcrumb([
            {'text': 'Skill Lab Courses', 'url': reverse('skilllabcourse:skilllabcourselist')},
            {'text': skilllab.name, 'url': ''},
        ])
    
    def get(self, request,skilllab_slug, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request,skilllab_slug,*args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabCourseChapterDetail(TemplateView):
    template_name = "template20/skilllab/skilllab_chapter_detail.html"

    def html_head(self,skilllab):
        t= skilllab.chapter_name 
        d = skilllab.content or ''
        return build_html_head(title=t, description=d)
    
    def get_context(self,request,chapter_slug,*args,**kwargs):
        ctx={}
        skillab_course_chapter=get_object_or_404(SkillLabCourseChapter, slug=chapter_slug)
        skilllab_course = skillab_course_chapter.skilllab
        chapters = list(skilllab_course.skilllabcoursechapter.order_by('created'))
        ctx['skilllab_course_chapter']=skillab_course_chapter
        ctx['all_chapters']=chapters
        idx = next((i for i, c in enumerate(chapters) if c.id == skillab_course_chapter.id), 0)
        ctx['prev_chapter']=chapters[idx-1] if idx > 0 else None
        ctx['next_chapter']=chapters[idx+1] if idx < len(chapters)-1 else None
        ctx['breadcrumb']=self._breadcrumb(skillab_course_chapter)
        ctx["html_head"] = self.html_head(skillab_course_chapter)
        return ctx
    
    def _breadcrumb(self, skilllab_course_chapter):
        return get_breadcrumb([
            {'text': 'SkilllabCourse', 'url': reverse_lazy('skilllabcourse:skilllabcourselist')},
            {'text': skilllab_course_chapter.skilllab.name, 'url': reverse_lazy('skilllabcourse:skilllabcoursedetail', args=[skilllab_course_chapter.skilllab.slug])},
            {'text': skilllab_course_chapter.chapter_name, 'url': ''},
        ])
    
    def get(self, request,chapter_slug, *args, **kwargs):
        ctx=self.get_context(request,chapter_slug,*args, **kwargs)
        course_payment_status=ctx['skilllab_course_chapter'].skilllab.is_user_vissible(request)
        if not course_payment_status:
            raise Http404
        return render(request, self.template_name, ctx)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabCourseLearningView(TemplateView):
    """Main learning interface at /skilllabcourse/course_learning/<course_slug>/"""
    template_name = "template20/skilllab/course_learning.html"

    def _get_chapter_progress(self, user, skilllab_course):
        """Returns dict {chapter_id: completed} from SkillLabCourseProgress."""
        records = SkillLabCourseProgress.objects.filter(
            user=user, skilllab_course=skilllab_course, chapter__isnull=False
        ).select_related('chapter')
        return {r.chapter_id: r.completed for r in records if r.chapter_id}

    def _get_chapter_locked_status(self, chapters, chapter_progress):
        """Chapters are locked if previous chapter is not completed. First chapter always unlocked."""
        locked = {}
        for i, ch in enumerate(chapters):
            if i == 0:
                locked[ch.id] = False
            else:
                prev_ch = chapters[i - 1]
                prev_completed = chapter_progress.get(prev_ch.id, False)
                locked[ch.id] = not prev_completed
        return locked

    def _get_progress_percentage(self, chapters, chapter_progress):
        """Percentage of completed chapters (used for locking, certificate)."""
        if not chapters:
            return 0
        completed = sum(1 for ch in chapters if chapter_progress.get(ch.id, False))
        return int((completed / len(chapters)) * 100)

    def _get_section_progress_percentage(self, sections_flat, worksheet_progress, mcq_attempts_ids):
        """Overall individual course progress: % of this course's sections completed (intro, worksheet downloaded, MCQ submitted)."""
        if not sections_flat:
            return 0
        completed = 0
        for sec in sections_flat:
            if sec['type'] == 'intro':
                completed += 1
            elif sec['type'] == 'worksheet':
                if sec['id'] in worksheet_progress:
                    completed += 1
            elif sec['type'] == 'mcq':
                if sec['id'] in mcq_attempts_ids:
                    completed += 1
        return int((completed / len(sections_flat)) * 100)

    def get_context(self, request, course_slug, *args, **kwargs):
        skilllab_course = get_object_or_404(SkillLabCourse, slug=course_slug)
        if not skilllab_course.is_user_vissible(request):
            raise Http404("You do not have access to this course.")

        chapters = list(skilllab_course.skilllabcoursechapter.order_by('created'))
        chapter_progress = self._get_chapter_progress(request.user, skilllab_course)
        chapter_locked_status = self._get_chapter_locked_status(chapters, chapter_progress)

        # Current chapter from ?chapter=N or ?chapter_slug=slug
        # When no URL params: resume at first incomplete chapter (based on progress)
        chapter_index = 0
        chapter_slug = request.GET.get('chapter_slug')
        chapter_num = request.GET.get('chapter')
        if chapter_slug:
            idx = next((i for i, c in enumerate(chapters) if c.slug == chapter_slug), 0)
            chapter_index = idx
        elif chapter_num is not None:
            try:
                idx = int(chapter_num)
                chapter_index = max(0, min(idx, len(chapters) - 1))
            except ValueError:
                pass
        else:
            chapter_index = 0  # Placeholder; will update after sections_flat if resume exists

        current_chapter = chapters[chapter_index] if chapters else None
        is_current_locked = chapter_locked_status.get(current_chapter.id, True) if current_chapter else False
        is_current_completed = chapter_progress.get(current_chapter.id, False) if current_chapter else False

        # Certificate: show if all chapters completed
        all_completed = all(chapter_progress.get(ch.id, False) for ch in chapters) if chapters else False

        def _short_section_title(t):
            """Extract 'Section N' from 'Section N: Long title...' for nav/sidebar display."""
            if not t:
                return t
            import re
            m = re.match(r'^(Section\s+\d+)\s*:.*', t, re.I)
            return m.group(1) if m else t

        # Build sections per chapter: Introduction, Section 1, Section 2, ..., Worksheet, MCQ
        sections_by_chapter = {}
        for ch in chapters:
            sections = []
            chapter_sections = list(ch.sections.order_by('order'))
            if chapter_sections:
                section_num = 0
                for sec in chapter_sections:
                    if sec.section_type == 'introduction':
                        title = sec.title or 'Introduction'
                    elif sec.section_type == 'chapter_wrap_up':
                        title = sec.title or 'Chapter Wrap-Up'
                    else:
                        section_num += 1
                        title = sec.title or f"Section {section_num}"
                    short_title = _short_section_title(title)
                    sections.append({'type': 'intro', 'id': sec.id, 'title': title, 'short_title': short_title, 'section_type': sec.section_type})
            else:
                intro_parts = _split_content_by_headings(ch.content or '')
                for idx, (step_title, _) in enumerate(intro_parts):
                    short_title = _short_section_title(step_title)
                    sections.append({'type': 'intro', 'id': ch.id, 'step': idx, 'title': step_title, 'short_title': short_title})
            for act in ch.skilllabcourseactivity.filter(type=choices.SkillLabAcivityChoice.worksheet):
                sections.append({'type': 'worksheet', 'id': act.id, 'title': act.name, 'short_title': act.name})
            for mcq in ch.mcqs.all():
                mcq_title = mcq.title or 'Quiz'
                sections.append({'type': 'mcq', 'id': mcq.id, 'title': mcq_title, 'short_title': mcq_title})
            sections_by_chapter[ch.id] = sections

        # Worksheet progress (downloaded) - filter by this course only
        activity_ids = [
            act.id for ch in chapters
            for act in ch.skilllabcourseactivity.filter(type=choices.SkillLabAcivityChoice.worksheet)
        ]
        worksheet_progress = set(
            SkillLabWorksheetProgress.objects.filter(
                user=request.user, activity_id__in=activity_ids
            ).values_list('activity_id', flat=True)
        )

        # MCQ attempts (latest per mcq) - filter by this course only
        mcq_ids = [m.id for ch in chapters for m in ch.mcqs.all()]
        mcq_attempts = {}
        for a in SkillLabMCQAttempt.objects.filter(
            user=request.user, mcq_id__in=mcq_ids
        ).select_related('mcq').order_by('-attempted_at'):
            if a.mcq_id not in mcq_attempts:
                mcq_attempts[a.mcq_id] = a

        # Flat sections list for JS (include step for intro)
        import json
        sections_flat = []
        for ch_idx, ch in enumerate(chapters):
            for sec in sections_by_chapter.get(ch.id, []):
                item = {
                    'type': sec['type'], 'id': sec['id'], 'title': sec['title'],
                    'shortTitle': sec.get('short_title', sec['title']),
                    'chapterId': ch.id, 'chapterName': ch.chapter_name, 'chapterIndex': ch_idx,
                }
                if sec['type'] == 'intro' and 'step' in sec:
                    item['step'] = sec.get('step', 0)
                sections_flat.append(item)
        sections_flat_json = json.dumps(sections_flat)
        # Prevent </script> in section titles/content from closing the HTML script element
        sections_flat_json = re.sub(r'</script>', r'<\\/script>', sections_flat_json, flags=re.IGNORECASE)
        worksheet_progress_ids = list(worksheet_progress)
        mcq_attempts_ids = list(mcq_attempts.keys())
        progress_summary = SkillLabCourseProgressSummary.objects.filter(
            user=request.user, skilllab_course=skilllab_course
        ).first()
        if progress_summary is None:
            try:
                update_skilllab_course_progress_summary(request.user, skilllab_course)
            except IntegrityError:
                pass
            progress_summary = SkillLabCourseProgressSummary.objects.filter(
                user=request.user, skilllab_course=skilllab_course
            ).first()
        if progress_summary is None:
            # Last resort: create record so view never fails (e.g. if update_skilllab_course_progress_summary errored before save)
            progress_summary, _ = SkillLabCourseProgressSummary.objects.get_or_create(
                user=request.user,
                skilllab_course=skilllab_course,
                defaults={
                    'progress_percentage': 0,
                    'completed_sections_count': 0,
                    'total_sections_count': len(sections_flat),
                }
            )
        progress_percentage = progress_summary.progress_percentage

        # Reached sections for green tick: intro/section/wrap-up show tick when user has viewed them
        resume = SkillLabCourseResume.objects.filter(
            user=request.user, skilllab_course=skilllab_course
        ).first()
        last_section_idx = resume.last_section_index if (resume and resume.last_section_index is not None) else -1
        reached_sections = set()
        for i, sec in enumerate(sections_flat):
            if i <= last_section_idx:
                if sec['type'] == 'intro':
                    reached_sections.add(('intro', sec['id'], sec.get('step', 0)))
                else:
                    reached_sections.add((sec['type'], sec['id']))

        # When no URL params: restore from SkillLabCourseResume or first incomplete chapter
        initial_section_idx = None
        if chapter_slug is None and chapter_num is None:
            if resume and 0 <= resume.last_section_index < len(sections_flat):
                chapter_index = sections_flat[resume.last_section_index]['chapterIndex']
                current_chapter = chapters[chapter_index] if chapters else None
                initial_section_idx = resume.last_section_index
            else:
                for i, ch in enumerate(chapters):
                    if not chapter_progress.get(ch.id, False):
                        chapter_index = i
                        current_chapter = chapters[chapter_index] if chapters else None
                        break

        ctx = {
            'skilllab_course': skilllab_course,
            'chapters': chapters,
            'current_chapter': current_chapter,
            'chapter_index': chapter_index,
            'chapter_progress': chapter_progress,
            'chapter_locked_status': chapter_locked_status,
            'progress_percentage': progress_percentage,
            'is_current_locked': is_current_locked,
            'is_current_completed': is_current_completed,
            'all_completed': all_completed,
            'prev_chapter': chapters[chapter_index - 1] if chapter_index > 0 else None,
            'next_chapter': chapters[chapter_index + 1] if chapter_index < len(chapters) - 1 else None,
            'sections_by_chapter': sections_by_chapter,
            'worksheet_progress': worksheet_progress,
            'mcq_attempts': mcq_attempts,
            'sections_flat_json': sections_flat_json,
            'worksheet_progress_ids': worksheet_progress_ids,
            'mcq_attempts_ids': mcq_attempts_ids,
            'initial_section_idx': initial_section_idx,
            'reached_sections': reached_sections,
        }
        ctx["html_head"] = build_html_head(
            title=skilllab_course.name,
            description=skilllab_course.description or skilllab_course.name
        )
        return ctx

    def get(self, request, course_slug, *args, **kwargs):
        ctx = self.get_context(request, course_slug, *args, **kwargs)
        return render(request, self.template_name, ctx)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabSaveResumeView(APIView):
    """API to save last viewed section for state restore. POST with course_slug, section_idx."""

    def post(self, request):
        course_slug = None
        section_idx = None
        if hasattr(request, 'data') and request.data:
            course_slug = request.data.get('course_slug')
            section_idx = request.data.get('section_idx')
        if course_slug is None:
            course_slug = request.POST.get('course_slug')
        if section_idx is None:
            section_idx = request.POST.get('section_idx')
        if not course_slug:
            return Response({'success': False, 'error': 'course_slug required'}, status=status.HTTP_400_BAD_REQUEST)
        skilllab_course = get_object_or_404(SkillLabCourse, slug=course_slug)
        if not skilllab_course.is_user_vissible(request):
            return Response({'success': False, 'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        try:
            idx = int(section_idx) if section_idx is not None else 0
            idx = max(0, idx)
        except (TypeError, ValueError):
            idx = 0
        SkillLabCourseResume.objects.update_or_create(
            user=request.user,
            skilllab_course=skilllab_course,
            defaults={'last_section_index': idx}
        )
        update_skilllab_course_progress_summary(request.user, skilllab_course)
        summary = SkillLabCourseProgressSummary.objects.get(
            user=request.user, skilllab_course=skilllab_course
        )
        return Response({'success': True, 'progress_percentage': summary.progress_percentage})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabMarkChapterCompleteView(APIView):
    """API to mark a chapter as complete. POST with chapter_id."""

    def post(self, request):
        chapter_id = None
        if hasattr(request, 'data') and request.data:
            chapter_id = request.data.get('chapter_id')
        if chapter_id is None:
            chapter_id = request.POST.get('chapter_id')
        if not chapter_id:
            return Response({'success': False, 'error': 'chapter_id required'}, status=status.HTTP_400_BAD_REQUEST)
        chapter = get_object_or_404(SkillLabCourseChapter, id=chapter_id)
        skilllab_course = chapter.skilllab
        if not skilllab_course.is_user_vissible(request):
            return Response({'success': False, 'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        progress, _ = SkillLabCourseProgress.objects.update_or_create(
            user=request.user,
            skilllab_course=skilllab_course,
            chapter=chapter,
            defaults={'completed': True, 'completed_at': timezone.now()}
        )
        return Response({'success': True, 'completed': progress.completed})


def _get_course_and_check_access(request, course_slug):
    """Return (skilllab_course, None) or (None, error_response)."""
    if not course_slug:
        return None, Response({'success': False, 'error': 'course_slug required'}, status=status.HTTP_400_BAD_REQUEST)
    skilllab_course = get_object_or_404(SkillLabCourse, slug=course_slug)
    if not skilllab_course.is_user_vissible(request):
        return None, Response({'success': False, 'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    return skilllab_course, None


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabHighlightSaveView(APIView):
    """POST: Save a highlight. course_slug, section_type, section_id, section_step (optional), highlighted_text, color (optional)."""

    def post(self, request):
        import json
        data = getattr(request, 'data', None) or {}
        if not data and request.body:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = dict(request.POST)
        course_slug = data.get('course_slug') or request.POST.get('course_slug')
        skilllab_course, err = _get_course_and_check_access(request, course_slug)
        if err:
            return err
        section_type = data.get('section_type') or request.POST.get('section_type')
        section_id = data.get('section_id') or request.POST.get('section_id')
        section_step = data.get('section_step')
        highlighted_text = (data.get('highlighted_text') or request.POST.get('highlighted_text') or '').strip()
        color = (data.get('color') or request.POST.get('color') or 'yellow').strip() or 'yellow'
        if not section_type or not section_id or not highlighted_text:
            return Response({'success': False, 'error': 'section_type, section_id, highlighted_text required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            section_id = int(section_id)
            section_step = int(section_step) if section_step is not None and str(section_step).strip() != '' else None
        except (TypeError, ValueError):
            section_step = None
        obj = SkillLabUserHighlight.objects.create(
            user=request.user,
            skilllab_course=skilllab_course,
            section_type=section_type,
            section_id=section_id,
            section_step=section_step,
            highlighted_text=highlighted_text,
            color=color,
        )
        return Response({'success': True, 'id': obj.id})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabHighlightListView(APIView):
    """GET: List highlights for a section. ?course_slug=&section_type=&section_id=&section_step="""

    def get(self, request):
        course_slug = request.GET.get('course_slug')
        skilllab_course, err = _get_course_and_check_access(request, course_slug)
        if err:
            return err
        section_type = request.GET.get('section_type')
        section_id = request.GET.get('section_id')
        section_step = request.GET.get('section_step')
        if not section_type or not section_id:
            return Response({'success': False, 'error': 'section_type, section_id required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            section_id = int(section_id)
            section_step = int(section_step) if section_step not in (None, '') else None
        except (TypeError, ValueError):
            section_step = None
        qs = SkillLabUserHighlight.objects.filter(
            user=request.user,
            skilllab_course=skilllab_course,
            section_type=section_type,
            section_id=section_id,
        )
        if section_step is not None:
            qs = qs.filter(section_step=section_step)
        else:
            qs = qs.filter(section_step__isnull=True)
        items = [{'id': h.id, 'highlighted_text': h.highlighted_text, 'color': h.color} for h in qs.order_by('created')]
        return Response({'success': True, 'highlights': items})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabHighlightDeleteView(APIView):
    """POST: Delete a highlight. highlight_id (and course_slug for access check)."""

    def post(self, request):
        import json
        data = getattr(request, 'data', None) or {}
        if not data and request.body:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = dict(request.POST)
        highlight_id = data.get('highlight_id') or request.POST.get('highlight_id')
        if not highlight_id:
            return Response({'success': False, 'error': 'highlight_id required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            highlight_id = int(highlight_id)
        except (TypeError, ValueError):
            return Response({'success': False, 'error': 'invalid highlight_id'}, status=status.HTTP_400_BAD_REQUEST)
        obj = SkillLabUserHighlight.objects.filter(id=highlight_id, user=request.user).first()
        if not obj:
            return Response({'success': False, 'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response({'success': True})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabNoteSaveView(APIView):
    """POST: Save a note. course_slug, section_type, section_id, section_step (optional), note_text, anchor_text (optional)."""

    def post(self, request):
        import json
        data = getattr(request, 'data', None) or {}
        if not data and request.body:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = dict(request.POST)
        course_slug = data.get('course_slug') or request.POST.get('course_slug')
        skilllab_course, err = _get_course_and_check_access(request, course_slug)
        if err:
            return err
        section_type = data.get('section_type') or request.POST.get('section_type')
        section_id = data.get('section_id') or request.POST.get('section_id')
        section_step = data.get('section_step')
        name = (data.get('name') or request.POST.get('name') or '').strip()[:255]
        note_text = (data.get('note_text') or request.POST.get('note_text') or '').strip()
        anchor_text = (data.get('anchor_text') or request.POST.get('anchor_text') or '')[:2000]
        if not section_type or not section_id:
            return Response({'success': False, 'error': 'section_type, section_id required'}, status=status.HTTP_400_BAD_REQUEST)
        if not note_text:
            return Response({'success': False, 'error': 'Note cannot be empty'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            section_id = int(section_id)
            section_step = int(section_step) if section_step is not None and str(section_step).strip() != '' else None
        except (TypeError, ValueError):
            section_step = None
        obj = SkillLabUserNote.objects.create(
            user=request.user,
            skilllab_course=skilllab_course,
            section_type=section_type,
            section_id=section_id,
            section_step=section_step,
            name=name,
            note_text=note_text,
            anchor_text=anchor_text,
        )
        return Response({'success': True, 'id': obj.id})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabNoteListView(APIView):
    """GET: List notes for a section."""

    def get(self, request):
        course_slug = request.GET.get('course_slug')
        skilllab_course, err = _get_course_and_check_access(request, course_slug)
        if err:
            return err
        section_type = request.GET.get('section_type')
        section_id = request.GET.get('section_id')
        section_step = request.GET.get('section_step')
        if not section_type or not section_id:
            return Response({'success': False, 'error': 'section_type, section_id required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            section_id = int(section_id)
            section_step = int(section_step) if section_step not in (None, '') else None
        except (TypeError, ValueError):
            section_step = None
        qs = SkillLabUserNote.objects.filter(
            user=request.user,
            skilllab_course=skilllab_course,
            section_type=section_type,
            section_id=section_id,
        )
        if section_step is not None:
            qs = qs.filter(section_step=section_step)
        else:
            qs = qs.filter(section_step__isnull=True)
        items = [{'id': n.id, 'name': n.name or '', 'note_text': n.note_text, 'anchor_text': n.anchor_text} for n in qs.order_by('created')]
        return Response({'success': True, 'notes': items})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabNoteDeleteView(APIView):
    """POST: Delete a note."""

    def post(self, request):
        import json
        data = getattr(request, 'data', None) or {}
        if not data and request.body:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = dict(request.POST)
        note_id = data.get('note_id') or request.POST.get('note_id')
        if not note_id:
            return Response({'success': False, 'error': 'note_id required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            note_id = int(note_id)
        except (TypeError, ValueError):
            return Response({'success': False, 'error': 'invalid note_id'}, status=status.HTTP_400_BAD_REQUEST)
        obj = SkillLabUserNote.objects.filter(id=note_id, user=request.user).first()
        if not obj:
            return Response({'success': False, 'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response({'success': True})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabBookmarkSaveView(APIView):
    """POST: Add or update bookmark for a section. One bookmark per section (section_key)."""

    def post(self, request):
        import json
        data = getattr(request, 'data', None) or {}
        if not data and request.body:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = dict(request.POST)
        course_slug = data.get('course_slug') or request.POST.get('course_slug')
        skilllab_course, err = _get_course_and_check_access(request, course_slug)
        if err:
            return err
        section_type = data.get('section_type') or request.POST.get('section_type')
        section_id = data.get('section_id') or request.POST.get('section_id')
        section_step = data.get('section_step')
        section_title = (data.get('section_title') or request.POST.get('section_title') or 'Section')[:255]
        if not section_type or not section_id:
            return Response({'success': False, 'error': 'section_type, section_id required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            section_id = int(section_id)
            section_step = int(section_step) if section_step is not None and str(section_step).strip() != '' else None
        except (TypeError, ValueError):
            section_step = None
        section_key = '{}_{}_{}'.format(section_type, section_id, section_step if section_step is not None else '')
        obj, created = SkillLabUserBookmark.objects.update_or_create(
            user=request.user,
            skilllab_course=skilllab_course,
            section_key=section_key,
            defaults={
                'section_type': section_type,
                'section_id': section_id,
                'section_step': section_step,
                'section_title': section_title,
            }
        )
        return Response({'success': True, 'id': obj.id, 'created': created})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabBookmarkListView(APIView):
    """GET: List bookmarks for a course. ?course_slug= Optional section_type, section_id to check if current is bookmarked."""

    def get(self, request):
        course_slug = request.GET.get('course_slug')
        skilllab_course, err = _get_course_and_check_access(request, course_slug)
        if err:
            return err
        section_type = request.GET.get('section_type')
        section_id = request.GET.get('section_id')
        section_step = request.GET.get('section_step')
        if section_type is not None and section_id is not None:
            try:
                section_id = int(section_id)
                section_step = int(section_step) if section_step not in (None, '') else None
            except (TypeError, ValueError):
                section_step = None
            section_key = '{}_{}_{}'.format(section_type, section_id, section_step if section_step is not None else '')
            is_bookmarked = SkillLabUserBookmark.objects.filter(
                user=request.user,
                skilllab_course=skilllab_course,
                section_key=section_key,
            ).exists()
            return Response({'success': True, 'is_bookmarked': is_bookmarked})
        bookmarks = SkillLabUserBookmark.objects.filter(
            user=request.user,
            skilllab_course=skilllab_course,
        ).order_by('-created')
        items = [{'id': b.id, 'section_type': b.section_type, 'section_id': b.section_id, 'section_step': b.section_step, 'section_title': b.section_title} for b in bookmarks]
        return Response({'success': True, 'bookmarks': items})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabBookmarkDeleteView(APIView):
    """POST: Remove bookmark. course_slug, section_type, section_id, section_step (optional)."""

    def post(self, request):
        import json
        data = getattr(request, 'data', None) or {}
        if not data and request.body:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = dict(request.POST)
        course_slug = data.get('course_slug') or request.POST.get('course_slug')
        skilllab_course, err = _get_course_and_check_access(request, course_slug)
        if err:
            return err
        section_type = data.get('section_type') or request.POST.get('section_type')
        section_id = data.get('section_id') or request.POST.get('section_id')
        section_step = data.get('section_step')
        if not section_type or not section_id:
            return Response({'success': False, 'error': 'section_type, section_id required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            section_id = int(section_id)
            section_step = int(section_step) if section_step is not None and str(section_step).strip() != '' else None
        except (TypeError, ValueError):
            section_step = None
        section_key = '{}_{}_{}'.format(section_type, section_id, section_step if section_step is not None else '')
        deleted, _ = SkillLabUserBookmark.objects.filter(
            user=request.user,
            skilllab_course=skilllab_course,
            section_key=section_key,
        ).delete()
        return Response({'success': True, 'deleted': deleted > 0})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabSavedCountView(APIView):
    """GET: Count of highlights, notes, bookmarks for a course (for top-right notification). ?course_slug="""

    def get(self, request):
        course_slug = request.GET.get('course_slug')
        skilllab_course, err = _get_course_and_check_access(request, course_slug)
        if err:
            return err
        h_count = SkillLabUserHighlight.objects.filter(user=request.user, skilllab_course=skilllab_course).count()
        n_count = SkillLabUserNote.objects.filter(user=request.user, skilllab_course=skilllab_course).count()
        b_count = SkillLabUserBookmark.objects.filter(user=request.user, skilllab_course=skilllab_course).count()
        return Response({
            'success': True,
            'highlights': h_count,
            'notes': n_count,
            'bookmarks': b_count,
            'total': h_count + n_count + b_count,
        })


def _split_content_by_headings(html):
    """Split HTML content by h2/h3 into steps. Returns list of (title, html) tuples."""
    if not html or not html.strip():
        return [('Introduction', html or '')]
    import re
    parts = re.split(r'(?=<h[23][^>]*>)', html, flags=re.IGNORECASE)
    result = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        title_match = re.search(r'<h[23][^>]*>([^<]+)</h[23]>', part, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ('Introduction' if i == 0 else f'Section {i + 1}')
        result.append((title, part))
    return result if result else [('Introduction', html)]


def update_skilllab_course_progress_summary(user, skilllab_course):
    """Recalculate and store course progress in DB. Call when worksheet downloaded or MCQ submitted."""
    chapters = list(skilllab_course.skilllabcoursechapter.order_by('created'))
    sections_by_chapter = {}
    for ch in chapters:
        sections = []
        chapter_sections = list(ch.sections.order_by('order'))
        if chapter_sections:
            section_num = 0
            for sec in chapter_sections:
                if sec.section_type == 'introduction':
                    title = sec.title or 'Introduction'
                elif sec.section_type == 'chapter_wrap_up':
                    title = sec.title or 'Chapter Wrap-Up'
                else:
                    section_num += 1
                    title = sec.title or f"Section {section_num}"
                sections.append({'type': 'intro', 'id': sec.id})
        else:
            intro_parts = _split_content_by_headings(ch.content or '')
            for idx in range(len(intro_parts)):
                sections.append({'type': 'intro', 'id': ch.id, 'step': idx})
        for act in ch.skilllabcourseactivity.filter(type=choices.SkillLabAcivityChoice.worksheet):
            sections.append({'type': 'worksheet', 'id': act.id})
        for mcq in ch.mcqs.all():
            sections.append({'type': 'mcq', 'id': mcq.id})
        sections_by_chapter[ch.id] = sections
    sections_flat = []
    for ch in chapters:
        for sec in sections_by_chapter.get(ch.id, []):
            sections_flat.append(sec)
    activity_ids = [
        act.id for ch in chapters
        for act in ch.skilllabcourseactivity.filter(type=choices.SkillLabAcivityChoice.worksheet)
    ]
    worksheet_progress = set(
        SkillLabWorksheetProgress.objects.filter(
            user=user, activity_id__in=activity_ids
        ).values_list('activity_id', flat=True)
    )
    mcq_ids = [m.id for ch in chapters for m in ch.mcqs.all()]
    mcq_attempts_ids = list(
        SkillLabMCQAttempt.objects.filter(user=user, mcq_id__in=mcq_ids)
        .values_list('mcq_id', flat=True)
        .distinct()
    )
    resume = SkillLabCourseResume.objects.filter(
        user=user, skilllab_course=skilllab_course
    ).first()
    last_section_index = resume.last_section_index if resume else -1

    completed = 0
    total = len(sections_flat)
    for idx, sec in enumerate(sections_flat):
        if sec['type'] == 'intro':
            if idx <= last_section_index:
                completed += 1
        elif sec['type'] == 'worksheet':
            if sec['id'] in worksheet_progress:
                completed += 1
        elif sec['type'] == 'mcq':
            if sec['id'] in mcq_attempts_ids:
                completed += 1
    pct = int((completed / total) * 100) if total > 0 else 0
    try:
        SkillLabCourseProgressSummary.objects.update_or_create(
            user=user,
            skilllab_course=skilllab_course,
            defaults={
                'progress_percentage': pct,
                'completed_sections_count': completed,
                'total_sections_count': total,
            }
        )
    except IntegrityError:
        # Race: another request created it. Fetch and update if visible (may not be committed yet).
        obj = SkillLabCourseProgressSummary.objects.filter(
            user=user, skilllab_course=skilllab_course
        ).first()
        if obj:
            obj.progress_percentage = pct
            obj.completed_sections_count = completed
            obj.total_sections_count = total
            obj.save()


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabSectionContentView(View):
    """AJAX: Get section content (intro, worksheet, mcq). GET ?section_type=intro|worksheet|mcq&section_id=X&course_slug=Y&step=N (for intro)"""

    def get(self, request):
        section_type = request.GET.get('section_type')
        section_id = request.GET.get('section_id')
        course_slug = request.GET.get('course_slug')
        step_str = request.GET.get('step', '0')
        if not section_type or not section_id or not course_slug:
            return HttpResponse('', status=400)
        skilllab_course = get_object_or_404(SkillLabCourse, slug=course_slug)
        if not skilllab_course.is_user_vissible(request):
            return HttpResponse('', status=403)
        ctx = {'skilllab_course': skilllab_course}
        if section_type == 'intro':
            # Try SkillLabChapterSection first (section-based storage)
            section = SkillLabChapterSection.objects.filter(
                id=section_id, chapter__skilllab=skilllab_course
            ).select_related('chapter').first()
            if section:
                ctx['chapter'] = section.chapter
                ctx['content'] = section.content or ''
                return render(request, 'template20/skilllab/partials/section_intro.html', ctx)
            # Fallback: legacy chapter.content with step param
            chapter = get_object_or_404(SkillLabCourseChapter, id=section_id, skilllab=skilllab_course)
            ctx['chapter'] = chapter
            intro_parts = _split_content_by_headings(chapter.content or '')
            step_idx = max(0, min(int(step_str) if step_str.isdigit() else 0, len(intro_parts) - 1))
            ctx['content'] = intro_parts[step_idx][1] if intro_parts else ''
            return render(request, 'template20/skilllab/partials/section_intro.html', ctx)
        elif section_type == 'worksheet':
            activity = get_object_or_404(SkillLabCourseActivity, id=section_id, skilllab_chapter__skilllab=skilllab_course)
            ctx['activity'] = activity
            ctx['downloaded'] = SkillLabWorksheetProgress.objects.filter(user=request.user, activity=activity).exists()
            # Use proxy URL for downloads - avoids S3 Access Denied (generates presigned URL server-side)
            has_file = bool(activity.downloadable_file) or bool(
                activity.content and re.search(r'href=["\']([^"\']+)["\']', activity.content)
            )
            download_url = reverse('skilllabcourse:download_worksheet', kwargs={'activity_id': activity.id}) if has_file else None
            ctx['worksheet_download_url'] = download_url
            return render(request, 'template20/skilllab/partials/section_worksheet.html', ctx)
        elif section_type == 'mcq':
            mcq = get_object_or_404(SkillLabMCQ, id=section_id, skilllab_chapter__skilllab=skilllab_course)
            ctx['mcq'] = mcq
            ctx['questions'] = mcq.questions.all().order_by('order', 'question_number')
            last_attempt = SkillLabMCQAttempt.objects.filter(user=request.user, mcq=mcq).order_by('-attempted_at').first()
            ctx['last_attempt'] = last_attempt
            return render(request, 'template20/skilllab/partials/section_mcq.html', ctx)
        return HttpResponse('', status=400)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabWorksheetDownloadView(View):
    """Serve worksheet download via presigned S3 URL to avoid Access Denied on private buckets."""

    def get(self, request, activity_id):
        activity = get_object_or_404(SkillLabCourseActivity, id=activity_id)
        if not activity.skilllab_chapter.skilllab.is_user_vissible(request):
            raise Http404("Access denied")
        s3_service = get_s3_upload_service()
        s3_key = None
        if activity.downloadable_file:
            # FileField - name is the storage key (path in S3 or local)
            storage = activity.downloadable_file.storage
            if hasattr(storage, 'bucket_name'):
                s3_key = activity.downloadable_file.name
        if not s3_key and activity.content:
            href_match = re.search(r'href=["\']([^"\']+)["\']', activity.content)
            if href_match:
                raw_url = href_match.group(1)
                s3_key = s3_service.s3_key_from_url(raw_url)
        if s3_key and s3_service.s3_client:
            # Verify object exists before redirecting (avoids NoSuchKey error)
            if s3_service.object_exists(s3_key):
                presigned_url = s3_service.generate_presigned_url(s3_key, expires_in=3600)
                if presigned_url:
                    return redirect(presigned_url)
            # S3 object missing - try local fallback
            local_path = self._get_local_worksheet_path(activity)
            if local_path:
                from django.http import FileResponse
                import os
                try:
                    return FileResponse(open(local_path, 'rb'), as_attachment=True,
                        filename=os.path.basename(local_path),
                        content_type='application/pdf')
                except (OSError, IOError):
                    pass
        if activity.downloadable_file:
            return redirect(activity.downloadable_file.url)
        return render(request, 'template20/skilllab/worksheet_not_found.html', {
            'activity': activity,
            'skilllab_course': activity.skilllab_chapter.skilllab,
        }, status=404)

    def _get_local_worksheet_path(self, activity):
        """Try to find worksheet PDF in skilllabcourses_html as fallback when S3 file is missing."""
        from pathlib import Path
        from django.conf import settings
        from django.utils.text import slugify
        chapter = activity.skilllab_chapter
        course = chapter.skilllab
        base = Path(settings.BASE_DIR) / 'skilllabcourses_html'
        if not base.exists():
            return None
        chapters_ordered = list(course.skilllabcoursechapter.order_by('created'))
        chapter_num = chapters_ordered.index(chapter) + 1
        course_name_lower = (course.name or '').lower()
        course_slug = slugify(course.name or '')
        # Try exact match, slugified, and iterate subdirs for case-insensitive match
        candidates = [course.name, course_slug, course_slug.replace('-', ' ')]
        for subdir in base.iterdir():
            if subdir.is_dir() and subdir.name.lower() == course_name_lower:
                candidates.insert(0, subdir.name)
                break
        for folder_name in candidates:
            if not folder_name:
                continue
            chapter_dir = base / folder_name / f'chapter_{chapter_num}'
            if chapter_dir.exists():
                for pattern in [f'worksheet{chapter_num}.pdf', f'worksheet{chapter_num}_*.pdf']:
                    matches = list(chapter_dir.glob(pattern))
                    if matches:
                        return str(matches[0])
        return None


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabMarkWorksheetDownloadedView(View):
    """AJAX: Mark worksheet as downloaded. POST activity_id."""

    def post(self, request):
        activity_id = request.POST.get('activity_id') or (request.data.get('activity_id') if hasattr(request, 'data') else None)
        if not activity_id:
            return JsonResponse({'success': False, 'error': 'activity_id required'}, status=400)
        activity = get_object_or_404(SkillLabCourseActivity, id=activity_id)
        if not activity.skilllab_chapter.skilllab.is_user_vissible(request):
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        prog, _ = SkillLabWorksheetProgress.objects.update_or_create(
            user=request.user, activity=activity,
            defaults={'downloaded_at': timezone.now()}
        )
        skilllab_course = activity.skilllab_chapter.skilllab
        update_skilllab_course_progress_summary(request.user, skilllab_course)
        summary = SkillLabCourseProgressSummary.objects.get(
            user=request.user, skilllab_course=skilllab_course
        )
        return JsonResponse({'success': True, 'progress_percentage': summary.progress_percentage})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabSubmitMCQView(View):
    """AJAX: Submit MCQ answers, return results. POST mcq_id, answers {question_id: answer_id}."""

    def post(self, request):
        import json
        data = getattr(request, 'data', None) or {}
        if not data and request.body:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = dict(request.POST)
        mcq_id = data.get('mcq_id') or request.POST.get('mcq_id')
        answers = data.get('answers') or {}
        if isinstance(answers, str):
            try:
                answers = json.loads(answers)
            except (json.JSONDecodeError, TypeError):
                answers = {}
        if not mcq_id:
            return JsonResponse({'success': False, 'error': 'mcq_id required'}, status=400)
        mcq = get_object_or_404(SkillLabMCQ, id=mcq_id)
        if not mcq.skilllab_chapter.skilllab.is_user_vissible(request):
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        questions = list(mcq.questions.all().order_by('order', 'question_number'))
        correct_map = {}
        for q in questions:
            correct = q.answers.filter(is_correct=True).first()
            if correct:
                correct_map[str(q.id)] = correct.id
        score = 0
        result_detail = []
        for q in questions:
            user_ans = answers.get(str(q.id)) or answers.get(q.id)
            if user_ans:
                user_ans = int(user_ans) if isinstance(user_ans, (str, float)) and str(user_ans).isdigit() else user_ans
            correct_id = correct_map.get(str(q.id))
            is_correct = (user_ans == correct_id) if user_ans and correct_id else False
            if is_correct:
                score += 1
            result_detail.append({
                'question_id': q.id,
                'question_text': q.question_text[:100],
                'user_answer': user_ans,
                'correct': is_correct,
            })
        total = len(questions)
        attempt = SkillLabMCQAttempt.objects.create(
            user=request.user, mcq=mcq, score=score, total=total, answers=answers
        )
        skilllab_course = mcq.skilllab_chapter.skilllab
        update_skilllab_course_progress_summary(request.user, skilllab_course)
        summary = SkillLabCourseProgressSummary.objects.get(
            user=request.user, skilllab_course=skilllab_course
        )
        return JsonResponse({
            'success': True,
            'progress_percentage': summary.progress_percentage,
            'score': score,
            'total': total,
            'percentage': int((score / total * 100)) if total else 0,
            'result_detail': result_detail,
        })


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabCourseCertificateView(TemplateView):
    """Certificate view - shown when all chapters are completed."""
    template_name = "template20/skilllab/course_certificate.html"

    def get_context(self, request, course_slug, *args, **kwargs):
        skilllab_course = get_object_or_404(SkillLabCourse, slug=course_slug)
        if not skilllab_course.is_user_vissible(request):
            raise Http404("You do not have access to this course.")
        chapters = list(skilllab_course.skilllabcoursechapter.order_by('created'))
        chapter_progress = SkillLabCourseProgress.objects.filter(
            user=request.user, skilllab_course=skilllab_course, chapter__isnull=False
        )
        completed_ids = set(chapter_progress.filter(completed=True).values_list('chapter_id', flat=True))
        all_completed = all(ch.id in completed_ids for ch in chapters) if chapters else False
        ctx = {
            'skilllab_course': skilllab_course,
            'all_completed': all_completed,
            'certificate_date': timezone.now(),
        }
        ctx["html_head"] = build_html_head(title=f"Certificate - {skilllab_course.name}", description=skilllab_course.name)
        return ctx

    def get(self, request, course_slug, *args, **kwargs):
        ctx = self.get_context(request, course_slug, *args, **kwargs)
        return render(request, self.template_name, ctx)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class SkillLabCourseActivityDetail(TemplateView):
    template_name="topteenfrontend/skilllabactivityworksheet.html"

    def _breadcrumb(self, skilllab_activity):
        return get_breadcrumb([
            {'text': 'SkilllabCourse', 'url': reverse_lazy('skilllabcourse:skilllabcourselist')},
            {'text': skilllab_activity.skilllab_chapter.skilllab.name, 'url': reverse_lazy('skilllabcourse:skilllabcoursedetail', args=[skilllab_activity.skilllab_chapter.skilllab.slug])},
            {'text': skilllab_activity.skilllab_chapter.chapter_name, 'url': reverse_lazy('skilllabcourse:skilllabcoursechapterdetail', args=[skilllab_activity.skilllab_chapter.slug])},
            {'text': skilllab_activity.name, 'url': ''},
        ])

    def html_head(self,skillactive):
        t= skillactive.name 
        return build_html_head(title=t, description=t)

    def get_context(self,request,workactive_slug,*args,**kwargs):
        ctx={}
        sklibactive=get_object_or_404(SkillLabCourseActivity, slug=workactive_slug)
        ctx['activityworksheet']=sklibactive
        ctx["html_head"] = self.html_head(sklibactive)
        ctx['breadcrumb'] =self._breadcrumb(sklibactive)
        return ctx

    def get(self, request,workactive_slug, *args, **kwargs):
        ctx=self.get_context(request,workactive_slug,*args, **kwargs)
        course_payment_status=ctx['activityworksheet'].skilllab_chapter.skilllab.is_user_vissible(request)
        if not course_payment_status:
            raise Http404
        return render(request, self.template_name,ctx)

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class SkilllabCoursePaymentSuccess(TemplateView):
    template_name ="topteenfrontend/skilllabcoursepaymentsuccess.html"

    def html_head(self):
        name='Skilllab Course Payment Success'
        return build_html_head(title=name, description=name)

    def get_context(self,request,enc_id,*args,**kwargs):
        sign=Signer()
        signobj=sign.unsign_object(enc_id)
        id=signobj.get('enc_id')
        ctx={}
        skilllab_payment = get_object_or_404(SkilllabCoursePayment, id=id)
        ctx['skilllab_payment'] = skilllab_payment
        # Payment record for order id, transaction id and invoice/receipt
        payment = Payment.objects.filter(
            user=request.user,
            obj_id=skilllab_payment.id,
            obj_type=choices.PaymentObjectType.SKILLLABCOURSE,
            is_success=choices.YesNoChoices.YES,
        ).order_by('-created').first()
        ctx['payment'] = payment
        try:
            ctx['invoice_id'] = payment.invoice.id if payment else None
        except Exception:
            ctx['invoice_id'] = None
        ctx["html_head"] = self.html_head()
        return ctx

    def get(self, request,enc_id,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,enc_id,*args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class SkilllabCoursePaymentFail(TemplateView):
    template_name ="topteenfrontend/skilllabcoursepaymentfail.html"

    def html_head(self):
        name='Skilllab Course Payment Fail'
        return build_html_head(title=name, description=name)

    def get_context(self,request,enc_id,*args,**kwargs):
        sign=Signer()
        signobj=sign.unsign_object(enc_id)
        id=signobj.get('enc_id')
        ctx={}
        ctx['skilllab_payment']=get_object_or_404(SkilllabCoursePayment,id=id)
        ctx["html_head"] = self.html_head()
        return ctx

    def get(self, request,enc_id,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,enc_id,*args, **kwargs))
    
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class CreateSkilllabCoursePaymentWithEazyPay(View):
    def get_payment_url(self,request,slug,*args, **kwargs):
        skillab_course=get_object_or_404(SkillLabCourse,slug=slug)
        user=request.user
        # Create a shorter receipt format (Razorpay requires max 40 characters)
        # Format: SL{user_id}_{course_id} (e.g., "SL123_456")
        gateway_receipt="SL{}_{}".format(request.user.id, skillab_course.id)
        amount=skillab_course.amount
        sp,_=SkilllabCoursePayment.objects.get_or_create(user=user,skilllab_course=skillab_course,gateway_receipt=gateway_receipt,is_success=choices.YesNoChoices.NO,amount=amount,currency=choices.Currency.IND)
        
        # Get preferred gateway with fallback
        preferred_gateway = get_preferred_payment_gateway()
        payment,_=Payment.objects.get_or_create(
            user=user,
            gateway_receipt=sp.gateway_receipt,
            gateway=preferred_gateway,
            is_success=choices.YesNoChoices.NO,
            obj_id=sp.id,
            obj_type=choices.PaymentObjectType.SKILLLABCOURSE,
            amount=sp.amount,
            currency=sp.currency
        )
        
        # If ICICI Eazypay is not available, fallback to Razorpay
        if payment.gateway == choices.GatewayChoices.ICICIEAZYPAY and not is_gateway_available(choices.GatewayChoices.ICICIEAZYPAY):
            payment.gateway = choices.GatewayChoices.RAZORPAY
            payment.save()
        
        # If gateway is Razorpay, return payment info
        if payment.gateway == choices.GatewayChoices.RAZORPAY:
            # For Razorpay, return payment info (will be handled in get method)
            from django.http import JsonResponse
            import json
            try:
                payment_info_str = payment.get_payment_info()
                # get_payment_info() returns JSON string, parse it to dict
                payment_info_dict = json.loads(payment_info_str) if isinstance(payment_info_str, str) else payment_info_str
                return {
                    'type': 'json',
                    'data': {
                        'payment_info': payment_info_dict,
                        'gateway': 'razorpay'
                    }
                }
            except Exception as e:
                logger.exception("[Payment Error] Failed to get payment info: %s", e)
                # Fallback: return error message
                from django.http import HttpResponse
                return HttpResponse(f"Error preparing payment: {str(e)}", status=500)
        
        # Use ICICI Eazypay - wrap in try-except to handle encryption errors
        try:
            ezypy=IciciEazyPayService()
            reference_no=str(payment.id)
            sub_merchant_id=str(user.id)
            transaction_amount=str(amount)
            email = user.email
            login_user_id=str(user.id)
            mobile_no = user.mobile if user.mobile else "1111111111"
            remarks=gateway_receipt
            purchase_item="Skilllab Course {}".format(skillab_course.name)
            order_no_1="x"
            order_no="x"
            upivpa="x"
            payment_url = ezypy.get_encrypt_payment_url(reference_no=reference_no,sub_merchant_id=sub_merchant_id,transaction_amount=transaction_amount,email=email,login_user_id=login_user_id,mobile_no=mobile_no,remarks=remarks,purchase_item=purchase_item,order_no_1=order_no_1,order_no=order_no,upivpa=upivpa)
            return {
                'type': 'redirect',
                'url': payment_url
            }
        except (ValueError, AttributeError, Exception) as e:
            # If ICICI Eazypay fails (e.g., missing/empty encryption key), fallback to Razorpay
            logger.warning("[Payment] ICICI Eazypay failed, falling back to Razorpay: %s", e, exc_info=True)
            # Update payment gateway to Razorpay
            payment.gateway = choices.GatewayChoices.RAZORPAY
            payment.save()
            
            # Return Razorpay payment info
            from django.http import JsonResponse
            import json
            try:
                payment_info_str = payment.get_payment_info()
                # get_payment_info() returns JSON string, parse it to dict
                payment_info_dict = json.loads(payment_info_str) if isinstance(payment_info_str, str) else payment_info_str
                return {
                    'type': 'json',
                    'data': {
                        'payment_info': payment_info_dict,
                        'gateway': 'razorpay'
                    }
                }
            except Exception as e2:
                logger.exception("[Payment Error] Failed to get Razorpay payment info: %s", e2)
                # Fallback: return error message
                from django.http import HttpResponse
                return HttpResponse(f"Error preparing Razorpay payment: {str(e2)}", status=500)

    def get(self, request,slug,*args, **kwargs):
        from django.http import JsonResponse
        skillab_course=get_object_or_404(SkillLabCourse,slug=slug)
        # Free courses: redirect to course learning instead of payment
        if not skillab_course.amount or skillab_course.amount <= 0:
            return redirect('skilllabcourse:course_learning', course_slug=skillab_course.slug)
        result = self.get_payment_url(request,slug,*args, **kwargs)
        
        # Get success/fail URLs
        user=request.user
        gateway_receipt="SL{}_{}".format(request.user.id, skillab_course.id)
        sp,_=SkilllabCoursePayment.objects.get_or_create(user=user,skilllab_course=skillab_course,gateway_receipt=gateway_receipt,is_success=choices.YesNoChoices.NO,amount=skillab_course.amount,currency=choices.Currency.IND)
        url_info = sp.get_payment_success_fail_url()
        
        # Handle different return types
        if isinstance(result, dict):
            if result.get('type') == 'json':
                # Render payment template with Razorpay data
                try:
                    payment_info = result.get('data', {}).get('payment_info', {})
                    if isinstance(payment_info, str):
                        import json
                        payment_info = json.loads(payment_info)
                    
                    if not payment_info:
                        raise ValueError("Payment info is empty")
                    
                    # Convert payment_info dict to JSON string for template
                    import json
                    payment_info_json = json.dumps(payment_info)
                    
                    ctx = {
                        'skilllab': skillab_course,
                        'payment_info_json': payment_info_json,
                        'payment_info': payment_info,  # Keep dict version too
                        'gateway': result.get('data', {}).get('gateway', 'razorpay'),
                        'success_url': url_info['success_url'],
                        'fail_url': url_info['fail_url'],
                        'payment_id': sp.id,
                    }
                    return render(request, 'template20/skilllab/payment.html', ctx)
                except Exception as e:
                    logger.exception("[Template Render Error] %s", e)
                    from django.http import HttpResponse
                    return HttpResponse(f"Error rendering payment page: {str(e)}", status=500)
            elif result.get('type') == 'redirect':
                return redirect(result['url'])
        
        # Fallback: assume it's a URL string (for backward compatibility)
        if isinstance(result, str):
            return redirect(result)
        
        # If we get here, something went wrong
        from django.http import HttpResponse
        return HttpResponse("Unable to process payment. Please try again.", status=500)
    
class UpdateSkilllabCoursePaymentWithEazyPay(APIView):
    def post(self, request,*args, **kwargs):
        # Check if this is a Razorpay payment (has gateway_order_id, gateway_payment_id, gateway_signature)
        gateway_order_id = request.data.get('gateway_order_id')
        gateway_payment_id = request.data.get('gateway_payment_id')
        gateway_signature = request.data.get('gateway_signature')
        payment_id = request.data.get('payment_id')
        
        if gateway_order_id and gateway_payment_id and gateway_signature and payment_id:
            # Razorpay payment update
            try:
                sp = get_object_or_404(SkilllabCoursePayment, id=payment_id, user=request.user)
                payment = get_object_or_404(Payment, obj_id=sp.id, obj_type=choices.PaymentObjectType.SKILLLABCOURSE, user=request.user)
                
                # Update payment with Razorpay details
                # update_payment signature: (gateway_payment_id, gateway_order_id, gateway_signature)
                payment_status = payment.update_payment(gateway_payment_id, gateway_order_id, gateway_signature)
                try:
                    from invoices.utils import record_gateway_callback
                    from invoices.models import PaymentGatewayHealth
                    record_gateway_callback(
                        PaymentGatewayHealth.RAZORPAY,
                        success=bool(payment_status),
                        callback_url=request.build_absolute_uri(request.path) if request else None,
                    )
                except Exception:
                    pass
                if payment_status:
                    redirect_url = sp.get_payment_success_fail_url().get("success_url")
                    sp.is_success = choices.YesNoChoices.YES
                    sp.save()
                    send_skillabcourse_payment_success_mail.delay(sp.id)
                    return Response({'success': True, 'redirect_url': redirect_url}, status=status.HTTP_200_OK)
                else:
                    redirect_url = sp.get_payment_success_fail_url().get("fail_url")
                    return Response({'success': False, 'redirect_url': redirect_url}, status=status.HTTP_200_OK)
            except Exception as e:
                logger.exception("[Payment Update Error] %s", e)
                # Try to get fail URL
                try:
                    sp = get_object_or_404(SkilllabCoursePayment, id=payment_id, user=request.user)
                    redirect_url = sp.get_payment_success_fail_url().get("fail_url")
                except:
                    redirect_url = reverse('skilllabcourse:skilllabcourselist')
                return HttpResponseRedirect(redirect_url)
        
        # ICICI Eazypay payment update (original logic)
        response_code=request.data.get("Response Code")
        unique_reference_no=request.data.get("Unique Ref Number")
        service_tax_amount=request.data.get("Service Tax Amount") 
        processing_fee_amount=request.data.get("Processing Fee Amount")
        total_amount=request.data.get("Total Amount")
        transaction_amount=request.data.get("Transaction Amount")
        transaction_date=request.data.get("Transaction Date")
        interchange_value=request.data.get("Interchange Value")
        tdr=request.data.get("TDR")
        payment_mode=request.data.get("Payment Mode")
        submerchantid=request.data.get("SubMerchantId")
        referenceno=request.data.get("ReferenceNo")
        rs=request.data.get("RS")
        tps=request.data.get("TPS")
        mandotry_fields=request.data.get("mandatory fields")
        optional_fields=request.data.get("optional fields")
        rsv=request.data.get("RSV")
        
        payment=get_object_or_404(Payment,id=referenceno,user__id=submerchantid)
        sp=get_object_or_404(SkilllabCoursePayment,id=payment.obj_id,user__id=submerchantid)
            
        payment_status=payment.update_eazypay_payment(response_code,unique_reference_no,service_tax_amount,processing_fee_amount,total_amount,transaction_amount,transaction_date,interchange_value,tdr,payment_mode,rs=rs,tps=tps,rsv=rsv)
        try:
            from invoices.utils import record_gateway_callback
            from invoices.models import PaymentGatewayHealth
            record_gateway_callback(
                PaymentGatewayHealth.ICICI_EAZYPAY,
                success=bool(payment_status),
                error_message=None if payment_status else 'Response code: {}'.format(response_code),
                callback_url=request.build_absolute_uri(request.path) if request else None,
            )
        except Exception:
            pass
        if payment_status==choices.YesNoChoices.YES:
            redirect_url=sp.get_payment_success_fail_url().get("success_url")
            sp.is_success=choices.YesNoChoices.YES
            sp.save()
            send_skillabcourse_payment_success_mail.delay(sp.id)
        else:
            redirect_url=sp.get_payment_success_fail_url().get("fail_url")
            
        return HttpResponseRedirect(redirect_url)