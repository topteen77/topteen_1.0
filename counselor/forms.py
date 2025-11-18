# counselor/forms.py
from django import forms
from .models import Counselor
from institute.models import StudentManagement

class CounselorAdminForm(forms.ModelForm):
    class Meta:
        model = Counselor
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'counselor_admin' in self.fields:
            institute = self.instance.counselor_admin
            # Filter students based on the associated institute
            self.fields['students'].queryset = StudentManagement.objects.filter(institute=institute) if institute else StudentManagement.objects.none()

class AssignStudentsForm(forms.Form):
    students = forms.ModelMultipleChoiceField(queryset=StudentManagement.objects.none(), widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, **kwargs):
        institute = kwargs.pop('institute')
        super().__init__(*args, **kwargs)
        self.fields['students'].queryset = StudentManagement.objects.filter(institute=institute).exclude(counselor__isnull=False)
