from modeltranslation.translator import translator, TranslationOptions
from .models import College,CollegeFlatText,CollegeText,CollegeFacts,Facility


class CollegeTranslationOptions(TranslationOptions):
    fields = ('name',)
    
class CollegeTextTranslationOptions(TranslationOptions):
    fields=('value',)

class CollegeFlatTextTranslationOption(TranslationOptions):
    fields=('value',)
    
class CollegeFactsTranslationOption(TranslationOptions):
    fields=('value',)
    
class FacilityTranslationOption(TranslationOptions):
    fields = ('name',)    
    
translator.register(College,CollegeTranslationOptions)
translator.register(CollegeFlatText,CollegeFlatTextTranslationOption)
translator.register(CollegeText,CollegeTextTranslationOptions)
translator.register(CollegeFacts,CollegeFactsTranslationOption)
translator.register(Facility,FacilityTranslationOption)