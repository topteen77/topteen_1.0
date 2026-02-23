from calendar import calendar
from datetime import date
from elasticsearch_dsl import FacetedSearch,FacetedResponse,TermsFacet,DateHistogramFacet,Search,NestedFacet,RangeFacet,HistogramFacet

class CareerFilterFacets(FacetedSearch):
    index ='careers'

    doc_types = ['Career', ]
    # fields that should be searched
    fields = ['name,slug']
    # Limit facet sizes for performance (was 9999; 150 is enough for filter dropdowns)
    facets = {
        'skill': TermsFacet(field="skills.name", size=150),
        'profession': NestedFacet('profession', TermsFacet(field="profession.name", size=150)),
        'career_tags': TermsFacet(field="career_tags.slug", size=150),
    }


