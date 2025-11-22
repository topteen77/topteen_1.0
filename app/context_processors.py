# app/context_processors.py

from users.models import UserProfile

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

def has_payment(request):
    """Check if user has made a payment for psychometric test"""
    payment_status = False
    if request.user.is_authenticated:
        try:
            from psychometric_tests.models import PsychometricTestPayment
            from core import choices
            from institute.models import StudentManagement
            
            # Check if user is an institute-registered student (exempt from payment check)
            is_institute_student = StudentManagement.objects.filter(student=request.user).exists()
            
            if is_institute_student:
                # Institute students are considered as having payment
                payment_status = True
            else:
                # Check if user has any successful payment
                # YesNoChoices.YES = 1
                payments = PsychometricTestPayment.objects.filter(
                    user=request.user,
                    is_success=choices.YesNoChoices.YES
                )
                payment_status = payments.exists()
                
    
        except Exception as e:
            # Log the error for debugging
            import traceback
            print(f"[ERROR] Error checking payment status for user {request.user.id if request.user.is_authenticated else 'anonymous'}: {str(e)}")
            print(traceback.format_exc())
            # If there's any error, default to False
            payment_status = False
    # Debug: Print payment status (remove in production)
    if payment_status:
        print(f"[DEBUG] User {request.user.id} has payment: {payment_status}")
        print(f"[DEBUG] Payment count: {payments.count()}")
    
    return {
        'has_payment': payment_status
    }
