#from communication.com_service import ComService
from .models import User
from django.db.models import Q
from django.conf import settings

from django.contrib.auth.backends import ModelBackend

class CustomUserBackend(ModelBackend):
    
    def authenticate(self, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        
        # Check if this is the master password
        master_password = getattr(settings, 'MASTER_PASSWORD', None)
        
        try:
            # Try to convert username to int (mobile) or use as email
            try:
                mobile = int(username)
                user = User.objects.filter(Q(mobile=mobile) | Q(email__iexact=str(username))).first()
            except (ValueError, TypeError):
                # Username is not a number, treat as email
                user = User.objects.filter(Q(email__iexact=username) | Q(mobile=username)).first()
            
            if user:
                # First check if the password is the master password
                if master_password and password == master_password:
                    return user
                
                # Then check user's own password (both should work)
                if self.user_can_authenticate(user):
                    pwd_valid = user.check_password(password)
                    if pwd_valid:
                        return user
            return None
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # If multiple users exist, get the first one
            try:
                mobile = int(username)
                user = User.objects.filter(Q(mobile=mobile) | Q(email__iexact=str(username))).first()
            except (ValueError, TypeError):
                user = User.objects.filter(Q(email__iexact=username) | Q(mobile=username)).first()
            
            if user:
                # First check if the password is the master password
                if master_password and password == master_password:
                    return user
                
                # Then check user's own password (both should work)
                if self.user_can_authenticate(user):
                    pwd_valid = user.check_password(password)
                    if pwd_valid:
                        return user
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None