from django.urls import path,include
from topteenadmin import views

app_name="topteenadminmanaged"
urlpatterns = [
    
    #skilllab CRUD
    path('skilllab/skilllabcourse/list',views.SkillLabCourseListView.as_view(),name="skilllabcourselist"),
    path('skilllab/skilllabcourse/view/<pk>',views.SkillLabCourseDetailView.as_view(),name='skilllabcoursedetail'),
    path('skilllab/skilllabcourse/add',views.CreateSkillLabCourse.as_view(),name="skilllabcoursecreate"),
    path('skilllab/skilllabcourse/change/<pk>',views.SkillLabCourseUpdateView.as_view(),name="skilllabcourseedit"),
    path('skilllab/skilllabcourse/delete/<pk>',views.SkillLabCourseDeleteView.as_view(),name='skilllabcoursedelete'),
    
    
    #skilllabchapter CRUD
    path('skilllab/skilllabcoursechapter/list',views.SkillLabCourseChapterListView.as_view(),name="skilllabcoursechapterlist"),
    path('skilllab/skilllabcoursechapter/view/<pk>',views.SkillLabCourseChapterDetailView.as_view(),name='skilllabcoursechapterdetail'),
    path('skilllab/skilllabcoursechapter/add',views.CreateSkillLabCourseChapter.as_view(),name="skilllabcoursechaptercreate"),
    path('skilllab/skilllabcoursechapter/change/<pk>',views.SkillLabCourseChapterUpdateView.as_view(),name="skilllabcoursechapteredit"),
    path('skilllab/skilllabcoursechapter/delete/<pk>',views.SkillLabCourseChapterDeleteView.as_view(),name='skilllabcoursechapterdelete'),
    

    #skilllabactivity CRUD
    path('skilllab/skilllabcourseactivity/list',views.SkillLabCourseActivityListView.as_view(),name="skilllabcourseactivitylist"),
    path('skilllab/skilllabcourseactivity/view/<pk>',views.SkillLabCourseActivityDetailView.as_view(),name='skilllabcourseactivitydetail'),
    path('skilllab/skilllabcourseactivity/add',views.CreateSkillLabCourseActivity.as_view(),name="skilllabcourseactivitycreate"),
    path('skilllab/skilllabcourseactivity/change/<pk>',views.SkillLabCourseActivityUpdateView.as_view(),name="skilllabcourseactivityedit"),
    path('skilllab/skilllabcourseactivity/delete/<pk>',views.SkillLabCourseActivityDeleteView.as_view(),name='skilllabcourseactivitydelete'),
    
    #Careers APP
    #Career CRUD
    path('careers/career/list',views.CareerListView.as_view(),name="careerlist"),
    path('careers/career/view/<pk>',views.CareerDetailView.as_view(),name='careerdetail'),
    path('careers/career/add',views.CreateCareer.as_view(),name="careercreate"),
    path('careers/career/change/<pk>',views.CareerUpdateView.as_view(),name="careeredit"),
    path('careers/career/delete/<pk>',views.CareerDeleteView.as_view(),name='careerdelete'),
    
    #skill CRUD
    path('careers/skill/list',views.SkillListView.as_view(),name="skilllist"),
    path('careers/skill/view/<pk>',views.SkillDetailView.as_view(),name='skilldetail'),
    path('careers/skill/add',views.CreateSkill.as_view(),name="skillcreate"),
    path('careers/skill/change/<pk>',views.SkillUpdateView.as_view(),name="skilledit"),
    path('careers/skill/delete/<pk>',views.SkillDeleteView.as_view(),name='skilldelete'),
    
    
    #Prospectiveemploymentarea CRUD
    path('careers/prospectiveemploymentarea/list',views.ProspectiveEmploymentAreaListView.as_view(),name="prospectiveemploymentarealist"),
    path('careers/prospectiveemploymentarea/view/<pk>',views.ProspectiveEmploymentAreaDetailView.as_view(),name='prospectiveemploymentareadetail'),
    path('careers/prospectiveemploymentarea/add',views.CreateProspectiveEmploymentArea.as_view(),name="prospectiveemploymentareacreate"),
    path('careers/prospectiveemploymentarea/change/<pk>',views.ProspectiveEmploymentAreaUpdateView.as_view(),name="prospectiveemploymentareaedit"),
    path('careers/prospectiveemploymentarea/delete/<pk>',views.ProspectiveEmploymentAreaDeleteView.as_view(),name='prospectiveemploymentareadelete'),
    
    #ProspectiveRecruiter
    path('careers/prospectiverecruiter/list',views.ProspectiveRecruiterListView.as_view(),name="prospectiverecruiterlist"),
    path('careers/prospectiverecruiter/view/<pk>',views.ProspectiveRecruiterDetailView.as_view(),name='prospectiverecruiterdetail'),
    path('careers/prospectiverecruiter/add',views.CreateProspectiveRecruiter.as_view(),name="prospectiverecruitercreate"),
    path('careers/prospectiverecruiter/change/<pk>',views.ProspectiveRecruiterUpdateView.as_view(),name="prospectiverecruiteredit"),
    path('careers/prospectiverecruiter/delete/<pk>',views.ProspectiveRecruiterDeleteView.as_view(),name='prospectiverecruiterdelete'),
  
    #careermedia CRUD
    path('careers/careermedia/list',views.CareerMediaListView.as_view(),name="careermedialist"),
    path('careers/careermedia/view/<pk>',views.CareerMediaDetailView.as_view(),name='careermediadetail'),
    path('careers/careermedia/add',views.CreateCareerMedia.as_view(),name="careermediacreate"),
    path('careers/careermedia/change/<pk>',views.CareerMediaUpdateView.as_view(),name="careermediaedit"),
    path('careers/careermedia/delete/<pk>',views.CareerMediaDeleteView.as_view(),name='careermediadelete'),
    
    #careerpath CRUD
    path('careers/careerpath/list',views.CareerPathListView.as_view(),name="careerpathlist"),
    path('careers/careerpath/view/<pk>',views.CareerPathDetailView.as_view(),name='careerpathdetail'),
    path('careers/careerpath/add',views.CreateCareerPath.as_view(),name="careerpathcreate"),
    path('careers/careerpath/change/<pk>',views.CareerPathUpdateView.as_view(),name="careerpathedit"),
    path('careers/careerpath/delete/<pk>',views.CareerPathDeleteView.as_view(),name='careerpathdelete'),

    #careerpathstep CRUD
    path('careers/careerpathstep/list',views.CareerPathStepListView.as_view(),name="careerpathsteplist"),
    path('careers/careerpathstep/view/<pk>',views.CareerPathStepDetailView.as_view(),name='careerpathstepdetail'),
    path('careers/careerpathstep/add',views.CreateCareerPathStep.as_view(),name="careerpathstepcreate"),
    path('careers/careerpathstep/change/<pk>',views.CareerPathStepUpdateView.as_view(),name="careerpathstepedit"),
    path('careers/careerpathstep/delete/<pk>',views.CareerPathStepDeleteView.as_view(),name='careerpathstepdelete'),

    #careerFAQ CRUD
    path('careers/careerfaq/list',views.CareerFAQListView.as_view(),name="careerfaqlist"),
    path('careers/careerfaq/view/<pk>',views.CareerFAQDetailView.as_view(),name='careerfaqdetail'),
    path('careers/careerfaq/add',views.CreateCareerFAQ.as_view(),name="careerfaqcreate"),
    path('careers/careerfaq/change/<pk>',views.CareerFAQUpdateView.as_view(),name="careerfaqedit"),
    path('careers/careerfaq/delete/<pk>',views.CareerFAQDeleteView.as_view(),name='careerfaqdelete'),

    # Vocational Course Category CRUD
    path('core/vocationalcoursecategory/list', views.VocationalCourseCategoryListView.as_view(), name="vocationalcoursecategorylist"),
    path('core/vocationalcoursecategory/view/<pk>', views.VocationalCourseCategoryDetailView.as_view(), name='vocationalcoursecategorydetail'),
    path('core/vocationalcoursecategory/add', views.CreateVocationalCourseCategory.as_view(), name="vocationalcoursecategorycreate"),
    path('core/vocationalcoursecategory/change/<pk>', views.VocationalCourseCategoryUpdateView.as_view(), name="vocationalcoursecategoryedit"),
    path('core/vocationalcoursecategory/delete/<pk>', views.VocationalCourseCategoryDeleteView.as_view(), name='vocationalcoursecategorydelete'),

    # Vocational Course CRUD
    path('core/vocationalcourse/list', views.VocationalCourseListView.as_view(), name="vocationalcourselist"),
    path('core/vocationalcourse/view/<pk>', views.VocationalCourseDetailView.as_view(), name='vocationalcoursedetail'),
    path('core/vocationalcourse/add', views.CreateVocationalCourse.as_view(), name="vocationalcoursecreate"),
    path('core/vocationalcourse/change/<pk>', views.VocationalCourseUpdateView.as_view(), name="vocationalcourseedit"),
    path('core/vocationalcourse/delete/<pk>', views.VocationalCourseDeleteView.as_view(), name='vocationalcoursedelete'),

    # Extracurricular Activity Category CRUD
    path('core/extracurricularactivitycategory/list', views.ExtracurricularActivityCategoryListView.as_view(), name="extracurricularactivitycategorylist"),
    path('core/extracurricularactivitycategory/view/<pk>', views.ExtracurricularActivityCategoryDetailView.as_view(), name='extracurricularactivitycategorydetail'),
    path('core/extracurricularactivitycategory/add', views.CreateExtracurricularActivityCategory.as_view(), name="extracurricularactivitycategorycreate"),
    path('core/extracurricularactivitycategory/change/<pk>', views.ExtracurricularActivityCategoryUpdateView.as_view(), name="extracurricularactivitycategoryedit"),
    path('core/extracurricularactivitycategory/delete/<pk>', views.ExtracurricularActivityCategoryDeleteView.as_view(), name='extracurricularactivitycategorydelete'),

    # Extracurricular Activity CRUD
    path('core/extracurricularactivity/list', views.ExtracurricularActivityListView.as_view(), name="extracurricularactivitylist"),
    path('core/extracurricularactivity/view/<pk>', views.ExtracurricularActivityDetailView.as_view(), name='extracurricularactivitydetail'),
    path('core/extracurricularactivity/add', views.CreateExtracurricularActivity.as_view(), name="extracurricularactivitycreate"),
    path('core/extracurricularactivity/change/<pk>', views.ExtracurricularActivityUpdateView.as_view(), name="extracurricularactivityedit"),
    path('core/extracurricularactivity/delete/<pk>', views.ExtracurricularActivityDeleteView.as_view(), name='extracurricularactivitydelete'),

    #category CRUD
    path('careers/videocategory/list',views.CategoryListView.as_view(),name="videocategorylist"),
    path('careers/videocategory/view/<pk>',views.CategoryDetailView.as_view(),name='videocategorydetail'),
    path('careers/videocategory/add',views.CategoryCreate.as_view(),name="videocategorycreate"),
    path('careers/videocategory/change/<pk>',views.CategoryUpdateView.as_view(),name="videocategoryedit"),
    path('careers/videocategory/delete/<pk>',views.CategoryDetailView.as_view(),name='videocategorydelete'),

    #videos CRUD
    path('careers/videos/list',views.VideosListView.as_view(),name="videoslist"),
    path('careers/videos/view/<pk>',views.VideosDetailView.as_view(),name='videosdetail'),
    path('careers/videos/add',views.VideosCreate.as_view(),name="videoscreate"),
    path('careers/videos/change/<pk>',views.VideosUpdateView.as_view(),name="videosedit"),
    path('careers/videos/delete/<pk>',views.VideosDeleteView.as_view(),name='videosdelete'),


    #Core APP
    #country CRUD
    path('core/country/list',views.CountryListView.as_view(),name="countrylist"),
    path('core/country/view/<pk>',views.CountryDetailView.as_view(),name='countrydetail'),
    path('core/country/add',views.CreateCountry.as_view(),name="countrycreate"),
    path('core/country/change/<pk>',views.CountryUpdateView.as_view(),name="countryedit"),
    path('core/country/delete/<pk>',views.CountryDeleteView.as_view(),name='countrydelete'),
    
    # state CRUD
    path('core/state/list',views.StateListView.as_view(),name="statelist"),
    path('core/state/view/<pk>',views.StateDetailView.as_view(),name='statedetail'),
    path('core/state/add',views.CreateState.as_view(),name="statecreate"),
    path('core/state/change/<pk>',views.StateUpdateView.as_view(),name="stateedit"),
    path('core/state/delete/<pk>',views.StateDeleteView.as_view(),name='statedelete'),
    
    
    # state CRUD
    path('core/city/list',views.CityListView.as_view(),name="citylist"),
    path('core/city/view/<pk>',views.CityDetailView.as_view(),name='citydetail'),
    path('core/city/add',views.CreateCity.as_view(),name="citycreate"),
    path('core/city/change/<pk>',views.CityUpdateView.as_view(),name="cityedit"),
    path('core/city/delete/<pk>',views.CityDeleteView.as_view(),name='citydelete'),
    
    #Colleges APP
    #college CRUD
    path('colleges/college/list',views.CollegeListView.as_view(),name="collegelist"),
    path('colleges/college/view/<pk>',views.CollegeDetailView.as_view(),name='collegedetail'),
    path('colleges/college/add',views.CreateCollege.as_view(),name="collegecreate"),
    path('colleges/college/change/<pk>',views.CollegeUpdateView.as_view(),name="collegeedit"),
    path('colleges/college/delete/<pk>',views.CollegeDeleteView.as_view(),name='collegedelete'),
    path('colleges/college/filtercollege',views.AjaxCollegeFilter.as_view(),name='ajaxcollegefilter'),
    

    #collegeimages CRUDImages
    path('colleges/collegeimages/list',views.CollegeImagesListView.as_view(),name="collegeimageslist"),
    path('colleges/collegeimages/view/<pk>',views.CollegeImagesDetailView.as_view(),name='collegeimagesdetail'),
    path('colleges/collegeimages/add',views.CreateCollegeImages.as_view(),name="collegeimagescreate"),
    path('colleges/collegeimages/change/<pk>',views.CollegeImagesUpdateView.as_view(),name="collegeimagesedit"),
    path('colleges/collegeimages/delete/<pk>',views.CollegeImagesDeleteView.as_view(),name="collegeimagesdelete"),
    
    #collegeflattext CRUDImages
    path('colleges/collegeflattext/list',views.CollegeFlatTextListView.as_view(),name="collegeflattextlist"),
    path('colleges/collegeflattext/view/<pk>',views.CollegeFlatTextDetailView.as_view(),name='collegeflattextdetail'),
    path('colleges/collegeflattext/add',views.CreateCollegeFlatText.as_view(),name="collegeflattextcreate"),
    path('colleges/collegeflattext/change/<pk>',views.CollegeFlatTextUpdateView.as_view(),name="collegeflattextedit"),
    path('colleges/collegeflattext/delete/<pk>',views.CollegeFlatTextDeleteView.as_view(),name="collegeflattextdelete"),
    
    #collegetext CRUDImages
    path('colleges/collegetext/list',views.CollegeTextListView.as_view(),name="collegetextlist"),
    path('colleges/collegetext/view/<pk>',views.CollegeTextDetailView.as_view(),name='collegetextdetail'),
    path('colleges/collegetext/add',views.CreateCollegeText.as_view(),name="collegetextcreate"),
    path('colleges/collegetext/change/<pk>',views.CollegeTextUpdateView.as_view(),name="collegetextedit"),
    path('colleges/collegetext/delete/<pk>',views.CollegeTextDeleteView.as_view(),name="collegetextdelete"),
    
    #collegefacts CRUDImages
    path('colleges/collegefacts/list',views.CollegeFactsListView.as_view(),name="collegefactslist"),
    path('colleges/collegefacts/view/<pk>',views.CollegeFactsDetailView.as_view(),name='collegefactsdetail'),
    path('colleges/collegefacts/add',views.CreateCollegeFacts.as_view(),name="collegefactscreate"),
    path('colleges/collegefacts/change/<pk>',views.CollegeFactsUpdateView.as_view(),name="collegefactsedit"),
    path('colleges/collegefacts/delete/<pk>',views.CollegeFactsDeleteView.as_view(),name="collegefactsdelete"),
    
    #recruitingrompanies CRUDImages
    path('colleges/recruitingcompanies/list',views.RecruitingCompaniesListView.as_view(),name="recruitingcompanieslist"),
    path('colleges/recruitingcompanies/view/<pk>',views.RecruitingCompaniesDetailView.as_view(),name='recruitingcompaniesdetail'),
    path('colleges/recruitingcompanies/add',views.CreateRecruitingCompanies.as_view(),name="recruitingcompaniescreate"),
    path('colleges/recruitingcompanies/change/<pk>',views.RecruitingCompaniesUpdateView.as_view(),name="recruitingcompaniesedit"),
    path('colleges/recruitingcompanies/delete/<pk>',views.RecruitingCompaniesDeleteView.as_view(),name="recruitingcompaniesdelete"),


    #collegerecruitingrompanies CRUDImages
    path('colleges/collegerecruitingrompanies/list',views.CollegeRecruitingCompaniesListView.as_view(),name="collegerecruitingcompanieslist"),
    path('colleges/collegerecruitingrompanies/view/<pk>',views.CollegeRecruitingCompaniesDetailView.as_view(),name='collegerecruitingcompaniesdetail'),
    path('colleges/collegerecruitingrompanies/add',views.CreateCollegeRecruitingCompanies.as_view(),name="collegerecruitingcompaniescreate"),
    path('colleges/collegerecruitingrompanies/change/<pk>',views.CollegeRecruitingCompaniesUpdateView.as_view(),name="collegerecruitingcompaniesedit"),
    path('colleges/collegerecruitingrompanies/delete/<pk>',views.CollegeRecruitingCompaniesDeleteView.as_view(),name="collegerecruitingcompaniesdelete"),
    
    #facility CRUD
    path('colleges/facility/list',views.FacilityListView.as_view(),name="facilitylist"),
    path('colleges/facility/view/<pk>',views.FacilityDetailView.as_view(),name='facilitydetail'),
    path('colleges/facility/add',views.CreateFacility.as_view(),name="facilitycreate"),
    path('colleges/facility/change/<pk>',views.FacilityUpdateView.as_view(),name="facilityedit"),
    path('colleges/facility/delete/<pk>',views.FacilityDeleteView.as_view(),name="facilitydelete"),
    
    
    #collegefacility CRUD
    path('colleges/collegefacility/list',views.CollegeFacilityListView.as_view(),name="collegefacilitylist"),
    path('colleges/collegefacility/view/<pk>',views.CollegeFacilityDetailView.as_view(),name='collegefacilitydetail'),
    path('colleges/collegefacility/add',views.CreateCollegeFacility.as_view(),name="collegefacilitycreate"),
    path('colleges/collegefacility/change/<pk>',views.CollegeFacilityUpdateView.as_view(),name="collegefacilityedit"),
    path('colleges/collegefacility/delete/<pk>',views.CollegeFacilityDeleteView.as_view(),name="collegefacilitydelete"),
    
    
    #collegemoneyvalue CRUD
    path('colleges/collegemoneyvalue/list',views.CollegeMoneyValueListView.as_view(),name="collegemoneyvaluelist"),
    path('colleges/collegemoneyvalue/view/<pk>',views.CollegeMoneyValueDetailView.as_view(),name='collegemoneyvaluedetail'),
    path('colleges/collegemoneyvalue/add',views.CreateCollegeMoneyValue.as_view(),name="collegemoneyvaluecreate"),
    path('colleges/collegemoneyvalue/change/<pk>',views.CollegeMoneyValueUpdateView.as_view(),name="collegemoneyvalueedit"),
    path('colleges/collegemoneyvalue/delete/<pk>',views.CollegeMoneyValueDeleteView.as_view(),name="collegemoneyvaluedelete"),
    
    #profession CRUD
    path('careers/profession/list',views.ProfessionListView.as_view(),name="professionlist"),
    path('careers/profession/view/<pk>',views.ProfessionDetailView.as_view(),name='professiondetail'),
    path('careers/profession/add',views.CreateProfession.as_view(),name="professioncreate"),
    path('careers/profession/change/<pk>',views.ProfessionUpdateView.as_view(),name="professionedit"),
    path('careers/profession/delete/<pk>',views.ProfessionDeleteView.as_view(),name='professiondelete'),
    
    #Course APP CRUD
    #Stream CRUD
    path('courses/stream/list',views.StreamListView.as_view(),name="streamlist"),
    path('courses/stream/view/<pk>',views.StreamDetailView.as_view(),name='streamdetail'),
    path('courses/stream/add',views.CreateStream.as_view(),name="streamcreate"),
    path('courses/stream/change/<pk>',views.StreamUpdateView.as_view(),name="streamedit"),
    path('courses/stream/delete/<pk>',views.StreamDeleteView.as_view(),name='streamdelete'),
    
    #Course CRUD
    path('courses/course/list',views.CourseListView.as_view(),name="courselist"),
    path('courses/course/view/<pk>',views.CourseDetailView.as_view(),name='coursedetail'),
    path('courses/course/add',views.CreateCourse.as_view(),name="coursecreate"),
    path('courses/course/change/<pk>',views.CourseUpdateView.as_view(),name="courseedit"),
    path('courses/course/delete/<pk>',views.CourseDeleteView.as_view(),name='coursedelete'),
    
    #CourseFacts CRUD
    path('courses/coursefacts/list',views.CourseFactsListView.as_view(),name="coursefactslist"),
    path('courses/coursefacts/view/<pk>',views.CourseFactsDetailView.as_view(),name='coursefactsdetail'),
    path('courses/coursefacts/add',views.CreateCourseFacts.as_view(),name="coursefactscreate"),
    path('courses/coursefacts/change/<pk>',views.CourseFactsUpdateView.as_view(),name="coursefactsedit"),
    path('courses/coursefacts/delete/<pk>',views.CourseFactsDeleteView.as_view(),name='coursefactsdelete'),
    
    #CourseText CRUD
    path('courses/coursetext/list',views.CourseTextListView.as_view(),name="coursetextlist"),
    path('courses/coursetext/view/<pk>',views.CourseTextDetailView.as_view(),name='coursetextdetail'),
    path('courses/coursetext/add',views.CreateCourseText.as_view(),name="coursetextcreate"),
    path('courses/coursetext/change/<pk>',views.CourseTextUpdateView.as_view(),name="coursetextedit"),
    path('courses/coursetext/delete/<pk>',views.CourseTextDeleteView.as_view(),name='coursetextdelete'),
 
    #coursemoneyvalue CRUD
    path('courses/coursemoneyvalue/list',views.CourseMoneyValueListView.as_view(),name="coursemoneyvaluelist"),
    path('courses/coursemoneyvalue/view/<pk>',views.CourseMoneyValueDetailView.as_view(),name='coursemoneyvaluedetail'),
    path('courses/coursemoneyvalue/add',views.CreateCourseMoneyValue.as_view(),name="coursemoneyvaluecreate"),
    path('courses/coursemoneyvalue/change/<pk>',views.CourseMoneyValueUpdateView.as_view(),name="coursemoneyvalueedit"),
    path('courses/coursemoneyvalue/delete/<pk>',views.CourseMoneyValueDeleteView.as_view(),name="coursemoneyvaluedelete"),   
    
    #courseintake CRUD
    path('courses/courseintake/list',views.CourseIntakeListView.as_view(),name="courseintakelist"),
    path('courses/courseintake/view/<pk>',views.CourseIntakeDetailView.as_view(),name='courseintakedetail'),
    path('courses/courseintake/add',views.CreateCourseIntake.as_view(),name="courseintakecreate"),
    path('courses/courseintake/change/<pk>',views.CourseIntakeUpdateView.as_view(),name="courseintakeedit"),
    path('courses/courseintake/delete/<pk>',views.CourseIntakeDeleteView.as_view(),name="courseintakedelete"),   
    
    #courseenglighrequirements CRUD
    path('courses/courseenglighrequirements/list',views.CourseEnglighRequirementsListView.as_view(),name="courseenglighrequirementslist"),
    path('courses/courseenglighrequirements/view/<pk>',views.CourseEnglighRequirementsDetailView.as_view(),name='courseenglighrequirementsdetail'),
    path('courses/courseenglighrequirements/add',views.CreateCourseEnglighRequirements.as_view(),name="courseenglighrequirementscreate"),
    path('courses/courseenglighrequirements/change/<pk>',views.CourseEnglighRequirementsUpdateView.as_view(),name="courseenglighrequirementsedit"),
    path('courses/courseenglighrequirements/delete/<pk>',views.CourseEnglighRequirementsDeleteView.as_view(),name="courseenglighrequirementsdelete"), 
    
    #EntranceExam APP CRUD
    #entranceexam CRUD
    path('entrance_exams/entranceexam/list',views.EntranceExamListView.as_view(),name="entranceexamlist"),
    path('entrance_exams/entranceexam/view/<pk>',views.EntranceExamDetailView.as_view(),name='entranceexamdetail'),
    path('entrance_exams/entranceexam/add',views.CreateEntranceExam.as_view(),name="entranceexamcreate"),
    path('entrance_exams/entranceexam/change/<pk>',views.EntranceExamUpdateView.as_view(),name="entranceexamedit"),
    path('entrance_exams/entranceexam/delete/<pk>',views.EntranceExamDeleteView.as_view(),name="entranceexamdelete"), 
    
    #examtags CRUD
    path('entrance_exams/examtags/list',views.ExamTagsListView.as_view(),name="examtagslist"),
    path('entrance_exams/examtags/view/<pk>',views.ExamTagsDetailView.as_view(),name='examtagsdetail'),
    path('entrance_exams/examtags/add',views.CreateExamTags.as_view(),name="examtagscreate"),
    path('entrance_exams/examtags/change/<pk>',views.ExamTagsUpdateView.as_view(),name="examtagsedit"),
    path('entrance_exams/examtags/delete/<pk>',views.ExamTagsDeleteView.as_view(),name="examtagsdelete"), 
   
    #careertags CRUD
    path('careers/careertags/list',views.CareerTagsView.as_view(),name="careertagslist"),
    path('careers/careertags/view/<pk>',views.CareerTagsDetailView.as_view(),name='careertagsdetail'),
    path('careers/careertags/add',views.CreateCareerTags.as_view(),name="careertagscreate"),
    path('careers/careertags/change/<pk>',views.CareerTagsUpdateView.as_view(),name="careertagsedit"),
    path('careers/careertags/delete/<pk>',views.CareerTagsDeleteView.as_view(),name='careertagsdelete'),
    

    # blog CRUD
    path('blog/blog/list',views.BlogListView.as_view(),name="bloglist"),
    path('blog/blog/view/<pk>',views.BlogDetailView.as_view(),name='blogdetail'),
    path('blog/blog/add',views.BlogCreate.as_view(),name="blogcreate"),
    path('blog/blog/change/<pk>',views.BlogUpdateView.as_view(),name="blogedit"),
    path('blog/blog/delete/<pk>',views.BlogDeleteView.as_view(), name='blogdelete'),

    #blog category CRUD
    path('blog/blogcategory/list',views.BlogCategoryListView.as_view(),name="blogcategorylist"),
    path('blog/blogcategory/view/<pk>',views.BlogCategoryDetailView.as_view(),name='blogcategorydetail'),
    path('blog/blogcategory/add',views.BlogCategoryCreate.as_view(),name="blogcategorycreate"),
    path('blog/blogcategory/change/<pk>',views.BlogCategoryUpdateView.as_view(),name="blogcategoryedit"),
    path('blog/blogcategory/delete/<pk>',views.BlogCategoryDeleteView.as_view(), name='blogcategorydelete'),

    #blog tag CRUD
    path('blog/blogtag/list',views.BlogTagListView.as_view(),name="blogtaglist"),
    path('blog/blogtag/view/<pk>',views.BlogTagDetailView.as_view(),name="blogtagdetail"),
    path('blog/blogtag/add',views.BlogTagCreate.as_view(),name="blogtagcreate"),
    path('blog/blogtag/change/<pk>',views.BlogTagUpdateView.as_view(),name="blogtagedit"),
    path('blog/blogtag/delete/<pk>',views.BlogTagDeleteView.as_view(), name="blogtagdelete"),

#careercluster CRUD
    path('careers/careercluster/list',views.CareerClusterListView.as_view(),name="careerclusterlist"),
    path('careers/careercluster/view/<pk>',views.CareerClusterDetailView.as_view(),name='careerclusterdetail'),
    path('careers/careercluster/add',views.CreateCareerCluster.as_view(),name="careerclustercreate"),
    path('careers/careercluster/change/<pk>',views.CareerClusterUpdateView.as_view(),name="careerclusteredit"),
    path('careers/careercluster/delete/<pk>',views.CareerClusterDeleteView.as_view(),name='careerclusterdelete'),

    #review CRUD    
    path('core/review/list',views.ReviewListView.as_view(),name="reviewlist"),
    path('core/review/view/<pk>',views.ReviewDetailView.as_view(),name='reviewdetail'),
    path('core/review/add',views.ReviewCreateView.as_view(),name="reviewcreate"),
    path('core/review/change/<pk>',views.ReviewUpdateView.as_view(),name="reviewedit"),
    path('core/review/delete/<pk>',views.ReviewDeleteView.as_view(),name='reviewdelete'),

    #commonfaq CRUD    
    path('core/commonfaq/list',views.CommonFAQListView.as_view(),name="commonfaqlist"),
    path('core/commonfaq/view/<pk>',views.CommonFAQDetailView.as_view(),name='commonfaqdetail'),
    path('core/commonfaq/add',views.CommonFAQCreateView.as_view(),name="commonfaqcreate"),
    path('core/commonfaq/change/<pk>',views.CommonFAQUpdateView.as_view(),name="commonfaqedit"),
    path('core/commonfaq/delete/<pk>',views.CommonFAQDeleteView.as_view(),name='commonfaqdelete'),

    #Hobbies CRUD    
    path('core/hobbies/list',views.HobbiesListView.as_view(),name="hobbieslist"),
    path('core/hobbies/view/<pk>',views.HobbiesDetailView.as_view(),name='hobbiesdetail'),
    path('core/hobbies/add',views.HobbiesCreate.as_view(),name="hobbiescreate"),
    path('core/hobbies/change/<pk>',views.HobbiesUpdateView.as_view(),name="hobbiesedit"),
    path('core/hobbies/delete/<pk>',views.HobbiesDeleteView.as_view(),name='hobbiesdelete'),

    #Subject CRUD    
    path('core/subject/list',views.SubjectListView.as_view(),name="subjectlist"),
    path('core/subject/view/<pk>',views.SubjectDetailView.as_view(),name='subjectdetail'),
    path('core/subject/add',views.SubjectCreate.as_view(),name="subjectcreate"),
    path('core/subject/change/<pk>',views.SubjectUpdateView.as_view(),name="subjectedit"),
    path('core/subject/delete/<pk>',views.SubjectDeleteView.as_view(),name='subjectdelete'),

    #UserFigureOut CRUD    
    path('core/userfigureout/list',views.UserFigureOutListView.as_view(),name="userfigureoutlist"),
    path('core/userfigureout/view/<pk>',views.UserFigureOutDetailView.as_view(),name='userfigureoutdetail'),
    path('core/userfigureout/add',views.UserFigureOutCreate.as_view(),name="userfigureoutcreate"),
    path('core/userfigureout/change/<pk>',views.UserFigureOutUpdateView.as_view(),name="userfigureoutedit"),
    path('core/userfigureout/delete/<pk>',views.UserFigureOutDeleteView.as_view(),name='userfigureoutdelete'),

    #Stories CRUD    
    path('core/stories/list',views.StoriesListView.as_view(),name="storieslist"),
    path('core/stories/view/<pk>',views.StoriesDetailView.as_view(),name='storiesdetail'),
    path('core/stories/add',views.StoriesCreate.as_view(),name="storiescreate"),
    path('core/stories/change/<pk>',views.StoriesUpdateView.as_view(),name="storiesedit"),
    path('core/stories/delete/<pk>',views.StoriesDeleteView.as_view(),name='storiesdelete'),
    
    #APILOG CRUD    
    path('core/apilog/list',views.APILogListView.as_view(),name="apiloglist"),
    path('core/apilog/view/<pk>',views.APILogDetailView.as_view(),name='apilogdetail'),
    
    #APILOG CRUD    
    path('crm/lead/list',views.LeadListView.as_view(),name="leadlist"),
    path('crm/lead/view/<pk>',views.LeadDetailView.as_view(),name='leaddetail'),
    
    #PsychometricTest CRUD    
    path('psychometric_tests/psychometricfaq/list',views.PsychometricFAQListView.as_view(),name="psychometricfaqlist"),
    path('psychometric_tests/psychometricfaq/view/<pk>',views.PsychometricDetailView.as_view(),name='psychometricfaqdetail'),
    path('psychometric_tests/psychometricfaq/add',views.PsychometricFAQCreate.as_view(),name="psychometricfaqcreate"),
    path('psychometric_tests/psychometricfaq/change/<pk>',views.PsychometricUpdateView.as_view(),name="psychometricfaqedit"),
    path('psychometric_tests/psychometricfaq/delete/<pk>',views.PsychometricDeleteView.as_view(),name='psychometricfaqdelete'),
    
    #Assessment Students Management
    path('assessment/students/list',views.StudentListView.as_view(),name="studentlist"),
    path('assessment/student/<int:user_id>/test-history/',views.StudentTestHistoryView.as_view(),name="studenttesthistory"),
    # Student List API endpoints
    path('api/assessment/students/stats/',views.StudentListStatsAPIView.as_view(),name="studentlist_stats_api"),
    path('api/assessment/students/schools/',views.StudentListSchoolsAPIView.as_view(),name="studentlist_schools_api"),
    path('assessment/student/<int:user_id>/export/class12/',views.ExportClass12ResultsView.as_view(),name="exportclass12results"),
    path('assessment/students/export/all-class12/',views.ExportAllClass12ResultsView.as_view(),name="exportallclass12results"),
    path('assessment/students/export/all-class10/',views.ExportAllClass10ResultsView.as_view(),name="exportallclass10results"),
    path('assessment/students/export/class12-test-questions/',views.ExportClass12TestQuestionsView.as_view(),name="exportclass12testquestions"),
    path('assessment/students/export/class10-test-questions/',views.ExportClass10TestQuestionsView.as_view(),name="exportclass10testquestions"),
]