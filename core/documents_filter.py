from colleges.documents import CollegeDocument
from careers.documents import CareerDocument
from courses.documents import CourseDocument
from skilllab.documents import SkillLabCourseDocument
from careers.models import Videos
from entrance_exams.documents import EntranceExamDocument
from elasticsearch_dsl import Q ,Nested
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.db.models import Q as DjangoQ
from dataclasses import dataclass,field


class ItemSearch:
    
    career : list =field(default_factory=list)
    college : list =field(default_factory=list)
    courses : list =field(default_factory=list)
    entranceexam : list =field(default_factory=list)
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
        entranceexams = self.entranceexam
        if entranceexams:
            all_search['entranceexam']=entranceexams
        else:
            all_search['entranceexam']=[]
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
        self.searchexam=EntranceExamDocument.search()
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

        exam = self._search_entranceexam(value)
        searcheddata.entranceexam = exam

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
        except Exception:
            # Fallback to Django ORM if Elasticsearch fails
            try:
                from colleges.models import College
                colleges = list(College.objects.filter(name__icontains=search_term)[:10])
            except Exception:
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
        except Exception:
            # Fallback to Django ORM if Elasticsearch fails
            try:
                from careers.models import Career
                from core import choices
                career = list(Career.objects.filter(
                    name__icontains=search_term,
                    publish_status=choices.PublishStatus.PUBLISHED
                )[:10])
            except Exception:
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
    
    def _search_entranceexam(self,search):
        q = Q("match_phrase", name=search) 
        try:
            search=self.searchexam.query(q) 
            entranceexam = search.execute()[0:]
        except:
            entranceexam = None
        return entranceexam
    
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
        except Exception:
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
        except Exception:
            blogs = []
        return blogs