from colleges.documents import CollegeDocument
from careers.documents import CareerDocument
from courses.documents import CourseDocument
from skilllab.documents import SkillLabCourseDocument
from careers.models import Videos
from elasticsearch_dsl import Q ,Nested
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.db.models import Q as DjangoQ
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class ItemSearch:
    
    career : list =field(default_factory=list)
    college : list =field(default_factory=list)
    courses : list =field(default_factory=list)
    entrance_test_prep_exams : list =field(default_factory=list)
    videos : list =field(default_factory=list)
    


    def _get_search(self):
        all_search = {}
        career_search = self.career
        if career_search:
            all_search['career']=career_search
        else:
            all_search['career']=[]
            
        colleges = self.college
        if colleges:
            all_search['college']=colleges
        else:
            all_search['college']=[]
            
        search_courses = self.courses
        if search_courses:
            all_search['course']=search_courses
        else:
            all_search['course']=[]
        etp_exams = getattr(self, 'entrance_test_prep_exams', None) or []
        if etp_exams:
            all_search['entrance_test_prep_exams'] = etp_exams
        else:
            all_search['entrance_test_prep_exams'] = []
        video=self.videos
        if video:
            all_search['videos']=video
        else:
            all_search['videos']=[]
        professions = self.professions
        if professions:
            all_search['professions']=professions
        else:
            all_search['professions']=[]
        blogs = self.blogs
        if blogs:
            all_search['blogs']=blogs
        else:
            all_search['blogs']=[]
        return all_search
    

class AllSearch:
    def __init__(self):
        self.searchcollege=CollegeDocument.search()
        self.searchcareer=CareerDocument.search()
        self.searchcourse=SkillLabCourseDocument.search()

    def get_ajax_search_Item_list(self,request,result=None):
        if result==None:
            value=request.GET.get('search')
        else:
            value=result
        
        searcheddata = ItemSearch()

        career_search = self._search_career(value)
        searcheddata.career = career_search  

        search_courses = self._search_course(value)
        searcheddata.courses = search_courses           

        entrance_test_prep_exams = self._search_entrance_test_prep_exams(value)
        searcheddata.entrance_test_prep_exams = entrance_test_prep_exams

        colleges = self._search_college(value)
        searcheddata.college = colleges

        videos = self._search_videos(value)
        searcheddata.videos = videos

        professions = self._search_professions(value)
        searcheddata.professions = professions

        blogs = self._search_blogs(value)
        searcheddata.blogs = blogs

        search_data = searcheddata._get_search()
        return search_data

    def _search_college(self,search_term):
        # Use match with fuzziness for partial matching - allows "Amity" to match "Amity University"
        q = Q("match", name={"query": search_term, "fuzziness": "AUTO"}) 
        colleges = None
        try:
            es_search=self.searchcollege.query(q) 
            colleges = es_search.execute()[0:]
        except Exception as e:
            logger.warning("Elasticsearch error in college search: %s", e)
            try:
                from colleges.models import College
                colleges = list(College.objects.filter(name__icontains=search_term)[:10])
            except Exception as e2:
                logger.warning("Django ORM fallback error in college search: %s", e2)
                colleges = None
        if colleges is None:
            colleges = []
        return colleges

    def _search_career(self,search_term):
        # Use match with fuzziness for partial matching
        q = Q("match", name={"query": search_term, "fuzziness": "AUTO"})
        career = None
        try:
            es_search=self.searchcareer.query(q) 
            career = es_search.execute()[0:]
        except Exception as e:
            logger.warning("Elasticsearch error in career search: %s", e)
            try:
                from careers.models import Career
                from core import choices
                career = list(Career.objects.filter(
                    name__icontains=search_term,
                    publish_status=choices.PublishStatus.PUBLISHED
                )[:10])
            except Exception as e2:
                logger.warning("Django ORM fallback error in career search: %s", e2)
                career = None
        if career is None:
            career = []
        return career

    def _search_course(self,search):
        q = Q("match_phrase", name=search) 
        try:
            search=self.searchcourse.query(q) 
            courses = search.execute()[0:]
        except:
            courses = None
        return courses

    def _search_entrance_test_prep_exams(self, search_term):
        """Search Entrance Test Prep exams (core.EntranceTestPrepExam) by name. Use raw SQL to avoid modeltranslation rewriting 'name' to 'name_en' (this model has no translated fields)."""
        try:
            from core.models import EntranceTestPrepExam
            from core import choices
            from django.db import connection
            # Raw SQL so modeltranslation cannot rewrite field names
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM core_entrancetestprepexam
                    WHERE name LIKE %s AND object_status = %s
                    ORDER BY name
                    LIMIT 15
                    """,
                    ["%" + search_term + "%", choices.ObjectStatus.ACTIVE],
                )
                pks = [row[0] for row in cursor.fetchall()]
            if not pks:
                return []
            # Load by pk only (no name in filter) then sort by search order
            pk_order = {pk: i for i, pk in enumerate(pks)}
            exams = list(EntranceTestPrepExam._base_manager.filter(pk__in=pks))
            exams.sort(key=lambda e: pk_order.get(e.pk, 999))
            return exams
        except Exception as e:
            logger.warning("Error searching entrance test prep exams: %s", e)
            return []
    
    def _search_videos(self,search):
        try:
            video=Videos.objects.filter(name__icontains=search)[:10]
        except:
            video=None
        return video
    
    def _search_professions(self,search):
        try:
            from careers.models import Profession
            professions = list(Profession.objects.filter(name__icontains=search)[:10])
        except Exception as e:
            logger.warning("Error searching professions: %s", e)
            professions = []
        return professions
    
    def _search_blogs(self,search):
        try:
            from blog.models import Blog
            from core import choices
            blogs = list(Blog.objects.filter(
                DjangoQ(title__icontains=search) | DjangoQ(summary__icontains=search),
                publish_status=choices.PublishStatus.PUBLISHED
            )[:10])
        except Exception as e:
            logger.warning("Error searching blogs: %s", e)
            blogs = []
        return blogs