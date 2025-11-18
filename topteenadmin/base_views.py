import re
from urllib import request
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.views.generic.base import ContextMixin,View
from django.views.generic import TemplateView,ListView,CreateView, UpdateView,DeleteView,DetailView
from datetime import datetime
from .utils import build_admin_breadcrumb
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.contrib.auth.decorators import user_passes_test,login_required
from django.utils.decorators import method_decorator
from django.http import HttpResponseRedirect

@method_decorator(login_required,name='dispatch')
class BaseListView(ListView):
    paginate_by = 25
    paginate_orphans = 2
    def _get_filters(self,qs):
        if hasattr(self,'filterset_class'):
            return self.filterset_class(self.request.GET, queryset=qs)
        else:
            raise ImproperlyConfigured(
                "%(cls)s is missing a filterset_class" % {
                    'cls': self.__class__.__name__
                }
            )
            
    def _get_filter_form(self):
        fm=self._get_filters(self.get_queryset()).form
        return fm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['now'] = datetime.now()
        title=self.title
        ctx['active_tab']=self.active_tab
        ctx['meta_title']=title
        ctx['html_head']={'title':title,'description':''}
        ctx['breadcrumb']=self._breadcrumb()
        ctx['filter_form']=self._get_filter_form()
        return ctx

    def get_queryset(self):
        qs = super().get_queryset()
        return self._get_filters(qs).qs

    def _breadcrumb(self):
        class_name=self.model.__name__.lower()
        app_name=self.model._meta.app_label
        return build_admin_breadcrumb([{'title':self.title,'text':self.title,'url':reverse_lazy('topteenadminmanaged:{}list'.format(class_name))}])

@method_decorator(login_required,name='dispatch')    
class BaseCreateView(SuccessMessageMixin,CreateView):

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        title=self.title
        ctx['active_tab']=self.active_tab
        ctx['meta_title']=title
        ctx['html_head']={'title':title,'description':''}
        ctx['breadcrumb']=self._breadcrumb()
        return ctx

    def _breadcrumb(self):
        class_name=self.model()._get_class_name()
        url=reverse_lazy('topteenadminmanaged:{}list'.format(class_name.lower()))
        lst=[{'title':'{}s'.format(class_name),'text':'{}s'.format(class_name),'url':url}]
        lst.append({'title':'AddCareer','text':'AddCareer','url':'#'})
        return build_admin_breadcrumb(lst)

    def get_success_url(self, *args, **kwargs):
        url = super().get_success_url( *args, **kwargs)
        if self.request.method == "POST" and self.request.POST.get('_popup') == "1":
            url ="{}?_popupsubmit=1&id={}&name={}&foreign_key={}".format(url,self.object.id,str(self.object),self.request.POST.get('foreign_key'))
        print("url",url)
        return url
        
@method_decorator(login_required,name='dispatch')      
class BaseUpdateView(SuccessMessageMixin,UpdateView):
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        title=self.title
        ctx['active_tab']=self.active_tab
        ctx['meta_title']=title
        ctx['html_head']={'title':title,'description':''}
        ctx['breadcrumb']=self._breadcrumb()
        return ctx

    def _breadcrumb(self):
        class_name=self.model()._get_class_name()
        url=reverse_lazy('topteenadminmanaged:{}list'.format(class_name.lower()))
        lst=[{'title':'{}s'.format(class_name),'text':'{}s'.format(class_name),'url':url}]
        lst.append({'title':'UpdateCareer','text':'UpdateCareer','url':'#'})
        return build_admin_breadcrumb(lst)
 
@method_decorator(login_required,name='dispatch')  
class BaseDetailView(UpdateView):
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        title=self.title
        ctx['active_tab']=self.active_tab
        ctx['meta_title']=title
        ctx['html_head']={'title':title,'description':''}
        ctx['breadcrumb']=self._breadcrumb()
        return ctx

    def _breadcrumb(self):
        class_name=self.model()._get_class_name()
        url=reverse_lazy('topteenadminmanaged:{}list'.format(class_name.lower()))
        lst=[{'title':'{}s'.format(class_name),'text':'{}s'.format(class_name),'url':url}]
        lst.append({'title':'Detail','text':'Detail','url':'#'})
        return build_admin_breadcrumb(lst)    

@method_decorator(login_required,name='dispatch')   
class BaseDeleteView(DeleteView):
    def post(self, request, *args, **kwargs):
        resp= self.delete(request, *args, **kwargs)
        messages.success(self.request, self.success_message)
        return resp