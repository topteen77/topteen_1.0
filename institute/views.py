from datetime import datetime, timedelta
import json
from django.shortcuts import render
from rest_framework.views import APIView
from django.http import JsonResponse
from django.views.generic import TemplateView,View
from counselor.models import Counselor, FollowUpStatus
from counselor.views import get_students_by_role, apply_student_filters, get_class_and_sections_by_role, get_class_counts, get_results_data_for_students, get_unique_streams_by_role
from users.models import User, UserProfile
from core import choices
from psychometric_tests.models import PsychometricTestResult,CentralTestCandidate
from django.core.paginator import Paginator
from core.utils import build_html_head
from django.contrib import messages
from .task import send_new_student_credential,institute_deletion_request,create_student_and_send_mail,send_institute_mail
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from institute.decorators import change_counselor_password_only, institute_user_only,institute_authenticated_user_only,institute_block_student_only,institute_update_delete_student_only,institute_change_student_password_only,institute_profile_update_delete, marketing_group_user_only,only_superuser,institute_group_user_only
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.views import View
from institute.task import update_student_data,create_institute_log,send_institute_group_mail
from institute.models import Institute,StudentManagement,InstituteAccountDeletion,ClassAndSection,InstituteLog,get_global_remain_credits,InstituteGroup,InstituteMarketingGroup
from django.conf import settings
from django.http import HttpResponse
from institute.filters import StudentFilter
from django.db.models import Count
from django.utils import timezone
from app.models import Results, TestCompletion
from institute.utils import get_heatmap_data_for_group, get_heatmap_data_for_institute
# Create your views here.

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
@method_decorator(only_superuser,name='dispatch')
class InstituteCreateView(TemplateView):
    template_name = 'template20/institute/marketing_group_dashboard.html'
    
    def get(self, request, *args, **kwargs):
        # Redirect to marketing dashboard if accessed via GET
        return HttpResponseRedirect(reverse('institute:marketinggroupdashboard'))
    
    def post(self,request,*args,**kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        ins_email=request.POST.get("institute_email")
        # ins_user=get_object_or_404(User,id=user_id)
        name= request.POST.get("institute_name")
        address=request.POST.get("institute_address")
        contact=request.POST.get("institute_contact")
        admin_contact=request.POST.get("institute_admin")
        credit_counts=request.POST.get("ins_credits")
        institute_group_id=request.POST.get("institute_group")
        logo=request.FILES.get("institute_logo")
        ins_em=re.match(evalid,ins_email)
        if ins_em and name and address and contact and admin_contact and logo and (0<=int(credit_counts)<=get_global_remain_credits()):
            # Attach institute to selected institute group (if any)
            if institute_group_id:
                ins_group=get_object_or_404(InstituteGroup,id=institute_group_id)
            else:
                ins_group=None

            # Attach institute to the marketing group of the logged-in marketing admin
            marketing_group = InstituteMarketingGroup.objects.filter(
                marketing_group_admin=request.user
            ).first()

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
            if User.objects.filter(email=ins_email).exists():
                messages.error(request,"{} Already Exist !!".format(ins_email))
            elif not (int(credit_counts)<=get_global_remain_credits()):
                messages.error(request,"No Remaining Credits")
            else:
                messages.error(request,"Something Went Wrong !!")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

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
        # Get marketing group
        marketing_group = InstituteMarketingGroup.objects.filter(
            marketing_group_admin=group_admin
        ).first()
        
        if not marketing_group:
            return {
                "institutes": Institute.objects.none(),
                "student_count": 0,
                "counselor_count": 0,
                "institute_data": [],
                "tstudents": StudentManagement.objects.none(),
                "streams": {},
                "locations": []
            }
        
        # Start with base queryset
        institutes = Institute.objects.filter(marketing_group=marketing_group)
        
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
                institute__marketing_group=marketing_group
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
                institute__marketing_group=marketing_group
            ).count() if not load_full_data else tstudents.count(),
            "counselor_count": Counselor.objects.filter(
                counselor_admin__marketing_group=marketing_group
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
        search_params = {
            'institute': request.GET.get('institute', '').strip(),
            'location': request.GET.get('location', '').strip(),
            'location_search': request.GET.get('location_search', '').strip()
        }
        
        # Check what data is being requested
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        data_type = request.GET.get('data_type', '')  # 'institutes', 'stats', 'charts', 'seat_capacity'
        
        # For initial page load, use lightweight mode
        if not is_ajax:
            # Lightweight initial load - minimal queries
            group_admin = request.user
            marketing_group = InstituteMarketingGroup.objects.filter(
                marketing_group_admin=group_admin
            ).first()
            
            if marketing_group:
                # Quick counts only - no full data loading
                ctx.update({
                    'total_institute_count': Institute.objects.filter(marketing_group=marketing_group).count(),
                    'total_stu_count': None,  # Will load via AJAX
                    'counselors_count': None,  # Will load via AJAX
                    'institutes': [],
                    'total_students_count': None,
                    'test_result_count': None,
                    'streams': {},
                    'locations': list(Institute.objects.filter(
                        marketing_group=marketing_group
                    ).values_list('address', flat=True).distinct()[:50]),  # Limit locations, convert to list
                    'search_params': search_params,
                    "institute_group": InstituteGroup.objects.all(),
                    "institute_types": choices.InstituteType.CHOICES,
                    'institutes_paginations': None
                })
            else:
                ctx.update({
                    'total_institute_count': Institute.objects.none(),
                    'total_stu_count': 0,
                    'counselors_count': 0,
                    'institutes': [],
                    'total_students_count': None,
                    'test_result_count': None,
                    'streams': {},
                    'locations': [],
                    'search_params': search_params,
                    "institute_group": InstituteGroup.objects.all(),
                    "institute_types": choices.InstituteType.CHOICES,
                    'institutes_paginations': None
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
        elif data_type == 'stats':
            # AJAX request for statistics
            group_admin = request.user
            marketing_group = InstituteMarketingGroup.objects.filter(
                marketing_group_admin=group_admin
            ).first()
            if marketing_group:
                from institute.models import get_global_remain_credits
                from django.conf import settings
                institutes_in_group = Institute.objects.filter(marketing_group=marketing_group)
                total_credits = sum(inst.credit_counts for inst in institutes_in_group)
                ctx.update({
                    'total_stu_count': StudentManagement.objects.filter(
                        institute__marketing_group=marketing_group
                    ).count(),
                    'counselors_count': Counselor.objects.filter(
                        counselor_admin__marketing_group=marketing_group
                    ).count(),
                    'total_credits': total_credits,
                    'global_credits': settings.CREDIT_LIMIT,
                    'total_events': 0,  # Placeholder - add actual events count if available
                })
            else:
                ctx.update({
                    'total_stu_count': 0,
                    'counselors_count': 0,
                    'total_credits': 0,
                    'total_events': 0,
                })
        elif data_type == 'charts':
            # AJAX request for charts data - OPTIMIZED for performance
            group_admin = request.user
            marketing_group = InstituteMarketingGroup.objects.filter(
                marketing_group_admin=group_admin
            ).first()
            
            if not marketing_group:
                ctx.update({
                    'institutes': [],
                    'total_students_count': 0,
                    'test_result_count': 0,
                    'streams': {},
                    'streams_chart_data': [],
                })
            else:
                # OPTIMIZED: Get institute data for location chart (only address and student_count)
                # Use values() and annotate() to get aggregated data directly from DB
                # Limit to top 20 locations by student count to prevent chart overflow
                institute_data = list(
                    Institute.objects
                    .filter(marketing_group=marketing_group)
                    .values('address')
                    .annotate(student_count=Count('student_management'))
                    .order_by('-student_count')[:20]  # Top 20 locations only
                )
                
                # Get full institute list for seat capacity table (with seat capacity data)
                seat_capacity_institutes = list(
                    Institute.objects
                    .filter(marketing_group=marketing_group)
                    .values('id', 'name', 'address', 'pcm', 'cbm', 'comm', 'hme', 'hmb')
                    .order_by('name')[:100]  # Limit to 100 institutes
                )
                
                # OPTIMIZED: Get total student count (single query)
                total_students_count = StudentManagement.objects.filter(
                    institute__marketing_group=marketing_group
                ).count()
                
                # OPTIMIZED: Get test result count (single query with exists check)
                test_result_count = StudentManagement.objects.filter(
                    institute__marketing_group=marketing_group
                ).filter(
                    student__results__test_paper='test3'
                ).distinct().count()
                
                # OPTIMIZED: Get streams data (only if needed, with limits)
                # Only fetch a sample of students with results for stream calculation
                sample_students = StudentManagement.objects.filter(
                    institute__marketing_group=marketing_group
                ).select_related('student')[:200]  # Limit to 200 for stream calculation
                
                # Get test results for sample students only
                student_users = [stu.student for stu in sample_students]
                test_results_queryset = Results.objects.filter(
                    user__in=student_users,
                    test_paper='test3'
                ).select_related('user')[:200]  # Limit results
                
                # Create mapping and process streams
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
                # Sort by count (descending) and limit to top 15 to prevent chart overflow
                streams_chart_data = []
                if streams_data:
                    sorted_streams = sorted(streams_data.items(), key=lambda x: x[1], reverse=True)[:15]
                    for stream, count in sorted_streams:
                        streams_chart_data.append({
                            'stream': stream,
                            'count': count
                        })
                
                ctx.update({
                    'institutes': institute_data,  # Optimized: only address and student_count for chart
                    'total_students_count': total_students_count,
                    'test_result_count': test_result_count,
                    'streams': streams_data,
                    'streams_chart_data': streams_chart_data,
                    'seat_capacity_institutes': seat_capacity_institutes,  # Add seat capacity data
                })
                
                # Handle seat capacity pagination separately
                if data_type == 'seat_capacity':
                    # Get paginated seat capacity data
                    page = request.GET.get('page', 1)
                    per_page = request.GET.get('per_page', 10)
                    
                    seat_capacity_queryset = Institute.objects.filter(
                        marketing_group=marketing_group
                    ).order_by('name')
                    
                    paginator = Paginator(seat_capacity_queryset, per_page)
                    seat_capacity_page = paginator.get_page(page)
                    
                    seat_capacity_list = []
                    for inst in seat_capacity_page:
                        seat_capacity_list.append({
                            'id': inst.id,
                            'name': inst.name,
                            'pcm': inst.pcm,
                            'cbm': inst.cbm,
                            'comm': inst.comm,
                            'hme': inst.hme,
                            'hmb': inst.hmb
                        })
                    
                    ctx.update({
                        'institutes': seat_capacity_list,
                        'page': seat_capacity_page.number,
                        'per_page': per_page,
                        'total_pages': paginator.num_pages,
                        'total_count': paginator.count,
                        'has_previous': seat_capacity_page.has_previous(),
                        'has_next': seat_capacity_page.has_next(),
                        'previous_page': seat_capacity_page.previous_page_number() if seat_capacity_page.has_previous() else None,
                        'next_page': seat_capacity_page.next_page_number() if seat_capacity_page.has_next() else None,
                        'start_index': seat_capacity_page.start_index(),
                        'end_index': seat_capacity_page.end_index(),
                    })
        else:
            # Default AJAX - just institute table
            group_admin = request.user
            info = self.get_institute_group_info(group_admin, search_params, load_full_data=False)
            institutes_list = info['institutes']
            pages = Paginator(institutes_list, 10)
            page_number = request.GET.get('page', 1)
            ctx['institutes_paginations'] = pages.get_page(page_number)
            ctx['search_params'] = search_params
        
        return ctx
    
    def get(self, request, *args, **kwargs):
        from django.template.loader import render_to_string
        from django.http import JsonResponse, HttpResponse
        
        # Check if this is an AJAX request for specific data
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        data_type = request.GET.get('data_type', '')
        
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
            # Regular page load
            return render(request, self.template_name, self.get_context(request, *args, **kwargs))
    
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
            # Verify the institute belongs to the user's marketing group
            group_admin = request.user
            marketing_group = InstituteMarketingGroup.objects.filter(
                marketing_group_admin=group_admin
            ).first()
            
            if not marketing_group or ins.marketing_group != marketing_group:
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
        
        ins=get_object_or_404(Institute,id=ins_id)
        
        # Verify the institute belongs to the user's marketing group
        group_admin = request.user
        marketing_group = InstituteMarketingGroup.objects.filter(
            marketing_group_admin=group_admin
        ).first()
        
        if not marketing_group or ins.marketing_group != marketing_group:
            messages.error(request, "Unauthorized access.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
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
            # Regular page load
            return render(request,self.template_name,self.get_context(request,*args,**kwargs))

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
                
                # Determine system based on class
                if class_number and class_number >= 11:
                    # Class 11-12: Use post-matric system
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
                
                # Determine system based on class
                if class_number and class_number >= 11:
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
            
            # Correct test3_complete if it's incorrectly set
            if test_completion.test3_complete != all_test3_subtests_complete:
                test_completion.test3_complete = all_test3_subtests_complete
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

        # Optimize: Batch fetch psychometric results for all students
        from psychometric_tests.models import PsychometricTestResult
        student_users = [stu.student for stu in stu_manage if stu.student]
        psychometric_results_map = {}
        if student_users:
            psychometric_results = PsychometricTestResult.objects.filter(
                assessment__central_test_candidate__user__in=student_users
            ).select_related('assessment__central_test_candidate__user')
            for result in psychometric_results:
                user = result.assessment.central_test_candidate.user
                if user not in psychometric_results_map:
                    psychometric_results_map[user] = []
                psychometric_results_map[user].append(result)
        
        # Count students with psychometric results (for this specific institute)
        ptr_count = len([r for r in stu_manage if r.student and r.student in psychometric_results_map])
        
        # Optimize: Batch fetch test results for all students (for this specific institute)
        from app.models import Results
        test_results_map = {}
        if student_users:
            all_results = Results.objects.filter(user__in=student_users).select_related('user')
            for result in all_results:
                if result.user not in test_results_map:
                    test_results_map[result.user] = []
                test_results_map[result.user].append(result)
        
        # Count students with test results (for this specific institute)
        ptr_count1 = len([
            r1 for r1 in stu_manage 
            if r1.student and r1.student in test_results_map and 
            any(res.is_test_successful for res in test_results_map[r1.student])
        ])
        
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
        
        # Lightweight: Don't convert to list - keep as QuerySet for initial load
        # Only get count for statistics
        student_user_ids = stu_manage.values_list('student_id', flat=True).filter(student__isnull=False)
        
        # Lightweight streams calculation for chart - only process sample of students with results
        from app.models import Results
        streams = {}
        if student_user_ids:
            # Get a sample of students with test3 results for stream calculation (limit to 200 for performance)
            sample_students = list(stu_manage[:200])
            student_users = [stu.student for stu in sample_students if stu.student]
            
            if student_users:
                test_results_queryset = Results.objects.filter(
                    user__in=student_users,
                    test_paper='test3'
                ).select_related('user')[:200]
                
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
        ctx['sessions_data_json']= sessions_data_json 
        ctx['streams'] = streams  # Empty for initial load
        ctx['higher_class_results'] = {}  # Empty for initial load
        ctx['Testsession'] = TestSession
        return ctx

    def get(self, request, *args, **kwargs):
        download=request.GET.get("download")
        
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
                return render(request, 'template20/shared/students_table.html', ctx)
        
        # Full context for initial page load
        ctx=self.get_context(request, *args, **kwargs)
        if download=="Yes":
            data=ctx.get('stu')
            return self.get_filter_data(request,data)
        
        return render(request, self.template_name, ctx )
    
    def get_student_table_context_ajax(self, request, *args, **kwargs):
        """
        Lightweight context method for AJAX student table requests.
        Only processes student-related data, skipping heavy operations like counselor data, charts, etc.
        """
        slug=kwargs.get("slug")
        institute=get_object_or_404(Institute,slug=slug)
        
        # Use centralized function to get students based on role
        stu_manage = get_students_by_role(request.user, institute=institute).select_related(
            'student', 
            'class_and_section',
            'institute'
        )
        
        # Get filter parameters
        stream_filter = request.GET.get('stream', '')
        
        # Get class and sections for filter dropdown
        class_and_sections = get_class_and_sections_by_role(request.user, stu_manage)
        class_counts = get_class_counts(stu_manage)
        
        # Get unique streams using centralized function
        unique_streams = get_unique_streams_by_role(request.user, stu_manage)
        
        # Optimize: Batch fetch all test-related data for all students at once
        from app.models import TestCompletion, Results
        from app_post_matric.models import TestSession as PostMatricTestSession
        
        student_users = [stu.student for stu in stu_manage if stu.student]
        
        # Batch fetch TestCompletion records
        test_completion_map = {}
        if student_users:
            test_completions = TestCompletion.objects.filter(user__in=student_users).select_related('user')
            test_completion_map = {tc.user: tc for tc in test_completions}
        
        # Batch fetch post-matric TestSession records
        post_matric_sessions_map = {}
        if student_users:
            post_matric_sessions = PostMatricTestSession.objects.filter(
                user__in=student_users
            ).select_related('user', 'test')
            for session in post_matric_sessions:
                if session.user not in post_matric_sessions_map:
                    post_matric_sessions_map[session.user] = []
                post_matric_sessions_map[session.user].append(session)
        
        # Batch fetch Results for psychometric students
        results_queryset_map = {}
        if student_users:
            results_queryset = Results.objects.filter(user__in=student_users).select_related('user')
            for result in results_queryset:
                if result.user not in results_queryset_map:
                    results_queryset_map[result.user] = []
                results_queryset_map[result.user].append(result)
        
        # Now fetch results for each student using batch-fetched data
        results_data = {}
        for stu in stu_manage:
            if not stu.student:
                continue
            user = stu.student
            student_result = self._get_student_test_result_optimized(
                user, 
                stu,
                test_completion_map.get(user),
                post_matric_sessions_map.get(user, []),
                results_queryset_map.get(user, [])
            )
            results_data[user.id] = student_result
        
        # Apply filters using centralized function
        filtered_students = apply_student_filters(stu_manage, request, results_data=results_data)
        
        # Handle stream filter separately if needed
        if stream_filter:
            if hasattr(filtered_students, 'filter'):
                filtered_students = filtered_students.filter(class_and_section__stream=stream_filter)
            else:
                filtered_students = [
                    s for s in filtered_students
                    if hasattr(s, 'class_and_section') and s.class_and_section and
                    s.class_and_section.stream == stream_filter
                ]
        
        # Handle per_page parameter
        per_page_param = request.GET.get('per_page', '10')
        if per_page_param == 'all':
            per_page_value = 10000
        else:
            try:
                per_page_value = int(per_page_param)
            except (ValueError, TypeError):
                per_page_value = 10
        
        # Pagination
        if isinstance(filtered_students, list):
            sorted_students = sorted(filtered_students, key=lambda x: x.created, reverse=True)
            pages = Paginator(sorted_students, per_page_value)
        else:
            pages = Paginator(filtered_students.order_by('-created'), per_page_value)
        
        page_number = request.GET.get('page', 1)
        total_students = pages.get_page(page_number)
        
        return {
            'total_students': total_students,
            'total_students_count': list(stu_manage),
            'class_and_sections': class_and_sections,
            'class_counts': class_counts,
            'unique_streams': unique_streams,
            'results_data': results_data,
            'stu': filtered_students if hasattr(filtered_students, 'filter') else filtered_students,
            'institute': institute,
        }
    
    def post(self, request, *args, **kwargs):
        slug=kwargs.get("slug")
        institute=get_object_or_404(Institute,slug=slug)
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
        return render(request, self.template_name, ctx)

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(marketing_group_user_only,name='dispatch')
class InstituteApproveView(View):
    """
    View to approve an institute by changing its status from pending to approved.
    """
    def get(self, request, id):
        try:
            institute = Institute.objects.get(id=id)
            institute.institute_status = choices.InstituteStatus.APPROVED
            institute.save()
            messages.success(request, f"Institute '{institute.name}' has been approved successfully.")
        except Institute.DoesNotExist:
            messages.error(request, "Institute not found.")
        
        # Redirect back to the referring page or to a default page
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))


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
        return render(request,self.template_name,self.get_context(request,*args,**kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_user_only,name='dispatch')
class StudentData(APIView):
    def post(self,request,*args,**kwargs):
        id=request.POST.get("id")
        # user=get_object_or_404(User,id=id)
        stu=get_object_or_404(StudentManagement,student__id=id)
        if stu.class_and_section is not None:
            response={"success":"true","name":stu.student.name,"email":stu.student.email,"mobile":stu.student.mobile,"class_id":stu.class_and_section.id,"class":stu.class_and_section.class_and_section}
        else:
            response={"success":"true","name":stu.student.name,"email":stu.student.email,"mobile":stu.student.mobile,"class":"Not Selected"}
        return JsonResponse(response)

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
class InstituteData(APIView):
    def post(self,request,*args,**kwargs):
        id=request.POST.get("id")
        ins=get_object_or_404(Institute,id=id)
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
        from django.conf import settings
        context['show_demo_credentials'] = (
            getattr(settings, 'SHOW_DEMO_CREDENTIALS', False) and
            getattr(settings, 'ENVIRONMENT', 'production') == 'development'
        )
        if context.get('show_demo_credentials'):
            email = getattr(settings, 'DEMO_INSTITUTE_EMAIL', '')
            pwd = getattr(settings, 'DEMO_INSTITUTE_PASSWORD', '')
            context['demo_credentials'] = [{
                'role': 'Institute', 'email': email, 'password': pwd,
                'description': 'Access institute dashboard and manage students'
            }] if email else []
        else:
            context['demo_credentials'] = []
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
                return JsonResponse({'error': 'User is not authorized'}, status=403)
        
        # Get heatmap data for group
        heatmap_data = get_heatmap_data_for_group(user, group_type, demographic_type)
        
        return JsonResponse(heatmap_data, safe=False)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)