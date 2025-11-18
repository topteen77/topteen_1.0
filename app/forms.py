# quiz/forms.py

from django import forms

class UploadFileForm(forms.Form):
    file = forms.FileField()

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
# from .models import UserProfile

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control custom-input',
        'placeholder': 'Enter your email'
    }))
    name_of_student = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'form-control custom-input',
        'placeholder': 'Enter your name'
    }))
    grade = forms.CharField(max_length=50, widget=forms.TextInput(attrs={
        'class': 'form-control custom-input',
        'placeholder': 'Enter your grade'
    }))
    college = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'form-control custom-input',
        'placeholder': 'Enter your School'
    }))
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]
    gender = forms.ChoiceField(choices=GENDER_CHOICES, widget=forms.Select(attrs={
        'class': 'form-control custom-input'
    }))

    password1 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control custom-input', 
        'placeholder': 'Enter your password'
    }))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control custom-input', 
        'placeholder': 'Confirm your password'
    }))

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'name_of_student', 'grade', 'college', 'gender']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control custom-input', 'placeholder': 'Enter your username'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.label_suffix = ''
            existing_classes = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing_classes} custom-label'.strip()
