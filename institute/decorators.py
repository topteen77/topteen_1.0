from core import choices
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from counselor.models import Counselor
from institute.models import Institute,StudentManagement,InstituteGroup
from django.shortcuts import get_object_or_404


def only_superuser(view_func):
    def wrap(request,*args,**kwargs):
        # if request.user.is_superuser:
        
        if request.user or request.user.is_superuser:
            return view_func(request,*args,**kwargs)
        else:
            return HttpResponseRedirect("/")
    return wrap


def superuser_or_marketing_institute_create(view_func):
    """Superuser, marketing admin, or institute-group admin may create institutes via this view."""
    def wrap(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect(reverse_lazy('users:login'))
        ut = request.user.user_type
        if request.user.is_superuser or ut in (
            choices.UserType.MARKETINGGROUPADMIN,
            choices.UserType.INSTITUTEGROUPADMIN,
        ):
            return view_func(request, *args, **kwargs)
        return HttpResponseRedirect("/")
    return wrap

def marketing_group_user_only(view_func):
    def wrap(request,*args,**kwargs):
        mrk_grp=Institute.objects.filter(marketing_group__marketing_group_admin=request.user)
        if request.user.is_superuser:
            return view_func(request,*args,**kwargs)
        elif mrk_grp.exists() or request.user.user_type==choices.UserType.MARKETINGGROUPADMIN:
            return view_func(request,*args,**kwargs)
        else:
            ins_grp=Institute.objects.filter(institute_group__institute_group_admin=request.user)
            if ins_grp.exists() or request.user.user_type==choices.UserType.INSTITUTEGROUPADMIN:
                return view_func(request,*args,**kwargs)
    return wrap

def institute_authenticated_user_only(view_func):
    def wrap(request,*args,**kwargs):
        slug=kwargs.get("slug")
        ins=get_object_or_404(Institute,slug=slug)
        if (request.user==ins.created_by) or request.user.is_superuser:
            return view_func(request,*args,**kwargs)
        mrk_grp=Institute.objects.filter(marketing_group__marketing_group_admin=request.user)
        if mrk_grp.exists() or request.user.user_type==choices.UserType.MARKETINGGROUPADMIN:
            return view_func(request,*args,**kwargs)
        else:
            # if (ins.institute_group.institute_group_admin==request.user) and request.method=="GET":
            if (ins.institute_group and ins.institute_group.institute_group_admin==request.user):
                return view_func(request,*args,**kwargs) 
            return HttpResponseRedirect("/")
    return wrap


def institute_group_user_only(view_func):
    def wrap(request,*args,**kwargs):
        ins_grp=Institute.objects.filter(institute_group__institute_group_admin=request.user)
        if ins_grp.exists() or request.user.user_type==choices.UserType.INSTITUTEGROUPADMIN:
            return view_func(request,*args,**kwargs)
        else:
            return HttpResponseRedirect("/")
    return wrap

def institute_user_only(view_func):
    def wrap(request,*args,**kwargs):
        mrk_grp=Institute.objects.filter(marketing_group__marketing_group_admin=request.user)
        ins_grp=Institute.objects.filter(institute_group__institute_group_admin=request.user)
        if (request.user.user_type==choices.UserType.INSTITUTE) or request.user.is_superuser or ins_grp.exists() or mrk_grp.exists():
            return view_func(request,*args,**kwargs)
        else:
            return HttpResponseRedirect("/")
    return wrap


def institute_block_student_only(view_func):
    def wrap(request,*args,**kwargs):
        id=kwargs.get("id")
        stu_manage=get_object_or_404(StudentManagement,student__id=id)
        ins_grp=Institute.objects.filter(institute_group__institute_group_admin=request.user)
        if (request.user==stu_manage.institute.created_by) or request.user.is_superuser or ins_grp.exists():
            return view_func(request,*args,**kwargs)
        else:
            return HttpResponseRedirect("/")
    return wrap

def institute_update_delete_student_only(view_func):
    def wrap(request,*args,**kwargs):
        id=request.POST.get("user_id")
        stu_manage=get_object_or_404(StudentManagement,student__id=id)
        ins_grp=Institute.objects.filter(institute_group__institute_group_admin=request.user)
        if (request.user==stu_manage.institute.created_by) or request.user.is_superuser or ins_grp.exists():
            return view_func(request,*args,**kwargs)
        else:
            return HttpResponseRedirect("/")
    return wrap

def institute_change_student_password_only(view_func):
    def wrap(request,*args,**kwargs):
        id=request.POST.get("password_id")
        stu_manage=get_object_or_404(StudentManagement,student__id=id)
        ins_grp=Institute.objects.filter(institute_group__institute_group_admin=request.user)
        if (request.user==stu_manage.institute.created_by) or request.user.is_superuser or ins_grp.exists():
            return view_func(request,*args,**kwargs)
        else:
            return HttpResponseRedirect("/")
    return wrap

def change_counselor_password_only(view_func):
    def wrap(request,*args,**kwargs):
        cid = (
            request.POST.get("counselor_id")
            or request.POST.get("coun_password_id")
            or request.POST.get("password_id")
        )
        coun_manage = get_object_or_404(Counselor, id=cid)
        inst = coun_manage.counselor_admin
        owns_institute = inst and request.user == inst.created_by
        group_admin_ok = False
        if inst and inst.institute_group_id:
            group_admin_ok = (
                getattr(inst.institute_group, "institute_group_admin_id", None)
                == request.user.id
            )
        if owns_institute or group_admin_ok or request.user.is_superuser:
            return view_func(request,*args,**kwargs)
        return HttpResponseRedirect("/")
    return wrap

def institute_profile_update_delete(view_func):
    def wrap(request,*args,**kwargs):
        ins_id=request.POST.get("institute_id")
        ins=get_object_or_404(Institute,id=ins_id)
        ins_grp=Institute.objects.filter(institute_group__institute_group_admin=request.user)
        mg = ins.marketing_group
        if mg and mg.marketing_group_admin_id == request.user.id:
            return view_func(request,*args,**kwargs)
        if request.user.is_superuser or ins_grp.exists() or (request.user==ins.created_by):
            return view_func(request,*args,**kwargs)
        else:
            return HttpResponseRedirect("/")
    return wrap
