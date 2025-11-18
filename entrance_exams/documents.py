from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from entrance_exams.models import EntranceExam ,ExamTags
from courses.models import Stream
from elasticsearch_dsl import analyzer ,tokenizer

autocomplete_analyzer = analyzer('autocomplete_analyzer',
            tokenizer=tokenizer('trigram', 'ngram', min_gram=1, max_gram=2),
            filter=['lowercase']
        )


@registry.register_document
class EntranceExamDocument(Document):
    name = fields.TextField(analyzer=autocomplete_analyzer)
    category=fields.KeywordField(attr="get_category_display")
    logo_url=fields.TextField(attr="logo_url")
    slug=fields.KeywordField()
    about = fields.TextField()

    stream = fields.ObjectField(properties={
        'name':fields.TextField(),
        'slug': fields.KeywordField(),
    })
    examtags = fields.ObjectField(properties={
        'name':fields.TextField(),
        'slug': fields.KeywordField(),
    })
    url=fields.TextField(attr="url")
    
    class Index:
        name = 'entrance_exam'
        settings = {'number_of_shards': 1,
                    'number_of_replicas': 0}

    class Django:

        model = EntranceExam

        fields = [
            'id'
        ]

        related_models =[Stream,ExamTags]

    def get_instances_from_related(self, related_instance):
        """If related_models is set, define how to retrieve the Car instance(s) from the related model.
        The related_models option should be used with caution because it can lead in the index
        to the updating of a lot of items. 
        """
        if isinstance(related_instance,Stream):
            return related_instance.entranceexam_set.all()
        