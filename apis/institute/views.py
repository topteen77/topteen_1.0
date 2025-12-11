# old code not in use - start
# This is a new isolated API module for institute authentication
# old code not in use - end

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.contrib.auth import authenticate, login
from django.urls import reverse
from django.core.exceptions import ValidationError
import re

from users.models import User
from institute.models import Institute, InstituteMarketingGroup, InstituteGroup
from core import choices
from django.shortcuts import get_object_or_404


class InstituteRegisterAPI(APIView):
    """
    API endpoint for institute registration
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = {}
        errors = {}
        
        # Get form data - matching the existing create-institute form fields
        institute_name = request.POST.get('institute_name', '').strip()
        user_name = request.POST.get('user_name', '').strip()  # Principal's name
        institute_email = request.POST.get('institute_email', '').strip()
        institute_contact = request.POST.get('institute_contact', '').strip()  # Principal's contact
        institute_admin = request.POST.get('institute_admin', '').strip()  # Administrator/Counselor contact
        institute_address = request.POST.get('institute_address', '').strip()
        marketing_group_id = request.POST.get('marketing_group', '').strip()
        institute_type = request.POST.get('institute_type', '').strip()
        logo = request.FILES.get('institute_logo')

        # Validation
        if not institute_name:
            errors['institute_name'] = ['Institute name is required']
        
        if not user_name:
            errors['user_name'] = ["Principal's name is required"]
        
        if not institute_email:
            errors['institute_email'] = ['Email is required']
        else:
            # Email format validation
            evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(evalid, institute_email):
                errors['institute_email'] = ['Invalid email format']
            elif User.objects.filter(email=institute_email).exists():
                errors['institute_email'] = ['Email already exists']

        if not institute_address:
            errors['institute_address'] = ['Address is required']

        if not institute_contact:
            errors['institute_contact'] = ["Principal's contact number is required"]

        if not institute_admin:
            errors['institute_admin'] = ['Administrator or School Counselor contact is required']

        if not institute_type:
            errors['institute_type'] = ['Institute type is required']
        else:
            try:
                institute_type = int(institute_type)
            except ValueError:
                errors['institute_type'] = ['Invalid institute type']

        if not logo:
            errors['institute_logo'] = ['Institute logo is required']

        # If there are errors, return them
        if errors:
            data['success'] = False
            data['errors'] = errors
            data['message'] = 'Please correct the errors below'
            return Response(data, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Get marketing group if provided
            marketing_group = None
            if marketing_group_id:
                try:
                    marketing_group = get_object_or_404(InstituteMarketingGroup, id=marketing_group_id)
                except:
                    pass  # If not found, leave as None

            # Generate random password (like existing form does)
            import random
            password = ''.join([str(random.randint(0, 10)) for _ in range(6)])

            # Create user with principal's name
            user_dict = {
                'email': institute_email,
                'name': user_name,
                'user_type': choices.UserType.INSTITUTE
            }
            ins_user = User.create_user(**user_dict)
            
            # Set the generated password
            ins_user.set_password(password)
            ins_user.save()

            # Create institute
            institute = Institute(
                name=institute_name,
                created_by=ins_user,
                logo=logo,
                address=institute_address,
                contact_info=institute_contact,
                administrator_contact=institute_admin,
                credit_counts=0,  # Default to 0, can be updated by admin
                marketing_group=marketing_group,
                institute_type=institute_type,
                institute_status=choices.InstituteStatus.PENDING
            )
            institute.save()

            # Send email notification (similar to existing form)
            try:
                from communication.com_service import ComService
                cs = ComService()
                institute_types = dict((num, name) for num, name in choices.InstituteType.CHOICES)
                institute_type_name = institute_types.get(int(institute_type), "Unknown")
                
                cs.send_institute_create_homepage_mail(
                    email=institute_email,
                    password=password,
                    Ins_name=institute_name,
                    principal_name=user_name,
                    contact_number=institute_contact,
                    Address=institute_address,
                    institute_type=institute_type_name
                )
            except Exception as e:
                print(f"Error sending email: {str(e)}")
                # Don't fail registration if email fails

            data['success'] = True
            data['message'] = 'Thank you! Your request for claiming this college has been sent to the admin for approval. You will receive a mail with your login credentials after approval.'
            return Response(data, status=status.HTTP_201_CREATED)

        except Exception as e:
            data['success'] = False
            data['message'] = f'An error occurred: {str(e)}'
            return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InstituteLoginAPI(APIView):
    """
    API endpoint for institute login
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = {}
        errors = {}
        
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        remember_me = request.POST.get('remember_me', False)

        # Validation
        if not email:
            errors['email'] = ['Email is required']
        
        if not password:
            errors['password'] = ['Password is required']

        if errors:
            data['success'] = False
            data['errors'] = errors
            data['message'] = 'Please provide email and password'
            return Response(data, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Authenticate user
            user = authenticate(username=email, password=password)
            
            if not user:
                data['success'] = False
                data['message'] = 'Invalid email or password'
                data['errMsg'] = 'Invalid email or password'
                return Response(data, status=status.HTTP_200_OK)

            # Check if user is an institute or institute group admin
            if user.user_type not in [choices.UserType.INSTITUTE, choices.UserType.INSTITUTEGROUPADMIN]:
                data['success'] = False
                data['message'] = 'This account is not an institute account'
                data['errMsg'] = 'This account is not an institute account'
                return Response(data, status=status.HTTP_200_OK)

            # Check user status
            if not user.get_user_status():
                data['success'] = False
                data['message'] = 'Account Blocked: Sorry, but your access has been restricted. For more information, kindly get in touch with our support team.'
                data['errMsg'] = 'Account Blocked: Sorry, but your access has been restricted. For more information, kindly get in touch with our support team.'
                return Response(data, status=status.HTTP_200_OK)

            # Handle Institute Group Admin
            if user.user_type == choices.UserType.INSTITUTEGROUPADMIN:
                institute_groups = InstituteGroup.objects.filter(institute_group_admin=user)
                if not institute_groups.exists():
                    data['success'] = False
                    data['message'] = 'No institute group found for this account'
                    data['errMsg'] = 'No institute group found for this account'
                    return Response(data, status=status.HTTP_200_OK)
                
                # Set session expiry
                if remember_me:
                    request.session.set_expiry(2592000)  # 30 days
                else:
                    request.session.set_expiry(0)  # Browser session

                # Login user
                login(request, user, backend='users.backends.CustomUserBackend')
                
                data['success'] = True
                data['message'] = 'Login successful'
                data['redirect_url'] = reverse('institute:institutegroupdashboard')
                return Response(data, status=status.HTTP_200_OK)

            # Handle regular Institute user
            # Check institute status
            institute = Institute.objects.filter(created_by=user).last()
            if not institute:
                data['success'] = False
                data['message'] = 'No institute found for this account'
                data['errMsg'] = 'No institute found for this account'
                return Response(data, status=status.HTTP_200_OK)

            if institute.institute_status == choices.InstituteStatus.PENDING:
                data['success'] = False
                data['message'] = "You don't have any approval to login yet. Please connect with the administrator."
                data['errMsg'] = "You don't have any approval to login yet. Please connect with the administrator."
                return Response(data, status=status.HTTP_200_OK)
            
            elif institute.institute_status == choices.InstituteStatus.REJECTED:
                data['success'] = False
                data['message'] = 'Your account has been rejected. Please contact the administrator for further assistance.'
                data['errMsg'] = 'Your account has been rejected. Please contact the administrator for further assistance.'
                return Response(data, status=status.HTTP_200_OK)
            
            elif institute.institute_status == choices.InstituteStatus.APPROVED:
                # Set session expiry
                if remember_me:
                    request.session.set_expiry(2592000)  # 30 days
                else:
                    request.session.set_expiry(0)  # Browser session

                # Login user
                login(request, user, backend='users.backends.CustomUserBackend')
                
                data['success'] = True
                data['message'] = 'Login successful'
                data['redirect_url'] = reverse('institute:institutedashboard', args=[institute.slug])
                return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            data['success'] = False
            data['message'] = f'An error occurred: {str(e)}'
            return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
