from datetime import datetime, timedelta
import json
from django.shortcuts import render
from rest_framework.views import APIView
from django.http import JsonResponse
from django.views.generic import TemplateView,View
from counselor.models import Counselor, FollowUpStatus
from counselor.views import (
    get_students_by_role,
    apply_student_filters,
    get_class_and_sections_by_role,
    get_class_counts,
    get_results_data_for_students,
    get_unique_streams_by_role,
    build_students_analytics_payload,
)
from users.models import User, UserProfile
from core import choices
from psychometric_tests.models import PsychometricTestResult,CentralTestCandidate
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from core.utils import build_html_head
from django.contrib import messages
from .task import send_new_student_credential,institute_deletion_request,create_student_and_send_mail,send_institute_mail
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from institute.decorators import change_counselor_password_only, institute_user_only,institute_authenticated_user_only,institute_block_student_only,institute_update_delete_student_only,institute_change_student_password_only,institute_profile_update_delete, marketing_group_user_only,only_superuser,institute_group_user_only,superuser_or_marketing_institute_create
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.views import View
from institute.task import update_student_data,create_institute_log,send_institute_group_mail
from institute.models import Institute,StudentManagement,InstituteAccountDeletion,ClassAndSection,InstituteLog,get_global_remain_credits,InstituteGroup,InstituteMarketingGroup
from django.conf import settings
from django.http import HttpResponse
from institute.filters import StudentFilter
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from app.models import Results, TestCompletion
from institute.utils import get_heatmap_data_for_group, get_heatmap_data_for_institute, get_empty_heatmap_data
# Dashboard template switch (v1/v2)
from core.models import Configuration
# Create your views here.

def _ttv2_week_start_from_request(request):
    """
    Parse ?ttv2_week_start=YYYY-MM-DD (Monday) into a date, or None.
    Used by template-v2 analytics to show a selected week range.
    """
    raw = (request.GET.get("ttv2_week_start") or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except Exception:
        return None


def user_manages_institute_for_api(user, institute):
    """
    True if the user may read institute/student API payloads for this institute.
    Scopes marketing, institute-group, school, and counselor roles to their own institutes.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if institute.created_by_id == user.id:
        return True
    if institute.institute_group_id and institute.institute_group.institute_group_admin_id == user.id:
        return True
    if institute.marketing_group_id and institute.marketing_group.marketing_group_admin_id == user.id:
        return True
    if Counselor.objects.filter(coun_user=user, counselor_admin=institute).exists():
        return True
    return False


def _dashboard_template(v1_path: str, v2_path: str) -> str:
    """
    Global dashboard template switch controlled by core.Configuration key DASHBOARD_TEMPLATE_VERSION.
    Defaults to v1 for safety.
    """
    try:
        v = (Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1").strip()
    except Exception:
        v = "v1"
    return v2_path if v == "v2" else v1_path


def _dashboard_primary_template_name(view) -> str:
    """
    Several dashboard views override get_template_names() but still render() with self.template_name.
    Use this helper so the admin v1/v2 switch actually affects those manual render() paths.
    """
    try:
        names = view.get_template_names()
        if names:
            return names[0]
    except Exception:
        pass
    return view.template_name

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
class AdminDashboardView(TemplateView):
    # template_name="topteenfrontend/user/admin_dashboard.html"
    # template_name="topteenfrontend/user/app/Admin_Dashboard.html"
    template_name="template20/institute/admin_dashboard.html"

    def html_head(self):
        name='Admin Dashboard'
        return build_html_head(title=name, description=name)
    
    def get_student_test_sreams(self, user):
        try:
            # Fetch the test result for the specific user
            test3_result = Results.objects.filter(user=user, test_paper='test3').first()
            if not test3_result:
                return None
            personality_res = test3_result.results

            scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
            # Get the count of successful tests
            results = Results.objects.filter(user=user)
            success_count = sum(1 for result in results if result.is_test_successful)

            # If there are results, get the latest result
            if results.exists():
                latest_result = results.last()
                return {
                    "streams": scores,  # Include the scores
                    "test_success": success_count > 0,
                    "test_link": latest_result.get_test_report_or_test_link(user) if latest_result else None,
                    "success_count": success_count
                }

        except Results.DoesNotExist:
            pass
        except Exception as e:
            print(f"An error occurred: {e}")

        return None
    
    def get_stream(self,test_results):
        # Initialize a dictionary to count streams
        stream_counts = {}

        for result in test_results:
            streams = result['streams']
            
            # From PERSONALITY
            personality_streams = streams.get('PERSONALITY', [])  # Use get to handle missing key
            if isinstance(personality_streams, list):  # Check if it's a list
                for personality in personality_streams:
                    stream = personality['stream']
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            
            # From INTELLIGENCE
            intelligence_data = streams.get('INTELLIGENCE', {})  # Use get to handle missing key
            intelligence_streams = intelligence_data.get('streams', [])
            if isinstance(intelligence_streams, list):  # Check if it's a list
                for stream in intelligence_streams:
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            elif isinstance(intelligence_streams, str):  # Handle single string case
                stream_counts[intelligence_streams] = stream_counts.get(intelligence_streams, 0) + 1

        # Extract unique streams and counts
        unique_streams = list(stream_counts.keys())
        counts = list(stream_counts.values())
        return stream_counts

    def get_context(self,request,*args,**kwargs):
        search=request.GET.get("institute")
        # if search:
            # institutes=Institute.objects.filter(name__icontains=search)| Institute.objects.filter(created_by__email__icontains=search)
            
            # institutes = (
            #     Institute.objects.filter(name__icontains=search)
            #     | Institute.objects.filter(created_by__email__icontains=search)
            # ).annotate(student_count=Count('student_management'))
        # else:
            # institutes=Institute.objects.all().order_by('-created')
        
        institutes = Institute.objects.all().order_by('-created').annotate(student_count=Count('student_management'))
        counselors_linked_to_institute = Counselor.objects.filter(counselor_admin__isnull=False)
        independent_counselors = Counselor.objects.filter(counselor_admin__isnull=True)


        institute_data = [
            {
                'address': institute.name,  # Assuming the address field exists
                'student_count': institute.student_count
            }
            for institute in institutes
        ]

        all_inst_student = StudentManagement.objects.all().order_by('-id')
        ptr_count1=[r1 for r1 in all_inst_student if r1.get_test_result()]

        results_data = {}
        for stu in all_inst_student:
            student_result = self.get_student_test_sreams(stu.student)
            if student_result:  # Only include results that were found
                results_data[stu.student] = student_result
        
        # If you want to create a list of results instead of a dictionary
        test_results = list(results_data.values())
        streams = self.get_stream(test_results) if test_results else {}

        
        pages=Paginator(institutes,4)
        pages1=Paginator(all_inst_student,10)

        page_number=request.GET.get('page')
        page_number1=request.GET.get('page')

        ctx={}
        ctx["html_head"] = self.html_head()
        ctx["Total_institutes"]=institutes
        
        ctx['results_data']=results_data
        ctx["institutes"]=pages.get_page(page_number)
        ctx["students"]=pages1.get_page(page_number1)

        ctx['total_stus']= institute_data
        ctx["institute_users"] = User.objects.filter(user_type=choices.UserType.INSTITUTE)
        # old code not in use - start
        # Marketing users list for admin dashboard
        # old code not in use - end
        ctx["marketing_users"] = User.objects.filter(user_type=choices.UserType.MARKETINGGROUPADMIN).order_by('-created')
        ctx["active_marketing_users"] = User.objects.filter(user_type=choices.UserType.MARKETINGGROUPADMIN, user_status=choices.UserStatus.UNBLOCK)
        ctx["inactive_marketing_users"] = User.objects.filter(user_type=choices.UserType.MARKETINGGROUPADMIN, user_status=choices.UserStatus.BLOCK)
        ctx["Total_students"] = StudentManagement.objects.all()
        ctx['counselors'] = Counselor.objects.all()
        ctx['counselors_linked_to_institute'] = counselors_linked_to_institute
        ctx['independent_counselors'] = independent_counselors
        ctx["global_credits"]=settings.CREDIT_LIMIT
        ctx["remaining_credits"]=get_global_remain_credits()
        ctx["institute_groups"]=InstituteGroup.objects.all()
        ctx['streams'] = streams
        ctx['test_result_count'] = ptr_count1
        return ctx
    
    def get(self,request,*args,**kwargs):
        return render(request,self.template_name,self.get_context(request,*args,**kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(superuser_or_marketing_institute_create,name='dispatch')
class InstituteCreateView(TemplateView):
    template_name = 'template20/institute/marketing_group_dashboard.html'
    
    def get(self, request, *args, **kwargs):
        # Redirect to marketing dashboard if accessed via GET
        return HttpResponseRedirect(reverse('institute:marketinggroupdashboard'))
    
    def post(self,request,*args,**kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        ins_email = (request.POST.get("institute_email") or "").strip()
        name = (request.POST.get("institute_name") or "").strip()
        address = (request.POST.get("institute_address") or "").strip()
        contact = (request.POST.get("institute_contact") or "").strip()
        admin_contact = (request.POST.get("institute_admin") or "").strip()
        credit_counts_raw = request.POST.get("ins_credits")
        institute_group_id = request.POST.get("institute_group")
        logo = request.FILES.get("institute_logo")
        referer = request.META.get('HTTP_REFERER') or reverse('institute:marketinggroupdashboard')

        ins_em = re.match(evalid, ins_email) if ins_email else None

        if ins_email and User.objects.filter(email__iexact=ins_email).exists():
            messages.error(
                request,
                "This email is already registered. An institute with this login may already exist.",
            )
            return HttpResponseRedirect(referer)

        if name and address and Institute.objects.filter(name__iexact=name, address__iexact=address).exists():
            messages.error(
                request,
                "An institute with this name and address already exists.",
            )
            return HttpResponseRedirect(referer)

        try:
            credit_counts = int(credit_counts_raw)
        except (TypeError, ValueError):
            messages.error(request, "Enter a valid number for exam credits.")
            return HttpResponseRedirect(referer)

        max_credits = get_global_remain_credits()
        if ins_em and name and address and contact and admin_contact and logo and 0 <= credit_counts <= max_credits:
            # Attach institute to selected institute group (if any)
            if institute_group_id:
                ins_group=get_object_or_404(InstituteGroup,id=institute_group_id)
            else:
                ins_group=None

            # Attach institute to this user's marketing group (create one if missing — common for new admins)
            marketing_group = InstituteMarketingGroup.objects.filter(
                marketing_group_admin=request.user
            ).order_by('id').first()
            if request.user.user_type == choices.UserType.MARKETINGGROUPADMIN and not marketing_group:
                label = (request.user.name or request.user.email or '').strip()
                if not label:
                    label = f"Marketing group {request.user.pk}"
                marketing_group = InstituteMarketingGroup.objects.create(
                    m_group_name=label[:250],
                    marketing_group_admin=request.user,
                )

            import random
            password=''.join([str(random.randint(0,10)) for _ in range(6)])
            user_dict={'email':ins_email,'password':password,'user_type':choices.UserType.INSTITUTE}
            ins_user=User.create_user(**user_dict)
            ins=Institute(
                name=name,
                created_by=ins_user,
                logo=logo,
                address=address,
                contact_info=contact,
                administrator_contact=admin_contact,
                credit_counts=credit_counts,
                institute_group=ins_group,
                marketing_group=marketing_group
            )
            ins.save()
            send_institute_mail.delay(ins.created_by.email,password)
            messages.success(request, "Institute Created")
        else:
            if credit_counts > max_credits:
                messages.error(request, "No remaining credits for this allocation.")
            elif not logo:
                messages.error(request, "Institute logo is required.")
            elif not ins_em:
                messages.error(request, "Enter a valid institute email address.")
            elif not (name and address and contact and admin_contact):
                messages.error(request, "Please fill all required institute fields.")
            else:
                messages.error(request, "Something went wrong. Please check the form and try again.")
        return HttpResponseRedirect(referer)

# manish
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_authenticated_user_only,name='dispatch')
class CounselorCreateView(TemplateView):
    
    def post(self,request,*args,**kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        coun_email=request.POST.get("counselor_email")
        name= request.POST.get("counselor_name")
        address=request.POST.get("counselor_address")
        contact=request.POST.get("counselor_contact_info")
        education = request.POST.get("counselor_education") if request.POST.get("c_education") == "Any other" else request.POST.get("c_education")
        gender_str=request.POST.get("counselor_gender", "")  # Get gender as string
        counselor_admin=request.POST.get("counselor_admin")
        ins_em=re.match(evalid,coun_email)

        slug=kwargs.get("slug")
        # Convert gender string to integer value
        # GenderChoices: UNKNOWN=10, MALE=20, FEMALE=30
        if gender_str:
            gender_str = gender_str.strip().lower()
            if gender_str in ['m', 'male', '20']:
                gender = choices.GenderChoices.MALE  # 20
            elif gender_str in ['f', 'female', '30']:
                gender = choices.GenderChoices.FEMALE  # 30
            else:
                gender = choices.GenderChoices.UNKNOWN  # 10
        else:
            gender = choices.GenderChoices.UNKNOWN  # Default to UNKNOWN if not provided
        
        # Validate required fields: email, name, address, contact, education
        # Gender is optional, so we don't require it
        if ins_em and name and address and contact and education:
            if ins_em:
                current_institute=get_object_or_404(Institute,slug=slug)
            else:
                current_institute = None
            
            # Check if user already exists
            if User.objects.filter(email=coun_email).exists():
                messages.error(request,"{} Already Exist !!".format(coun_email))
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
            import random
            password=''.join([str(random.randint(0,10)) for _ in range(6)])
            user_dict={'email':coun_email,'password':password,'user_type':choices.UserType.COUNSELOR}
            coun_user=User.create_user(**user_dict)
            coun=Counselor(counselor_name=name,coun_user = coun_user,counselor_email=coun_email,counselor_address=address,counselor_contact_info=contact,counselor_education=education,counselor_gender=gender,counselor_admin=current_institute)
            coun.save()
            send_institute_mail.delay(coun.coun_user.email,password)
            messages.success(request, "Counselor Created Successfully")
        else:
            if User.objects.filter(email=coun_email).exists():
                messages.error(request,"{} Already Exist !!".format(coun_email))
            else:
                missing_fields = []
                if not ins_em:
                    missing_fields.append("valid email")
                if not name:
                    missing_fields.append("name")
                if not address:
                    missing_fields.append("address")
                if not contact:
                    missing_fields.append("contact info")
                if not education:
                    missing_fields.append("education")
                messages.error(request,"Please fill all required fields: {}".format(", ".join(missing_fields)))
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
class InstituteGroupCreateView(TemplateView):
    def post(self,request,*args,**kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        group_email=request.POST.get("group_email")
        name= request.POST.get("group_name")
        group_em=re.match(evalid,group_email)
        if group_em and name :
            import random
            password=''.join([str(random.randint(0,10)) for _ in range(6)])
            user_dict={'email':group_email,'password':password,'user_type':choices.UserType.INSTITUTEGROUPADMIN}
            group_user=User.create_user(**user_dict)
            ins_grp=InstituteGroup(group_name=name,institute_group_admin=group_user)
            ins_grp.save()
            send_institute_group_mail.delay(ins_grp.group_name,ins_grp.institute_group_admin.email,password)
            messages.success(request, "Institute Group Created")
        else:
            if User.objects.filter(email=group_email).exists():
                messages.error(request,"{} Already Exist !!".format(group_email))
            else:
                messages.error(request,"Something Went Wrong !!")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(marketing_group_user_only,name='dispatch')
class MarketingGroupDashboardView(TemplateView):
    # template_name="topteenfrontend/user/institute_group_dashboard.html"
    template_name="template20/institute/marketing_group_dashboard.html"

    def get_template_names(self):
        return [
            _dashboard_template(
                "template20/institute/marketing_group_dashboard.html",
                "template_v2/dashboard_unified.html",
            )
        ]

    def html_head(self):
        name='Institute Group Dashboard'
        return build_html_head(title=name, description=name)
    
    def get_student_test_sreams(self, user):
        try:
            # Get all results for the user
            results = Results.objects.filter(user=user)
            
            if not results.exists():
                return None
            
            # Try to get test3 result first (personality test)
            test3_result = None
            try:
                test3_result = Results.objects.get(user=user, test_paper='test3')
            except Results.DoesNotExist:
                pass
            
            # If test3 exists, use it for personality data
            if test3_result:
                personality_res = test3_result.results
                sreams_scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
            else:
                # If no test3, try to get any available test result
                latest_result = results.last()
                if latest_result.results:
                    sreams_scores = {label.split("_")[0].upper(): value for label, value in latest_result.results.items()}
                else:
                    sreams_scores = {}

            return {
                "streams": sreams_scores,  # Include the scores
            }

        except Exception as e:
            print(f"An error occurred in get_student_test_sreams: {e}")
            return None
    
    def get_stream(self,test_results):
        # Initialize a dictionary to count streams
        stream_counts = {}        

        for result in test_results:
            streams = result['streams']
            
            # From PERSONALITY
            personality_streams = streams.get('PERSONALITY', [])  # Use get to handle missing key
            if isinstance(personality_streams, list):  # Check if it's a list
                for personality in personality_streams:
                    stream = personality['stream']
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            
            # From INTELLIGENCE
            intelligence_data = streams.get('INTELLIGENCE', {})  # Use get to handle missing key
            intelligence_streams = intelligence_data.get('streams', [])
            if isinstance(intelligence_streams, list):  # Check if it's a list
                for stream in intelligence_streams:
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            elif isinstance(intelligence_streams, str):  # Handle single string case
                stream_counts[intelligence_streams] = stream_counts.get(intelligence_streams, 0) + 1

        return stream_counts
    
    def get_institute_group_info(self, group_admin, search_params=None, load_full_data=False):
        # Scope by marketing_group.admin user (not .first() on InstituteMarketingGroup) so each
        # marketing admin only sees institutes tied to groups they own — even with multiple groups.
        institutes = Institute.objects.filter(
            marketing_group__marketing_group_admin=group_admin
        )
        
        # Apply filters if provided
        if search_params:
            # Institute name search
            if search_params.get('institute'):
                institutes = institutes.filter(
                    name__icontains=search_params['institute']
                )
            
            # Location exact match
            if search_params.get('location'):
                institutes = institutes.filter(
                    address__iexact=search_params['location']
                )
            
            # Location search
            if search_params.get('location_search'):
                institutes = institutes.filter(
                    address__icontains=search_params['location_search']
                )

            status_key = (search_params.get('status') or '').strip().lower()
            status_map = {
                'pending': choices.InstituteStatus.PENDING,
                'approved': choices.InstituteStatus.APPROVED,
                'rejected': choices.InstituteStatus.REJECTED,
            }
            if status_key in status_map:
                institutes = institutes.filter(institute_status=status_map[status_key])

        # Annotate with student count
        institutes = institutes.annotate(
            student_count=Count('student_management')
        )

        # Get unique locations for dropdown
        locations = institutes.values_list('address', flat=True).distinct()
        
        # Prepare institute data (only if loading full data)
        institute_data = []
        if load_full_data:
            institute_data = [
                {
                    'address': institute.address,
                    'student_count': institute.student_count
                }
                for institute in institutes[:100]  # Limit to 100 for performance
            ]
        
        # Only load full student data if requested (for charts/stats)
        if load_full_data:
            # Use select_related to optimize queries
            tstudents = StudentManagement.objects.filter(
                institute__marketing_group__marketing_group_admin=group_admin
            ).select_related('student', 'institute')[:1000]  # Limit to 1000 students
            
            # Optimize test results query - use prefetch_related
            results_data = {}
            # Get all students first
            student_users = [stu.student for stu in tstudents]
            
            # Batch query for test results
            test_results_queryset = Results.objects.filter(
                user__in=student_users,
                test_paper='test3'
            ).select_related('user')[:500]  # Limit results
            
            # Create a mapping of user to result
            results_map = {result.user: result for result in test_results_queryset}
            
            # Process only students with results
            test_results = []
            for stu in tstudents[:500]:  # Limit processing
                if stu.student in results_map:
                    result = results_map[stu.student]
                    if result.results:
                        personality_res = result.results
                        sreams_scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
                        test_results.append({"streams": sreams_scores})
            
            streams = self.get_stream(test_results) if test_results else {}
        else:
            # Lightweight mode - just counts
            tstudents = StudentManagement.objects.none()  # Empty queryset
            streams = {}
        
        return {
            "institutes": institutes,
            "student_count": StudentManagement.objects.filter(
                institute__marketing_group__marketing_group_admin=group_admin
            ).count() if not load_full_data else tstudents.count(),
            "counselor_count": Counselor.objects.filter(
                counselor_admin__marketing_group__marketing_group_admin=group_admin
            ).count(),
            "institute_data": institute_data,
            "tstudents": tstudents,
            "streams": streams,
            "locations": locations  # Add locations for dropdown
        }

    def update_institute_streams(request, institutes):
        # Ensure that the user is allowed to update this institute
        
        pass
    
    def get_context(self, request, *args, **kwargs):
        ctx = {}
        ctx["html_head"] = self.html_head()
        
        # Get search parameters
        _raw_status = (request.GET.get('status') or '').strip().lower()
        _status = _raw_status if _raw_status in ('pending', 'approved', 'rejected', '') else ''
        search_params = {
            'institute': request.GET.get('institute', '').strip(),
            'location': request.GET.get('location', '').strip(),
            'location_search': request.GET.get('location_search', '').strip(),
            'status': _status,
        }
        
        # Check what data is being requested
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        data_type = request.GET.get('data_type', '')  # 'institutes', 'stats', 'charts', 'seat_capacity'
        # Template v2 loads this HTML via fetch(XHR) + ?ttv2_partial=1 — must use full dashboard context
        # (otherwise we hit the "default AJAX" branch and omit ttv2_analytics / counselor_data_list).
        is_v2_shell_partial = (
            is_ajax
            and request.GET.get("ttv2_partial") == "1"
            and data_type not in ("institutes", "stats", "charts")
        )

        # For initial page load, use lightweight mode
        if (not is_ajax) or is_v2_shell_partial:
            # Lightweight initial load — scope all institute metrics to this user's marketing admin
            group_admin = request.user
            _scoped = Institute.objects.filter(
                marketing_group__marketing_group_admin=group_admin
            )
            from core.ttv2_dashboard_analytics import build_ttv2_analytics, empty_ttv2_analytics
            from institute.counselor_component_data import build_counselor_data_list_for_institute_ids

            _sm_mkt = StudentManagement.objects.filter(
                institute__marketing_group__marketing_group_admin=group_admin
            )
            try:
                ctx["ttv2_analytics"] = build_ttv2_analytics(
                    "marketing_group",
                    student_management_qs=_sm_mkt,
                    week_start=_ttv2_week_start_from_request(request),
                )
            except Exception:
                ctx["ttv2_analytics"] = empty_ttv2_analytics()
            _mkt_counselor_iids = list(_scoped.values_list("id", flat=True))
            ctx["counselor_data_list"] = build_counselor_data_list_for_institute_ids(
                _mkt_counselor_iids, include_institute_name=True
            )
            ctx.update({
                'total_institute_count': _scoped.count(),
                'pending_institute_count': _scoped.filter(
                    institute_status=choices.InstituteStatus.PENDING,
                ).count(),
                'total_stu_count': None,  # Will load via AJAX
                'counselors_count': None,  # Will load via AJAX
                'institutes': [],
                'total_students_count': None,
                'test_result_count': None,
                'streams': {},
                'locations': list(
                    _scoped.values_list('address', flat=True).distinct()[:50]
                ),
                'search_params': search_params,
                "institute_group": InstituteGroup.objects.all(),
                "institute_types": choices.InstituteType.CHOICES,
                'institutes_paginations': None,
            })
        elif data_type == 'institutes':
            # AJAX request for institute table
            group_admin = request.user
            info = self.get_institute_group_info(group_admin, search_params, load_full_data=False)
            institutes_list = info['institutes']
            
            # Get per_page parameter from request, default to 10
            per_page = request.GET.get('per_page', '10')
            
            # Handle pagination
            if per_page == 'all':
                # Show all records without pagination
                ctx['institutes_paginations'] = None
                ctx['institutes_list_all'] = list(institutes_list)
            else:
                try:
                    per_page_int = int(per_page)
                    # Limit to valid options: 10, 100
                    if per_page_int not in [10, 100]:
                        per_page_int = 10
                except (ValueError, TypeError):
                    per_page_int = 10
                
                pages = Paginator(institutes_list, per_page_int)
                page_number = request.GET.get('page', 1)
                try:
                    ctx['institutes_paginations'] = pages.get_page(page_number)
                except:
                    ctx['institutes_paginations'] = pages.get_page(1)
            
            ctx['search_params'] = search_params
            ctx['per_page'] = per_page
            from urllib.parse import urlencode
            _qs = {}
            for _k in ('institute', 'location', 'location_search', 'status'):
                _v = (search_params.get(_k) or '').strip()
                if _v:
                    _qs[_k] = _v
            if per_page:
                _qs['per_page'] = str(per_page)
            ctx['institute_table_query_string'] = urlencode(_qs)
        elif data_type == 'stats':
            # AJAX request for statistics
            group_admin = request.user
            from django.conf import settings
            institutes_in_group = Institute.objects.filter(
                marketing_group__marketing_group_admin=group_admin
            )
            total_credits = sum(inst.credit_counts for inst in institutes_in_group)
            ctx.update({
                'total_stu_count': StudentManagement.objects.filter(
                    institute__marketing_group__marketing_group_admin=group_admin
                ).count(),
                'counselors_count': Counselor.objects.filter(
                    counselor_admin__marketing_group__marketing_group_admin=group_admin
                ).count(),
                'total_credits': total_credits,
                'global_credits': settings.CREDIT_LIMIT,
                'total_events': 0,  # Placeholder - add actual events count if available
            })
        elif data_type == 'charts':
            # AJAX request for charts data - OPTIMIZED for performance
            group_admin = request.user
            _mscope = Institute.objects.filter(
                marketing_group__marketing_group_admin=group_admin
            )
            # OPTIMIZED: Get institute data for location chart (only address and student_count)
            institute_data = list(
                _mscope.values('address')
                .annotate(student_count=Count('student_management'))
                .order_by('-student_count')[:20]
            )
            seat_capacity_institutes = list(
                _mscope.values('id', 'name', 'address', 'pcm', 'cbm', 'comm', 'hme', 'hmb')
                .order_by('name')[:100]
            )
            total_students_count = StudentManagement.objects.filter(
                institute__marketing_group__marketing_group_admin=group_admin
            ).count()
            test_result_count = StudentManagement.objects.filter(
                institute__marketing_group__marketing_group_admin=group_admin
            ).filter(
                student__results__test_paper='test3'
            ).distinct().count()
            sample_students = StudentManagement.objects.filter(
                institute__marketing_group__marketing_group_admin=group_admin
            ).select_related('student')[:200]
            student_users = [stu.student for stu in sample_students]
            test_results_queryset = Results.objects.filter(
                user__in=student_users,
                test_paper='test3'
            ).select_related('user')[:200]
            results_map = {result.user: result for result in test_results_queryset}
            test_results = []
            for stu in sample_students:
                if stu.student in results_map:
                    result = results_map[stu.student]
                    if result.results:
                        personality_res = result.results
                        sreams_scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
                        test_results.append({"streams": sreams_scores})
            streams_data = self.get_stream(test_results) if test_results else {}
            streams_chart_data = []
            if streams_data:
                sorted_streams = sorted(streams_data.items(), key=lambda x: x[1], reverse=True)[:15]
                for stream, count in sorted_streams:
                    streams_chart_data.append({
                        'stream': stream,
                        'count': count
                    })
            ctx.update({
                'institutes': institute_data,
                'total_students_count': total_students_count,
                'test_result_count': test_result_count,
                'streams': streams_data,
                'streams_chart_data': streams_chart_data,
                'seat_capacity_institutes': seat_capacity_institutes,
            })
        elif is_ajax and not data_type and request.GET.get("ttv2_partial") != "1":
            # Default AJAX — institute table only (not Template v2 partial fetch)
            group_admin = request.user
            info = self.get_institute_group_info(group_admin, search_params, load_full_data=False)
            institutes_list = info['institutes']
            pages = Paginator(institutes_list, 10)
            page_number = request.GET.get('page', 1)
            ctx['institutes_paginations'] = pages.get_page(page_number)
            ctx['search_params'] = search_params
            ctx['per_page'] = '10'
            from urllib.parse import urlencode
            _qs = {}
            for _k in ('institute', 'location', 'location_search', 'status'):
                _v = (search_params.get(_k) or '').strip()
                if _v:
                    _qs[_k] = _v
            _qs['per_page'] = '10'
            ctx['institute_table_query_string'] = urlencode(_qs)
        # v2 shell: separate page mode (dashboard/students/assessments/...) from URL
        ctx["ttv2_page"] = (kwargs.get("page") or "dashboard").strip().lower()
        return ctx
    
    def get(self, request, *args, **kwargs):
        from django.template.loader import render_to_string
        from django.http import JsonResponse, HttpResponse
        
        # Check if this is an AJAX request for specific data
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        data_type = request.GET.get('data_type', '')
        
        if is_ajax and data_type == 'students_analytics':
            group_admin = request.user
            qs = StudentManagement.objects.filter(
                institute__marketing_group__marketing_group_admin=group_admin
            )
            return JsonResponse(
                build_students_analytics_payload(qs, week_start=_ttv2_week_start_from_request(request))
            )
        if is_ajax and data_type == 'institutes':
            # Return institute table partial
            context = self.get_context(request, *args, **kwargs)
            html = render_to_string('template20/institute/marketing_institutes_table.html', context, request=request)
            return HttpResponse(html)
        elif is_ajax and data_type in ['stats', 'charts']:
            # Return JSON data for stats or charts
            context = self.get_context(request, *args, **kwargs)
            # Convert QuerySets to counts/lists for JSON serialization
            json_data = {}
            for key, value in context.items():
                # Skip non-serializable items
                if key in ['html_head', 'request', 'search_params']:
                    continue
                if hasattr(value, 'count') and not isinstance(value, (str, dict, list)):
                    json_data[key] = value.count()
                elif isinstance(value, (list, tuple)):
                    # Handle lists of dicts (like institute_data)
                    json_data[key] = value
                elif isinstance(value, dict):
                    json_data[key] = value
                elif hasattr(value, '__iter__') and not isinstance(value, (str, dict, list)):
                    try:
                        json_data[key] = list(value)[:100]  # Limit to 100 items
                    except:
                        json_data[key] = []
                elif value is None:
                    json_data[key] = None
                else:
                    # For simple types (int, str, bool, etc.)
                    try:
                        json_data[key] = value
                    except:
                        pass
            return JsonResponse(json_data)
        else:
            # Regular page load (support v2 partial for AJAX shell boot)
            ctx = self.get_context(request, *args, **kwargs)
            try:
                template_version = (
                    Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1"
                ).strip()
            except Exception:
                template_version = "v1"
            if template_version == "v2" and request.GET.get("ttv2_partial") == "1":
                return render(request, "template_v2/dashboard_unified_body.html", ctx)
            return render(request, _dashboard_primary_template_name(self), ctx)
    
    def get_search_parameters(self, request):
        """Extract and validate search parameters from request"""
        _raw_status = (request.GET.get('status') or '').strip().lower()
        _status = _raw_status if _raw_status in ('pending', 'approved', 'rejected', '') else ''
        return {
            'institute': request.GET.get('institute', '').strip(),
            'location': request.GET.get('location', '').strip(),
            'location_search': request.GET.get('location_search', '').strip(),
            'status': _status,
        }

    def apply_filters(self, queryset, search_params):
        """Apply filters to queryset based on search parameters"""
        if search_params.get('institute'):
            queryset = queryset.filter(name__icontains=search_params['institute'])
        
        if search_params.get('location'):
            queryset = queryset.filter(address__iexact=search_params['location'])
            
        if search_params.get('location_search'):
            queryset = queryset.filter(address__icontains=search_params['location_search'])

        status_key = (search_params.get('status') or '').strip().lower()
        status_map = {
            'pending': choices.InstituteStatus.PENDING,
            'approved': choices.InstituteStatus.APPROVED,
            'rejected': choices.InstituteStatus.REJECTED,
        }
        if status_key in status_map:
            queryset = queryset.filter(institute_status=status_map[status_key])
        
        return queryset
    

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(marketing_group_user_only,name='dispatch')
class InstituteMarketingProfileEditView(TemplateView):
    template_name = 'template20/institute/marketing_group_dashboard.html'
    
    def get(self, request, *args, **kwargs):
        # Redirect to marketing dashboard if accessed via GET
        return HttpResponseRedirect(reverse('institute:marketinggroupdashboard'))
    
    def post(self,request, *args, **kwargs):
        ins_id = request.POST.get("institute_id")
        change_password = request.POST.get("change_password")
        
        # Handle password change
        if change_password == "1":
            new_password = request.POST.get("new_password")
            confirm_password = request.POST.get("confirm_password")
            
            if not new_password or not confirm_password:
                messages.error(request, "Both password fields are required.")
                # Handle AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Both password fields are required.'}, status=400)
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
            if new_password != confirm_password:
                messages.error(request, "Passwords do not match.")
                # Handle AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Passwords do not match.'}, status=400)
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
            ins = get_object_or_404(Institute, id=ins_id)
            group_admin = request.user
            mg = ins.marketing_group
            if not request.user.is_superuser:
                if not mg or mg.marketing_group_admin_id != group_admin.id:
                    messages.error(request, "Unauthorized access.")
                    # Handle AJAX requests
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'error': 'Unauthorized access.'}, status=403)
                    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
            # Get the institute user (created_by)
            if ins.created_by:
                ins_user = ins.created_by
                ins_user.set_password(new_password)
                ins_user.save()
                send_new_student_credential.delay(ins_user.email, new_password)
                messages.success(request, f"Password changed successfully for {ins.name}.")
                
                # Handle AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': f'Password changed successfully for {ins.name}.'})
            else:
                messages.error(request, "Institute user not found.")
                # Handle AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Institute user not found.'}, status=400)
            
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        # Handle institute profile update
        ins_name=request.POST.get("institute_name")
        ins_address=request.POST.get("institute_address")
        ins_contact=request.POST.get("institute_contact")
        ins_admin=request.POST.get("institute_admin")
        ins_credits=request.POST.get("upd_credits")
        ins_group=request.POST.get("institute_group")
        ins_logo=request.FILES.get("institute_logo")
        ins_status_raw = request.POST.get("institute_status")

        ins=get_object_or_404(Institute,id=ins_id)
        group_admin = request.user
        mg = ins.marketing_group
        if not request.user.is_superuser:
            if not mg or mg.marketing_group_admin_id != group_admin.id:
                messages.error(request, "Unauthorized access.")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Unauthorized access.'}, status=403)
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        status_updated = False
        if ins_status_raw not in (None, ""):
            try:
                s = int(str(ins_status_raw).strip())
            except (ValueError, TypeError):
                s = None
            allowed = (
                choices.InstituteStatus.APPROVED,
                choices.InstituteStatus.REJECTED,
                choices.InstituteStatus.PENDING,
            )
            if s in allowed and ins.institute_status != s:
                ins.institute_status = s
                status_updated = True

        if ins_name or ins_address or ins_contact or ins_admin or ins_logo or ins_credits or ins_group or status_updated:
            if ins_name:
                update_student_data.delay(ins.id,ins_name)
                ins.name=ins_name
            if ins_address:
                ins.address=ins_address
            if ins_contact:
                ins.contact_info=ins_contact
            if ins_admin:
                ins.administrator_contact=ins_admin
            if ins_credits and (0<=int(ins_credits)<=(ins.credit_counts+get_global_remain_credits())):
                ins.credit_counts=ins_credits
            if ins_group:
                institute_group=get_object_or_404(InstituteGroup,id=ins_group)
                ins.institute_group=institute_group
            
            if ins_logo:
                ins.logo=ins_logo
            ins.save()
            messages.success(request, f"Institute {ins.name} updated successfully.")
        else:
            messages.info(request, "No changes were made.")
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': f'Institute {ins.name} updated successfully.'})
        
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_group_user_only,name='dispatch')
class InstituteGroupDashboardView(TemplateView):
    # template_name="topteenfrontend/user/institute_group_dashboard.html"
    # template_name="topteenfrontend/user/app/institute_group_dashboard.html"
    template_name="template20/institute/institute_group_dashboard.html"

    def get_template_names(self):
        return [
            _dashboard_template(
                "template20/institute/institute_group_dashboard.html",
                "template_v2/dashboard_unified.html",
            )
        ]

    def html_head(self):
        name='Institute Group Dashboard'
        return build_html_head(title=name, description=name)
    
    def get_student_test_sreams(self, user):
        try:
            # Get all results for the user
            results = Results.objects.filter(user=user)
            
            if not results.exists():
                return None
            
            # Try to get test3 result first (personality test)
            test3_result = None
            try:
                test3_result = Results.objects.get(user=user, test_paper='test3')
            except Results.DoesNotExist:
                pass
            
            # If test3 exists, use it for personality data
            if test3_result:
                personality_res = test3_result.results
                sreams_scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
            else:
                # If no test3, try to get any available test result
                latest_result = results.last()
                if latest_result.results:
                    sreams_scores = {label.split("_")[0].upper(): value for label, value in latest_result.results.items()}
                else:
                    sreams_scores = {}

            return {
                "streams": sreams_scores,  # Include the scores
            }

        except Exception as e:
            print(f"An error occurred in get_student_test_sreams: {e}")
            return None
    
    def get_stream(self,test_results):
        # Initialize a dictionary to count streams
        stream_counts = {}        

        for result in test_results:
            streams = result['streams']
            
            # From PERSONALITY
            personality_streams = streams.get('PERSONALITY', [])  # Use get to handle missing key
            if isinstance(personality_streams, list):  # Check if it's a list
                for personality in personality_streams:
                    stream = personality['stream']
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            
            # From INTELLIGENCE
            intelligence_data = streams.get('INTELLIGENCE', {})  # Use get to handle missing key
            intelligence_streams = intelligence_data.get('streams', [])
            if isinstance(intelligence_streams, list):  # Check if it's a list
                for stream in intelligence_streams:
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            elif isinstance(intelligence_streams, str):  # Handle single string case
                stream_counts[intelligence_streams] = stream_counts.get(intelligence_streams, 0) + 1

        return stream_counts
    
    def get_institute_group_info(self, group_admin, search_params=None):
        # 1. List of institutes associated with the group admin's institute group
        institute_group = InstituteGroup.objects.filter(institute_group_admin=group_admin).first()    
        # Retrieve institutes in the group and annotate each with a student count
        
        institutes = Institute.objects.filter(institute_group=institute_group).annotate(student_count=Count('student_management'))
        self.update_institute_streams(institutes)

        # Apply filters if provided
        if search_params:
            # Institute name search
            if search_params.get('institute'):
                institutes = institutes.filter(
                    name__icontains=search_params['institute']
                )
            
            # Location exact match
            if search_params.get('location'):
                institutes = institutes.filter(
                    address__iexact=search_params['location']
                )
            
            # Location search
            if search_params.get('location_search'):
                institutes = institutes.filter(
                    address__icontains=search_params['location_search']
                )

        # Annotate with student count
        institutes = institutes.annotate(
            student_count=Count('student_management')
        )

        # Get unique locations for dropdown
        locations = institutes.values_list('address', flat=True).distinct()
        
        # Prepare institute data
        institute_data = [
            {
                'address': institute.address,
                'student_count': institute.student_count
            }
            for institute in institutes
        ]
        # Prepare a list of dictionaries to pass to the template
        institute_data = [
            {
                'address': institute.address,  # Assuming the address field exists
                'student_count': institute.student_count
            }
            for institute in institutes
        ]
        
        # 2. Count of students in all related institutes
        tstudents = StudentManagement.objects.filter(institute__institute_group=institute_group)
        results_data = {}
        for stu in tstudents:
            student_result = self.get_student_test_sreams(stu.student)
            if student_result:  # Only include results that were found
                results_data[stu.student] = student_result
        
        # If you want to create a list of results instead of a dictionary
        test_results = list(results_data.values())
                
        return {
            "institutes": institutes,
            "student_count": tstudents.count(),
            "counselor_count": Counselor.objects.filter(
                counselor_admin__institute_group=institute_group)
                .count(),
            "institute_data": institute_data,
            "tstudents": tstudents,
            "streams": self.get_stream(test_results) if 'test_results' in locals() else {},
            "locations": locations  # Add locations for dropdown
        }

    def update_institute_streams(request, institutes):
        # Ensure that the user is allowed to update this institute
        
        pass
    
    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        
        # Check if this is an AJAX request for specific data
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        data_type = request.GET.get('data_type', '')
        
        search_params = {
            'institute': request.GET.get('institute', '').strip(),
            'location': request.GET.get('location', '').strip(),
            'location_search': request.GET.get('location_search', '').strip()
        }

        group_admin = request.user
        institute_group = InstituteGroup.objects.filter(institute_group_admin=group_admin).first()
        
        if is_ajax and data_type == 'stats':
            # AJAX request for statistics (credits, counts)
            if institute_group:
                institutes_in_group = Institute.objects.filter(institute_group=institute_group)
                total_credits = sum(inst.credit_counts for inst in institutes_in_group)
                remaining_credits = get_global_remain_credits()
                ctx.update({
                    'total_stu_count': StudentManagement.objects.filter(
                        institute__institute_group=institute_group
                    ).count(),
                    'counselors_count': Counselor.objects.filter(
                        counselor_admin__institute_group=institute_group
                    ).count(),
                    'total_credits': total_credits,
                    'remaining_credits': remaining_credits,
                })
            else:
                ctx.update({
                    'total_stu_count': 0,
                    'counselors_count': 0,
                    'total_credits': 0,
                    'remaining_credits': get_global_remain_credits(),
                })
        elif is_ajax and data_type == 'charts':
            # AJAX request for charts data - OPTIMIZED for performance
            if not institute_group:
                ctx.update({
                    'institutes': [],
                    'total_students_count': 0,
                    'test_result_count': 0,
                    'streams': {},
                    'streams_chart_data': [],
                    'seat_capacity_institutes': [],
                })
            else:
                # OPTIMIZED: Get institute data for students per institute chart
                institute_data = list(
                    Institute.objects
                    .filter(institute_group=institute_group)
                    .annotate(student_count=Count('student_management'))
                    .values('id', 'name', 'student_count')
                    .order_by('-student_count')[:20]  # Top 20 institutes
                )
                
                # Get full institute list for seat capacity table
                seat_capacity_institutes = list(
                    Institute.objects
                    .filter(institute_group=institute_group)
                    .values('id', 'name', 'address', 'pcm', 'cbm', 'comm', 'hme', 'hmb')
                    .order_by('name')[:100]  # Limit to 100 institutes
                )
                
                # OPTIMIZED: Get total student count
                total_students_count = StudentManagement.objects.filter(
                    institute__institute_group=institute_group
                ).count()
                
                # OPTIMIZED: Get test result count
                test_result_count = StudentManagement.objects.filter(
                    institute__institute_group=institute_group
                ).filter(
                    student__results__test_paper='test3'
                ).distinct().count()
                
                # OPTIMIZED: Get streams data
                sample_students = StudentManagement.objects.filter(
                    institute__institute_group=institute_group
                ).select_related('student')[:200]
                
                student_users = [stu.student for stu in sample_students]
                test_results_queryset = Results.objects.filter(
                    user__in=student_users,
                    test_paper='test3'
                ).select_related('user')[:200]
                
                results_map = {result.user: result for result in test_results_queryset}
                test_results = []
                for stu in sample_students:
                    if stu.student in results_map:
                        result = results_map[stu.student]
                        if result.results:
                            personality_res = result.results
                            sreams_scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
                            test_results.append({"streams": sreams_scores})
                
                streams_data = self.get_stream(test_results) if test_results else {}
                
                # Convert streams dict to list format for chart
                streams_chart_data = []
                if streams_data:
                    sorted_streams = sorted(streams_data.items(), key=lambda x: x[1], reverse=True)[:15]
                    for stream, count in sorted_streams:
                        streams_chart_data.append({
                            'stream': stream,
                            'count': count
                        })
                
                ctx.update({
                    'institutes': institute_data,
                    'total_students_count': total_students_count,
                    'test_result_count': test_result_count,
                    'streams': streams_data,
                    'streams_chart_data': streams_chart_data,
                    'seat_capacity_institutes': seat_capacity_institutes,
                })
        elif is_ajax and data_type == 'institutes':
            # AJAX request for institute table
            info = self.get_institute_group_info(group_admin, search_params)
            institutes_list = info['institutes']
            per_page = int(request.GET.get('per_page', 10))
            if per_page == 0:
                per_page = institutes_list.count() if institutes_list else 10
            pages = Paginator(institutes_list, per_page)
            page_number = request.GET.get('page', 1)
            try:
                ctx['institutes_paginations'] = pages.get_page(page_number)
            except:
                ctx['institutes_paginations'] = pages.get_page(1)
            ctx['search_params'] = search_params
            ctx['per_page'] = per_page
        else:
            # Default page load - lightweight initial data
            info = self.get_institute_group_info(group_admin, search_params)
            institutes_list = info['institutes']        
            pages = Paginator(institutes_list, 3)
            page_number = request.GET.get('page', 1)
            
            # Update context
            try:
                institutes_paginations = pages.get_page(page_number)
            except:
                institutes_paginations = pages.get_page(1)
            
            from core.ttv2_dashboard_analytics import build_ttv2_analytics, empty_ttv2_analytics
            from institute.counselor_component_data import build_counselor_data_list_for_institute_ids

            _sm_ig = (
                StudentManagement.objects.filter(institute__institute_group=institute_group)
                if institute_group
                else StudentManagement.objects.none()
            )
            try:
                ctx["ttv2_analytics"] = build_ttv2_analytics(
                    "institute_group",
                    student_management_qs=_sm_ig,
                    week_start=_ttv2_week_start_from_request(request),
                )
            except Exception:
                ctx["ttv2_analytics"] = empty_ttv2_analytics()
            if institute_group:
                _ig_counselor_iids = list(
                    Institute.objects.filter(institute_group=institute_group).values_list(
                        "id", flat=True
                    )
                )
            else:
                _ig_counselor_iids = []
            ctx["counselor_data_list"] = build_counselor_data_list_for_institute_ids(
                _ig_counselor_iids, include_institute_name=True
            )
            ctx.update({
                'institutes_paginations': institutes_paginations,
                'total_institute_count': institutes_list.count() if institutes_list else 0,
                'total_stu_count': info['student_count'],
                'counselors_count': info['counselor_count'],
                'institutes': info['institute_data'],
                'total_students_count': info['tstudents'],
                'test_result_count': [r1 for r1 in info['tstudents'] if r1.get_test_result()],
                'streams': info['streams'],
                'locations': info['locations'],
                'search_params': search_params,
                "institute_group": institute_group,
                "institute_groups": InstituteGroup.objects.all(),
                "institute_types": choices.InstituteType.CHOICES
            })
        # v2 shell: separate page mode (dashboard/students/assessments/...) from URL
        ctx["ttv2_page"] = (kwargs.get("page") or "dashboard").strip().lower()
        return ctx
    
    def get_search_parameters(self, request):
        """Extract and validate search parameters from request"""
        return {
            'institute': request.GET.get('institute', '').strip(),
            'location': request.GET.get('location', '').strip(),
            'location_search': request.GET.get('location_search', '').strip()
        }

    def apply_filters(self, queryset, search_params):
        """Apply filters to queryset based on search parameters"""
        if search_params.get('institute'):
            queryset = queryset.filter(name__icontains=search_params['institute'])
        
        if search_params.get('location'):
            queryset = queryset.filter(address__iexact=search_params['location'])
            
        if search_params.get('location_search'):
            queryset = queryset.filter(address__icontains=search_params['location_search'])
        
        return queryset
    
    def get(self,request,*args,**kwargs):
        from django.template.loader import render_to_string
        from django.http import JsonResponse, HttpResponse
        import json
        
        # Check if this is an AJAX request for specific data
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        data_type = request.GET.get('data_type', '')
        
        if is_ajax and data_type == 'students_analytics':
            institute_group = InstituteGroup.objects.filter(institute_group_admin=request.user).first()
            if not institute_group:
                return JsonResponse(
                    build_students_analytics_payload(
                        StudentManagement.objects.none(),
                        week_start=_ttv2_week_start_from_request(request),
                    )
                )
            qs = StudentManagement.objects.filter(institute__institute_group=institute_group)
            return JsonResponse(
                build_students_analytics_payload(qs, week_start=_ttv2_week_start_from_request(request))
            )
        if is_ajax and data_type == 'institutes':
            # Return institute table partial
            context = self.get_context(request, *args, **kwargs)
            html = render_to_string('template20/institute/institute_group_institutes_table.html', context, request=request)
            return HttpResponse(html)
        elif is_ajax and data_type in ['stats', 'charts']:
            # Return JSON data for stats or charts
            context = self.get_context(request, *args, **kwargs)
            # Convert QuerySets to counts/lists for JSON serialization
            json_data = {}
            for key, value in context.items():
                # Skip non-serializable items
                if key in ['html_head', 'request', 'search_params', 'institute_group', 'institute_groups', 'institute_types']:
                    continue
                if hasattr(value, 'count') and not isinstance(value, (str, dict, list, int)):
                    try:
                        json_data[key] = value.count()
                    except:
                        json_data[key] = len(value) if hasattr(value, '__len__') else str(value)
                elif hasattr(value, '__iter__') and not isinstance(value, (str, dict)):
                    try:
                        json_data[key] = list(value)
                    except:
                        json_data[key] = str(value)
                elif isinstance(value, (list, dict, int, str, float, bool, type(None))):
                    json_data[key] = value
                else:
                    json_data[key] = str(value)
            return JsonResponse(json_data)
        else:
            # Regular page load (support v2 partial for AJAX shell boot)
            ctx = self.get_context(request, *args, **kwargs)
            try:
                template_version = (
                    Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1"
                ).strip()
            except Exception:
                template_version = "v1"
            if template_version == "v2" and request.GET.get("ttv2_partial") == "1":
                return render(request, "template_v2/dashboard_unified_body.html", ctx)
            return render(request, _dashboard_primary_template_name(self), ctx)

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(marketing_group_user_only,name='dispatch')
class InstituteBlockView(TemplateView):
    def get(self,request,*args,**kwargs):
        id=kwargs.get("id")
        ins_user=get_object_or_404(User,id=id)
        if ins_user.user_status==choices.UserStatus.UNBLOCK:
            ins_user.user_status=choices.UserStatus.BLOCK
            ins_user.save()
        else:
            ins_user.user_status=choices.UserStatus.UNBLOCK
            ins_user.save()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
class MarketingBlockView(TemplateView):
    """
    View to activate/deactivate marketing users (admin only)
    """
    def get(self,request,*args,**kwargs):
        id=kwargs.get("id")
        marketing_user=get_object_or_404(User,id=id, user_type=choices.UserType.MARKETINGGROUPADMIN)
        if marketing_user.user_status==choices.UserStatus.UNBLOCK:
            marketing_user.user_status=choices.UserStatus.BLOCK
            marketing_user.save()
        else:
            marketing_user.user_status=choices.UserStatus.UNBLOCK
            marketing_user.save()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
class InstituteChangePasswordView(TemplateView):
    def post(self, request, *args, **kwargs):
        
        id=request.POST.get("password_id")
        password=request.POST.get("change_password")
        user=get_object_or_404(User,id=id)
        user.set_password(password)
        user.save()
        send_new_student_credential.delay(user.email,password)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
from app_post_matric.models import (
    TestCategory, Test, Question, Answer,
    TestSession, UserResponse, TestResult, Sections, SectionSession, TestTopCategories
)
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_authenticated_user_only,name='dispatch')
class InstituteDashboardView(TemplateView):
    # template_name="topteenfrontend/user/institute_dashboard.html" 
    # template_name="topteenfrontend/user/app/profile_index.html" 
    template_name="template20/institute/institute_dashboard.html"

    def get_template_names(self):
        return [
            _dashboard_template(
                "template20/institute/institute_dashboard.html",
                "template_v2/dashboard_unified.html",
            )
        ]
    
    def html_head(self):
        name='Institute Dashboard'
        return build_html_head(title=name, description=name)
    
    
    def get_student_test(self,user):
        ctd=CentralTestCandidate.objects.filter(user=user)
        if ctd.exists():
            test=ctd.last().candidate_test.last()
            if test.is_success == choices.YesNoChoices.YES:
                link="{}{}".format('https://www.topteen.in',test.get_pyschometric_test_result_url())
                return link
                # return True
            else:
                return test.test_link
                # return False
        else:
            return ""

    def get_post_matric_student(self, user):
        # Check if all 4 tests are completed
        test1_completed = TestSession.objects.filter(
            user=user, 
            test__id=1,
            is_completed=True
        ).exists()
        
        test2_completed = TestSession.objects.filter(
            user=user, 
            test__id=2,
            is_completed=True
        ).exists()
        
        test3_completed = TestSession.objects.filter(
            user=user, 
            test__id=3,
            is_completed=True
        ).exists()
        
        test4_completed = TestSession.objects.filter(
            user=user, 
            test__id=4,
            is_completed=True
        ).exists()
        
        all_tests_completed = test1_completed and test2_completed and test3_completed and test4_completed
        

        
        # From APTITUDE
        return all_tests_completed
    
    def get_student_test_result(self, user):
        try:
            # Check student's class to determine which system to use
            student_management = StudentManagement.objects.filter(student=user).first()
            
            if student_management and student_management.class_and_section:
                class_name = student_management.class_and_section.class_and_section
                
                # Extract class number
                class_number = None
                try:
                    import re
                    numbers = re.findall(r'\d+', class_name)
                    if numbers:
                        class_number = int(numbers[0])
                except (ValueError, IndexError):
                    pass
                
                # Determine system based on class (and demo: demo Class 12 uses psychometric data)
                if class_number and class_number >= 11:
                    # Class 11-12: use psychometric for demo institute (demo data has no post-matric)
                    institute = getattr(student_management, "institute", None)
                    if institute and getattr(institute, "is_system_demo", False):
                        return self._get_psychometric_test_result(user)
                    # Class 11-12: Use post-matric system for non-demo
                    from app_post_matric.models import TestSession, TestResult
                    post_matric_sessions = TestSession.objects.filter(user=user)
                    return self._get_post_matric_test_result(user, post_matric_sessions)
                else:
                    # Class 10 and below: Use psychometric system
                    return self._get_psychometric_test_result(user)
            else:
                # No class information, default to psychometric system
                return self._get_psychometric_test_result(user)
                
        except Exception as e:
            print(f"An error occurred in get_student_test_result: {e}")
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
    
    def _get_post_matric_test_result(self, user, test_sessions):
        """Handle post-matric students (class 11-12) using TestSession/TestResult"""
        try:
            
            # Initialize test completion status for 4 tests
            # Based on actual test IDs from the database
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
                # test_link = reverse('post_matric:tests')
                test_link = f"{reverse('post_matric:combined_report',args=[user.id])}"
            
            
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
                "test_link": reverse('post_matric:tests'),
                "success_count": 0,
                "test_status": "no_tests",
                "test_details": {
                    "test1": False,
                    "test2": False,
                    "test3": False,
                    "test4": False
                },
                "tooltip": "Error loading post-matric test data"
            }
    
    def _get_psychometric_test_result(self, user):
        """Handle psychometric students (class 1-10) using TestCompletion/Results"""
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
            
            # Correct test3_complete if it's incorrectly set
            if test_completion.test3_complete and not all_test3_subtests_complete:
                test_completion.test3_complete = False
                test_completion.save()
            elif not test_completion.test3_complete and all_test3_subtests_complete:
                test_completion.test3_complete = True
                test_completion.save()
            
            test3_complete = test_completion.test3_complete
            
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
            
            # Get streams data if any tests are completed
            scores = {}
            if completed_tests > 0:
                results = Results.objects.filter(user=user)
                
                # Try to get test3 result first (personality test) for streams data
                test3_result = None
                try:
                    test3_result = Results.objects.get(user=user, test_paper='test3')
                except Results.DoesNotExist:
                    pass
                
                # If test3 exists, use it for personality data
                if test3_result:
                    personality_res = test3_result.results
                    scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
                else:
                    # If no test3, try to get any available test result
                    if results.exists():
                        latest_result = results.last()
                        if latest_result.results:
                            scores = {label.split("_")[0].upper(): value for label, value in latest_result.results.items()}

            # Get test link - only provide link if all tests are completed
            test_link = None
            if test_status == "completed":
                results = Results.objects.filter(user=user)
                if results.exists():
                    latest_result = results.last()
                    test_link = latest_result.get_test_report_or_test_link(user)
                else:
                    # If no Results but has TestCompletion, link to test buttons
                    test_link = reverse('app:test_buttons')

            return {
                "streams": scores,
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
                "test_link": reverse('app:test_buttons'),
                "success_count": 0,
                "test_status": "no_tests",
                "test_details": {
                    "test1": False,
                    "test2": False,
                    "test3": False
                },
                "tooltip": "Error loading psychometric test data"
            }

    def get_stream(self,test_results):
        # Initialize a dictionary to count streams
        stream_counts = {}

        for result in test_results:
            streams = result['streams']
            
            # From PERSONALITY
            personality_streams = streams.get('PERSONALITY', [])  # Use get to handle missing key
            if isinstance(personality_streams, list):  # Check if it's a list
                for personality in personality_streams:
                    stream = personality['stream']
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            
            # From INTELLIGENCE
            intelligence_data = streams.get('INTELLIGENCE', {})  # Use get to handle missing key
            intelligence_streams = intelligence_data.get('streams', [])
            if isinstance(intelligence_streams, list):  # Check if it's a list
                for stream in intelligence_streams:
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            elif isinstance(intelligence_streams, str):  # Handle single string case
                stream_counts[intelligence_streams] = stream_counts.get(intelligence_streams, 0) + 1

        # Extract unique streams and counts
        unique_streams = list(stream_counts.keys())
        counts = list(stream_counts.values())
        return stream_counts
    
    def get_filter_data(self,request,data):
        import csv
        response=HttpResponse(content_type="text/csv")
        writer=csv.writer(response)
        writer.writerow(['Name','Email','Class','Mobile','test taken','Test Link'])
        for d in data:
            test_result = self.get_student_test_result(d.student)
            # Extracting the specific fields
            test_link = test_result.get("test_link", None) if test_result else None
            test_success = test_result.get("test_success", False) if test_result else False
            writer.writerow([d.student.name,d.student.email,d.class_and_section,d.student.mobile,test_success,test_link])
        response['Content-Disposition'] = 'attachment; filename="students_data.csv"'
        return response
    
    def get_higher_class_result(self, stu_manage):
        higher_class_students = [ts.student for ts in stu_manage if 
                            ts.class_and_section.class_and_section in ['11', '12', '11th', '12th']]
        return higher_class_students
    
    def _get_student_test_result_optimized(self, user, student_management, test_completion, post_matric_sessions, results_list):
        """
        Optimized version of get_student_test_result that uses pre-fetched data.
        This avoids N+1 queries by using batch-fetched data.
        """
        try:
            if student_management and student_management.class_and_section:
                class_name = student_management.class_and_section.class_and_section
                
                # Extract class number
                class_number = None
                try:
                    import re
                    numbers = re.findall(r'\d+', class_name)
                    if numbers:
                        class_number = int(numbers[0])
                except (ValueError, IndexError):
                    pass
                
                # Determine system based on class (demo Class 12 uses psychometric data)
                if class_number and class_number >= 11:
                    institute = getattr(student_management, "institute", None)
                    if institute and getattr(institute, "is_system_demo", False):
                        return self._get_psychometric_test_result_optimized(user, test_completion, results_list)
                    # Class 11-12: Use post-matric system
                    return self._get_post_matric_test_result_optimized(user, post_matric_sessions)
                else:
                    # Class 10 and below: Use psychometric system
                    return self._get_psychometric_test_result_optimized(user, test_completion, results_list)
            else:
                # No class information, default to psychometric system
                return self._get_psychometric_test_result_optimized(user, test_completion, results_list)
                
        except Exception as e:
            print(f"An error occurred in _get_student_test_result_optimized: {e}")
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
    
    def _get_post_matric_test_result_optimized(self, user, test_sessions):
        """Optimized version using pre-fetched test_sessions"""
        try:
            # Initialize test completion status for 4 tests
            test_completion = {
                1: False,  # Personality Assessment
                2: False,  # Motivation Assessment
                3: False,  # Career Interest Inventory  
                4: False   # Aptitude Assessment
            }
            
            # Check completed sessions from pre-fetched data
            for session in test_sessions:
                if session.is_completed and session.test:
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
                from django.urls import reverse
                test_link = f"{reverse('post_matric:combined_report',args=[user.id])}"
            
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
            print(f"Error in _get_post_matric_test_result_optimized: {e}")
            from django.urls import reverse
            return {
                "streams": {},
                "test_success": False,
                "test_link": reverse('post_matric:tests'),
                "success_count": 0,
                "test_status": "no_tests",
                "test_details": {
                    "test1": False,
                    "test2": False,
                    "test3": False,
                    "test4": False
                },
                "tooltip": "Error loading post-matric test data"
            }
    
    def _get_psychometric_test_result_optimized(self, user, test_completion, results_list):
        """Optimized version using pre-fetched test_completion and results_list"""
        try:
            if not test_completion:
                # If no TestCompletion record exists, student hasn't taken any tests
                from django.urls import reverse
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
            
            # Use computed subtest state for display; do not write on dashboard read.
            test3_complete = all_test3_subtests_complete
            
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
            
            # Get streams data if any tests are completed
            scores = {}
            if completed_tests > 0 and results_list:
                # Use pre-fetched results_list instead of querying
                # Try to get test3 result first (personality test) for streams data
                test3_result = None
                for result in results_list:
                    if result.test_paper == 'test3':
                        test3_result = result
                        break
                
                if test3_result and test3_result.results:
                    personality_res = test3_result.results
                    scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
                
                # Count successful tests from pre-fetched results
                success_count = sum(1 for result in results_list if result.is_test_successful)
            else:
                success_count = 0
            
            # Get test link
            from django.urls import reverse
            test_link = None
            if test_status == "completed":
                # Try to get latest result for test link
                latest_result = None
                if results_list:
                    # Get the latest result by created date
                    latest_result = max(results_list, key=lambda r: r.created if hasattr(r, 'created') else r.id)
                    if latest_result:
                        test_link = latest_result.get_test_report_or_test_link(user)
            
            if not test_link:
                test_link = reverse('app:test_buttons')
            
            return {
                "streams": scores,
                "test_success": completed_tests > 0,
                "test_link": test_link,
                "success_count": success_count,
                "test_status": test_status,
                "test_details": {
                    "test1": test1_complete,
                    "test2": test2_complete,
                    "test3": test3_complete
                },
                "tooltip": tooltip
            }
            
        except Exception as e:
            print(f"Error in _get_psychometric_test_result_optimized: {e}")
            from django.urls import reverse
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
                "tooltip": "Error loading psychometric test data"
            }
    
    def get_context(self,request,*args,**kwargs):        
        slug=kwargs.get("slug")
        institute=get_object_or_404(Institute,slug=slug)
        
        # Use centralized function to get students based on role
        # Optimize with select_related and prefetch_related to avoid N+1 queries
        stu_manage = get_students_by_role(request.user, institute=institute).select_related(
            'student', 
            'class_and_section',
            'institute'
        )
        
        # Get filter parameters
        test_taken_filter = request.GET.get('test_taken', '')
        stream_filter = request.GET.get('stream', '')

        # Batch psychometric + Results without materializing all StudentManagement rows
        from psychometric_tests.models import PsychometricTestResult
        from app.models import Results
        student_user_ids = list(
            stu_manage.values_list("student_id", flat=True).filter(student__isnull=False)
        )
        psychometric_results_map = {}
        if student_user_ids:
            psychometric_results = PsychometricTestResult.objects.filter(
                assessment__central_test_candidate__user_id__in=student_user_ids
            ).select_related("assessment__central_test_candidate__user")
            for result in psychometric_results:
                user = result.assessment.central_test_candidate.user
                if user not in psychometric_results_map:
                    psychometric_results_map[user] = []
                psychometric_results_map[user].append(result)

        psych_stu_ids = set(psychometric_results_map.keys())
        ptr_count = stu_manage.filter(student_id__in=[u.id for u in psych_stu_ids]).count()

        test_results_map = {}
        all_results = []
        if student_user_ids:
            all_results = list(
                Results.objects.filter(
                    user_id__in=student_user_ids
                ).select_related("user")
            )
            for result in all_results:
                if result.user not in test_results_map:
                    test_results_map[result.user] = []
                test_results_map[result.user].append(result)

        success_user_ids = {
            r.user_id
            for r in all_results
            if getattr(r, "is_test_successful", False)
        }
        ptr_count1 = stu_manage.filter(student_id__in=success_user_ids).count()
        
        # Use centralized function to get class_and_sections based on role
        class_and_sections = get_class_and_sections_by_role(request.user, stu_manage)
        
        # Get class counts using centralized function
        class_counts = get_class_counts(stu_manage)
        
        # Get unique streams using centralized function
        from counselor.views import get_unique_streams_by_role
        unique_streams = get_unique_streams_by_role(request.user, stu_manage)

        # For initial page load, skip heavy student data processing
        # Student table will be loaded via AJAX with full data
        results_data = {}
        completed_students_count = []
        higher_class_results = {}
        
        # Lightweight streams chart: sample first 200 students, batch Results by user_id
        streams = {}
        if student_user_ids:
            sample_students = list(stu_manage[:200])
            sample_user_ids = [s.student_id for s in sample_students if s.student_id]
            if sample_user_ids:
                test_results_queryset = Results.objects.filter(
                    user_id__in=sample_user_ids,
                    test_paper="test3",
                ).select_related("user")[:200]
                
                # Process streams from sample results - use same format as marketing dashboard
                test_results = []
                results_map = {result.user: result for result in test_results_queryset}
                for stu in sample_students:
                    if stu.student and stu.student in results_map:
                        result = results_map[stu.student]
                        if result.results:
                            personality_res = result.results
                            streams_scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
                            test_results.append({"streams": streams_scores})
                
                # Calculate streams from sample
                if test_results:
                    streams = self.get_stream(test_results)
        
        # Lightweight: Don't convert to list - keep as QuerySet for initial load
        # Only get count for statistics
        total_students_count_list = stu_manage.count() if hasattr(stu_manage, 'count') else len(list(stu_manage))
        
        # Optimize: Batch fetch counselor data and FollowUpStatus records
        counselors = Counselor.objects.filter(counselor_admin=institute).select_related('counselor_admin')
        counselor_ids = [c.id for c in counselors]

        # v2 dashboard: Unassigned students (not mapped to any counselor)
        ttv2_unassigned_rows = []
        ttv2_counselor_options = []
        try:
            unassigned_qs = (
                stu_manage.filter(counselors__isnull=True)
                .select_related("student", "class_and_section")
                .order_by("-created")
            )
            unassigned_rows = []
            for sm in list(unassigned_qs[:25]):
                u = getattr(sm, "student", None)
                cas = getattr(sm, "class_and_section", None)
                unassigned_rows.append(
                    {
                        "sm_id": sm.id,
                        "student_id": getattr(sm, "student_id", None),
                        "name": getattr(u, "name", None) or getattr(u, "email", None) or "Student",
                        "email": getattr(u, "email", None) or "",
                        "class": getattr(cas, "class_and_section", None) or "",
                        "stream": getattr(cas, "stream", None) or "",
                    }
                )
            ttv2_unassigned_rows = unassigned_rows
            ttv2_counselor_options = [
                {"id": c.id, "name": getattr(c, "counselor_name", "") or f"Counselor {c.id}"}
                for c in counselors
            ]
        except Exception:
            ttv2_unassigned_rows = []
            ttv2_counselor_options = []
        
        # Batch fetch all FollowUpStatus records for all counselors at once
        all_followups = FollowUpStatus.objects.filter(counselor_id__in=counselor_ids).select_related('counselor')
        
        # Create maps for efficient lookup
        followups_by_counselor = {}
        for followup in all_followups:
            if followup.counselor_id not in followups_by_counselor:
                followups_by_counselor[followup.counselor_id] = []
            followups_by_counselor[followup.counselor_id].append(followup)
        
        # Batch fetch session data grouped by counselor and date
        from django.db.models import Count
        sessions_data_all = (
            FollowUpStatus.objects
            .filter(counselor_id__in=counselor_ids)
            .values('counselor_id', 'last_follow_up_date')
            .annotate(session_count=Count('id'))
        )
        
        # Group session data by counselor
        sessions_by_counselor = {}
        for session in sessions_data_all:
            counselor_id = session['counselor_id']
            if counselor_id not in sessions_by_counselor:
                sessions_by_counselor[counselor_id] = []
            sessions_by_counselor[counselor_id].append(session)
        
        counselor_data_list = []
        couns_sessions_data = []

        for counselor in counselors:
            counselor_id = counselor.id
            followups = followups_by_counselor.get(counselor_id, [])
            
            # Calculate counts from pre-fetched data
            sessions_count = len(followups)
            students_counseled_count = sum(1 for f in followups if f.follow_up_status == 'completed')
            
            # Append data for each counselor to the list
            counselor_data_list.append({
                'id': counselor.id,
                'coun_admin': counselor.counselor_admin,
                'name': counselor.counselor_name,
                'email': counselor.counselor_email,
                'sessions': sessions_count,
                'students_counseled': students_counseled_count,
                'created': counselor.created
            })
            
            # Get session data for the current counselor from pre-fetched data
            sessions_data_list = sessions_by_counselor.get(counselor_id, [])
            # Convert dates to strings
            for session in sessions_data_list:
                if session.get('last_follow_up_date'):
                    session['last_follow_up_date'] = session['last_follow_up_date'].isoformat()

            # Calculate sessions for the current week (Monday to Saturday)
            week_data = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}  # Monday to Saturday
            for session in sessions_data_list:
                try:
                    if session.get('last_follow_up_date'):
                        session_date = datetime.strptime(session['last_follow_up_date'], "%Y-%m-%d")
                        day_of_week = session_date.weekday()  # Monday is 0
                        if day_of_week < 6:  # Only consider Monday to Saturday
                            week_data[day_of_week] += session.get('session_count', 0)
                except (KeyError, ValueError) as e:
                    print(f"Error parsing session data: {e} in session: {session}")

            # Prepare the final sessions data for the counselor
            final_sessions_data = []
            for day, count in week_data.items():
                # Calculate the correct date for each day in the week
                # Assume we want the date of the most recent Monday
                recent_monday = datetime.now() - timedelta(days=datetime.now().weekday())
                final_sessions_data.append({
                    "day": (recent_monday + timedelta(days=day)).strftime("%Y-%m-%d"),
                    "session_count": count
                })

            # Append the sessions data for the current counselor to the main list
            couns_sessions_data.append({
                'counselor_id': counselor.id,
                'counselor_name': counselor.counselor_name,
                'sessions': final_sessions_data  # Add sessions data for this counselor
            })
        # Convert to JSON
        try:
            sessions_data_json = json.dumps(couns_sessions_data)
        except Exception as e:
            print(f"Error serializing sessions data: {e}")
            sessions_data_json = '[]'
        
        # For initial page load, create minimal pagination - table will load via AJAX
        # Don't process filters or student data here - it's done in AJAX request
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
        # Create a minimal paginator with just 1 item for initial structure
        minimal_students = stu_manage[:1] if hasattr(stu_manage, '__getitem__') else []
        pages = Paginator(minimal_students, 10)
        page_number = request.GET.get('page', 1)
        try:
            total_students = pages.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            total_students = pages.get_page(1)
        
        ctx={}
        ctx["html_head"] = self.html_head()
        # Pass count directly as integer for this specific institute
        ctx['total_students_count'] = total_students_count_list  # Direct count for this institute
        ctx["total_students"]=total_students  # Minimal for initial structure
        ctx["active_students"]=stu_manage.filter(student__is_active=True).count() if hasattr(stu_manage, 'count') else 0
        ctx["psychometric_test_result_count"]=ptr_count  # Just count
        ctx["central_test_candidate"]=CentralTestCandidate.objects.none()  # Don't load all
        ctx["institute"]=institute
        ctx["class_and_sections"]=class_and_sections
        ctx['class_counts']=class_counts  # Add class counts for dropdown
        ctx['unique_streams']=unique_streams  # Add unique streams for dropdown
        ctx['stu']=stu_manage  # Keep as QuerySet, don't convert to list
        ctx['results_data']={}  # Empty - will be loaded via AJAX
        ctx['test_result_count']=ptr_count1  # Just count
        ctx['counselor_list']= counselors     
        ctx['counselor_data_list']= counselor_data_list
        ctx["ttv2_unassigned_students"] = ttv2_unassigned_rows
        ctx["ttv2_counselor_options"] = ttv2_counselor_options
        ctx['sessions_data_json']= sessions_data_json 
        ctx['streams'] = streams  # Empty for initial load
        ctx['higher_class_results'] = {}  # Empty for initial load
        ctx['Testsession'] = TestSession
        try:
            from core.ttv2_dashboard_analytics import build_ttv2_analytics, empty_ttv2_analytics

            ctx["ttv2_analytics"] = build_ttv2_analytics(
                "institute",
                institute=institute,
                student_management_qs=stu_manage,
                week_start=_ttv2_week_start_from_request(request),
            )
        except Exception:
            from core.ttv2_dashboard_analytics import empty_ttv2_analytics

            ctx["ttv2_analytics"] = empty_ttv2_analytics()
        # v2 shell: separate page mode (dashboard/students/assessments/...) from URL
        ctx["ttv2_page"] = (kwargs.get("page") or "dashboard").strip().lower()

        # Students page: Psychometric assessment PDF stats (MI/EI attempts in scope)
        try:
            from core.models import MIAssessmentResult, EQAssessmentResult
            uids = list(stu_manage.values_list("student_id", flat=True))
            uids = [int(x) for x in uids if x]
            mi_uids = set(MIAssessmentResult.objects.filter(user_id__in=uids).values_list("user_id", flat=True).distinct())
            eq_uids = set(EQAssessmentResult.objects.filter(user_id__in=uids).values_list("user_id", flat=True).distinct())
            attempted = len(mi_uids.union(eq_uids))
            ctx["ttv2_psych_pdf"] = {"attempted": attempted, "total": len(set(uids))}
        except Exception:
            ctx["ttv2_psych_pdf"] = {"attempted": 0, "total": 0}
        return ctx

    def get(self, request, *args, **kwargs):
        download=request.GET.get("download")

        # Students page: Psychometric assessment PDF download (MI/EI attempts in current scope; ignores search filters)
        if (request.GET.get("psychometric_pdf") or "").strip() == "1":
            slug = kwargs.get("slug")
            institute = get_object_or_404(Institute, slug=slug)
            stu_manage = (
                get_students_by_role(request.user, institute=institute)
                .select_related("student", "class_and_section", "institute")
                .prefetch_related("counselors")
            )
            uids = [int(x) for x in stu_manage.values_list("student_id", flat=True) if x]
            try:
                from core.models import MIAssessmentResult, EQAssessmentResult
                mi_latest = {}
                for r in MIAssessmentResult.objects.filter(user_id__in=uids).order_by("user_id", "-updated_at"):
                    if r.user_id not in mi_latest:
                        mi_latest[r.user_id] = r
                eq_latest = {}
                for r in EQAssessmentResult.objects.filter(user_id__in=uids).order_by("user_id", "-updated_at"):
                    if r.user_id not in eq_latest:
                        eq_latest[r.user_id] = r
                keep = []
                for sm in stu_manage:
                    uid = getattr(sm, "student_id", None)
                    if uid and (uid in mi_latest or uid in eq_latest):
                        keep.append(sm)

                # Build a simple 1-page-per-student PDF (page breaks)
                def esc(s):
                    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
                pages = []
                for sm in keep:
                    u = sm.student
                    cas = sm.class_and_section
                    uid = sm.student_id
                    mi = mi_latest.get(uid)
                    eq = eq_latest.get(uid)
                    mi_line = "MI: —"
                    if mi:
                        mi_line = "MI: %s (%s)" % (esc(mi.style_name), esc(mi.primary_style))
                    eq_line = "EI: —"
                    if eq:
                        eq_line = "EI: %.1f (%s)" % (float(eq.ei_total or 0), esc(eq.band_label))
                    pages.append(
                        """
                        <div class="page">
                          <div class="h1">%s</div>
                          <div class="meta">%s%s</div>
                          <div class="meta">%s</div>
                          <div class="box">
                            <div class="row">%s</div>
                            <div class="row">%s</div>
                          </div>
                          <div class="foot">Generated for %s</div>
                        </div>
                        """ % (
                            esc(getattr(u, "name", "") or "-"),
                            esc(getattr(cas, "class_and_section", "") or "-"),
                            (" · " + esc(getattr(cas, "stream", "") or "")) if cas and getattr(cas, "stream", None) else "",
                            esc(getattr(u, "email", "") or ""),
                            mi_line,
                            eq_line,
                            esc(getattr(institute, "name", "") or "School"),
                        )
                    )

                full_html = """<!doctype html>
                <html><head><meta charset="utf-8">
                <title>Psychometric assessment PDF</title>
                <style>
                  @page { size: A4; margin: 18mm; }
                  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; color:#111827; }
                  .page { page-break-after: always; }
                  .h1 { font-size: 18px; font-weight: 800; margin: 0 0 4px; }
                  .meta { font-size: 11px; color:#4b5563; margin: 0 0 2px; }
                  .box { margin-top: 14px; padding: 12px; border: 1px solid #e5e7eb; border-radius: 12px; }
                  .row { font-size: 12px; margin: 0 0 6px; }
                  .foot { margin-top: 18px; font-size: 10px; color:#6b7280; }
                </style></head><body>%s</body></html>""" % ("\n".join(pages) if pages else "<p>No students with MI/EI attempts found.</p>")
                try:
                    import weasyprint
                    pdf_bytes = weasyprint.HTML(string=full_html, base_url=request.build_absolute_uri("/")).write_pdf()
                except Exception as e:
                    return HttpResponse("PDF generation failed: %s" % str(e), status=500)
                resp = HttpResponse(pdf_bytes, content_type="application/pdf")
                resp["Content-Disposition"] = 'attachment; filename="Psychometric-assessment.pdf"'
                return resp
            except Exception as e:
                return HttpResponse("PDF generation failed: %s" % str(e), status=500)
        
        # Check if this is an AJAX request for student table - process only student data
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            data_type = request.GET.get('data_type', '')
            if data_type == 'students':
                # Lightweight context for AJAX - only student table data
                ctx = self.get_student_table_context_ajax(request, *args, **kwargs)
                from institute.student_table_helpers import get_student_table_config, get_student_action_urls
                ctx['table_config'] = get_student_table_config('institute')
                ctx['action_urls'] = get_student_action_urls('institute')
                # Map total_students to students for template compatibility
                ctx['students'] = ctx.get('total_students')

                # Enrich results_data for card UI (best-effort; missing data stays empty/disabled).
                try:
                    from colleges.models import CollegeShortlist
                    from core.models import MIAssessmentResult, EQAssessmentResult
                    uids = []
                    for sm in (ctx.get("students") or []):
                        try:
                            if sm and getattr(sm, "student_id", None):
                                uids.append(int(sm.student_id))
                        except Exception:
                            continue
                    uids = list({x for x in uids if x})
                    abroad_uids = set()
                    if uids:
                        # Abroad exploring: user has at least 1 shortlisted college outside India.
                        qs = (
                            CollegeShortlist.objects.filter(user_id__in=uids)
                            .select_related("college", "college__country")
                        )
                        for cs in qs:
                            try:
                                c = cs.college
                                country = getattr(c, "country", None) if c else None
                                name = (getattr(country, "name", "") or "").strip().lower()
                                short = (getattr(country, "short_name", "") or "").strip().lower()
                                if country and name and name != "india" and short != "in":
                                    abroad_uids.add(int(cs.user_id))
                            except Exception:
                                continue
                    mi_uids = set()
                    eq_uids = set()
                    try:
                        if uids:
                            mi_uids = set(
                                MIAssessmentResult.objects.filter(user_id__in=uids)
                                .values_list("user_id", flat=True)
                                .distinct()
                            )
                            eq_uids = set(
                                EQAssessmentResult.objects.filter(user_id__in=uids)
                                .values_list("user_id", flat=True)
                                .distinct()
                            )
                    except Exception:
                        mi_uids, eq_uids = set(), set()
                    results_data = ctx.get("results_data") or {}
                    for sm in (ctx.get("students") or []):
                        try:
                            uid = int(sm.student_id) if sm and sm.student_id else None
                        except Exception:
                            uid = None
                        if not uid:
                            continue
                        rd = results_data.get(uid) or {}
                        # Stream/track: prefer class_and_section.stream, fallback to "-" (report-derived not available reliably)
                        try:
                            cas = getattr(sm, "class_and_section", None)
                            rd.setdefault("track", (getattr(cas, "stream", "") or "").strip() or "")
                        except Exception:
                            rd.setdefault("track", "")
                        # Match / Risk: if present in rd keep it; otherwise blank
                        rd.setdefault("match_pct", rd.get("match_pct") or "")
                        rd.setdefault("risk_score", rd.get("risk_score") or "")
                        # MI/EI attempted flags (from core assessment results)
                        rd["mi_attempted"] = True if uid in mi_uids else False
                        rd["eq_attempted"] = True if uid in eq_uids else False
                        rd["abroad_exploring"] = True if uid in abroad_uids else False
                        results_data[uid] = rd
                    ctx["results_data"] = results_data
                except Exception:
                    pass

                display = (request.GET.get("display") or "").strip().lower()
                if display == "cards":
                    return render(request, "template_v2/institute/pages/student_roster_cards.html", ctx)
                # default: list/table
                return render(request, "template20/shared/students_table.html", ctx)
            if data_type == 'students_analytics':
                slug = kwargs.get("slug")
                institute = get_object_or_404(Institute, slug=slug)
                stu_manage = get_students_by_role(request.user, institute=institute)
                return JsonResponse(
                    build_students_analytics_payload(
                        stu_manage, week_start=_ttv2_week_start_from_request(request)
                    )
                )

        # Full context for initial page load
        ctx=self.get_context(request, *args, **kwargs)
        if download=="Yes":
            data=ctx.get('stu')
            return self.get_filter_data(request,data)

        # v2 "Payments" page: show payments scoped to this institute's students.
        if (ctx.get("ttv2_page") or "").strip().lower() == "payments":
            try:
                stu_qs = ctx.get("stu")
                if hasattr(stu_qs, "values_list"):
                    uids = [int(x) for x in stu_qs.values_list("student_id", flat=True) if x]
                else:
                    uids = []

                uids = list({x for x in uids if x})
                payments_rows = []
                status_filter = (request.GET.get("status") or "").strip().lower()
                # allow: success / failed / pending
                if uids:
                    from payments.models import Payment
                    from psychometric_tests.models import PsychometricTestPayment
                    from skilllab.models import SkilllabCoursePayment
                    from core import choices as core_choices

                    def _yesno_to_status(v):
                        try:
                            return "Successful" if int(v) == int(core_choices.YesNoChoices.YES) else "Failed"
                        except Exception:
                            return "—"

                    # Psychometric test payments
                    for p in (
                        PsychometricTestPayment.objects.filter(user_id__in=uids)
                        .select_related("user")
                        .order_by("-created")[:500]
                    ):
                        st = _yesno_to_status(getattr(p, "is_success", None))
                        if status_filter in ("success", "successful") and st != "Successful":
                            continue
                        if status_filter in ("failed", "fail") and st != "Failed":
                            continue
                        payments_rows.append(
                            {
                                "when": getattr(p, "created", None).strftime("%Y-%m-%d %H:%M") if getattr(p, "created", None) else "-",
                                "user": (getattr(getattr(p, "user", None), "email", "") or "-"),
                                "kind": getattr(p, "get_test_name", lambda: "Psychometric Test")(),
                                "amount": getattr(p, "amount", 0) or 0,
                                "status": st,
                            }
                        )

                    # Skilllab course payments
                    for p in (
                        SkilllabCoursePayment.objects.filter(user_id__in=uids)
                        .select_related("user", "skilllab_course")
                        .order_by("-created")[:500]
                    ):
                        course = getattr(p, "skilllab_course", None)
                        st = _yesno_to_status(getattr(p, "is_success", None))
                        if status_filter in ("success", "successful") and st != "Successful":
                            continue
                        if status_filter in ("failed", "fail") and st != "Failed":
                            continue
                        payments_rows.append(
                            {
                                "when": getattr(p, "created", None).strftime("%Y-%m-%d %H:%M") if getattr(p, "created", None) else "-",
                                "user": (getattr(getattr(p, "user", None), "email", "") or "-"),
                                "kind": ("Skilllab: %s" % (getattr(course, "name", "") or "Course")),
                                "amount": getattr(p, "amount", 0) or 0,
                                "status": st,
                            }
                        )

                    # Generic gateway payments (if used elsewhere)
                    for p in (
                        Payment.objects.filter(user_id__in=uids)
                        .select_related("user")
                        .order_by("-created")[:500]
                    ):
                        st = _yesno_to_status(getattr(p, "is_success", None))
                        # "pending" filter: failed rows that look like pending attempt (order id exists, payment id missing)
                        if status_filter in ("pending",):
                            if not (
                                getattr(p, "gateway_order_id", None)
                                and not getattr(p, "gateway_payment_id", None)
                                and st == "Failed"
                            ):
                                continue
                            st = "Pending"
                        elif status_filter in ("success", "successful") and st != "Successful":
                            continue
                        elif status_filter in ("failed", "fail") and st != "Failed":
                            continue
                        payments_rows.append(
                            {
                                "when": getattr(p, "created", None).strftime("%Y-%m-%d %H:%M") if getattr(p, "created", None) else "-",
                                "user": (getattr(getattr(p, "user", None), "email", "") or "-"),
                                "kind": getattr(p, "get_obj_type_display", lambda: "Payment")(),
                                "amount": getattr(p, "amount", 0) or 0,
                                "status": st,
                            }
                        )

                # Sort combined rows newest-first (string date format is sortable here).
                payments_rows.sort(key=lambda r: r.get("when") or "", reverse=True)
                ctx["ttv2_institute_payments"] = payments_rows
            except Exception:
                ctx["ttv2_institute_payments"] = []

        # v2 "Accounts" page: institute-scoped accounts analytics (similar to user_analytics accounts dashboard).
        if (ctx.get("ttv2_page") or "").strip().lower() == "accounts":
            try:
                from django.utils import timezone
                from datetime import timedelta
                from django.db.models import Sum
                from core import choices as core_choices
                from users.models import User
                from payments.models import Payment
                from psychometric_tests.models import PsychometricTestPayment
                from skilllab.models import SkilllabCoursePayment

                def _date_range_from_period(period, default_days=30):
                    end = timezone.now()
                    p = (period or "").strip()
                    if p == "today":
                        start = end.replace(hour=0, minute=0, second=0, microsecond=0)
                    elif p == "yesterday":
                        start = (end - timedelta(days=1)).replace(
                            hour=0, minute=0, second=0, microsecond=0
                        )
                        end = start + timedelta(days=1)
                    elif p == "7days":
                        start = end - timedelta(days=7)
                    elif p == "30days":
                        start = end - timedelta(days=30)
                    elif p == "90days":
                        start = end - timedelta(days=90)
                    elif p == "alltime":
                        return None, None
                    else:
                        start = end - timedelta(days=default_days)
                    return start, end

                def _status_label(is_success):
                    try:
                        return (
                            "Successful"
                            if int(is_success) == int(core_choices.YesNoChoices.YES)
                            else "Failed"
                        )
                    except Exception:
                        return "—"

                stu_qs = ctx.get("stu")
                if hasattr(stu_qs, "values_list"):
                    uids = [int(x) for x in stu_qs.values_list("student_id", flat=True) if x]
                else:
                    uids = []
                uids = list({x for x in uids if x})

                time_period = (request.GET.get("period") or "30days").strip()
                start_date, end_date = _date_range_from_period(time_period, default_days=30)

                # Registrations: count institute students created in the selected period.
                reg_qs = User.objects.filter(id__in=uids)
                if start_date is not None:
                    reg_qs = reg_qs.filter(created__gte=start_date, created__lte=end_date)
                total_registrations = reg_qs.count()

                # Payments / revenue across models.
                def _filter_by_date(qs):
                    if start_date is None:
                        return qs
                    return qs.filter(created__gte=start_date, created__lte=end_date)

                ptp_s = _filter_by_date(
                    PsychometricTestPayment.objects.filter(
                        user_id__in=uids, is_success=core_choices.YesNoChoices.YES
                    )
                )
                ptp_f = _filter_by_date(
                    PsychometricTestPayment.objects.filter(
                        user_id__in=uids, is_success=core_choices.YesNoChoices.NO
                    )
                )
                slp_s = _filter_by_date(
                    SkilllabCoursePayment.objects.filter(
                        user_id__in=uids, is_success=core_choices.YesNoChoices.YES
                    )
                )
                slp_f = _filter_by_date(
                    SkilllabCoursePayment.objects.filter(
                        user_id__in=uids, is_success=core_choices.YesNoChoices.NO
                    )
                )
                pay_s = _filter_by_date(
                    Payment.objects.filter(user_id__in=uids, is_success=core_choices.YesNoChoices.YES)
                )
                pay_f = _filter_by_date(
                    Payment.objects.filter(user_id__in=uids, is_success=core_choices.YesNoChoices.NO)
                )

                total_revenue = 0
                for qs in (ptp_s, slp_s, pay_s):
                    try:
                        total_revenue += float(qs.aggregate(total=Sum("amount"))["total"] or 0)
                    except Exception:
                        pass

                payment_status = {
                    "success": int(ptp_s.count() + slp_s.count() + pay_s.count()),
                    "failed": int(ptp_f.count() + slp_f.count() + pay_f.count()),
                    "pending": 0,
                }

                # Pending: best-effort from gateway Payment rows without payment id (order created, not completed).
                pending_qs = Payment.objects.filter(user_id__in=uids, is_success=core_choices.YesNoChoices.NO)
                pending_qs = pending_qs.exclude(gateway_order_id__isnull=True).exclude(gateway_order_id__exact="")
                pending_qs = pending_qs.filter(gateway_payment_id__isnull=True)
                if start_date is not None:
                    pending_qs = pending_qs.filter(created__gte=start_date, created__lte=end_date)
                payment_status["pending"] = int(pending_qs.count())

                # Prospects: not tracked per institute here (set to 0 for institute dashboards).
                total_prospects = 0
                converted_prospects = 0
                pending_prospects = 0

                # Revenue by source: not reliably available per institute (no UTM/source on payment models).
                # Show a single "Unknown" bucket for now so UI matches.
                success_count = payment_status["success"]
                revenue_by_source = []
                if success_count > 0 and total_revenue > 0:
                    revenue_by_source = [
                        {"metadata__source": "Unknown", "revenue": float(total_revenue), "count": int(success_count)}
                    ]

                failed_payments = []
                if payment_status["failed"] > 0:
                    if int(ptp_f.count()) > 0:
                        failed_payments.append({"event_name": "Psychometric Test Payment", "count": int(ptp_f.count())})
                    if int(slp_f.count()) > 0:
                        failed_payments.append({"event_name": "Skilllab Course Payment", "count": int(slp_f.count())})
                    if int(pay_f.count()) > 0:
                        failed_payments.append({"event_name": "Gateway Payment", "count": int(pay_f.count())})

                pending_payments_list = []
                for p in pending_qs.select_related("user").order_by("-created")[:20]:
                    pending_payments_list.append(
                        {
                            "user": getattr(p, "user", None),
                            "event_name": "Payment Pending",
                            "amount": getattr(p, "amount", 0) or 0,
                            "created": getattr(p, "created", None),
                        }
                    )

                ctx["ttv2_accounts"] = {
                    "time_period": time_period,
                    "total_registrations": int(total_registrations),
                    "total_revenue": float(total_revenue),
                    "total_prospects": int(total_prospects),
                    "converted_prospects": int(converted_prospects),
                    "pending_prospects": int(pending_prospects),
                    "payment_status": payment_status,
                    "revenue_by_source": revenue_by_source,
                    "failed_payments": failed_payments,
                    "pending_payments_list": pending_payments_list,
                }
            except Exception:
                ctx["ttv2_accounts"] = {
                    "time_period": (request.GET.get("period") or "30days").strip(),
                    "total_registrations": 0,
                    "total_revenue": 0,
                    "total_prospects": 0,
                    "converted_prospects": 0,
                    "pending_prospects": 0,
                    "payment_status": {"success": 0, "failed": 0, "pending": 0},
                    "revenue_by_source": [],
                    "failed_payments": [],
                    "pending_payments_list": [],
                }

        # v2 "Sessions" page: show counselor follow-ups for this institute.
        if (ctx.get("ttv2_page") or "").strip().lower() == "sessions":
            try:
                from counselor.models import FollowUpStatus

                slug = kwargs.get("slug")
                institute = get_object_or_404(Institute, slug=slug) if slug else ctx.get("institute")
                qs = (
                    FollowUpStatus.objects.filter(counselor__counselor_admin=institute)
                    .select_related("counselor", "student", "student__student")
                    .order_by("-last_follow_up_date", "-created")[:200]
                )
                rows = []
                for fu in qs:
                    sm = getattr(fu, "student", None)
                    u = getattr(sm, "student", None) if sm else None
                    rows.append(
                        {
                            "when": getattr(fu, "last_follow_up_date", None).strftime("%Y-%m-%d")
                            if getattr(fu, "last_follow_up_date", None)
                            else (getattr(fu, "created", None).strftime("%Y-%m-%d") if getattr(fu, "created", None) else "-"),
                            "counselor": getattr(getattr(fu, "counselor", None), "counselor_name", None) or "-",
                            "student": getattr(u, "name", None)
                            or getattr(u, "email", None)
                            or (getattr(sm, "student_name", None) if sm else None)
                            or "-",
                            "mode": getattr(fu, "mode_of_follow_up", None) or "-",
                            "status": getattr(fu, "follow_up_status", None) or "-",
                            "next": getattr(fu, "next_follow_up_date", None).strftime("%Y-%m-%d")
                            if getattr(fu, "next_follow_up_date", None)
                            else "-",
                        }
                    )
                if not rows:
                    ctx["ttv2_sessions_is_dummy"] = True
                    ctx["ttv2_sessions"] = [
                        {"when": "2026-04-28", "counselor": "Counselor A", "student": "Student One", "mode": "Call", "status": "completed", "next": "—"},
                        {"when": "2026-04-27", "counselor": "Counselor B", "student": "Student Two", "mode": "Meeting", "status": "pending", "next": "2026-04-30"},
                        {"when": "2026-04-26", "counselor": "Counselor A", "student": "Student Three", "mode": "Email", "status": "follow-up", "next": "2026-05-02"},
                    ]
                else:
                    ctx["ttv2_sessions_is_dummy"] = False
                    ctx["ttv2_sessions"] = rows
            except Exception:
                ctx["ttv2_sessions_is_dummy"] = True
                ctx["ttv2_sessions"] = [
                    {"when": "2026-04-28", "counselor": "Counselor A", "student": "Student One", "mode": "Call", "status": "completed", "next": "—"},
                    {"when": "2026-04-27", "counselor": "Counselor B", "student": "Student Two", "mode": "Meeting", "status": "pending", "next": "2026-04-30"},
                    {"when": "2026-04-26", "counselor": "Counselor A", "student": "Student Three", "mode": "Email", "status": "follow-up", "next": "2026-05-02"},
                ]

        # v2 "Streams & capacity" page: counts per stream vs configured seat capacity on Institute.
        if (ctx.get("ttv2_page") or "").strip().lower() == "streams_capacity":
            try:
                inst = ctx.get("institute")
                stu_qs = ctx.get("stu")
                stream_counts = {}
                if hasattr(stu_qs, "exclude"):
                    for row in (
                        stu_qs.exclude(class_and_section__stream__isnull=True)
                        .exclude(class_and_section__stream__exact="")
                        .values("class_and_section__stream")
                        .annotate(n=Count("id"))
                    ):
                        key = (row.get("class_and_section__stream") or "").strip().upper()
                        if key:
                            stream_counts[key] = int(row.get("n") or 0)

                # Default known streams with capacities from Institute model
                cap_map = {
                    "PCM": int(getattr(inst, "pcm", 0) or 0),
                    "CBM": int(getattr(inst, "cbm", 0) or 0),
                    "COMM": int(getattr(inst, "comm", 0) or 0),
                    "HME": int(getattr(inst, "hme", 0) or 0),
                    "HMB": int(getattr(inst, "hmb", 0) or 0),
                }

                rows = []
                seen = set()
                for code, cap in cap_map.items():
                    enrolled = int(stream_counts.get(code, 0))
                    rows.append(
                        {
                            "code": code,
                            "label": code,
                            "enrolled": enrolled,
                            "capacity": cap,
                            "remaining": max(0, int(cap) - enrolled) if cap else 0,
                        }
                    )
                    seen.add(code)

                # Include any other streams present in data (capacity unknown -> 0)
                for code, enrolled in sorted(stream_counts.items(), key=lambda x: x[0]):
                    if code in seen:
                        continue
                    rows.append(
                        {
                            "code": code,
                            "label": code,
                            "enrolled": int(enrolled),
                            "capacity": 0,
                            "remaining": 0,
                        }
                    )

                # If no data at all, show dummy disabled rows
                if not rows or all(int(r.get("enrolled", 0)) == 0 for r in rows):
                    ctx["ttv2_streams_capacity_is_dummy"] = True
                    ctx["ttv2_streams_capacity"] = [
                        {"code": "PCM", "label": "PCM", "enrolled": 30, "capacity": 100, "remaining": 70},
                        {"code": "CBM", "label": "CBM", "enrolled": 45, "capacity": 100, "remaining": 55},
                        {"code": "COMM", "label": "COMM", "enrolled": 60, "capacity": 100, "remaining": 40},
                        {"code": "HME", "label": "HME", "enrolled": 20, "capacity": 100, "remaining": 80},
                        {"code": "HMB", "label": "HMB", "enrolled": 10, "capacity": 100, "remaining": 90},
                    ]
                else:
                    ctx["ttv2_streams_capacity_is_dummy"] = False
                    ctx["ttv2_streams_capacity"] = rows
            except Exception:
                ctx["ttv2_streams_capacity_is_dummy"] = True
                ctx["ttv2_streams_capacity"] = [
                    {"code": "PCM", "label": "PCM", "enrolled": 30, "capacity": 100, "remaining": 70},
                    {"code": "CBM", "label": "CBM", "enrolled": 45, "capacity": 100, "remaining": 55},
                    {"code": "COMM", "label": "COMM", "enrolled": 60, "capacity": 100, "remaining": 40},
                    {"code": "HME", "label": "HME", "enrolled": 20, "capacity": 100, "remaining": 80},
                    {"code": "HMB", "label": "HMB", "enrolled": 10, "capacity": 100, "remaining": 90},
                ]

        # v2: allow AJAX refresh of payments page without full reload
        if (
            (ctx.get("ttv2_page") or "").strip().lower() == "payments"
            and (request.GET.get("ttv2_payments_partial") or "").strip() == "1"
        ):
            return render(request, "template_v2/institute/pages/institute_payments.html", ctx)

        # v2 partial rendering for fast AJAX shell boot
        try:
            template_version = (Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1").strip()
        except Exception:
            template_version = "v1"
        if template_version == "v2" and request.GET.get("ttv2_partial") == "1":
            return render(request, "template_v2/dashboard_unified_body.html", ctx)

        return render(request, _dashboard_primary_template_name(self), ctx )
    
    def _results_aux_maps_by_user_id(self, user_ids):
        """Batch-fetch test rows for institute student table; dict keys are user_id (int)."""
        tcm, pmm, rmap = {}, {}, {}
        if not user_ids:
            return tcm, pmm, rmap
        from app.models import TestCompletion, Results
        from app_post_matric.models import TestSession as PostMatricTestSession
        try:
            uids = list({int(x) for x in user_ids if x is not None})
        except (TypeError, ValueError):
            uids = []
        if not uids:
            return tcm, pmm, rmap
        for tc in TestCompletion.objects.filter(user_id__in=uids).select_related("user"):
            tcm[tc.user_id] = tc
        for s in PostMatricTestSession.objects.filter(user_id__in=uids).select_related("user", "test"):
            pmm.setdefault(s.user_id, []).append(s)
        for r in Results.objects.filter(user_id__in=uids).select_related("user"):
            rmap.setdefault(r.user_id, []).append(r)
        return tcm, pmm, rmap

    def _build_results_data_for_managements(self, sm_list, tcm, pmm, rmap):
        out = {}
        for stu in sm_list:
            if not stu.student_id or not stu.student:
                continue
            user = stu.student
            out[user.id] = self._get_student_test_result_optimized(
                user,
                stu,
                tcm.get(stu.student_id),
                pmm.get(stu.student_id) or [],
                rmap.get(stu.student_id) or [],
            )
        return out

    def get_student_table_context_ajax(self, request, *args, **kwargs):
        """
        Lightweight context for the AJAX student table.
        When the "Test taken" filter is off, paginate first and only build test/result
        data for the current page (avoids N× work for large institutes).
        """
        slug = kwargs.get("slug")
        institute = get_object_or_404(Institute, slug=slug)
        stu_manage = (
            get_students_by_role(request.user, institute=institute)
            .select_related("student", "class_and_section", "institute")
            .prefetch_related("counselors")
        )

        stream_filter = request.GET.get("stream", "")
        test_taken_filter = request.GET.get("test_taken", "").strip()

        class_and_sections = get_class_and_sections_by_role(request.user, stu_manage)
        class_counts = get_class_counts(stu_manage)
        unique_streams = get_unique_streams_by_role(request.user, stu_manage)

        # Class / name: DB; do not require results_data yet.
        filtered_students = apply_student_filters(stu_manage, request, results_data=None)
        if stream_filter:
            if hasattr(filtered_students, "filter"):
                filtered_students = filtered_students.filter(
                    class_and_section__stream=stream_filter
                )
            else:
                filtered_students = [
                    s
                    for s in filtered_students
                    if hasattr(s, "class_and_section")
                    and s.class_and_section
                    and s.class_and_section.stream == stream_filter
                ]

        per_page_param = request.GET.get("per_page", "10")
        if per_page_param == "all":
            per_page_value = 10000
        else:
            try:
                per_page_value = int(per_page_param)
            except (ValueError, TypeError):
                per_page_value = 10

        page_number = request.GET.get("page", 1)
        if test_taken_filter:
            if hasattr(filtered_students, "order_by"):
                sm_all = list(
                    filtered_students.select_related(
                        "student", "class_and_section", "institute"
                    ).order_by("-created")
                )
            else:
                sm_all = sorted(
                    list(filtered_students), key=lambda x: x.created, reverse=True
                )
            uids_all = [sm.student_id for sm in sm_all if sm.student_id]
            tcm, pmm, rmap = self._results_aux_maps_by_user_id(uids_all)
            full_results = self._build_results_data_for_managements(
                sm_all, tcm, pmm, rmap
            )
            kept = []
            for sm in sm_all:
                if not sm.student:
                    continue
                tr = full_results.get(sm.student_id, {})
                ts = tr.get("test_status", "no_tests")
                if test_taken_filter == "Yes" and ts == "completed":
                    kept.append(sm)
                elif test_taken_filter == "No" and ts == "no_tests":
                    kept.append(sm)
                elif test_taken_filter == "In Progress" and ts == "in_progress":
                    kept.append(sm)
            pages = Paginator(kept, per_page_value)
        else:
            if isinstance(filtered_students, list):
                pages = Paginator(
                    sorted(filtered_students, key=lambda x: x.created, reverse=True),
                    per_page_value,
                )
            else:
                pages = Paginator(filtered_students.order_by("-created"), per_page_value)

        try:
            total_students = pages.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            total_students = pages.get_page(1)

        if test_taken_filter:
            page_list = list(total_students.object_list)
            results_data = {
                sm.student_id: full_results[sm.student_id]
                for sm in page_list
                if sm.student_id in full_results
            }
        else:
            page_list = list(total_students.object_list)
            page_uids = [sm.student_id for sm in page_list if sm.student_id]
            tcm, pmm, rmap = self._results_aux_maps_by_user_id(page_uids)
            results_data = self._build_results_data_for_managements(
                page_list, tcm, pmm, rmap
            )

        stu_value = (
            filtered_students
            if hasattr(filtered_students, "filter")
            else filtered_students
        )
        return {
            "total_students": total_students,
            "total_students_count": stu_manage.count(),
            "class_and_sections": class_and_sections,
            "class_counts": class_counts,
            "unique_streams": unique_streams,
            "results_data": results_data,
            "stu": stu_value,
            "institute": institute,
            "ttv2_counselor_options": [
                {"id": c.id, "name": getattr(c, "counselor_name", "") or f"Counselor {c.id}"}
                for c in Counselor.objects.filter(counselor_admin=institute).only("id", "counselor_name")
            ],
        }
    
    def post(self, request, *args, **kwargs):
        slug=kwargs.get("slug")
        institute=get_object_or_404(Institute,slug=slug)
        if getattr(institute, "is_system_demo", False):
            messages.error(request, "Demo institute: cannot add new students.")
            ctx = self.get_context(request, *args, **kwargs)
            return render(request, _dashboard_primary_template_name(self), ctx)
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        class_section=request.POST.get("class_section")
        email=request.POST.get("student_email")
        filter_emails=email.replace(" ","").replace("\r\n",'')
        email_list=filter_emails.split(",")
        ctx=self.get_context(request, *args, **kwargs)
        error_list=[]
        for semail in email_list:
            em=re.match(evalid,semail)
            user_exist=User.objects.filter(email=semail).exists()
            if institute.is_valid_credit_count() and class_section and em and not user_exist:
                cas=get_object_or_404(ClassAndSection,id=class_section)
                import random
                password=''.join([str(random.randint(0,10)) for _ in range(6)])
                student=User.objects.create_user(email=semail, password=password)
                student.save()
                stu_manage=StudentManagement(institute=institute,student=student,class_and_section=cas)
                stu_manage.save()
                update_student_data.delay(institute.id,institute.name)
                create_student_and_send_mail.delay(stu_manage.id,semail,password,institute.name,institute.logo.url)
                # messages.success(request, "{} Created".format(semail))
            else:
                if user_exist:
                    messages.error(request,"{} Already Exist !!".format(semail))
                    error_list.append(semail)
                elif not em:
                    messages.error(request,"{} Invalid Email !!".format(semail))
                    error_list.append(semail)
                elif not institute.is_valid_credit_count():
                    messages.info(request,"No remaining credits")
                    error_list.append(semail)
                elif not class_section:
                    messages.info(request,"Class Not Selected")
                else:
                    messages.error(request,"{} Something Went Wrong !!".format(semail))
                    error_list.append(semail)
        ctx["error_list"]=error_list
        create_institute_log.delay(institute.id,error_list,len(email_list))
        return render(request, _dashboard_primary_template_name(self), ctx)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
@method_decorator(institute_authenticated_user_only, name='dispatch')
class AssignStudentToCounselorView(View):
    """
    AJAX endpoint: assign a StudentManagement row to a counselor (M2M Counselor.students).
    """

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads((request.body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}

        sm_id = payload.get("student_management_id")
        counselor_id = payload.get("counselor_id")
        slug = kwargs.get("slug")

        try:
            sm_id = int(sm_id)
            counselor_id = int(counselor_id)
        except Exception:
            return JsonResponse({"ok": False, "error": "invalid_params"}, status=400)

        institute = get_object_or_404(Institute, slug=slug)
        counselor = get_object_or_404(Counselor, id=counselor_id, counselor_admin=institute)
        sm = get_object_or_404(StudentManagement, id=sm_id, institute=institute)

        try:
            counselor.students.add(sm)
        except Exception:
            return JsonResponse({"ok": False, "error": "assign_failed"}, status=500)

        # Notify counselor (in-app + email) about assignment.
        try:
            counselor_user = getattr(counselor, "coun_user", None)
            if counselor_user and getattr(counselor_user, "email", None):
                from notifications.services import emit_notification
                from notifications.models import NotificationCategory
                from communication.com_service import ComService

                student_user = getattr(sm, "student", None)
                student_name = getattr(student_user, "name", None) or getattr(student_user, "email", None) or "Student"
                student_email = getattr(student_user, "email", None) or ""
                inst_name = getattr(institute, "name", None) or "Institute"

                emit_notification(
                    event_type="institute.student_assigned",
                    title="New student assigned",
                    body=f"A new student {student_name} ({student_email}) was assigned to you by {inst_name}.",
                    recipients=[counselor_user],
                    category=NotificationCategory.INSTITUTE,
                    payload={
                        "student_management_id": sm.id,
                        "student_id": getattr(sm, "student_id", None),
                        "institute_id": institute.id,
                        "counselor_id": counselor.id,
                    },
                    source_obj=sm,
                    dedupe_key=f"institute.student_assigned:{sm.id}:{counselor.id}",
                )

                # Email (best-effort)
                try:
                    cs = ComService()
                    subject = cs.build_email_subject("New student assigned")
                    html = (
                        f"<p>Hello {getattr(counselor, 'counselor_name', '') or 'Counselor'},</p>"
                        f"<p><strong>{student_name}</strong> ({student_email}) has been assigned to you by <strong>{inst_name}</strong>.</p>"
                        f"<p>Please login to your counselor dashboard to view details.</p>"
                    )
                    to_list = []
                    try:
                        if counselor_user.email:
                            to_list.append(str(counselor_user.email).strip())
                    except Exception:
                        pass
                    try:
                        if getattr(counselor, "counselor_email", None):
                            to_list.append(str(getattr(counselor, "counselor_email")).strip())
                    except Exception:
                        pass
                    # de-dupe
                    to_list = [x for i, x in enumerate(to_list) if x and x not in to_list[:i]]
                    if to_list:
                        cs.send_mail(subject, to_list, html, html)
                except Exception:
                    pass
        except Exception:
            pass

        return JsonResponse({"ok": True})


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
@method_decorator(institute_authenticated_user_only, name='dispatch')
class SetStudentCounselorView(View):
    """
    AJAX endpoint: change/unassign counselor for a StudentManagement row.

    Payload:
      - student_management_id: int
      - counselor_id: int | null | ''   (if empty -> unassign)
    """

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads((request.body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}

        sm_id = payload.get("student_management_id")
        counselor_id = payload.get("counselor_id")
        slug = kwargs.get("slug")

        try:
            sm_id = int(sm_id)
        except Exception:
            return JsonResponse({"ok": False, "error": "invalid_params"}, status=400)

        # counselor_id can be empty for unassign
        counselor_id_int = None
        try:
            if counselor_id is not None and str(counselor_id).strip() != "":
                counselor_id_int = int(counselor_id)
        except Exception:
            return JsonResponse({"ok": False, "error": "invalid_params"}, status=400)

        institute = get_object_or_404(Institute, slug=slug)
        sm = get_object_or_404(StudentManagement, id=sm_id, institute=institute)

        # Remove from any counselors of this institute (avoid cross-institute bleed)
        try:
            for c in Counselor.objects.filter(counselor_admin=institute, students=sm):
                c.students.remove(sm)
        except Exception:
            return JsonResponse({"ok": False, "error": "unassign_failed"}, status=500)

        # Assign to new counselor if provided
        if counselor_id_int is not None:
            counselor = get_object_or_404(
                Counselor, id=counselor_id_int, counselor_admin=institute
            )
            try:
                counselor.students.add(sm)
            except Exception:
                return JsonResponse({"ok": False, "error": "assign_failed"}, status=500)

            # Notify counselor about assignment (same as assign endpoint)
            try:
                counselor_user = getattr(counselor, "coun_user", None)
                if counselor_user and getattr(counselor_user, "email", None):
                    from notifications.services import emit_notification
                    from notifications.models import NotificationCategory
                    from communication.com_service import ComService

                    student_user = getattr(sm, "student", None)
                    student_name = getattr(student_user, "name", None) or getattr(student_user, "email", None) or "Student"
                    student_email = getattr(student_user, "email", None) or ""
                    inst_name = getattr(institute, "name", None) or "Institute"

                    emit_notification(
                        event_type="institute.student_assigned",
                        title="New student assigned",
                        body=f"A new student {student_name} ({student_email}) was assigned to you by {inst_name}.",
                        recipients=[counselor_user],
                        category=NotificationCategory.INSTITUTE,
                        payload={
                            "student_management_id": sm.id,
                            "student_id": getattr(sm, "student_id", None),
                            "institute_id": institute.id,
                            "counselor_id": counselor.id,
                        },
                        source_obj=sm,
                        dedupe_key=f"institute.student_assigned:{sm.id}:{counselor.id}",
                    )

                    # Email (best-effort)
                    try:
                        cs = ComService()
                        subject = cs.build_email_subject("New student assigned")
                        html = (
                            f"<p>Hello {getattr(counselor, 'counselor_name', '') or 'Counselor'},</p>"
                            f"<p><strong>{student_name}</strong> ({student_email}) has been assigned to you by <strong>{inst_name}</strong>.</p>"
                            f"<p>Please login to your counselor dashboard to view details.</p>"
                        )
                        to_list = []
                        try:
                            if counselor_user.email:
                                to_list.append(str(counselor_user.email).strip())
                        except Exception:
                            pass
                        try:
                            if getattr(counselor, "counselor_email", None):
                                to_list.append(str(getattr(counselor, "counselor_email")).strip())
                        except Exception:
                            pass
                        to_list = [x for i, x in enumerate(to_list) if x and x not in to_list[:i]]
                        if to_list:
                            cs.send_mail(subject, to_list, html, html)
                    except Exception:
                        pass
            except Exception:
                pass

        return JsonResponse({"ok": True})


class InstituteMasterDashboardView(InstituteDashboardView):
    """Institute master dashboard at /institute/<slug>/dashboard/ (heatmap + shell)."""

    template_name = "template20/institute/institute_master_dashboard.html"

    def html_head(self):
        name = "Institute Master Dashboard"
        return build_html_head(title=name, description=name)

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        stu_q = ctx.get("stu")
        rows = []
        if stu_q is not None:
            try:
                rows = list(
                    stu_q.select_related("student", "class_and_section").order_by("-created")[:40]
                )
            except Exception:
                rows = []
        ctx["master_student_rows"] = rows

        tsc = ctx.get("total_students_count")
        n_total = tsc if isinstance(tsc, int) else (len(tsc) if tsc is not None else 0)
        ctx["master_n_students"] = n_total

        sessions_week = 0
        try:
            for block in json.loads(ctx.get("sessions_data_json") or "[]"):
                for day in block.get("sessions") or []:
                    sessions_week += int(day.get("session_count") or 0)
        except (TypeError, ValueError, KeyError):
            sessions_week = 0
        ctx["master_sessions_week_total"] = sessions_week

        trc = ctx.get("test_result_count") or 0
        if n_total:
            ctx["master_psychometric_pct"] = min(100, int(round(100 * float(trc) / float(n_total))))
        else:
            ctx["master_psychometric_pct"] = 0

        cc = ctx.get("class_counts") or {}
        ctx["master_active_classes"] = len(cc) if isinstance(cc, dict) else 0

        inst = ctx.get("institute")
        if inst:
            try:
                ctx["master_credits_remaining"] = int(inst.get_current_credits_count())
            except Exception:
                ctx["master_credits_remaining"] = 0
            ctx["master_credits_total"] = int(inst.credit_counts or 0)
        else:
            ctx["master_credits_remaining"] = 0
            ctx["master_credits_total"] = 0

        streams = ctx.get("streams") or {}
        ctx["master_stream_keys"] = list(streams.keys()) if isinstance(streams, dict) else []
        ctx["master_stream_vals"] = list(streams.values()) if isinstance(streams, dict) else []
        return ctx


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(marketing_group_user_only,name='dispatch')
class InstituteApproveView(View):
    """
    View to approve an institute by changing its status from pending to approved.
    """
    def get(self, request, id):
        referer = request.META.get('HTTP_REFERER') or reverse('institute:marketinggroupdashboard')
        try:
            institute = Institute.objects.get(id=id)
        except Institute.DoesNotExist:
            messages.error(request, "Institute not found.")
            return HttpResponseRedirect(referer)
        if not request.user.is_superuser:
            mg = institute.marketing_group
            if not mg or mg.marketing_group_admin_id != request.user.id:
                messages.error(
                    request,
                    "You can only approve institutes that belong to your marketing group.",
                )
                return HttpResponseRedirect(referer)
        institute.institute_status = choices.InstituteStatus.APPROVED
        institute.save()
        messages.success(request, f"Institute '{institute.name}' has been approved successfully.")
        return HttpResponseRedirect(referer)


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
@method_decorator(marketing_group_user_only, name='dispatch')
class InstituteHardDeleteView(View):
    """
    Permanently remove an institute from the database when it has no student registrations.
    Allowed for superuser or the institute's marketing_group marketing_group_admin.
    """

    http_method_names = ['post']

    def post(self, request, id, *args, **kwargs):
        referer = request.META.get('HTTP_REFERER') or reverse('institute:marketinggroupdashboard')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        def respond_error(message, status=400):
            if is_ajax:
                return JsonResponse({'success': False, 'error': message}, status=status)
            messages.error(request, message)
            return HttpResponseRedirect(referer)

        def respond_success(message):
            if is_ajax:
                return JsonResponse({'success': True, 'message': message})
            messages.success(request, message)
            return HttpResponseRedirect(referer)

        try:
            institute = Institute.objects.get(id=id)
        except Institute.DoesNotExist:
            return respond_error('Institute not found.', 404)

        if getattr(institute, 'is_system_demo', False):
            return respond_error('System demo institutes cannot be deleted.', 403)

        if not request.user.is_superuser:
            mg = institute.marketing_group
            if not mg or mg.marketing_group_admin_id != request.user.id:
                return respond_error(
                    'You can only delete institutes that belong to your marketing group.',
                    403,
                )

        name = institute.name
        try:
            with transaction.atomic():
                locked = Institute.objects.select_for_update().get(pk=institute.pk)
                if StudentManagement.objects.complete().filter(institute_id=locked.pk).exists():
                    return respond_error(
                        'Cannot delete: this institute has student registrations (including inactive rows).',
                    )
                locked.delete(hard_delete=True)
        except Institute.DoesNotExist:
            return respond_error('Institute not found.', 404)
        except Exception:
            return respond_error('Could not delete this institute.', 500)

        return respond_success(f"Institute '{name}' was permanently deleted.")


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_user_only,name='dispatch')
class InstituteStudentCreateView(TemplateView):

    def post(self, request, *args, **kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        mvalid = r'^(\+91|0)?[6789]\d{9}$'

        institute_id=request.POST.get("institute")
        stu_name=request.POST.get("stu_name")
        class_section=request.POST.get("class_section")
        stu_email=request.POST.get("stu_email")
        stu_mobile=request.POST.get("mobile")
        stu_profile=request.FILES.get("profile_pic")
        institute=get_object_or_404(Institute,id=institute_id)
        if getattr(institute, "is_system_demo", False):
            messages.error(request, "Demo institute: cannot add new students.")
            return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
        if stu_name and stu_email and stu_mobile and stu_profile:
            stu_exist=User.objects.filter(email=stu_email).exists()
            stu_em=re.match(evalid,stu_email)
            stu_mob=re.match(mvalid,stu_mobile)
            if institute.is_valid_credit_count() and stu_em and stu_mob and class_section and not stu_exist:                
                if class_section:
                    cas,_cas=ClassAndSection.objects.get_or_create(class_and_section=class_section)
                else:
                    cas=get_object_or_404(ClassAndSection,id=class_section)               

                import random
                password=''.join([str(random.randint(0,10)) for _ in range(6)])                
                user_dict={'name':stu_name,'mobile':stu_mobile,'image':stu_profile,'email':stu_email,'password':password}
                student=User.create_user(**user_dict)
                stu_manage=StudentManagement(institute=institute,student=student,class_and_section=cas)
                stu_manage.save()
                update_student_data.delay(institute.id,institute.name)
                create_student_and_send_mail.delay(stu_manage.id,stu_email,password,institute.name,institute.logo.url)
            else:
                if stu_exist:
                    messages.error(request,"{} Already Exist !!".format(stu_email))
                elif not institute.is_valid_credit_count():
                    messages.error(request,"No remaining credits")
                elif not stu_em:
                    messages.error(request,"{} Invalid Email !!".format(stu_email))
                elif not stu_mob:
                    messages.error(request,"Invalid Mobile Number !!")
                elif not class_section:
                    messages.error(request,"Class Not Selected")
                else:
                    messages.error(request,"Something Went Wrong !!")
        else:
            messages.error(request,"Not saved")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_user_only,name='dispatch')
class InstituteCsvStudentCreateView(TemplateView):

    def post(self, request, *args, **kwargs):
        import re
        import random
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        mvalid = r'^(\+91|0)?[6789]\d{9}$'
        institute_id=request.POST.get("institute")
        institute=get_object_or_404(Institute,id=institute_id)
        if getattr(institute, "is_system_demo", False):
            messages.error(request, "Demo institute: cannot add new students.")
            return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
        csv_file=request.FILES.get('stu_file')
        
        # Validate file exists
        if not csv_file:
            messages.error(request, "No file uploaded")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        # Try to decode the file with error handling
        file_content = csv_file.read()
        try:
            csvfile=file_content.decode('utf-8').splitlines()
        except UnicodeDecodeError:
            try:
                csvfile=file_content.decode('utf-8-sig').splitlines()
            except:
                csvfile=file_content.decode('latin-1').splitlines()
        
        import csv
        stu_file=csv.reader(csvfile)
        
        # Get and normalize headers
        try:
            header_raw=next(stu_file)
            # Normalize headers: strip whitespace and convert to lowercase
            header = [h.strip().lower() for h in header_raw]
        except StopIteration:
            messages.error(request, "CSV file is empty")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        # Validate required headers
        required_headers = ['name', 'mobile', 'class_and_section']
        missing_headers = [h for h in required_headers if h not in header]
        if missing_headers:
            messages.error(request, f"CSV file is missing required columns: {', '.join(missing_headers)}. Required columns are: name, mobile, class_and_section. Email is optional.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        error_list=[]
        email_list=[]
        row_number = 1  # Track row number for better error messages
        
        for stu in stu_file:
            row_number += 1
            # Skip empty rows
            if not any(stu) or len(stu) == 0:
                continue
            
            email_list.append(stu)
            # Normalize values: strip whitespace and handle empty strings
            stu_d={header[i]:s.strip() if s and s.strip() else None for i,s in enumerate(stu) if i < len(header)}
            stu_name=stu_d.get('name')
            stu_mobile=stu_d.get('mobile')
            stu_email=stu_d.get('email')
            class_section=stu_d.get('class_and_section')

            # If email is not present, generate a random email using the student's name
            if not stu_email:
                random_number = str(random.randint(1000, 9999))
                if stu_name:
                    stu_email = f"{stu_name.lower().replace(' ', '_')}_{random_number}@yopmail.com"
                else:
                    # If name is also missing, use a default
                    stu_email = f"student_{random_number}@yopmail.com"
            
            if stu_name and stu_email and stu_mobile and class_section:
                stu_exist=User.objects.filter(email=stu_email).exists()
                stu_em=re.match(evalid,stu_email)
                stu_mob=re.match(mvalid,stu_mobile)
                if institute.is_valid_credit_count() and stu_em and stu_mob and class_section and not stu_exist:
                    cas,_cas=ClassAndSection.objects.get_or_create(class_and_section=class_section)
                    
                    password=''.join([str(random.randint(0,10)) for _ in range(6)])
                    user_dict={'name':stu_name,'mobile':stu_mobile,'email':stu_email,'password':password}
                    student=User.create_user(**user_dict)
                    stu_manage=StudentManagement(institute=institute,student=student,class_and_section=cas)
                    stu_manage.save()
                    update_student_data.delay(institute.id,institute.name)
                    create_student_and_send_mail.delay(stu_manage.id,stu_email,password,institute.name,institute.logo.url)
                else:
                    if stu_exist:
                        messages.error(request,"{} Already Exist !!".format(stu_email))
                        error_list.append(stu_email)
                    elif not institute.is_valid_credit_count():
                        messages.error(request,"No remaining credits")
                        error_list.append(stu_email)
                    elif not stu_em:
                        messages.error(request,"{} Invalid Email !!".format(stu_email))
                        error_list.append(stu_email)
                    elif not stu_mob:
                        messages.error(request,"Invalid Mobile Number !!")
                        error_list.append(stu_email)
                    elif not class_section:
                        messages.error(request,"Class Not Selected")
                        error_list.append(stu_email)
                    else:
                        messages.error(request,"Something Went Wrong !!")
                        error_list.append(stu_email)
            else:
                # Provide specific error message about what's missing
                missing_fields = []
                if not stu_name:
                    missing_fields.append("name")
                if not stu_mobile:
                    missing_fields.append("mobile")
                if not class_section:
                    missing_fields.append("class_and_section")
                
                error_msg = f"Row {row_number}: Missing required fields - {', '.join(missing_fields)}"
                messages.error(request, error_msg)
                error_list.append(f"Row {row_number}: {error_msg}")
        
        create_institute_log.delay(institute.id,error_list,len(email_list))
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


# Post-Matric csv upload

def get_gender_value(gender_str):
    if not gender_str:
        return choices.GenderChoices.UNKNOWN
    gender_str = gender_str.strip().lower()
    if gender_str in ['m', 'male']:
        return choices.GenderChoices.MALE
    elif gender_str in ['f', 'female']:
        return choices.GenderChoices.FEMALE
    else:
        return choices.GenderChoices.UNKNOWN
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_user_only,name='dispatch')
class InstitutePostMatricCsvStudentCreateView(TemplateView):

    def post(self, request, *args, **kwargs):
        import re
        import random
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        mvalid = r'^(\+91|0)?[6789]\d{9}$'
        institute_id=request.POST.get("institute")
        institute=get_object_or_404(Institute,id=institute_id)
        csv_file=request.FILES.get('stu_file')
        
        # Validate file exists
        if not csv_file:
            messages.error(request, "No file uploaded")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        # Try to decode the file with error handling
        file_content = csv_file.read()
        try:
            csvfile=file_content.decode('utf-8').splitlines()
        except UnicodeDecodeError:
            try:
                csvfile=file_content.decode('utf-8-sig').splitlines()
            except:
                csvfile=file_content.decode('latin-1').splitlines()
        
        import csv
        stu_file=csv.reader(csvfile)
        
        # Get and normalize headers
        try:
            header_raw=next(stu_file)
            # Normalize headers: strip whitespace and convert to lowercase
            header = [h.strip().lower() for h in header_raw]
        except StopIteration:
            messages.error(request, "CSV file is empty")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        # Validate required headers for post-matric
        required_headers = ['name', 'mobile', 'class_and_section']
        missing_headers = [h for h in required_headers if h not in header]
        if missing_headers:
            messages.error(request, f"CSV file is missing required columns: {', '.join(missing_headers)}. Required columns are: name, mobile, class_and_section. Email and gender are optional.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        error_list=[]
        email_list=[]
        row_number = 1  # Track row number for better error messages
        
        for stu in stu_file:
            row_number += 1
            # Skip empty rows
            if not any(stu) or len(stu) == 0:
                continue
            
            email_list.append(stu)
            # Normalize values: strip whitespace and handle empty strings
            stu_d={header[i]:s.strip() if s and s.strip() else None for i,s in enumerate(stu) if i < len(header)}
            stu_name=stu_d.get('name')
            stu_mobile=stu_d.get('mobile')
            stu_email=stu_d.get('email')
            stu_gender=stu_d.get('gender')
            class_section_stream=stu_d.get('stream')
            class_section=stu_d.get('class_and_section')

            # If email is not present, generate a random email using the student's name
            if not stu_email:
                random_number = str(random.randint(1000, 9999))
                if stu_name:
                    stu_email = f"{stu_name.lower().replace(' ', '_')}_{random_number}@yopmail.com"
                else:
                    # If name is also missing, use a default
                    stu_email = f"student_{random_number}@yopmail.com"
            
            if stu_name and stu_email and stu_mobile and class_section:
                stu_exist=User.objects.filter(email=stu_email).exists()
                stu_em=re.match(evalid,stu_email)
                stu_mob=re.match(mvalid,stu_mobile)
                if institute.is_valid_credit_count() and stu_em and stu_mob and class_section and not stu_exist:
                    cas,_cas=ClassAndSection.objects.get_or_create(class_and_section=class_section,stream=class_section_stream)
                    
                    password=''.join([str(random.randint(0,10)) for _ in range(6)])
                    user_dict={'name':stu_name,'mobile':stu_mobile,'email':stu_email,'password':password}
                    student=User.create_user(**user_dict)
                    user_profile, created = UserProfile.objects.get_or_create(user=student)
                    if stu_gender:
                        stu_gender_raw = stu_d.get('gender')
                        stu_gender = get_gender_value(stu_gender_raw)
                        user_profile.gender = stu_gender
                        user_profile.save()
                    stu_manage=StudentManagement(institute=institute,student=student,class_and_section=cas)
                    stu_manage.save()
                    update_student_data.delay(institute.id,institute.name)
                    create_student_and_send_mail.delay(stu_manage.id,stu_email,password,institute.name,institute.logo.url)
                else:
                    if stu_exist:
                        messages.error(request,"{} Already Exist !!".format(stu_email))
                        error_list.append(stu_email)
                    elif not institute.is_valid_credit_count():
                        messages.error(request,"No remaining credits")
                        error_list.append(stu_email)
                    elif not stu_em:
                        messages.error(request,"{} Invalid Email !!".format(stu_email))
                        error_list.append(stu_email)
                    elif not stu_mob:
                        messages.error(request,"Invalid Mobile Number !!")
                        error_list.append(stu_email)
                    elif not class_section:
                        messages.error(request,"Class Not Selected")
                        error_list.append(stu_email)
                    else:
                        messages.error(request,"Something Went Wrong !!")
                        error_list.append(stu_email)
            else:
                # Provide specific error message about what's missing
                missing_fields = []
                if not stu_name:
                    missing_fields.append("name")
                if not stu_mobile:
                    missing_fields.append("mobile")
                if not class_section:
                    missing_fields.append("class_and_section")
                
                error_msg = f"Row {row_number}: Missing required fields - {', '.join(missing_fields)}"
                messages.error(request, error_msg)
                error_list.append(f"Row {row_number}: {error_msg}")
        
        create_institute_log.delay(institute.id,error_list,len(email_list))
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))



@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_update_delete_student_only,name='dispatch')
class InstituteStudentUpdateView(TemplateView):
    def post(self, request, *args, **kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        mvalid = r'^(\+91|0)?[6789]\d{9}$'
        id=request.POST.get("user_id")
        
        print("id",id)
        user=get_object_or_404(User,id=id)
        upd_name=request.POST.get("upd_name")
        upd_email=request.POST.get("upd_email")
        upd_class=request.POST.get("class_section")
        upd_mobile=request.POST.get("upd_mobile")
        upd_profile_pic=request.FILES.get("upd_profile_pic")
        upd_em=re.match(evalid,upd_email)
        upd_mob=re.match(mvalid,upd_mobile)
        upd_exist=User.objects.filter(email=upd_email).exists()
        if (upd_name or upd_em or upd_mob or upd_profile_pic or upd_class):
            if upd_name:
                user.name=upd_name
            if upd_em and not upd_exist:         
                user.email=upd_email
            if upd_mob:
                user.mobile=upd_mobile
            if upd_profile_pic:
                user.image=upd_profile_pic
            if upd_class:
                stu=get_object_or_404(StudentManagement,student=user)
                cas=get_object_or_404(ClassAndSection,id=upd_class)
                stu.class_and_section=cas
                stu.save()
            user.save()
        else:
            if upd_exist:
                messages.error(request,"Try another email")
            else:
                messages.error(request,"Something Went Wrong !!")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_update_delete_student_only,name='dispatch')
class InstituteStudentDeleteView(TemplateView):
    def post(self, request, *args, **kwargs):

        
        id=request.POST.get("user_id")
        user=get_object_or_404(User,id=id)
        stu_manage=get_object_or_404(StudentManagement,student=user)
        stu_manage.delete()
        user.delete()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_change_student_password_only,name='dispatch')  
class InstituteStudentChangePasswordView(TemplateView):
    def post(self, request, *args, **kwargs):
        id=request.POST.get("password_id")
        password=request.POST.get("change_password")
        user=get_object_or_404(User,id=id)
        user.set_password(password)
        user.save()
        send_new_student_credential.delay(user.email,password)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(change_counselor_password_only,name='dispatch')  
class CounselorChangePasswordView(TemplateView):
    def post(self, request, *args, **kwargs):
        
        id=request.POST.get("password_id")
        password=request.POST.get("change_password")
        user=get_object_or_404(User,id=id)
        user.set_password(password)
        user.save()
        # send_new_student_credential.delay(user.email,password)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_block_student_only,name='dispatch')  
class InstituteStudentBlockView(TemplateView):
    def get(self,request,*args,**kwargs):
        id=kwargs.get("id")
        stu=get_object_or_404(User,id=id)
        if stu.user_status==choices.UserStatus.UNBLOCK:
            stu.user_status=choices.UserStatus.BLOCK
            stu.save()
        else:
            stu.user_status=choices.UserStatus.UNBLOCK
            stu.save()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(marketing_group_user_only,name='dispatch')
class UpdateSeatCapacityView(View):
    """View to update seat capacity for an institute via AJAX"""
    
    def post(self, request, *args, **kwargs):
        try:
            institute_id = request.POST.get('institute_id')
            pcm = request.POST.get('pcm')
            cbm = request.POST.get('cbm')
            comm = request.POST.get('comm')
            hme = request.POST.get('hme')
            hmb = request.POST.get('hmb')
            
            if not institute_id:
                return JsonResponse({'success': False, 'error': 'Institute ID is required'}, status=400)
            
            # Get the institute
            institute = get_object_or_404(Institute, id=institute_id)
            
            # Verify the institute belongs to the user's marketing group
            group_admin = request.user
            marketing_group = InstituteMarketingGroup.objects.filter(
                marketing_group_admin=group_admin
            ).first()
            
            if not marketing_group or institute.marketing_group != marketing_group:
                return JsonResponse({'success': False, 'error': 'Unauthorized access'}, status=403)
            
            # Update seat capacity fields
            if pcm is not None:
                institute.pcm = int(pcm)
            if cbm is not None:
                institute.cbm = int(cbm)
            if comm is not None:
                institute.comm = int(comm)
            if hme is not None:
                institute.hme = int(hme)
            if hmb is not None:
                institute.hmb = int(hmb)
            
            institute.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Seat capacity updated successfully',
                'data': {
                    'pcm': institute.pcm,
                    'cbm': institute.cbm,
                    'comm': institute.comm,
                    'hme': institute.hme,
                    'hmb': institute.hmb
                }
            })
            
        except ValueError as e:
            return JsonResponse({'success': False, 'error': f'Invalid value: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(marketing_group_user_only,name='dispatch') 
class InstituteProfileEditView(TemplateView):
    def post(self,request,*args,**kwargs):
        ins_id=request.POST.get("institute_id")
        ins_name=request.POST.get("institute_name")
        ins_address=request.POST.get("institute_address")
        ins_contact=request.POST.get("institute_contact")
        ins_admin=request.POST.get("institute_admin")
        ins_credits=request.POST.get("upd_credits")
        ins_group=request.POST.get("institute_group")
        ins_logo=request.FILES.get("institute_logo")
        ins=get_object_or_404(Institute,id=ins_id)
        if ins_name or ins_address or ins_contact or ins_admin or ins_logo or ins_credits or ins_group:
            if ins_name:
                update_student_data.delay(ins.id,ins_name)
                ins.name=ins_name
            if ins_address:
                ins.address=ins_address
            if ins_contact:
                ins.contact_info=ins_contact
            if ins_admin:
                ins.administrator_contact=ins_admin
            if ins_credits and (0<=int(ins_credits)<=(ins.credit_counts+get_global_remain_credits())):
                ins.credit_counts=ins_credits
            if ins_group:
                institute_group=get_object_or_404(InstituteGroup,id=ins_group)
                ins.institute_group=institute_group
            if ins_logo:
                ins.logo=ins_logo
            ins.save()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_profile_update_delete,name='dispatch') 
class InstituteDeletionView(TemplateView):
    def post(self,request,*args,**kwargs):
        ins_id=request.POST.get("institute_id")
        ins=get_object_or_404(Institute,id=ins_id)
        ins_reason=request.POST.get("ins_reason")
        if ins and ins_reason:
            ins_del=InstituteAccountDeletion(institute=ins,reason=ins_reason)
            ins_del.save()
            institute_deletion_request.delay(ins_id,ins.name,ins_reason)
            messages.success(request, "Sent Account Deletion Request")
        else:
            messages.error(request,"Something Went Wrong !!")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
class CreateClassSectionView(TemplateView):
    def post(self,request,*args,**kwargs):
        cl=request.POST.get("create_class")
        cas=ClassAndSection(class_and_section=cl)
        cas.save()
        messages.success(request, "New Class Created")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_authenticated_user_only,name='dispatch')
class InstituteHistoryLogView(TemplateView):
    # template_name="topteenfrontend/user/institute_log.html"
    template_name="template20/institute/institute_history_log.html"

    def html_head(self):
        name='Institute Logs'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        slug=kwargs.get("slug")
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx["institute_logs"]=InstituteLog.objects.filter(institute__slug=slug).order_by("-created")
        return ctx
    
    def get(self,request,*args,**kwargs):
        return render(request, _dashboard_primary_template_name(self), self.get_context(request, *args, **kwargs))


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
@method_decorator(marketing_group_user_only, name='dispatch')
class MarketingGroupHeatmapView(TemplateView):
    """
    Dedicated Heatmap page for Marketing Group users.
    Reuses the same heatmap UI/JS as the dashboard, but on its own page.
    """
    template_name = "template20/institute/marketing_group_heatmap.html"

    def get_template_names(self):
        return [
            _dashboard_template(
                "template20/institute/marketing_group_heatmap.html",
                "template_v2/institute/marketing_group_heatmap.html",
            )
        ]

    def html_head(self):
        name = "Heatmap | Marketing Group"
        return build_html_head(title=name, description=name)

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        try:
            template_version = (
                Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1"
            ).strip()
        except Exception:
            template_version = "v1"
        if template_version == "v2" and request.GET.get("ttv2_partial") == "1":
            return render(request, "template_v2/institute/marketing_group_heatmap_body.html", ctx)
        return render(request, _dashboard_primary_template_name(self), ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["html_head"] = self.html_head()
        return ctx


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
@method_decorator(institute_group_user_only, name="dispatch")
class InstituteGroupHeatmapView(TemplateView):
    """Dedicated heatmap page for institute-group admins (aggregated group data)."""

    template_name = "template20/institute/institute_group_heatmap.html"

    def get_template_names(self):
        return [
            _dashboard_template(
                "template20/institute/institute_group_heatmap.html",
                "template_v2/institute/institute_group_heatmap.html",
            )
        ]

    def html_head(self):
        name = "Heatmap | Institute Group"
        return build_html_head(title=name, description=name)

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        try:
            template_version = (
                Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1"
            ).strip()
        except Exception:
            template_version = "v1"
        if template_version == "v2" and request.GET.get("ttv2_partial") == "1":
            return render(request, "template_v2/institute/institute_group_heatmap_body.html", ctx)
        return render(request, _dashboard_primary_template_name(self), ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["html_head"] = self.html_head()
        return ctx


@method_decorator(login_required(login_url=reverse_lazy("users:login")), name="dispatch")
@method_decorator(institute_authenticated_user_only, name="dispatch")
class InstituteHeatmapView(TemplateView):
    """Dedicated heatmap page for a single institute (scoped by URL slug)."""

    template_name = "template20/institute/institute_heatmap.html"

    def get_template_names(self):
        return [
            _dashboard_template(
                "template20/institute/institute_heatmap.html",
                "template_v2/institute/institute_heatmap.html",
            )
        ]

    def html_head(self):
        return build_html_head(
            title="Heatmap | Institute",
            description="Career education analytics heatmap.",
        )

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        try:
            template_version = (
                Configuration.get("DASHBOARD_TEMPLATE_VERSION", "v1", editable=True) or "v1"
            ).strip()
        except Exception:
            template_version = "v1"
        if template_version == "v2" and request.GET.get("ttv2_partial") == "1":
            return render(request, "template_v2/institute/institute_heatmap_body.html", ctx)
        return render(request, _dashboard_primary_template_name(self), ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        slug = kwargs.get("slug")
        ctx["institute"] = get_object_or_404(Institute, slug=slug)
        ctx["html_head"] = self.html_head()
        return ctx


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class StudentData(APIView):
    def post(self,request,*args,**kwargs):
        id=request.POST.get("id")
        stu = StudentManagement.objects.filter(student__id=id).select_related(
            'institute', 'student', 'class_and_section'
        ).first()
        if not stu:
            return JsonResponse({"success": "false", "error": "Not found"}, status=404)
        if not user_manages_institute_for_api(request.user, stu.institute):
            return JsonResponse({"success": "false", "error": "Forbidden"}, status=403)
        if stu.class_and_section is not None:
            response={"success":"true","name":stu.student.name,"email":stu.student.email,"mobile":stu.student.mobile,"class_id":stu.class_and_section.id,"class":stu.class_and_section.class_and_section}
        else:
            response={"success":"true","name":stu.student.name,"email":stu.student.email,"mobile":stu.student.mobile,"class":"Not Selected"}
        return JsonResponse(response)

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class InstituteData(APIView):
    def post(self,request,*args,**kwargs):
        id=request.POST.get("id")
        ins = Institute.objects.filter(id=id).select_related(
            'institute_group', 'marketing_group', 'created_by'
        ).first()
        if not ins:
            return JsonResponse({"success": "false", "error": "Not found"}, status=404)
        if not user_manages_institute_for_api(request.user, ins):
            return JsonResponse({"success": "false", "error": "Forbidden"}, status=403)
        response={"success":"true","name":ins.name,"address":ins.address,"contact_info":ins.contact_info,"admin_contact":ins.administrator_contact,"credits":ins.credit_counts}
        if ins.institute_group:
            response["ins_group"]=ins.institute_group.group_name
            response["ins_group_id"]=ins.institute_group.id
        return JsonResponse(response)
    
def students_csv_sample_file(request):
    import os
    try:
        # Try multiple possible locations for the CSV file
        base_dir = settings.BASE_DIR
        possible_paths = [
            os.path.join(base_dir, "student_sample_data.csv"),
            os.path.join(base_dir, "scripts", "student_sample_data.csv"),
            os.path.join(base_dir, "static", "student_sample_data.csv"),
            os.path.join(base_dir, "demo-topteens", "student_sample_data.csv"),
        ]
        
        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                break
        
        if not file_path:
            # Create a sample CSV if file doesn't exist
            sample_content = "Email,Name,Mobile,class_and_section\nstudent1@example.com,Student One,9876543210,10th A\nstudent2@example.com,Student Two,9876543211,10th B"
            response = HttpResponse(sample_content, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="Student sample data.csv"'
            return response
        
        with open(file_path, 'r', encoding='utf-8') as file:
            response = HttpResponse(file.read(), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="Student sample data.csv"'
            return response
    except Exception as e:
        print("---Error downloading student sample CSV----", e)
        # Return a basic sample CSV even if file read fails
        sample_content = "Email,Name,Mobile,class_and_section\nstudent1@example.com,Student One,9876543210,10th A\nstudent2@example.com,Student Two,9876543211,10th B"
        response = HttpResponse(sample_content, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="Student sample data.csv"'
        return response
    
def post_matric_student_sample_data(request):
    import os
    try:
        # Try multiple possible locations for the CSV file
        base_dir = settings.BASE_DIR
        possible_paths = [
            os.path.join(base_dir, "post_matric_student_sample_data.csv"),
            os.path.join(base_dir, "scripts", "post_matric_student_sample_data.csv"),
            os.path.join(base_dir, "static", "post_matric_student_sample_data.csv"),
            os.path.join(base_dir, "demo-topteens", "post_matric_student_sample_data.csv"),
        ]
        
        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                break
        
        if not file_path:
            # Create a sample CSV if file doesn't exist
            sample_content = "Email,Name,Mobile,class_and_section,Stream,Gender\nstudent1@example.com,Student One,9876543210,11th,PCM,M\nstudent2@example.com,Student Two,9876543211,12th,COMM,F"
            response = HttpResponse(sample_content, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="Post Matric Student sample data.csv"'
            return response
        
        with open(file_path, 'r', encoding='utf-8') as file:
            response = HttpResponse(file.read(), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="Post Matric Student sample data.csv"'
            return response
    except Exception as e:
        print("---Error downloading post-matric sample CSV----", e)
        # Return a basic sample CSV even if file read fails
        sample_content = "Email,Name,Mobile,class_and_section,Stream,Gender\nstudent1@example.com,Student One,9876543210,11th,PCM,M\nstudent2@example.com,Student Two,9876543211,12th,COMM,F"
        response = HttpResponse(sample_content, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="Post Matric Student sample data.csv"'
        return response
    
# def CounselorDashboard(request):    
#     return render(request, 'topteenfrontend/user/app/counselor_dashboard.html')

# def CounselorCourse(request):    
#     return render(request, 'topteenfrontend/user/app/counselor-course.html')

# old code not in use - start
# New isolated views for institute authentication frontend
# old code not in use - end

class InstituteRegisterView(TemplateView):
    """
    View to render institute registration page
    """
    template_name = 'institute/register.html'
    
    def html_head(self):
        name = 'Institute Registration'
        return build_html_head(title=name, description=name)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['html_head'] = self.html_head()
        # old code not in use - start
        # Add marketing groups and institute types for dropdowns
        # old code not in use - end
        from institute.models import InstituteMarketingGroup
        context['marketing_groups'] = InstituteMarketingGroup.objects.all()
        context['institute_types'] = choices.InstituteType.CHOICES
        return context


class InstituteLoginView(TemplateView):
    """
    View to render institute login page
    """
    template_name = 'institute/login.html'
    
    def html_head(self):
        name = 'Institute Login'
        return build_html_head(title=name, description=name)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['html_head'] = self.html_head()
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
            from users.demo_accounts import get_demo_institute_login_context
            context.update(get_demo_institute_login_context(self.request))
        else:
            context["demo_accounts"] = []
            context["demo_login_url"] = ""
            context["demo_csrf_token"] = ""
        return context


# old code not in use - start
# New isolated views for marketing authentication frontend
# old code not in use - end

class MarketingRegisterView(TemplateView):
    """
    View to render marketing registration page
    """
    template_name = 'marketing/register.html'
    
    def html_head(self):
        name = 'Marketing Registration'
        return build_html_head(title=name, description=name)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['html_head'] = self.html_head()
        return context


class MarketingLoginView(TemplateView):
    """
    View to render marketing login page
    """
    template_name = 'marketing/login.html'
    
    def html_head(self):
        name = 'Marketing Login'
        return build_html_head(title=name, description=name)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['html_head'] = self.html_head()
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
            from users.demo_accounts import get_demo_login_context
            from core import choices
            context.update(get_demo_login_context(
                self.request,
                user_types=[choices.UserType.MARKETINGGROUPADMIN],
            ))
        else:
            context["demo_accounts"] = []
            context["demo_login_url"] = ""
            context["demo_csrf_token"] = ""
        return context


@login_required(login_url=reverse_lazy('users:login'))
def get_heatmap_data_api(request):
    """
    API endpoint to get heatmap data for institute, marketing group, or individual institute
    """
    try:
        user = request.user
        demographic_type = request.GET.get('demographic_type', 'grade')  # grade, section, or stream
        institute_slug = request.GET.get('institute_slug', None)  # For individual institute
        
        # If institute_slug is provided, get data for that specific institute
        if institute_slug:
            try:
                institute = Institute.objects.get(slug=institute_slug)
                # Verify user has access to this institute
                if not (institute.created_by == user or 
                       (institute.institute_group and institute.institute_group.institute_group_admin == user) or
                       (institute.marketing_group and institute.marketing_group.marketing_group_admin == user)):
                    return JsonResponse({'error': 'Unauthorized access to institute'}, status=403)
                
                heatmap_data = get_heatmap_data_for_institute(institute, demographic_type)
                return JsonResponse(heatmap_data, safe=False)
            except Institute.DoesNotExist:
                return JsonResponse({'error': 'Institute not found'}, status=404)
        
        # Otherwise, check for group admin
        # Check if user is institute group admin
        institute_group = InstituteGroup.objects.filter(institute_group_admin=user).first()
        if institute_group:
            group_type = 'institute'
        else:
            # Check if user is marketing group admin
            marketing_group = InstituteMarketingGroup.objects.filter(marketing_group_admin=user).first()
            if marketing_group:
                group_type = 'marketing'
            else:
                # Check if user is an institute user (individual institute)
                institute = Institute.objects.filter(created_by=user).first()
                if institute:
                    heatmap_data = get_heatmap_data_for_institute(institute, demographic_type)
                    return JsonResponse(heatmap_data, safe=False)
                # Marketing / institute-group dashboards load this API before an org row may exist
                ut = getattr(user, 'user_type', None)
                if ut == choices.UserType.MARKETINGGROUPADMIN or ut == choices.UserType.INSTITUTEGROUPADMIN:
                    return JsonResponse(get_empty_heatmap_data(), safe=False)
                return JsonResponse({'error': 'User is not authorized'}, status=403)
        
        # Get heatmap data for group
        heatmap_data = get_heatmap_data_for_group(user, group_type, demographic_type)
        
        return JsonResponse(heatmap_data, safe=False)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)