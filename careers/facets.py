from calendar import calendar
from datetime import date
from elasticsearch_dsl import FacetedSearch,FacetedResponse,TermsFacet,DateHistogramFacet,Search,NestedFacet,RangeFacet,HistogramFacet

class CareerFilterFacets(FacetedSearch):
    index ='careers'

    doc_types = ['Career', ]
    # fields that should be searched
    fields = ['name,slug']
    facets = {
        # use bucket aggregations to define facets
        'skill':TermsFacet(field="skills.name",size=9999),
        # 'course':TermsFacet(field="courses.name",size=9999),
        'profession':NestedFacet('profession',TermsFacet(field="profession.name",size=9999)),
        'career_tags':TermsFacet(field="career_tags.slug",size=9999),
        }


