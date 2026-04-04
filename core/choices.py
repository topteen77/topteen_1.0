from random import choices

class GetString:
    @classmethod
    def get_choice_string(cls,choice):
        dictchoice = dict(cls.CHOICES)
        str = dictchoice[choice]
        return str

class ObjectStatus(object):
    DELETED=0
    ACTIVE=1
    INACTIVE=2
    CHOICES = (
        (DELETED, "Deleted"),
        (ACTIVE, "Active"),
        (INACTIVE, "Inactive"),
    )

class RegisterSource(object):
    DIRECT=0
    PROCAMPUZ=10
    CHANNEL_PARTNER=20
    CHOICES=(
        (DIRECT,"Direct"),
        (PROCAMPUZ,"Procampuz"),
        (CHANNEL_PARTNER,"Channel Partner"),
    )

class CollegeType(object):
    PRIVATE=1
    GOVERNMENT=2
    CHOICES = (
        (PRIVATE, "Private"),
        (GOVERNMENT, "Public"),
    )

class CareerMediaType(object):
    IMAGE =1
    VIDEO = 2
    PDF =3
    CHOICES =(
        (IMAGE,"Image"),
        (VIDEO,"Video"),
        (PDF,"Pdf"),
    )
    
class PublishStatus(object):
    DRAFT=0
    PUBLISHED=1
    CHOICES = (
        (DRAFT, "Draft"),
        (PUBLISHED, "Published"),
    )
    
class Currency(object):
    USD=0
    IND=1
    CHOICES = (
        (USD, "US Dollar"),
        (IND, "IND Rupees / INR")
    )
    
class FlatTextType(object):
    MOBILE=1
    EMAIL=2
    WEBSITE=3
    LOCATION=4
    CHOICES = (
        (MOBILE, 'Mobile'),
        (EMAIL,'Email'),
        (WEBSITE,'Website'),
        (LOCATION,'Location')
    )

class CollegeFactType(object):
    YEAR_OF_EST=0
    TOTAL_STUD=1
    INTERNATIONAL_STUD=2
    VIEWS=3
    CHOICES = (
        (YEAR_OF_EST, "Year of Establishment"),
        (TOTAL_STUD,"Total Students"),
        (INTERNATIONAL_STUD,"International Students"),
        (VIEWS,"Views")

    )
       
class CollegeTextType(object):
    ABOUT=1
    SERVICES_FACILITES=2
    ACCOMODATION=3
    SCHOLARSHIPS=4
    ALUMNI=5
    ADMISSIONS_REQUIREMENTS=6
    ENTRY_REQUIREMENTS=7
    CHOICES = (
        (ABOUT,'About Us'),
        (SERVICES_FACILITES,'Services & Facilities'),
        (ACCOMODATION,'Accomodation'),
        (SCHOLARSHIPS,'Scholarships'),
        (ALUMNI,'Notable Alumni'),
        (ADMISSIONS_REQUIREMENTS,'Admission Requirements'),
        (ENTRY_REQUIREMENTS,'Entry Requirements'),
    )

class CollegeMoneyType(object):
    AVG_COST_OF_LIVING=0
    AVG_TUITION_FEE_PA_MIN=1
    AVG_TUITION_FEE_PA_MAX=2
    TUITION_FEE_UG_FROM=3
    TUITION_FEE_UG_TO=4
    TUITION_FEE_PG_FROM=5
    TUITION_FEE_PG_TO=6
    CHOICES = (
        (AVG_COST_OF_LIVING, "Average Cost of Living"),
        (AVG_TUITION_FEE_PA_MAX, "Average Tuition Fee Max"),
        (AVG_TUITION_FEE_PA_MIN, "Average Tuition Fee Min"),
        (TUITION_FEE_UG_FROM, "Minimum Tuition Fee For UG"),
        (TUITION_FEE_UG_TO, "Maximum Tuition Fee for UG"),
        (TUITION_FEE_PG_FROM, "Minimum Tuition Fee for PG"),
        (TUITION_FEE_PG_TO, "Maximum Tuition Fee for PG"),
        
        
    )
    
class ProgramLevel(object):
    UG=0
    PG=1
    CHOICES = (
        (UG, "Under Graduate"),
        (PG, "Post Graduate"),

    )
    
class CourseFactType(object):
    START_DATE=0
    STUDY_MODE=1
    LOCATION=2
    APPLICATION_PROCESSING_DAYS=3
    CHOICES = (
        (START_DATE, "Start Date"),
        (STUDY_MODE, "Study Mode"),
        (LOCATION, "Location"),
        (APPLICATION_PROCESSING_DAYS, "Application Processing Days"),

    )
class CourseType(object):
    FULL_TIME_ON_CAMPUS=0
    CHOICES = (
        (FULL_TIME_ON_CAMPUS, "Full Time On Campus"),
    )
class CourseTextType(object):
    OVERVIEW=1
    ADMISSIONS=2
    WORK_PERMIT=3
    CHOICES = (
        (OVERVIEW,'Overview'),
        (ADMISSIONS,'Admissions'),
        (WORK_PERMIT,'Work Permit'),
    )
    
class CourseMoneyType(object):
    TUITION_FEE=0
    
    CHOICES = (
        (TUITION_FEE, "Tuition Fee"),
    )

class EnglishRequirementTest(object):
    IELETS=0
    TOEFL=1
    PTE=2
    CHOICES = (
        (IELETS, "IELTS"),
        (TOEFL, "TOEFL"),
        (PTE, "PTE"),
    )

class EnglishRequirementTestScoreType(object):
    MIN_OVERALL_SCORE=0
    MINIMUM_LISTENING=1
    MINIMUM_READING=2
    MINIMUM_WRITING=3
    MINIMUM_SPEAKING=4
    CHOICES = (
        (MIN_OVERALL_SCORE, "Minimum Overall Score"),
        (MINIMUM_LISTENING, "Minimum Listening"),
        (MINIMUM_READING, "Minimum Reading"),
        (MINIMUM_WRITING, "Minimum Writing"),
        (MINIMUM_SPEAKING, "Minimum Speaking"),
        
    )
class UniversityType(object):
    COLLEGE=0
    UNIVERSITY=1
    CHOICES = (
        (COLLEGE,"College"),
        (UNIVERSITY,"University"),
        )

class CommunicationTypeChooices(object):
    EMAIL=1
    SMS=2
    CHOICES = (
        (EMAIL, 'Email'),
        (SMS, 'SMS')

    )

class SalaryType(object):
    PER_ANNUM=1
    PER_MONTH=2
    CHOICE=(
        (PER_ANNUM,"PER ANNUM"),
        (PER_MONTH,"PER MONTH"),
    )
class EntranceExamTypechoice(object):
    after_10_class=1
    after_12_class=2
    BOTH=3
    after_college=4
    CHOICE=(
        (after_10_class,'After 10th'),
        (after_12_class,'After 12th'),
        (BOTH,'After 10th or 12th'),
        (after_college,'After College'),
    )
    
    @classmethod
    def get_choice_string(cls,choice):
        dictchoice = dict(cls.CHOICE)
        str = dictchoice[choice]
        return str
    
class SkillLabCourseTypeChoice(object):
    after_10_class=1
    after_12_class=2
    BOTH=3
    after_college=4
    CHOICE=(
        (after_10_class,'After 10th'),
        (after_12_class,'After 12th'),
        (BOTH,'After 10th or 12th'),
        (after_college,'After College'),
    )

class SkillLabAcivityChoice(object):
    activity=1
    worksheet=2
    CHOICE=(
        (activity,'Activity'),
        (worksheet,'Worksheet'),
    )

class FAQType(object):
    parent=0
    student=1
    CHOICES=(
        (parent,'Parent'),
        (student,'Student'),
    )

class FAQFeaturedType(object):
    NONE=0
    HOME=1
    CHOICES=(
        (NONE,'None'),
        (HOME,'Home'),
    )

class GatewayChoices(object):
    RAZORPAY=1
    ICICIEAZYPAY=2
    CHOICES = (
        (RAZORPAY, 'Razorpay'),
        (ICICIEAZYPAY,"Icici eazypay"),
    )

class YesNoChoices(object):
    YES=1
    NO=0
    CHOICES = (
        (YES, 'Yes'),
        (NO, 'No'),
    )

class PsychometricTestType(object):
    BASIC=10
    ADVANCED=20    

    CHOICES=(
        (BASIC,"Basic test"),
        (ADVANCED,"Advanced test")
    )

class PaymentObjectType(object):
    PYSCHOMETRICTESTDETAIL=10
    SKILLLABCOURSE=20
    COUNSELOR=30
    CHOICES=(
        (PYSCHOMETRICTESTDETAIL,"PsychometricTestDetail"),
        (SKILLLABCOURSE,"Skilllabcourse"),
        (COUNSELOR,"Counselor"),
    )

class GenderChoices(object):
    UNKNOWN=10
    MALE=20
    FEMALE=30
    CHOICES = (
        (UNKNOWN, "Unknown"),
        (MALE, "Male"),
        (FEMALE, "Female"),
    )

class UserResumeProficiency(object):
    BEGINNER=10
    INTERMEDIATE=20
    EXPERT=30
    CHOICES=(
        (BEGINNER,"Beginner"),
        (INTERMEDIATE,"Intermediate"),
        (EXPERT,"Expert"),
    )

class StoryObjectType(object):
    SUBJECT=10
    CHOICES=(
        (SUBJECT,"Subject"),
    )

class FileType(object):
    VIDEO=10
    IMAGE=20
    CHOICES=(
        (VIDEO,"Video"),
        (IMAGE,"Image"),
    )
    
class LeadAction(object):
    PSYCHOMETRICTESTCOUNSLING=10
    CHOICES=(
        (PSYCHOMETRICTESTCOUNSLING,"Psychometric test"),
    )
    
class LeadStatus(object):
    FRESH=10
    COMPLETE=20
    CHOICES=(
        (FRESH,"Fresh"),
        (COMPLETE,"Complate"),
    )
class UserType(object):
    STUDENT=1
    INSTITUTE=2
    INSTITUTEGROUPADMIN=3
    COUNSELOR=4
    MARKETINGGROUPADMIN=5
    PARENT=6
    CHOICES=(
        (STUDENT,"Student"),
        (INSTITUTE,"Institute"),
        (INSTITUTEGROUPADMIN,"Institute group admin"),
        (COUNSELOR,"Counselor"),
        (MARKETINGGROUPADMIN,"Marketing Group Admin"),
        (PARENT,"Parent"),
    )

class UserStatus(object):
    BLOCK=1
    UNBLOCK=2
    CHOICES=(
        (BLOCK,"Block"),
        (UNBLOCK,"Unblock"),
    )

class InstituteStatus(object):
    APPROVED=1
    REJECTED=2
    PENDING=3
    CHOICES=(
        (APPROVED,"Approved"),
        (REJECTED,"Rejected"),
        (PENDING,"Pending"),
    )
    

class InstituteType(object):
    COLLEGE=1
    HIGHSCHOOL=2
    SENIORSECONDARYSCHOOL=3
    UNIVERSITIES=4
    COACHINGINSTITUTE=5
    LANGUAGEINSTITUTE=6
    OTHER=7
    CHOICES=(
        (COLLEGE,"College"),
        (HIGHSCHOOL,"High School"),
        (SENIORSECONDARYSCHOOL,"Senior secondary School"),
        (UNIVERSITIES,"Universities"),
        (LANGUAGEINSTITUTE,"Language Institute"),
        (COACHINGINSTITUTE,"Coaching Institute"),
        (OTHER,"Other")
    )


# Mindmap layout types for dedicated mindmap page (variation 1–16)
# Used in Core website settings and career mindmap dropdown.
MINDMAP_TYPE_CHOICES = (
    ('1', 'Compact'),
    ('2', 'Minimal'),
    ('3', 'Fullscreen'),
    ('4', 'Sidebar'),
    ('5', 'Bottom Controls'),
    ('6', 'Radial'),
    ('7', 'Cards'),
    ('8', 'Flow'),
    ('9', 'Network'),
    ('10', 'Timeline'),
    ('11', 'Vertical Radial'),
    ('12', 'Vertical Cards'),
    ('13', 'Vertical Flow'),
    ('14', 'Vertical Network'),
    ('15', 'Vertical Timeline'),
    ('16', 'Classic mindmap — horizontal pills & curved links'),
    ('17', 'Classic mindmap — vertical (top-down pills)'),
)

# Counselor course/chapter/part static JSON mindmaps (counselor_mindmap_widget.html).
# Stored as Configuration DEFAULT_course_MINDMAP_TYPE (numeric string 1–9; see counselor.mindmap_config._NUM_TO_WIDGET_MAP_TYPE).
# Aligns 6/7 with career layouts where useful. 8 = classic horizontal; 9 = classic vertical.
COURSE_MINDMAP_CONFIG_CHOICES = (
    ('1', 'Tree — Markmap (collapsible outline)'),
    ('2', 'Concept map — rings'),
    ('3', 'Radial tree — D3'),
    ('4', 'Cluster / dendrogram — D3'),
    ('5', 'Career-style radial — drill & zoom'),
    ('6', 'D3 radial tree (same spirit as career “Radial”)'),
    ('7', 'Career-style radial (same spirit as career “Cards” / interactive)'),
    ('8', 'Classic mindmap — horizontal pills & curved links'),
    ('9', 'Classic mindmap — vertical (top-down pills)'),
)