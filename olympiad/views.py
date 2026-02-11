"""
NSEO Olympiad views.
Uses project auth (request.user); login_required for student actions.
"""
import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.utils import timezone
from django.db import transaction

from .models import (
    OlympiadExam,
    OlympiadQuestion,
    OlympiadExamQuestionSet,
    OlympiadRegistration,
    OlympiadSession,
    OlympiadResponse,
)


def _get_questions_for_exam(exam):
    """Return ordered questions for exam (via exam_question_sets or exam.questions)."""
    sets = OlympiadExamQuestionSet.objects.filter(exam=exam).select_related('question').order_by('order')
    if sets.exists():
        return [s.question for s in sets]
    return list(exam.questions.order_by('order'))


def _shuffle_options(options, seed):
    """Deterministic shuffle of options based on seed (e.g. user id)."""
    if not options or not isinstance(options, list):
        return options
    shuffled = list(options)
    h = 0
    for c in str(seed):
        h = ((h << 5) - h) + ord(c)
        h = h & 0xFFFFFFFF
    for i in range(len(shuffled) - 1, 0, -1):
        j = abs((h + i) % (i + 1))
        shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
    return shuffled


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class OlympiadExamListView(TemplateView):
    """List published Olympiad exams (web)."""
    template_name = "olympiad/exam_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        exams = OlympiadExam.objects.filter(
            object_status=1,
            is_published=True,
            status__in=('published', 'ongoing', 'draft'),
        ).order_by('-exam_date')
        registrations = OlympiadRegistration.objects.filter(
            user=self.request.user,
            exam__in=exams,
        ).select_related('exam')
        registered_ids = {r.exam_id for r in registrations}
        # Exams this user has already completed (attempted and submitted); map exam_id -> latest session_id for links
        exam_ids = [e.id for e in exams]
        completed_sessions = OlympiadSession.objects.filter(
            user=self.request.user,
            exam_id__in=exam_ids,
            status='completed',
        ).order_by('-ended_at').values('exam_id', 'id')
        completed_exam_ids = set()
        completed_session_by_exam = {}
        for s in completed_sessions:
            completed_exam_ids.add(s['exam_id'])
            if s['exam_id'] not in completed_session_by_exam:
                completed_session_by_exam[s['exam_id']] = s['id']
        ctx['exams'] = exams
        ctx['registered_ids'] = registered_ids
        ctx['completed_exam_ids'] = completed_exam_ids
        ctx['completed_session_by_exam'] = completed_session_by_exam
        return ctx


def olympiad_exam_list_api(request):
    """JSON list of published exams (for API/frontend)."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    exams = OlympiadExam.objects.filter(
        object_status=1,
        is_published=True,
        status__in=('published', 'ongoing'),
    ).order_by('-exam_date')
    data = [
        {
            'id': e.id,
            'name': e.name,
            'level': e.level,
            'class_level': e.class_level,
            'exam_date': e.exam_date.isoformat() if e.exam_date else None,
            'duration_minutes': e.duration_minutes,
            'total_marks': e.total_marks,
        }
        for e in exams
    ]
    return JsonResponse({'exams': data})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class OlympiadRegisterView(View):
    """Register current user for an exam (creates OlympiadRegistration)."""

    def post(self, request, exam_id):
        exam = get_object_or_404(OlympiadExam, id=exam_id, object_status=1, is_published=True)
        reg, created = OlympiadRegistration.objects.get_or_create(
            user=request.user,
            exam=exam,
            defaults={
                'registration_type': 'individual',
                'payment_status': 'completed',  # For Phase 1 / demo; integrate payment later
            },
        )
        if not created and reg.payment_status != 'completed':
            reg.payment_status = 'completed'
            reg.save(update_fields=['payment_status'])
        return JsonResponse({
            'success': True,
            'message': 'Registered successfully',
            'registration_id': reg.id,
        })


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class OlympiadStartExamView(View):
    """Start an exam: create session and return first batch of questions (or one-by-one)."""

    def post(self, request, exam_id):
        exam = get_object_or_404(OlympiadExam, id=exam_id, object_status=1)
        reg = OlympiadRegistration.objects.filter(
            user=request.user,
            exam=exam,
            payment_status='completed',
        ).first()
        if not reg:
            return JsonResponse({'error': 'Not registered or payment not completed'}, status=403)

        # Check for existing in-progress session
        session = OlympiadSession.objects.filter(
            user=request.user,
            exam=exam,
            status='in_progress',
        ).first()
        if session:
            return JsonResponse({
                'success': True,
                'session_id': session.id,
                'exam_already_started': True,
                'message': 'Resume existing session',
            }, status=200)

        questions = _get_questions_for_exam(exam)
        if not questions:
            return JsonResponse({'error': 'No questions configured for this exam'}, status=400)

        with transaction.atomic():
            session = OlympiadSession.objects.create(
                user=request.user,
                exam=exam,
                status='in_progress',
                ip_address=_get_client_ip(request),
                device_id=request.POST.get('device_id', '') or request.GET.get('device_id', ''),
            )
            # Don't create responses yet; they are created on submit-answer

        # Return exam info and full question list (or first question only for strict one-by-one)
        end_time = timezone.now() + timezone.timedelta(minutes=exam.duration_minutes)
        questions_payload = []
        for idx, q in enumerate(questions):
            opts = q.options
            if opts and isinstance(opts, list):
                opts = _shuffle_options(opts, request.user.id)
            questions_payload.append({
                'question_id': q.id,
                'order': idx + 1,
                'type': q.question_type,
                'content': q.content,
                'options': opts,
                'marks': q.marks,
                'estimated_time_seconds': q.estimated_time_seconds,
            })

        return JsonResponse({
            'success': True,
            'session_id': session.id,
            'exam_id': exam.id,
            'duration_minutes': exam.duration_minutes,
            'total_marks': exam.total_marks,
            'end_time': end_time.isoformat(),
            'questions': questions_payload,
        })


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class OlympiadSubmitAnswerView(View):
    """Submit a single answer and optionally return next question."""

    def post(self, request):
        try:
            body = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        session_id = body.get('session_id')
        question_id = body.get('question_id')
        answer = body.get('answer')
        time_taken_seconds = int(body.get('time_taken_seconds', 0) or 0)
        flagged = bool(body.get('flagged', False))
        if not session_id or not question_id:
            return JsonResponse({'error': 'session_id and question_id required'}, status=400)

        session = get_object_or_404(
            OlympiadSession,
            id=session_id,
            user=request.user,
            status='in_progress',
        )
        question = get_object_or_404(OlympiadQuestion, id=question_id)
        # Allow if question is linked to this exam via exam FK or exam_question_sets
        if question.exam_id and question.exam_id != session.exam_id:
            return JsonResponse({'error': 'Question does not belong to this exam'}, status=400)
        if not question.exam_id and not OlympiadExamQuestionSet.objects.filter(exam=session.exam, question=question).exists():
            return JsonResponse({'error': 'Question does not belong to this exam'}, status=400)

        # Auto-score MCQ
        marks_awarded = None
        if question.question_type == 'mcq' and question.correct_answer is not None:
            correct = question.correct_answer
            if isinstance(correct, dict) and 'option_id' in correct:
                is_correct = answer == correct.get('option_id')
            else:
                is_correct = answer == correct
            marks_awarded = question.marks if is_correct else 0

        with transaction.atomic():
            resp, created = OlympiadResponse.objects.update_or_create(
                session=session,
                question=question,
                defaults={
                    'response': answer if isinstance(answer, (dict, list)) else {'value': answer},
                    'time_taken_seconds': time_taken_seconds,
                    'flagged_for_review': flagged,
                    'marks_awarded': marks_awarded,
                    'auto_scored': marks_awarded is not None,
                },
            )

        return JsonResponse({
            'success': True,
            'marks_awarded': float(resp.marks_awarded) if resp.marks_awarded is not None else None,
            'next_question_available': True,
        })


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class OlympiadSubmitExamView(View):
    """End exam: set session to completed and return summary."""

    def post(self, request, session_id):
        session = get_object_or_404(
            OlympiadSession,
            id=session_id,
            user=request.user,
            status='in_progress',
        )
        from django.db.models import Sum
        total = session.responses.aggregate(s=Sum('marks_awarded'))
        total_marks = total['s'] or 0
        with transaction.atomic():
            session.status = 'completed'
            session.ended_at = timezone.now()
            session.total_marks_awarded = total_marks
            session.save(update_fields=['status', 'ended_at', 'total_marks_awarded'])

        return JsonResponse({
            'success': True,
            'session_id': session.id,
            'total_marks_awarded': float(total_marks),
            'answered_count': session.responses.count(),
            'status': 'completed',
        })


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class OlympiadTakeExamView(TemplateView):
    """Take exam page: show questions for an active session."""
    template_name = "olympiad/take_exam.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        session_id = kwargs.get('session_id')
        session = get_object_or_404(
            OlympiadSession,
            id=session_id,
            user=self.request.user,
            status='in_progress',
        )
        questions = _get_questions_for_exam(session.exam)
        end_time = session.started_at + timezone.timedelta(minutes=session.exam.duration_minutes)
        question_list = []
        for idx, q in enumerate(questions):
            opts = _shuffle_options(q.options, self.request.user.id) if q.options else None
            content = q.content or {}
            content_text = content.get('text', content) if isinstance(content, dict) else content
            question_list.append({
                'id': q.id,
                'order': idx + 1,
                'type': q.question_type,
                'content': q.content,
                'content_text': content_text,
                'options': opts,
                'marks': q.marks,
            })
        ctx['session'] = session
        ctx['questions'] = question_list
        ctx['end_time_iso'] = end_time.isoformat()
        return ctx


def _correct_answer_text(question):
    """Return human-readable correct answer for display (e.g. option text for MCQ)."""
    if question.correct_answer is None:
        return None
    correct = question.correct_answer
    option_id = correct.get('option_id', correct) if isinstance(correct, dict) else correct
    if question.options and isinstance(question.options, list):
        for opt in question.options:
            if isinstance(opt, dict) and opt.get('id') == option_id:
                return opt.get('text', str(option_id))
    return str(option_id)


def _student_answer_text(question, response_value):
    """Return human-readable student answer from response JSON."""
    if response_value is None:
        return '—'
    if isinstance(response_value, dict):
        val = response_value.get('value', response_value)
    else:
        val = response_value
    if question.options and isinstance(question.options, list):
        for opt in question.options:
            if isinstance(opt, dict) and str(opt.get('id')) == str(val):
                return opt.get('text', str(val))
    return str(val)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class OlympiadResultDetailView(TemplateView):
    """Detailed result for a completed session: per-question breakdown with correct/incorrect."""
    template_name = "olympiad/result_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        session_id = kwargs.get('session_id')
        session = get_object_or_404(
            OlympiadSession,
            id=session_id,
            user=self.request.user,
            status='completed',
        )
        questions = _get_questions_for_exam(session.exam)
        response_map = {r.question_id: r for r in session.responses.select_related('question')}
        rows = []
        for idx, q in enumerate(questions):
            resp = response_map.get(q.id)
            student_val = resp.response.get('value', resp.response) if resp and isinstance(resp.response, dict) else (resp.response if resp else None)
            rows.append({
                'order': idx + 1,
                'question': q,
                'question_text': (q.content or {}).get('text', '') if isinstance(q.content, dict) else str(q.content or ''),
                'student_answer': _student_answer_text(q, student_val) if resp else '—',
                'correct_answer': _correct_answer_text(q),
                'marks_awarded': float(resp.marks_awarded) if resp and resp.marks_awarded is not None else 0,
                'marks_max': q.marks,
                'correct': resp and resp.marks_awarded is not None and resp.marks_awarded >= q.marks,
            })
        ctx['session'] = session
        ctx['result_rows'] = rows
        ctx['total_marks'] = session.exam.total_marks
        ctx['total_awarded'] = float(session.total_marks_awarded or 0)
        return ctx


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class OlympiadCertificateView(TemplateView):
    """Certificate view for a completed Olympiad session (print-friendly)."""
    template_name = "olympiad/certificate.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        session_id = kwargs.get('session_id')
        session = get_object_or_404(
            OlympiadSession,
            id=session_id,
            user=self.request.user,
            status='completed',
        )
        ctx['session'] = session
        ctx['student_name'] = getattr(session.user, 'name', None) or session.user.email or 'Student'
        ctx['exam_name'] = session.exam.name
        ctx['score'] = float(session.total_marks_awarded or 0)
        ctx['total_marks'] = session.exam.total_marks
        ctx['completed_date'] = session.ended_at or timezone.now()
        return ctx


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class OlympiadMyResultsView(TemplateView):
    """List current user's Olympiad sessions (results)."""
    template_name = "olympiad/my_results.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sessions = OlympiadSession.objects.filter(
            user=self.request.user,
            status='completed',
        ).select_related('exam').order_by('-ended_at')
        ctx['sessions'] = sessions
        return ctx
