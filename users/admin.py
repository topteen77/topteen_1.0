from django.contrib import admin
from django.contrib.admin.decorators import action
from core import choices
from .models import (
    User,
    UserProfile,
    UserCalender,
    UserNote,
    UserResume,
    UserFolder,
    UserSearchHistory,
    ResumeStudioHtmlTemplate,
    ResumeV2AISettings,
    EducationLoanApplication,
    EducationLoanCRMSettings,
    EducationLoanOpsSettings,
    EducationLoanRemark,
    LoanInstantLoginToken,
)
from django.urls import reverse, path
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.html import format_html_join
from django.contrib import messages
from django.conf import settings
from django.db.models import Q, Max
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
import os
import glob
import json

try:
    from payments.models import Payment
except ImportError:
    Payment = None
try:
    from psychometric_tests.models import PsychometricTestPayment
except ImportError:
    PsychometricTestPayment = None
try:
    from skilllab.models import SkilllabCoursePayment, SkillLabCourse
except ImportError:
    SkilllabCoursePayment = None
    SkillLabCourse = None

MANUAL_CASH_PAYMENT_DEFAULT_REMARK = 'Manual payment cash'


class StudentClassFilter(admin.SimpleListFilter):
    """Filter users by ClassAndSection label (via StudentManagement)."""

    title = 'Class'
    parameter_name = 'student_class'

    def lookups(self, request, model_admin):
        from institute.models import ClassAndSection

        values = (
            ClassAndSection.objects
            .exclude(class_and_section__isnull=True)
            .exclude(class_and_section='')
            .values_list('class_and_section', flat=True)
            .distinct()
            .order_by('class_and_section')
        )
        return [(v, v) for v in values]

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        return queryset.filter(
            student_management__class_and_section__class_and_section=value,
        ).distinct()


def _record_manual_cash_skilllab_payment(user, course, amount=None, remark=None, staff_user=None):
    """
    Record an offline cash payment and activate Skill Lab course access.
    No Razorpay — stores remark on the Payment row.
    Returns (skilllab_payment, payment, status) where status is 'created' or 'already_active'.
    """
    from payments.models import Payment
    from payments.reconciliation import finalize_side_effects_after_gateway_success

    if not course:
        raise ValueError('Course is required')
    amount = amount if amount is not None else course.amount
    remark = (remark or MANUAL_CASH_PAYMENT_DEFAULT_REMARK).strip() or MANUAL_CASH_PAYMENT_DEFAULT_REMARK
    if staff_user and getattr(staff_user, 'pk', None):
        remark = '{} (staff #{})'.format(remark, staff_user.pk)

    gateway_receipt = 'SL{}_{}'.format(user.id, course.id)
    sp, _ = SkilllabCoursePayment.objects.get_or_create(
        user=user,
        skilllab_course=course,
        defaults={
            'gateway_receipt': gateway_receipt,
            'is_success': choices.YesNoChoices.NO,
            'amount': amount,
            'currency': choices.Currency.IND,
        },
    )
    if sp.is_success == choices.YesNoChoices.YES:
        return sp, None, 'already_active'

    sp.gateway_receipt = gateway_receipt
    sp.amount = amount
    sp.save(update_fields=['gateway_receipt', 'amount'])

    payment, _ = Payment.objects.get_or_create(
        user=user,
        gateway_receipt=gateway_receipt,
        obj_id=sp.id,
        obj_type=choices.PaymentObjectType.SKILLLABCOURSE,
        defaults={
            'gateway': choices.GatewayChoices.MANUAL,
            'is_success': choices.YesNoChoices.NO,
            'amount': amount,
            'currency': choices.Currency.IND,
            'payment_mode': 'Manual cash',
            'response_details': remark,
        },
    )
    payment.gateway = choices.GatewayChoices.MANUAL
    payment.amount = amount
    payment.payment_mode = 'Manual cash'
    payment.response_details = remark
    payment.is_success = choices.YesNoChoices.YES
    payment.save(
        update_fields=['gateway', 'amount', 'payment_mode', 'response_details', 'is_success']
    )
    finalize_side_effects_after_gateway_success(payment)
    return sp, payment, 'created'


# Register your models here.


# Psychometric test keys (TestCompletion flags + Results test_paper)
PSYCHOMETRIC_TEST_KEYS = [
    ('test1', 'test1_complete'), ('test2', 'test2_complete'), ('test3', 'test3_complete'),
    ('numerical', 'numerical_complete'), ('verbal', 'verbal_complete'), ('logical', 'logical_complete'),
    ('emotional', 'emotional_complete'), ('machanical', 'machanical_complete'),
    ('language', 'language_complete'), ('spatial', 'spatial_complete'),
]


def _skilllab_course_display_name(course):
    """Label skill lab courses in the admin reset UI."""
    name_lower = (course.name or '').lower()
    if any(kw in name_lower for kw in ('career', 'class 6', 'class 7', 'class 8', 'readiness', 'awareness')):
        return 'Career Readiness: ' + course.name
    return 'Skill Lab: ' + course.name


def _get_user_skilllab_course_ids(user_ids):
    """Return course IDs where any selected user has skill lab learning progress."""
    from skilllab.models import (
        SkillLabCourseProgressSummary,
        SkillLabCourseResume,
        SkillLabCourseProgress,
        SkillLabWorksheetProgress,
        SkillLabMCQAttempt,
    )
    if not user_ids:
        return set()
    course_ids = set()
    course_ids.update(
        SkillLabCourseProgressSummary.objects.filter(user_id__in=user_ids)
        .values_list('skilllab_course_id', flat=True)
    )
    course_ids.update(
        SkillLabCourseResume.objects.filter(user_id__in=user_ids)
        .values_list('skilllab_course_id', flat=True)
    )
    course_ids.update(
        SkillLabCourseProgress.objects.filter(user_id__in=user_ids)
        .values_list('skilllab_course_id', flat=True)
    )
    course_ids.update(
        SkillLabWorksheetProgress.objects.filter(user_id__in=user_ids)
        .values_list('activity__skilllab_chapter__skilllab_id', flat=True)
    )
    course_ids.update(
        SkillLabMCQAttempt.objects.filter(user_id__in=user_ids)
        .values_list('mcq__skilllab_chapter__skilllab_id', flat=True)
    )
    return {cid for cid in course_ids if cid}


def _reset_skilllab_course(user, course_id):
    """Clear all learning progress for one user on one skill lab course."""
    from skilllab.models import (
        SkillLabCourse,
        SkillLabCourseProgressSummary,
        SkillLabWorksheetProgress,
        SkillLabMCQAttempt,
        SkillLabCourseResume,
        SkillLabCourseProgress,
        SkillLabUserHighlight,
        SkillLabUserNote,
        SkillLabUserBookmark,
    )
    course = SkillLabCourse.objects.filter(pk=course_id).first()
    if not course:
        return
    SkillLabCourseProgressSummary.objects.filter(user=user, skilllab_course=course).delete()
    SkillLabCourseResume.objects.filter(user=user, skilllab_course=course).delete()
    SkillLabCourseProgress.objects.filter(user=user, skilllab_course=course).delete()
    SkillLabWorksheetProgress.objects.filter(
        user=user, activity__skilllab_chapter__skilllab=course
    ).delete()
    SkillLabMCQAttempt.objects.filter(
        user=user, mcq__skilllab_chapter__skilllab=course
    ).delete()
    SkillLabUserHighlight.objects.filter(user=user, skilllab_course=course).delete()
    SkillLabUserNote.objects.filter(user=user, skilllab_course=course).delete()
    SkillLabUserBookmark.objects.filter(user=user, skilllab_course=course).delete()


def _reset_all_skilllab_courses(user):
    for course_id in _get_user_skilllab_course_ids([user.id]):
        _reset_skilllab_course(user, course_id)


def _get_students_with_recent_tests_queryset(email_filter=None):
    """Return User queryset of students with test or skill lab activity."""
    from core.choices import UserType
    qs = User.objects.filter(user_type=UserType.STUDENT).filter(
        Q(test_sessions__isnull=False)
        | Q(results__isnull=False)
        | Q(skilllabcourseprogresssummary__isnull=False)
        | Q(skilllabcourseresume__isnull=False)
        | Q(skilllabcourseprogress__isnull=False)
    ).annotate(
        latest_session=Max('test_sessions__created_at'),
        latest_result=Max('results__modified'),
        latest_skilllab=Max('skilllabcourseprogresssummary__updated_at'),
    ).distinct()
    if email_filter:
        qs = qs.filter(email__icontains=email_filter.strip())
    return qs.order_by('-latest_session', '-latest_result', '-latest_skilllab')


def _get_user_test_count(user):
    """Return total test count for a user (psychometric, post-matric, skill lab courses)."""
    from app.models import Results
    psychometric_count = Results.objects.filter(user=user).count()
    post_matric_count = user.test_sessions.count()
    skilllab_count = len(_get_user_skilllab_course_ids([user.id]))
    return psychometric_count + post_matric_count + skilllab_count


def _get_tests_for_users(user_ids):
    """Return list of tests that the given users have. Each item: { id, name, type }."""
    from app.models import Results
    from app.stream_decision import is_questionnaire_completed
    from app_post_matric.models import TestSession
    from skilllab.models import SkillLabCourse
    if not user_ids:
        return []
    users = list(User.objects.filter(pk__in=user_ids))
    test_ids_seen = set()
    out = []
    # Psychometric: distinct test_paper from Results
    result_papers = Results.objects.filter(user_id__in=user_ids).values_list('test_paper', flat=True).distinct()
    for paper in result_papers:
        key = 'psychometric_' + paper
        if key not in test_ids_seen:
            test_ids_seen.add(key)
            out.append({'id': key, 'name': 'Psychometric: ' + paper, 'type': 'psychometric'})
    for user in users:
        try:
            test3_result = Results.objects.get(user=user, test_paper='test3')
        except Results.DoesNotExist:
            continue
        if is_questionnaire_completed(test3_result.results):
            if 'stream_decision_questionnaire' not in test_ids_seen:
                test_ids_seen.add('stream_decision_questionnaire')
                out.append({
                    'id': 'stream_decision_questionnaire',
                    'name': 'Stream Decision Questionnaire',
                    'type': 'questionnaire',
                })
            break
    # Post-matric: distinct Test from TestSession
    sessions = TestSession.objects.filter(user_id__in=user_ids).select_related('test')
    for s in sessions:
        if s.test_id and ('post_matric_' + str(s.test_id)) not in test_ids_seen:
            test_ids_seen.add('post_matric_' + str(s.test_id))
            out.append({'id': 'post_matric_' + str(s.test_id), 'name': 'Post-matric: ' + (s.test.title if s.test else str(s.test_id)), 'type': 'post_matric'})
    # Skill Lab / Career Readiness courses with progress
    for course in SkillLabCourse.objects.filter(pk__in=_get_user_skilllab_course_ids(user_ids)).order_by('name'):
        key = 'skilllab_' + str(course.id)
        if key not in test_ids_seen:
            test_ids_seen.add(key)
            out.append({
                'id': key,
                'name': _skilllab_course_display_name(course),
                'type': 'skilllab',
            })
    return out


def _reset_stream_decision_questionnaire(user):
    from app.stream_decision import clear_questionnaire

    return clear_questionnaire(user)


def _reset_student_tests(user, test_ids=None):
    """Reset test flags for one user. If test_ids is None or ['all'], reset all; else reset only given test ids."""
    from app.models import TestCompletion, Results
    from app_post_matric.models import TestSession
    if test_ids is None or (isinstance(test_ids, list) and ('all' in test_ids or not test_ids)):
        # Reset all
        TestCompletion.objects.filter(user=user).update(
            test1_complete=False, test2_complete=False, test3_complete=False,
            numerical_complete=False, verbal_complete=False, logical_complete=False,
            emotional_complete=False, machanical_complete=False,
            language_complete=False, spatial_complete=False,
        )
        Results.objects.filter(user=user).delete()
        TestSession.objects.filter(user=user).delete()
        _reset_stream_decision_questionnaire(user)
        _reset_all_skilllab_courses(user)
        return
    # Partial reset
    tc_update = {}
    for paper, flag_name in PSYCHOMETRIC_TEST_KEYS:
        key = 'psychometric_' + paper
        if key in test_ids:
            tc_update[flag_name] = False
    if tc_update:
        TestCompletion.objects.filter(user=user).update(**tc_update)
    for tid in test_ids:
        if tid == 'stream_decision_questionnaire':
            _reset_stream_decision_questionnaire(user)
        elif tid.startswith('psychometric_'):
            paper = tid.replace('psychometric_', '')
            Results.objects.filter(user=user, test_paper=paper).delete()
        elif tid.startswith('post_matric_'):
            try:
                pk = int(tid.replace('post_matric_', ''))
                TestSession.objects.filter(user=user, test_id=pk).delete()
            except ValueError:
                pass
        elif tid.startswith('skilllab_'):
            try:
                course_id = int(tid.replace('skilllab_', ''))
                _reset_skilllab_course(user, course_id)
            except ValueError:
                pass


class PaymentInline(admin.TabularInline):
    extra = 0
    max_num = 0
    can_delete = False
    readonly_fields = (
        'payment_id', 'amount_display', 'gateway_display', 'obj_type_display',
        'is_success_display', 'payment_remark_display', 'gateway_order_id', 'created', 'payment_actions',
    )
    fields = readonly_fields
    show_change_link = True
    verbose_name = 'Payment'
    verbose_name_plural = 'Payments'

    def payment_id(self, obj):
        return obj.id if obj else '-'

    payment_id.short_description = 'ID'

    def amount_display(self, obj):
        return obj.get_display_price() if obj else '-'

    amount_display.short_description = 'Amount'

    def gateway_display(self, obj):
        return obj.get_gateway_display() if obj else '-'

    gateway_display.short_description = 'Gateway'

    def obj_type_display(self, obj):
        return obj.get_obj_type_display() if obj else '-'

    obj_type_display.short_description = 'For'

    def is_success_display(self, obj):
        if obj is None:
            return '-'
        if obj.is_success == 1:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')

    is_success_display.short_description = 'Success'

    def payment_remark_display(self, obj):
        if not obj:
            return '-'
        if obj.gateway == choices.GatewayChoices.MANUAL or (obj.payment_mode or '').lower().startswith('manual'):
            return obj.response_details or MANUAL_CASH_PAYMENT_DEFAULT_REMARK
        return format_html('<span style="color:#999;">—</span>')

    payment_remark_display.short_description = 'Remark'

    def payment_actions(self, obj):
        if not obj or not obj.pk or not obj.user_id:
            return '-'
        if obj.is_success == choices.YesNoChoices.YES:
            return format_html('<span style="color:#666;">—</span>')
        if obj.obj_type != choices.PaymentObjectType.SKILLLABCOURSE:
            return format_html('<span style="color:#999;">—</span>')
        cash_url = reverse(
            'admin:users_user_manual_cash_payment',
            args=[obj.user_id],
        ) + '?payment_id={}'.format(obj.id)
        return format_html(
            '<a class="button" href="{}" style="padding:4px 8px;font-size:11px;">Manual payment (cash)</a>',
            cash_url,
        )

    payment_actions.short_description = 'Actions'


class SkilllabCoursePaymentInline(admin.TabularInline):
    extra = 0
    max_num = 0
    can_delete = False
    readonly_fields = (
        'payment_id', 'course_display', 'amount_display', 'is_success_display', 'created',
        'course_payment_actions',
    )
    fields = readonly_fields
    show_change_link = True
    verbose_name = 'Skill Lab course payment'
    verbose_name_plural = 'Skill Lab course payments'

    def payment_id(self, obj):
        return obj.id if obj else '-'

    payment_id.short_description = 'ID'

    def course_display(self, obj):
        if not obj or not obj.skilllab_course:
            return '-'
        return obj.skilllab_course.name

    course_display.short_description = 'Course'

    def amount_display(self, obj):
        return obj.get_display_price() if obj else '-'

    amount_display.short_description = 'Amount'

    def is_success_display(self, obj):
        if obj is None:
            return '-'
        if obj.is_success == 1:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Not active</span>')

    is_success_display.short_description = 'Access'

    def course_payment_actions(self, obj):
        if not obj or not obj.pk or obj.is_success == choices.YesNoChoices.YES:
            return format_html('<span style="color:#666;">—</span>')
        if not obj.user_id:
            return '-'
        cash_url = reverse(
            'admin:users_user_manual_cash_payment',
            args=[obj.user_id],
        ) + '?course_payment_id={}'.format(obj.id)
        return format_html(
            '<a class="button" href="{}" style="padding:4px 8px;font-size:11px;">Manual payment (cash)</a>',
            cash_url,
        )

    course_payment_actions.short_description = 'Actions'


class PsychometricTestPaymentInline(admin.TabularInline):
    extra = 0
    max_num = 0
    can_delete = False
    readonly_fields = ('payment_id', 'test_type_display', 'amount_display', 'is_success_display', 'created')
    fields = readonly_fields
    show_change_link = True
    verbose_name = 'Psychometric test payment'
    verbose_name_plural = 'Psychometric test payments'

    def payment_id(self, obj):
        return obj.id if obj else '-'

    payment_id.short_description = 'ID'

    def test_type_display(self, obj):
        return obj.get_test_name() if obj else '-'

    test_type_display.short_description = 'Test'

    def amount_display(self, obj):
        return obj.get_display_price() if obj else '-'

    amount_display.short_description = 'Amount'

    def is_success_display(self, obj):
        if obj is None:
            return '-'
        if obj.is_success == 1:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')

    is_success_display.short_description = 'Success'


@admin.register(ResumeStudioHtmlTemplate)
class ResumeStudioHtmlTemplateAdmin(admin.ModelAdmin):
    """HTML resume studio gallery (student /templates/embed iframe); keys map to app.js RENDERERS."""

    list_display = (
        "name",
        "template_key",
        "studio_html_preview_link",
        "category",
        "mock_class",
        "is_active",
        "sort_order",
    )
    list_filter = ("is_active", "category")
    search_fields = ("name", "template_key", "description")
    ordering = ("sort_order", "id")
    readonly_fields = ("studio_html_preview_link_detail",)
    actions = ("activate_selected_studio_templates", "deactivate_selected_studio_templates")

    @action(description="Activate selected templates", permissions=["change"])
    def activate_selected_studio_templates(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, "Activated %d template(s)." % n, messages.SUCCESS)

    @action(description="Deactivate selected templates", permissions=["change"])
    def deactivate_selected_studio_templates(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, "Deactivated %d template(s)." % n, messages.SUCCESS)

    @admin.display(description="Preview")
    def studio_html_preview_link(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("users:admin_resume_studio_html_template_preview", kwargs={"template_pk": obj.pk})
        return format_html(
            '<a class="button" href="{}" target="_blank" rel="noopener noreferrer">Preview</a>',
            url,
        )

    @admin.display(description="HTML studio preview")
    def studio_html_preview_link_detail(self, obj):
        if not obj.pk:
            return "Save this row first, then use Preview."
        url = reverse("users:admin_resume_studio_html_template_preview", kwargs={"template_pk": obj.pk})
        return format_html(
            '<a class="button" href="{}" target="_blank" rel="noopener noreferrer">Open studio preview</a>'
            '<p class="help" style="margin-top:8px">Opens the same student resume studio with sample data and this layout. '
            "Changing <strong>template key</strong> only works for keys implemented in the prototype JavaScript.</p>",
            url,
        )


def _user_admin_inlines():
    inlines = []
    if Payment is not None:
        PaymentInline.model = Payment
        inlines.append(PaymentInline)
    if SkilllabCoursePayment is not None:
        SkilllabCoursePaymentInline.model = SkilllabCoursePayment
        inlines.append(SkilllabCoursePaymentInline)
    if PsychometricTestPayment is not None:
        PsychometricTestPaymentInline.model = PsychometricTestPayment
        inlines.append(PsychometricTestPaymentInline)
    return inlines


class UserAdmin(admin.ModelAdmin):
    # form = UserForm
    fields = [
        'name',
        'email',
        'mobile',
        'is_active',
        'is_staff',
        'image',
        'password',
        'groups',
        'user_permissions',
        'user_type',
        'user_status',
        'is_demo_account',
        'is_system_demo',
        'admin_password_reset',
        'admin_payment_tools',
    ]
    readonly_fields = ['is_system_demo', 'admin_password_reset', 'admin_payment_tools']
    inlines = _user_admin_inlines()
    # date_hierarchy = 'created'
    list_display = [
        'id',
        'name',
        'email',
        'mobile',
        'is_active',
        'is_demo_account',
        'admin_password_reset_link',
        'is_system_demo',
        'object_status',
        'created',
        'last_login',
    ]
    sortable_by=['id', 'name','email','mobile']
    ordering = ['-id']
    list_editable = ['is_demo_account']
    list_filter = ('is_active','is_demo_account','is_system_demo','last_login','user_type','object_status')
    search_fields=['id','name','email','mobile']
    actions = [
        'hard_delete_selected',
        'reset_counselor_course_soft',
        'reset_counselor_course_hard',
    ]
    change_list_template = 'admin/users/user/change_list.html'

    def _is_student_filter_active(self, request):
        """True when the changelist is filtered to Student (user_type=1)."""
        return request.GET.get('user_type__exact') == str(choices.UserType.STUDENT)

    def get_list_display(self, request):
        display = list(self.list_display)
        if self._is_student_filter_active(request) and 'student_class' not in display:
            try:
                idx = display.index('mobile') + 1
            except ValueError:
                idx = 3
            display.insert(idx, 'student_class')
        return display

    def get_list_filter(self, request):
        filters = list(self.list_filter)
        if self._is_student_filter_active(request) and StudentClassFilter not in filters:
            filters.append(StudentClassFilter)
        return filters

    @admin.display(description='Class')
    def student_class(self, obj):
        sms = getattr(obj, '_prefetched_objects_cache', {}).get('student_management')
        if sms is None:
            sms = obj.student_management.all()
        for sm in sms:
            cas = getattr(sm, 'class_and_section', None)
            if cas and cas.class_and_section:
                label = cas.class_and_section
                if cas.stream:
                    return '%s (%s)' % (label, cas.stream)
                return label
        return '—'

    def admin_password_reset(self, obj):
        if not obj or not obj.pk:
            return format_html(
                '<span class="help">Save the user first, then use this button to set a new password without the old password.</span>'
            )
        url = reverse(
            'admin:%s_%s_set_password'
            % (self.model._meta.app_label, self.model._meta.model_name),
            args=[obj.pk],
        )
        return format_html(
            '<a class="button" href="{}" style="display:inline-block;padding:10px 15px;background:#417690;color:#fff;'
            'text-decoration:none;border-radius:4px;font-weight:600;">Set new password (admin)</a>'
            '<p class="help" style="margin-top:8px;">Sets a new login password directly. Does not require the current password.</p>',
            url,
        )

    admin_password_reset.short_description = 'Password reset (admin)'

    def admin_payment_tools(self, obj):
        if not obj or not obj.pk:
            return format_html(
                '<span class="help">Save the user first, then add a manual cash payment to activate a paid Skill Lab course.</span>'
            )
        cash_url = reverse('admin:users_user_manual_cash_payment', args=[obj.pk])
        return format_html(
            '<p style="margin:0 0 8px;">Record an offline <strong>cash payment</strong> to activate a paid Skill Lab course. '
            'No Razorpay — a remark such as <em>Manual payment cash</em> is stored on the payment row.</p>'
            '<a class="button" href="{}" style="display:inline-block;padding:10px 15px;background:#417690;color:#fff;'
            'text-decoration:none;border-radius:4px;font-weight:600;">Add manual payment (cash)</a>',
            cash_url,
        )

    admin_payment_tools.short_description = 'Manual payment (cash)'

    def admin_password_reset_link(self, obj):
        url = reverse(
            'admin:%s_%s_set_password'
            % (self.model._meta.app_label, self.model._meta.model_name),
            args=[obj.pk],
        )
        return format_html(
            '<a class="button" href="{}" style="display:inline-block;padding:4px 10px;background:#417690;'
            'color:#fff;text-decoration:none;border-radius:4px;font-size:12px;font-weight:600;">Set password</a>',
            url,
        )

    admin_password_reset_link.short_description = 'Password'
    admin_password_reset_link.admin_order_field = None

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'set-password/<int:user_id>/',
                self.admin_site.admin_view(self.set_password_view),
                name='%s_%s_set_password' % (self.model._meta.app_label, self.model._meta.model_name),
            ),
            path(
                'manual-cash-payment/<int:user_id>/',
                self.admin_site.admin_view(self.manual_cash_payment_view),
                name='users_user_manual_cash_payment',
            ),
            path('student-test-reset/', self.admin_site.admin_view(self.student_test_reset_view), name='users_user_student_test_reset'),
            path('student-test-reset/list/', self.admin_site.admin_view(self.student_test_reset_list_view), name='users_user_student_test_reset_list'),
            path('student-test-reset/tests/', self.admin_site.admin_view(self.student_test_reset_tests_view), name='users_user_student_test_reset_tests'),
            path('student-test-reset/action/', self.admin_site.admin_view(self.student_test_reset_action_view), name='users_user_student_test_reset_action'),
        ]
        return custom + urls

    def set_password_view(self, request, user_id):
        """Admin-only: set a user's password without knowing the old password."""
        if not (
            request.user.is_superuser
            or request.user.has_perm('users.change_user')
            or request.user.has_perm('counselor.change_counselor')
        ):
            messages.error(request, 'You do not have permission to reset passwords.')
            return redirect('admin:index')

        target = get_object_or_404(User, pk=user_id)

        if request.method == 'POST':
            p1 = request.POST.get('password1', '')
            p2 = request.POST.get('password2', '')
            if p1 != p2:
                messages.error(request, 'The two password fields did not match.')
            elif not p1:
                messages.error(request, 'Password cannot be empty.')
            else:
                # No AUTH_PASSWORD_VALIDATORS check here — admin may set any non-empty password.
                target.set_password(p1)
                # Single SQL UPDATE: avoids User.save() (avatar fetch, extra signals) for speed.
                User.objects.filter(pk=target.pk).update(
                    password=target.password,
                    modified=timezone.now(),
                )
                messages.success(
                    request,
                    'Password updated for %s.' % (target.email or target.pk),
                )
                return redirect(
                    'admin:%s_%s_changelist'
                    % (self.model._meta.app_label, self.model._meta.model_name),
                )

        context = {
            **self.admin_site.each_context(request),
            'title': 'Set password (%s)' % (target.email or target.pk),
            'opts': self.model._meta,
            'target_user': target,
        }
        return render(request, 'admin/users/user/set_password.html', context)

    def _staff_can_manage_payments(self, request):
        """Manual cash payment: Django admin / staff with user change permission only."""
        return request.user.is_active and (
            request.user.is_superuser
            or (
                request.user.is_staff
                and request.user.has_perm('users.change_user')
            )
        )

    def manual_cash_payment_view(self, request, user_id):
        """Staff: record offline cash payment and activate Skill Lab course access."""
        if not self._staff_can_manage_payments(request):
            messages.error(request, 'You do not have permission to record manual payments.')
            return redirect('admin:index')

        from payments.models import Payment

        target_user = get_object_or_404(User, pk=user_id)
        payment_id = (request.GET.get('payment_id') or request.POST.get('payment_id') or '').strip()
        course_payment_id = (request.GET.get('course_payment_id') or request.POST.get('course_payment_id') or '').strip()

        preset_course = None
        preset_amount = None
        if payment_id:
            gateway_payment = get_object_or_404(
                Payment,
                pk=int(payment_id),
                user_id=user_id,
                obj_type=choices.PaymentObjectType.SKILLLABCOURSE,
            )
            if gateway_payment.is_success == choices.YesNoChoices.YES:
                messages.warning(request, 'Payment #{} is already successful.'.format(gateway_payment.id))
                return redirect('admin:users_user_change', user_id)
            if SkilllabCoursePayment is not None:
                preset_course = SkilllabCoursePayment.objects.filter(
                    pk=gateway_payment.obj_id, user_id=user_id
                ).select_related('skilllab_course').first()
                if preset_course and preset_course.skilllab_course:
                    preset_course = preset_course.skilllab_course
            preset_amount = gateway_payment.amount
        elif course_payment_id and SkilllabCoursePayment is not None:
            sp = get_object_or_404(
                SkilllabCoursePayment.objects.select_related('skilllab_course'),
                pk=int(course_payment_id),
                user_id=user_id,
            )
            if sp.is_success == choices.YesNoChoices.YES:
                messages.warning(request, 'This course is already active for the user.')
                return redirect('admin:users_user_change', user_id)
            preset_course = sp.skilllab_course
            preset_amount = sp.amount

        paid_courses = []
        if SkillLabCourse is not None:
            paid_courses = list(
                SkillLabCourse.objects.filter(amount__gt=0, object_status=choices.ObjectStatus.ACTIVE)
                .order_by('name')
            )

        if request.method == 'POST':
            course_id = (request.POST.get('course_id') or '').strip()
            remark = (request.POST.get('remark') or MANUAL_CASH_PAYMENT_DEFAULT_REMARK).strip()
            amount_raw = (request.POST.get('amount') or '').strip()
            try:
                course = get_object_or_404(SkillLabCourse, pk=int(course_id))
                amount = int(amount_raw) if amount_raw else course.amount
            except (TypeError, ValueError):
                messages.error(request, 'Select a valid course and amount.')
            else:
                try:
                    sp, payment, status = _record_manual_cash_skilllab_payment(
                        target_user,
                        course,
                        amount=amount,
                        remark=remark,
                        staff_user=request.user,
                    )
                except Exception as exc:
                    messages.error(request, 'Could not record payment: {}'.format(exc))
                else:
                    if status == 'already_active':
                        messages.warning(
                            request,
                            '{} is already active for this user.'.format(
                                course.name if course else 'Course'
                            ),
                        )
                    else:
                        messages.success(
                            request,
                            'Manual cash payment recorded (₹{}). {} is now active. Remark: {}'.format(
                                amount,
                                course.name,
                                remark,
                            ),
                        )
                    return redirect('admin:users_user_change', user_id)

        context = {
            **self.admin_site.each_context(request),
            'title': 'Manual payment (cash)',
            'opts': self.model._meta,
            'target_user': target_user,
            'paid_courses': paid_courses,
            'preset_course': preset_course,
            'preset_amount': preset_amount,
            'default_remark': MANUAL_CASH_PAYMENT_DEFAULT_REMARK,
            'payment_id': payment_id,
            'course_payment_id': course_payment_id,
        }
        return render(request, 'admin/users/user/manual_cash_payment.html', context)

    def student_test_reset_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            'title': 'Student Test Reset',
            'opts': self.model._meta,
        }
        return render(request, 'admin/users/user/student_test_reset.html', context)

    def student_test_reset_list_view(self, request):
        email = request.GET.get('email', '').strip()
        page = request.GET.get('page', '1')
        per_page = min(int(request.GET.get('per_page', 20)), 100)
        qs = _get_students_with_recent_tests_queryset(email_filter=email or None)
        paginator = Paginator(qs, per_page)
        try:
            p = paginator.page(int(page))
        except (ValueError, TypeError):
            p = paginator.page(1)
        students = []
        for u in p.object_list:
            students.append({
                'id': u.id,
                'name': u.name or '',
                'email': u.email or '',
                'test_count': _get_user_test_count(u),
                'last_session': u.latest_session.isoformat() if getattr(u, 'latest_session', None) else None,
                'last_result': u.latest_result.isoformat() if getattr(u, 'latest_result', None) else None,
            })
        return JsonResponse({
            'students': students,
            'total': paginator.count,
            'page': p.number,
            'num_pages': paginator.num_pages,
            'per_page': per_page,
        })

    def student_test_reset_tests_view(self, request):
        """GET ?user_ids=1,2,3 - return list of tests for those users."""
        user_ids = request.GET.get('user_ids', '')
        if not user_ids:
            return JsonResponse({'tests': []})
        ids = [int(x.strip()) for x in user_ids.split(',') if x.strip()]
        tests = _get_tests_for_users(ids)
        return JsonResponse({'tests': tests})

    def student_test_reset_action_view(self, request):
        if request.method != 'POST':
            return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)
        try:
            body = json.loads(request.body) if request.body else {}
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
        user_ids = body.get('user_ids') or []
        test_ids = body.get('test_ids')  # None or ['all'] or ['psychometric_test1', 'post_matric_5', ...]
        reset_all = body.get('reset_all', False)
        email_filter = (body.get('email') or '').strip()
        if reset_all:
            qs = _get_students_with_recent_tests_queryset(email_filter=email_filter or None)
            user_ids = list(qs.values_list('id', flat=True))
        if not user_ids:
            return JsonResponse({'success': False, 'message': 'No students selected'}, status=400)
        count = 0
        for uid in user_ids:
            try:
                user = User.objects.get(pk=uid)
                _reset_student_tests(user, test_ids=test_ids)
                count += 1
            except User.DoesNotExist:
                continue
        return JsonResponse({'success': True, 'message': f'Test flags reset for {count} student(s).', 'count': count})

    def get_queryset(self, request):
        # Show all users including soft-deleted ones
        qs = User.objects.complete()
        if self._is_student_filter_active(request):
            from django.db.models import Prefetch
            from institute.models import StudentManagement

            qs = qs.prefetch_related(
                Prefetch(
                    'student_management',
                    queryset=StudentManagement.objects.select_related('class_and_section'),
                )
            )
        return qs
    
    
    def _reset_counselor_course_for_users(self, request, queryset, mode):
        from counselor.course_reset import reset_counselor_course_data_for_user

        if not request.user.is_superuser and not request.user.has_perm('users.change_user'):
            self.message_user(
                request,
                'You do not have permission to reset counselor course data.',
                messages.ERROR,
            )
            return
        ok_n = 0
        err_n = 0
        lines = []
        for user in queryset:
            try:
                result = reset_counselor_course_data_for_user(
                    user, mode=mode, actor=request.user
                )
                if result.get('ok'):
                    ok_n += 1
                    c = result.get('counts') or {}
                    extra = ''
                    if mode == 'soft' and result.get('backup_id'):
                        extra = f" backup#{result.get('backup_id')}"
                    lines.append(
                        f'{user.email or user.pk}: removed video={c.get("video_progress", 0)} '
                        f'notes={c.get("notes", 0)} quiz={c.get("quiz_results", 0)} '
                        f'cert={c.get("certifications", 0)}{extra}'
                    )
                else:
                    err_n += 1
                    lines.append(f'{user.email or user.pk}: {result.get("message", "Failed")}')
            except Exception as ex:
                err_n += 1
                lines.append(f'{user.email or user.pk}: {ex}')
        label = 'Soft reset (backup + clear)' if mode == 'soft' else 'Hard reset (no backup)'
        if ok_n:
            self.message_user(
                request,
                f'{label}: counselor course reset for {ok_n} user(s). Payment records were not removed. '
                + (
                    ' | '.join(lines[:20])
                    if len(lines) <= 20
                    else ' | '.join(lines[:20]) + ' …'
                ),
                messages.SUCCESS if not err_n else messages.WARNING,
            )
        elif err_n:
            self.message_user(request, ' | '.join(lines), messages.ERROR)

    @action(
        description='Soft reset counselor course (backup snapshot, then clear; keeps payment)',
        permissions=['change'],
    )
    def reset_counselor_course_soft(self, request, queryset):
        self._reset_counselor_course_for_users(request, queryset, 'soft')

    @action(
        description='Hard reset counselor course (delete attempt data, no backup; keeps payment)',
        permissions=['change'],
    )
    def reset_counselor_course_hard(self, request, queryset):
        self._reset_counselor_course_for_users(request, queryset, 'hard')

    def save_model(self, request, obj, form, change):
        # Override this to set the password to the value in the field if it's
        # changed.
        if obj.pk:
            orig_obj = User.objects.get(pk=obj.pk)
            if obj.password != orig_obj.password:
                obj.set_password(obj.password)
        else:
            obj.set_password(obj.password)
        obj.save()
    
    def hard_delete_selected(self, request, queryset):
        """
        Admin action to permanently delete selected users and all their related data.
        This performs a hard delete (not soft delete) and removes all associated records.
        """
        deleted_count = 0
        errors = []
        
        for user in queryset:
            try:
                user_id = user.id
                user_name = user.name
                user_email = user.email
                
                # Use complete() to access all records including soft-deleted ones
                from app.models import TestCompletion, Results
                from institute.models import StudentManagement
                from careers.models import CareerShortlist
                from psychometric_tests.models import PsychometricTestPayment, CentralTestCandidate
                from payments.models import Payment
                
                # Delete TestCompletion (not a BaseModel, so regular delete)
                TestCompletion.objects.filter(user=user).delete()
                
                # Delete Results (not a BaseModel, so regular delete)
                Results.objects.filter(user=user).delete()
                
                # Delete UserProfile (CASCADE will handle related data)
                if hasattr(user, 'user_profile'):
                    try:
                        user.user_profile.delete(hard_delete=True)
                    except:
                        pass
                
                # Delete UserNotes (BaseModel - need to hard delete each instance)
                for note in UserNote.objects.complete().filter(user=user):
                    note.delete(hard_delete=True)
                
                # Delete UserResume rows and related sections
                for ur in UserResume.objects.complete().filter(user=user):
                    try:
                        ur.delete(hard_delete=True)
                    except Exception:
                        pass
                
                # Delete UserFolders (BaseModel - need to hard delete each instance)
                for folder in UserFolder.objects.complete().filter(user=user):
                    folder.delete(hard_delete=True)
                
                # Delete UserCalender (BaseModel - need to hard delete each instance)
                for cal in UserCalender.objects.complete().filter(user=user):
                    cal.delete(hard_delete=True)
                
                # Delete UserSearchHistory (BaseModel - need to hard delete each instance)
                try:
                    for search in UserSearchHistory.objects.complete().filter(user=user):
                        search.delete(hard_delete=True)
                except:
                    pass
                
                # Delete StudentManagement (BaseModel - need to hard delete each instance)
                for sm in StudentManagement.objects.complete().filter(student=user):
                    sm.delete(hard_delete=True)
                
                # Delete CareerShortlist (BaseModel - need to hard delete each instance)
                try:
                    for cs in CareerShortlist.objects.complete().filter(user=user):
                        cs.delete(hard_delete=True)
                except:
                    pass
                
                # Delete PsychometricTestPayment (BaseModel - need to hard delete each instance)
                try:
                    for ptp in PsychometricTestPayment.objects.complete().filter(user=user):
                        ptp.delete(hard_delete=True)
                except:
                    pass
                
                # Delete CentralTestCandidate (BaseModel - need to hard delete)
                try:
                    if hasattr(user, 'central_test_candidate'):
                        user.central_test_candidate.delete(hard_delete=True)
                except:
                    pass
                
                # Delete Payment (BaseModel - need to hard delete each instance)
                try:
                    for payment in Payment.objects.complete().filter(user=user):
                        payment.delete(hard_delete=True)
                except:
                    pass
                
                # Delete user media files
                if user.image:
                    try:
                        if os.path.exists(user.image.path):
                            os.remove(user.image.path)
                    except:
                        pass
                
                # Delete graph images for this user
                try:
                    sanitized_name = str(user_name).replace(' ', '_')
                    graph_pattern = os.path.join(settings.MEDIA_ROOT, 'graph_images', f'{sanitized_name}-{user_id}_*.png')
                    graph_files = glob.glob(graph_pattern)
                    for graph_file in graph_files:
                        try:
                            os.remove(graph_file)
                        except:
                            pass
                except:
                    pass
                
                # Delete user PDFs
                try:
                    user_pdf_dir = os.path.join(settings.MEDIA_ROOT, 'users_pdfs', str(user_id))
                    if os.path.exists(user_pdf_dir):
                        pdf_files = glob.glob(os.path.join(user_pdf_dir, '*'))
                        for pdf_file in pdf_files:
                            try:
                                if os.path.isfile(pdf_file):
                                    os.remove(pdf_file)
                            except:
                                pass
                        # Try to remove directory if empty
                        try:
                            os.rmdir(user_pdf_dir)
                        except:
                            pass
                except:
                    pass
                
                # Finally hard delete the user
                user.delete(hard_delete=True)
                deleted_count += 1
                
            except Exception as e:
                errors.append(f"Error deleting {user.email}: {str(e)}")
        
        if deleted_count > 0:
            self.message_user(
                request,
                f'Successfully permanently deleted {deleted_count} user(s) and all associated data.',
                messages.SUCCESS
            )
        
        if errors:
            for error in errors:
                self.message_user(request, error, messages.ERROR)
    
    hard_delete_selected.short_description = "Permanently delete selected users (hard delete with all related data)"

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['id','user','birthdate','schoolname','gender']
    readonly_fields=['created','modified']

class UserCalenderAdmin(admin.ModelAdmin):
    fields=['user','event_name','start_date','end_date']
    list_display=['id','event_name','start_date','end_date']
    
admin.site.register(User,UserAdmin)

admin.site.register(UserProfile,UserProfileAdmin)
admin.site.register(UserCalender,UserCalenderAdmin)


@admin.register(ResumeV2AISettings)
class ResumeV2AISettingsAdmin(admin.ModelAdmin):
    """Singleton: OpenAI model + prompt for Resume Builder V2 “Generate with AI”."""

    list_display = ("openai_model", "updated_at")
    fields = ("openai_model", "generate_resume_prompt", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not ResumeV2AISettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        ResumeV2AISettings.load()
        return super().changelist_view(request, extra_context=extra_context)


class _EducationLoanHubAdminMixin:
    """Use Education Loan hub breadcrumbs instead of Users › …"""

    change_list_template = "admin/hub/loan_model_change_list.html"
    change_form_template = "admin/hub/loan_model_change_form.html"

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        from django.urls import reverse

        extra_context = extra_context or {}
        here = extra_context.get("sidebar_you_are_here")
        if not here:
            # each_context already injects this on request templates; also set for submit_row
            try:
                from core.admin_hub import resolve_you_are_here

                here = resolve_you_are_here(request)
            except Exception:
                here = None
        extra_context["loan_hub_cancel_url"] = (
            (here or {}).get("hub_url")
            if isinstance(here, dict)
            else None
        ) or reverse("admin:hub_education_loan")
        return super().changeform_view(
            request, object_id, form_url, extra_context=extra_context
        )


class _EducationLoanSingletonAdminMixin(_EducationLoanHubAdminMixin):
    """Singleton settings: opening the list jumps straight to the edit form."""

    def changelist_view(self, request, extra_context=None):
        from django.shortcuts import redirect

        obj = self.model.load()
        return redirect(
            f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change",
            obj.pk,
        )


@admin.register(EducationLoanCRMSettings)
class EducationLoanCRMSettingsAdmin(_EducationLoanSingletonAdminMixin, admin.ModelAdmin):
    """Singleton: Bank API URL, method, and parameter template with {{variables}}."""

    change_form_template = "admin/users/educationloancrmsettings/change_form.html"
    list_display = ("is_enabled", "http_method", "api_url", "updated_at")
    fieldsets = (
        (
            "Bank API connection",
            {
                "fields": (
                    "is_enabled",
                    "api_url",
                    "http_method",
                    "parameters_template",
                    "timeout_seconds",
                ),
                "description": (
                    "Configure the bank endpoint. Use {{variable}} placeholders in the URL "
                    "and in Parameters JSON. Click variables below the form to insert them. "
                    "GET sends parameters as query string; POST/PUT/PATCH as JSON body."
                ),
            },
        ),
        (
            "Authentication",
            {"fields": ("auth_header_name", "auth_header_value")},
        ),
        ("Meta", {"fields": ("updated_at",)}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not EducationLoanCRMSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def get_form(self, request, obj=None, change=False, **kwargs):
        from users.education_loan_crm import validate_parameters_template

        form = super().get_form(request, obj, change=change, **kwargs)

        class BankApiSettingsForm(form):
            def clean_parameters_template(self):
                raw = self.cleaned_data.get("parameters_template") or ""
                ok, err = validate_parameters_template(raw)
                if not ok:
                    from django.core.exceptions import ValidationError

                    raise ValidationError(err)
                return raw

        return BankApiSettingsForm

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        from users.education_loan_crm import BANK_API_VARIABLES

        extra_context = extra_context or {}
        extra_context["bank_api_variables"] = BANK_API_VARIABLES
        return super().changeform_view(request, object_id, form_url, extra_context=extra_context)

    def save_model(self, request, obj, form, change):
        if not (obj.parameters_template or "").strip():
            obj.parameters_template = EducationLoanCRMSettings.DEFAULT_PARAMETERS_TEMPLATE
        super().save_model(request, obj, form, change)


@admin.register(EducationLoanOpsSettings)
class EducationLoanOpsSettingsAdmin(_EducationLoanSingletonAdminMixin, admin.ModelAdmin):
    change_form_template = "admin/users/educationloanopssettings/change_form.html"
    list_display = (
        "pwa_enabled",
        "daily_report_enabled",
        "notify_on_enquiry",
        "auto_crm_on_enquiry",
        "reminder_enabled",
        "reminder_unfollowed_after_hours",
        "updated_at",
    )
    fieldsets = (
        (
            "Loan Desk PWA",
            {"fields": ("pwa_enabled", "instant_login_ttl_hours")},
        ),
        (
            "Enquiry notify",
            {"fields": ("notify_on_enquiry",)},
        ),
        (
            "Bank handoff",
            {
                "fields": (
                    "auto_crm_on_enquiry",
                    "bank_email_recipients",
                    "bank_email_subject_template",
                ),
                "description": (
                    "Bank email recipients receive qualified-lead packets from Loan Desk. "
                    "Bank API uses Education Loan CRM settings; leave auto push off so "
                    "managers push only after Qualify."
                ),
            },
        ),
        (
            "Daily report",
            {
                "fields": (
                    "daily_report_enabled",
                    "daily_report_times",
                    "manager_report_emails",
                ),
                "description": (
                    "Enable the daily loan enquiry email, set one or more IST send times "
                    "(HH:MM), and recipient emails. Multiple times create multiple Celery "
                    "Beat schedules. Disable to remove those schedules. Restart Celery Beat "
                    "after saving so workers pick up the new times."
                ),
            },
        ),
        (
            "Follow-up reminders",
            {"fields": ("reminder_enabled", "reminder_unfollowed_after_hours")},
        ),
        ("Meta", {"fields": ("updated_at",)}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not EducationLoanOpsSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        times = obj.parsed_daily_report_times()
        if obj.daily_report_enabled:
            labels = ", ".join(f"{h:02d}:{m:02d}" for h, m in times)
            self.message_user(
                request,
                f"Daily report Celery times set to {labels} IST. Restart Celery Beat to apply.",
                messages.WARNING,
            )
        else:
            self.message_user(
                request,
                "Daily report disabled — Celery daily-report schedules cleared. Restart Celery Beat to apply.",
                messages.WARNING,
            )


class EducationLoanRemarkInline(admin.TabularInline):
    model = EducationLoanRemark
    extra = 0
    readonly_fields = ("author", "body", "created")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(EducationLoanRemark)
class EducationLoanRemarkAdmin(_EducationLoanHubAdminMixin, admin.ModelAdmin):
    list_display = ("id", "application", "author", "short_body", "created")
    list_filter = ("created",)
    search_fields = ("body", "application__id", "application__student_name", "author__email")
    raw_id_fields = ("application", "author")
    readonly_fields = ("created", "modified")
    ordering = ("-created",)

    @admin.display(description="Remark")
    def short_body(self, obj):
        text = (obj.body or "").strip()
        return text[:80] + ("…" if len(text) > 80 else "")


@admin.register(EducationLoanApplication)
class EducationLoanApplicationAdmin(_EducationLoanHubAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "parent",
        "student_name",
        "loan_amount",
        "status_display",
        "lead_follow",
        "callback_preferred_at",
        "bank_email_status_display",
        "crm_sync_status_display",
        "submitted_at",
        "modified",
    )
    list_filter = (
        "status",
        "bank_email_status",
        "crm_sync_status",
        "disqualify_reason",
        "country_preference",
        "created",
        "submitted_at",
    )
    search_fields = (
        "id",
        "student_name",
        "parent_name",
        "email",
        "mobile",
        "institute_name",
        "course_name",
        "parent__email",
        "parent__name",
        "assigned_to__email",
        "assigned_to__name",
    )
    readonly_fields = (
        "created",
        "modified",
        "submitted_at",
        "qualification_decision_at",
        "crm_synced_at",
        "crm_external_id",
        "crm_sync_response",
        "bank_email_sent_at",
        "bank_email_last_error",
        "bank_email_message_id",
    )
    raw_id_fields = ("parent", "student", "assigned_to", "qualification_decided_by")
    ordering = ("-modified", "-id")
    actions = ("retry_crm_sync", "notify_loan_team")
    inlines = (EducationLoanRemarkInline,)

    fieldsets = (
        (
            "Lead",
            {
                "fields": (
                    "parent",
                    "student",
                    "assigned_to",
                    "status",
                    "student_name",
                    "parent_name",
                    "mobile",
                    "email",
                    "institute_name",
                    "course_name",
                    "country_preference",
                    "additional_details",
                )
            },
        ),
        (
            "Qualification",
            {
                "fields": (
                    "qualification_decision_at",
                    "qualification_decided_by",
                    "qualification_note",
                    "disqualify_reason",
                    "disqualify_reason_text",
                )
            },
        ),
        (
            "Callback / follow-up",
            {
                "fields": (
                    "callback_preferred_at",
                    "callback_note",
                    "next_follow_up_at",
                    "last_followed_up_at",
                )
            },
        ),
        (
            "Calculator",
            {
                "fields": (
                    "loan_amount",
                    "interest_rate",
                    "tenure_years",
                    "moratorium_months",
                    "estimated_emi",
                    "total_interest",
                    "total_payable",
                )
            },
        ),
        (
            "Bank email handoff",
            {
                "fields": (
                    "bank_email_status",
                    "bank_email_sent_at",
                    "bank_email_last_error",
                    "bank_email_message_id",
                )
            },
        ),
        (
            "Bank API handoff",
            {
                "fields": (
                    "crm_sync_status",
                    "crm_synced_at",
                    "crm_external_id",
                    "crm_sync_response",
                ),
                "description": "Stored in crm_* columns; shown as Bank API in Loan Desk.",
            },
        ),
        ("Timestamps", {"fields": ("submitted_at", "created", "modified")}),
    )

    def lead_follow(self, obj):
        return obj.lead_follow_username

    lead_follow.short_description = "Lead follow"

    def save_model(self, request, obj, form, change):
        prev_assignee_id = None
        if change and obj.pk:
            prev_assignee_id = (
                type(obj)
                .objects.filter(pk=obj.pk)
                .values_list("assigned_to_id", flat=True)
                .first()
            )
        super().save_model(request, obj, form, change)
        new_id = obj.assigned_to_id
        if new_id and new_id != prev_assignee_id:
            try:
                from loan_desk.tasks import send_loan_assignment_notify

                send_loan_assignment_notify.delay(obj.id, request.user.id)
            except Exception:
                try:
                    from loan_desk.services import notify_lead_assignee

                    notify_lead_assignee(obj, request=request, assigned_by=request.user)
                except Exception:
                    pass

    @admin.action(description="Notify Loan Managers (email + instant login)")
    def notify_loan_team(self, request, queryset):
        from loan_desk.tasks import send_loan_enquiry_notify

        n = 0
        for app in queryset.exclude(status=choices.EducationLoanApplicationStatus.DRAFT):
            send_loan_enquiry_notify.delay(app.id, "enquiry")
            n += 1
        self.message_user(request, f"Queued manager notify for {n} enquiries.")

    @admin.display(description="Status", ordering="status")
    def status_display(self, obj):
        colors = {
            choices.EducationLoanApplicationStatus.DRAFT: "#92400e",
            choices.EducationLoanApplicationStatus.ENQUIRY_SENT: "#065f46",
            choices.EducationLoanApplicationStatus.CALLBACK_SCHEDULED: "#1d4ed8",
            choices.EducationLoanApplicationStatus.IN_PROGRESS: "#7c3aed",
            choices.EducationLoanApplicationStatus.FOLLOW_UP: "#b45309",
            choices.EducationLoanApplicationStatus.CLOSED: "#334155",
            choices.EducationLoanApplicationStatus.QUALIFIED: "#0f766e",
            choices.EducationLoanApplicationStatus.NOT_QUALIFIED: "#9f1239",
        }
        color = colors.get(obj.status, "#334155")
        return format_html(
            '<span style="font-weight:600;color:{};">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description="Bank email", ordering="bank_email_status")
    def bank_email_status_display(self, obj):
        if obj.status == choices.EducationLoanApplicationStatus.DRAFT:
            return "—"
        colors = {
            choices.EducationLoanBankEmailStatus.NONE: "#64748b",
            choices.EducationLoanBankEmailStatus.PENDING: "#92400e",
            choices.EducationLoanBankEmailStatus.SENT: "#15803d",
            choices.EducationLoanBankEmailStatus.ERROR: "#b91c1c",
        }
        color = colors.get(obj.bank_email_status, "#334155")
        return format_html(
            '<span style="font-weight:600;color:{};">{}</span>',
            color,
            obj.get_bank_email_status_display(),
        )

    @admin.display(description="Bank API", ordering="crm_sync_status")
    def crm_sync_status_display(self, obj):
        if obj.status == choices.EducationLoanApplicationStatus.DRAFT:
            return "—"
        colors = {
            choices.EducationLoanCRMSyncStatus.PENDING: "#92400e",
            choices.EducationLoanCRMSyncStatus.SENT: "#1d4ed8",
            choices.EducationLoanCRMSyncStatus.SUCCESS: "#15803d",
            choices.EducationLoanCRMSyncStatus.ERROR: "#b91c1c",
        }
        color = colors.get(obj.crm_sync_status, "#334155")
        return format_html(
            '<span style="font-weight:600;color:{};">{}</span>',
            color,
            obj.get_crm_sync_status_display(),
        )

    @action(description="Retry Bank API push for selected leads", permissions=["change"])
    def retry_crm_sync(self, request, queryset):
        from users.education_loan_crm import sync_education_loan_lead_to_crm

        ok_n = 0
        err_n = 0
        for app in queryset:
            if app.status == choices.EducationLoanApplicationStatus.DRAFT:
                err_n += 1
                continue
            success, _message = sync_education_loan_lead_to_crm(app, force=True)
            if success:
                ok_n += 1
            else:
                err_n += 1
        if ok_n:
            self.message_user(request, f"Bank API push succeeded for {ok_n} lead(s).", messages.SUCCESS)
        if err_n:
            self.message_user(request, f"Bank API push failed or skipped for {err_n} lead(s).", messages.WARNING)

