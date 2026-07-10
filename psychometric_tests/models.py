from django.db import models
from core.models import BaseModel,BaseMoneyModel, SeoModel,SlugModel,Configuration
from users.models import User
from core import choices
import json
from django.conf import settings
from .central_test.centraltest import CentralTestService
from communication.com_service import ComService
from django.core.signing import Signer
from django.urls import reverse,reverse_lazy
from ckeditor.fields import RichTextField
from skilllab.models import SkillLabCourse,SkilllabCoursePayment

class PsychometricTestPayment(BaseModel,BaseMoneyModel):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="psychometrictest")
    gateway_receipt=models.CharField(max_length=120,blank=True,null=True)
    test_type = models.SmallIntegerField(choices=choices.PsychometricTestType.CHOICES)
    is_success = models.SmallIntegerField(choices=choices.YesNoChoices.CHOICES,default=choices.YesNoChoices.NO)

    def get_test_name(self):
        """Get the display name for the test (Stream Sorter or Career Direction)"""
        if self.test_type == choices.PsychometricTestType.BASIC:
            return "Stream Sorter"
        elif self.test_type == choices.PsychometricTestType.ADVANCED:
            return "Career Direction"
        return self.get_test_type_display()

    def create_central_test_candidate(self):
        self.create_skilllab_course_payment()
        cntrltstcnd=CentralTestCandidate.objects.filter(user=self.user)
        if cntrltstcnd.exists():
            cntrltstcnd=cntrltstcnd.last()
            self.create_candidate_test(cntrltstcnd)
        else:
            ct=CentralTestService()
            candidate,error=ct.create_candidate(self.user)
            if not error:
                c=CentralTestCandidate()
                c.user=self.user
                c.candidate_id=candidate.get("id")
                c.title_id=candidate.get("title_id")
                c.country_code=candidate.get("country_code")
                c.email=candidate.get("email")
                c.login=candidate.get("login")
                c.last_name=candidate.get("lastname")
                c.first_name=candidate.get("firstname")
                c.last_connection_date=candidate.get("last_connection_date")
                c.groups=candidate.get("groups")
                c.postal_code=candidate.get("postal_code")
                c.phone=candidate.get("phone")
                c.candidate_function=candidate.get("function")
                c.sector_id=candidate.get("sector_id")
                c.observations=candidate.get("observations")
                c.save()
                self.create_candidate_test(c)
    
    def create_skilllab_course_payment(self):
        course= SkillLabCourse.objects.get(id=settings.PSYCHOMETRIC_COURSE_FREE_ID)
        course_payment = SkilllabCoursePayment.objects.get_or_create(skilllab_course=course,user=self.user,is_success=choices.YesNoChoices.YES)
    
    def create_candidate_test(self,candidate):
        from .task import send_pychometric_test_payment_success_mail

        ## calling to the centeral test from here!!
        ct=CentralTestService()
        response,error=ct.invite_candidate_take_test(candidate)

        


        if not error:
            candidate_test=CandidateTest()
            candidate_test.pyschometric_test_payment=self
            candidate_test.central_test_candidate=candidate
            candidate_test.assessment_id=response.get("id")
            if response.get("link",None):
                candidate_test.test_link=response.get("link")
            else:
                candidate_test.test_link=response.get("url")
            candidate_test.save()
            send_pychometric_test_payment_success_mail.delay(self.id)

    def send_payment_mail(self):
        cs=ComService()
        cs.send_pyschometric_payment_success_mail(self.user.email,self)

    def get_test_payment_success_fail_url(self):
        d={}
        sign = Signer()
        enc_id=sign.sign_object(({"enc_id":self.id}))
        d["success_url"]=reverse('psychometrictests:pyschometrictestpaymentsuccess',kwargs={'enc_id':enc_id})
        d["fail_url"]=reverse('psychometrictests:pyschometrictestpaymentfail',kwargs={'enc_id':enc_id})
        return d
        

class CentralTestCandidate(BaseModel):
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name="central_test_candidate")
    candidate_id=models.IntegerField()
    title_id=models.IntegerField()
    country_code=models.CharField(max_length=120,null=True,blank=True)
    email=models.CharField(max_length=120,null=True,blank=True)
    login=models.CharField(max_length=255,null=True,blank=True)
    last_name=models.CharField(max_length=255,null=True,blank=True)
    first_name=models.CharField(max_length=120,null=True,blank=True)
    last_connection_date=models.CharField(max_length=120,null=True,blank=True)
    groups=models.JSONField(null=True,blank=True)
    postal_code=models.CharField(max_length=120,null=True,blank=True)
    phone=models.CharField(max_length=120,null=True,blank=True)
    candidate_function=models.CharField(max_length=120,null=True,blank=True)
    sector_id=models.CharField(max_length=120,null=True,blank=True)
    observations=models.JSONField(null=True,blank=True)


    def get_test_report_or_test_link(self):
        from .task import create_pyschometric_assessment_result
        test = self.candidate_test.last()
        if not test:
            return "#"
        if test.is_success == choices.YesNoChoices.YES:
            return test.get_pyschometric_test_result_url()
        else:
            return test.test_link

    def last_test_is_success(self):
        from .task import create_pyschometric_assessment_result
        test = self.candidate_test.last()
        if test and test.is_success == choices.YesNoChoices.YES:
            return True
        else:
            self.update_last_test(test)
            test = self.candidate_test.last()
            if test.is_success == choices.YesNoChoices.YES:
                return True
            else:
                return False
            
    def students_test_is_success(self):
        from .task import create_pyschometric_assessment_result
        test = self.candidate_test.last()
        if not test:
            return False
        if test.is_success == choices.YesNoChoices.YES:
            return True
        else:
            test = self.candidate_test.last()
            if test.is_success == choices.YesNoChoices.YES:
                return True
            else:
                return False

    def update_last_test(self,test):
        from .task import create_pyschometric_assessment_result
        if not test.is_success:
            ct=CentralTestService()
            pending,error=ct.check_test_pending_or_complete(self.candidate_id)
            if not pending:
               completed,error=ct.get_complete_test(test.assessment_id,self.candidate_id)
               if completed:
                    test.is_success=choices.YesNoChoices.YES
                    test.save()
                    create_pyschometric_assessment_result.delay(test.id)



class CandidateTest(BaseModel):
    pyschometric_test_payment=models.ForeignKey(PsychometricTestPayment,on_delete=models.CASCADE,null=True,blank=True,related_name="candidate_test")
    central_test_candidate=models.ForeignKey(CentralTestCandidate,on_delete=models.CASCADE,null=True,blank=True,related_name="candidate_test")
    assessment_id=models.IntegerField()
    test_link=models.CharField(max_length=255,null=True,blank=True)
    is_success = models.SmallIntegerField(choices=choices.YesNoChoices.CHOICES,default=choices.YesNoChoices.NO)

    def get_pyschometric_test_result_url(self):
        if PsychometricTestResult.objects.filter(assessment=self).exists():
            return reverse_lazy("psychometrictests:pyschometrictestreport",args=[self.psychometric_test_results.id])
        return "#"

class PsychometricTestResult(BaseModel):
    assessment = models.OneToOneField(CandidateTest,null=True,blank=True,on_delete=models.CASCADE,related_name="psychometric_test_results")
    realistic=models.FloatField(null=True,blank=True)
    investigative=models.FloatField(null=True,blank=True)
    artistic=models.FloatField(null=True,blank=True)
    social=models.FloatField(null=True,blank=True)
    entrepreneurial=models.FloatField(null=True,blank=True)
    conventional=models.FloatField(null=True,blank=True)
    about = models.TextField(null=True,blank=True)
    suggested_trades=models.TextField(null=True,blank=True)
    pdf_url=models.CharField(max_length=250,null=True,blank=True)
    xml_file_url=models.CharField(max_length=250,null=True,blank=True)
    

    def get_riasec_best_score(self):
        riasecdict={"Realistic":self.realistic,"Investigative":self.investigative,"Artistic":self.artistic,"Social":self.social,"Entrepreneurial":self.entrepreneurial,"Conventional":self.conventional}
        sorted_dict=dict(sorted(riasecdict.items(), key=lambda x:x[1], reverse=True)[:3])
        return sorted_dict

    def get_sort_form_riasec(self):
        d=self.get_riasec_best_score()
        keys=list(d.keys())
        return keys[0][0]+keys[1][0]+keys[2][0]


    def get_score_color_code(self,key):
        d={"Realistic":"bg-[#6495ED]","Investigative":"bg-[#FFD700]","Artistic":"bg-[#FFA500]","Social":"bg-[#FF4500]","Entrepreneurial":"bg-[#32CD32]","Conventional":"bg-[#BA55D3]"}
        return d[key]

class PsychometricFAQ(BaseModel):
    question = models.CharField(max_length=300,null=True)
    answer = RichTextField(null=True)
    priority = models.PositiveSmallIntegerField(default=1,help_text="1 is higher than 2")


class Assessment(BaseModel):
    """Atomic psychometric test unit (personality, interest, aptitude, etc.)."""
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=200)
    track = models.CharField(max_length=20, choices=choices.PsychometricTrack.CHOICES)
    engine_key = models.CharField(
        max_length=40,
        help_text="Class 10: test1/test2/test3. Post-matric: post_matric Test pk as string.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('track', 'code')

    def __str__(self):
        return f"{self.name} ({self.code})"


class PsychometricPackage(BaseModel):
    """Sellable package composed of one or more assessments."""
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    track = models.CharField(max_length=20, choices=choices.PsychometricTrack.CHOICES)
    credit_cost = models.PositiveSmallIntegerField(
        default=1,
        help_text="Assignment credits deducted when this package is assigned to a student.",
    )
    list_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_legacy_bundle = models.BooleanField(
        default=False,
        help_text="Maps to legacy Stream Sorter / Career Direction full bundles.",
    )
    is_active = models.BooleanField(default=True)
    assessments = models.ManyToManyField(
        Assessment,
        through='PackageAssessment',
        related_name='packages',
    )

    class Meta:
        ordering = ('track', 'name')

    def __str__(self):
        return self.name


class PackageAssessment(BaseModel):
    package = models.ForeignKey(
        PsychometricPackage,
        on_delete=models.CASCADE,
        related_name='package_assessments',
    )
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='package_assessments',
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ('package', 'assessment')
        ordering = ('sort_order', 'id')

    def __str__(self):
        return f"{self.package.code} -> {self.assessment.code}"


class InstitutePackagePrice(BaseModel):
    institute = models.ForeignKey(
        'institute.Institute',
        on_delete=models.CASCADE,
        related_name='package_prices',
    )
    package = models.ForeignKey(
        PsychometricPackage,
        on_delete=models.CASCADE,
        related_name='institute_prices',
    )
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ('institute', 'package')

    def __str__(self):
        return f"{self.institute} — {self.package.code} @ {self.unit_price}"


class StudentPackageAssignment(BaseModel):
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='package_assignments',
    )
    package = models.ForeignKey(
        PsychometricPackage,
        on_delete=models.PROTECT,
        related_name='student_assignments',
    )
    institute = models.ForeignKey(
        'institute.Institute',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='package_assignments',
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='package_assignments_made',
    )
    credits_charged = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('-created',)

    def __str__(self):
        return f"{self.student_id} <- {self.package.code}"


class StudentAssessmentEntitlement(BaseModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assessment_entitlements',
    )
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='entitlements',
    )
    source = models.CharField(
        max_length=30,
        choices=choices.EntitlementSource.CHOICES,
        default=choices.EntitlementSource.PACKAGE_ASSIGNMENT,
    )
    package_assignment = models.ForeignKey(
        StudentPackageAssignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entitlements',
    )
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'assessment')
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user_id} — {self.assessment.code}"