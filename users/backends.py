#from communication.com_service import ComService
from .models import User
from django.db.models import Q

from django.contrib.auth.backends import ModelBackend

class CustomUserBackend(ModelBackend):
    
    def authenticate(self, username=None, password=None):
        # try:
        #     mobile=int(username)
        #     email=None
        # except:
        #     mobile=None
        #     email=str(username)
        email=username
        try:
             user = User.objects.get(
                 Q(email=email) 
             )
             pwd_valid = user.check_password(password) 
             if user and pwd_valid:            
                return user
             return None
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None