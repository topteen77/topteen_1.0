from django.contrib import admin
from django.contrib.admin.decorators import action
from .models import (
    User,
    UserProfile,
    UserCalender,
    UserNote,
    UserResume,
    UserFolder,
    UserSearchHistory,
    ResumeStudioHtmlTemplate,
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

# Register your models here.


# Psychometric test keys (TestCompletion flags + Results test_paper)
PSYCHOMETRIC_TEST_KEYS = [
    ('test1', 'test1_complete'), ('test2', 'test2_complete'), ('test3', 'test3_complete'),
    ('numerical', 'numerical_complete'), ('verbal', 'verbal_complete'), ('logical', 'logical_complete'),
    ('emotional', 'emotional_complete'), ('machanical', 'machanical_complete'),
    ('language', 'language_complete'), ('spatial', 'spatial_complete'),
]


def _get_students_with_recent_tests_queryset(email_filter=None):
    """Return User queryset of students only who have given tests, ordered by most recent activity."""
    from core.choices import UserType
    qs = User.objects.filter(user_type=UserType.STUDENT).filter(
        Q(test_sessions__isnull=False) | Q(results__isnull=False)
    ).annotate(
        latest_session=Max('test_sessions__created_at'),
        latest_result=Max('results__modified'),
    ).distinct()
    if email_filter:
        qs = qs.filter(email__icontains=email_filter.strip())
    return qs.order_by('-latest_session', '-latest_result')


def _get_user_test_count(user):
    """Return total test count for a user (psychometric results + post-matric sessions)."""
    from app.models import Results
    from app_post_matric.models import TestSession
    psychometric_count = Results.objects.filter(user=user).count()
    post_matric_count = user.test_sessions.count()
    return psychometric_count + post_matric_count


def _get_tests_for_users(user_ids):
    """Return list of tests that the given users have. Each item: { id, name, type }."""
    from app.models import Results
    from app_post_matric.models import TestSession, Test
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
    # Post-matric: distinct Test from TestSession
    sessions = TestSession.objects.filter(user_id__in=user_ids).select_related('test')
    for s in sessions:
        if s.test_id and ('post_matric_' + str(s.test_id)) not in test_ids_seen:
            test_ids_seen.add('post_matric_' + str(s.test_id))
            out.append({'id': 'post_matric_' + str(s.test_id), 'name': 'Post-matric: ' + (s.test.title if s.test else str(s.test_id)), 'type': 'post_matric'})
    return out


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
        if tid.startswith('psychometric_'):
            paper = tid.replace('psychometric_', '')
            Results.objects.filter(user=user, test_paper=paper).delete()
        elif tid.startswith('post_matric_'):
            try:
                pk = int(tid.replace('post_matric_', ''))
                TestSession.objects.filter(user=user, test_id=pk).delete()
            except ValueError:
                pass


class PaymentInline(admin.TabularInline):
    extra = 0
    max_num = 0
    can_delete = False
    readonly_fields = (
        'payment_id', 'amount_display', 'gateway_display', 'obj_type_display',
        'is_success_display', 'gateway_order_id', 'created',
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
    ]
    readonly_fields = ['is_system_demo', 'admin_password_reset']
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