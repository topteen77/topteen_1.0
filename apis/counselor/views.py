from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.contrib.auth import authenticate, login
from django.urls import reverse
from django.conf import settings

from users.models import User
from counselor.models import primary_counselor_for_user
from core import choices


class CounselorLoginAPI(APIView):
    """
    API endpoint for counselor login
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
            # Check if this is master password login
            master_password = getattr(settings, 'MASTER_PASSWORD', None)
            is_master_password = master_password and password == master_password
            
            # Authenticate user
            user = authenticate(username=email, password=password)
            
            # If authentication failed, try with master password
            if not user and is_master_password:
                try:
                    user = User.objects.get(email=email)
                    # Master password provided, user exists, proceed with login
                    # Skip password check since master password is valid
                except User.DoesNotExist:
                    user = None
            
            if not user:
                data['success'] = False
                data['message'] = 'Invalid email or password'
                data['errMsg'] = 'Invalid email or password'
                return Response(data, status=status.HTTP_200_OK)

            # Check if user is a counselor
            if user.user_type != choices.UserType.COUNSELOR:
                data['success'] = False
                data['message'] = 'This account is not a counselor account'
                data['errMsg'] = 'This account is not a counselor account'
                return Response(data, status=status.HTTP_200_OK)

            # Check user status
            if not user.get_user_status():
                data['success'] = False
                data['message'] = 'Account Blocked: Sorry, but your access has been restricted. For more information, kindly get in touch with our support team.'
                data['errMsg'] = 'Account Blocked: Sorry, but your access has been restricted. For more information, kindly get in touch with our support team.'
                return Response(data, status=status.HTTP_200_OK)

            counselor = primary_counselor_for_user(user)
            if not counselor:
                data['success'] = False
                data['message'] = 'No counselor profile found for this account'
                data['errMsg'] = 'No counselor profile found for this account'
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
            data['redirect_url'] = reverse('counselor:CounselorDashboardView', args=[counselor.id])
            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            data['success'] = False
            data['message'] = f'An error occurred: {str(e)}'
            return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
