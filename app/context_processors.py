# app/context_processors.py

from .models import UserProfile

def user_profile(request):
    user_profile = None
    if request.user.is_authenticated:
        try:
            user_profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            pass
    return {
        'user_profile': user_profile
    }
