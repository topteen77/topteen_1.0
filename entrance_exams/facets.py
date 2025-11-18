from calendar import calendar
from datetime import date
from unicodedata import category
from elasticsearch_dsl import FacetedSearch,FacetedResponse,TermsFacet,DateHistogramFacet,NestedFacet,RangeFacet,HistogramFacet

class EntranceExamFilterFacets(FacetedSearch):
    index ='entrance_exam'
    
    doc_types = ['EntranceExam', ]
    # fields that should be searched
    fields = ['slug','name','category','examtags']

    facets = {
        #use bucket aggregations to define facets
        'slug':TermsFacet(field="slug"),
        'category':TermsFacet(field="category"),
        'examtags_slug':TermsFacet(field="examtags.slug"),
        'stream_slug':TermsFacet(field="stream.slug",size=100),
        }

    def search(self):
        # override methods to add custom pieces
        s = super().search()
        return s