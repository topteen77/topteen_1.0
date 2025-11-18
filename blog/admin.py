from django.contrib import admin
from blog.models import SubscriptionEmail
# Register your models here.
class SubscriptionEmailAdmin(admin.ModelAdmin):
    fields=['email']
    list_display=['email','created']

admin.site.register(SubscriptionEmail,SubscriptionEmailAdmin)