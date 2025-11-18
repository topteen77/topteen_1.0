from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from skilllab.models import SkillLabCourse


@registry.register_document
class SkillLabCourseDocument(Document):
    slug=fields.KeywordField()
    description=fields.KeywordField()
    category=fields.TextField(attr="get_category_display")
    
    url=fields.TextField(attr="url")
    
    class Index:
        name = 'skilllabcourse'
        settings = {'number_of_shards': 1,
                    'number_of_replicas': 0}

    class Django:

        model = SkillLabCourse

        fields = [
            'id','name','image','video_url'
        ]

        related_models =[]

    def get_instances_from_related(self, related_instance):
        """If related_models is set, define how to retrieve the Car instance(s) from the related model.
        The related_models option should be used with caution because it can lead in the index
        to the updating of a lot of items. 
        """
        pass