from .models import ImageUploadModel
from django import forms

class ImageUploadModelForm(forms.ModelForm):

    class Meta:
        model = ImageUploadModel
        fields = ('file', 'upload')