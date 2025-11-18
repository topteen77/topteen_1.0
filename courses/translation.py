from modeltranslation.translator import translator, TranslationOptions
from .models import Course,CourseText,CourseFacts,Stream


class CourseTranslationOptions(TranslationOptions):
    fields = ('name',)
    
class CourseTextTranslationOptions(TranslationOptions):
    fields=('value',)
   
class CourseFactTranslationOption(TranslationOptions):
    fields=('value',)
    
class StreamTranslationOption(TranslationOptions):
    fields = ('name',)    
    
translator.register(Course,CourseTranslationOptions)
translator.register(CourseText,CourseTextTranslationOptions)
translator.register(CourseFacts,CourseFactTranslationOption)
translator.register(Stream,StreamTranslationOption)