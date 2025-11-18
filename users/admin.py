from django.contrib import admin
from .models import User,UserProfile,UserCalender, UserNote, UserResume, UserFolder, UserSearchHistory
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.html import format_html, format_html_join
from django.contrib import messages
from django.conf import settings
import os
import glob
# Register your models here.
    


class UserAdmin(admin.ModelAdmin):
    # form = UserForm
    fields = ['name','email','mobile','is_active','is_staff','image','password','groups', 'user_permissions','user_type','user_status']
    # date_hierarchy = 'created'
    list_display = ['id', 'name','email','mobile','is_active','object_status','created','last_login']
    sortable_by=['id', 'name','email','mobile']
    ordering = ['-id']
    # list_editable=['name','email']
    list_filter = ('is_active','last_login','user_type','object_status')
    search_fields=['id','name','email','mobile']
    actions = ['hard_delete_selected']
    
    def get_queryset(self, request):
        # Show all users including soft-deleted ones
        qs = User.objects.complete()
        return qs
    
    
    def save_model(self, request, obj, form, change):
        # Override this to set the password to the value in the field if it's
        # changed.
        if obj.pk:
            orig_obj = User.objects.get(pk=obj.pk)
            if obj.password != orig_obj.password:
                obj.set_password(obj.password)
        else:
            obj.set_password(obj.password)
        obj.save()
    
    def hard_delete_selected(self, request, queryset):
        """
        Admin action to permanently delete selected users and all their related data.
        This performs a hard delete (not soft delete) and removes all associated records.
        """
        deleted_count = 0
        errors = []
        
        for user in queryset:
            try:
                user_id = user.id
                user_name = user.name
                user_email = user.email
                
                # Use complete() to access all records including soft-deleted ones
                from app.models import TestCompletion, Results
                from institute.models import StudentManagement
                from careers.models import CareerShortlist
                from psychometric_tests.models import PsychometricTestPayment, CentralTestCandidate
                from payments.models import Payment
                
                # Delete TestCompletion (not a BaseModel, so regular delete)
                TestCompletion.objects.filter(user=user).delete()
                
                # Delete Results (not a BaseModel, so regular delete)
                Results.objects.filter(user=user).delete()
                
                # Delete UserProfile (CASCADE will handle related data)
                if hasattr(user, 'user_profile'):
                    try:
                        user.user_profile.delete(hard_delete=True)
                    except:
                        pass
                
                # Delete UserNotes (BaseModel - need to hard delete each instance)
                for note in UserNote.objects.complete().filter(user=user):
                    note.delete(hard_delete=True)
                
                # Delete UserResume and related
                if hasattr(user, 'user_resume'):
                    try:
                        user.user_resume.delete(hard_delete=True)
                    except:
                        pass
                
                # Delete UserFolders (BaseModel - need to hard delete each instance)
                for folder in UserFolder.objects.complete().filter(user=user):
                    folder.delete(hard_delete=True)
                
                # Delete UserCalender (BaseModel - need to hard delete each instance)
                for cal in UserCalender.objects.complete().filter(user=user):
                    cal.delete(hard_delete=True)
                
                # Delete UserSearchHistory (BaseModel - need to hard delete each instance)
                try:
                    for search in UserSearchHistory.objects.complete().filter(user=user):
                        search.delete(hard_delete=True)
                except:
                    pass
                
                # Delete StudentManagement (BaseModel - need to hard delete each instance)
                for sm in StudentManagement.objects.complete().filter(student=user):
                    sm.delete(hard_delete=True)
                
                # Delete CareerShortlist (BaseModel - need to hard delete each instance)
                try:
                    for cs in CareerShortlist.objects.complete().filter(user=user):
                        cs.delete(hard_delete=True)
                except:
                    pass
                
                # Delete PsychometricTestPayment (BaseModel - need to hard delete each instance)
                try:
                    for ptp in PsychometricTestPayment.objects.complete().filter(user=user):
                        ptp.delete(hard_delete=True)
                except:
                    pass
                
                # Delete CentralTestCandidate (BaseModel - need to hard delete)
                try:
                    if hasattr(user, 'central_test_candidate'):
                        user.central_test_candidate.delete(hard_delete=True)
                except:
                    pass
                
                # Delete Payment (BaseModel - need to hard delete each instance)
                try:
                    for payment in Payment.objects.complete().filter(user=user):
                        payment.delete(hard_delete=True)
                except:
                    pass
                
                # Delete user media files
                if user.image:
                    try:
                        if os.path.exists(user.image.path):
                            os.remove(user.image.path)
                    except:
                        pass
                
                # Delete graph images for this user
                try:
                    sanitized_name = str(user_name).replace(' ', '_')
                    graph_pattern = os.path.join(settings.MEDIA_ROOT, 'graph_images', f'{sanitized_name}-{user_id}_*.png')
                    graph_files = glob.glob(graph_pattern)
                    for graph_file in graph_files:
                        try:
                            os.remove(graph_file)
                        except:
                            pass
                except:
                    pass
                
                # Delete user PDFs
                try:
                    user_pdf_dir = os.path.join(settings.MEDIA_ROOT, 'users_pdfs', str(user_id))
                    if os.path.exists(user_pdf_dir):
                        pdf_files = glob.glob(os.path.join(user_pdf_dir, '*'))
                        for pdf_file in pdf_files:
                            try:
                                if os.path.isfile(pdf_file):
                                    os.remove(pdf_file)
                            except:
                                pass
                        # Try to remove directory if empty
                        try:
                            os.rmdir(user_pdf_dir)
                        except:
                            pass
                except:
                    pass
                
                # Finally hard delete the user
                user.delete(hard_delete=True)
                deleted_count += 1
                
            except Exception as e:
                errors.append(f"Error deleting {user.email}: {str(e)}")
        
        if deleted_count > 0:
            self.message_user(
                request,
                f'Successfully permanently deleted {deleted_count} user(s) and all associated data.',
                messages.SUCCESS
            )
        
        if errors:
            for error in errors:
                self.message_user(request, error, messages.ERROR)
    
    hard_delete_selected.short_description = "Permanently delete selected users (hard delete with all related data)"

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['id','user','birthdate','schoolname','gender']
    readonly_fields=['created','modified']

class UserCalenderAdmin(admin.ModelAdmin):
    fields=['user','event_name','start_date','end_date']
    list_display=['id','event_name','start_date','end_date']
    
admin.site.register(User,UserAdmin)

admin.site.register(UserProfile,UserProfileAdmin)
admin.site.register(UserCalender,UserCalenderAdmin)