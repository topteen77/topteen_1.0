from careers.models import Career, CareerCluster, CareerMedia, CareerPath, CareerTags, Profession, ProspectiveEmploymentArea, ProspectiveRecruiter, Skill
from courses.models import Course
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from elasticsearch_dsl import analyzer ,tokenizer

autocomplete_analyzer = analyzer('autocomplete_analyzer',
            tokenizer=tokenizer('trigram', 'ngram', min_gram=1, max_gram=2),
            filter=['lowercase']
        )

@registry.register_document
class CareerDocument(Document):
    slug=fields.KeywordField()
    summary=fields.TextField()
    description=fields.TextField()
    role_description=fields.TextField()
    eligibility=fields.TextField()
    pros_cons=fields.TextField()
    publish_status =fields.TextField(attr="get_publish_status_display")
    seo_title=fields.TextField()
    seo_description=fields.TextField()

    skills = fields.ObjectField(properties={
        'name':fields.KeywordField(),
        'slug': fields.KeywordField(),
        'priority':fields.IntegerField()
    })

    career_cluster = fields.ObjectField(properties={
        'name':fields.TextField(),
        'slug': fields.KeywordField(),
        'image':fields.FileField(),
    })

    prospective_employment_areas = fields.ObjectField(properties={
        'name':fields.TextField(),
        'slug': fields.KeywordField(),
    })

    prospective_recruiters = fields.ObjectField(properties={
        'name':fields.TextField(),
        'slug': fields.KeywordField(),
    })

    career_tags = fields.ObjectField(properties={
        'name':fields.KeywordField(),
        'slug': fields.KeywordField(),
        'priority':fields.IntegerField(),
        'icon':fields.FileField(),
        'status':fields.TextField(attr="get_status_display")
    })

    careermedia = fields.NestedField(properties={
        'type':fields.TextField(attr="get_type_display"),
        'media':fields.FileField(),
        'priority':fields.IntegerField()
    })

    career_paths = fields.NestedField(properties={
        'name':fields.TextField(),
        'slug': fields.KeywordField(),
        'career_path_steps':fields.ObjectField(properties={
        'name':fields.TextField(),
        'priority':fields.IntegerField(),
        'slug': fields.KeywordField(),
        },attr="get_sorted_priority"),
    })

    profession = fields.NestedField(properties={
        'slug': fields.KeywordField(),
        'name':fields.KeywordField(),
        'image':fields.FileField(),
        'summary':fields.TextField(),
        'salary':fields.IntegerField()
    })
    courses = fields.ObjectField(properties={
        'name':fields.KeywordField(),
        'slug': fields.KeywordField(),
        'overview':fields.TextField(),
        'logo':fields.FileField(),
        'stream':fields.ObjectField(properties={
        'name':fields.TextField(),
        'slug': fields.KeywordField()
        }),
    })
    get_rating_percent=fields.IntegerField(attr="get_rating_percent(num)")
    get_average_rating=fields.TextField(attr="get_average_rating")
    get_max_salary=fields.TextField(attr="get_max_salary")
    url=fields.TextField(attr="url")
    name = fields.TextField(analyzer=autocomplete_analyzer)
    class Index:

        name = 'careers'
        settings = {'number_of_shards': 1,
                    'number_of_replicas': 0}
    
            
    class Django:

        model = Career

        fields = [
            'id','image','created'
        ]
        
        related_models =[Skill,ProspectiveEmploymentArea,ProspectiveRecruiter,CareerTags,CareerMedia,CareerPath,Profession,Course,CareerCluster]

    def get_instances_from_related(self, related_instance):
        """If related_models is set, define how to retrieve the Car instance(s) from the related model.
        The related_models option should be used with caution because it can lead in the index
        to the updating of a lot of items. 
        """
        if isinstance(related_instance,Skill):
            return related_instance.career_set.all()
        elif isinstance(related_instance,ProspectiveEmploymentArea):
            return related_instance.career_set.all()
        elif isinstance(related_instance,ProspectiveRecruiter):
            return related_instance.career_set.all()
        elif isinstance(related_instance,CareerTags):
            return related_instance.career_set.all()
        elif isinstance(related_instance,Course):
            return related_instance.career_set.all()
        elif isinstance(related_instance,CareerCluster):
            return related_instance.career_clusters.all()
        elif isinstance(related_instance, CareerMedia):
            return related_instance.career
        elif isinstance(related_instance, CareerPath):
            return related_instance.career_set.all()
        elif isinstance(related_instance, Profession):
            return related_instance.career
        