import django_filters

class BaseFilter(django_filters.FilterSet):
    def __init__(self,data=None, queryset=None, *, request=None, prefix=None):
        super().__init__(data=data, queryset=queryset, request=request, prefix=prefix)
        for field_name,field in self.filters.items():
            self.add_class_attributes(field) 
               
    def add_class_attributes(self,field):
        if hasattr(field.field.widget,'input_type'):
            if field.field.widget.input_type == 'select':
                self.add_form_control_select_class(field)
            else:
                self.add_form_control_class(field)
        else:
            self.add_form_control_class(field) 
    
    def add_form_control_class(self,field):
        if field.field.widget.attrs.get('class'):
            field.field.widget.attrs['class'] += ' form-control form-control-lg form-control-solid '
        else:
            field.field.widget.attrs['class'] = ' form-control form-control-lg form-control-solid '
            
            
    def add_form_control_select_class(self,field):
        if field.field.widget.attrs.get('class'):
            field.field.widget.attrs['class'] += ' form-select form-select-solid fw-bolder js-example-basic-single'
        else:
            field.field.widget.attrs['class'] = ' form-select form-select-solid fw-bolder js-example-basic-single'
            
class NamedBaseFilter(BaseFilter):
    name = django_filters.CharFilter(lookup_expr='icontains')