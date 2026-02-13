from django.contrib import admin
from .models import PsychometricTestPayment,CentralTestCandidate,CandidateTest,PsychometricTestResult

class PsychometricTestPaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'user_type_display', 'test_type', 'amount_display', 'is_success', 'gateway_receipt', 'created']
    list_filter = ('is_success', 'test_type', 'created')
    search_fields = ('user__email', 'user__name', 'user__mobile', 'gateway_receipt')
    list_select_related = ('user',)
    ordering = ('-created',)
    date_hierarchy = 'created'

    def user_type_display(self, obj):
        return obj.user.get_user_type_display() if obj and obj.user else '-'

    user_type_display.short_description = 'Role'

    def amount_display(self, obj):
        return obj.get_display_price() if obj else '-'

    amount_display.short_description = 'Amount'
    
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