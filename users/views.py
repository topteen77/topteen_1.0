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

                # Generate random password
                password = "12345"

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
                    data['redirect_url'] = reverse('users:userdashboard')
                    return Response(data, status=status.HTTP_200_OK)
                else:
                    # New user - proceed to password form
                    sign = Signer()
                    enc_user_name=sign.sign_object(({"enc_user_name":username}))
                    data['enc_user_name']=enc_user_name  
                    data["otp_verify"]=True
                    data["user_exists"]=False
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
                
                # Check if user already exists
                if mobile:
                    existing_user = User.objects.filter(mobile=mobile).first()
                else:
                    existing_user = User.objects.filter(email=email).first()
                
                if existing_user:
                    data['message'] = "User with this email/mobile already exists. Please login instead."
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)
                
                try:
                    user=User.create_user(**user_dict)
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
                    
                    # Return redirect URL to dashboard after signup
                    # User is created successfully, so return success even if profile/login had minor issues
                    data['success'] = True
                    data['message'] = "Account created successfully"
                    data['redirect_url'] = reverse('users:userdashboard')
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
                    data['redirect_url'] = reverse('users:userdashboard')
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
                mobile = int(username)
                email = None
                username = mobile
            except:
                mobile = None
                email = str(username)
                username = email
            user = authenticate(username=username, password=pwd)
            
            if user and user.get_user_status():
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
                
                # Default redirect to user dashboard instead of test buttons
                # Test buttons now requires payment, so redirect to dashboard first
                data['redirect_url'] = reverse('users:userdashboard')
                
                # Get student class information if available
                student_info = None
                try:
                    if user.user_type != choices.UserType.INSTITUTE and user.user_type != choices.UserType.INSTITUTEGROUPADMIN and user.user_type != choices.UserType.MARKETINGGROUPADMIN and user.user_type != choices.UserType.COUNSELOR:
                        student_management = StudentManagement.objects.filter(student=user).first()
                        if student_management and student_management.class_and_section:
                            class_name = student_management.class_and_section.class_and_section
                            stream = student_management.class_and_section.stream
                            
                            # Check if class is 11 or 12 and redirect to post_matric
                            if class_name:
                                # Extract first 2 characters from class_name and check if it's 11 or 12
                                class_prefix = class_name[:2].strip()
                                if class_prefix == "11" or class_prefix == "12":
                                    data['redirect_url'] = reverse('post_matric:tests')
                                    print(f"Student in class {class_prefix} redirected to post_matric:home")
                            
                            # Format student info for display
                            if stream:
                                student_info = f"Class: {class_name}, Stream: {stream}"
                            else:
                                student_info = f"Class: {class_name}"
                            data['student_class'] = student_info
                            print(f"Student logged in - {student_info}")
                except Exception as e:
                    print(f"Error retrieving student class information: {str(e)}")

                
                if user.user_type == choices.UserType.INSTITUTE:
                    # Handle institute user
                    institute = Institute.objects.filter(created_by=user).last()
                    if institute:
                        if institute.institute_status == choices.InstituteStatus.PENDING:
                            data['success'] = False
                            data['errMsg'] = "You don't have any approval to login yet. Please connect with the administrator."
                            return Response(data, status=status.HTTP_200_OK)
                        elif institute.institute_status == choices.InstituteStatus.REJECTED:
                            data['success'] = False
                            data['errMsg'] = "Your account has been rejected. Please contact the administrator for further assistance."
                            return Response(data, status=status.HTTP_200_OK)
                        elif institute.institute_status == choices.InstituteStatus.APPROVED:
                            data['redirect_url'] = reverse('institute:institutedashboard', args=[institute.slug])

                elif user.user_type == choices.UserType.INSTITUTEGROUPADMIN:
                    try:
                        institute_groups = InstituteGroup.objects.filter(institute_group_admin=user)
                        if institute_groups.exists():
                            first_institute_group = institute_groups.first()
                            data['redirect_url'] = reverse('institute:institutegroupdashboard')                    
                        else:
                            data['success'] = False
                            data['errMsg'] = "No institute group found for this administrator."
                    except Exception as e:
                        data['success'] = False
                        data['errMsg'] = f"Error retrieving institute group: {str(e)}"
                
                elif user.user_type == choices.UserType.MARKETINGGROUPADMIN:
                    # Handle marketing group admin
                    marketing_group = Institute.objects.filter(marketing_group__marketing_group_admin=user)
                    if marketing_group.exists():
                        data['redirect_url'] = reverse('institute:marketinggroupdashboard')
                    else:
                        data['success'] = False
                        data['errMsg'] = "No Marketing group found for this administrator."

                elif user.user_type == choices.UserType.COUNSELOR:
                    # Handle counselor
                    try:
                        coun = Counselor.objects.get(coun_user=user)
                        data['redirect_url'] = reverse('counselor:CounselorDashboardView', args=[coun.id])
                    except Counselor.DoesNotExist:
                        pass

                return Response(data, status=status.HTTP_200_OK)
                
            data['success'] = False
            if not user:
                data['errMsg'] = "Password doesn't match try again"
            elif not user.get_user_status():
                data['errMsg'] = "Account Blocked: Sorry, but your access has been restricted. For more information, kindly get in touch with our support team."
            else:
                data['errMsg'] = "Password doesn't match try again"
                
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
            
            # Check for students - check if in class 11 or 12
            else:
                student_management = StudentManagement.objects.filter(student=user).first()
                if student_management and student_management.class_and_section:
                    class_name = student_management.class_and_section.class_and_section
                    if class_name:
                        class_prefix = class_name[:2].strip()
                        if class_prefix == "11" or class_prefix == "12":
                            redirect_url = reverse('post_matric:tests')
        
        except Exception as e:
            print(f"Error getting dashboard URL: {e}")
        
        return Response({'redirect_url': redirect_url}, status=status.HTTP_200_OK)


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
            # Get OTP and print it before sending
            otp = cs.get_otp(username, otp_type)
            # Print OTP to terminal for debugging
            if otp_type == choices.CommunicationTypeChooices.EMAIL:
                print(f"Resend - Email OTP for {username}: {otp}")
            else:
                print(f"Resend - SMS OTP for {username}: {otp}")
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


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class ProfileBasicDetails(TemplateView):
    template_name="template20/user/profile_basic_details.html"

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


@method_decorator(login_required(login_url=reverse_lazy('users:login')),name='dispatch')
class UserDashboard(TemplateView):
    template_name ="template20/user/user_dashboard.html"

    def html_head(self):
        name='User Profile'
        return build_html_head(title=name, description=name)

    def get_context(self,request,*args,**kwargs):
        from psychometric_tests.models import PsychometricTestPayment
        
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
        
        # Determine user's class (10 or 12)
        from institute.models import StudentManagement
        user_grade = None
        try:
            user_profile = request.user.user_profile
            if user_profile and user_profile.grade:
                user_grade = str(user_profile.grade)
        except:
            pass
        
        # If no grade from UserProfile, check StudentManagement
        if not user_grade:
            try:
                student_management = StudentManagement.objects.filter(student=request.user).first()
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
            user=request.user,
            is_success=choices.YesNoChoices.YES
        ).order_by('-created').first()
        
        ctx['psychometric_test_payment'] = successful_test_payment
        ctx['test_dashboard_url'] = None
        ctx['test_name'] = None
        ctx['has_test_payment'] = False
        
        # Check if user has purchased test for their class
        if user_grade == "10":
            # Class 10 should have BASIC test (Stream Sorter)
            class_test_payment = PsychometricTestPayment.objects.filter(
                user=request.user,
                test_type=choices.PsychometricTestType.BASIC,
                is_success=choices.YesNoChoices.YES
            ).first()
            if class_test_payment:
                ctx['has_test_payment'] = True
                ctx['test_dashboard_url'] = '/psychometric/home'
                ctx['test_name'] = 'Stream Sorter'
        elif user_grade == "12":
            # Class 12 should have ADVANCED test (Career Direction)
            class_test_payment = PsychometricTestPayment.objects.filter(
                user=request.user,
                test_type=choices.PsychometricTestType.ADVANCED,
                is_success=choices.YesNoChoices.YES
            ).first()
            if class_test_payment:
                ctx['has_test_payment'] = True
                ctx['test_dashboard_url'] = '/api/web/tests/'
                ctx['test_name'] = 'Career Direction'
        
        # Also check for any successful payment (for backward compatibility)
        if successful_test_payment and not ctx['has_test_payment']:
            if successful_test_payment.test_type == choices.PsychometricTestType.BASIC:
                ctx['test_dashboard_url'] = '/psychometric/home'
                ctx['test_name'] = 'Stream Sorter'
            elif successful_test_payment.test_type == choices.PsychometricTestType.ADVANCED:
                ctx['test_dashboard_url'] = '/psychometric/home'
                ctx['test_name'] = 'Career Direction'
        
        # Add buy URLs
        from django.urls import reverse
        ctx['test_buy_url_class10'] = reverse('psychometrictests:psychometrictest')
        # Class 12 students should redirect to /api/web/tests/ instead of PsychometricTest12
        ctx['test_buy_url_class12'] = '/api/web/tests/'
        
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
        career_interests=request.user.career_shortlists.all()
        ctx['career_interests']=career_interests
        ids=career_interests.values_list('career_id',flat=True)
        clstrs=CareerCluster.objects.filter(career_clusters__in=ids).distinct()
        ctx['career_ids']=ids
        ctx['clstrs']=clstrs
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
        videos=Videos.objects.filter(shortlist=request.user)
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
        exams=EntranceExam.objects.filter(shortlist=request.user)
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
        ctx={}
        ctx["html_head"] = self.html_head()
        ctx["colleges"] = College.objects.filter(shortlist=request.user)
        ctx['breadcrumb']=self.__breadcrumb()

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