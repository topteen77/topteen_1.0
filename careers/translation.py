from modeltranslation.translator import translator, TranslationOptions
from .models import Skill,ProspectiveEmploymentArea,ProspectiveRecruiter,Career,CareerPath

class SkillTranslationOptions(TranslationOptions):
    fields = ('name',)
    
class ProspectiveEmploymentAreaTranslationOptions(TranslationOptions):
    fields=('name',)

class ProspectiveRecruiterTranslationOption(TranslationOptions):
    fields=('name',)
    
# Note: Career translation fields have been removed from the database
# Unregister Career to prevent modeltranslation from trying to access removed fields
# class CareerTranslationOption(TranslationOptions):
#     fields=('name','summary','description')
    
class CareerPathTranslationOption(TranslationOptions):
    fields = ('name',)    
    
translator.register(Skill,SkillTranslationOptions)
translator.register(ProspectiveEmploymentArea,ProspectiveEmploymentAreaTranslationOptions)
translator.register(ProspectiveRecruiter,ProspectiveRecruiterTranslationOption)
# translator.register(Career,CareerTranslationOption)  # Disabled - translation fields removed
translator.register(CareerPath,CareerPathTranslationOption)