from django.contrib import admin
from .models import PsychometricTestPayment,CentralTestCandidate,CandidateTest,PsychometricTestResult

class PsychometricTestPaymentAdmin(admin.ModelAdmin):
    list_display = ['user','is_success','test_type','gateway_receipt']
    
class CentralTestCandidateAdmin(admin.ModelAdmin):
    list_display = ['user','candidate_id']

class CandidateTestAdmin(admin.ModelAdmin):
    list_display = ['pyschometric_test_payment','central_test_candidate','is_success']
    
class PsychometricTestResultAdmin(admin.ModelAdmin):
    list_display = ['assessment']
    
admin.site.register(PsychometricTestPayment,PsychometricTestPaymentAdmin)
admin.site.register(CentralTestCandidate,CentralTestCandidateAdmin)
admin.site.register(CandidateTest,CandidateTestAdmin)
admin.site.register(PsychometricTestResult,PsychometricTestResultAdmin)