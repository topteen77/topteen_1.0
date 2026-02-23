from re import T
from requests import request
from colleges.document_filters import CollegeDocumentFilter
from colleges.views import is_ajax
from .documents import CareerDocument
from django.utils.functional import LazyObject
from django.core.paginator import Paginator
from .facets import CareerFilterFacets
from core.models import Country
from colleges.models import College
from elasticsearch_dsl import Q ,Nested

class CareerDocumentFilter:
    def __init__(self):
        self.search=CareerDocument.search()

    def get_elasticsearch_document_career_all(self,request,tagslug):
        if tagslug is not None :
            # tagfilter=self._career_filter(self.search,request)
            return self._career_filter(self.search.filter("match",career_tags__slug=tagslug),request)
        return self._career_filter(self.search,request,tagslug)

    def _career_filter(self,search,request,tagslug=None):
        # Support both GET and POST requests
        request_data = request.POST if request.method == 'POST' else request.GET
        
        if request_data.getlist('professions'):
            q = Q('nested',path='profession',ignore_unmapped= "true",query=Q('terms', profession__name=request_data.getlist('professions')))
            search = search.query(q)
        if request_data.getlist('cluster'):
            # Filter by cluster IDs
            cluster_ids = request_data.getlist('cluster')
            # Convert cluster IDs to slugs for filtering (since ES document uses slug)
            from .models import CareerCluster
            try:
                clusters = CareerCluster.objects.filter(id__in=cluster_ids)
                cluster_slugs = [c.slug for c in clusters if c.slug]
                if cluster_slugs:
                    search = search.filter("terms",career_cluster__slug=cluster_slugs)
            except:
                # Fallback: try filtering by ID if available
                pass
        if request_data.getlist('courses'):
            search = search.filter("terms",courses__name=request_data.getlist('courses'))
        return search
    def get_career_list_context(self,request,tagslug=None):
        # Support both GET and POST requests
        request_data = request.POST if request.method == 'POST' else request.GET
        
        ctx={}
        search_results=SearchResults(self.get_elasticsearch_document_career_all(request,tagslug))
        paginator = Paginator(search_results, 15)
        page_number = request_data.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Enrich Elasticsearch results with Django model data for images and clusters
        from .models import Career, CareerCluster
        from django.db.models import Q as DjangoQ
        enriched_careers = []
        page_obj_list = list(page_obj)
        
        # Collect all doc ids and slugs for batch fetch (avoid N+1)
        doc_ids = set()
        doc_slugs = set()
        doc_meta = []  # (career_doc, doc_id, doc_slug)
        for career_doc in page_obj_list:
            doc_id = None
            doc_slug = None
            try:
                if hasattr(career_doc, 'id'):
                    doc_id = getattr(career_doc, 'id', None)
                if not doc_id and hasattr(career_doc, 'meta'):
                    try:
                        doc_id = getattr(career_doc.meta, 'id', None)
                    except Exception:
                        pass
                if not doc_id and hasattr(career_doc, '_id'):
                    doc_id = getattr(career_doc, '_id', None)
                if hasattr(career_doc, 'slug'):
                    doc_slug = getattr(career_doc, 'slug', None)
            except Exception:
                pass
            doc_meta.append((career_doc, doc_id, doc_slug))
            if doc_id is not None:
                try:
                    doc_ids.add(int(doc_id) if isinstance(doc_id, str) and doc_id.isdigit() else doc_id)
                except (ValueError, TypeError):
                    pass
            if doc_slug:
                doc_slugs.add(doc_slug)
        
        # Single batch query for all careers on this page with prefetched career_cluster
        career_by_id = {}
        career_by_slug = {}
        if doc_ids or doc_slugs:
            careers_qs = Career.objects.filter(
                DjangoQ(id__in=doc_ids) | DjangoQ(slug__in=doc_slugs)
            ).prefetch_related('career_cluster')
            for c in careers_qs:
                career_by_id[c.id] = c
                career_by_slug[c.slug] = c
        
        for career_doc, doc_id, doc_slug in doc_meta:
            try:
                career_id_int = None
                if doc_id is not None:
                    try:
                        career_id_int = int(doc_id) if isinstance(doc_id, str) and doc_id.isdigit() else doc_id
                    except (ValueError, TypeError):
                        pass
                career_obj = None
                if career_id_int is not None:
                    career_obj = career_by_id.get(career_id_int)
                if not career_obj and doc_slug:
                    career_obj = career_by_slug.get(doc_slug)
                
                if career_obj:
                    # Use Django model instance - ensure slug and id are correct
                    career_doc._django_instance = career_obj
                    # Always set slug and id from Django model (most reliable)
                    career_doc.slug = career_obj.slug
                    career_doc.id = career_obj.id
                    
                    # Get image URL from Django model
                    if hasattr(career_obj, 'get_image_url'):
                        career_doc._image_url = career_obj.get_image_url()
                    elif career_obj.image and career_obj.image.name:
                        career_doc._image_url = career_obj.image.url
                    else:
                        # No image in Django model, try ES document
                        if hasattr(career_doc, 'image') and career_doc.image:
                            career_doc._image_url = None  # Will use fallback in template
                        else:
                            career_doc._image_url = None
                    
                    # Cluster list already loaded via prefetch_related
                    try:
                        career_doc._career_cluster_list = list(career_obj.career_cluster.all())
                    except Exception:
                        career_doc._career_cluster_list = []
                else:
                    # No Django model found - use Elasticsearch document data
                    career_doc._django_instance = None
                    # Preserve original image from ES document for template fallback
                    career_doc._image_url = None  # Template will use career.image fallback
                    
                    # CRITICAL: Ensure slug and id are accessible from ES document
                    # Set them explicitly to ensure template can access them
                    # First, try to get id - it's essential for URL generation
                    final_id = None
                    if doc_id:
                        try:
                            final_id = int(doc_id) if isinstance(doc_id, str) and doc_id.isdigit() else doc_id
                        except (ValueError, TypeError):
                            final_id = doc_id
                    else:
                        # Last resort: try to get from meta or direct attribute access
                        try:
                            if hasattr(career_doc, 'meta'):
                                meta_id = getattr(career_doc.meta, 'id', None)
                                if meta_id:
                                    final_id = int(meta_id) if isinstance(meta_id, str) and meta_id.isdigit() else meta_id
                        except:
                            pass
                        # If still no id, try direct attribute
                        if not final_id:
                            try:
                                direct_id = getattr(career_doc, 'id', None)
                                if direct_id:
                                    final_id = int(direct_id) if isinstance(direct_id, str) and str(direct_id).isdigit() else direct_id
                            except:
                                pass
                    
                    # Always set id explicitly using setattr to ensure it's accessible
                    if final_id:
                        setattr(career_doc, 'id', final_id)
                    
                    # Now handle slug
                    final_slug = None
                    if doc_slug:
                        final_slug = doc_slug
                    else:
                        # Try to get slug from ES document directly
                        try:
                            direct_slug = getattr(career_doc, 'slug', None)
                            if direct_slug:
                                final_slug = direct_slug
                        except:
                            pass
                    
                    # If slug is still missing and we have an id, try to get from Django
                    if not final_slug and final_id:
                        try:
                            fallback_career = Career.objects.filter(id=final_id).only('slug').first()
                            if fallback_career and fallback_career.slug:
                                final_slug = fallback_career.slug
                        except:
                            pass
                    
                    # If we still don't have slug or id, try one more time to get Django model
                    # This ensures we always have valid slug/id for URL generation
                    if (not final_slug or not final_id) and (doc_id or doc_slug):
                        try:
                            if final_id:
                                final_career = Career.objects.filter(id=final_id).only('slug', 'id').first()
                            elif doc_slug:
                                final_career = Career.objects.filter(slug=doc_slug, publish_status=1).only('slug', 'id').first()
                            else:
                                final_career = None
                            
                            if final_career:
                                final_id = final_career.id
                                final_slug = final_career.slug
                        except:
                            pass
                    
                    # Always set slug and id explicitly using setattr to ensure they're accessible
                    if final_id:
                        setattr(career_doc, 'id', final_id)
                    if final_slug:
                        setattr(career_doc, 'slug', final_slug)
                    
                    # Extract cluster from ES document
                    if hasattr(career_doc, 'career_cluster') and career_doc.career_cluster:
                        cluster_name = getattr(career_doc.career_cluster, 'name', None) if hasattr(career_doc.career_cluster, 'name') else None
                        cluster_slug = getattr(career_doc.career_cluster, 'slug', None) if hasattr(career_doc.career_cluster, 'slug') else None
                        if cluster_slug:
                            try:
                                cluster_obj = CareerCluster.objects.filter(slug=cluster_slug).first()
                                if cluster_obj:
                                    career_doc._career_cluster_list = [cluster_obj]
                                else:
                                    career_doc._career_cluster_list = []
                            except:
                                career_doc._career_cluster_list = []
                        else:
                            career_doc._career_cluster_list = []
                    else:
                        career_doc._career_cluster_list = []
            except Exception as e:
                # If enrichment fails, continue with original document
                import traceback
                print(f"Error enriching career {getattr(career_doc, 'id', 'unknown')}: {e}")
                print(traceback.format_exc())
                career_doc._django_instance = None
                career_doc._image_url = None
                career_doc._career_cluster_list = []
            enriched_careers.append(career_doc)
        
        # Replace page_obj object_list with enriched careers
        # Create a new Page object with enriched careers
        from django.core.paginator import Page
        enriched_page = Page(enriched_careers, page_obj.number, page_obj.paginator)
        ctx['careers']=enriched_page
        ctx['facets_filter']=self.get_facets_filter(request,tagslug)
        
        # Add clusters and professions to context for filters (single query with annotate)
        from .models import CareerCluster, Profession, Career
        from django.db.models import Count, Q as DjangoQ
        clusters_qs = CareerCluster.objects.filter(
            career_clusters__publish_status=1,
            object_status=1
        ).distinct().annotate(
            career_count=Count('career_clusters', filter=DjangoQ(career_clusters__publish_status=1), distinct=True)
        ).filter(career_count__gt=0).order_by('name')
        clusters_with_counts = [{'cluster': c, 'count': c.career_count} for c in clusters_qs]
        ctx['clusters'] = [item['cluster'] for item in clusters_with_counts]
        ctx['clusters_with_counts'] = clusters_with_counts
        
        ctx['professions'] = Profession.objects.filter(
            career__publish_status=1,
            object_status=1
        ).distinct().order_by('name')[:100]
        
        # Add selected filters
        ctx['selected_clusters'] = request_data.getlist("cluster")
        ctx['selected_professions'] = request_data.getlist("professions")
        
        # Get shortlisted career IDs for authenticated users
        shortlisted_career_ids = []
        if request.user.is_authenticated:
            from careers.models import CareerShortlist
            shortlisted_career_ids = list(CareerShortlist.objects.filter(
                user=request.user
            ).values_list('career_id', flat=True))
        ctx['shortlisted_career_ids'] = shortlisted_career_ids
        
        return ctx

    def get_facets_filter(self, request, tagslug=None):
        from django.core.cache import cache
        d = self.get_filter_dict(request, tagslug)
        cache_key = "careers_facets_filter_empty"
        if not d and not tagslug:
            facets_filter = cache.get(cache_key)
            if facets_filter is not None:
                return facets_filter
        facets_filter = {}
        bs = CareerFilterFacets(filters=d)
        result = bs.execute()
        facets_filter["skill"] = sorted(result.facets.skill, key=lambda obj: obj[0].capitalize())
        facets_filter["profession"] = sorted(result.facets.profession, key=lambda obj: obj[0].capitalize())
        if not d and not tagslug:
            cache.set(cache_key, facets_filter, 300)
        return facets_filter

    def get_filter_dict(self,request,tagslug=None):
        # Support both GET and POST requests
        request_data = request.POST if request.method == 'POST' else request.GET
        
        d={}
        if request_data.getlist('professions') and len(request_data.getlist('professions')) > 0:
            d['profession']=request_data.getlist('professions')
            
        if request_data.getlist('cluster') and len(request_data.getlist('cluster')) >0:
            d['cluster']=request_data.getlist('cluster')
            
        if request_data.getlist('courses') and len(request_data.getlist('courses')) >0:
            d['course']=request_data.getlist('courses')

        if tagslug:
            d['career_tags']=tagslug
        return d

    def get_career_detail(self,request,slug,is_ajax=False):
        career=self.search.query("match",slug=slug)
        clgdf=CollegeDocumentFilter()
        ctx={}
        country=Country.objects.all()
        ctx['colleges'] = College.get_all_colleges()
        ctx['countries']=country
        ctx['career'] = career.execute()[0]
        return ctx

class SearchResults(LazyObject):
    def __init__(self, search_object):
        self._wrapped = search_object

    def __len__(self):
        return self._wrapped.count()

    def __getitem__(self, index):
        search_results = self._wrapped[index]
        if isinstance(index, slice):
            search_results = list(search_results)
        return search_results