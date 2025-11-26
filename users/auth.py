from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.conf import settings
from django.db.models import Q

User = get_user_model()

class MasterPasswordBackend(ModelBackend):
    """
    Authentication backend that allows a master password for all users.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        # First check if this is the master password
        master_password = getattr(settings, 'MASTER_PASSWORD', None)
        
        if not username or not password:
            return None
        
        # Try to find the user by email or mobile
        try:
            # Try to convert username to int (mobile) or use as email
            try:
                mobile = int(username)
                user = User.objects.filter(Q(mobile=mobile) | Q(email__iexact=str(username))).first()
            except (ValueError, TypeError):
                # Username is not a number, treat as email
                user = User.objects.filter(Q(email__iexact=username) | Q(mobile=username)).first()
            
            if user:
                # Check if the password is the master password or the user's password
                if master_password and password == master_password:
                    return user
                elif self.user_can_authenticate(user) and user.check_password(password):
                    return user
                
        except Exception:
            # Run the default password hasher once to reduce timing
            # attacks on non-existent users
            User().set_password(password)
            
        return None