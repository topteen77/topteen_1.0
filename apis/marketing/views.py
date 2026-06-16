# old code not in use - start
# This is a new isolated API module for marketing authentication
# old code not in use - end

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.contrib.auth import authenticate, login
from django.urls import reverse
from django.core.exceptions import ValidationError
import re

from users.models import User
from users.session_utils import apply_login_session_expiry
from institute.models import InstituteMarketingGroup
from core import choices


class MarketingRegisterAPI(APIView):
    """
    API endpoint for marketing group registration
    NOTE: Marketing users can only be registered by admin, not from public website
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Marketing registration is disabled - only admin can create marketing users
        data = {
            'success': False,
            'message': 'Marketing group registration is not available. Please contact administrator to create your account.',
            'errors': {}
        }
        return Response(data, status=status.HTTP_403_FORBIDDEN)
        
        # old code not in use - start
        # Original registration code - disabled
        # old code not in use - end
        """
        Original registration logic removed - marketing users must be created by admin
        """
        data = {}
        errors = {}
        
        # Get form data
        marketing_group_name = request.POST.get('marketing_group_name', '').strip()
        marketing_email = request.POST.get('marketing_email', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        # Validation
        if not marketing_group_name:
            errors['marketing_group_name'] = ['Marketing group name is required']
        elif len(marketing_group_name) < 2:
            errors['marketing_group_name'] = ['Marketing group name must be at least 2 characters long']
        
        if not marketing_email:
            errors['marketing_email'] = ['Email is required']
        else:
            # Email format validation
            evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(evalid, marketing_email):
                errors['marketing_email'] = ['Invalid email format']
            elif User.objects.filter(email=marketing_email).exists():
                errors['marketing_email'] = ['Email already exists']

        if not password:
            errors['password'] = ['Password is required']
        elif len(password) < 8:
            errors['password'] = ['Password must be at least 8 characters long']

        if not confirm_password:
            errors['confirm_password'] = ['Please confirm your password']
        elif password and confirm_password and password != confirm_password:
            errors['confirm_password'] = ['Passwords do not match']

        # If there are errors, return them
        if errors:
            data['success'] = False
            data['errors'] = errors
            data['message'] = 'Please correct the errors below'
            return Response(data, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Create user with marketing group admin type
            user_dict = {
                'email': marketing_email,
                'name': marketing_group_name,
                'user_type': choices.UserType.MARKETINGGROUPADMIN
            }
            marketing_user = User.create_user(**user_dict)
            
            # Set the password
            marketing_user.set_password(password)
            marketing_user.save()

            # Create marketing group
            marketing_group = InstituteMarketingGroup(
                m_group_name=marketing_group_name,
                marketing_group_admin=marketing_user
            )
            marketing_group.save()

            data['success'] = True
            data['message'] = 'Your marketing group account has been created successfully. You can now login with your credentials.'
            return Response(data, status=status.HTTP_201_CREATED)

        except Exception as e:
            data['success'] = False
            data['message'] = f'An error occurred: {str(e)}'
            return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MarketingLoginAPI(APIView):
    """
    API endpoint for marketing group login
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

            # Check if user is a marketing group admin
            if user.user_type != choices.UserType.MARKETINGGROUPADMIN:
                data['success'] = False
                data['message'] = 'This account is not a marketing group account'
                data['errMsg'] = 'This account is not a marketing group account'
                return Response(data, status=status.HTTP_200_OK)

            # Check user status
            if not user.get_user_status():
                data['success'] = False
                data['message'] = 'Account Blocked: Sorry, but your access has been restricted. For more information, kindly get in touch with our support team.'
                data['errMsg'] = 'Account Blocked: Sorry, but your access has been restricted. For more information, kindly get in touch with our support team.'
                return Response(data, status=status.HTTP_200_OK)

            # Check if marketing group exists
            try:
                marketing_group = InstituteMarketingGroup.objects.get(marketing_group_admin=user)
            except InstituteMarketingGroup.DoesNotExist:
                data['success'] = False
                data['message'] = 'No marketing group found for this account'
                data['errMsg'] = 'No marketing group found for this account'
                return Response(data, status=status.HTTP_200_OK)

            apply_login_session_expiry(request, remember_me=remember_me)

            # Login user
            login(request, user, backend='users.backends.CustomUserBackend')
            
            data['success'] = True
            data['message'] = 'Login successful'
            data['redirect_url'] = reverse('institute:marketinggroupdashboard')
            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            data['success'] = False
            data['message'] = f'An error occurred: {str(e)}'
            return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

