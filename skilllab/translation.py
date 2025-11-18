from modeltranslation.translator import translator, TranslationOptions
from .models import SkillLabCourse


class SkillLabTranslationOptions(TranslationOptions):
    fields = ('name',)

translator.register(SkillLabCourse,SkillLabTranslationOptions)