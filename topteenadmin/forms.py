from dataclasses import fields
from distutils.command.clean import clean
from statistics import mode
from django import forms
from blog.models import Blog,BlogCategory,BlogTag
from ckeditor.fields import RichTextField
from ckeditor.widgets import CKEditorWidget
from modeltranslation import translator
from django.conf import settings
from django.db import models
from careers.models import Career, CareerFAQ, CareerMedia, CareerPath, CareerTags, Profession,Skill,ProspectiveRecruiter,ProspectiveEmploymentArea,CareerCluster,CareerPathStep,VideoCategory,Videos
from bs4 import BeautifulSoup
from django.urls import reverse
from colleges.models import College, CollegeFacts, CollegeFlatText, CollegeImages, CollegeText, Facility,RecruitingCompanies,CollegeRecruitingCompanies,CollegeFacility,CollegeMoneyValue
from core.models import City, CommonFAQ, Country, Review,State,Hobbies,Subject,UserFigureOut,Stories,APILog
from courses.models import (Stream,Course,CourseFacts,CourseIntake,CourseText,CourseMoneyValue,CourseEnglighRequirements)
from entrance_exams.models import EntranceExam,ExamTags
from skilllab.models import SkillLabCourse,SkillLabCourseActivity,SkillLabCourseChapter
from crm.models import Lead
from psychometric_tests.models import PsychometricFAQ

class TranslationModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(TranslationModelForm, self).__init__(*args, **kwargs)
        
        # Get translation options for this model
        model = self._meta.model
        registered = False
        try:
            translation_options = translator.get_options_for_model(model)
            registered = True
        except:
            translation_options = None
        
        # Get list of translatable fields from modeltranslation
        translatable_fields = set()
        if registered and translation_options:
            translatable_fields = set(translation_options.fields)
        
        # Process all model fields
        for f in self._meta.model._meta.fields:
            field_id = "editor{}".format(f.name)
            field_name = f.name
            
            # Skip if field is not in form fields
            if field_name not in self.fields:
                continue
            
            # Check if this is a RichTextField (original, not translated)
            is_richtext = isinstance(f, RichTextField)
            
            # Check if this is a translation field by checking if base field name is translatable
            is_translation_field = False
            base_field_name = None
            lang_code = None
            
            if registered:
                # Check if field name ends with a language code (e.g., description_en)
                for lang, lang_name in settings.LANGUAGES:
                    if field_name.endswith('_' + lang):
                        base_field_name = field_name[:-len('_' + lang)]
                        lang_code = lang
                        if base_field_name in translatable_fields:
                            is_translation_field = True
                            break
                
                # Also check if this field name itself is a translatable field (for default language)
                # When default language field is used, it might just be the base name
                if not is_translation_field and field_name in translatable_fields:
                    # Check if original field is RichTextField
                    try:
                        original_field = model._meta.get_field(field_name)
                        # This might be the default language field if it's a TextField but translatable
                        # In modeltranslation, translatable fields become TextField
                        if isinstance(original_field, models.TextField) or isinstance(original_field, RichTextField):
                            is_translation_field = True
                            base_field_name = field_name
                            lang_code = settings.LANGUAGE_CODE if hasattr(settings, 'LANGUAGE_CODE') else 'en'
                    except models.FieldDoesNotExist:
                        pass
            
            # Handle RichTextField (original field) - apply CKEditor widget
            if is_richtext:
                if not is_translation_field:
                    # Original non-translatable RichTextField
                    self.fields[field_name] = forms.CharField(
                        widget=forms.Textarea(attrs={"id": field_id, "class": 'ckeditor'}),
                        required=self.fields[field_name].required
                    )
                else:
                    # This is a translatable RichTextField (original field used for default language)
                    field_label_suffix = f" [{lang_code.upper()}]" if lang_code else ""
                    self.fields[field_name] = forms.CharField(
                        widget=forms.Textarea(attrs={"id": field_id, "class": 'ckeditor'}),
                        required=self.fields[field_name].required,
                        label=self.fields[field_name].label or (base_field_name.replace('_', ' ').title() + field_label_suffix)
                    )
            
            # Handle RichTextField translation fields (e.g., description_en)
            # When modeltranslation marks a field as translatable, RichTextField becomes TextField with language suffixes
            elif is_translation_field and base_field_name:
                # If base_field_name is in translatable_fields and the current field is a TextField,
                # it might have been originally a RichTextField (modeltranslation converts RichTextField to TextField)
                # Check if base_field_name corresponds to a field that should be RichTextField
                # We'll check the actual model definition from the app
                try:
                    # Try to get original field definition
                    original_field = model._meta.get_field(base_field_name)
                    if isinstance(original_field, RichTextField):
                        # Original is still RichTextField (not replaced by modeltranslation yet or default language)
                        field_label_suffix = f" [{lang_code.upper()}]" if lang_code else ""
                        self.fields[field_name] = forms.CharField(
                            widget=forms.Textarea(attrs={"id": field_id, "class": "ckeditor"}),
                            required=False,
                            label=self.fields[field_name].label or (base_field_name.replace('_', ' ').title() + field_label_suffix)
                        )
                    elif isinstance(f, models.TextField):
                        # This is a TextField translation - check if base_field_name was originally RichTextField
                        # For Career model, we know description, role_description, eligibility, pros_cons are RichTextField
                        # So if base_field_name matches these, apply CKEditor
                        richtext_field_names = ['description', 'role_description', 'eligibility', 'pros_cons', 'content', 'answer', 'value']
                        if base_field_name in richtext_field_names:
                            # This is likely a translatable RichTextField that became TextField
                            field_label_suffix = f" [{lang_code.upper()}]" if lang_code else ""
                            self.fields[field_name] = forms.CharField(
                                widget=forms.Textarea(attrs={"id": field_id, "class": "ckeditor"}),
                                required=False,
                                label=self.fields[field_name].label or (base_field_name.replace('_', ' ').title() + field_label_suffix)
                            )
                        else:
                            # Regular TextField translation
                            self.fields[field_name] = forms.CharField(
                                widget=forms.Textarea(attrs={"rows": 5, "cols": 20}),
                                required=False
                            )
                except models.FieldDoesNotExist:
                    # Original field doesn't exist (replaced by modeltranslation)
                    # If base_field_name is in translatable_fields and matches known RichTextField names, treat as RichTextField
                    richtext_field_names = ['description', 'role_description', 'eligibility', 'pros_cons', 'content', 'answer', 'value']
                    if base_field_name in richtext_field_names and base_field_name in translatable_fields:
                        field_label_suffix = f" [{lang_code.upper()}]" if lang_code else ""
                        self.fields[field_name] = forms.CharField(
                            widget=forms.Textarea(attrs={"id": field_id, "class": "ckeditor"}),
                            required=False,
                            label=self.fields[field_name].label or (base_field_name.replace('_', ' ').title() + field_label_suffix)
                        )
                    elif isinstance(f, models.TextField):
                        # Regular TextField translation
                        self.fields[field_name] = forms.CharField(
                            widget=forms.Textarea(attrs={"rows": 5, "cols": 20}),
                            required=False
                        )

        for field_name, field in self.fields.items():
            if field.widget.attrs.get('class'):
                field.widget.attrs['class'] += ' form-control mb-2'
            else:
                field.widget.attrs['class']='form-control mb-2'

            if isinstance(field, forms.ModelChoiceField):
                if field.widget.attrs.get('class'):
                    field.widget.attrs['class'] += ' js-example-basic-single'
                else:
                    field.widget.attrs['class']='js-example-basic-single'

            if isinstance(field,forms.DateField):
                self.fields[field_name]   =forms.DateField(widget=forms.DateInput(attrs={'type':'date','class':' form-control mb-2'}))   

            if isinstance(field,forms.DateTimeField):
                self.fields[field_name]   =forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type':"datetime-local",'class':' form-control mb-2'}))  
                 
    def clean(self):
        model = self._meta.model
        
        # Get translation options to check translatable fields
        registered = False
        translatable_fields = set()
        try:
            translation_options = translator.get_options_for_model(model)
            registered = True
            translatable_fields = set(translation_options.fields)
        except:
            pass
        
        # Clean RichTextField fields (both original and translation fields)
        for f in self._meta.model._meta.fields:
            field_name = f.name
            
            # Check if this is a RichTextField (original)
            is_richtext_original = isinstance(f, RichTextField)
            
            # Check if this is a translation RichTextField field
            is_translation_rich = False
            if registered:
                for lang_code, lang_name in settings.LANGUAGES:
                    if field_name.endswith('_' + lang_code):
                        base_field_name = field_name[:-len('_' + lang_code)]
                        if base_field_name in translatable_fields:
                            try:
                                original_field = model._meta.get_field(base_field_name)
                                if isinstance(original_field, RichTextField):
                                    is_translation_rich = True
                                    break
                            except models.FieldDoesNotExist:
                                pass
            
            # Clean RichTextField data (remove style attributes)
            if (is_richtext_original or is_translation_rich) and field_name in self.fields.keys() and field_name in self.cleaned_data:
                try:
                    data = self.cleaned_data[field_name]
                    if data:
                        soup = BeautifulSoup(data, 'html.parser')
                        for p in soup.find_all():
                            if 'style' in p.attrs:
                                del p.attrs['style']
                        self.cleaned_data[field_name] = str(soup)
                except Exception as e:
                    print(f"Error cleaning field {field_name}: {e}")
        
        # Call base clean and return cleaned_data so child forms can use it
        cleaned = super(TranslationModelForm, self).clean()
        return cleaned

    def get_foreign_key_add_url(self,field):
        #TODO, check if field is a foreign key
        model = self._meta.model._meta.get_field(field.name).related_model
        if model and model.__name__ != "User":
            x= reverse('topteenadminmanaged:{}create'.format(model.__name__.lower()))
            return "{}?foreign_key=id_{}&_popup=1".format(x,field.name)
        return None

class CareerModelForm(TranslationModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # HIDE DUPLICATE TRANSLATION FIELDS - Keep only base fields for English-only mode
        # These fields are duplicates created by modeltranslation (_en suffix)
        # Frontend uses base fields (description, name, etc.) so hiding these won't affect output
        translation_fields_to_hide = [
            'name_en',
            'summary_en', 
            'description_en',
            'role_description_en',
            'eligibility_en',
            'pros_cons_en'
        ]
        
        for field_name in translation_fields_to_hide:
            if field_name in self.fields:
                del self.fields[field_name]
        
        # Align required flags with Django Admin behavior
        for fname in ['role_description', 'eligibility', 'pros_cons', 'career_paths', 'videos']:
            if fname in self.fields:
                self.fields[fname].required = False
        
        # Update labels for base fields (clean labels without [en] suffix)
        if 'description' in self.fields:
            self.fields['description'].label = 'Description'
        if 'role_description' in self.fields:
            self.fields['role_description'].label = 'Role description'
        if 'eligibility' in self.fields:
            self.fields['eligibility'].label = 'Eligibility'
        if 'name' in self.fields:
            self.fields['name'].label = 'Name'
        if 'summary' in self.fields:
            self.fields['summary'].label = 'Summary'
        if 'pros_cons' in self.fields:
            self.fields['pros_cons'].label = 'Pros & Cons'
        if 'career_paths' in self.fields:
            self.fields['career_paths'].label = 'Career paths'

    def clean(self):
        cleaned = super().clean()
        publish_status = cleaned.get('publish_status')
        image = cleaned.get('image')
        try:
            from core import choices as core_choices
            published_value = core_choices.PublishStatus.PUBLISHED
        except Exception:
            published_value = 1
        if publish_status == published_value:
            if not image or not getattr(image, 'name', None):
                self.add_error('image', 'Image is required to publish a career.')
        return cleaned
    class Meta:
        model = Career
        # Show all model fields to mirror Django Admin create/edit
        fields = '__all__'
        exclude = ['description_json']
        

class CareerClusterModelForm(TranslationModelForm):
    class Meta:
        model = CareerCluster
        fields = ['name','parent','image']

class SkillModelForm(TranslationModelForm):
    class Meta:
        model = Skill
        fields = ['name','priority']


class SkillLabCourseModelForm(TranslationModelForm):
    class Meta:
        model = SkillLabCourse
        fields = ['name','image','category','video_url','description','amount','currency']


class SkillLabCourseChapterModelForm(TranslationModelForm):
    class Meta:
        model = SkillLabCourseChapter
        fields = ['skilllab','chapter_name','content']


class SkillLabCourseActivityModelForm(TranslationModelForm):
    class Meta:
        model = SkillLabCourseActivity
        fields = ['skilllab_chapter','name','type','content','downloadable_file']

class CareerTagsForm(TranslationModelForm):
    class Meta:
        model = CareerTags
        fields = ['name','description','priority','icon','status']

class VideoCategoryForm(TranslationModelForm):
    class Meta:
        model = VideoCategory
        fields = ['name']

class VideosForm(TranslationModelForm):
    class Meta:
        model = Videos
        fields = ['name','link','upload_video','description','category']
        

class ProspectiveEmploymentAreaModelForm(TranslationModelForm):
    class Meta:
        model = ProspectiveEmploymentArea
        fields = ['name']


class ProspectiveRecruiterModelForm(TranslationModelForm):
    class Meta:
        model = ProspectiveRecruiter
        fields = ['name']

class CareerPathModelForm(TranslationModelForm):
    class Meta:
        model = CareerPath
        fields = ['name','career_path_steps']

class CareerPathStepModelForm(TranslationModelForm):
    class Meta:
        model = CareerPathStep
        fields = ['name','priority']

class CareerFAQModelForm(TranslationModelForm):
    class Meta:
        model = CareerFAQ
        fields = ['career','question','answer']

class CareerMediaModelForm(TranslationModelForm):
    class Meta:
        model = CareerMedia
        fields = ['career','media','type','priority']

class CareerMediaInlineFormsetModelForm(TranslationModelForm):
    class Meta:
        model = CareerMedia
        fields = ['media','type','priority']

class CollegeModelForm(TranslationModelForm):
    class Meta:
        model = College
        fields = ['name','created_by','banner','updated_by','country','logo','publish_status','state','city']

class CollegeImagesModelForm(TranslationModelForm):
    class Meta:
        model = CollegeImages
        fields = ['college','college_image','image_alt_text']

class CollegeFlatTextModelForm(TranslationModelForm):
    class Meta:
        model = CollegeFlatText
        fields = ['college','type','value']

class CollegeTextModelForm(TranslationModelForm):
    class Meta:
        model = CollegeText
        fields = ['college','type','value']

class CollegeFactsModelForm(TranslationModelForm):
    class Meta:
        model = CollegeFacts
        fields = ['college','type','value']

class RecruitingCompaniesModelForm(TranslationModelForm):
    class Meta:
        model = RecruitingCompanies
        fields = ['name','logo']

class CollegeRecruitingCompaniesModelForm(TranslationModelForm):
    class Meta:
        model = CollegeRecruitingCompanies
        fields = ['college','company']

class FacilityModelForm(TranslationModelForm):
    class Meta:
        model = Facility
        fields = ['name','logo']

class CollegeFacilityModelForm(TranslationModelForm):
    class Meta:
        model = CollegeFacility
        fields = ['college','facility']

class CollegeMoneyValueModelForm(TranslationModelForm):
    class Meta:
        model = CollegeMoneyValue
        fields = ['college','type','currency','amount']


class CountryModelForm(TranslationModelForm):
    class Meta:
        model = Country
        fields = ['name','short_name','phone_code','priority','flag']

class StateModelForm(TranslationModelForm):
    class Meta:
        model = State
        fields = ['name','country']

class CityModelForm(TranslationModelForm):
    class Meta:
        model = City
        fields = ['name','state']
        
class ProfessionModelForm(TranslationModelForm):
    class Meta:
        model=Profession
        fields=['name','career','image','summary','currency','salary','salary_type']

class StreamModelForm(TranslationModelForm):
    class Meta:
        model = Stream
        fields = ['name']

class CourseModelForm(TranslationModelForm):
    class Meta:
        model = Course
        fields = ['name','college','logo','stream','overview','duration_months','program_level','course_type']

class CourseFactsModelForm(TranslationModelForm):
    class Meta:
        model = CourseFacts
        fields = ['course','type','value']

class CourseTextModelForm(TranslationModelForm):
    class Meta:
        model = CourseText
        fields = ['course','type','value']

class CourseMoneyValueModelForm(TranslationModelForm):
    class Meta:
        model = CourseMoneyValue
        fields = ['course','type','currency','amount']

class CourseIntakeModelForm(TranslationModelForm):
    class Meta:
        model = CourseIntake
        fields = ['course','intake_date','intake_start_date','intake_end_date']

class CourseEnglighRequirementsModelForm(TranslationModelForm):
    class Meta:
        model = CourseEnglighRequirements
        fields = ['course','test','test_score_type','test_score']

class EntranceExamModelForm(TranslationModelForm):
    class Meta:
        model = EntranceExam
        fields = ['name','about','exam_pattern','eligibility','more_info','category','stream','logo','examtags','exam_date']

class ExamTagsModelForm(TranslationModelForm):
    class Meta:
        model = ExamTags
        fields = ['name']


class BlogModelForm(TranslationModelForm):
    class Meta:
        model = Blog
        fields = ['title','author','image','summary','content','category','tags','publish_status']

class TagModelForm(TranslationModelForm):
    class Meta:
        model = BlogTag
        fields = ['name',]

class BlogCategoryModelForm(TranslationModelForm):
    class Meta:
        model = BlogCategory
        fields = ['name',]


class ReviewModelForm(TranslationModelForm):
    class Meta:
        model = Review
        fields = ['name','image','description','profession']

class CommonFAQModelForm(TranslationModelForm):
    class Meta:
        model = CommonFAQ
        fields = ['question','answer','priority','user_type', 'is_featured']

class HobbiesModelForm(TranslationModelForm):
    class Meta:
        model = Hobbies
        fields = ['name','image']

class SubjectModelForm(TranslationModelForm):
    class Meta:
        model = Subject
        fields = ['name','image']

class UserFigureOutModelForm(TranslationModelForm):
    class Meta:
        model = UserFigureOut
        fields = ['name','image','description']

class StoriesModelForm(TranslationModelForm):
    class Meta:
        model = Stories
        fields = ['obj_id','obj_type','file_type','file','title','summary','start_date','end_date']
        
class ApilogModelForm(TranslationModelForm):
    class Meta:
        model = APILog
        fields = ['api_name','url','request','response','status_code']
        
        
class LeadModelForm(TranslationModelForm):
    class Meta:
        model = Lead
        fields = ['user','action','status']
        
class PsychometricFaqModelForm(TranslationModelForm):
    class Meta:
        model = PsychometricFAQ
        fields = ['question','answer','priority']
        