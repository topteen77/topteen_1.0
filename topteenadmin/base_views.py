import re
import json
from urllib import request
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.views.generic.base import ContextMixin,View
from django.views.generic import TemplateView,ListView,CreateView, UpdateView,DeleteView,DetailView
from django.template.loader import get_template
from datetime import datetime
from .utils import build_admin_breadcrumb
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.contrib.auth.decorators import user_passes_test,login_required
from django.utils.decorators import method_decorator
from django.http import HttpResponseRedirect

# #region agent log
_DEBUG_LOG = "/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/topteen_1.0/.cursor/debug-b428b8.log"
def _agent_log(msg, data, hypothesis_id):
    try:
        with open(_DEBUG_LOG, "a") as f:
            f.write(json.dumps({"sessionId": "b428b8", "message": msg, "data": data, "hypothesisId": hypothesis_id, "timestamp": __import__("time").time() * 1000}) + "\n")
    except Exception:
        pass
# #endregion

PER_PAGE_CHOICES = [
    ('all', 'All'),
    (25, '25'),
    (100, '100'),
    (500, '500'),
]

@method_decorator(login_required,name='dispatch')
class BaseListView(ListView):
    paginate_by = 25
    paginate_orphans = 2

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', '25')
        if per_page == 'all':
            return None
        try:
            val = int(per_page)
            if val in (25, 100, 500):
                return val
        except (ValueError, TypeError):
            pass
        return 25

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
        # #region agent log
        try:
            base_tpl = get_template('topteenadmin/base.html')
            origin_path = getattr(getattr(base_tpl, 'origin', None), 'name', None) or str(getattr(base_tpl, 'origin', ''))
            _agent_log("BaseListView get_context_data", {"request_path": self.request.path, "template_name": self.template_name, "base_origin": origin_path, "active_tab": self.active_tab}, "H2")
        except Exception as e:
            _agent_log("BaseListView get_context_data resolve error", {"request_path": self.request.path, "template_name": self.template_name, "error": str(e)}, "H4")
        # #endregion
        ctx['now'] = datetime.now()
        title=self.title
        ctx['active_tab']=self.active_tab
        ctx['meta_title']=title
        ctx['html_head']={'title':title,'description':''}
        ctx['breadcrumb']=self._breadcrumb()
        ctx['filter_form']=self._get_filter_form()
        # Pagination: per_page dropdown and page numbers
        ctx['per_page_choices'] = PER_PAGE_CHOICES
        ctx['current_per_page'] = self.request.GET.get('per_page', '25')
        if ctx.get('paginator'):
            ctx['total_count'] = ctx['paginator'].count
            ctx['page_numbers'] = self._get_page_numbers(ctx['paginator'], ctx['page_obj'])
        else:
            ctx['total_count'] = len(ctx.get('object_list', []))
            ctx['page_numbers'] = []
        return ctx

    def _get_page_numbers(self, paginator, page_obj):
        """Return list of page numbers to display, with '...' for gaps."""
        num_pages = paginator.num_pages
        current = page_obj.number
        if num_pages <= 9:
            return list(range(1, num_pages + 1))
        result = [1]
        if current > 3:
            result.append('...')
        for p in range(max(2, current - 2), min(num_pages, current + 2) + 1):
            if p not in result:
                result.append(p)
        if current < num_pages - 2:
            result.append('...')
        if num_pages > 1 and num_pages not in result:
            result.append(num_pages)
        return result

    def get_queryset(self):
        qs = super().get_queryset()
        return self._get_filters(qs).qs

    def _breadcrumb(self):
        class_name = self.model.__name__.lower()
        list_url = reverse_lazy('topteenadminmanaged:{}list'.format(class_name))
        return build_admin_breadcrumb([
            {'title': self.title, 'text': self.title, 'url': list_url},
        ])

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
        class_name = self.model()._get_class_name().lower()
        list_url = reverse_lazy('topteenadminmanaged:{}list'.format(class_name))
        return build_admin_breadcrumb([
            {'title': self.title, 'text': self.title, 'url': list_url},
            {'title': 'Add', 'text': 'Add new', 'url': '#'},
        ])

    def get_success_url(self, *args, **kwargs):
        url = super().get_success_url( *args, **kwargs)
        if self.request.method == "POST" and self.request.POST.get('_popup') == "1":
            url ="{}?_popupsubmit=1&id={}&name={}&foreign_key={}".format(url,self.object.id,str(self.object),self.request.POST.get('foreign_key'))
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
        class_name = self.model()._get_class_name().lower()
        list_url = reverse_lazy('topteenadminmanaged:{}list'.format(class_name))
        return build_admin_breadcrumb([
            {'title': self.title, 'text': self.title, 'url': list_url},
            {'title': 'Edit', 'text': 'Edit', 'url': '#'},
        ])
 
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
        class_name = self.model()._get_class_name().lower()
        list_url = reverse_lazy('topteenadminmanaged:{}list'.format(class_name))
        return build_admin_breadcrumb([
            {'title': self.title, 'text': self.title, 'url': list_url},
            {'title': 'View', 'text': 'View', 'url': '#'},
        ])    

@method_decorator(login_required,name='dispatch')   
class BaseDeleteView(DeleteView):
    def post(self, request, *args, **kwargs):
        resp= self.delete(request, *args, **kwargs)
        messages.success(self.request, self.success_message)
        return resp