from modeltranslation.translator import translator, TranslationOptions
from .models import EntranceExam


class EntrancExamTranslationOptions(TranslationOptions):
    fields = ('name',)

translator.register(EntranceExam,EntrancExamTranslationOptions)