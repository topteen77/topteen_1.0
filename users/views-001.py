from django.contrib import messages
from re import template
from django.contrib.auth import authenticate, login,logout as auth_logout
from django.contrib.auth import login
from django.views.generic import TemplateView,View
from django.http import Http404, HttpResponse,JsonResponse
from django.shortcuts import render, redirect
from communication.models import OTP
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
from institute.models import Institute

class LoginView(TemplateView):
    template_name='topteenfrontend/user/LoginForm.html'

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
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))

def logout(request):
    auth_logout(request)
    return redirect("/")

class LoginSignUp(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self,request,*args,**kwargs):
        data={}  
        data['message']="All fields required"
        username=request.POST.get('user_name')
        if username:
            try:
                mobile = int(username)
                email=str(username)
                username=mobile
            except:
                mobile=0
                email=str(username)
                username=email
            user=User.objects.filter(Q(mobile=mobile) | Q(email=email)).last()
            print("user",user)

            if user:                
                sign = Signer()
                enc_user_name=sign.sign_object(({"enc_user_name":username}))
                data['enc_user_name']=enc_user_name  
                data["show_password"]=True
                data["show_otp"]=False
                data['user_name']=username
                return Response(data, status=status.HTTP_200_OK)
            else:   
                otp_type=choices.CommunicationTypeChooices.SMS if isinstance(username, int) else choices.CommunicationTypeChooices.EMAIL
                
                send_otp_mail.delay(username,otp_type)
                print("send_otp_mail(username,otp_type)")
                
                data['user_name']=username
                data["show_otp"]=True
                data["show_password"]=False
                print("data",data)
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
                sign = Signer()
                enc_user_name=sign.sign_object(({"enc_user_name":username}))
                data['enc_user_name']=enc_user_name  
                data["otp_verify"]=True  
                data['user_name']=username
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
        username=request.POST.get("enc_user_name")
        refer_user_enc=request.POST.get('enc_referral_user')
        sign=Signer()
        if refer_user_enc:
            refer_user=sign.unsign_object(refer_user_enc)
            refer_user_id=refer_user.get('refer_enc_id')
        else:
            refer_user_id=None
        if pwd and username:
            signobj=sign.unsign_object(username)
            username=signobj.get('enc_user_name')
            try:
                mobile = int(username)
                email=None
                username=mobile
            except:
                mobile=None
                email=str(username)
                username=email
            if mobile and email is None:
                # user_dict={'mobile':username,'password': pwd}
                user_dict={'mobile':username,'password': pwd,'referral':refer_user_id}
            else:
                # user_dict={'email':username,'password': pwd}
                user_dict={'email':username,'password': pwd,'referral':refer_user_id}
            user=User.create_user(**user_dict)
            if user:
                data['success']=True
            return  Response(data, status=status.HTTP_200_OK)
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

class LoginPassword(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data={}
        data['message']="All fields required"
        pwd = request.POST.get('password') 
        username=request.POST.get("enc_user_name")
        if pwd and username:
            sign=Signer()
            signobj=sign.unsign_object(username)
            username=signobj.get('enc_user_name')
            try:
                mobile = int(username)
                email=None
                username=mobile
            except:
                mobile=None
                email=str(username)
                username=email
            user=authenticate(username=username,password=pwd)
            if user and user.get_user_status():
                login(request,user)
                data['success']=True

                # add counselor
                institute=Institute.objects.filter(created_by=request.user).last()
                institute_group=Institute.objects.filter(institute_group__institute_group_admin=request.user)
                if (request.user.user_type==choices.UserType.INSTITUTE) and institute:
                    data['redirect_url']=reverse('institute:institutedashboard',args=[institute.slug])
                elif institute_group.exists() and (request.user.user_type==choices.UserType.INSTITUTEGROUPADMIN):
                    data['redirect_url']=reverse('institute:institutegroupdashboard')
                elif (request.user.user_type==choices.UserType.COUNSELOR):
                    data['redirect_url']=reverse('counselor:CounselorDashboardView')
                else:
                    # data['redirect_url']=reverse('users:userfeeds')
                    data['redirect_url']=reverse('app:test_buttons')
                return  Response(data, status=status.HTTP_200_OK)
            data['success']=False
            if not user.get_user_status():
                data['errMsg']="Account Blocked: Sorry, but your access has been restricted. For more information, kindly get in touch with our support team."
            else:
                data['errMsg']="Password doesn't match try again"
            return  Response(data, status=status.HTTP_200_OK)
        return Response(data, status=status.HTTP_400_BAD_REQUEST)


class ForgotPassword(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self,request,*args,**kwargs):
        data={}  
        data['message']="All fields required"
        cs=ComService()
        username=request.POST.get('user_name')
        if username:
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
                send_otp_mail(username,otp_type)
                sign = Signer()
                enc_user_name=sign.sign_object(({"enc_user_name":username}))
                data['enc_user_name']=enc_user_name  
                data["show_password"]=True  
                data['success']=True
                data['user_name']=username
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
            try:
                mobile = int(username)
                email=str(username)
                username=mobile
            except:
                mobile=0
                email=str(username)
                username=email    
            otp_type=choices.CommunicationTypeChooices.SMS if isinstance(username, int) else choices.CommunicationTypeChooices.EMAIL
            send_otp_mail(username,otp_type)
            data['message']="Otp Send Successfully"
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


#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class ProfileBasicDetails(TemplateView):
    template_name="topteenfrontend/user/onboardingpage.html"

    def html_head(self):
        name='User profile update'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args, **kwargs):
        ctx={}
        ctx['hobbies']=Hobbies.objects.all()
        ctx['subjects']=Subject.objects.all()
        ctx['figureouts']=UserFigureOut.objects.all()
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
        if name and mobile and birthdate and gender and grade and school and figure_outs and subjects and hobbies and figure_outs:
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
            user_profile.hobbies.add(*hobbies)
            user_profile.subject.add(*subjects)
            user_profile.figure_out.add(*figure_outs)
            user_profile.save()
            user.is_completed=True
            user.save()
            return redirect(reverse('users:userdashboard'))
        return render(request,self.template_name, self.get_context(request,args, kwargs))



# #thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserDashboard(TemplateView):
    template_name ="topteenfrontend/user/user_dashboard.html"

    def html_head(self):
        name='User Profile'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        tags=CareerTags.objects.all().order_by('priority')[:5]
        country=Country.objects.all().order_by('priority')
        ctx={}
        ctx['blogs'] = Blog.get_published_objects().all()
        ctx['colleges'] = College.get_all_colleges()
        ctx['careers'] = Career.get_all_careers()
        ctx['careers_video']=Career.objects.filter(publish_status=choices.PublishStatus.PUBLISHED).exclude(Q(video_url=""))
        ctx['videos'] = Videos.objects.all()
        ctx['courses'] = Course.get_all_courses()
        ctx['tags']=tags
        ctx['countries']=country
        ctx['exams']=EntranceExam.objects.all().order_by('?')[:3]
        # ctc=CentralTestCandidate.objects.filter(user=request.user).last()
        ctc=CentralTestCandidate.objects.filter(user=request.user).last()
        try:
            ctc.last_test_is_success()
            ctx['central_test_candidate']=ctc
        except:
            ctx['central_test_candidate']=False
        ctx["html_head"] = self.html_head()
        ctx["notes"]=UserNote.objects.filter(user=request.user)[:3]
        return ctx

    def post(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))
        

#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserFeeds(TemplateView):
    template_name ="topteenfrontend/user/userfeeds.html"
    
    def html_head(self):
        name='User Feeds'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        print("current_user", request.user)
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

#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class Scrapbook(TemplateView):
    template_name="topteenfrontend/user/scrapbook.html"

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

#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class MyNotePad(TemplateView):
    template_name="topteenfrontend/user/mynotepad.html"

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

#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class CreateNote(TemplateView):
    template_name="topteenfrontend/user/createnote.html"

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

#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserHobbies(TemplateView):
    template_name="topteenfrontend/user/myhobbies.html"

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
        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,*args, **kwargs))
    
#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserColleges(TemplateView):
    template_name="topteenfrontend/user/mycolleges.html"

    def __breadcrumb(self):
        l=[{'title':'Profile page','text':'Profile page','url':reverse_lazy('users:userdashboard')},{'title':'Scrapbook','text':'Scrapbook','url':reverse_lazy('users:scrapbook')},{'title':'My Colleges','text':'My Colleges','url':''}]
        return build_breadcrumb(l)

    def html_head(self):
        name='My Colleges'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx['breadcrumb']=self.__breadcrumb()
        ctx['colleges']=CollegeShortlist.objects.filter(user=request.user)
        print("#"*30)
        print(ctx['colleges'])
        print("#"*30)
        return ctx

    def get(self, request,*args, **kwargs):
        return render(request, self.template_name, self.get_context(request,*args, **kwargs))

#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class CareerInterests(TemplateView):
    template_name="topteenfrontend/user/careerinterest.html"


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
        career_interests=request.user.career_shortlists.all()
        ctx['career_interests']=career_interests
        ids=career_interests.values_list('career_id',flat=True)
        clstrs=CareerCluster.objects.filter(career_clusters__in=ids).distinct()
        ctx['career_ids']=ids
        ctx['clstrs']=clstrs
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))

#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class SaveMedia(TemplateView):
    template_name="topteenfrontend/user/savemedia.html"

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


#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class ResumeBuilder(TemplateView):
    template_name="topteenfrontend/user/resumebuilder.html"

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


#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class ResumeBuilderWelcome(TemplateView):
    template_name="topteenfrontend/user/resumebuilderwelcomepage.html"

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
    
#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserFolders(TemplateView):
    template_name="topteenfrontend/user/userfolder.html"
    
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

#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserFolderDetail(TemplateView):
    template_name="topteenfrontend/user/folderFile.html"

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
        return redirect("users:resumebuilder")
    ctx={}
    ctx["request"]=request
    ctx["profile"]=get_object_or_404(UserProfile,user=request.user)
    ctx["user_resume"] = user_resume
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

#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserCalenderView(TemplateView):
    template_name="topteenfrontend/user/usercalender.html"

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

#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserHistoryView(TemplateView):
    template_name="topteenfrontend/user/user_history.html"

#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class Bookmark(TemplateView):
    template_name="topteenfrontend/user/bookmarklist.html"

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
    
#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class BookmarkVideo(TemplateView):
    template_name="topteenfrontend/user/bookmarkvideo.html"

    def html_head(self):
        name='My Bookmark'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        videos=Videos.objects.filter(shortlist=request.user)
        ctx["html_head"] = self.html_head()
        ctx["videos"] = videos
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))
    
#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class BookmarkExam(TemplateView):
    template_name="topteenfrontend/user/bookmarkexam.html"

    def html_head(self):
        name='My Exams'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        exams=EntranceExam.objects.filter(shortlist=request.user)
        ctx["html_head"] = self.html_head()
        ctx["exams"] = exams
        return ctx

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


#thod_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class BookmarkCollege(TemplateView):
    template_name="topteenfrontend/user/bookmarkcollege.html"

    def html_head(self):
        name='My Colleges'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx["colleges"] = College.objects.filter(shortlist=request.user)

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