from modeltranslation.translator import translator, TranslationOptions
from .models import Skill,ProspectiveEmploymentArea,ProspectiveRecruiter,Career,CareerPath

class SkillTranslationOptions(TranslationOptions):
    fields = ('name',)
    
class ProspectiveEmploymentAreaTranslationOptions(TranslationOptions):
    fields=('name',)

class ProspectiveRecruiterTranslationOption(TranslationOptions):
    fields=('name',)
    
class CareerTranslationOption(TranslationOptions):
    fields=('name','summary','description','role_description','eligibility','pros_cons')
    
class CareerPathTranslationOption(TranslationOptions):
    fields = ('name',)    
    
translator.register(Skill,SkillTranslationOptions)
translator.register(ProspectiveEmploymentArea,ProspectiveEmploymentAreaTranslationOptions)
translator.register(ProspectiveRecruiter,ProspectiveRecruiterTranslationOption)
translator.register(Career,CareerTranslationOption)
translator.register(CareerPath,CareerPathTranslationOption)