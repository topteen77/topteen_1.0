from django.contrib import admin
from .models import Configuration,City, Review,State,Country,CommonFAQ,APILog,Stories,Contact,Lead
# Register your models here.



class ConfigurationAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','key')
    fields = ['created','modified','key','value']
    date_hierarchy = 'created'
    list_display = ['id', 'key','value','created','modified']
    sortable_by=['id', 'key','created']
    ordering = ['id']
    # list_editable=['name','email']
    list_filter = ('modified','created')
    search_fields=['key','value']
    list_display_links=['id','key']

    def get_queryset(self, request):
        qs = super(ConfigurationAdmin, self).get_queryset(request)
        return qs.filter(editable=True)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


class CityAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','id')
    fields = ['created','modified','id','name','state']
    date_hierarchy = 'created'
    list_display = ['id', 'name','state','country','modified']
    sortable_by=['id', 'name','created']
    ordering = ['id']
    # list_editable=['name','email']
    list_filter = ('modified','created')
    search_fields=['name','id']
    list_display_links=['id','name']

    def country(self,obj):
        if obj.state and obj.state.country:
            return obj.state.country.name
        return ''


class StateAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','id')
    fields = ['created','modified','id','name','country']
    date_hierarchy = 'created'
    list_display = ['id', 'name','country','modified']
    sortable_by=['id', 'name','created']
    ordering = ['id']
    # list_editable=['name','email']
    list_filter = ('modified','created')
    search_fields=['name','id']
    list_display_links=['id','name']




class CountryAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','id')
    fields = ['created','modified','id','name','phone_code','short_name','priority','flag']
    date_hierarchy = 'created'
    list_display = ['id', 'name','short_name','modified']
    sortable_by=['id', 'name','created']
    ordering = ['id']
    # list_editable=['name','email']
    list_filter = ('modified','created')
    search_fields=['name','id']
    list_display_links=['id','name']

class ContactAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','id')
    fields = ['created','modified','id','name','mobile','email','message']
    list_display = ['id','name','email']
    list_display_links=['id','name']
    search_fields=['name','email']
    list_filter = ['created','modified','name','email']

class LeadAdmin(admin.ModelAdmin):
    readonly_fields = ('created','modified','id')
    fields = ['created','modified','id','name','mobile']
    list_display = ['id','name','mobile']
    list_display_links=['id','name']
    search_fields=['name']
    list_filter = ['created','modified']

admin.site.register(Configuration,ConfigurationAdmin)
admin.site.register(City,CityAdmin)
admin.site.register(State,StateAdmin)
admin.site.register(Country,CountryAdmin)
admin.site.register(Lead,LeadAdmin)
admin.site.register(Review)
admin.site.register(CommonFAQ)
admin.site.register(APILog)
admin.site.register(Stories)
admin.site.register(Contact,ContactAdmin)

