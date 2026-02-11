from django.contrib import messages
from re import template
from django.contrib.auth import authenticate, login,logout as auth_logout
from django.contrib.auth import login
from django.views.generic import TemplateView,View
from django.http import Http404, HttpResponse, HttpResponseRedirect,JsonResponse
from django.shortcuts import render, redirect
from communication.models import OTP
from counselor.models import Counselor
from .backends import CustomUserBackend
from .models import User, UserResume,UserResumeCertificate,UserResumeInternship,UserResumeActivity,UserResumeSkill,UserResumeVolunteerInvolvement
from communication.com_service import ComService
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.core.signing import Signer
from core import choices
from django.template.loader import render_to_string
from django.db.models import Q
from core.utils import build_breadcrumb,build_html_head
from rest_framework import permissions,authentication
from django.db.models import Q
from django.core.signing import Signer
from django.urls import reverse,reverse_lazy
from communication import models
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from careers.models import Videos,Career,CareerTags
from entrance_exams.models import EntranceExam
from colleges.models import College,CollegeShortlist
from courses.models import Course
from core.models import Country,Subject,Hobbies,UserFigureOut,Stories
from blog.models import Blog
from .models import UserProfile,UserNote,UserFolder,UserCalender
from psychometric_tests.models import CentralTestCandidate
from .task import send_otp_mail,send_referral_mail
from careers.models import CareerCluster,CareerShortlist,Videos
from skilllab.models import SkillLabCourse
from entrance_exams.document_filters import EntranceExamDocumentFilter
from django.shortcuts import get_object_or_404
from django.utils import timezone
from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
import pdfkit 
from django.core.files import File
from django.conf import settings
from institute.models import Institute, InstituteGroup, InstituteMarketingGroup,StudentManagement, get_global_remain_credits
from django.middleware.csrf import get_token
# from .forms import InstituteRegistrationForm
import re

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
        return build_breadcrumb(l)

    def __html_head(self):
        name='Login Signup'
        return build_html_head(title=name, description=name)

    def get_context(self,request,enc_id=None,*args,**kwargs):
        ctx={}
        ctx['html_head']=self.__html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        if enc_id:
            ctx['enc_referral_user']=enc_id
        else:
            ctx['enc_referral_user']=False
        # Demo credentials for development
        ctx['show_demo_credentials'] = (
            getattr(settings, 'SHOW_DEMO_CREDENTIALS', False) or
            getattr(settings, 'ENVIRONMENT', 'production') == 'development' or
            getattr(settings, 'DEBUG', False)
        )
        ctx['demo_credentials'] = []
        # Show Olympiad demo user (demo_olympiad) when demo credentials are shown
        if ctx.get('show_demo_credentials'):
            ctx['demo_credentials'].append({
                'role': 'demo_olympiad',
                'email': 'olympiad_demo@topteen.demo',
                'password': 'demo1234',
                'description': 'Try NSEO Olympiad – list exams, register, take exam, view results',
            })
        return ctx

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('users:userdashboard')
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class StudentLoginView(LoginView):
    """
    Student login landing page (/student/login/).
    OTP-first by default via template context.
    """
    template_name = "template20/student_login.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('users:userdashboard')
        ctx = self.get_context(request, *args, **kwargs)
        ctx['login_mode'] = 'student'
        if ctx.get('show_demo_credentials'):
            emails = getattr(settings, 'DEMO_STUDENT_EMAILS', []) or []
            pwd = getattr(settings, 'DEMO_STUDENT_PASSWORD', '')
            ctx['demo_credentials'] = [
                {'role': 'Student', 'email': e.strip(), 'password': pwd, 'description': 'Access student dashboard and career resources'}
                for e in emails if e.strip()
            ]
            # Add Olympiad demo so it appears on student login too
            ctx['demo_credentials'].append({
                'role': 'demo_olympiad',
                'email': 'olympiad_demo@topteen.demo',
                'password': 'demo1234',
                'description': 'Try NSEO Olympiad – list exams, register, take exam, view results',
            })
        return render(request, self.template_name, ctx)


class StudentSignupView(LoginView):
    """
    Student signup page (/student/signup/).
    Dedicated flow for new accounts: OTP verify -> set password.
    """
    template_name = "template20/student_signup.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('users:userdashboard')
        ctx = self.get_context(request, *args, **kwargs)
        ctx['login_mode'] = 'student'
        return render(request, self.template_name, ctx)


class ParentsLoginView(LoginView):
    """
    Parents login landing page (/parents/login/).
    Mobile + OTP only.
    """

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if getattr(request.user, 'user_type', None) == choices.UserType.PARENT:
                return redirect('parents_dashboard')
            return redirect('users:userdashboard')
        ctx = self.get_context(request, *args, **kwargs)
        ctx['login_mode'] = 'parent'
        if ctx.get('show_demo_credentials'):
            emails = getattr(settings, 'DEMO_PARENTS_EMAILS', []) or []
            pwd = getattr(settings, 'DEMO_PARENTS_PASSWORD', '')
            ctx['demo_credentials'] = [
                {'role': 'Parent', 'email': e.strip(), 'password': pwd, 'description': 'View linked students and their progress'}
                for e in emails if e.strip()
            ]
        return render(request, self.template_name, ctx)


class ParentsDashboardView(TemplateView):
    template_name = 'template20/parents/dashboard.html'

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('parents_login')
        if request.user.user_type != choices.UserType.PARENT:
            return redirect('users:userdashboard')
        from users.models import ParentStudentLink
        linked = ParentStudentLink.objects.filter(parent=request.user).select_related('student')
        students = [x.student for x in linked if x.student]

        # Build result status for each linked student (psychometric report availability)
        students_info = []
        try:
            from psychometric_tests.models import CentralTestCandidate
            for s in students:
                results_enabled = False
                try:
                    ctc = CentralTestCandidate.objects.filter(user=s).first()
                    if ctc:
                        test = ctc.candidate_test.last()
                        if test and getattr(test, "is_success", None) == choices.YesNoChoices.YES:
                            if hasattr(test, "psychometric_test_results") and test.psychometric_test_results:
                                results_enabled = True
                except Exception:
                    results_enabled = False
                students_info.append({"student": s, "results_enabled": results_enabled})
        except Exception:
            students_info = [{"student": s, "results_enabled": False} for s in students]

        ctx = {
            "linked_students": students,
            "linked_students_info": students_info,
        }
        return render(request, self.template_name, ctx)


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
            "breadcrumb": build_breadcrumb([
                {"title": "Parent Dashboard", "text": "Parent Dashboard", "url": reverse_lazy("parents_dashboard")},
                {"title": "Career Interests", "text": "Career Interests", "url": ""},
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
            "breadcrumb": build_breadcrumb([
                {"title": "Parent Dashboard", "text": "Parent Dashboard", "url": reverse_lazy("parents_dashboard")},
                {"title": "My Videos", "text": "My Videos", "url": ""},
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
            "breadcrumb": build_breadcrumb([
                {"title": "Parent Dashboard", "text": "Parent Dashboard", "url": reverse_lazy("parents_dashboard")},
                {"title": "My Colleges", "text": "My Colleges", "url": ""},
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
            "breadcrumb": build_breadcrumb([
                {"title": "Parent Dashboard", "text": "Parent Dashboard", "url": reverse_lazy("parents_dashboard")},
                {"title": "My Blogs", "text": "My Blogs", "url": ""},
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


def _normalize_mobile_digits(value: str) -> str:
    return re.sub(r"\D+", "", str(value or "")).strip()

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
                
                # For login requests: ALL STUDENTS see password popup FIRST, OTP as fallback
                # Priority: Password popup first, then OTP if password fails or not set
                try:
                    is_institute_student = False
                    has_usable_password = False
                    is_default_password = False
                    
                    # Debug logging helper (only in DEBUG mode)
                    def debug_log(message):
                        if settings.DEBUG:
                            print(f"[DEBUG] {message}")
                    
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
                # Create OTP synchronously first to ensure it's available immediately
                cs = ComService()
                otp = cs.get_otp(username, otp_type)
                # Print OTP to terminal for debugging
                if otp_type == choices.CommunicationTypeChooices.EMAIL:
                    print(f"Email OTP for {username}: {otp}")
                else:
                    print(f"SMS OTP for {username}: {otp}")
                # Then send email asynchronously
                send_otp_mail.delay(username,otp_type)
                
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
                if user:
                    # User exists - log them in directly
                    from django.contrib.auth import login
                    # Use CustomUserBackend for login
                    login(request, user, backend='users.backends.CustomUserBackend')
                    data["otp_verify"]=True
                    data["user_exists"]=True
                    data["success"]=True
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
        
        # Validate grade for direct signups (must be 10 or 12)
        if grade and grade not in ['10', '12']:
            data['message'] = "Please select a valid class (10 or 12)"
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
                    # Create user - Note: create_user method ignores password, so we set it manually
                    # The User model's save() method will set default name="Student" if not provided
                    if mobile and email is None:
                        user = User.objects.create(
                            mobile=mobile, 
                            referral=refer_user_id, 
                            user_type=choices.UserType.STUDENT,
                            name="Student"  # Set default name
                        )
                    else:
                        user = User.objects.create(
                            email=email, 
                            referral=refer_user_id, 
                            user_type=choices.UserType.STUDENT,
                            name="Student"  # Set default name
                        )
                    
                    # Set password manually since create_user doesn't use the password parameter
                    user.set_password(pwd)
                    user.save()
                    
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
                    
                    try:
                        # Auto-login the user
                        from django.contrib.auth import login
                        # Specify backend since multiple backends are configured
                        login(request, user, backend='users.backends.CustomUserBackend')
                    except Exception as login_error:
                        # Log but don't fail - user is already created
                        import traceback
                        print(f"Warning: Error logging in user: {str(login_error)}")
                        print(traceback.format_exc())
                    
                    # Return redirect URL to dashboard after signup based on user type
                    # User is created successfully, so return success even if profile/login had minor issues
                    data['success'] = True
                    data['message'] = "Account created successfully"
                    
                    # Redirect based on user type
                    if user.user_type == choices.UserType.COUNSELOR:
                        try:
                            from counselor.models import Counselor
                            coun = Counselor.objects.get(coun_user=user)
                            data['redirect_url'] = request.build_absolute_uri(reverse('counselor:CounselorDashboardView', args=[coun.id]))
                        except Counselor.DoesNotExist:
                            data['redirect_url'] = request.build_absolute_uri(reverse('users:userdashboard'))
                    elif user.user_type == choices.UserType.INSTITUTE:
                        from institute.models import Institute
                        institute = Institute.objects.filter(created_by=user).last()
                        if institute and institute.institute_status == choices.InstituteStatus.APPROVED:
                            data['redirect_url'] = request.build_absolute_uri(reverse('institute:institutedashboard', args=[institute.slug]))
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
                    # Use CustomUserBackend for login
                    login(request, user, backend='users.backends.CustomUserBackend')
                    data["otp_verify"]=True
                    data["success"]=True
                    
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
                    if remember_me:
                        request.session.set_expiry(2592000)
                    else:
                        request.session.set_expiry(0)
                    
                    login(request, user, backend='users.backends.CustomUserBackend')
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
                    if remember_me:
                        # Set session to expire in 30 days (2592000 seconds)
                        request.session.set_expiry(2592000)
                    else:
                        # Use default session expiry (browser session)
                        request.session.set_expiry(0)
                    
                    # Use CustomUserBackend for login
                    login(request, user, backend='users.backends.CustomUserBackend')
                    data['success'] = True
                # If master password was used, data['success'] is already set above
                
                # Check if user is staff or superuser - redirect to business analytics first
                if user.is_staff or user.is_superuser:
                    data['redirect_url'] = request.build_absolute_uri(reverse('user_analytics:business_dashboard'))
                    return Response(data, status=status.HTTP_200_OK)
                
                # Redirect based on user type
                # Check for counselor first
                if user.user_type == choices.UserType.COUNSELOR:
                    try:
                        from counselor.models import Counselor
                        coun = Counselor.objects.get(coun_user=user)
                        data['redirect_url'] = reverse('counselor:CounselorDashboardView', args=[coun.id])
                    except Counselor.DoesNotExist:
                        data['redirect_url'] = request.build_absolute_uri(reverse('users:userdashboard'))
                # Check for institute users
                elif user.user_type == choices.UserType.INSTITUTE:
                    from institute.models import Institute
                    institute = Institute.objects.filter(created_by=user).last()
                    if institute and institute.institute_status == choices.InstituteStatus.APPROVED:
                        data['redirect_url'] = reverse('institute:institutedashboard', args=[institute.slug])
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
                    print(f"[DEBUG] {message}")
            
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
        user = request.user
        redirect_url = reverse('app:test_buttons')  # Default
        
        try:
            # Check for institute users
            if user.user_type == choices.UserType.INSTITUTE:
                institute = Institute.objects.filter(created_by=user).last()
                if institute and institute.institute_status == choices.InstituteStatus.APPROVED:
                    redirect_url = reverse('institute:institutedashboard', args=[institute.slug])
            
            # Check for institute group admin
            elif user.user_type == choices.UserType.INSTITUTEGROUPADMIN:
                if InstituteGroup.objects.filter(institute_group_admin=user).exists():
                    redirect_url = reverse('institute:institutegroupdashboard')
            
            # Check for marketing group admin
            elif user.user_type == choices.UserType.MARKETINGGROUPADMIN:
                if Institute.objects.filter(marketing_group__marketing_group_admin=user).exists():
                    redirect_url = reverse('institute:marketinggroupdashboard')
            
            # Check for counselor
            elif user.user_type == choices.UserType.COUNSELOR:
                try:
                    coun = Counselor.objects.get(coun_user=user)
                    redirect_url = reverse('counselor:CounselorDashboardView', args=[coun.id])
                except Counselor.DoesNotExist:
                    pass  # Keep default

            elif user.user_type == choices.UserType.PARENT:
                redirect_url = reverse('parents_dashboard')
            
            # Check for students - check if in class 11 or 12
            else:
                redirect_url = _compute_student_destination(user)

            redirect_url = _apply_institute_student_mobile_gate(request, user, redirect_url)
        
        except Exception as e:
            print(f"Error getting dashboard URL: {e}")
        
        # Return absolute URI to avoid 404 issues
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
        print(f"Mobile Update - SMS OTP for {mobile}: {otp}")
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
        print(f"Parent Link - SMS OTP for {mobile}: {otp}")
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
            from django.contrib.auth import login
            login(request, user, backend='users.backends.CustomUserBackend')
            
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
                    print(f"Forgot Password - Email OTP for {username}: {otp}")
                else:
                    print(f"Forgot Password - SMS OTP for {username}: {otp}")
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
                        print(f"[DEBUG] Forgot Password - Password updated successfully for user: {user.email or user.mobile}")
                    
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
                print(f"Resend - Email OTP for {username}: {otp}")
            else:
                print(f"Resend - SMS OTP for {username}: {otp}")
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
        ctx['profile_user'] = profile_user or request.user
        ctx['is_parent_view'] = is_parent_view
        ctx['hobbies']=Hobbies.objects.all()
        ctx['subjects']=Subject.objects.all()
        ctx['figureouts']=UserFigureOut.objects.all()
        # Linked parent accounts (for adding/viewing parent mobile(s) in profile)
        try:
            from users.models import ParentStudentLink
            links = ParentStudentLink.objects.filter(student=ctx['profile_user']).select_related('parent')
            ctx['linked_parents'] = [x.parent for x in links if x.parent]
        except Exception:
            ctx['linked_parents'] = []
        ctx["html_head"] = self.html_head()
        return ctx

    def get(self, request,*args, **kwargs):      
        return render(request, self.template_name, self.get_context(request,args, kwargs))
    
    
    def post(self,request,*args,**kwargs):
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
            # Student mobile must be unique
            if request.user.user_type == choices.UserType.STUDENT and _student_mobile_exists(mobile, exclude_user_id=request.user.id):
                messages.error(request, "This mobile number is already used by another student.")
                return render(request,self.template_name, self.get_context(request,args, kwargs))
            # Student vs Parent mobile conflict
            if request.user.user_type == choices.UserType.STUDENT and _mobile_conflicts_student_parent(mobile, current_user=request.user, intended_user_type=choices.UserType.STUDENT):
                messages.error(request, "This mobile number is already used by a parent account.")
                return render(request,self.template_name, self.get_context(request,args, kwargs))
            hobbies=Hobbies.objects.filter(id__in=hobbies)
            subjects=Subject.objects.filter(id__in=subjects)
            figure_outs=UserFigureOut.objects.filter(id__in=figure_outs)
            user = User.objects.get(id=request.user.id)
            user.mobile=mobile
            user.name=name
            if image:
                user.image=image
            user.save()
            user_profile,_=UserProfile.objects.get_or_create(user=user)
            user_profile.birthdate=birthdate
            user_profile.gender=gender
            user_profile.schoolname=school
            user_profile.grade=grade
            user_profile.save()
            # Use .set() instead of .add() to replace existing relationships, not append
            user_profile.hobbies.set(hobbies)
            user_profile.subject.set(subjects)
            user_profile.figure_out.set(figure_outs)
            user_profile.save()
            user.is_completed=True
            user.save()
            return redirect(reverse('users:userdashboard'))
        return render(request,self.template_name, self.get_context(request,args, kwargs))


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class ViewProfile(TemplateView):
    template_name="template20/user/view_profile.html"

    def html_head(self):
        name='View Profile'
        return build_html_head(title=name, description=name)

    def get_context(self,request, profile_user=None, is_parent_view: bool = False, *args, **kwargs):
        ctx={}
        ctx['profile_user'] = profile_user or request.user
        ctx['is_parent_view'] = is_parent_view
        # Linked parent accounts for display
        try:
            from users.models import ParentStudentLink
            links = ParentStudentLink.objects.filter(student=ctx['profile_user']).select_related('parent')
            ctx['linked_parents'] = [x.parent for x in links if x.parent]
        except Exception:
            ctx['linked_parents'] = []
        ctx["html_head"] = self.html_head()
        return ctx

    def get(self, request,*args, **kwargs):      
        return render(request, self.template_name, self.get_context(request,args, kwargs))


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserDashboard(TemplateView):
    template_name ="template20/user/user_dashboard.html"

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
        ctx['exams']=EntranceExam.objects.all().order_by('?')[:3]
        
        # Determine user's class (10 or 12)
        from institute.models import StudentManagement
        user_grade = None
        try:
            user_profile = profile_user.user_profile
            if user_profile and user_profile.grade:
                user_grade = str(user_profile.grade)
        except:
            pass
        
        # If no grade from UserProfile, check StudentManagement
        if not user_grade:
            try:
                student_management = StudentManagement.objects.filter(student=profile_user).first()
                if student_management and student_management.class_and_section:
                    class_name = student_management.class_and_section.class_and_section
                    if class_name:
                        import re
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
        
        # ctc=CentralTestCandidate.objects.filter(user=request.user).last()
        ctc=CentralTestCandidate.objects.filter(user=profile_user).last()
        try:
            ctc.last_test_is_success()
            ctx['central_test_candidate']=ctc
        except:
            ctx['central_test_candidate']=False
        ctx["html_head"] = self.html_head()
        ctx["notes"]=UserNote.objects.filter(user=profile_user)[:3]

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
        return build_breadcrumb(l)

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
        return build_breadcrumb(l)

    def html_head(self):
        name='My Notepad'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        ctx['notes']=request.user.user_notes.all().exclude(title__isnull=True,content__isnull=True)
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

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserHobbies(TemplateView):
    template_name="template20/user/my_hobbies.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'Scrapbook','url':reverse_lazy('users:scrapbook')},{'title':'My Hobbies','text':'My Hobbies','url':''}]
        return build_breadcrumb(l)

    def html_head(self):
        name='My Hobbies'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        # Pre-evaluate hobbies for Jinja2 template
        try:
            if hasattr(request.user, 'user_profile') and request.user.user_profile:
                hobbies_qs = request.user.user_profile.hobbies.all()
                ctx['hobbies'] = list(hobbies_qs) if hobbies_qs.exists() else []
            else:
                ctx['hobbies'] = []
        except Exception as e:
            ctx['hobbies'] = []
        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,*args, **kwargs))
    
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserColleges(TemplateView):
    template_name="template20/user/bookmark_college.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'Scrapbook','url':reverse_lazy('users:scrapbook')},{'title':'My Colleges','text':'My Colleges','url':''}]
        return build_breadcrumb(l)

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
        return build_breadcrumb(l)

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
        return build_breadcrumb(l)

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


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class ResumeBuilder(TemplateView):
    template_name="template20/user/resume_builder.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'Scrapbook','url':reverse_lazy('users:scrapbook')},{'title':'Resume builder','text':'Resume builder','url':''}]
        return build_breadcrumb(l)

    def html_head(self):
        name='Resume builder'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        resume,_=UserResume.objects.get_or_create(user=request.user)
        ctx['resume']=resume
        ctx['resumeskill']=UserResumeSkill.objects.filter(resume=resume)
        ctx['resumecertificate']=UserResumeCertificate.objects.filter(resume=resume)
        ctx['resumeinternship']=UserResumeInternship.objects.filter(resume=resume)
        ctx['resumeactivity']=UserResumeActivity.objects.filter(resume=resume)
        ctx['resumevolunteer']=UserResumeVolunteerInvolvement.objects.filter(resume=resume)
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class ResumeBuilderWelcome(TemplateView):
    template_name="template20/user/resume_builder_welcome.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'Scrapbook','url':reverse_lazy('users:scrapbook')},{'title':'Resume builder welcome ','text':'Resume builder welcome','url':''}]
        return build_breadcrumb(l)

    def html_head(self):
        name='Resume builder'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))
    
@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserFolders(TemplateView):
    template_name="template20/user/user_folder.html"
    
    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'Scrapbook','url':reverse_lazy('users:scrapbook')},{'title':'My Folder','text':'My Folder','url':''}]
        return build_breadcrumb(l)

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
        return build_breadcrumb(l)

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
    
@login_required
def resume_pdf_download(request,*args, **kwargs):
    template = get_template("mail/user/userresumepdf.html")
    user_resume=request.user.user_resume
    ctx={}
    ctx["request"]=request
    ctx["profile"]=get_object_or_404(UserProfile,user=request.user)
    ctx["skills"]=UserResumeSkill.objects.filter(resume=user_resume)
    ctx["certificates"]=UserResumeCertificate.objects.filter(resume=user_resume).order_by("issue_date")
    ctx["internships"]=UserResumeInternship.objects.filter(resume=user_resume)
    ctx["activities"]=UserResumeActivity.objects.filter(resume=user_resume)
    ctx["volunteers"]=UserResumeVolunteerInvolvement.objects.filter(resume=user_resume)
    ctx["image_url"]="https://www.topteen.in{}".format(request.user.image.url)
    html  = template.render(ctx)
    pdf=pdfkit.from_string(html,False)
    response= HttpResponse(pdf, content_type='application/pdf')
    name="{}resume.pdf".format( request.user.name if request.user.name else "Student")
    response['Content-Disposition']='attachment; filename="' +name+ '"'
    return response

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserCalenderView(TemplateView):
    template_name="template20/user/user_calendar.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Calender','text':'calender','url':''}]
        return build_breadcrumb(l)

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

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserHistoryView(TemplateView):
    template_name="template20/user/user_history.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Payment History','text':'Payment History','url':''}]
        return build_breadcrumb(l)

    def html_head(self):
        name='Payment History'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        from payments.models import Payment
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['payments'] = Payment.objects.filter(user=request.user).order_by('-created')
        ctx['breadcrumb']=self.__breadcrumb()
        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,*args, **kwargs))

@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class Bookmark(TemplateView):
    template_name="template20/user/bookmark_list.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'My Bookmarks','text':'My Bookmarks','url':''}]
        return build_breadcrumb(l)

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
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'My Bookmarks','text':'My Bookmarks','url':reverse_lazy('users:bookmark')},{'title':'My Videos','text':'My Videos','url':''}]
        return build_breadcrumb(l)

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
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'My Bookmarks','text':'My Bookmarks','url':reverse_lazy('users:bookmark')},{'title':'My Exams','text':'My Exams','url':''}]
        return build_breadcrumb(l)

    def html_head(self):
        name='My Exams'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        user_ids = _bookmark_owner_user_ids(request.user)
        exams = EntranceExam.objects.filter(shortlist__in=user_ids).distinct()
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
        return build_breadcrumb(l)

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
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},
           {'title':'My Bookmarks','text':'My Bookmarks','url':reverse_lazy('users:bookmark')},
           {'title':'My Blogs','text':'My Blogs','url':''}]
        return build_breadcrumb(l)

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
    def post(self, request, *args, **kwargs):
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        email=request.POST.get("email")
        em=re.match(evalid,email)
        if em:
            to=email
            user_id=request.user.id
            send_referral_mail.delay(user_id,to)
            return JsonResponse({'success': "true"})
        else:
            return JsonResponse({'success': "false"})