from datetime import datetime, timedelta
import json
from django.shortcuts import render
from rest_framework.views import APIView
from django.http import JsonResponse
from django.views.generic import TemplateView,View
from counselor.models import Counselor, FollowUpStatus
from users.models import User
from core import choices
from psychometric_tests.models import PsychometricTestResult,CentralTestCandidate
from django.core.paginator import Paginator
from core.utils import build_html_head
from django.contrib import messages
from .task import send_new_student_credential,institute_deletion_request,create_student_and_send_mail,send_institute_mail
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from institute.decorators import change_counselor_password_only, institute_user_only,institute_authenticated_user_only,institute_block_student_only,institute_update_delete_student_only,institute_change_student_password_only,institute_profile_update_delete,only_superuser,institute_group_user_only
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import get_object_or_404
from institute.task import update_student_data,create_institute_log,send_institute_group_mail
from institute.models import Institute,StudentManagement,InstituteAccountDeletion,ClassAndSection,InstituteLog,get_global_remain_credits,InstituteGroup
from django.conf import settings
from django.http import HttpResponse
from institute.filters import StudentFilter
from django.db.models import Count
from django.utils import timezone
from app.models import Results, TestCompletion
# Create your views here.

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
class AdminDashboardView(TemplateView):
    # template_name="topteenfrontend/user/admin_dashboard.html"
    template_name="topteenfrontend/user/app/Admin_Dashboard.html"

    def html_head(self):
        name='Admin Dashboard'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        search=request.GET.get("institute")
        if search:
            institutes=Institute.objects.filter(name__icontains=search)|Institute.objects.filter(created_by__email__icontains=search)
        else:
            institutes=Institute.objects.all().order_by('-created')
        pages=Paginator(institutes,10)
        page_number=request.GET.get('page')
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx["Total_institutes"]=institutes
        ctx["institute_users"]=User.objects.filter(user_type=choices.UserType.INSTITUTE)
        ctx["Total_students"]=StudentManagement.objects.all()
        ctx["institutes"]=pages.get_page(page_number)
        ctx["global_credits"]=settings.CREDIT_LIMIT
        ctx["remaining_credits"]=get_global_remain_credits()
        ctx["institute_groups"]=InstituteGroup.objects.all()
        return ctx
    
    def get(self,request,*args,**kwargs):
        return render(request,self.template_name,self.get_context(request,*args,**kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
class InstituteCreateView(TemplateView):
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
            if institute_group_id:
                ins_group=get_object_or_404(InstituteGroup,id=institute_group_id)
            else:
                ins_group=None
            import random
            password=''.join([str(random.randint(0,10)) for _ in range(6)])
            user_dict={'email':ins_email,'password':password,'user_type':choices.UserType.INSTITUTE}
            ins_user=User.create_user(**user_dict)
            ins=Institute(name=name,created_by=ins_user,logo=logo,address=address,contact_info=contact,administrator_contact=admin_contact,credit_counts=credit_counts,institute_group=ins_group)
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
@method_decorator(only_superuser,name='dispatch')
class CounselorCreateView(TemplateView):
    
    def post(self,request,*args,**kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        coun_email=request.POST.get("counselor_email")
        name= request.POST.get("counselor_name")
        address=request.POST.get("counselor_address")
        contact=request.POST.get("counselor_contact_info")
        education = request.POST.get("counselor_education") if request.POST.get("c_education") == "Any other" else request.POST.get("c_education")
        gender=request.POST.get("counselor_gender")
        counselor_admin=request.POST.get("counselor_admin")
        ins_em=re.match(evalid,coun_email)

        # ins1 = Institute.objects.filter(created_by=request.user)
        slug=kwargs.get("slug")
        if ins_em and name and address and contact and education and gender:
            if ins_em:
                current_institute=get_object_or_404(Institute,slug=slug)
            else:
                current_institute = None
            import random
            password=''.join([str(random.randint(0,10)) for _ in range(6)])
            user_dict={'email':coun_email,'password':password,'user_type':choices.UserType.COUNSELOR}
            coun_user=User.create_user(**user_dict)
            coun=Counselor(counselor_name=name,coun_user = coun_user,counselor_email=coun_email,counselor_address=address,counselor_contact_info=contact,counselor_education=education,counselor_gender=gender,counselor_admin=current_institute)
            coun.save()
            send_institute_mail.delay(coun.coun_user.email,password)
            messages.success(request, "Institute Created")
        else:
            if User.objects.filter(email=coun_email).exists():
                messages.error(request,"{} Already Exist !!".format(coun_email))
            else:
                messages.error(request,"Something Went Wrong !!")
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
@method_decorator(institute_group_user_only,name='dispatch')
class InstituteGroupDashboardView(TemplateView):
    template_name="topteenfrontend/user/institute_group_dashboard.html"

    def html_head(self):
        name='Institute Group Dashboard'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        institute_group=InstituteGroup.objects.filter(institute_group_admin=request.user).last()
        group_students=StudentManagement.objects.filter(institute__institute_group=institute_group)
        ctx['group_institute']=institute_group
        ctx["group_stu_count"]=group_students.count()
        ctx["group_active_stu_count"]=group_students.filter(student__is_active=True).count()
        ctx["group_assesment_count"]=[stu for stu in group_students if stu.get_psychometric_result()]
        return ctx
    
    def get(self,request,*args,**kwargs):
        return render(request,self.template_name,self.get_context(request,*args,**kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(only_superuser,name='dispatch')
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
class InstituteChangePasswordView(TemplateView):
    def post(self, request, *args, **kwargs):
        id=request.POST.get("password_id")
        password=request.POST.get("change_password")
        user=get_object_or_404(User,id=id)
        user.set_password(password)
        user.save()
        send_new_student_credential.delay(user.email,password)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
@method_decorator(institute_authenticated_user_only,name='dispatch')
class InstituteDashboardView(TemplateView):
    # template_name="topteenfrontend/user/institute_dashboard.html" 
    # template_name="topteenfrontend/user/app/profile_index.html" 
    template_name="topteenfrontend/user/app/institute-dashboard-admin.html"
    
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

    # def get_student_test_result(self, user):

    #     try:
    #         test3_result = Results.objects.get(user=user, test_paper='test3')
    #         personality_res = test3_result.results
    #         scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}
    #         print('test3_result.scores', scores)
    #     except:
    #         pass

    #     results = Results.objects.filter(user=user)
    #     success_count = sum(1 for result in results if result.is_test_successful)

    #     if results.exists():
    #         latest_result = results.last()

    #         return {
    #             "test_success": success_count > 0,
    #             "test_link": latest_result.get_test_report_or_test_link(user) if latest_result else None,
    #             "success_count": success_count
    #         }
    #     return None

    def get_student_test_result(self, user):
        try:
            # Fetch the test result for the specific user
            test3_result = Results.objects.get(user=user, test_paper='test3')
            personality_res = test3_result.results
            scores = {label.split("_")[0].upper(): value for label, value in personality_res.items()}

            # Print scores for debugging (optional)
            print('test3_result.scores', scores)

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
            print(f"No results found for user: {user}")
        except Exception as e:
            print(f"An error occurred: {e}")

        return None

    def get_stream(self,test_results):
        # Initialize a dictionary to count streams
        stream_counts = {}

        # Extract streams and count occurrences
        for result in test_results:
            streams = result['streams']
            
            # From PERSONALITY
            for personality in streams['PERSONALITY']:
                stream = personality['stream']
                stream_counts[stream] = stream_counts.get(stream, 0) + 1
            
            # From INTELLIGENCE
            intelligence_streams = streams['INTELLIGENCE'].get('streams', [])
            if isinstance(intelligence_streams, list):  # Check if it's a list
                for stream in intelligence_streams:
                    stream_counts[stream] = stream_counts.get(stream, 0) + 1
            elif isinstance(intelligence_streams, str):  # Handle single string case
                stream_counts[intelligence_streams] = stream_counts.get(intelligence_streams, 0) + 1

        # Extract unique streams and counts
        unique_streams = list(stream_counts.keys())
        counts = list(stream_counts.values())

        print("Unique Streams:", unique_streams)
        print("Counts:", counts)
        print("Stream Counts:", stream_counts)
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
    
    def get_context(self,request,*args,**kwargs):        
        slug=kwargs.get("slug")
        institute=get_object_or_404(Institute,slug=slug)
        stu_manage=StudentManagement.objects.filter(institute=institute)

        ptr_count=[r for r in stu_manage if r.get_psychometric_result()]

        #<------------------------------ manish
        ptr_count1=[r1 for r1 in stu_manage if r1.get_test_result()]
        # Fetch the results for each student
        results_data = {}
        for stu in stu_manage:
            student_result = self.get_student_test_result(stu.student)
            if student_result:  # Only include results that were found
                results_data[stu.student] = student_result
        
        # If you want to create a list of results instead of a dictionary
        test_results = list(results_data.values())
        streams = self.get_stream(test_results)
        # results_data = {stu.student: self.get_student_test_result(stu.student) for stu in stu_manage}        
        counselors = Counselor.qs_for_institute(institute)
        counselor_data_list = []
        couns_sessions_data = []

        for counselor in counselors:
            # Get assigned students and count sessions (assuming FollowUpStatus represents a session)
            assigned_students = counselor.get_students(institute=institute)
            sessions_count = FollowUpStatus.objects.filter(counselor=counselor).count()
            students_counseled_count = FollowUpStatus.objects.filter(counselor=counselor, follow_up_status='completed').count()
            
            # Append data for each counselor to the list
            counselor_data_list.append({
                'id': counselor.id,
                'coun_admin':counselor.counselor_admin,
                'name': counselor.counselor_name,
                'email': counselor.counselor_email,
                'sessions': sessions_count,
                'students_counseled': students_counseled_count,
                'created': counselor.created
            })        
            # Get session data for the current counselor
            sessions_data = (
                FollowUpStatus.objects
                .filter(counselor_id=counselor.id)
                .values('last_follow_up_date', 'counselor__counselor_name')
                .annotate(session_count=Count('id'))
            )
            # Convert the queryset to a list and convert dates to strings
            sessions_data_list = list(sessions_data)  # Convert queryset to list
            for session in sessions_data_list:
                session['last_follow_up_date'] = session['last_follow_up_date'].isoformat()  # Convert date to ISO format

            # Calculate sessions for the current week (Monday to Saturday)
            week_data = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}  # Monday to Saturday
            for session in sessions_data_list:
                try:
                    session_date = datetime.strptime(session['last_follow_up_date'], "%Y-%m-%d")
                    day_of_week = session_date.weekday()  # Monday is 0
                    if day_of_week < 6:  # Only consider Monday to Saturday
                        week_data[day_of_week] += session['session_count']
                except KeyError as e:
                    print(f"KeyError: {e} in session data: {session}")

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
                'counselor_name':counselor.counselor_name,
                'sessions': final_sessions_data  # Add sessions data for this counselor
            })
        # Convert to JSON
        try:
            sessions_data_json = json.dumps(couns_sessions_data)
            print("sessions_data_json",sessions_data_json)
        except Exception as e:
            print(f"Error serializing sessions data: {e}")
            sessions_data_json = '[]'
        
        #end manish----------->

        queryset=stu_manage
        students=StudentFilter(request.GET,queryset=queryset)

        pages=Paginator(students.qs.order_by('-created'),10)
        page_number=request.GET.get('page')

        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['total_students_count'] = stu_manage
        ctx["total_students"]=pages.get_page(page_number)
        ctx["active_students"]=stu_manage.filter(student__is_active=True)
        # ptr_count=[r for r in stu_manage if r.get_psychometric_result()]
        ctx["psychometric_test_result_count"]=ptr_count
        # ctx["psychometric_test_result"]=PsychometricTestResult.objects.all()
        ctx["central_test_candidate"]=CentralTestCandidate.objects.all()
        ctx["institute"]=institute
        ctx["class_and_sections"]=ClassAndSection.objects.all()
        ctx['stu']=students.qs
        ctx['results_data']=results_data
        ctx['test_result_count']=ptr_count1
        ctx['counselor_list']= counselors     
        ctx['counselor_data_list']= counselor_data_list 
        ctx['sessions_data_json']= sessions_data_json 
        ctx['streams'] = streams
        return ctx

    def get(self, request, *args, **kwargs):
        ctx=self.get_context(request, *args, **kwargs)
        download=request.GET.get("download")
        if download=="Yes":
            data=ctx.get('stu')
            return self.get_filter_data(request,data)
        return render(request, self.template_name, ctx )
    
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
        csvfile=csv_file.read().decode('utf-8').splitlines()
        import csv
        stu_file=csv.reader(csvfile)
        header=next(stu_file)
        error_list=[]
        email_list=[]
        for stu in stu_file:
            email_list.append(stu)
            stu_d={header[i]:s for i,s in enumerate(stu) if s}
            stu_name=stu_d.get('name')
            stu_mobile=stu_d.get('mobile')
            stu_email=stu_d.get('email')
            class_section=stu_d.get('class_and_section')

            # If email is not present, generate a random email using the student's name
            if not stu_email:
                random_number = str(random.randint(1000, 9999))
                print("random_number",random_number)
                stu_email = f"{stu_name.lower().replace(' ', '_')}_{random_number}@yopmail.com"
            
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
                messages.error(request,"Invalid File Format")
                error_list.append(stu_email)
        
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
        print("coun",id)
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
@method_decorator(institute_profile_update_delete,name='dispatch') 
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
    template_name="topteenfrontend/user/institute_log.html"

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
    try:
        file=open("student_sample_data.csv",'r')
        data=HttpResponse(file.read(),content_type='application/x-download')
        data['Content-Disposition']='attachment;filename=Student sample data.csv'
        return data
    except Exception as e:
        print("---eeee----",e)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    

# def CounselorDashboard(request):    
#     return render(request, 'topteenfrontend/user/app/counselor_dashboard.html')

# def CounselorCourse(request):    
#     return render(request, 'topteenfrontend/user/app/counselor-course.html')