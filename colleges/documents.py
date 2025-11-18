from core.models import City, Country,State
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from entrance_exams.models import EntranceExam
from .models import CollegeCategory, College, CollegeFacility, CollegeFacts, CollegeFlatText, CollegeImages, CollegeMoneyValue, CollegeText, Stream

@registry.register_document
class CollegeDocument(Document):

    country = fields.ObjectField(properties={
        'name':fields.KeywordField(),
        'slug': fields.KeywordField(),
        'short_name':fields.TextField(),
        'phone_code':fields.TextField(),
        'priority':fields.IntegerField(),
        'flag':fields.FileField(),
    })        

    state = fields.ObjectField(properties={
        'name':fields.KeywordField(),
        'slug': fields.KeywordField(),
    })

    city = fields.ObjectField(properties={
        'name':fields.KeywordField(),
        'slug': fields.KeywordField(),
    })

    stream = fields.ObjectField(properties={
        'name':fields.TextField(),
        'slug': fields.KeywordField(),
    })

    category = fields.ObjectField(properties={
        'name':fields.TextField(),
        'slug': fields.KeywordField(),
    })
    
    college_images = fields.NestedField(properties={
        'college_image': fields.FileField(),
        'image_alt_text': fields.TextField(),
    })

    facts = fields.NestedField(properties={
        'type':fields.TextField(attr="get_type_display"),
        'value':fields.KeywordField(),
    })

    flat_texts = fields.NestedField(properties={
        'type':fields.TextField(attr="get_type_display"),
        'value':fields.TextField()
    })

    texts = fields.NestedField(properties={
        'type':fields.TextField(attr="get_type_display"),
        'value':fields.TextField()
    })
    texts_about = fields.NestedField(properties={
        'type':fields.TextField(attr="get_type_display"),
        'value':fields.TextField()
    },attr="prepare_texts_about")

    facilities = fields.NestedField(properties={
         'facility':fields.ObjectField(properties={
         'name':fields.TextField(),
         'logo':fields.FileField()
        }),
    })

    recruiting_companies= fields.NestedField(properties={
         'company':fields.ObjectField(properties={
         'name':fields.TextField(),
         'logo':fields.FileField()
        }),
    })

    money_values = fields.NestedField(properties={
         'amount':fields.IntegerField(),
         'currency':fields.TextField(attr="get_currency_display"),
         'type':fields.TextField(attr="get_type_display"),
    })

    entrance_exams = fields.NestedField(properties={
         'exam':fields.ObjectField(properties={
         'name':fields.TextField(),
        }),
    })
    
    college_type=fields.TextField(attr="get_college_type_display")

    university_type=fields.TextField(attr="get_university_type_display")

    url=fields.TextField(attr="url")
    
    slug=fields.KeywordField()

    class Index:

        name = 'colleges'
        settings = {'number_of_shards': 1,
                    'number_of_replicas': 0}
    
            
    class Django:

        model = College

        fields = [
            'id','name','logo','created','banner'
        ]
        
        related_models = [Country,State,City,CollegeImages,Stream,CollegeCategory,CollegeMoneyValue,CollegeFacts,
                          CollegeFlatText,CollegeText,CollegeFacility]

    def get_instances_from_related(self, related_instance):
        """If related_models is set, define how to retrieve the Car instance(s) from the related model.
        The related_models option should be used with caution because it can lead in the index
        to the updating of a lot of items.
        """
        if isinstance(related_instance,Country):
            return related_instance.college_set.all()
        elif isinstance(related_instance,State):
            return related_instance.college_set.all()
        elif isinstance(related_instance,City):
            return related_instance.college_set.all()
        elif isinstance(related_instance,Stream):
            return related_instance.college_set.all()
        elif isinstance(related_instance,CollegeCategory):
            return related_instance.college_set.all()
        elif isinstance(related_instance, CollegeImages):
            return related_instance.college
        elif isinstance(related_instance, CollegeMoneyValue):
            return related_instance.college
        elif isinstance(related_instance, CollegeFlatText):
            return related_instance.college
        elif isinstance(related_instance, CollegeFacts):
            return related_instance.college
        elif isinstance(related_instance, CollegeText):
            return related_instance.college
        elif isinstance(related_instance, CollegeFacility):
            return related_instance.college


# @registry.register_document
# class Country(Document):

