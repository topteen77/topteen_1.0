from calendar import calendar
from datetime import date
from elasticsearch_dsl import FacetedSearch,FacetedResponse,TermsFacet,DateHistogramFacet,NestedFacet,RangeFacet,HistogramFacet

class CollegeFilterFacets(FacetedSearch):
    index ='colleges'
    
    doc_types = ['College', ]
    # fields that should be searched
    fields = ['slug','country','state','city','courses']

    facets = {
        # use bucket aggregations to define facets
        'country':TermsFacet(field="country.name"),
        'state':TermsFacet(field="state.name"),
        'city':TermsFacet(field="city.name"),

        
         }

    def search(self):
        # override methods to add custom pieces
        s = super().search()
        return s



