from django.contrib import admin
from .models import CommunicationLog,OTP


# Register your models here.
class CommunicationLogAdmin(admin.ModelAdmin):
    readonly_fields = ('created','id')
    fields = ['created','to','body','type']
    date_hierarchy = 'created'
    list_display = ['id', 'created','to','type','response']
    sortable_by=['id', 'to','created']
    ordering = ['-id']
    # list_editable=['name','email']
    list_filter = ('created','type')
    search_fields=['to','body']
    list_display_links=['id','to']

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False




admin.site.register(OTP)
admin.site.register(CommunicationLog,CommunicationLogAdmin)