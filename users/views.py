from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from re import template
from django.contrib.auth import authenticate, login,logout as auth_logout
from django.contrib.auth import login
from django.views.generic import TemplateView,View
from django.http import Http404, HttpResponse, HttpResponseRedirect,JsonResponse
from django.shortcuts import render, redirect
from communication.models import OTP
from counselor.models import Counselor, primary_counselor_for_user
from .backends import CustomUserBackend
from .models import (
    User,
    UserResume,
    UserResumeCertificate,
    UserResumeInternship,
    UserResumeActivity,
    UserResumeSkill,
    UserResumeVolunteerInvolvement,
    ResumeStudioHtmlTemplate,
)
from communication.com_service import ComService
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.core.signing import Signer
from core import choices
from django.template.loader import render_to_string
from django.db.models import Q
from core.breadcrumbs import get_breadcrumb
from core.utils import build_html_head, expand_eq_band_percentile
from rest_framework import permissions,authentication
from django.db.models import Q
from django.core.signing import Signer
from django.urls import reverse,reverse_lazy
from communication import models
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from users.decorators import institute_dashboard_roles_only
from users.session_utils import login_user_with_session
from django.views.decorators.csrf import ensure_csrf_cookie
from careers.models import Videos,Career,CareerTags
from core.models import EntranceTestPrepExam
from colleges.models import College,CollegeShortlist
from courses.models import Course
from core.models import Country,Subject,Hobbies,UserFigureOut,Stories
from blog.models import Blog
from .models import UserProfile,UserNote,UserFolder,UserCalender
from psychometric_tests.models import CentralTestCandidate
from .task import send_otp_mail,send_referral_mail
from careers.models import CareerCluster,CareerShortlist,Videos
from skilllab.models import SkillLabCourse, SkilllabCoursePayment
from entrance_exams.document_filters import EntranceExamDocumentFilter
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from io import BytesIO
import logging

logger = logging.getLogger(__name__)
from django.http import HttpResponse
from django.template.loader import get_template
from django.core.files import File
from django.conf import settings
from institute.models import (
    Institute,
    InstituteGroup,
    InstituteMarketingGroup,
    StudentManagement,
    get_global_remain_credits,
    resolve_marketing_group_for_public_registration,
)
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
# from .forms import InstituteRegistrationForm
import json
import re
from django.utils.safestring import mark_safe
from user_analytics.tasks import link_analytics_session_to_user, reconcile_recent_user_events
from .pdf_utils import default_resume_pdf_options, html_to_pdf_bytes
from .resume_guided_ai import strip_markdown_fences
from .parent_dashboard_ai import (
    process_psychometric_data,
    generate_ai_insights,
    build_study_abroad_options,
    calculate_loan_metrics,
)
from .resume_payload import (
    STUDIO_PROTO_V1_KEY,
    apply_studio_resume_to_userresume_children,
    ensure_studio_proto_v1_defaults_saved,
    prepare_admitcv_wizard_restore,
    resume_editor_payload as _resume_editor_payload,
    resume_studio_embed_finish_pdf_urls,
    resume_studio_prototype_payload,
    studio_prefs_from_resume_record,
    studio_v1_pack_to_generated_html,
    wizard_prefers_generated_pdf,
)
from .resume_studio_html import (
    admin_studio_html_preview_initial_json,
    studio_html_template_catalog_json,
)
from .resume_studio_pdf_html import (
    studio_pack_root_css_block,
    studio_pdf_template_context,
    studio_proto_pack_from_resume,
    studio_proto_pack_to_mount_html,
    studio_render_html_for_resume,
)


def _link_current_analytics_session(request, user):
    """Attach pre-login anonymous analytics rows to the newly created/logged-in user."""
    try:
        session_id = request.session.get('analytics_session_id')
        if session_id and user:
            link_analytics_session_to_user(session_id, user)
            # Backfill session_id on any events created during AJAX auth flow.
            reconcile_recent_user_events(user, session_id=session_id, minutes=30)
            # Registration can be tracked before link completes; refresh source/session on recent rows.
            try:
                from datetime import timedelta
                from user_analytics.models import UserActivity, UserEvent

                source_name = None
                recent_activity = (
                    UserActivity.objects.filter(
                        session_id=session_id,
                        enquiry_source__isnull=False,
                    )
                    .select_related('enquiry_source')
                    .order_by('-created')
                    .first()
                )
                if recent_activity and getattr(recent_activity, 'enquiry_source', None):
                    source_name = recent_activity.enquiry_source.name

                reg_events = UserEvent.objects.filter(
                    user=user,
                    event_type='registration',
                    created__gte=timezone.now() - timedelta(minutes=30),
                ).order_by('-created')[:5]

                for ev in reg_events:
                    changed = False
                    if not ev.session_id:
                        ev.session_id = session_id
                        changed = True
                    if source_name:
                        meta = dict(ev.metadata or {})
                        old = str(meta.get('source') or '').strip()
                        # Align with Enquiry Sources stats: _enquiry_source_attribution_q uses
                        # metadata__source=source.name (exact). Always set the named source when we
                        # know it from ?ref= activity, not only placeholder values.
                        if old != source_name:
                            meta['source'] = source_name
                            ev.metadata = meta
                            changed = True
                    if changed:
                        ev.save(update_fields=['session_id', 'metadata'])
            except Exception:
                pass
    except Exception:
        pass


def is_safe_post_login_redirect_path(path):
    """
    Paths safe to open in the browser after HTML login/signup.
    Blocks XHR/JSON endpoints (e.g. notification poll) that @login_required
    sends to LOGIN_URL with ?next=..., which would otherwise strand users on raw JSON.
    """
    if not path or not isinstance(path, str):
        return False
    p = path.strip()
    if not p.startswith('/') or p.startswith('//'):
        return False
    base = (p.split('?')[0] or '').lower()
    if '/notifications/api/' in base:
        return False
    if base.startswith('/api/v1/'):
        return False
    if base.startswith('/api-auth/'):
        return False
    return True


# def create_institute(request):
#     if request.method == 'POST':      
        
#         # Get form data
#         ins_email = request.POST.get("institute_email")
#         username = request.POST.get("user_name")
#         name = request.POST.get("institute_name")
#         address = request.POST.get("institute_address")
#         contact = request.POST.get("institute_contact")
#         admin_contact = request.POST.get("institute_admin")
#         credit_counts = request.POST.get("ins_credits", 0)
#         institute_group_id = request.POST.get("institute_group")
#         markiting_group_id = request.POST.get("marketing_group")
#         institute_type = request.POST.get("institute_type")
#         logo = request.FILES.get("institute_logo")

#         # Convert institute_type to int
#         institute_type = int(institute_type)

#         # Email validation
#         import re
#         evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
#         ins_em = re.match(evalid, ins_email)

#         # Validate inputs
#         if (ins_em and name and address and contact and admin_contact and 
#             (credit_counts is None or (0 <= int(credit_counts) <= get_global_remain_credits()))):
            
#             try:
#                 # Check if email already exists
#                 if User.objects.filter(email=ins_email).exists():
#                     messages.error(request, f"{ins_email} Already Exists!")
#                     return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

#                 # Get institute group if provided
#                 ins_group = None
#                 mrk_group = None
#                 if institute_group_id:
#                     try:
#                         ins_group = get_object_or_404(InstituteGroup, id=institute_group_id)
#                     except:
#                         pass

#                 if markiting_group_id:
#                     try:
#                         mrk_group = get_object_or_404(InstituteMarketingGroup, id=markiting_group_id)
#                     except:
#                         pass

#                 # Generate random password
#                 password = "12345"

#                 # Create user
#                 user_dict = {
#                     'email': ins_email,
#                     'password': password,
#                     'name': username,
#                     'user_type': choices.UserType.INSTITUTE
#                 }
#                 ins_user = User.create_user(**user_dict)

#                 # Create institute
#                 ins = Institute(
#                     name=name,
#                     created_by=ins_user,
#                     logo=logo,
#                     address=address,
#                     contact_info=contact,
#                     administrator_contact=admin_contact,
#                     credit_counts=int(credit_counts) if credit_counts else 0,
#                     institute_group=ins_group,
#                     marketing_group=mrk_group,
#                     institute_type=institute_type,
#                     institute_status=choices.InstituteStatus.PENDING
#                 )
#                 ins.save()

#                 # Email sending with error handling
#                 try:
#                     # Define your list of emails
                    
#                     email_list = ["support4.it@canamgroup.com", "am.srp@canamgroup.com", 'support2.it@canamgroup.com']  # Add your emails here
                    
#                     institute_types = dict((num, name) for num, name in choices.InstituteType.CHOICES)
#                     institute_type_name = institute_types.get(int(institute_type), "Unknown")

#                     from communication.com_service import ComService
#                     cs = ComService()

#                     cs.send_institute_create_homepage_mail(
#                         email=ins_email,
#                         password=password,
#                         Ins_name=name,  # Institute name
#                         principal_name=username,  # Principal/admin name
#                         contact_number=contact,  # Contact info
#                         Address=address,  # Institute address
#                         institute_type=institute_type_name
#                     )
                    
#                     # Send to multiple emails
#                     results = cs.send_institute_create_homepage_mail_bulk(
#                         user_email=ins_email,
#                         emails=email_list,
#                         password=password,
#                         Ins_name=name,
#                         principal_name=username,
#                         contact_number=contact,
#                         Address=address,
#                         institute_type=institute_type_name
#                     )
                    
#                     # Check results
#                     for result in results:
#                         if result["status"] == "success":
#                             print(f"Email sent successfully to {result['email']}")
#                         else:
#                             print(f"Failed to send email to {result['email']}: {result['error']}")
                            
#                 except Exception as e:
#                     print("Error sending emails:", e)
#                     # Log the error properly
#                     pass

#                 return JsonResponse({
#                     'status': 'success',
#                     'message': "Thank you! Your request for claiming this college has been sent to the admin for approval. You will receive a mail with your login credentials after approval."
#                 })

#             except Exception as e:
#                 return JsonResponse({
#                     'status': 'error',
#                     'message': f"Failed to create institute: {str(e)}"
#                 })

#         else:
#             error_message = "Please fill all required fields"
#             if not ins_em:
#                 error_message = "Invalid email format"
#             elif credit_counts and not (0 <= int(credit_counts) <= get_global_remain_credits()):
#                 error_message = f"Credit count must be between 0 and {get_global_remain_credits()}"
            
#             return JsonResponse({
#                 'status': 'error',
#                 'message': error_message
#             })

#     csrf_token = get_token(request)
#     return render(request, 'topteenfrontend/add-instiutute.html', {
#         'remaining_credits': get_global_remain_credits(),
#         'institute_groups': InstituteGroup.objects.all(),
#         "marketing_groups": InstituteMarketingGroup.objects.all(),
#         'institute_types': choices.InstituteType.CHOICES,
#         'csrf_token': csrf_token
#     })

def create_institute(request):
    if request.method == 'POST':      
        
        # Get form data
        ins_email = request.POST.get("institute_email")
        username = request.POST.get("user_name")
        name = request.POST.get("institute_name")
        address = request.POST.get("institute_address")
        contact = request.POST.get("institute_contact")
        admin_contact = request.POST.get("institute_admin")
        credit_counts = request.POST.get("ins_credits", 0)
        institute_group_id = request.POST.get("institute_group")
        markiting_group_id = request.POST.get("marketing_group")
        institute_type = request.POST.get("institute_type")
        logo = request.FILES.get("institute_logo")

        # Convert institute_type to int
        institute_type = int(institute_type)

        # Email validation
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        ins_em = re.match(evalid, ins_email)

        # Validate inputs
        if (ins_em and name and address and contact and admin_contact and 
            (credit_counts is None or (0 <= int(credit_counts) <= get_global_remain_credits()))):
            
            try:
                # Check if email already exists
                if User.objects.filter(email=ins_email).exists():
                    messages.error(request, f"{ins_email} Already Exists!")
                    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

                # Get institute group if provided
                ins_group = None
                mrk_group = None
                if institute_group_id:
                    try:
                        ins_group = get_object_or_404(InstituteGroup, id=institute_group_id)
                    except:
                        pass

                if markiting_group_id:
                    try:
                        mrk_group = get_object_or_404(InstituteMarketingGroup, id=markiting_group_id)
                    except:
                        pass

                mrk_group = resolve_marketing_group_for_public_registration(mrk_group)

                # Generate random password (use default from settings)
                password = settings.DEFAULT_PASSWORD

                # Create user
                user_dict = {
                    'email': ins_email,
                    'password': password,
                    'name': username,
                    'user_type': choices.UserType.INSTITUTE
                }
                ins_user = User.create_user(**user_dict)

                # Create institute
                ins = Institute(
                    name=name,
                    created_by=ins_user,
                    logo=logo,
                    address=address,
                    contact_info=contact,
                    administrator_contact=admin_contact,
                    credit_counts=int(credit_counts) if credit_counts else 0,
                    institute_group=ins_group,
                    marketing_group=mrk_group,
                    institute_type=institute_type,
                    institute_status=choices.InstituteStatus.PENDING
                )
                ins.save()

                # Email sending with proper error handling
                try:
                    # Define your list of emails
                    email_list = ["support4.it@canamgroup.com", "am.srp@canamgroup.com", 'support2.it@canamgroup.com']
                    
                    institute_types = dict((num, name) for num, name in choices.InstituteType.CHOICES)
                    institute_type_name = institute_types.get(int(institute_type), "Unknown")

                    from communication.com_service import ComService
                    cs = ComService()
                    try:
                        result = cs.send_institute_create_homepage_mail(
                            email=ins_email,
                            password=password,
                            Ins_name=name,
                            principal_name=username,
                            contact_number=contact,
                            Address=address,
                            institute_type=institute_type_name
                        )
                        print(f"Email sent successfully to institute: {result}")
                    except Exception as e:
                        print(f"Error sending email to institute: {str(e)}")
                    
                    # Send bulk emails to team members
                    try:
                        results = cs.send_institute_create_homepage_mail_bulk(
                            user_email=ins_email,
                            emails=email_list,
                            password=password,
                            Ins_name=name,
                            principal_name=username,
                            contact_number=contact,
                            Address=address,
                            institute_type=institute_type_name
                        )
                        
                        # Log results properly
                        for result in results:
                            if result["status"] == "success":
                                print(f"Email sent successfully to {result['email']}")
                            else:
                                print(f"Failed to send email to {result['email']}: {result.get('error', 'Unknown error')}")
                                
                    except Exception as e:
                        print(f"Error sending bulk emails: {str(e)}")
                        
                except Exception as e:
                    print(f"Error in email sending process: {str(e)}")

                return JsonResponse({
                    'status': 'success',
                    'message': "Thank you! Your request for claiming this college has been sent to the admin for approval. You will receive a mail with your login credentials after approval."
                })

            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': f"Failed to create institute: {str(e)}"
                })

        else:
            error_message = "Please fill all required fields"
            if not ins_em:
                error_message = "Invalid email format"
            elif credit_counts and not (0 <= int(credit_counts) <= get_global_remain_credits()):
                error_message = f"Credit count must be between 0 and {get_global_remain_credits()}"
            
            return JsonResponse({
                'status': 'error',
                'message': error_message
            })

    csrf_token = get_token(request)
    return render(request, 'topteenfrontend/add-instiutute.html', {
        'remaining_credits': get_global_remain_credits(),
        'institute_groups': InstituteGroup.objects.all(),
        "marketing_groups": InstituteMarketingGroup.objects.all(),
        'institute_types': choices.InstituteType.CHOICES,
        'csrf_token': csrf_token
    })



class LoginView(TemplateView):
    template_name='template20/sign_in.html'

    def __breadcrumb(self):
        l=[]
        return get_breadcrumb(l)

    def __html_head(self):
        name='Login Signup'
        return build_html_head(title=name, description=name)

    def get_context(self,request,enc_id=None,*args,**kwargs):
        ctx={}
        ctx['html_head']=self.__html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        # If user is already authenticated and still hits a login URL, the UI should
        # prompt for logout instead of showing the login form.
        ctx["already_logged_in"] = bool(getattr(request, "user", None) and request.user.is_authenticated)
        try:
            ctx["logout_url"] = reverse("users:logout")
        except Exception:
            ctx["logout_url"] = "/user/logout/"
        try:
            ctx["dashboard_url"] = reverse("users:userdashboard")
        except Exception:
            ctx["dashboard_url"] = "/user/dashboard/"
        try:
            u = getattr(request, "user", None)
            ctx["logged_in_as"] = (getattr(u, "name", None) or getattr(u, "email", None) or "").strip()
        except Exception:
            ctx["logged_in_as"] = ""
        if enc_id:
            ctx['enc_referral_user']=enc_id
        else:
            ctx['enc_referral_user']=False
        # Preserve ?next= for redirect after login (e.g. back to psychometric payment page)
        next_url = (request.GET.get('next') or '').strip()
        if next_url:
            from django.utils.http import url_has_allowed_host_and_scheme
            full_url = request.build_absolute_uri(next_url)
            if not url_has_allowed_host_and_scheme(full_url, request.get_host()):
                next_url = ''
            elif not is_safe_post_login_redirect_path(next_url):
                next_url = ''
            else:
                # Store in session as fallback if client doesn't send next in login POST
                request.session['login_next_url'] = next_url
        ctx['next_url'] = next_url
        # When login is shown in an iframe (e.g. career swipe), show context-specific copy
        if request.GET.get('embed') == '1':
            if 'career_swipe' in (next_url or ''):
                ctx['login_embed_heading'] = 'Sign in to save your careers'
                ctx['login_embed_subtitle'] = 'Enter your email or mobile below. After you sign in, this window will close and your choices will be saved.'
            else:
                ctx['login_embed_heading'] = 'Sign in'
                ctx['login_embed_subtitle'] = 'Enter your details below to continue.'
        else:
            ctx['login_embed_heading'] = None
            ctx['login_embed_subtitle'] = None
        # Demo accounts for all roles; pass URL and CSRF so template works with Jinja2 and Django
        from .demo_accounts import get_demo_login_context
        ctx.update(get_demo_login_context(request))
        ctx['show_demo_credentials'] = False
        ctx['demo_credentials'] = []
        return ctx

    def get(self, request, *args, **kwargs):
        # After AJAX login the browser may still hit the login URL once; send user to dashboard
        # instead of showing the "logout first?" prompt (which caused accidental logouts).
        if (
            getattr(request, "user", None)
            and request.user.is_authenticated
            and request.session.pop("fresh_login", False)
        ):
            return redirect(get_dashboard_url_for_user(request, request.user))
        ctx = self.get_context(request, *args, **kwargs)
        return render(request, self.template_name, ctx)


class DemoLoginView(View):
    """
    POST-only view: log in as a demo user by token (signed user id).
    Only users with is_demo_account=True and is_active=True can be used.
    Credentials are never sent to the client.
    """
    def _login_fallback_url(self, request):
        """Redirect to institute/counselor login if request came from there."""
        referer = (request.META.get('HTTP_REFERER') or '').strip()
        if '/institute/auth/login' in referer:
            return redirect('institute:login')
        if '/counselor/auth/login' in referer:
            return redirect('counselor:login')
        return redirect('users:login')

    def post(self, request):
        token = (request.POST.get('token') or '').strip()
        if not token:
            messages.error(request, 'Invalid demo login request.')
            return self._login_fallback_url(request)
        try:
            sign = Signer()
            obj = sign.unsign_object(token)
            user_id = obj.get('demo_user_id')
        except Exception:
            messages.error(request, 'Invalid demo login link.')
            return self._login_fallback_url(request)
        user = User.objects.filter(pk=user_id).first()
        if not user or not user.is_active:
            messages.error(request, 'This demo account is not available.')
            return self._login_fallback_url(request)
        # Allow: is_demo_account (user demo) OR created_by of a demo institute
        from institute.models import Institute
        is_demo_user = user.is_demo_account
        is_demo_institute_user = Institute.objects.filter(
            created_by=user, is_demo_institute=True
        ).exists()
        if not (is_demo_user or is_demo_institute_user):
            messages.error(request, 'This demo account is not available.')
            return self._login_fallback_url(request)
        if not user.get_user_status():
            messages.error(request, 'Account is blocked or inactive.')
            return self._login_fallback_url(request)
        login_user_with_session(request, user, demo=True)
        redirect_url = self._redirect_url(request, user)
        return redirect(redirect_url)

    def _redirect_url(self, request, user):
        return get_dashboard_url_for_user(request, user)


@method_decorator(ensure_csrf_cookie, name='dispatch')
class StudentLoginView(LoginView):
    """
    Student login landing page (/student/login/).
    OTP-first by default via template context.
    Demo accounts: only Student role.
    """
    template_name = "template20/student_login.html"

    def get_context(self, request, enc_id=None, *args, **kwargs):
        ctx = super().get_context(request, enc_id, *args, **kwargs)
        # Demo accounts toggle (controlled by existing Core Configuration keys)
        try:
            from core.models import Configuration
            from django.conf import settings
            env = str(getattr(settings, "ENVIRONMENT", "") or "").strip().lower()
            is_production = (env == "production") if env else (not bool(getattr(settings, "DEBUG", False)))
            key = "SHOW_DEMO_ACCOUNT_ON_PRODUCTION" if is_production else "SHOW_DEMO_ACCOUNT_ON_DEVELOPMENT"
            show_demo = str(Configuration.get(key, default="false", editable=True)).lower() in ("true", "1", "yes", "on")
        except Exception:
            show_demo = False

        if show_demo:
            from .demo_accounts import get_demo_login_context
            ctx.update(get_demo_login_context(request, user_types=[choices.UserType.STUDENT]))
        else:
            ctx["demo_accounts"] = []
            ctx["demo_login_url"] = ""
            ctx["demo_csrf_token"] = ""
        return ctx

    def get(self, request, *args, **kwargs):
        if (
            getattr(request, "user", None)
            and request.user.is_authenticated
            and request.session.pop("fresh_login", False)
        ):
            return redirect(get_dashboard_url_for_user(request, request.user))
        ctx = self.get_context(request, *args, **kwargs)
        ctx['login_mode'] = 'student'
        return render(request, self.template_name, ctx)


class StudentSignupView(LoginView):
    """
    Student signup page (/student/signup/).
    Dedicated flow for new accounts: OTP verify -> set password.
    """
    template_name = "template20/student_signup.html"

    def get(self, request, *args, **kwargs):
        ctx = self.get_context(request, *args, **kwargs)
        ctx['login_mode'] = 'student'
        return render(request, self.template_name, ctx)


class ParentsLoginView(LoginView):
    """
    Parents login landing page (/parents/login/).
    Mobile + OTP only.
    Demo accounts: only Parent role.
    """

    def get_context(self, request, enc_id=None, *args, **kwargs):
        ctx = super().get_context(request, enc_id, *args, **kwargs)
        # Demo accounts toggle (controlled by existing Core Configuration keys)
        try:
            from core.models import Configuration
            from django.conf import settings
            env = str(getattr(settings, "ENVIRONMENT", "") or "").strip().lower()
            is_production = (env == "production") if env else (not bool(getattr(settings, "DEBUG", False)))
            key = "SHOW_DEMO_ACCOUNT_ON_PRODUCTION" if is_production else "SHOW_DEMO_ACCOUNT_ON_DEVELOPMENT"
            show_demo = str(Configuration.get(key, default="false", editable=True)).lower() in ("true", "1", "yes", "on")
        except Exception:
            show_demo = False

        if show_demo:
            from .demo_accounts import get_demo_login_context
            ctx.update(get_demo_login_context(request, user_types=[choices.UserType.PARENT]))
        else:
            ctx["demo_accounts"] = []
            ctx["demo_login_url"] = ""
            ctx["demo_csrf_token"] = ""
        return ctx

    def get(self, request, *args, **kwargs):
        ctx = self.get_context(request, *args, **kwargs)
        ctx['login_mode'] = 'parent'
        return render(request, self.template_name, ctx)


class ParentsDashboardView(TemplateView):
    template_name = 'template20/parents/dashboard.html'

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('parents_login')
        if request.user.user_type != choices.UserType.PARENT:
            return redirect(get_dashboard_url_for_user(request, request.user))
        from users.models import ParentStudentLink
        linked = ParentStudentLink.objects.filter(parent=request.user).select_related('student')
        students = [x.student for x in linked if x.student]

        # Build result status for each linked student (psychometric report availability)
        students_info = []
        psychometric_students = []
        psychometric_summary = {
            "total_students": len(students),
            "tested_students": 0,
            "pending_students": 0,
            "completion_percent": 0,
            "class10": {"label": "Class 10", "total": 0, "completed": 0, "pending": 0, "percent": 0},
            "class12": {"label": "Class 12", "total": 0, "completed": 0, "pending": 0, "percent": 0},
            "other": {"label": "Other Classes", "total": 0, "completed": 0, "pending": 0, "percent": 0},
        }

        def _resolve_grade_bucket(student_user):
            grade_raw = ""
            try:
                if getattr(student_user, "user_profile", None) and getattr(student_user.user_profile, "grade", None):
                    grade_raw = str(student_user.user_profile.grade).strip()
            except Exception:
                grade_raw = ""

            if not grade_raw:
                try:
                    sm = student_user.student_management.last()
                    if sm and getattr(sm, "class_and_section", None):
                        class_section = str(sm.class_and_section).strip()
                        grade_raw = class_section.split()[0] if class_section else ""
                except Exception:
                    grade_raw = ""

            if grade_raw.startswith("10"):
                return "10", "Class 10"
            if grade_raw.startswith("12"):
                return "12", "Class 12"
            return "other", (grade_raw or "Other")

        try:
            from psychometric_tests.models import CentralTestCandidate
            for s in students:
                results_enabled = False
                has_candidate = False
                latest_test = None
                result_url = ""
                try:
                    ctc = CentralTestCandidate.objects.filter(user=s).first()
                    if ctc:
                        has_candidate = True
                        test = ctc.candidate_test.last()
                        latest_test = test
                        if test and getattr(test, "is_success", None) == choices.YesNoChoices.YES and hasattr(test, "psychometric_test_results") and test.psychometric_test_results:
                            results_enabled = True
                            try:
                                result_url = test.get_pyschometric_test_result_url() or ""
                            except Exception:
                                result_url = ""
                except Exception:
                    results_enabled = False
                students_info.append({"student": s, "results_enabled": results_enabled})

                bucket_key, bucket_label = _resolve_grade_bucket(s)
                summary_key = "class10" if bucket_key == "10" else ("class12" if bucket_key == "12" else "other")
                psychometric_summary[summary_key]["total"] += 1
                if results_enabled:
                    psychometric_summary[summary_key]["completed"] += 1
                    psychometric_summary["tested_students"] += 1
                else:
                    psychometric_summary[summary_key]["pending"] += 1
                    psychometric_summary["pending_students"] += 1

                psychometric_students.append({
                    "student": s,
                    "grade_label": bucket_label,
                    "results_enabled": results_enabled,
                    "has_candidate": has_candidate,
                    "latest_test": latest_test,
                    "result_url": result_url,
                })
        except Exception:
            students_info = [{"student": s, "results_enabled": False} for s in students]
            psychometric_students = []

        if psychometric_summary["total_students"] > 0:
            psychometric_summary["completion_percent"] = int(
                round((psychometric_summary["tested_students"] / psychometric_summary["total_students"]) * 100)
            )
        for key in ("class10", "class12", "other"):
            total = psychometric_summary[key]["total"]
            completed = psychometric_summary[key]["completed"]
            psychometric_summary[key]["percent"] = int(round((completed / total) * 100)) if total else 0

        # Graph + AI insight payloads for parent home
        line_labels = ["Term 1", "Term 2", "Term 3", "Term 4"]
        class10_series, class12_series = [], []

        def _base_from_student(stu, offset):
            # deterministic pseudo score generator based on student id
            sid = int(getattr(stu, "id", 0) or 0)
            return 45 + ((sid * 13 + offset) % 41)

        for item in psychometric_students:
            stu = item.get("student")
            g = str(item.get("grade_label") or "")
            trend = [
                _base_from_student(stu, 5),
                _base_from_student(stu, 16),
                _base_from_student(stu, 23),
                _base_from_student(stu, 30),
            ]
            if item.get("results_enabled"):
                trend = [min(100, x + 8) for x in trend]
            item["academic_trend"] = trend
            item["subject_scores"] = {
                "math": _base_from_student(stu, 3),
                "science": _base_from_student(stu, 9),
                "english": _base_from_student(stu, 21),
            }
            item["career_readiness"] = int(round((sum(trend[-2:]) / 2 + item["subject_scores"]["science"]) / 2))

            psychometric_payload = {
                "personality": {
                    "openness": _base_from_student(stu, 2),
                    "conscientiousness": _base_from_student(stu, 4),
                    "extraversion": _base_from_student(stu, 6),
                    "agreeableness": _base_from_student(stu, 8),
                    "emotional_stability": _base_from_student(stu, 10),
                },
                "aptitude": {
                    "numerical": item["subject_scores"]["math"],
                    "logical": _base_from_student(stu, 12),
                    "verbal": item["subject_scores"]["english"],
                },
                "interest": {
                    "realistic": _base_from_student(stu, 11),
                    "investigative": _base_from_student(stu, 14),
                    "artistic": _base_from_student(stu, 17),
                    "social": _base_from_student(stu, 20),
                    "enterprising": _base_from_student(stu, 22),
                    "conventional": _base_from_student(stu, 24),
                },
            }
            psychometric_result = process_psychometric_data(
                psychometric_payload,
                benchmarks={"numerical": 60, "logical": 60, "verbal": 60, "investigative": 62},
            )
            item["psychometric_result"] = psychometric_result
            item["ai_insights"] = generate_ai_insights(
                psychometric_result,
                item["subject_scores"],
            )
            item["study_abroad"] = build_study_abroad_options(
                item["ai_insights"].get("career_paths", []),
                item["career_readiness"],
            )

            if g.startswith("Class 10"):
                class10_series.append(trend)
            elif g.startswith("Class 12"):
                class12_series.append(trend)

        def _avg_series(rows):
            if not rows:
                return [0, 0, 0, 0]
            out = []
            for idx in range(4):
                out.append(int(round(sum(r[idx] for r in rows) / len(rows))))
            return out

        line_chart_data = {
            "labels": line_labels,
            "datasets": [
                {"label": "Class 10", "data": _avg_series(class10_series), "borderColor": "#5c54d4", "backgroundColor": "rgba(92,84,212,0.2)", "tension": 0.35},
                {"label": "Class 12", "data": _avg_series(class12_series), "borderColor": "#20b7e8", "backgroundColor": "rgba(32,183,232,0.2)", "tension": 0.35},
            ],
        }

        selected_student = psychometric_students[0] if psychometric_students else None
        radar_chart_data = {"labels": [], "values": []}
        bar_chart_data = {"labels": ["Math", "Science", "English"], "values": [0, 0, 0]}
        ai_alerts = []
        study_abroad_options = []
        if selected_student:
            radar_chart_data = {
                "labels": selected_student["psychometric_result"]["radar"]["labels"][:8],
                "values": selected_student["psychometric_result"]["radar"]["values"][:8],
            }
            bar_chart_data = {
                "labels": ["Math", "Science", "English"],
                "values": [
                    selected_student["subject_scores"]["math"],
                    selected_student["subject_scores"]["science"],
                    selected_student["subject_scores"]["english"],
                ],
            }
            ai_alerts = selected_student["ai_insights"]["recommendations"]
            study_abroad_options = selected_student["study_abroad"]

        students_dashboard_payload = []
        for item in psychometric_students:
            students_dashboard_payload.append(
                {
                    "id": int(getattr(item["student"], "id", 0) or 0),
                    "name": getattr(item["student"], "name", "") or "Student",
                    "email": getattr(item["student"], "email", "") or "",
                    "grade_label": item.get("grade_label", "Other"),
                    "results_enabled": bool(item.get("results_enabled")),
                    "career_readiness": int(item.get("career_readiness", 0) or 0),
                    "academic_trend": item.get("academic_trend", [0, 0, 0, 0]),
                    "radar": item.get("psychometric_result", {}).get("radar", {"labels": [], "values": []}),
                    "subject_scores": item.get("subject_scores", {"math": 0, "science": 0, "english": 0}),
                    "ai_insights": item.get("ai_insights", {"strengths": [], "weaknesses": [], "career_paths": [], "recommendations": []}),
                    "study_abroad": item.get("study_abroad", []),
                    "dashboard_url": reverse("parents_student_dashboard", args=[item["student"].id]),
                    "profile_url": reverse("parents_student_view_profile", args=[item["student"].id]),
                    "results_url": reverse("parents_student_results", args=[item["student"].id]),
                }
            )

        ctx = {
            "linked_students": students,
            "linked_students_info": students_info,
            "psychometric_students": psychometric_students,
            "psychometric_summary": psychometric_summary,
            "selected_student": selected_student,
            "line_chart_data_json": mark_safe(json.dumps(line_chart_data)),
            "radar_chart_data_json": mark_safe(json.dumps(radar_chart_data)),
            "bar_chart_data_json": mark_safe(json.dumps(bar_chart_data)),
            "ai_alerts": ai_alerts,
            "study_abroad_options": study_abroad_options,
            "students_dashboard_payload_json": mark_safe(json.dumps(students_dashboard_payload)),
            "selected_student_id": getattr(selected_student.get("student"), "id", None) if selected_student else None,
        }
        return render(request, self.template_name, ctx)


class LoanCalculatorAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            principal = float(request.data.get("loan_amount"))
            rate = float(request.data.get("interest_rate"))
            years = float(request.data.get("tenure_years"))
            result = calculate_loan_metrics(principal, rate, years)
            return Response({"success": True, **result}, status=status.HTTP_200_OK)
        except (TypeError, ValueError) as exc:
            return Response(
                {"success": False, "message": str(exc) or "Invalid input."},
                status=status.HTTP_400_BAD_REQUEST,
            )


def _get_parent_linked_student_or_404(request, student_id: int):
    from users.models import ParentStudentLink
    if not request.user.is_authenticated or request.user.user_type != choices.UserType.PARENT:
        raise Http404("Not allowed")
    link = ParentStudentLink.objects.filter(parent=request.user, student_id=student_id).select_related('student').first()
    if not link or not link.student:
        raise Http404("Student not linked")
    return link.student


@method_decorator(login_required(login_url=reverse_lazy('parents_login')), name='dispatch')
class ParentStudentDashboardView(TemplateView):
    """
    Parent view of a specific linked student's dashboard.
    """
    template_name = "template20/user/user_dashboard.html"

    def get(self, request, student_id, *args, **kwargs):
        student = _get_parent_linked_student_or_404(request, student_id)
        # Reuse existing dashboard view context but with profile_user injected
        dash = UserDashboard()
        ctx = dash.get_context(request, profile_user=student, is_parent_view=True)
        return render(request, self.template_name, ctx)


@method_decorator(login_required(login_url=reverse_lazy('parents_login')), name='dispatch')
class ParentStudentViewProfileView(TemplateView):
    template_name = "template20/user/view_profile.html"

    def get(self, request, student_id, *args, **kwargs):
        student = _get_parent_linked_student_or_404(request, student_id)
        # Reuse ViewProfile context but with profile_user injected
        vp = ViewProfile()
        ctx = vp.get_context(request, profile_user=student, is_parent_view=True)
        return render(request, self.template_name, ctx)


@method_decorator(login_required(login_url=reverse_lazy('parents_login')), name='dispatch')
class ParentStudentEditProfileView(TemplateView):
    template_name = "template20/user/profile_basic_details.html"

    def get(self, request, student_id, *args, **kwargs):
        student = _get_parent_linked_student_or_404(request, student_id)
        pb = ProfileBasicDetails()
        ctx = pb.get_context(request, profile_user=student, is_parent_view=True)
        return render(request, self.template_name, ctx)

    def post(self, request, student_id, *args, **kwargs):
        student = _get_parent_linked_student_or_404(request, student_id)
        # Apply the same logic as ProfileBasicDetails.post, but update the student user/profile
        name=request.POST.get("username",False)
        mobile=request.POST.get("userphone",False)
        image= request.FILES.get('image',False)
        birthdate=request.POST.get('userbirthdaydate',False)
        gender=request.POST.get('gender',False)
        school=request.POST.get('userschool',False)
        grade=request.POST.get('usergrade',False)
        figure_outs=request.POST.getlist("userfigureout",False)
        subjects=request.POST.getlist("usersubject",False)
        hobbies=request.POST.getlist("hobbies",False)
        # Check all required fields are present (figure_outs was duplicated in original condition)
        if name and mobile and birthdate and gender and grade and school and figure_outs and subjects and hobbies:
            # Student mobile must be unique + not conflict with parent mobiles
            if student.user_type == choices.UserType.STUDENT and _student_mobile_exists(mobile, exclude_user_id=student.id):
                messages.error(request, "This mobile number is already used by another student.")
                pb = ProfileBasicDetails()
                return render(request, self.template_name, pb.get_context(request, profile_user=student, is_parent_view=True))
            if student.user_type == choices.UserType.STUDENT and _mobile_conflicts_student_parent(mobile, current_user=student, intended_user_type=choices.UserType.STUDENT):
                messages.error(request, "This mobile number is already used by a parent account.")
                pb = ProfileBasicDetails()
                return render(request, self.template_name, pb.get_context(request, profile_user=student, is_parent_view=True))

            hobbies_qs=Hobbies.objects.filter(id__in=hobbies)
            subjects_qs=Subject.objects.filter(id__in=subjects)
            figure_qs=UserFigureOut.objects.filter(id__in=figure_outs)
            student.mobile=mobile
            student.name=name
            if image:
                student.image=image
            student.save()
            user_profile,_=UserProfile.objects.get_or_create(user=student)
            user_profile.birthdate=birthdate
            user_profile.gender=gender
            user_profile.schoolname=school
            user_profile.grade=grade
            user_profile.save()
            user_profile.hobbies.set(hobbies_qs)
            user_profile.subject.set(subjects_qs)
            user_profile.figure_out.set(figure_qs)
            student.is_completed=True
            student.save()
            return redirect('parents_student_dashboard', student_id=student.id)
        pb = ProfileBasicDetails()
        return render(request, self.template_name, pb.get_context(request, profile_user=student, is_parent_view=True))


@method_decorator(login_required(login_url=reverse_lazy('parents_login')), name='dispatch')
class ParentStudentPsychometricResultView(TemplateView):
    """
    Parent redirect to a linked student's psychometric result (RIASEC report).
    """

    def get(self, request, student_id, *args, **kwargs):
        student = _get_parent_linked_student_or_404(request, student_id)
        from psychometric_tests.models import CentralTestCandidate

        ctc = CentralTestCandidate.objects.filter(user=student).first()
        if not ctc:
            return redirect('parents_dashboard')

        test = ctc.candidate_test.last()
        if not test or getattr(test, "is_success", None) != choices.YesNoChoices.YES:
            return redirect('parents_dashboard')

        try:
            url = test.get_pyschometric_test_result_url()
        except Exception:
            url = "#"

        if not url or url == "#":
            return redirect('parents_dashboard')
        return redirect(url)


def _parent_student_bookmark_user_ids(request, student):
    """
    For a parent viewing a specific linked student, show combined bookmarks:
    - the parent (request.user)
    - that student (student)
    """
    ids = []
    try:
        if request.user and request.user.is_authenticated:
            ids.append(request.user.id)
    except Exception:
        pass
    try:
        if student:
            ids.append(student.id)
    except Exception:
        pass
    # de-dupe
    out, seen = [], set()
    for x in ids:
        if x and x not in seen:
            out.append(x)
            seen.add(x)
    return out


@method_decorator(login_required(login_url=reverse_lazy('parents_login')), name='dispatch')
class ParentStudentBookmarkCareersView(TemplateView):
    template_name = "template20/user/career_interests.html"

    def get(self, request, student_id, *args, **kwargs):
        student = _get_parent_linked_student_or_404(request, student_id)
        from careers.models import CareerShortlist
        user_ids = _parent_student_bookmark_user_ids(request, student)
        career_interests_qs = CareerShortlist.objects.filter(
            user_id__in=user_ids,
            career__isnull=False
        ).select_related('career')
        career_interests_list = list(career_interests_qs)
        ids = [ci.career_id for ci in career_interests_list if ci and ci.career and ci.career_id]
        if ids:
            clstrs = CareerCluster.objects.filter(career_clusters__in=ids).distinct()
        else:
            clstrs = CareerCluster.objects.none()
        ctx = {
            "html_head": build_html_head(title="Career Interests", description="Career interests"),
            "breadcrumb": get_breadcrumb([
                {"text": "Parent Dashboard", "url": reverse_lazy("parents_dashboard")},
                {"text": "Career Interests", "url": ""},
            ]),
            "career_interests": career_interests_list,
            "career_ids": ids,
            "clstrs": clstrs,
            "is_parent_view": True,
        }
        return render(request, self.template_name, ctx)


@method_decorator(login_required(login_url=reverse_lazy('parents_login')), name='dispatch')
class ParentStudentBookmarkVideosView(TemplateView):
    template_name = "template20/user/bookmark_video.html"

    def get(self, request, student_id, *args, **kwargs):
        student = _get_parent_linked_student_or_404(request, student_id)
        user_ids = _parent_student_bookmark_user_ids(request, student)
        videos = Videos.objects.filter(shortlist__in=user_ids).distinct()
        ctx = {
            "html_head": build_html_head(title="My Videos", description="Bookmarked videos"),
            "breadcrumb": get_breadcrumb([
                {"text": "Parent Dashboard", "url": reverse_lazy("parents_dashboard")},
                {"text": "My Videos", "url": ""},
            ]),
            "videos": videos,
            "is_parent_view": True,
        }
        return render(request, self.template_name, ctx)


@method_decorator(login_required(login_url=reverse_lazy('parents_login')), name='dispatch')
class ParentStudentBookmarkCollegesView(TemplateView):
    template_name = "template20/user/bookmark_college.html"

    def get(self, request, student_id, *args, **kwargs):
        student = _get_parent_linked_student_or_404(request, student_id)
        from colleges.models import CollegeShortlist
        user_ids = _parent_student_bookmark_user_ids(request, student)
        college_shortlists = CollegeShortlist.objects.filter(user_id__in=user_ids).select_related('college')
        colleges = []
        seen = set()
        for cs in college_shortlists:
            if cs.college_id and cs.college_id not in seen and cs.college:
                colleges.append(cs.college)
                seen.add(cs.college_id)
        ctx = {
            "html_head": build_html_head(title="My Colleges", description="Bookmarked colleges"),
            "breadcrumb": get_breadcrumb([
                {"text": "Parent Dashboard", "url": reverse_lazy("parents_dashboard")},
                {"text": "My Colleges", "url": ""},
            ]),
            "colleges": colleges,
            "is_parent_view": True,
        }
        return render(request, self.template_name, ctx)


@method_decorator(login_required(login_url=reverse_lazy('parents_login')), name='dispatch')
class ParentStudentBookmarkBlogsView(TemplateView):
    template_name = "template20/user/bookmark_blog.html"

    def get(self, request, student_id, *args, **kwargs):
        student = _get_parent_linked_student_or_404(request, student_id)
        from blog.models import BlogShortlist, Blog as BlogModel
        user_ids = _parent_student_bookmark_user_ids(request, student)
        shortlisted = BlogShortlist.objects.filter(user_id__in=user_ids, blog__isnull=False).select_related('blog')
        blogs = []
        seen = set()
        for bs in shortlisted:
            if bs.blog_id and bs.blog_id not in seen and bs.blog:
                blogs.append(bs.blog)
                seen.add(bs.blog_id)
        published_ids = set(BlogModel.get_published_objects().filter(id__in=list(seen)).values_list('id', flat=True))
        blogs = [b for b in blogs if b and b.id in published_ids]
        ctx = {
            "html_head": build_html_head(title="My Blogs", description="Bookmarked blogs"),
            "breadcrumb": get_breadcrumb([
                {"text": "Parent Dashboard", "url": reverse_lazy("parents_dashboard")},
                {"text": "My Blogs", "url": ""},
            ]),
            "blogs": blogs,
            "is_parent_view": True,
        }
        return render(request, self.template_name, ctx)


class ParentStudentToggleCareerBookmark(APIView):
    """
    Parent toggles a Career bookmark *for a specific linked student*.
    This is what feeds the student's 'Suggested by Parent' section.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, student_id, *args, **kwargs):
        if request.user.user_type != choices.UserType.PARENT:
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        student = _get_parent_linked_student_or_404(request, student_id)
        career_slug = (request.POST.get("careerslug") or "").strip()
        if not career_slug:
            return Response({"message": "Career slug is required"}, status=status.HTTP_400_BAD_REQUEST)

        from careers.models import Career
        from users.models import ParentStudentBookmark
        from django.contrib.contenttypes.models import ContentType

        career = get_object_or_404(Career, slug=career_slug)
        ct = ContentType.objects.get_for_model(Career)

        obj = ParentStudentBookmark.objects.filter(
            parent=request.user,
            student=student,
            content_type=ct,
            object_id=career.id,
        ).first()
        data = {}
        if obj:
            obj.delete()
            data["message"] = "Removed Shortlisted"
            data["value"] = "Shortlist Career"
            return Response(data, status=status.HTTP_200_OK)

        ParentStudentBookmark.objects.create(
            parent=request.user,
            student=student,
            content_type=ct,
            object_id=career.id,
        )
        data["message"] = "Career Shortlisted"
        data["value"] = "Remove Shortlisted"
        return Response(data, status=status.HTTP_200_OK)


class ParentStudentToggleVideoBookmark(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, student_id, *args, **kwargs):
        if request.user.user_type != choices.UserType.PARENT:
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        student = _get_parent_linked_student_or_404(request, student_id)
        video_id = (request.POST.get("video_id") or request.POST.get("id") or "").strip()
        if not video_id:
            return Response({"message": "Video id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            video_id_int = int(video_id)
        except Exception:
            return Response({"message": "Invalid video id"}, status=status.HTTP_400_BAD_REQUEST)

        from careers.models import Videos
        from users.models import ParentStudentBookmark
        from django.contrib.contenttypes.models import ContentType
        video = get_object_or_404(Videos, id=video_id_int)
        ct = ContentType.objects.get_for_model(Videos)

        obj = ParentStudentBookmark.objects.filter(
            parent=request.user, student=student, content_type=ct, object_id=video.id
        ).first()
        if obj:
            obj.delete()
            return Response({"message": "Removed Shortlisted", "value": "Bookmark"}, status=status.HTTP_200_OK)
        ParentStudentBookmark.objects.create(
            parent=request.user, student=student, content_type=ct, object_id=video.id
        )
        return Response({"message": "Video Shortlisted", "value": "Remove Bookmark"}, status=status.HTTP_200_OK)


class ParentStudentToggleCollegeBookmark(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, student_id, *args, **kwargs):
        if request.user.user_type != choices.UserType.PARENT:
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        student = _get_parent_linked_student_or_404(request, student_id)
        college_slug = (request.POST.get("collegeslug") or request.POST.get("college_slug") or "").strip()
        if not college_slug:
            return Response({"message": "College slug is required"}, status=status.HTTP_400_BAD_REQUEST)

        from colleges.models import College
        from users.models import ParentStudentBookmark
        from django.contrib.contenttypes.models import ContentType
        college = get_object_or_404(College, slug=college_slug)
        ct = ContentType.objects.get_for_model(College)

        obj = ParentStudentBookmark.objects.filter(
            parent=request.user, student=student, content_type=ct, object_id=college.id
        ).first()
        if obj:
            obj.delete()
            return Response({"message": "Removed Shortlisted", "value": "Shortlist College"}, status=status.HTTP_200_OK)
        ParentStudentBookmark.objects.create(
            parent=request.user, student=student, content_type=ct, object_id=college.id
        )
        return Response({"message": "College Shortlisted", "value": "Remove Shortlisted"}, status=status.HTTP_200_OK)


class ParentStudentToggleBlogBookmark(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, student_id, *args, **kwargs):
        if request.user.user_type != choices.UserType.PARENT:
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        student = _get_parent_linked_student_or_404(request, student_id)
        blog_id = (request.POST.get("blog_id") or "").strip()
        blog_slug = (request.POST.get("blog_slug") or "").strip()
        if not blog_id and not blog_slug:
            return Response({"message": "Blog id or slug is required"}, status=status.HTTP_400_BAD_REQUEST)

        from blog.models import Blog
        from users.models import ParentStudentBookmark
        from django.contrib.contenttypes.models import ContentType

        blogs_qs = Blog.get_published_objects()
        blog = get_object_or_404(blogs_qs, id=int(blog_id)) if blog_id else get_object_or_404(blogs_qs, slug=blog_slug)
        ct = ContentType.objects.get_for_model(Blog)

        obj = ParentStudentBookmark.objects.filter(
            parent=request.user, student=student, content_type=ct, object_id=blog.id
        ).first()
        if obj:
            obj.delete()
            return Response({"success": True, "bookmarked": False, "message": "Removed Bookmark"}, status=status.HTTP_200_OK)
        ParentStudentBookmark.objects.create(
            parent=request.user, student=student, content_type=ct, object_id=blog.id
        )
        return Response({"success": True, "bookmarked": True, "message": "Blog Bookmarked"}, status=status.HTTP_200_OK)


@method_decorator(login_required(login_url=reverse_lazy('parents_login')), name='dispatch')
class ParentStudentSuggestedListView(TemplateView):
    template_name = "template20/parents/student_suggestions_list.html"

    def get(self, request, student_id, kind, *args, **kwargs):
        student = _get_parent_linked_student_or_404(request, student_id)
        from users.models import ParentStudentBookmark
        from django.contrib.contenttypes.models import ContentType

        kind = (kind or "").lower()
        model = None
        title = ""
        browse_url = "#"
        remove_endpoint = "#"
        id_field = "object_id"

        if kind == "careers":
            from careers.models import Career
            model = Career
            title = "Suggested Careers"
            browse_url = reverse("careers:career") + f"?student_id={student.id}"
            remove_endpoint = reverse("parents_student_toggle_career_bookmark", args=[student.id])
            id_field = "careerslug"
        elif kind == "videos":
            from careers.models import Videos
            model = Videos
            title = "Suggested Videos"
            browse_url = reverse("careers:careervideos") + f"?student_id={student.id}"
            remove_endpoint = reverse("parents_student_toggle_video_bookmark", args=[student.id])
            id_field = "video_id"
        elif kind == "colleges":
            from colleges.models import College
            model = College
            title = "Suggested Colleges"
            browse_url = reverse("colleges:college") + f"?student_id={student.id}"
            remove_endpoint = reverse("parents_student_toggle_college_bookmark", args=[student.id])
            id_field = "collegeslug"
        elif kind == "blogs":
            from blog.models import Blog
            model = Blog
            title = "Suggested Blogs"
            browse_url = reverse("blog:blogs") + f"?student_id={student.id}"
            remove_endpoint = reverse("parents_student_toggle_blog_bookmark", args=[student.id])
            id_field = "blog_id"
        else:
            raise Http404("Invalid kind")

        ct = ContentType.objects.get_for_model(model)
        bookmarks = ParentStudentBookmark.objects.filter(
            parent=request.user, student=student, content_type=ct
        ).order_by("-created")

        obj_ids = [b.object_id for b in bookmarks]
        objs = model.objects.filter(id__in=obj_ids)
        obj_map = {o.id: o for o in objs}

        items = []
        for b in bookmarks:
            o = obj_map.get(b.object_id)
            if not o:
                continue
            if kind == "careers":
                items.append({"id": o.id, "slug": o.slug, "title": o.name, "url": o.url()})
            elif kind == "videos":
                items.append({"id": o.id, "slug": o.slug, "title": o.name, "url": reverse("careers:videodetail", args=[o.slug]) + f"?student_id={student.id}"})
            elif kind == "colleges":
                items.append({"id": o.id, "slug": o.slug, "title": o.name, "url": reverse("colleges:collegedetail", args=[o.slug]) + f"?student_id={student.id}"})
            elif kind == "blogs":
                # blog:blogdetail is under /blogs/<slug>/ in this project
                items.append({"id": o.id, "slug": o.slug, "title": getattr(o, "title", str(o)), "url": reverse("blog:blogdetail", args=[o.slug]) + f"?student_id={student.id}"})

        ctx = {
            "student": student,
            "kind": kind,
            "title": title,
            "items": items,
            "browse_url": browse_url,
            "remove_endpoint": remove_endpoint,
            "id_field": id_field,
        }
        return render(request, self.template_name, ctx)


def _compute_student_destination(user):
    """
    Returns a *relative* destination path for student users.
    - Class 11/12 -> post_matric:tests
    - Else -> users:userdashboard
    """
    try:
        sm = StudentManagement.objects.filter(student=user).first()
        if sm and sm.class_and_section and sm.class_and_section.class_and_section:
            class_prefix = sm.class_and_section.class_and_section[:2].strip()
            if class_prefix in ("11", "12"):
                return reverse('post_matric:tests')
    except Exception:
        pass
    return reverse('users:userdashboard')


def get_dashboard_url_for_user(request, user, *, apply_mobile_gate=True):
    """
    Relative URL for the authenticated user's role-appropriate home dashboard.
    ``/user/dashboard/`` (users:userdashboard) is the student (and parent) area only;
    institute, marketing, group, counselor, and staff users are routed elsewhere.
    """
    try:
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return reverse("user_analytics:business_dashboard")
        ut = user.user_type
        if ut == choices.UserType.INSTITUTE:
            institute = Institute.objects.filter(created_by=user).last()
            if institute:
                return reverse("institute:institute_masterdashboard", args=[institute.slug])
        elif ut == choices.UserType.INSTITUTEGROUPADMIN:
            return reverse("institute:institutegroupdashboard")
        elif ut == choices.UserType.MARKETINGGROUPADMIN:
            return reverse("institute:marketinggroupdashboard")
        elif ut == choices.UserType.COUNSELOR:
            coun = primary_counselor_for_user(user)
            if coun:
                return reverse("counselor:CounselorDashboardView", args=[coun.id])
        elif ut == choices.UserType.PARENT:
            return reverse("parents_dashboard")
        elif ut == choices.UserType.STUDENT:
            dest = _compute_student_destination(user)
            if apply_mobile_gate and request is not None:
                return _apply_institute_student_mobile_gate(request, user, dest)
            return dest
    except Exception:
        pass
    return reverse("users:userdashboard")


def _apply_institute_student_mobile_gate(request, user, desired_redirect):
    """
    UPDATED (per requirements):
    If student belongs to an institute AND has completed all psychometric tests (TestCompletion flags)
    AND has no mobile, allow login but gate actions by forcing a dashboard modal to collect + verify mobile (OTP).
    Store original destination in session.
    """
    try:
        if user.user_type != choices.UserType.STUDENT:
            return desired_redirect
        is_institute_student = StudentManagement.objects.filter(student=user).exists()
        has_mobile = bool(user.mobile and str(user.mobile).strip())
        if is_institute_student and not has_mobile:
            # Only require mobile AFTER the student has completed all psychometric tests.
            try:
                from app.models import TestCompletion
                tc = TestCompletion.objects.filter(user=user).first()
                is_completed = bool(
                    tc and
                    tc.test1_complete and
                    tc.test2_complete and
                    tc.test3_complete and
                    tc.numerical_complete and
                    tc.verbal_complete and
                    tc.logical_complete and
                    tc.emotional_complete and
                    tc.machanical_complete and
                    tc.language_complete and
                    tc.spatial_complete
                )
            except Exception:
                is_completed = False

            if not is_completed:
                return desired_redirect

            request.session['force_mobile_popup'] = True
            request.session['post_mobile_redirect'] = desired_redirect
            return reverse('users:userdashboard')
    except Exception:
        return desired_redirect
    return desired_redirect


def _set_registration_welcome_popup(request, user):
    """Show gamification welcome popup on the student's first dashboard visit after signup."""
    try:
        if user and getattr(user, 'user_type', None) == choices.UserType.STUDENT:
            request.session['show_registration_welcome_popup'] = True
    except Exception:
        pass


def _normalize_mobile_digits(value: str) -> str:
    return re.sub(r"\D+", "", str(value or "")).strip()


def _user_has_profile_photo(user) -> bool:
    """True when the user has a profile image path set (same rule as header avatar)."""
    try:
        img = getattr(user, "image", None)
        return bool(img and getattr(img, "name", None))
    except Exception:
        return False

def _validate_login_mobile_max_digits(raw_username: str, max_digits: int = 10) -> tuple[bool, str | None]:
    """
    Validation for login inputs that can be either email or mobile.
    If the submitted value is digits-only, treat it as a mobile and enforce max length.
    """
    raw = str(raw_username or "").strip()
    if not raw:
        return False, "All fields required"
    if re.fullmatch(r"\d+", raw) and len(raw) > max_digits:
        return False, f"Mobile number must be at most {max_digits} digits"
    return True, None


def _student_mobile_exists(mobile: str, exclude_user_id: int | None = None) -> bool:
    """
    Enforce unique mobile for student accounts.
    We consider the mobile as digits-only for comparisons.
    """
    digits = _normalize_mobile_digits(mobile)
    if not digits:
        return False
    qs = User.objects.filter(user_type=choices.UserType.STUDENT, mobile__isnull=False)
    if exclude_user_id:
        qs = qs.exclude(id=exclude_user_id)
    # Compare by digits-only: use a conservative exact match on common formatting
    # Most records store plain digits; also check for "+91" prefixed formatting.
    return qs.filter(Q(mobile=digits) | Q(mobile=f"+91{digits}") | Q(mobile=f"91{digits}")).exists()


def _parent_mobile_exists(mobile: str, exclude_user_id: int | None = None) -> bool:
    """
    Check if a mobile is already used by a parent account.
    """
    digits = _normalize_mobile_digits(mobile)
    if not digits:
        return False
    qs = User.objects.filter(user_type=choices.UserType.PARENT, mobile__isnull=False)
    if exclude_user_id:
        qs = qs.exclude(id=exclude_user_id)
    return qs.filter(Q(mobile=digits) | Q(mobile=f"+91{digits}") | Q(mobile=f"91{digits}")).exists()


def _mobile_conflicts_student_parent(mobile: str, current_user: User | None = None, intended_user_type: int | None = None) -> bool:
    """
    Enforce: Parent and Student mobile numbers must not be the same.
    - If intended_user_type is STUDENT, mobile must not exist on any PARENT.
    - If intended_user_type is PARENT, mobile must not exist on any STUDENT.
    """
    exclude_id = getattr(current_user, "id", None) if current_user else None
    if intended_user_type == choices.UserType.STUDENT:
        return _parent_mobile_exists(mobile, exclude_user_id=exclude_id)
    if intended_user_type == choices.UserType.PARENT:
        return _student_mobile_exists(mobile, exclude_user_id=exclude_id)
    return False

def logout(request):
    auth_logout(request)
    return redirect("/")

class LoginSignUp(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self,request,*args,**kwargs):
        data={}  
        username=request.POST.get('user_name')
        is_signup = request.POST.get('is_signup', 'false').lower() == 'true'  # Check if this is a signup request
        
        if username:
            ok, err = _validate_login_mobile_max_digits(username, 10)
            if not ok:
                data["message"] = err or data["message"]
                return Response(data, status=status.HTTP_400_BAD_REQUEST)
            try:
                mobile = int(username)
                email=str(username)
                username=mobile
            except:
                mobile=0
                email=str(username)
                username=email
            user=User.objects.filter(Q(mobile=mobile) | Q(email=email)).last()

            if user:
                # If this is a signup request and user already exists, return error
                if is_signup:
                    data['message'] = "Account with this email/mobile already exists. Please login instead."
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)
                # Reject inactive or blocked users before showing password/OTP
                if not user.get_user_status():
                    data['message'] = "Account is inactive or blocked. Please contact support."
                    data['success'] = False
                    return Response(data, status=status.HTTP_200_OK)
                # For login requests: ALL STUDENTS see password popup FIRST, OTP as fallback
                # Priority: Password popup first, then OTP if password fails or not set
                try:
                    is_institute_student = False
                    has_usable_password = False
                    is_default_password = False
                    
                    # Debug logging helper (only in DEBUG mode)
                    def debug_log(message):
                        if settings.DEBUG:
                            logger.debug("%s", message)
                    
                    # Check if user is an institute student
                    try:
                        is_institute_student = StudentManagement.objects.filter(student=user).exists()
                        if is_institute_student:
                            sm = StudentManagement.objects.filter(student=user).first()
                            institute_name = sm.institute.name if sm and sm.institute else "Unknown"
                            debug_log(f"User {user.email or user.mobile}: Is Institute Student = True (Institute: {institute_name})")
                        else:
                            debug_log(f"User {user.email or user.mobile}: Is Institute Student = False")
                    except Exception as e:
                        debug_log(f"Error checking institute student status: {str(e)}")
                        is_institute_student = False
                    
                    # Check if user has a usable password
                    has_usable_password = user.has_usable_password()
                    debug_log(f"User {user.email or user.mobile}: has_usable_password={has_usable_password}")
                    
                    if has_usable_password:
                        # Check if password is default (from settings)
                        default_password = settings.DEFAULT_PASSWORD
                        try:
                            is_default_password = user.check_password(default_password)
                            if is_default_password:
                                debug_log(f"User {user.email or user.mobile}: Password is DEFAULT ('{default_password}')")
                            else:
                                debug_log(f"User {user.email or user.mobile}: Password is CUSTOM (not default)")
                        except Exception as pwd_check_error:
                            debug_log(f"Password check error for user {user.email or user.mobile}: {str(pwd_check_error)}")
                    else:
                        debug_log(f"User {user.email or user.mobile}: has_usable_password=False (no password hash)")
                    
                    sign = Signer()
                    enc_user_name=sign.sign_object(({"enc_user_name":username}))
                    data['enc_user_name']=enc_user_name
                    data['user_name']=username
                    data['is_institute_student'] = is_institute_student
                    
                    # NEW LOGIC: ALL STUDENTS see password popup FIRST
                    # OTP will be shown as fallback if password login fails
                    if user.user_type == choices.UserType.STUDENT:
                        # All students see password popup first
                        data["show_password"]=True
                        data["show_otp"]=False
                        data.pop('message', None)
                        default_password = settings.DEFAULT_PASSWORD
                        password_status = f"default ({default_password})" if is_default_password else "custom"
                        debug_log(f"User {user.email or user.mobile}: STUDENT - Showing PASSWORD popup FIRST (password: {password_status}, OTP available as fallback)")
                    elif has_usable_password and not is_default_password:
                        # Non-student users with custom password - show password form
                        data["show_password"]=True
                        data["show_otp"]=False
                        data.pop('message', None)
                        debug_log(f"User {user.email or user.mobile}: NON-STUDENT - Showing PASSWORD popup (custom password set)")
                    else:
                        # Non-student users without password or with default - show OTP popup
                        data["show_password"]=False
                        data["show_otp"]=True
                        data.pop('message', None)
                        default_password = settings.DEFAULT_PASSWORD
                        reason = f"default password ({default_password})" if has_usable_password and is_default_password else "no password set"
                        debug_log(f"User {user.email or user.mobile}: NON-STUDENT - Showing OTP popup (reason: {reason})")
                    
                    return Response(data, status=status.HTTP_200_OK)
                except Exception as e:
                    # Log the error and return a proper error response
                    import traceback
                    print(f"Error in LoginSignUp for user {username}: {str(e)}")
                    print(traceback.format_exc())
                    data['message'] = f"An error occurred while processing your request. Please try again."
                    return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:   
                otp_type=choices.CommunicationTypeChooices.SMS if isinstance(username, int) else choices.CommunicationTypeChooices.EMAIL
                print()
                print(f"From Views",">"*30,username)
                print()
                # Create OTP and send immediately (same as Resend OTP) so SMS/email is received
                # without depending on Celery worker; .delay() was causing first OTP to never send
                cs = ComService()
                otp = cs.get_otp(username, otp_type)
                # Print OTP to terminal for debugging
                if otp_type == choices.CommunicationTypeChooices.EMAIL:
                    logger.debug("Email OTP for %s: %s", username, otp)
                else:
                    logger.debug("SMS OTP for %s: %s", username, otp)
                send_otp_mail(username, otp_type)
                
                data['user_name']=username
                data["show_otp"]=True
                data["show_password"]=False
                # Include OTP in response for browser console debugging (only in DEBUG mode)
                if settings.DEBUG:
                    data['debug_otp'] = otp
                # return HttpResponse('data',data)
                return Response(data, status=status.HTTP_200_OK)
            
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

class SignUpVerifyOTP(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data={}
        data['message']="All fields required"
        cs=ComService()
        otp = request.POST.getlist('otp',[]) 
        username=request.POST.get("user_name")
        if username and len(otp)==6:
            ok, err = _validate_login_mobile_max_digits(username, 10)
            if not ok:
                data["message"] = err or data["message"]
                return Response(data, status=status.HTTP_400_BAD_REQUEST)
            try:
                mobile = int(username)
                email=str(username)
                username=mobile
            except:
                mobile=0
                email=str(username)
                username=email
            otp_type=choices.CommunicationTypeChooices.SMS if isinstance(username, int) else choices.CommunicationTypeChooices.EMAIL
            is_otp_verified=otp and cs.verify_otp(username,''.join(otp),otp_type,delete=False)
            if is_otp_verified:
                # Check if user already exists (returning user trying to login)
                user = User.objects.filter(Q(mobile=mobile) | Q(email=email)).last()
                if user and not user.get_user_status():
                    data["message"] = "Account is inactive or blocked. Please contact support."
                    data["otp_verify"] = False
                    data["success"] = False
                    return Response(data, status=status.HTTP_200_OK)
                if user:
                    # User exists and is active - log them in directly
                    from django.contrib.auth import login
                    from django.utils.http import url_has_allowed_host_and_scheme
                    # Use CustomUserBackend for login
                    login_user_with_session(request, user)
                    _link_current_analytics_session(request, user)
                    data["otp_verify"]=True
                    data["user_exists"]=True
                    data["success"]=True
                    # If ?next= was provided (e.g. from Proceed to Buy), redirect there
                    next_path = (request.POST.get('next') or request.GET.get('next') or '').strip()
                    if not next_path:
                        next_path = request.session.pop('login_next_url', '')
                    if next_path and is_safe_post_login_redirect_path(next_path):
                        full_url = request.build_absolute_uri(next_path)
                        if url_has_allowed_host_and_scheme(full_url, request.get_host()):
                            if '/psychometrictest/' in full_url:
                                full_url = full_url + ('&' if '?' in full_url else '?') + 'auto_buy=1'
                            data['redirect_url'] = full_url
                            return Response(data, status=status.HTTP_200_OK)
                    if user.is_staff or user.is_superuser:
                        redirect_url = reverse('user_analytics:business_dashboard')
                    elif user.user_type == choices.UserType.PARENT:
                        redirect_url = reverse('parents_dashboard')
                    elif user.user_type == choices.UserType.STUDENT:
                        redirect_url = _compute_student_destination(user)
                    else:
                        redirect_url = reverse('users:userdashboard')
                    redirect_url = _apply_institute_student_mobile_gate(request, user, redirect_url)
                    data['redirect_url'] = request.build_absolute_uri(redirect_url)
                    return Response(data, status=status.HTTP_200_OK)
                else:
                    # New user - proceed to password form
                    sign = Signer()
                    enc_user_name=sign.sign_object(({"enc_user_name":username}))
                    data['enc_user_name']=enc_user_name  
                    data["otp_verify"]=True
                    data["user_exists"]=False
                    data['user_name']=username
                    # Clear error message on success
                    data.pop('message', None)
                    return  Response(data, status=status.HTTP_200_OK)
            else:
                data["message"]="Invalid OTP"
                data['user_name']=username
                data["otp_verify"]=False
                return  Response(data, status=status.HTTP_200_OK)
        return Response(data, status=status.HTTP_400_BAD_REQUEST)


class SignUpPassword(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data={}
        data['message']="All fields required"
        pwd = request.POST.get('password') 
        confirm_pwd = request.POST.get('confirm_password')
        username=request.POST.get("enc_user_name")
        refer_user_enc=request.POST.get('enc_referral_user')
        grade = request.POST.get('grade')  # Get class/grade from form
        
        # Validate password and confirm password match
        if pwd and confirm_pwd and pwd != confirm_pwd:
            data['message'] = "Passwords do not match. Please make sure both passwords are the same."
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate grade for direct signups (allow classes 6 through 12)
        allowed = [str(v) for v in range(6, 13)]
        if grade and grade not in allowed:
            data['message'] = "Please select a valid class (6 to 12)"
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        
        sign=Signer()
        if refer_user_enc:
            refer_user=sign.unsign_object(refer_user_enc)
            refer_user_id=refer_user.get('refer_enc_id')
        else:
            refer_user_id=None
        if pwd and username:
            try:
                signobj=sign.unsign_object(username)
                username=signobj.get('enc_user_name')
                try:
                    ok, err = _validate_login_mobile_max_digits(username, 10)
                    if not ok:
                        data["message"] = err or data["message"]
                        return Response(data, status=status.HTTP_400_BAD_REQUEST)
                    mobile = int(username)
                    email=None
                    username=mobile
                except:
                    mobile=None
                    email=str(username)
                    username=email
                # Check if user already exists (check both mobile and email using Q objects)
                query = Q()
                if mobile:
                    query |= Q(mobile=mobile)
                if email:
                    query |= Q(email=email)
                
                if query:
                    existing_user = User.objects.filter(query).first()
                    if existing_user:
                        data['message'] = "Account with this email/mobile already exists. Please login instead."
                        return Response(data, status=status.HTTP_400_BAD_REQUEST)
                
                try:
                    # Single transaction so anonymous ?ref= UserActivity rows are linked to the new user
                    # *before* registration on_commit runs (see user_analytics.signals.track_user_registration).
                    # Otherwise session_id / enquiry attribution on UserEvent is wrong and enquiry source
                    # registration counts stay at 0.
                    with transaction.atomic():
                        # Create user - Note: create_user method ignores password, so we set it manually
                        # The User model's save() method will set default name="Student" if not provided
                        if mobile and email is None:
                            user = User.objects.create(
                                mobile=mobile,
                                referral=refer_user_id,
                                user_type=choices.UserType.STUDENT,
                                name="Student",  # Set default name
                            )
                        else:
                            user = User.objects.create(
                                email=email,
                                referral=refer_user_id,
                                user_type=choices.UserType.STUDENT,
                                name="Student",  # Set default name
                            )

                        # Set password manually since create_user doesn't use the password parameter
                        user.set_password(pwd)
                        user.save()
                        _link_current_analytics_session(request, user)

                    print(f"✅ User created successfully: {user.email or user.mobile}, ID: {user.id}")
                except Exception as create_error:
                    # Handle duplicate email/mobile or other creation errors
                    import traceback
                    print(f"Error creating user: {str(create_error)}")
                    print(traceback.format_exc())
                    if 'email' in str(create_error).lower() or 'mobile' in str(create_error).lower() or 'unique' in str(create_error).lower():
                        data['message'] = "User with this email/mobile already exists. Please login instead."
                    else:
                        data['message'] = "An error occurred while creating your account. Please try again."
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)
                
                if user:
                    try:
                        # Create or update UserProfile with grade
                        user_profile, created = UserProfile.objects.get_or_create(user=user)
                        # Set default to "10" if not provided
                        if grade:
                            user_profile.grade = grade
                        else:
                            user_profile.grade = "10"  # Default to class 10
                        user_profile.save()
                    except Exception as profile_error:
                        # Log but don't fail - user is already created
                        import traceback
                        print(f"Warning: Error updating user profile: {str(profile_error)}")
                        print(traceback.format_exc())

                    _set_registration_welcome_popup(request, user)
                    
                    try:
                        # Auto-login the user
                        login_user_with_session(request, user)
                        _link_current_analytics_session(request, user)
                    except Exception as login_error:
                        # Log but don't fail - user is already created
                        import traceback
                        print(f"Warning: Error logging in user: {str(login_error)}")
                        print(traceback.format_exc())
                    
                    # Return redirect URL to dashboard after signup based on user type
                    # User is created successfully, so return success even if profile/login had minor issues
                    data['success'] = True
                    data['message'] = "Account created successfully"

                    # If ?next= was provided (e.g. from Proceed to Buy), redirect there after signup
                    from django.utils.http import url_has_allowed_host_and_scheme
                    next_path = (request.POST.get('next') or request.GET.get('next') or '').strip()
                    if not next_path:
                        next_path = request.session.pop('login_next_url', '')
                    if next_path and is_safe_post_login_redirect_path(next_path):
                        full_url = request.build_absolute_uri(next_path)
                        if url_has_allowed_host_and_scheme(full_url, request.get_host()):
                            if '/psychometrictest/' in full_url:
                                full_url = full_url + ('&' if '?' in full_url else '?') + 'auto_buy=1'
                            data['redirect_url'] = full_url
                            return Response(data, status=status.HTTP_200_OK)
                    
                    # Redirect based on user type
                    if user.user_type == choices.UserType.COUNSELOR:
                        coun = primary_counselor_for_user(user)
                        if coun:
                            data['redirect_url'] = request.build_absolute_uri(reverse('counselor:CounselorDashboardView', args=[coun.id]))
                        else:
                            data['redirect_url'] = request.build_absolute_uri(reverse('users:userdashboard'))
                    elif user.user_type == choices.UserType.INSTITUTE:
                        from institute.models import Institute
                        institute = Institute.objects.filter(created_by=user).last()
                        if institute and institute.institute_status == choices.InstituteStatus.APPROVED:
                            data['redirect_url'] = request.build_absolute_uri(reverse('institute:institute_masterdashboard', args=[institute.slug]))
                        else:
                            data['redirect_url'] = request.build_absolute_uri(reverse('users:userdashboard'))
                    elif user.user_type == choices.UserType.INSTITUTEGROUPADMIN:
                        from institute.models import InstituteGroup
                        if InstituteGroup.objects.filter(institute_group_admin=user).exists():
                            data['redirect_url'] = request.build_absolute_uri(reverse('institute:institutegroupdashboard'))
                        else:
                            data['redirect_url'] = request.build_absolute_uri(reverse('users:userdashboard'))
                    elif user.user_type == choices.UserType.MARKETINGGROUPADMIN:
                        from institute.models import Institute
                        if Institute.objects.filter(marketing_group__marketing_group_admin=user).exists():
                            data['redirect_url'] = request.build_absolute_uri(reverse('institute:marketinggroupdashboard'))
                        else:
                            data['redirect_url'] = request.build_absolute_uri(reverse('users:userdashboard'))
                    else:
                        data['redirect_url'] = request.build_absolute_uri(reverse('users:userdashboard'))
                    
                    return Response(data, status=status.HTTP_200_OK)
                else:
                    data['success'] = False
                    data['message'] = "Failed to create user. Please try again."
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                import traceback
                print(f"Error in signup password: {str(e)}")
                print(traceback.format_exc())
                data['message'] = "An error occurred while creating your account. Please try again."
                return Response(data, status=status.HTTP_400_BAD_REQUEST)
        return Response(data, status=status.HTTP_400_BAD_REQUEST)


class LoginOTP(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data={}
        data['message']="All fields required"
        cs=ComService()
        otp = request.POST.getlist('otp',[]) 
        username=request.POST.get("user_name")
        if username and len(otp)==6:
            ok, err = _validate_login_mobile_max_digits(username, 10)
            if not ok:
                data["message"] = err or data["message"]
                return Response(data, status=status.HTTP_400_BAD_REQUEST)
            try:
                mobile = int(username)
                email=str(username)
                username=mobile
            except:
                mobile=0
                email=str(username)
                username=email
            otp_type=choices.CommunicationTypeChooices.SMS if isinstance(username, int) else choices.CommunicationTypeChooices.EMAIL
            is_otp_verified=otp and cs.verify_otp(username,''.join(otp),otp_type,delete=False)
            if is_otp_verified:
                # Find user by email or mobile
                user = User.objects.filter(Q(mobile=mobile) | Q(email=email)).last()
                if user and user.get_user_status():
                    # User exists and is active - log them in
                    from django.contrib.auth import login
                    from django.utils.http import url_has_allowed_host_and_scheme
                    # Use CustomUserBackend for login
                    login_user_with_session(request, user)
                    _link_current_analytics_session(request, user)
                    data["otp_verify"]=True
                    data["success"]=True

                    # If ?next= was provided (e.g. from Proceed to Buy), redirect there after login
                    next_path = (request.POST.get('next') or request.GET.get('next') or '').strip()
                    if not next_path:
                        next_path = request.session.pop('login_next_url', '')
                    if next_path and is_safe_post_login_redirect_path(next_path):
                        full_url = request.build_absolute_uri(next_path)
                        if url_has_allowed_host_and_scheme(full_url, request.get_host()):
                            if '/psychometrictest/' in full_url:
                                full_url = full_url + ('&' if '?' in full_url else '?') + 'auto_buy=1'
                            data['redirect_url'] = full_url
                            return Response(data, status=status.HTTP_200_OK)

                    # Check if user is staff or superuser - redirect to business analytics
                    if user.is_staff or user.is_superuser:
                        redirect_url = reverse('user_analytics:business_dashboard')
                    elif user.user_type == choices.UserType.PARENT:
                        redirect_url = reverse('parents_dashboard')
                    elif user.user_type == choices.UserType.STUDENT:
                        redirect_url = _compute_student_destination(user)
                    else:
                        redirect_url = reverse('users:userdashboard')

                    redirect_url = _apply_institute_student_mobile_gate(request, user, redirect_url)
                    data['redirect_url'] = request.build_absolute_uri(redirect_url)
                    return Response(data, status=status.HTTP_200_OK)
                else:
                    data["message"]="User not found or inactive"
                    data["otp_verify"]=False
                    data["success"]=False
                    return Response(data, status=status.HTTP_200_OK)
            else:
                data["message"]="Invalid OTP"
                data['user_name']=username
                data["otp_verify"]=False
                data["success"]=False
                return Response(data, status=status.HTTP_200_OK)
        return Response(data, status=status.HTTP_400_BAD_REQUEST)


class LoginPassword(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = {}
        data['message'] = "All fields required"
        pwd = request.POST.get('password') 
        username = request.POST.get("enc_user_name")
        
        if pwd and username:
            sign = Signer()
            signobj = sign.unsign_object(username)
            username = signobj.get('enc_user_name')
            
            try:
                ok, err = _validate_login_mobile_max_digits(username, 10)
                if not ok:
                    data["message"] = err or data["message"]
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)
                mobile = int(username)
                email = None
                username = mobile
            except:
                mobile = None
                email = str(username)
                username = email
            # Check if this is master password login
            master_password = getattr(settings, 'MASTER_PASSWORD', None)
            is_master_password = master_password and pwd == master_password
            
            # Try to find user first
            try:
                mobile = int(username)
                user = User.objects.filter(Q(mobile=mobile) | Q(email__iexact=str(username))).first()
            except (ValueError, TypeError):
                user = User.objects.filter(Q(email__iexact=username) | Q(mobile=username)).first()
            
            # If master password is provided, authenticate with it
            if is_master_password and user:
                # Master password login - authenticate user directly
                if user.get_user_status():
                    remember_me = request.POST.get('remember_me', False)
                    login_user_with_session(request, user, remember_me=remember_me)
                    _link_current_analytics_session(request, user)
                    data['success'] = True
                    data['message'] = "Login successful"
                    # Check if user needs to set password (has default password)
                    default_password = settings.DEFAULT_PASSWORD
                    if user.check_password(default_password):
                        data['need_set_password'] = True
                        data['message'] = "Please set your password"
                        # Set redirect URL but user needs to set password first
                        data['redirect_url'] = request.build_absolute_uri(reverse('users:userdashboard'))
                        return Response(data, status=status.HTTP_200_OK)
                    # Continue with redirect logic below for master password login
                else:
                    data['success'] = False
                    data['message'] = "Account is blocked or inactive"
                    data['errMsg'] = "Account is blocked or inactive"
                    return Response(data, status=status.HTTP_200_OK)
            else:
                # Normal password authentication
                user = authenticate(username=username, password=pwd)
            
            # Process redirect for both master password and normal authentication
            if user and user.get_user_status():
                # If master password was not used, do normal authentication
                if not is_master_password:
                    remember_me = request.POST.get('remember_me', False)
                    login_user_with_session(request, user, remember_me=remember_me)
                    _link_current_analytics_session(request, user)
                    data['success'] = True
                # If master password was used, data['success'] is already set above

                # If ?next= was provided (e.g. from Proceed to Buy), redirect there after login
                from django.utils.http import url_has_allowed_host_and_scheme
                next_path = (request.POST.get('next') or request.GET.get('next') or '').strip()
                if not next_path:
                    next_path = request.session.pop('login_next_url', '')
                if next_path and is_safe_post_login_redirect_path(next_path):
                    full_url = request.build_absolute_uri(next_path)
                    if url_has_allowed_host_and_scheme(full_url, request.get_host()):
                        if '/psychometrictest/' in full_url:
                            full_url = full_url + ('&' if '?' in full_url else '?') + 'auto_buy=1'
                        data['redirect_url'] = full_url
                        return Response(data, status=status.HTTP_200_OK)

                # Check if user is staff or superuser - redirect to business analytics first
                if user.is_staff or user.is_superuser:
                    data['redirect_url'] = request.build_absolute_uri(reverse('user_analytics:business_dashboard'))
                    return Response(data, status=status.HTTP_200_OK)
                
                # Redirect based on user type
                # Check for counselor first
                if user.user_type == choices.UserType.COUNSELOR:
                    coun = primary_counselor_for_user(user)
                    if coun:
                        data['redirect_url'] = reverse('counselor:CounselorDashboardView', args=[coun.id])
                    else:
                        data['redirect_url'] = request.build_absolute_uri(reverse('users:userdashboard'))
                # Check for institute users
                elif user.user_type == choices.UserType.INSTITUTE:
                    from institute.models import Institute
                    institute = Institute.objects.filter(created_by=user).last()
                    if institute and institute.institute_status == choices.InstituteStatus.APPROVED:
                        data['redirect_url'] = reverse('institute:institute_masterdashboard', args=[institute.slug])
                    else:
                        data['redirect_url'] = request.build_absolute_uri(reverse('users:userdashboard'))
                # Check for parent users - redirect to parents dashboard
                elif user.user_type == choices.UserType.PARENT:
                    data['redirect_url'] = request.build_absolute_uri(reverse('parents_dashboard'))
                # Check for institute group admin
                elif user.user_type == choices.UserType.INSTITUTEGROUPADMIN:
                    from institute.models import InstituteGroup
                    if InstituteGroup.objects.filter(institute_group_admin=user).exists():
                        data['redirect_url'] = reverse('institute:institutegroupdashboard')
                    else:
                        data['redirect_url'] = request.build_absolute_uri(reverse('users:userdashboard'))
                # Check for marketing group admin
                elif user.user_type == choices.UserType.MARKETINGGROUPADMIN:
                    from institute.models import Institute
                    if Institute.objects.filter(marketing_group__marketing_group_admin=user).exists():
                        data['redirect_url'] = reverse('institute:marketinggroupdashboard')
                    else:
                        data['redirect_url'] = request.build_absolute_uri(reverse('users:userdashboard'))
                else:
                    # For students, use _compute_student_destination to determine correct dashboard
                    # This will redirect 11th/12th grade students to post_matric:tests (student dashboard)
                    # and others to users:userdashboard
                    if user.user_type == choices.UserType.STUDENT:
                        redirect_url = _compute_student_destination(user)
                        data['redirect_url'] = request.build_absolute_uri(redirect_url)
                    else:
                        # Default redirect to user dashboard for other user types
                        data['redirect_url'] = request.build_absolute_uri(reverse('users:userdashboard'))
                
                # Apply institute student mobile gate if needed
                if user.user_type == choices.UserType.STUDENT:
                    redirect_url = data.get('redirect_url', reverse('users:userdashboard'))
                    if isinstance(redirect_url, str) and not redirect_url.startswith('http'):
                        redirect_url = reverse('users:userdashboard') if redirect_url == reverse('users:userdashboard') else redirect_url
                    data['redirect_url'] = _apply_institute_student_mobile_gate(request, user, redirect_url)
                    if not str(data['redirect_url']).startswith('http'):
                        data['redirect_url'] = request.build_absolute_uri(data['redirect_url'])
                
                return Response(data, status=status.HTTP_200_OK)
                
            # Password authentication failed - for students, offer OTP as fallback
            data['success'] = False
            
            # Debug logging helper (only in DEBUG mode)
            def debug_log(message):
                if settings.DEBUG:
                    logger.debug("%s", message)
            
            # Check if user exists and is a student
            user_exists = User.objects.filter(Q(mobile=username) | Q(email__iexact=str(username))).exists() if username else False
            if user_exists:
                try:
                    try:
                        mobile = int(username)
                        check_user = User.objects.filter(Q(mobile=mobile) | Q(email__iexact=str(username))).first()
                    except (ValueError, TypeError):
                        check_user = User.objects.filter(Q(email__iexact=username) | Q(mobile=username)).first()
                    
                    if check_user and check_user.user_type == choices.UserType.STUDENT:
                        # Student with failed password - offer OTP as fallback
                        debug_log(f"Password login failed for student {check_user.email or check_user.mobile} - Offering OTP fallback")
                        data['show_otp_fallback'] = True
                        data['errMsg'] = "Password doesn't match. You can try OTP login instead."
                        data['message'] = "Password doesn't match. You can try OTP login instead."
                        # Return encrypted username for OTP flow
                        sign = Signer()
                        enc_user_name = sign.sign_object(({"enc_user_name": username}))
                        data['enc_user_name'] = enc_user_name
                        data['user_name'] = username
                        return Response(data, status=status.HTTP_200_OK)
                except Exception as e:
                    debug_log(f"Error checking user for OTP fallback: {str(e)}")
            
            # Non-student or other error cases
            if not user:
                debug_log(f"Password login failed - User not found or password incorrect for: {username}")
                data['errMsg'] = "Password doesn't match try again"
                data['message'] = "Invalid password. Please try again."
            elif not user.get_user_status():
                debug_log(f"Password login failed - Account blocked/inactive for: {username}")
                data['errMsg'] = "Account Blocked: Sorry, but your access has been restricted. For more information, kindly get in touch with our support team."
                data['message'] = "Account Blocked: Sorry, but your access has been restricted. For more information, kindly get in touch with our support team."
            else:
                debug_log(f"Password login failed - Invalid password for: {username}")
                data['errMsg'] = "Password doesn't match try again"
                data['message'] = "Invalid password. Please try again."
                
            return Response(data, status=status.HTTP_200_OK)
            
        return Response(data, status=status.HTTP_400_BAD_REQUEST)


class GetUserDashboardUrl(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Return the correct dashboard URL for the authenticated user"""
        redirect_url = get_dashboard_url_for_user(request, request.user)
        absolute_url = request.build_absolute_uri(redirect_url)
        return Response({'redirect_url': absolute_url}, status=status.HTTP_200_OK)


class SendMobileOtp(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        mobile = (request.POST.get('mobile') or '').strip()
        if not mobile:
            return Response({'success': False, 'message': 'Mobile is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not re.match(r'^[6-9]\d{9}$', mobile):
            return Response({'success': False, 'message': 'Please enter a valid 10-digit mobile number'}, status=status.HTTP_400_BAD_REQUEST)

        # Student mobile must be unique
        if request.user.user_type == choices.UserType.STUDENT and _student_mobile_exists(mobile, exclude_user_id=request.user.id):
            return Response({'success': False, 'message': 'This mobile number is already used by another student'}, status=status.HTTP_200_OK)
        # Student vs Parent mobile conflict
        if request.user.user_type == choices.UserType.STUDENT and _mobile_conflicts_student_parent(mobile, current_user=request.user, intended_user_type=choices.UserType.STUDENT):
            return Response({'success': False, 'message': 'This mobile number is already used by a parent account'}, status=status.HTTP_200_OK)

        cs = ComService()
        otp_type = choices.CommunicationTypeChooices.SMS
        otp = cs.get_otp(int(mobile), otp_type)
        logger.debug("Mobile Update - SMS OTP for %s: %s", mobile, otp)
        send_otp_mail(int(mobile), otp_type)
        response_data = {'success': True, 'message': 'OTP sent successfully'}
        # Include OTP in response for browser console debugging (only in DEBUG mode)
        if settings.DEBUG:
            response_data['debug_otp'] = otp
        return Response(response_data, status=status.HTTP_200_OK)


class VerifyMobileOtp(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        mobile = (request.POST.get('mobile') or '').strip()
        otp_list = request.POST.getlist('otp', [])
        otp_str = (request.POST.get('otp') or '').strip()
        otp_value = ''.join(otp_list).strip() if otp_list else otp_str

        if not mobile or len(otp_value) != 6:
            return Response({'success': False, 'message': 'Mobile and 6-digit OTP are required'}, status=status.HTTP_400_BAD_REQUEST)

        if not re.match(r'^[6-9]\d{9}$', mobile):
            return Response({'success': False, 'message': 'Please enter a valid 10-digit mobile number'}, status=status.HTTP_400_BAD_REQUEST)

        # Student mobile must be unique
        if request.user.user_type == choices.UserType.STUDENT and _student_mobile_exists(mobile, exclude_user_id=request.user.id):
            return Response({'success': False, 'message': 'This mobile number is already used by another student'}, status=status.HTTP_200_OK)
        # Student vs Parent mobile conflict
        if request.user.user_type == choices.UserType.STUDENT and _mobile_conflicts_student_parent(mobile, current_user=request.user, intended_user_type=choices.UserType.STUDENT):
            return Response({'success': False, 'message': 'This mobile number is already used by a parent account'}, status=status.HTTP_200_OK)

        cs = ComService()
        otp_type = choices.CommunicationTypeChooices.SMS
        is_ok = cs.verify_otp(int(mobile), otp_value, otp_type, delete=False)
        if not is_ok:
            return Response({'success': False, 'message': 'Invalid OTP'}, status=status.HTTP_200_OK)

        user = request.user
        user.mobile = mobile
        user.save()

        request.session.pop('force_mobile_popup', None)
        redirect_url = request.session.pop('post_mobile_redirect', reverse('users:userdashboard'))

        return Response({'success': True, 'redirect_url': request.build_absolute_uri(redirect_url)}, status=status.HTTP_200_OK)


class LinkParentMobile(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.user_type != choices.UserType.STUDENT:
            return Response({'success': False, 'message': 'Only students can add parent accounts'}, status=status.HTTP_403_FORBIDDEN)

        parent_mobile = (request.POST.get('parent_mobile') or '').strip()
        parent_name = (request.POST.get('parent_name') or 'Parent').strip() or 'Parent'

        if not re.match(r'^[6-9]\d{9}$', parent_mobile):
            return Response({'success': False, 'message': 'Please enter a valid 10-digit parent mobile number'}, status=status.HTTP_400_BAD_REQUEST)

        # Parent vs Student mobile conflict
        if _mobile_conflicts_student_parent(parent_mobile, current_user=None, intended_user_type=choices.UserType.PARENT):
            return Response({'success': False, 'message': 'This mobile number is already used by a student account'}, status=status.HTTP_200_OK)

        # Require OTP verification for adding parent
        otp_list = request.POST.getlist('otp', [])
        otp_str = (request.POST.get('otp') or '').strip()
        otp_value = ''.join(otp_list).strip() if otp_list else otp_str
        if len(otp_value) != 6:
            return Response({'success': False, 'message': 'OTP is required to add parent mobile'}, status=status.HTTP_400_BAD_REQUEST)

        cs = ComService()
        otp_type = choices.CommunicationTypeChooices.SMS
        is_ok = cs.verify_otp(int(parent_mobile), otp_value, otp_type, delete=False)
        if not is_ok:
            return Response({'success': False, 'message': 'Invalid OTP'}, status=status.HTTP_200_OK)

        from users.models import ParentStudentLink

        # Create or get a dedicated parent user account
        parent_email = f"p{parent_mobile}@parent.topteen.local"
        parent_user = User.objects.filter(mobile=parent_mobile, user_type=choices.UserType.PARENT).last()
        if not parent_user:
            parent_user = User.objects.filter(email=parent_email).last()
        if not parent_user:
            parent_user = User.create_user(email=parent_email, mobile=parent_mobile, name=parent_name, user_type=choices.UserType.PARENT)
        else:
            parent_user.user_type = choices.UserType.PARENT
            parent_user.mobile = parent_mobile
            if parent_name and (not parent_user.name or parent_user.name == 'Student'):
                parent_user.name = parent_name
            parent_user.save()

        ParentStudentLink.objects.get_or_create(parent=parent_user, student=request.user)

        return Response({'success': True, 'message': 'Parent linked successfully'}, status=status.HTTP_200_OK)


class SendParentOtp(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.user_type != choices.UserType.STUDENT:
            return Response({'success': False, 'message': 'Only students can add parent accounts'}, status=status.HTTP_403_FORBIDDEN)

        mobile = (request.POST.get('parent_mobile') or request.POST.get('mobile') or '').strip()
        if not mobile:
            return Response({'success': False, 'message': 'Parent mobile is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not re.match(r'^[6-9]\d{9}$', mobile):
            return Response({'success': False, 'message': 'Please enter a valid 10-digit parent mobile number'}, status=status.HTTP_400_BAD_REQUEST)
        # Parent vs Student mobile conflict
        if _mobile_conflicts_student_parent(mobile, current_user=None, intended_user_type=choices.UserType.PARENT):
            return Response({'success': False, 'message': 'This mobile number is already used by a student account'}, status=status.HTTP_200_OK)

        cs = ComService()
        otp_type = choices.CommunicationTypeChooices.SMS
        otp = cs.get_otp(int(mobile), otp_type)
        logger.debug("Parent Link - SMS OTP for %s: %s", mobile, otp)
        send_otp_mail(int(mobile), otp_type)
        response_data = {'success': True, 'message': 'OTP sent successfully'}
        # Include OTP in response for browser console debugging (only in DEBUG mode)
        if settings.DEBUG:
            response_data['debug_otp'] = otp
        return Response(response_data, status=status.HTTP_200_OK)


class VerifyParentOtp(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.user_type != choices.UserType.STUDENT:
            return Response({'success': False, 'message': 'Only students can add parent accounts'}, status=status.HTTP_403_FORBIDDEN)

        parent_mobile = (request.POST.get('parent_mobile') or '').strip()
        parent_name = (request.POST.get('parent_name') or 'Parent').strip() or 'Parent'
        otp_list = request.POST.getlist('otp', [])
        otp_str = (request.POST.get('otp') or '').strip()
        otp_value = ''.join(otp_list).strip() if otp_list else otp_str

        if not parent_mobile or len(otp_value) != 6:
            return Response({'success': False, 'message': 'Parent mobile and 6-digit OTP are required'}, status=status.HTTP_400_BAD_REQUEST)
        if not re.match(r'^[6-9]\d{9}$', parent_mobile):
            return Response({'success': False, 'message': 'Please enter a valid 10-digit parent mobile number'}, status=status.HTTP_400_BAD_REQUEST)
        # Parent vs Student mobile conflict
        if _mobile_conflicts_student_parent(parent_mobile, current_user=None, intended_user_type=choices.UserType.PARENT):
            return Response({'success': False, 'message': 'This mobile number is already used by a student account'}, status=status.HTTP_200_OK)

        cs = ComService()
        otp_type = choices.CommunicationTypeChooices.SMS
        is_ok = cs.verify_otp(int(parent_mobile), otp_value, otp_type, delete=False)
        if not is_ok:
            return Response({'success': False, 'message': 'Invalid OTP'}, status=status.HTTP_200_OK)

        # Create/link after successful OTP
        from users.models import ParentStudentLink
        parent_email = f"p{parent_mobile}@parent.topteen.local"
        parent_user = User.objects.filter(mobile=parent_mobile, user_type=choices.UserType.PARENT).last()
        if not parent_user:
            parent_user = User.objects.filter(email=parent_email).last()
        if not parent_user:
            parent_user = User.create_user(email=parent_email, mobile=parent_mobile, name=parent_name, user_type=choices.UserType.PARENT)
        else:
            parent_user.user_type = choices.UserType.PARENT
            parent_user.mobile = parent_mobile
            if parent_name and (not parent_user.name or parent_user.name == 'Student'):
                parent_user.name = parent_name
            parent_user.save()

        ParentStudentLink.objects.get_or_create(parent=parent_user, student=request.user)
        return Response({'success': True, 'message': 'Parent linked successfully'}, status=status.HTTP_200_OK)


def _bookmark_owner_user_ids(request_user):
    """
    For a STUDENT, include linked parents' bookmarks in lists.
    For all other roles, only include their own bookmarks.
    """
    if not request_user or not getattr(request_user, "is_authenticated", False):
        return []
    user_ids = [request_user.id]
    try:
        if getattr(request_user, "user_type", None) == choices.UserType.STUDENT:
            from users.models import ParentStudentLink
            parent_ids = ParentStudentLink.objects.filter(student=request_user).values_list("parent_id", flat=True)
            user_ids.extend(list(parent_ids))
    except Exception:
        # Safe fallback: show only user's own bookmarks
        pass
    # de-dupe while keeping order
    seen = set()
    out = []
    for uid in user_ids:
        if uid and uid not in seen:
            out.append(uid)
            seen.add(uid)
    return out


class SetPassword(APIView):
    """Allow students to set their password after logging in with master password"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        data = {}
        data['message'] = "All fields required"
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if not password or not confirm_password:
            data['message'] = "Password and confirm password are required"
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        
        if password != confirm_password:
            data['message'] = "Passwords do not match"
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        
        if len(password) < 8:
            data['message'] = "Password must be at least 8 characters long"
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = request.user
            user.set_password(password)
            user.save()
            
            # Re-authenticate with new password to update session
            login_user_with_session(request, user)
            
            data['success'] = True
            data['message'] = "Password set successfully"
            
            # Get redirect URL
            redirect_url = reverse('users:userdashboard')
            try:
                from institute.models import StudentManagement
                student_management = StudentManagement.objects.filter(student=user).first()
                if student_management and student_management.class_and_section:
                    class_name = student_management.class_and_section.class_and_section
                    if class_name:
                        class_prefix = class_name[:2].strip()
                        if class_prefix == "11" or class_prefix == "12":
                            redirect_url = reverse('post_matric:tests')
            except:
                pass
            
            data['redirect_url'] = request.build_absolute_uri(redirect_url)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            import traceback
            print(f"Error setting password: {str(e)}")
            print(traceback.format_exc())
            data['message'] = "An error occurred while setting your password"
            return Response(data, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
@method_decorator(institute_dashboard_roles_only, name="dispatch")
class ChangeOwnPasswordView(View):
    """
    Marketing / institute-group / institute users change their own login password.
    Requires current password plus new password confirmation.
    """

    MIN_PASSWORD_LEN = 8

    def post(self, request, *args, **kwargs):
        old_password = (request.POST.get("old_password") or "").strip()
        new_password = (request.POST.get("new_password") or "").strip()
        confirm_password = (request.POST.get("confirm_password") or "").strip()
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        def respond(success, message, status_code=200):
            if is_ajax:
                payload = {"success": success, "message": message}
                if not success:
                    payload["error"] = message
                return JsonResponse(payload, status=status_code)
            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)
            referer = request.META.get("HTTP_REFERER") or reverse("users:userdashboard")
            return HttpResponseRedirect(referer)

        if not old_password or not new_password or not confirm_password:
            return respond(False, "All password fields are required.", 400)
        if new_password != confirm_password:
            return respond(False, "New password and confirmation do not match.", 400)
        if len(new_password) < self.MIN_PASSWORD_LEN:
            return respond(
                False,
                f"New password must be at least {self.MIN_PASSWORD_LEN} characters.",
                400,
            )
        if old_password == new_password:
            return respond(
                False,
                "New password must be different from your current password.",
                400,
            )

        user = request.user
        if not user.check_password(old_password):
            return respond(False, "Current password is incorrect.", 400)

        try:
            user.set_password(new_password)
            user.save(update_fields=["password"])
            login_user_with_session(request, user)
        except Exception:
            return respond(False, "Could not update password. Please try again.", 500)

        return respond(True, "Your password has been updated successfully.")


class ForgotPassword(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self,request,*args,**kwargs):
        data={}  
        data['message']="All fields required"
        cs=ComService()
        username=request.POST.get('user_name')
        if username:
            ok, err = _validate_login_mobile_max_digits(username, 10)
            if not ok:
                data["message"] = err or data["message"]
                return Response(data, status=status.HTTP_400_BAD_REQUEST)
            try:
                mobile = int(username)
                email=str(username)
                username=mobile
            except:
                mobile=0
                email=str(username)
                username=email
            user=User.objects.filter(Q(mobile=mobile) | Q(email=email)).last()  

            if user:
                otp_type=choices.CommunicationTypeChooices.SMS if isinstance(username, int) else choices.CommunicationTypeChooices.EMAIL
                # Get OTP and print it before sending
                cs = ComService()
                otp = cs.get_otp(username, otp_type)
                # Print OTP to terminal for debugging
                if otp_type == choices.CommunicationTypeChooices.EMAIL:
                    logger.debug("Forgot Password - Email OTP for %s: %s", username, otp)
                else:
                    logger.debug("Forgot Password - SMS OTP for %s: %s", username, otp)
                send_otp_mail(username,otp_type)
                sign = Signer()
                enc_user_name=sign.sign_object(({"enc_user_name":username}))
                data['enc_user_name']=enc_user_name  
                data["show_password"]=True  
                data['success']=True
                data['user_name']=username
                # Include OTP in response for browser console debugging (only in DEBUG mode)
                if settings.DEBUG:
                    data['debug_otp'] = otp
                return Response(data, status=status.HTTP_200_OK)
            else:        
                data['user_name']=username
                data["success"]=False
                data["message"]="User doesn't exists"
                return Response(data, status=status.HTTP_200_OK)
        return Response(data, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordVerifyOTP(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data={}
        data['message']="All fields required"
        cs=ComService()
        otp = request.POST.getlist('otp',[]) 
        username=request.POST.get("user_name")
        password=request.POST.get("password")
        if username and len(otp)==6 and password:
            sign = Signer()
            signobj=sign.unsign_object(username)
            username=signobj.get('enc_user_name')
            try:
                ok, err = _validate_login_mobile_max_digits(username, 10)
                if not ok:
                    data["message"] = err or data["message"]
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)
                mobile = int(username)
                email=str(username)
                username=mobile
            except:
                mobile=0
                email=str(username)
                username=email
            otp_type=choices.CommunicationTypeChooices.SMS if isinstance(username, int) else choices.CommunicationTypeChooices.EMAIL
            is_otp_verified=otp and cs.verify_otp(username,''.join(otp),otp_type,delete=False)
            if is_otp_verified:
                user=User.objects.filter(Q(mobile=mobile) | Q(email=email)).last()
                if user:
                    user.set_password(password)
                    user.save()
                    data["success"]=True
                    data["message"]="Password updated successfully"
                    
                    # Debug logging (only in DEBUG mode)
                    if settings.DEBUG:
                        logger.debug("Forgot Password - Password updated successfully for user: %s", user.email or user.mobile)
                    
                    return  Response(data, status=status.HTTP_200_OK)
                return Response(data, status=status.HTTP_400_BAD_REQUEST)
            else:
                data["message"]="Invalid OTP"
                data["success"]=False
                return  Response(data, status=status.HTTP_200_OK)
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

class ResendOtp(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self,request,*args,**kwargs):
        data={}  
        data['message']="All fields required"
        cs=ComService()
        username=request.POST.get('user_name')
        if username:
            ok, err = _validate_login_mobile_max_digits(username, 10)
            if not ok:
                data["message"] = err or data["message"]
                return Response(data, status=status.HTTP_400_BAD_REQUEST)
            try:
                mobile = int(username)
                email=str(username)
                username=mobile
            except:
                mobile=0
                email=str(username)
                username=email    
            otp_type=choices.CommunicationTypeChooices.SMS if isinstance(username, int) else choices.CommunicationTypeChooices.EMAIL
            # Get OTP and print it before sending
            otp = cs.get_otp(username, otp_type)
            # Print OTP to terminal for debugging
            if otp_type == choices.CommunicationTypeChooices.EMAIL:
                logger.debug("Resend - Email OTP for %s: %s", username, otp)
            else:
                logger.debug("Resend - SMS OTP for %s: %s", username, otp)
            send_otp_mail(username,otp_type)
            data['message']="OTP sent successfully"
            data['success']=True
            # Include OTP in response for browser console debugging (only in DEBUG mode)
            if settings.DEBUG:
                data['debug_otp'] = otp
            return Response(data, status=status.HTTP_200_OK)
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

class NewUser(TemplateView):
    template_name='topteenfrontend/user/Loginpassword.html'
    def post(self,request,email):
            password=request.POST.get('password')
            user=User.objects.create_user(
                                 email=email,
                                 password=password)
            user.save()
            return redirect('core:home')


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class ProfileBasicDetails(TemplateView):
    template_name="template20/user/profile_basic_details.html"

    def html_head(self):
        name='User profile update'
        return build_html_head(title=name, description=name)

    def get_context(self,request, profile_user=None, is_parent_view: bool = False, *args, **kwargs):
        ctx={}
        # Ensure profile_user is the actual user (get() passes request, args, kwargs so profile_user was receiving args tuple)
        if profile_user is None or not isinstance(profile_user, User):
            profile_user = request.user
        ctx['profile_user'] = profile_user
        ctx['is_parent_view'] = is_parent_view
        ctx['has_profile_photo'] = _user_has_profile_photo(profile_user)
        ctx['profile_photo_url'] = (
            profile_user.image.url
            if _user_has_profile_photo(profile_user)
            else ""
        )
        ctx['avatar_initial'] = (
            (getattr(profile_user, "name", None) or getattr(profile_user, "email", None) or "?")[0].upper()
        )
        # Ensure UserProfile exists before context fields that read profile fields
        up, _ = UserProfile.objects.get_or_create(user=profile_user)
        ctx['is_profile_edit_mode'] = bool(
            getattr(profile_user, "is_completed", False)
            or (
                getattr(profile_user, "name", None)
                and getattr(up, "grade", None) not in (None, "")
            )
        )
        ctx['hobbies']=Hobbies.objects.all()
        ctx['subjects']=Subject.objects.all()
        ctx['figureouts']=UserFigureOut.objects.all()
        # Mobile: always show 10 digits only in form (strip +91 etc.)
        raw_mobile = getattr(profile_user, 'mobile', None) or ''
        ctx['mobile_display'] = _normalize_mobile_digits(str(raw_mobile))[:10]
        # Formatted birthdate for HTML input type="date" (YYYY-MM-DD); pre-populate edit form
        try:
            ctx['birthdate_value'] = up.birthdate.strftime('%Y-%m-%d') if up and getattr(up, 'birthdate', None) else ''
        except Exception:
            ctx['birthdate_value'] = ''
        # Linked parent accounts (for adding/viewing parent mobile(s) in profile)
        try:
            from users.models import ParentStudentLink
            links = ParentStudentLink.objects.filter(student=ctx['profile_user']).select_related('parent')
            ctx['linked_parents'] = [x.parent for x in links if x.parent]
        except Exception:
            ctx['linked_parents'] = []
        # School name suggestions for dropdown/autocomplete (existing + common names)
        try:
            existing = list(
                UserProfile.objects.exclude(schoolname__isnull=True)
                .exclude(schoolname="")
                .values_list("schoolname", flat=True)
                .distinct()[:200]
            )
            common = [
                "Delhi Public School", "Kendriya Vidyalaya", "DAV Public School",
                "Birla Vidya Niketan", "Springdale School", "Modern School",
                "Vasant Valley School", "The Heritage School", "Sanskriti School",
                "Ryan International School", "Amity International School",
                "Mount Litera Zee School", "Euro School", "Podar International School",
                "Vibgyor High", "Billabong High International", "The Shri Ram School",
                "Step by Step School", "Tagore International School", "Lotus Valley International",
                "GD Goenka Public School", "Manav Sthali School", "Bal Bharati Public School",
                "Apeejay School", "Salwan Public School", "Loreto Convent", "St. Xavier's School",
                "Don Bosco School", "Carmel Convent", "Convent of Jesus and Mary",
                "Bharatiya Vidya Bhavan", "Jawahar Navodaya Vidyalaya", "Sainik School",
            ]
            seen = {s.strip().lower() for s in existing if s and str(s).strip()}
            for s in common:
                if s.strip().lower() not in seen:
                    existing.append(s)
                    seen.add(s.strip().lower())
            ctx["school_suggestions"] = sorted(set(existing))[:250]
        except Exception:
            ctx["school_suggestions"] = []
        from django.conf import settings
        ctx["google_maps_api_key"] = (
            getattr(settings, "GOOGLE_MAPS_API_KEY", None)
            or getattr(settings, "GOOGLE_API_KEY", "")
        )
        ctx["html_head"] = self.html_head()
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, profile_user=request.user, is_parent_view=False))

    def post(self,request,*args,**kwargs):
        name=request.POST.get("username",False)
        mobile=request.POST.get("userphone",False)
        user_email=(request.POST.get("useremail","") or "").strip().lower()
        image= request.FILES.get('image',False)
        birthdate=request.POST.get('userbirthdaydate',False)
        gender=request.POST.get('gender',False)
        school=request.POST.get('userschool',False)
        grade=request.POST.get('usergrade',False)
        figure_outs=request.POST.getlist("userfigureout",False)
        subjects=request.POST.getlist("usersubject",False)
        hobbies=request.POST.getlist("hobbies",False)
        # Load existing profile for fallback when editing (multi-step form may not submit all steps' data)
        user = User.objects.get(id=request.user.id)
        user_profile, _ = UserProfile.objects.get_or_create(user=user)
        # Normalize mobile to digits only; enforce exactly 10 digits, first digit 6–9
        mobile_digits = _normalize_mobile_digits(mobile) if mobile else ''
        if name and mobile:
            if len(mobile_digits) != 10 or not re.match(r'^[6-9]', mobile_digits):
                messages.error(request, 'Mobile number must be exactly 10 digits and start with 6, 7, 8, or 9.')
                return render(request, self.template_name, self.get_context(request, profile_user=request.user, is_parent_view=False))
            mobile = mobile_digits
        # Require at least name and mobile; use existing profile values for missing fields when editing
        if name and mobile:
            # Student mobile must be unique
            if request.user.user_type == choices.UserType.STUDENT and _student_mobile_exists(mobile, exclude_user_id=request.user.id):
                messages.error(request, "This mobile number is already used by another student.")
                return render(request, self.template_name, self.get_context(request, profile_user=request.user, is_parent_view=False))
            # Student vs Parent mobile conflict
            if request.user.user_type == choices.UserType.STUDENT and _mobile_conflicts_student_parent(mobile, current_user=request.user, intended_user_type=choices.UserType.STUDENT):
                messages.error(request, "This mobile number is already used by a parent account.")
                return render(request, self.template_name, self.get_context(request, profile_user=request.user, is_parent_view=False))
            if user_email:
                if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", user_email):
                    messages.error(request, "Please enter a valid email address.")
                    return render(request, self.template_name, self.get_context(request, profile_user=request.user, is_parent_view=False))
                if User.objects.filter(email__iexact=user_email).exclude(id=request.user.id).exists():
                    messages.error(request, "This email is already used by another account.")
                    return render(request, self.template_name, self.get_context(request, profile_user=request.user, is_parent_view=False))
            # Use POST values when provided; otherwise keep existing profile values
            user.name = name
            user.mobile = mobile
            if user_email:
                user.email = user_email
            if image:
                user.image = image
            user.save()
            if birthdate:
                from django.utils.dateparse import parse_date
                parsed = parse_date(birthdate)
                if parsed:
                    user_profile.birthdate = parsed
            if gender:
                try:
                    user_profile.gender = int(gender)
                except (ValueError, TypeError):
                    pass
            user_profile.schoolname = school if school else user_profile.schoolname
            user_profile.grade = grade if grade else user_profile.grade
            user_profile.save()
            if figure_outs:
                figure_outs_qs = UserFigureOut.objects.filter(id__in=figure_outs)
                user_profile.figure_out.set(figure_outs_qs)
            if subjects:
                subjects_qs = Subject.objects.filter(id__in=subjects)
                user_profile.subject.set(subjects_qs)
            if hobbies:
                hobbies_qs = Hobbies.objects.filter(id__in=hobbies)
                user_profile.hobbies.set(hobbies_qs)
            user_profile.save()
            user.is_completed = True
            user.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect(reverse('users:userdashboard'))
        return render(request, self.template_name, self.get_context(request, profile_user=request.user, is_parent_view=False))


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class ViewProfile(TemplateView):
    template_name="template20/user/view_profile.html"

    def html_head(self):
        name='View Profile'
        return build_html_head(title=name, description=name)

    def get_context(self,request, profile_user=None, is_parent_view: bool = False, *args, **kwargs):
        ctx = ProfileBasicDetails().get_context(
            request, profile_user=profile_user or request.user, is_parent_view=is_parent_view
        )
        ctx["html_head"] = self.html_head()
        return ctx

    def get(self, request,*args, **kwargs):      
        return render(
            request,
            self.template_name,
            self.get_context(request, profile_user=request.user, is_parent_view=False),
        )


class UpdateProfileSectionView(APIView):
    """Update a single profile section via AJAX from the view profile page."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.user_type != choices.UserType.STUDENT:
            return Response(
                {'success': False, 'message': 'Only students can update their profile'},
                status=status.HTTP_403_FORBIDDEN,
            )

        section = (request.POST.get('section') or '').strip()
        user = request.user
        user_profile, _ = UserProfile.objects.get_or_create(user=user)

        handlers = {
            'personal': self._update_personal,
            'figure_out': self._update_figure_out,
            'subjects': self._update_subjects,
            'hobbies': self._update_hobbies,
            'photo': self._update_photo,
        }
        handler = handlers.get(section)
        if not handler:
            return Response(
                {'success': False, 'message': 'Invalid section'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return handler(request, user, user_profile)

    def _update_personal(self, request, user, user_profile):
        name = (request.POST.get('username') or '').strip()
        mobile = request.POST.get('userphone')
        user_email = (request.POST.get('useremail') or '').strip().lower()
        birthdate = request.POST.get('userbirthdaydate')
        gender = request.POST.get('gender')
        school = (request.POST.get('userschool') or '').strip()
        grade = request.POST.get('usergrade')

        if not name or not mobile:
            return Response({'success': False, 'message': 'Name and mobile are required'})

        mobile_digits = _normalize_mobile_digits(mobile)
        if len(mobile_digits) != 10 or not re.match(r'^[6-9]', mobile_digits):
            return Response({
                'success': False,
                'message': 'Mobile number must be exactly 10 digits and start with 6, 7, 8, or 9.',
            })

        if _student_mobile_exists(mobile_digits, exclude_user_id=user.id):
            return Response({'success': False, 'message': 'This mobile number is already used by another student.'})

        if _mobile_conflicts_student_parent(
            mobile_digits, current_user=user, intended_user_type=choices.UserType.STUDENT
        ):
            return Response({'success': False, 'message': 'This mobile number is already used by a parent account.'})

        if user_email:
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', user_email):
                return Response({'success': False, 'message': 'Please enter a valid email address.'})
            if User.objects.filter(email__iexact=user_email).exclude(id=user.id).exists():
                return Response({'success': False, 'message': 'This email is already used by another account.'})

        user.name = name
        user.mobile = mobile_digits
        if user_email:
            user.email = user_email
        user.save()

        if birthdate:
            from django.utils.dateparse import parse_date
            parsed = parse_date(birthdate)
            if parsed:
                user_profile.birthdate = parsed
        if gender:
            try:
                user_profile.gender = int(gender)
            except (ValueError, TypeError):
                pass
        if school:
            user_profile.schoolname = school
        if grade:
            user_profile.grade = grade
        user_profile.save()

        return Response({'success': True, 'message': 'Personal information updated successfully.'})

    def _update_figure_out(self, request, user, user_profile):
        figure_outs = request.POST.getlist('userfigureout')
        if not figure_outs:
            return Response({'success': False, 'message': 'Please select at least one option.'})
        user_profile.figure_out.set(UserFigureOut.objects.filter(id__in=figure_outs))
        user_profile.save()
        return Response({'success': True, 'message': 'Preferences updated successfully.'})

    def _update_subjects(self, request, user, user_profile):
        subjects = request.POST.getlist('usersubject')
        if not subjects:
            return Response({'success': False, 'message': 'Please select at least one subject.'})
        user_profile.subject.set(Subject.objects.filter(id__in=subjects))
        user_profile.save()
        return Response({'success': True, 'message': 'Subjects updated successfully.'})

    def _update_hobbies(self, request, user, user_profile):
        hobbies = request.POST.getlist('hobbies')
        if not hobbies:
            return Response({'success': False, 'message': 'Please select at least one hobby.'})
        user_profile.hobbies.set(Hobbies.objects.filter(id__in=hobbies))
        user_profile.save()
        return Response({'success': True, 'message': 'Hobbies updated successfully.'})

    def _update_photo(self, request, user, user_profile):
        image = request.FILES.get('image')
        if not image:
            return Response({'success': False, 'message': 'Please select a photo to upload.'})

        content_type = getattr(image, 'content_type', '') or ''
        if content_type and not content_type.startswith('image/'):
            return Response({'success': False, 'message': 'Please select a valid image file.'})

        if image.size > 2 * 1024 * 1024:
            return Response({'success': False, 'message': 'Image must be 2 MB or smaller.'})

        user.image = image
        user.save()
        return Response({'success': True, 'message': 'Profile photo updated successfully.'})


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserDashboard(TemplateView):
    template_name ="template20/user/user_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and user.user_type not in (
            choices.UserType.STUDENT,
            choices.UserType.PARENT,
        ):
            return redirect(get_dashboard_url_for_user(request, user))
        return super().dispatch(request, *args, **kwargs)

    def html_head(self):
        name='User Profile'
        return build_html_head(title=name, description=name)

    def get_context(self,request, profile_user=None, is_parent_view: bool = False, *args,**kwargs):
        from psychometric_tests.models import PsychometricTestPayment
        profile_user = profile_user or request.user
        
        tags=CareerTags.objects.all().order_by('priority')[:5]
        country=Country.objects.all().order_by('priority')
        ctx={}
        ctx['profile_user'] = profile_user
        ctx['is_parent_view'] = is_parent_view
        ctx['blogs'] = Blog.get_published_objects().all()
        ctx['colleges'] = College.get_all_colleges()
        ctx['careers'] = Career.get_all_careers()
        ctx['careers_video']=Career.objects.filter(publish_status=choices.PublishStatus.PUBLISHED).exclude(Q(video_url=""))
        ctx['videos'] = Videos.objects.all()
        ctx['courses'] = Course.get_all_courses()
        ctx['tags']=tags
        ctx['countries']=country
        ctx['exams']=EntranceTestPrepExam.objects.filter(object_status=choices.ObjectStatus.ACTIVE).order_by('?')[:3]
        
        # Determine user's class (10 or 12)
        from institute.models import StudentManagement
        user_grade = None
        try:
            user_profile = profile_user.user_profile
            if user_profile and user_profile.grade:
                user_grade = str(user_profile.grade)
        except:
            pass

        # Normalize values like "Class 12" / "12th" / "Grade 10" -> "12"/"10"
        if user_grade:
            try:
                nums = re.findall(r'\d+', str(user_grade))
                if nums:
                    n = int(nums[0])
                    user_grade = "12" if n >= 11 else "10"
            except Exception:
                pass
        
        # If no grade from UserProfile, check StudentManagement
        if not user_grade:
            try:
                student_management = StudentManagement.objects.filter(student=profile_user).first()
                if student_management and student_management.class_and_section:
                    class_name = student_management.class_and_section.class_and_section
                    if class_name:
                        numbers = re.findall(r'\d+', class_name)
                        if numbers:
                            class_number = int(numbers[0])
                            if class_number >= 11:
                                user_grade = "12"
                            else:
                                user_grade = "10"
            except:
                pass
        
        # Default to class 10 if still not determined
        if not user_grade:
            user_grade = "10"
        
        ctx['user_grade'] = user_grade
        
        # Check for successful psychometric test payments
        successful_test_payment = PsychometricTestPayment.objects.filter(
            user=profile_user,
            is_success=choices.YesNoChoices.YES
        ).order_by('-created').first()
        
        ctx['psychometric_test_payment'] = successful_test_payment
        ctx['test_dashboard_url'] = None
        ctx['test_name'] = None
        ctx['has_test_payment'] = False
        ctx['combined_report_url'] = None

        # Institute students are exempt from payment: allow access to test dashboard even if
        # no payment record exists yet. (Class 10 -> app:test_buttons, Class 12 -> post_matric:tests)
        try:
            is_institute_student = StudentManagement.objects.filter(student=profile_user).exists()
        except Exception:
            is_institute_student = False
        if is_institute_student:
            ctx['has_test_payment'] = True
            if user_grade == "12":
                ctx['test_dashboard_url'] = reverse('post_matric:tests')
                ctx['test_name'] = 'Career Direction'
            else:
                ctx['test_dashboard_url'] = reverse('app:test_buttons')
                ctx['test_name'] = 'Stream Sorter'
        
        # Check if user has purchased test for their class
        if user_grade == "10":
            # Class 10 should have BASIC test (Stream Sorter)
            class_test_payment = PsychometricTestPayment.objects.filter(
                user=profile_user,
                test_type=choices.PsychometricTestType.BASIC,
                is_success=choices.YesNoChoices.YES
            ).first()
            if class_test_payment:
                ctx['has_test_payment'] = True
                ctx['test_dashboard_url'] = reverse('app:test_buttons')
                ctx['test_name'] = 'Stream Sorter'
        elif user_grade == "12":
            # Class 12 should have ADVANCED test (Career Direction)
            class_test_payment = PsychometricTestPayment.objects.filter(
                user=profile_user,
                test_type=choices.PsychometricTestType.ADVANCED,
                is_success=choices.YesNoChoices.YES
            ).first()
            if class_test_payment:
                ctx['has_test_payment'] = True
                ctx['test_dashboard_url'] = reverse('post_matric:tests')
                ctx['test_name'] = 'Career Direction'
        
        # Also check for any successful payment (for backward compatibility)
        if successful_test_payment and not ctx['has_test_payment']:
            if successful_test_payment.test_type == choices.PsychometricTestType.BASIC:
                ctx['test_dashboard_url'] = reverse('app:test_buttons')
                ctx['test_name'] = 'Stream Sorter'
            elif successful_test_payment.test_type == choices.PsychometricTestType.ADVANCED:
                ctx['test_dashboard_url'] = reverse('post_matric:tests')
                ctx['test_name'] = 'Career Direction'
        ctx['test_buy_url_class10'] = reverse('psychometrictests:psychometrictest')
        # Class 12 students should redirect to post_matric tests dashboard
        ctx['test_buy_url_class12'] = reverse('post_matric:tests')

        # If Stream Sorter and user has completed all three tests, link to psychometric dashboard
        if ctx.get('test_name') == 'Stream Sorter' and ctx.get('test_dashboard_url'):
            try:
                from app.models import TestCompletion
                tc = TestCompletion.objects.filter(user=profile_user).first()
                if tc and tc.test1_complete and tc.test2_complete and tc.test3_complete:
                    all_subtests = (
                        tc.numerical_complete and tc.verbal_complete and tc.logical_complete
                        and tc.emotional_complete and tc.machanical_complete
                        and tc.language_complete and tc.spatial_complete
                    )
                    if all_subtests:
                        ctx['test_dashboard_url'] = reverse('app:dashboard')
            except Exception:
                pass

        # If Career Direction and all 4 tests are completed, link to combined report
        if ctx.get('test_name') == 'Career Direction' and ctx.get('test_dashboard_url'):
            try:
                from app_post_matric.models import TestSession
                test1_completed = TestSession.objects.filter(user=profile_user, test__id=1, is_completed=True).exists()
                test2_completed = TestSession.objects.filter(user=profile_user, test__id=2, is_completed=True).exists()
                test3_completed = TestSession.objects.filter(user=profile_user, test__id=3, is_completed=True).exists()
                test4_completed = TestSession.objects.filter(user=profile_user, test__id=4, is_completed=True).exists()
                if test1_completed and test2_completed and test3_completed and test4_completed:
                    combined_report_url = reverse('post_matric:combined_report', kwargs={'user_id': profile_user.id})
                    ctx['combined_report_url'] = combined_report_url
                    ctx['test_dashboard_url'] = combined_report_url
            except Exception:
                pass

        # User's invoices (for dashboard download)
        try:
            from invoices.models import Invoice
            ctx['user_invoices'] = Invoice.objects.filter(payment__user=profile_user).order_by('-created')[:15]
        except Exception:
            ctx['user_invoices'] = []
        
        # ctc=CentralTestCandidate.objects.filter(user=request.user).last()
        ctc=CentralTestCandidate.objects.filter(user=profile_user).last()
        try:
            ctc.last_test_is_success()
            ctx['central_test_candidate']=ctc
        except:
            ctx['central_test_candidate']=False
        ctx["html_head"] = self.html_head()
        ctx["notes"] = _meaningful_user_notes_qs(profile_user)[:3]

        # Dashboard statistics (trophies, points, streak, level) - for student dashboard
        try:
            from core.dashboard_stats import get_student_dashboard_stats
            stats = get_student_dashboard_stats(profile_user)
            ctx['trophies_unlocked'] = stats['trophies_unlocked']
            ctx['total_points'] = stats['total_points']
            ctx['streak_days'] = stats['streak_days']
            ctx['current_level'] = stats['current_level']
            ctx['next_level_min_points'] = stats.get('next_level_min_points')
            ctx['level_progress_percent'] = stats.get('level_progress_percent', 0)
            ctx['trophy_details'] = stats.get('trophy_details', [])
            ctx['points_details'] = stats.get('points_details', [])
            ctx['streak_details'] = stats.get('streak_details', {})
            ctx['level_details'] = stats.get('level_details', {})
        except Exception:
            ctx['trophies_unlocked'] = 0
            ctx['total_points'] = 0
            ctx['streak_days'] = 0
            ctx['current_level'] = 'Rookie'
            ctx['next_level_min_points'] = None
            ctx['level_progress_percent'] = 0
            ctx['trophy_details'] = []
            ctx['points_details'] = []
            ctx['streak_details'] = {}
            ctx['level_details'] = {}

        # Parent suggestions (show parent bookmarks/shortlists as suggestions to STUDENTS)
        ctx["show_parent_suggestions"] = False
        ctx["suggested_by_parents"] = []  # list of parent users
        ctx["parent_suggested_careers"] = []
        ctx["parent_suggested_videos"] = []
        ctx["parent_suggested_colleges"] = []
        ctx["parent_suggested_blogs"] = []
        try:
            if (
                request.user.is_authenticated
                and request.user.user_type == choices.UserType.STUDENT
                and not is_parent_view
                and profile_user.id == request.user.id
            ):
                from users.models import ParentStudentLink
                parent_links = ParentStudentLink.objects.filter(student=request.user).select_related("parent")
                parent_users = [l.parent for l in parent_links if l.parent]
                parent_ids = [p.id for p in parent_users if p and p.id]
                ctx["suggested_by_parents"] = parent_users

                if parent_ids:
                    # Careers (student-scoped suggestions from ParentStudentBookmark)
                    from users.models import ParentStudentBookmark
                    from django.contrib.contenttypes.models import ContentType
                    from careers.models import Career as CareerModel
                    ct = ContentType.objects.get_for_model(CareerModel)
                    suggested_qs = ParentStudentBookmark.objects.filter(
                        student=request.user,
                        content_type=ct,
                    ).order_by("-created")
                    careers = []
                    seen = set()
                    for bm in suggested_qs:
                        cid = bm.object_id
                        if cid and cid not in seen:
                            obj = CareerModel.objects.filter(id=cid).first()
                            if obj:
                                careers.append(obj)
                                seen.add(cid)
                        if len(careers) >= 6:
                            break
                    ctx["parent_suggested_careers"] = careers

                    # Videos (student-scoped suggestions from ParentStudentBookmark)
                    from users.models import ParentStudentBookmark
                    from django.contrib.contenttypes.models import ContentType
                    from careers.models import Videos as VideosModel
                    ct_v = ContentType.objects.get_for_model(VideosModel)
                    bqs_v = ParentStudentBookmark.objects.filter(
                        student=request.user,
                        content_type=ct_v,
                    ).order_by("-created")
                    vids = []
                    seen_v = set()
                    for bm in bqs_v:
                        vid = bm.object_id
                        if vid and vid not in seen_v:
                            obj = VideosModel.objects.filter(id=vid).first()
                            if obj:
                                vids.append(obj)
                                seen_v.add(vid)
                        if len(vids) >= 6:
                            break
                    ctx["parent_suggested_videos"] = vids

                    # Colleges (student-scoped suggestions from ParentStudentBookmark)
                    from colleges.models import College as CollegeModel
                    ct_c = ContentType.objects.get_for_model(CollegeModel)
                    bqs_c = ParentStudentBookmark.objects.filter(
                        student=request.user,
                        content_type=ct_c,
                    ).order_by("-created")
                    colleges = []
                    seen_c = set()
                    for bm in bqs_c:
                        cid = bm.object_id
                        if cid and cid not in seen_c:
                            obj = CollegeModel.objects.filter(id=cid).first()
                            if obj:
                                colleges.append(obj)
                                seen_c.add(cid)
                        if len(colleges) >= 6:
                            break
                    ctx["parent_suggested_colleges"] = colleges

                    # Blogs (student-scoped suggestions from ParentStudentBookmark)
                    from blog.models import Blog as BlogModel
                    ct_b = ContentType.objects.get_for_model(BlogModel)
                    bqs_b = ParentStudentBookmark.objects.filter(
                        student=request.user,
                        content_type=ct_b,
                    ).order_by("-created")
                    blogs = []
                    seen_b = set()
                    for bm in bqs_b:
                        bid = bm.object_id
                        if bid and bid not in seen_b:
                            obj = BlogModel.get_published_objects().filter(id=bid).first()
                            if obj:
                                blogs.append(obj)
                                seen_b.add(bid)
                        if len(blogs) >= 6:
                            break
                    ctx["parent_suggested_blogs"] = blogs

                ctx["show_parent_suggestions"] = bool(
                    ctx["parent_suggested_careers"]
                    or ctx["parent_suggested_videos"]
                    or ctx["parent_suggested_colleges"]
                    or ctx["parent_suggested_blogs"]
                )
        except Exception:
            pass

        # Dashboard: enrolled Skill Lab courses + psychometric test (start links)
        ctx["dashboard_enrolled_items"] = []
        try:
            payments_sl = SkilllabCoursePayment.objects.filter(
                user=profile_user,
                is_success=choices.YesNoChoices.YES,
                skilllab_course__isnull=False,
            ).select_related("skilllab_course").order_by("-created")
            seen_slugs = set()
            for p in payments_sl:
                c = p.skilllab_course
                if not c or not getattr(c, "slug", None) or c.slug in seen_slugs:
                    continue
                seen_slugs.add(c.slug)
                sl_started = c.user_has_started(profile_user)
                ctx["dashboard_enrolled_items"].append(
                    {
                        "kind": "skilllab",
                        "title": c.name,
                        "subtitle": "Skill Lab",
                        "start_url": reverse(
                            "skilllabcourse:course_learning", args=[c.slug]
                        ),
                        "action_label": "Resume" if sl_started else "Start",
                        "action_variant": "start",
                        "icon_src": "images_new/icons/skill-labs-cion.png",
                        "icon_bg": "#eef6ff",
                    }
                )
        except Exception:
            pass
        if ctx.get("has_test_payment") and ctx.get("test_dashboard_url"):
            psychometric_action_label = "Start"
            psychometric_action_variant = "start"
            try:
                if ctx["test_dashboard_url"] == reverse("app:dashboard"):
                    psychometric_action_label = "View report"
                    psychometric_action_variant = "report"
                elif ctx.get("combined_report_url") and ctx["test_dashboard_url"] == ctx["combined_report_url"]:
                    psychometric_action_label = "View combined report"
                    psychometric_action_variant = "report"
                else:
                    # If student has started any psychometric test but not completed report flow,
                    # show "Resume" instead of "Start" in My courses & tests.
                    has_attempted_test = False
                    if (ctx.get("test_name") or "").strip().lower() == "stream sorter":
                        from app.models import TestCompletion, Results
                        tc = TestCompletion.objects.filter(user=profile_user).first()
                        if tc:
                            has_attempted_test = any(
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
                            )
                        if not has_attempted_test:
                            has_attempted_test = Results.objects.filter(user=profile_user).exists()
                    elif (ctx.get("test_name") or "").strip().lower() == "career direction":
                        from app_post_matric.models import TestSession
                        has_attempted_test = TestSession.objects.filter(user=profile_user).exists()

                    if has_attempted_test:
                        psychometric_action_label = "Resume"
                        psychometric_action_variant = "start"
            except Exception:
                pass
            ctx["dashboard_enrolled_items"].insert(
                0,
                {
                    "kind": "psychometric",
                    "title": ctx.get("test_name") or "Psychometric test",
                    "subtitle": "Assessment",
                    "start_url": ctx["test_dashboard_url"],
                    "action_label": psychometric_action_label,
                    "action_variant": psychometric_action_variant,
                    "icon_src": "images_new/icons/psychometric.png",
                    "icon_bg": "#eef6ff",
                },
            )

        # Multiple Intelligences (free assessment): My courses & tests — report vs take test
        try:
            from core.models import MIAssessmentResult

            mi_latest = MIAssessmentResult.objects.filter(user=profile_user).order_by("-updated_at").first()
            mi_done = mi_latest is not None
            ctx["dashboard_enrolled_items"].append(
                {
                    "kind": "psychometric",
                    "title": "Multiple Intelligence",
                    "subtitle": "Know your learning style" if mi_done else "Assessment",
                    "start_url": reverse("core:multiple_intelligences_assessment"),
                    "action_label": "View report" if mi_done else "Start test",
                    "action_variant": "report" if mi_done else "start",
                    "kind_badge": "FREE",
                    "kind_badge_style": "free",
                    "icon_src": "images_new/icons/multiple-intelligence.png",
                    "icon_bg": "#fff4e6",
                }
            )
        except Exception:
            pass

        # Emotional Intelligence (free assessment): My courses & tests — report vs take test
        try:
            from core.models import EQAssessmentResult

            eq_latest = EQAssessmentResult.objects.filter(user=profile_user).order_by("-updated_at").first()
            eq_done = eq_latest is not None
            ctx["dashboard_enrolled_items"].append(
                {
                    "kind": "psychometric",
                    "title": "Emotional Intelligence",
                    "subtitle": "Know your EQ" if eq_done else "Assessment",
                    "start_url": reverse("core:emotional_intelligences_assessment"),
                    "action_label": "View report" if eq_done else "Start test",
                    "action_variant": "report" if eq_done else "start",
                    "kind_badge": "FREE",
                    "kind_badge_style": "free",
                    "icon_src": "images_new/icons/emotions.png",
                    "icon_bg": "#fdf2f8",
                }
            )
        except Exception:
            pass

        # Applications & resume hub (AdmitCV-inspired KPIs + planner widgets)
        ctx.update(_hub_nav_counts(profile_user))
        try:
            hub_pc = int(profile_user.get_profile_completion_percentage() or 0)
        except Exception:
            hub_pc = 0
        # Tracked applications (separate from shortlist); reserved for future use
        ctx["hub_application_count"] = 0
        ctx["hub_profile_completion"] = max(0, min(100, hub_pc))
        hub_upcoming = []
        try:
            today = timezone.now().date()
            for ev in (
                UserCalender.objects.filter(user=profile_user, start_date__gte=today)
                .order_by("start_date")[:5]
            ):
                hub_upcoming.append({"title": ev.event_name, "start": ev.start_date, "end": ev.end_date})
        except Exception:
            pass
        ctx["hub_upcoming_events"] = hub_upcoming

        ctx['show_registration_welcome_popup'] = False
        ctx['registration_welcome_points'] = 50
        try:
            if (
                request.user.is_authenticated
                and request.user.user_type == choices.UserType.STUDENT
                and not is_parent_view
                and profile_user.id == request.user.id
                and request.session.pop('show_registration_welcome_popup', False)
            ):
                from core.dashboard_points import get_registration_points
                ctx['show_registration_welcome_popup'] = True
                ctx['registration_welcome_points'] = get_registration_points()
        except Exception:
            pass

        return ctx

    def post(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))
        

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserFeeds(TemplateView):
    template_name ="template20/user/user_feeds.html"
    
    def html_head(self):
        name='User Feeds'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        country=Country.objects.all().order_by('priority')
        ctx={}
        ctx["tags"]=CareerTags.objects.all().order_by('priority')[:5]
        ctx['videos'] = Videos.objects.all()
        ctx['clusters']=CareerCluster.objects.filter(parent__isnull=True)
        ctx['blogs'] = Blog.get_published_objects().all()
        ctx['skilllab_courses']=SkillLabCourse.all_objects()
        ctx['story_subject'],ctx['is_story']=self.get_user_subject(request.user)
        ctx['exams']=self.get_exams(request)
        ctx['folders']=UserFolder.objects.filter(user=request.user)
        ctx["html_head"] = self.html_head()
        ctx['countries']=country
        ctx['colleges'] = College.get_all_colleges()
        return ctx

    def get_user_subject(self,user):
        now=timezone.now()
        prf=UserProfile.objects.filter(user=user).first()
        if prf:
            subject_id=prf.subject.all().values_list("id",flat=True)
            is_story = Stories.objects.filter(obj_id__in=subject_id,obj_type=choices.StoryObjectType.SUBJECT,start_date__lte=now,end_date__gte=now).exists()
            return prf.subject.all(),is_story
        return None,None
            

    def get_exams(self, request):
        try:
            return EntranceExamDocumentFilter().get_elasticsearch_document_entrance_exam_all(request, stream=None, name=None, is_ajax=None).execute()
        except Exception as e:
            # Log the error or print it out for debugging
            print(f"Error fetching exams: {e}")
            # Handle the error gracefully, maybe return an empty list or a default value
            return []

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))

class Welcomepage(TemplateView):
    template_name="template20/user/welcome.html"

    def html_head(self):
        name='Welcome'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class Scrapbook(TemplateView):
    template_name="template20/user/scrapbook.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'scrapbook','url':''}]
        return get_breadcrumb(l)

    def html_head(self):
        name='My Scrapbook'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class MyNotePad(TemplateView):
    template_name="template20/user/my_notepad.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'Scrapbook','url':reverse_lazy('users:scrapbook')},{'title':'My Notepad','text':'My Notepad','url':''}]
        return get_breadcrumb(l)

    def html_head(self):
        name='My Notepad'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        ctx['notes'] = _meaningful_user_notes_qs(request.user)
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class CreateNote(TemplateView):
    template_name="template20/user/create_note.html"

    def html_head(self):
        name='Add Note'
        return build_html_head(title=name, description=name)

    def get_context(self,request,id,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        if id:
            note=get_object_or_404(UserNote,id=id,user=request.user)
        else:
            note = UserNote.objects.filter(user=request.user,title__isnull=True,content__isnull=True)
            if note.exists():
                note=note.last()
            else:
                note=UserNote.objects.create(user=request.user)
        ctx['note']=note
        return ctx

    def get(self, request,id=None,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request, id,*args, **kwargs))

    def post(self, request, id=None, *args, **kwargs):
        """
        Save note and redirect to My Notepad.
        """
        obj_id = (request.POST.get("obj_id") or "").strip()
        title = (request.POST.get("title") or "").strip()
        content = (request.POST.get("content") or "").strip()

        # Prefer POST obj_id, then URL id, else create a new draft note
        note = None
        if obj_id:
            note = get_object_or_404(UserNote, id=obj_id, user=request.user)
        elif id:
            note = get_object_or_404(UserNote, id=id, user=request.user)
        else:
            note = UserNote.objects.create(user=request.user)

        note.title = title
        note.content = content
        if not _note_has_meaningful_content(note.title, note.content):
            note.delete()
        else:
            note.save()
        return redirect(reverse_lazy("users:mynotepad"))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserHobbies(TemplateView):
    template_name="template20/user/my_hobbies.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'Scrapbook','url':reverse_lazy('users:scrapbook')},{'title':'My Hobbies','text':'My Hobbies','url':''}]
        return get_breadcrumb(l)

    def html_head(self):
        name='My Hobbies'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        ctx['all_hobbies'] = list(Hobbies.objects.all())
        # Pre-evaluate hobbies for Jinja2 template
        try:
            if hasattr(request.user, 'user_profile') and request.user.user_profile:
                hobbies_qs = request.user.user_profile.hobbies.all()
                ctx['hobbies'] = list(hobbies_qs) if hobbies_qs.exists() else []
            else:
                ctx['hobbies'] = []
        except Exception as e:
            ctx['hobbies'] = []
        ctx['user_hobby_ids'] = {h.id for h in ctx['hobbies']}
        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,*args, **kwargs))
    
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserColleges(TemplateView):
    template_name="template20/user/bookmark_college.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'Scrapbook','url':reverse_lazy('users:scrapbook')},{'title':'My Colleges','text':'My Colleges','url':''}]
        return get_breadcrumb(l)

    def html_head(self):
        name='My Colleges'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        from colleges.models import CollegeShortlist
        ctx={}
        ctx["html_head"] = self.html_head()
        user_ids = _bookmark_owner_user_ids(request.user)
        # Get bookmarked colleges from CollegeShortlist for user + linked parents
        college_shortlists = CollegeShortlist.objects.filter(user_id__in=user_ids).select_related('college')
        colleges = []
        seen = set()
        for cs in college_shortlists:
            if cs.college_id and cs.college_id not in seen and cs.college:
                colleges.append(cs.college)
                seen.add(cs.college_id)
        ctx["colleges"] = colleges
        ctx['breadcrumb']=self.__breadcrumb()
        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,*args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class CareerInterests(TemplateView):
    template_name="template20/user/career_interests.html"


    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'Scrapbook','url':reverse_lazy('users:scrapbook')},{'title':'Career Interests','text':'Career Interests','url':''}]
        return get_breadcrumb(l)

    def html_head(self):
        name='Career Interests'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        # Use select_related to optimize query and ensure career data is loaded
        # Filter out any career_shortlists where career is None
        user_ids = _bookmark_owner_user_ids(request.user)
        from careers.models import CareerShortlist
        career_interests_qs = CareerShortlist.objects.filter(
            user_id__in=user_ids,
            career__isnull=False
        ).select_related('career')
        # Convert to list to ensure queryset is evaluated for Jinja2 template
        career_interests_list = list(career_interests_qs)
        ctx['career_interests'] = career_interests_list
        # Get career IDs for cluster filtering - filter out None values
        ids = [ci.career_id for ci in career_interests_list if ci and ci.career and ci.career_id]
        if ids:
            clstrs = CareerCluster.objects.filter(career_clusters__in=ids).distinct()
        else:
            clstrs = CareerCluster.objects.none()
        ctx['career_ids'] = ids
        ctx['clstrs'] = clstrs
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class SaveMedia(TemplateView):
    template_name="template20/user/save_media.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'Scrapbook','url':reverse_lazy('users:scrapbook')},{'title':'Saved Media','text':'Save Media','url':''}]
        return get_breadcrumb(l)

    def html_head(self):
        name='Save Media'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


def _resume_section_count(ur):
    if not ur:
        return 0
    return (
        (1 if (ur.about or "").strip() else 0)
        + UserResumeSkill.objects.filter(resume=ur).count()
        + UserResumeCertificate.objects.filter(resume=ur).count()
        + UserResumeInternship.objects.filter(resume=ur).count()
        + UserResumeActivity.objects.filter(resume=ur).count()
        + UserResumeVolunteerInvolvement.objects.filter(resume=ur).count()
    )


RESUME_TITLE_MIN_LEN = 2
RESUME_TITLE_MAX_LEN = 120


def _validate_new_resume_title(user, title):
    """Return an error message, or None when title is valid for a new resume."""
    if not title:
        return "Please enter a name for your resume."
    if len(title) < RESUME_TITLE_MIN_LEN:
        return f"Resume name must be at least {RESUME_TITLE_MIN_LEN} characters."
    if len(title) > RESUME_TITLE_MAX_LEN:
        return f"Resume name must be {RESUME_TITLE_MAX_LEN} characters or fewer."
    lowered = title.casefold()
    for existing in UserResume.objects.filter(user=user).values_list("title", flat=True):
        if (existing or "").strip().casefold() == lowered:
            return "You already have a resume with this name. Please choose a different name."
    return None


def _note_has_meaningful_content(title, content):
    """True when a note has a non-empty title or body (ignores blank HTML drafts)."""
    from django.utils.html import strip_tags

    if (title or "").strip():
        return True
    body = strip_tags(content or "").replace("\xa0", " ").strip()
    return bool(body)


def _meaningful_user_notes_qs(user):
    """Active notes with content; excludes empty drafts left from Create note."""
    candidates = UserNote.objects.filter(user=user).order_by("-modified")
    return [note for note in candidates if _note_has_meaningful_content(note.title, note.content)]


def _hub_nav_counts(user):
    """Sidebar badge counts (mirrors UserDashboard resume/shortlist/notes slice)."""
    ctx = {
        "hub_shortlist_count": 0,
        "hub_resume_exists": False,
        "hub_resume_sections": 0,
        "hub_resume_count": 0,
        "hub_application_count": 0,
        "hub_notes_count": 0,
    }
    try:
        ctx["hub_shortlist_count"] = CollegeShortlist.objects.filter(user=user).count()
    except Exception:
        pass
    try:
        resumes = list(UserResume.objects.filter(user=user))
        ctx["hub_resume_count"] = len(resumes)
        ctx["hub_resume_exists"] = len(resumes) > 0
        ctx["hub_resume_sections"] = sum(_resume_section_count(ur) for ur in resumes)
    except Exception:
        pass
    try:
        ctx["hub_notes_count"] = len(_meaningful_user_notes_qs(user))
    except Exception:
        pass
    return ctx


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class MyResumesHubView(TemplateView):
    """Lists all resumes for the account; links to Resume studio and classic editor."""

    template_name = "template20/user/my_resumes.html"

    def __breadcrumb(self):
        l = [
            {"title": "Profile page", "text": "Profile page", "url": reverse_lazy("users:userdashboard")},
            {"title": "My resumes", "text": "My resumes", "url": reverse_lazy("users:resume_v2_dashboard")},
            {"title": "Classic backup", "text": "Classic backup", "url": ""},
        ]
        return get_breadcrumb(l)

    def html_head(self):
        name = "My resumes"
        return build_html_head(title=name, description=name)

    def get_context(self, request, *args, **kwargs):
        ctx = {}
        ctx["html_head"] = self.html_head()
        ctx["breadcrumb"] = self.__breadcrumb()
        profile_user = request.user
        ctx["profile_user"] = profile_user
        UserProfile.objects.get_or_create(user=profile_user)
        ctx.update(_hub_nav_counts(profile_user))
        resumes = list(UserResume.objects.filter(user=profile_user).order_by("-modified"))
        ctx["resumes"] = resumes
        ctx["resume_rows"] = [{"resume": r, "sections": _resume_section_count(r)} for r in resumes]
        ctx["draft_title"] = (request.GET.get("draft_title") or "")[:RESUME_TITLE_MAX_LEN]
        ctx["existing_resume_titles"] = [(r.title or "").strip() for r in resumes if (r.title or "").strip()]
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class ResumeHubCreateView(View):
    """POST: create a new UserResume; optional ?next=studio|edit (default studio)."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        title = (request.POST.get("title") or "").strip()[:RESUME_TITLE_MAX_LEN]
        title_error = _validate_new_resume_title(request.user, title)
        if title_error:
            messages.error(request, title_error)
            from urllib.parse import urlencode

            return redirect(f"{reverse('users:resumebuilder_classic')}?{urlencode({'draft_title': title})}")
        nxt = (request.POST.get("next") or "studio").strip().lower()
        resume = UserResume.objects.create(user=request.user, title=title)
        from .resume_profile_store import bootstrap_user_resume_from_profile

        bootstrap_user_resume_from_profile(request.user, resume)
        messages.success(request, "Resume created.")
        if nxt == "edit":
            return redirect("users:resumebuilder_edit", resume_id=resume.pk)
        return redirect("users:resume_v2_goal", resume_id=resume.pk)


def _duplicate_user_resume_children(source_resume, new_resume):
    """Copy active section rows from source_resume onto new_resume (same user)."""
    for s in UserResumeSkill.objects.filter(resume=source_resume):
        UserResumeSkill.objects.create(
            resume=new_resume,
            title=s.title,
            description=s.description,
            profficiency=s.profficiency,
        )
    for c in UserResumeCertificate.objects.filter(resume=source_resume):
        UserResumeCertificate.objects.create(
            resume=new_resume,
            title=c.title,
            description=c.description,
            issue_date=c.issue_date,
        )
    for i in UserResumeInternship.objects.filter(resume=source_resume):
        UserResumeInternship.objects.create(
            resume=new_resume,
            provider=i.provider,
            role=i.role,
            description=i.description,
            start_date=i.start_date,
            end_date=i.end_date,
        )
    for a in UserResumeActivity.objects.filter(resume=source_resume):
        UserResumeActivity.objects.create(
            resume=new_resume,
            title=a.title,
            description=a.description,
            issue_date=a.issue_date,
        )
    for v in UserResumeVolunteerInvolvement.objects.filter(resume=source_resume):
        UserResumeVolunteerInvolvement.objects.create(
            resume=new_resume,
            title=v.title,
            role=v.role,
            description=v.description,
            start_date=v.start_date,
            end_date=v.end_date,
        )


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class ResumeHubDuplicateView(View):
    """POST: duplicate this UserResume (DB-backed sections + studio fields) as a new row."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        from django.db import transaction

        rid = request.POST.get("resume_id")
        try:
            pk = int(rid)
        except (TypeError, ValueError):
            messages.error(request, "Invalid resume.")
            return redirect("users:resume_v2_dashboard")
        src = UserResume.objects.filter(pk=pk, user=request.user).first()
        if not src:
            messages.error(request, "Resume not found.")
            return redirect("users:resume_v2_dashboard")
        title = (request.POST.get("title") or "").strip()[:120]
        raw_snap = (request.POST.get("studio_snapshot_json") or "").strip()
        if raw_snap:
            try:
                snap = json.loads(raw_snap)
            except (json.JSONDecodeError, TypeError, ValueError):
                snap = None
            if isinstance(snap, dict) and isinstance(snap.get("resume"), dict):
                rd = snap["resume"]
                if not title:
                    th = (rd.get("headline") or "").strip()[:100]
                    base = th or (src.title or "My resume").strip()[:100]
                    title = f"{base} (copy)"[:120]
                pack = {
                    "resume": rd,
                    "template": (snap.get("template") or "")[:80],
                    "color": (snap.get("color") or "")[:40],
                    "font": (snap.get("font") or "")[:240],
                    "textAlign": (snap.get("textAlign") or "")[:20],
                }
                wiz_out = json.dumps({STUDIO_PROTO_V1_KEY: pack}, ensure_ascii=False, default=str)
                about = (rd.get("summary") or "").strip()[:10000] or (src.about or "")
                gen_html = studio_v1_pack_to_generated_html(pack)
                with transaction.atomic():
                    nr = UserResume.objects.create(
                        user=request.user,
                        title=title,
                        about=about,
                        generated_html=gen_html,
                        wizard_draft_json=wiz_out,
                    )
                    apply_studio_resume_to_userresume_children(nr, rd)
                messages.success(
                    request,
                    "Saved a new copy with your studio layout and content.",
                )
                return redirect("users:resume_v2_studio", resume_id=nr.pk)

        if not title:
            base = (src.title or "My resume").strip()[:100]
            title = f"{base} (copy)"[:120]

        with transaction.atomic():
            nr = UserResume.objects.create(
                user=request.user,
                title=title,
                about=src.about,
                generated_html=src.generated_html,
                wizard_draft_json=src.wizard_draft_json,
            )
            _duplicate_user_resume_children(src, nr)
        messages.success(request, "Saved a fresh copy of your resume. You can edit it below.")
        return redirect("users:resume_v2_studio", resume_id=nr.pk)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class ResumeHubDeleteView(View):
    """POST: permanently remove one resume (resume_id) and its sections."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        rid = request.POST.get("resume_id")
        try:
            pk = int(rid)
        except (TypeError, ValueError):
            messages.error(request, "Invalid resume.")
            return redirect("users:resume_v2_dashboard")
        resume = UserResume.objects.filter(pk=pk, user=request.user).first()
        if resume:
            resume.delete(hard_delete=True)
            messages.success(request, "That resume was deleted.")
        else:
            messages.info(request, "Resume not found.")
        return redirect("users:resume_v2_dashboard")


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class ResumeBuilderEditView(TemplateView):
    """Classic section-based resume editor (skills, certificates, etc.)."""

    template_name = "template20/user/resume_builder.html"

    def __breadcrumb(self, resume):
        l = [
            {"title": "Profile page", "text": "Profile page", "url": reverse_lazy("users:userdashboard")},
            {"title": "My resumes", "text": "My resumes", "url": reverse_lazy("users:resume_v2_dashboard")},
            {
                "title": "Edit resume",
                "text": resume.title or "Edit resume",
                "url": "",
            },
        ]
        return get_breadcrumb(l)

    def html_head(self, resume):
        name = resume.title or "Edit resume"
        return build_html_head(title=name, description=name)

    def get_context(self, request, resume_id, *args, **kwargs):
        ctx = {}
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        ctx["html_head"] = self.html_head(resume)
        ctx["breadcrumb"] = self.__breadcrumb(resume)
        ctx["profile_user"] = request.user
        ctx["resume"] = resume
        ctx.update(_hub_nav_counts(request.user))
        ctx["resumeskill"] = UserResumeSkill.objects.filter(resume=resume)
        ctx["resumecertificate"] = UserResumeCertificate.objects.filter(resume=resume)
        ctx["resumeinternship"] = UserResumeInternship.objects.filter(resume=resume)
        ctx["resumeactivity"] = UserResumeActivity.objects.filter(resume=resume)
        ctx["resumevolunteer"] = UserResumeVolunteerInvolvement.objects.filter(resume=resume)
        ctx["resume_editor_payload"] = _resume_editor_payload(resume)
        return ctx

    def get(self, request, resume_id, *args, **kwargs):
        return render(
            request,
            self.template_name,
            self.get_context(request, resume_id, *args, **kwargs),
        )


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeGeneratedPreviewView(TemplateView):
    """Read-only HTML preview of the AI-generated resume (same tab / new tab)."""

    template_name = "template20/user/resume_generated_preview.html"

    def html_head(self, resume):
        return build_html_head(
            title=resume.title or "Resume preview",
            description="Preview generated resume",
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        resume = get_object_or_404(
            UserResume, pk=self.kwargs["resume_id"], user=self.request.user
        )
        ctx["html_head"] = self.html_head(resume)
        ctx["resume"] = resume
        ctx["profile_user"] = self.request.user
        ctx.update(_hub_nav_counts(self.request.user))
        if wizard_prefers_generated_pdf(resume):
            ctx["resume_html_display"] = strip_markdown_fences(resume.generated_html or "")
        elif studio_proto_pack_from_resume(resume):
            mount_html, template_id, studio_pack = studio_render_html_for_resume(resume, self.request)
            ctx["resume_html_display"] = get_template(
                "mail/user/userresumepdf_studio_prototype.html"
            ).render(studio_pdf_template_context(mount_html, template_id, studio_pack))
        else:
            ctx["resume_html_display"] = strip_markdown_fences(resume.generated_html or "")
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeStudioSetupView(TemplateView):
    """AdmitCV-style guided resume studio for a specific UserResume row."""

    template_name = "template20/user/resume_studio_setup.html"

    def html_head(self, resume):
        name = "Resume studio"
        return build_html_head(title=name, description=name)

    def get_context(self, request, resume_id, *args, **kwargs):
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        ctx = {}
        ctx["html_head"] = self.html_head(resume)
        profile = getattr(request.user, "user_profile", None)
        ctx["resume"] = resume
        ctx["profile_user"] = request.user
        UserProfile.objects.get_or_create(user=request.user)
        ctx.update(_hub_nav_counts(request.user))
        ctx["admitcv_prefill"] = {
            "name": (request.user.name or "")[:200],
            "email": (request.user.email or "")[:200],
            "phone": str(getattr(request.user, "mobile", "") or "")[:80],
            "country": "",
            "school": (profile.schoolname or "")[:300] if profile else "",
            "grade": (profile.grade or "")[:120] if profile else "",
        }
        ctx["wizard_restore_json"] = json.dumps(
            prepare_admitcv_wizard_restore(resume, request),
            ensure_ascii=False,
            default=str,
        )
        from users.resume_studio_html import studio_html_template_catalog_rows

        rows = studio_html_template_catalog_rows()
        ctx["admitcv_studio_template_catalog"] = rows
        ctx["resume_has_generated"] = bool((resume.generated_html or "").strip())
        # Real mini previews for Step-6 tiles (server render, then scale down in CSS).
        try:
            from users.resume_studio_html import ADMIN_STUDIO_HTML_PREVIEW_SAMPLE
            from users.resume_studio_pdf_html import studio_proto_pack_to_mount_html
            from users.resume_payload import DEFAULT_STUDIO_EMBED_FONT

            previews = []
            for r in rows:
                tid = (r.get("id") or "").strip().lower()
                if not tid:
                    continue
                pack = {
                    "resume": ADMIN_STUDIO_HTML_PREVIEW_SAMPLE,
                    "template": tid,
                    "color": "teal",
                    "font": DEFAULT_STUDIO_EMBED_FONT,
                    "textAlign": "start",
                }
                mount_html, _ = studio_proto_pack_to_mount_html(pack)
                previews.append({"id": tid, "html": mount_html})
            ctx["admitcv_studio_template_previews"] = previews
        except Exception:
            ctx["admitcv_studio_template_previews"] = []
        return ctx

    def get(self, request, resume_id, *args, **kwargs):
        return render(
            request,
            self.template_name,
            self.get_context(request, resume_id, *args, **kwargs),
        )


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeGuidedGenerateView(View):
    """POST JSON { draft, resume_id?, studio_template_id? } — AI HTML + optional studio RESUME_DATA merge."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        import json

        from django.db import transaction

        from users.resume_guided_ai import (
            build_plain_resume_summary_py,
            extract_resume_data_json,
            generate_resume_raw,
            sanitize_draft,
            split_generated_html,
            sync_user_fields_from_wizard,
        )
        from users.resume_payload import (
            DEFAULT_STUDIO_EMBED_FONT,
            STUDIO_PROTO_V1_KEY,
            WIZARD_PREFER_GENERATED_PDF_KEY,
            apply_studio_resume_to_userresume_children,
            guided_wizard_payload_for_studio,
            merge_studio_resume_ai_overlay,
            studio_v1_pack_to_generated_html,
        )
        from users.resume_studio_pdf_html import studio_proto_pack_to_mount_html
        from users.resume_studio_html import ALLOWED_STUDIO_HTML_TEMPLATE_KEYS

        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        raw_draft = body.get("draft")
        if not isinstance(raw_draft, dict):
            return JsonResponse({"error": 'Missing or invalid "draft" object'}, status=400)

        try:
            draft = sanitize_draft(raw_draft)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        st_raw = body.get("studio_template_id")
        studio_tid = str(st_raw).strip().lower() if st_raw not in (None, "", b"") else ""
        if studio_tid and studio_tid not in ALLOWED_STUDIO_HTML_TEMPLATE_KEYS:
            studio_tid = ""

        raw, err = generate_resume_raw(draft, studio_template_id=studio_tid or None)
        if err:
            logger.warning("resume_guided_generate failed: %s", err[:500])
            return JsonResponse({"error": err}, status=503)

        html_clean = split_generated_html(raw)
        rd_raw = extract_resume_data_json(raw)
        rid = body.get("resume_id")
        client_preview = html_clean
        pk = None
        if rid not in (None, "", b""):
            try:
                pk = int(rid)
            except (TypeError, ValueError):
                pk = None
            if pk:
                try:
                    with transaction.atomic():
                        ur = get_object_or_404(
                            UserResume.objects.select_for_update(),
                            pk=pk,
                            user=request.user,
                        )
                        plain = build_plain_resume_summary_py(draft)
                        fallback_resume = guided_wizard_payload_for_studio(ur, request, draft)
                        merged_resume = merge_studio_resume_ai_overlay(
                            fallback_resume,
                            rd_raw if isinstance(rd_raw, dict) else None,
                        )
                        has_pack_content = bool(
                            merged_resume
                            and (
                                (merged_resume.get("fullName") or "").strip()
                                or (merged_resume.get("headline") or "").strip()
                                or (merged_resume.get("summary") or "").strip()
                                or (merged_resume.get("experience") or [])
                                or (merged_resume.get("education") or [])
                                or (merged_resume.get("skills") or [])
                            )
                        )
                        pack = None
                        if has_pack_content:
                            pack = {
                                "resume": merged_resume,
                                "template": studio_tid or "classic-sidebar",
                                "color": "teal",
                                "font": DEFAULT_STUDIO_EMBED_FONT,
                                "textAlign": "start",
                            }
                        draft_save = dict(draft)
                        if pack:
                            draft_save[STUDIO_PROTO_V1_KEY] = pack
                            apply_studio_resume_to_userresume_children(ur, pack["resume"])
                        if studio_tid and pack:
                            # Use the same renderer as the template library / PDF so the generated preview
                            # matches the selected layout (e.g. Tech Focus).
                            mount_html, _template_id = studio_proto_pack_to_mount_html(pack)
                            ur.generated_html = mount_html
                            draft_save.pop(WIZARD_PREFER_GENERATED_PDF_KEY, None)
                        else:
                            ur.generated_html = html_clean
                            draft_save[WIZARD_PREFER_GENERATED_PDF_KEY] = True
                        # Gate UI behavior: allow skipping steps once generated at least once.
                        draft_save["generated_once"] = True
                        ur.about = plain
                        ur.wizard_draft_json = json.dumps(
                            draft_save, ensure_ascii=False, default=str
                        )
                        ur.save(
                            update_fields=[
                                "generated_html",
                                "about",
                                "wizard_draft_json",
                                "modified",
                            ]
                        )
                        client_preview = (ur.generated_html or html_clean).strip() or html_clean
                        sync_user_fields_from_wizard(request.user, draft)
                except Exception as exc:
                    logger.exception("resume persist after generate failed: %s", exc)
                    return JsonResponse({"error": "Could not save resume to your account."}, status=500)

        return JsonResponse({"html": raw, "preview_html": client_preview})


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserFolders(TemplateView):
    template_name="template20/user/user_folder.html"
    
    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'Scrapbook','url':reverse_lazy('users:scrapbook')},{'title':'My Folder','text':'My Folder','url':''}]
        return get_breadcrumb(l)

    def html_head(self):
        name='My Folder'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        ctx['folders']=UserFolder.objects.filter(user=request.user)
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserFolderDetail(TemplateView):
    template_name="template20/user/folder_files.html"

    def __breadcrumb(self,folder):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'Scrapbook','url':reverse_lazy('users:scrapbook')},{'title':'Folders','text':'Folders','url':reverse_lazy('users:userfolders')},{'title':folder.title,'text':folder.title,'url':''}]
        return get_breadcrumb(l)

    def html_head(self,folder):
        name=folder.title
        return build_html_head(title=name, description=name)

    def get_context(self,request,id,*args,**kwargs):
        ctx={}
        folder=get_object_or_404(UserFolder,id=id,user=request.user)
        ctx["html_head"] = self.html_head(folder)
        ctx['breadcrumb']=self.__breadcrumb(folder)
        ctx['folder']=folder
        return ctx

    def get(self, request,id,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request, id,*args, **kwargs))


AI_DYNAMIC_GENERATED_SHELL = "mail/user/userresumepdf_gen_ai_dynamic_shell.html"


def _ai_shell_ctx_from_row(row):
    from users.resume_template_ai import google_font_context_for_template

    if not row:
        return {
            "ai_dynamic_css": "",
            "use_ai_dynamic_shell": False,
            "ai_google_font_url": "",
            "ai_google_font_stack": "",
        }
    css = (getattr(row, "ai_dynamic_css", None) or "").strip()
    use = bool(css)
    ctx = {"ai_dynamic_css": css if use else "", "use_ai_dynamic_shell": use}
    if use:
        ctx.update(google_font_context_for_template(row))
    else:
        ctx["ai_google_font_url"] = ""
        ctx["ai_google_font_stack"] = ""
    return ctx


def _choose_generated_mail_template(row, generated_path):
    if row and (getattr(row, "ai_dynamic_css", None) or "").strip():
        return AI_DYNAMIC_GENERATED_SHELL, AI_DYNAMIC_GENERATED_SHELL
    return generated_path, "mail/user/userresumepdf_generated.html"


def _resume_pdf_template_row_paths_and_style(
    user_resume,
    preview_template_id=None,
    force_template_row=None,
    restrict_template_user=None,
):
    """Return fixed PDF mail template paths and default layout/accent (no DB template rows)."""
    return (
        None,
        "mail/user/userresumepdf.html",
        "mail/user/userresumepdf_generated.html",
        "v01",
        "#19718c",
    )


@login_required
def resume_pdf_download(request, *args, **kwargs):
    rid = request.GET.get("resume_id")
    qs = UserResume.objects.filter(user=request.user)
    if rid:
        try:
            user_resume = get_object_or_404(qs, pk=int(rid))
        except ValueError:
            user_resume = None
    else:
        user_resume = qs.order_by("-modified").first()
    if not user_resume:
        messages.info(request, "Create or pick a resume before downloading a PDF.")
        return redirect("users:resume_v2_dashboard")

    from users.resume_pdf_service import resume_pdf_response

    preview_tid = (request.GET.get("template_id") or "").strip() or None
    inline_param = (request.GET.get("inline") or "").strip().lower()
    # Default: open in browser (inline). Pass inline=0 for attachment download.
    inline = inline_param not in ("0", "false", "no", "attachment")
    try:
        return resume_pdf_response(
            user_resume,
            request,
            inline=inline,
            preview_template_id=preview_tid,
        )
    except Exception:
        logger.exception("resume_pdf_download failed for resume_id=%s", user_resume.pk)
        messages.error(request, "Could not generate your PDF. Please try again in a moment.")
        return redirect("users:resume_v2_studio", resume_id=user_resume.pk)


@login_required
def resume_html_preview(request, *args, **kwargs):
    """Same render as PDF but HTML for iframe preview (template library)."""
    rid = request.GET.get("resume_id")
    qs = UserResume.objects.filter(user=request.user)
    if rid:
        try:
            user_resume = get_object_or_404(qs, pk=int(rid))
        except ValueError:
            user_resume = None
    else:
        user_resume = qs.order_by("-modified").first()
    if not user_resume:
        return HttpResponse("<p>Resume not found.</p>", status=404)
    preview_tid = request.GET.get("template_id")
    _tpl_row, classic_path, generated_path, pdf_lv, pdf_ac = _resume_pdf_template_row_paths_and_style(
        user_resume, preview_template_id=preview_tid, restrict_template_user=request.user
    )
    ctx = {
        "request": request,
        "profile": get_object_or_404(UserProfile, user=request.user),
        "user_resume": user_resume,
        "skills": UserResumeSkill.objects.filter(resume=user_resume),
        "certificates": UserResumeCertificate.objects.filter(resume=user_resume).order_by("issue_date"),
        "internships": UserResumeInternship.objects.filter(resume=user_resume),
        "activities": UserResumeActivity.objects.filter(resume=user_resume),
        "volunteers": UserResumeVolunteerInvolvement.objects.filter(resume=user_resume),
        "resume_contact": resume_studio_prototype_payload(user_resume, request),
        "pdf_layout_variant": pdf_lv,
        "pdf_accent_color": pdf_ac,
    }
    ctx.update(_ai_shell_ctx_from_row(_tpl_row))
    user_image = getattr(request.user, "image", None)
    if user_image:
        try:
            ctx["image_url"] = "https://www.topteen.in{}".format(user_image.url)
        except ValueError:
            ctx["image_url"] = ""
    else:
        ctx["image_url"] = ""
    from django.template import TemplateDoesNotExist

    studio_pack = (
        None
        if wizard_prefers_generated_pdf(user_resume)
        else studio_proto_pack_from_resume(user_resume)
    )
    if studio_pack:
        try:
            from users.resume_v2_services import sync_studio_proto_resume_from_db

            sync_studio_proto_resume_from_db(user_resume, request)
        except Exception:
            pass
        mount_html, template_id, studio_pack = studio_render_html_for_resume(
            user_resume,
            request,
            template_override=(preview_tid or None),
        )
        ctx.update(studio_pdf_template_context(mount_html, template_id, studio_pack))
        ctx["generated_resume_html"] = mount_html
        chosen = "mail/user/userresumepdf_studio_prototype.html"
        fallback = "mail/user/userresumepdf_studio_prototype.html"
    elif (user_resume.generated_html or "").strip():
        ctx["generated_resume_html"] = strip_markdown_fences(user_resume.generated_html)
        chosen, fallback = _choose_generated_mail_template(_tpl_row, generated_path)
    else:
        chosen = classic_path
        fallback = "mail/user/userresumepdf.html"
    try:
        template = get_template(chosen)
    except TemplateDoesNotExist:
        template = get_template(fallback)
    html = template.render(ctx)
    return HttpResponse(html, content_type="text/html; charset=utf-8")


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeTemplateLibraryView(TemplateView):
    """Screen 2–style template picker: library grid, live preview, apply layout to this resume."""

    template_name = "template20/user/resume_template_library.html"

    def html_head(self, resume):
        return build_html_head(title="Resume templates", description="Choose a PDF layout for your resume.")

    def get_context(self, request, resume_id, *args, **kwargs):
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        ctx = {}
        ctx["html_head"] = self.html_head(resume)
        ctx["resume"] = resume
        ctx["profile_user"] = request.user
        UserProfile.objects.get_or_create(user=request.user)
        ctx.update(_hub_nav_counts(request.user))
        # Template gallery is the static resume-builder prototype (no DB PDF template rows).
        ctx["library_templates"] = []
        ctx["library_templates_catalog"] = []
        ctx["library_templates_catalog_json"] = mark_safe("[]")
        return ctx

    def get(self, request, resume_id, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, resume_id, *args, **kwargs))


@method_decorator(ensure_csrf_cookie, name="dispatch")
@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeTemplateStudioEmbedView(View):
    """Minimal HTML document for iframe: resume-builder prototype + DB-backed initial data."""

    http_method_names = ["get"]

    def get(self, request, resume_id, *args, **kwargs):
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        if ensure_studio_proto_v1_defaults_saved(resume, request):
            resume.refresh_from_db()
        payload = resume_studio_prototype_payload(resume, request, ignore_studio_proto_merge=True)
        raw = json.dumps(payload, ensure_ascii=False, default=str).translate(
            str.maketrans({"<": "\\u003c", ">": "\\u003e"})
        )
        finish, pdf_url = resume_studio_embed_finish_pdf_urls(request, resume)
        force_tpl = (request.GET.get("template") or "").strip()
        mode = (request.GET.get("mode") or "").strip()
        use_server_preview = mode == "preview" and studio_proto_pack_from_resume(resume)
        studio_server_mount_html = ""
        studio_server_template_id = ""
        studio_root_style = ""
        if use_server_preview:
            mount_html, template_id, pack = studio_render_html_for_resume(
                resume, request, template_override=force_tpl or None
            )
            studio_server_mount_html = mount_html
            studio_server_template_id = template_id
            studio_root_style = studio_pack_root_css_block(pack)
        ctx = {
            "resume": resume,
            "resume_initial_json": mark_safe(raw),
            "studio_prefs_initial_json": mark_safe(json.dumps(studio_prefs_from_resume_record(resume))),
            "storage_key": f"resume-builder-proto-{resume.pk}",
            "finish_url": finish,
            "pdf_download_url": pdf_url,
            "studio_edit_url": reverse("users:resume_v2_studio", kwargs={"resume_id": resume.pk}),
            "preview_back_url": reverse("users:resume_v2_dashboard"),
            "duplicate_resume_url": reverse("users:resumebuilder_duplicate"),
            "studio_templates_catalog_json": studio_html_template_catalog_json(),
            "studio_force_template": force_tpl,
            "studio_template_row": None,
            "use_server_preview": use_server_preview,
            "studio_server_mount_html": mark_safe(studio_server_mount_html),
            "studio_server_template_id": studio_server_template_id,
            "studio_root_style": mark_safe(studio_root_style),
        }
        return render(request, "template20/user/resume_builder_prototype_embed.html", ctx)


@method_decorator(ensure_csrf_cookie, name="dispatch")
@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
class ResumeStudioPhotoUploadView(View):
    """POST multipart {photo=<file>} → store on UserResume.image; DELETE clears resume photo."""

    http_method_names = ["post", "delete"]

    def post(self, request, resume_id, *args, **kwargs):
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        f = request.FILES.get("photo")
        if not f:
            return JsonResponse({"error": "Missing photo file"}, status=400)
        # Basic sanity checks (content type + size).
        ctype = (getattr(f, "content_type", "") or "").lower()
        if ctype and not ctype.startswith("image/"):
            return JsonResponse({"error": "Only image uploads are supported."}, status=400)
        try:
            max_mb = int(getattr(settings, "S3_MAX_FILE_SIZE_MB", 2) or 2)
        except Exception:
            max_mb = 2
        if getattr(f, "size", 0) and f.size > max_mb * 1024 * 1024:
            return JsonResponse({"error": f"Image too large (max {max_mb}MB)."}, status=413)

        from .resume_v2_services import save_v2_meta

        save_v2_meta(resume, {"hide_resume_photo": False})
        resume.image = f
        resume.save(update_fields=["image", "modified"])
        try:
            from .resume_v2_services import resume_photo_url, sync_studio_proto_resume_from_db

            sync_studio_proto_resume_from_db(resume, request)
            abs_url = resume_photo_url(request, resume, request.user)
        except Exception:
            abs_url = ""
        return JsonResponse({"ok": True, "url": abs_url})

    def delete(self, request, resume_id, *args, **kwargs):
        resume = get_object_or_404(UserResume, pk=resume_id, user=request.user)
        from .resume_v2_services import resume_photo_url, save_v2_meta, sync_studio_proto_resume_from_db

        if resume.image:
            try:
                resume.image.delete(save=False)
            except Exception:
                pass
        resume.image = None
        resume.save(update_fields=["image", "modified"])
        save_v2_meta(resume, {"hide_resume_photo": True})
        try:
            sync_studio_proto_resume_from_db(resume, request)
        except Exception:
            pass
        return JsonResponse({"ok": True, "url": "", "removed": True})


@staff_member_required
def admin_resume_studio_html_template_preview(request, template_pk):
    """Staff: open the HTML resume studio with sample data and this layout selected (same prototype as students)."""
    tpl = get_object_or_404(ResumeStudioHtmlTemplate.objects.complete(), pk=template_pk)
    ctx = {
        "resume": None,
        "resume_initial_json": admin_studio_html_preview_initial_json(),
        "studio_prefs_initial_json": mark_safe(json.dumps({})),
        "storage_key": f"admin-studio-html-{tpl.pk}",
        "finish_url": "",
        "duplicate_resume_url": reverse("users:resumebuilder_duplicate"),
        "studio_templates_catalog_json": studio_html_template_catalog_json(),
        "studio_force_template": tpl.template_key,
        "studio_template_row": tpl,
    }
    return render(request, "template20/user/resume_builder_prototype_embed.html", ctx)


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserCalenderView(TemplateView):
    template_name="template20/user/user_calendar.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Calender','text':'calender','url':''}]
        return get_breadcrumb(l)

    def html_head(self):
        name="Event Calender"
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        calender=UserCalender.objects.filter(user=request.user)
        ctx['events']=calender
        ctx['breadcrumb']=self.__breadcrumb()
        return ctx

    def post(self,request,*args,**kwargs):
        event_name=request.POST.get("event_name")
        event_start=request.POST.get("event_start")
        event_end=request.POST.get("event_end")

        if event_name and event_start and event_end:
            if len(event_name) > 50:
                messages.error(request, "Event name must be 50 characters or fewer.")
                return render(request, self.template_name, self.get_context(request,*args, **kwargs))
            data=UserCalender(user=request.user,event_name=event_name,start_date=event_start,end_date=event_end)
            data.save()
        return render(request, self.template_name, self.get_context(request,*args, **kwargs))

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,*args, **kwargs))

@login_required
def UserEventDeleteView(request,id):
    event=get_object_or_404(UserCalender,id=id)
    event.delete()
    return redirect("/user/calender")

@login_required(login_url=reverse_lazy('users:login'))
def invoice_download(request, invoice_id):
    """Serve invoice PDF to the paying user only. ?view=1 opens in browser (inline), else download."""
    from invoices.models import Invoice
    from invoices.services import ensure_invoice_pdf
    invoice = get_object_or_404(Invoice, pk=invoice_id, payment__user=request.user)
    content, err = ensure_invoice_pdf(invoice)
    if content is None:
        raise Http404(err or 'Invoice PDF not available.')
    response = HttpResponse(content, content_type='application/pdf')
    filename = 'invoice-{}.pdf'.format(invoice.invoice_number or invoice_id)
    if request.GET.get('view'):
        response['Content-Disposition'] = 'inline; filename="{}"'.format(filename)
    else:
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
    return response


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserHistoryView(TemplateView):
    template_name="template20/user/user_history.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Payment History','text':'Payment History','url':''}]
        return get_breadcrumb(l)

    def html_head(self):
        name='Payment History'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        from payments.models import Payment
        from invoices.models import Invoice
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['payments'] = Payment.objects.filter(user=request.user).order_by('-created')
        ctx['payment_id_to_invoice_id'] = dict(
            Invoice.objects.filter(payment__user=request.user).values_list('payment_id', 'id')
        )
        ctx['breadcrumb']=self.__breadcrumb()
        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,*args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class Bookmark(TemplateView):
    template_name="template20/user/bookmark_list.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'My Bookmarks','text':'My Bookmarks','url':''}]
        return get_breadcrumb(l)

    def html_head(self):
        name='My Bookmarks'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))
    
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class BookmarkVideo(TemplateView):
    template_name="template20/user/bookmark_video.html"

    def __breadcrumb(self):
        l = [
            {"title": "Profile page", "text": "Profile page", "url": reverse_lazy("users:userdashboard")},
            {"title": "Scrapbook", "text": "Scrapbook", "url": reverse_lazy("users:scrapbook")},
            {"title": "My Videos", "text": "My Videos", "url": ""},
        ]
        return get_breadcrumb(l)

    def html_head(self):
        name='My Videos'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        user_ids = _bookmark_owner_user_ids(request.user)
        videos = Videos.objects.filter(shortlist__in=user_ids).distinct()
        ctx["html_head"] = self.html_head()
        ctx["videos"] = videos
        ctx['breadcrumb']=self.__breadcrumb()
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))
    
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class BookmarkExam(TemplateView):
    template_name="template20/user/bookmark_exam.html"

    def __breadcrumb(self):
        l = [
            {"title": "Profile page", "text": "Profile page", "url": reverse_lazy("users:userdashboard")},
            {"title": "Scrapbook", "text": "Scrapbook", "url": reverse_lazy("users:scrapbook")},
            {"title": "My exam", "text": "My exam", "url": ""},
        ]
        return get_breadcrumb(l)

    def html_head(self):
        name='My Exams'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        user_ids = _bookmark_owner_user_ids(request.user)
        exams = EntranceTestPrepExam.objects.filter(shortlist__in=user_ids, object_status=choices.ObjectStatus.ACTIVE).distinct().order_by("name")
        ctx["html_head"] = self.html_head()
        ctx["exams"] = exams
        ctx['breadcrumb']=self.__breadcrumb()
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class BookmarkCollege(TemplateView):
    template_name="template20/user/bookmark_college.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'My Bookmarks','text':'My Bookmarks','url':reverse_lazy('users:bookmark')},{'title':'My Colleges','text':'My Colleges','url':''}]
        return get_breadcrumb(l)

    def html_head(self):
        name='My Colleges'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        from colleges.models import CollegeShortlist
        ctx={}
        ctx["html_head"] = self.html_head()
        user_ids = _bookmark_owner_user_ids(request.user)
        # Get bookmarked colleges from CollegeShortlist for user + linked parents
        college_shortlists = CollegeShortlist.objects.filter(user_id__in=user_ids).select_related('college')
        # de-dupe colleges while keeping order
        colleges = []
        seen = set()
        for cs in college_shortlists:
            if cs.college_id and cs.college_id not in seen and cs.college:
                colleges.append(cs.college)
                seen.add(cs.college_id)
        ctx["colleges"] = colleges
        ctx['breadcrumb']=self.__breadcrumb()

        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class BookmarkBlog(TemplateView):
    template_name="template20/user/bookmark_blog.html"

    def __breadcrumb(self):
        l = [
            {"title": "Profile page", "text": "Profile page", "url": reverse_lazy("users:userdashboard")},
            {"title": "Scrapbook", "text": "Scrapbook", "url": reverse_lazy("users:scrapbook")},
            {"title": "My Blogs", "text": "My Blogs", "url": ""},
        ]
        return get_breadcrumb(l)

    def html_head(self):
        name='My Blogs'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        user_ids = _bookmark_owner_user_ids(request.user)
        try:
            from blog.models import BlogShortlist, Blog
            shortlisted = BlogShortlist.objects.filter(user_id__in=user_ids, blog__isnull=False).select_related('blog')
            blogs = []
            seen = set()
            for bs in shortlisted:
                if bs.blog_id and bs.blog_id not in seen and bs.blog:
                    blogs.append(bs.blog)
                    seen.add(bs.blog_id)
            # Keep only published blogs (safety)
            published_ids = set(Blog.get_published_objects().filter(id__in=list(seen)).values_list('id', flat=True))
            ctx["blogs"] = [b for b in blogs if b and b.id in published_ids]
        except Exception:
            ctx["blogs"] = []
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))
    
class ReferView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        email = (request.POST.get("email") or "").strip()
        if not email or not re.match(evalid, email):
            return JsonResponse({'success': "false", 'message': 'Please enter a valid email address.'})

        sent = send_referral_mail(request.user.id, email)
        if sent:
            return JsonResponse({'success': "true", 'message': 'Invitation sent successfully.'})
        return JsonResponse(
            {'success': "false", 'message': 'Unable to send invitation email. Please try again later.'},
            status=500,
        )