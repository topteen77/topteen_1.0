from colleges.models import Stream
from courses.models import Course, CourseEnglighRequirements, CourseFacts, CourseIntake, CourseMoneyValue, CourseText
from django_elasticsearch_dsl import Document ,fields
from django_elasticsearch_dsl.registries import registry

@registry.register_document
class CourseDocument(Document):
    
    slug=fields.KeywordField()
    overview=fields.TextField()
    duration_months=fields.KeywordField()
    program_level=fields.KeywordField(attr="get_program_level_display")
    course_type=fields.TextField(attr="get_course_type_display")

    college = fields.ObjectField(properties={
        'name':fields.TextField(),
        'slug': fields.KeywordField(),
    })

    stream = fields.ObjectField(properties={
        'name':fields.TextField(),
        'slug': fields.KeywordField(),
    })

    facts = fields.NestedField(properties={
        'type':fields.TextField(attr="get_type_display"),
        'value':fields.IntegerField()
    })

    texts = fields.NestedField(properties={
        'type':fields.TextField(attr="get_type_display"),
        'value':fields.TextField()
    })

    money_values = fields.NestedField(properties={

        'amount':fields.IntegerField(),
        'currency':fields.TextField(attr="get_currency_display"),
        'type':fields.TextField(attr="get_type_display")
    })

    english_requirements=fields.NestedField(properties={
        'test':fields.TextField(attr="get_test_display"), 
        'test_score_type':fields.TextField(attr="get_test_score_type_display"),
        'test_score':fields.KeywordField() 
    })

    intakes=fields.NestedField(properties={
        'intake_date':fields.DateField(), 
        'intake_start_date':fields.DateField(),
        'intake_end_date':fields.DateField()
    })

    class Index:

        name = 'courses'
        settings = {'number_of_shards': 1,
                    'number_of_replicas': 0}
    
            
    class Django:

        model = Course

        fields = [
            'name','logo'
        ]
        
        related_models =[Stream,CourseFacts,CourseText,CourseMoneyValue,CourseIntake,CourseEnglighRequirements]

    def get_instances_from_related(self, related_instance):
        """If related_models is set, define how to retrieve the Car instance(s) from the related model.
        The related_models option should be used with caution because it can lead in the index
        to the updating of a lot of items.
        """
        if isinstance(related_instance, CourseFacts):
            return related_instance.course
        elif isinstance(related_instance, CourseText):
            return related_instance.course
        elif isinstance(related_instance, CourseMoneyValue):
            return related_instance.course
        elif isinstance(related_instance, CourseIntake):
            return related_instance.course
        elif isinstance(related_instance, CourseEnglighRequirements):
            return related_instance.course