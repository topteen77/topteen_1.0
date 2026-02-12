from django.db import models
from core import choices
from core.models import BaseModel,SlugModel
from users.models import User
from psychometric_tests.models import PsychometricTestResult,PsychometricTestPayment,CandidateTest

from app.models import TestCompletion, Results
from core.models import Configuration
from psychometric_tests.task import create_central_test_candidate
from django.db.models import Sum
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
# Create your models here.

def get_global_remain_credits():
        credits=Institute.objects.aggregate(sum=Sum("credit_counts"))
        global_credits=settings.CREDIT_LIMIT
        if credits['sum'] is not None:
            remain_credit=global_credits-credits['sum']
        else:
            remain_credit=global_credits
        return remain_credit

def credit_validator(value):
    credits=Institute.objects.aggregate(sum=Sum("credit_counts"))
    global_credits=settings.CREDIT_LIMIT
    remain_credit=global_credits-credits['sum']
    if value>=remain_credit:
        raise ValidationError(_("Value must be less than {}".format(remain_credit)))

class InstituteGroup(BaseModel):
    group_name=models.CharField(max_length=250)
    institute_group_admin=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name="institute_group",limit_choices_to={'user_type':choices.UserType.INSTITUTEGROUPADMIN})

    def __str__(self):
        return self.group_name
    
class InstituteMarketingGroup(BaseModel):
    m_group_name = models.CharField(max_length=250)
    marketing_group_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marketing_group",
        limit_choices_to={'user_type': choices.UserType.MARKETINGGROUPADMIN}  # Changed from MARKETING to MARKETINGGROUPADMIN
    )

    def __str__(self):
        return self.m_group_name

class Institute(BaseModel, SlugModel):
    """
    Model representing an educational institute.
    """
    name = models.CharField(
        max_length=500,
        verbose_name="Institute Name",
        help_text="Name of the educational institute"
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="institute_created",
        limit_choices_to={'user_type': choices.UserType.INSTITUTE},
        verbose_name="Created By"
    )
    logo = models.ImageField(
        upload_to="upload/institute/logo/",
        null=True,
        max_length=250,
        verbose_name="Institute Logo"
    )
    address = models.CharField(
        max_length=350,
        null=True,
        blank=True,
        verbose_name="Address"
    )
    contact_info = models.CharField(
        max_length=250,
        null=True,
        blank=True,
        verbose_name="Contact Information"
    )
    administrator_contact = models.CharField(
        max_length=250,
        null=True,
        blank=True,
        verbose_name="Administrator Contact"
    )
    credit_counts = models.PositiveIntegerField(
        default=0,
        validators=[credit_validator],
        verbose_name="Credit Count",
        help_text="Number of credits allocated to the institute"
    )
    institute_group = models.ForeignKey(
        InstituteGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="institute",
        verbose_name="Institute Group"
    )
    marketing_group = models.ForeignKey(
        InstituteMarketingGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="institute",
        verbose_name="Marketing Institute Group"
    )
    institute_type = models.SmallIntegerField(
        choices=choices.InstituteType.CHOICES,default=choices.InstituteType.COLLEGE,
        verbose_name="Institute Type"
    )

    institute_status = models.SmallIntegerField(
        choices=choices.InstituteStatus.CHOICES,
        default=choices.InstituteStatus.PENDING,
        verbose_name="institute Status",
        help_text="Current status of the institute"
    )

    is_demo_institute = models.BooleanField(
        default=False,
        verbose_name="Demo institute",
        help_text=_("Mark as demo institute (e.g. for display on institute demo login or filtering)."),
    )
    is_system_demo = models.BooleanField(
        default=False,
        editable=False,
        verbose_name="System demo",
        help_text=_("Set only by the system for the fixed demo dataset. Only such data can be reset. Do not edit."),
    )

    # Seat Capacity fields for streams
    pcm = models.PositiveIntegerField(
        default=100,
        verbose_name="PCM Seat Capacity",
        help_text="Seat capacity for PCM stream"
    )
    cbm = models.PositiveIntegerField(
        default=100,
        verbose_name="CBM Seat Capacity",
        help_text="Seat capacity for CBM stream"
    )
    comm = models.PositiveIntegerField(
        default=100,
        verbose_name="COMM Seat Capacity",
        help_text="Seat capacity for COMM stream"
    )
    hme = models.PositiveIntegerField(
        default=100,
        verbose_name="HME Seat Capacity",
        help_text="Seat capacity for HME stream"
    )
    hmb = models.PositiveIntegerField(
        default=100,
        verbose_name="HMB Seat Capacity",
        help_text="Seat capacity for HMB stream"
    )

    class Meta:
        verbose_name = "Institute"
        verbose_name_plural = "Institutes"
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['address']),
        ]

    def __str__(self):
        """String representation of the Institute."""
        return self.name

    def get_current_credits_count(self):
        """
        Calculate and return the current available credits.
        
        Returns:
            int: Number of remaining credits
        """
        sm = StudentManagement.objects.filter(institute=self).count()
        current_credits = self.credit_counts - sm
        return current_credits
    
    def is_valid_credit_count(self):
        """
        Check if the institute has valid credit count.
        
        Returns:
            bool: True if credit count is valid, False otherwise
        """
        sm = StudentManagement.objects.filter(institute=self).count()
        current_credits = self.credit_counts - sm
        return 0 < current_credits <= self.credit_counts

    def clean(self):
        """
        Custom validation for the Institute model.
        """
        super().clean()
        if self.credit_counts < 0:
            raise ValidationError({
                'credit_counts': 'Credit count cannot be negative.'
            })
        
class ClassAndSection(BaseModel):
    class_and_section=models.CharField(max_length=100,null=True,blank=True)
    stream=models.CharField(max_length=100,null=True,blank=True)

    def __str__(self):
        return self.class_and_section

class StudentManagement(BaseModel):
    institute=models.ForeignKey(Institute,null=True,on_delete=models.SET_NULL,related_name="student_management")
    student=models.ForeignKey(User,null=True,on_delete=models.SET_NULL,related_name="student_management")
    class_and_section=models.ForeignKey(ClassAndSection,null=True,blank=True,on_delete=models.SET_NULL,related_name="student_management")

    # ForeignKey to Counselor Manish
    counselor = models.ForeignKey('counselor.Counselor', null=True, blank=True, on_delete=models.SET_NULL, related_name="student_management")

    def get_psychometric_result(self):
        return PsychometricTestResult.objects.filter(assessment__central_test_candidate__user=self.student)

    def get_test_result(self):
        test_res = Results.objects.filter(user=self.student)
        success_count = sum(1 for result in test_res if result.is_test_successful)
        return success_count
    
    def create_student_psychometric_test(self):
        user=self.student
        sm=StudentManagement.objects.filter(student=user).exists()
        if sm:
            gateway_receipt="Student_Psychometric_test_receipt_{}".format(user.id)
            amount=Configuration.get('EAZYPAY_PSYCHOMETRIC_TEST_AMOUNT',10,editable=True)
            test_type=choices.PsychometricTestType.BASIC
            test,_test=PsychometricTestPayment.objects.get_or_create(user=user,gateway_receipt=gateway_receipt,test_type=test_type,is_success=choices.YesNoChoices.NO,amount=amount,currency=choices.Currency.IND)
            test.is_success=choices.YesNoChoices.YES
            test.save()
            create_central_test_candidate.delay(test.id)

    def get_student_test_link(self):
        ct=CandidateTest.objects.filter(central_test_candidate__user=self.student)
        if ct.exists():
            return ct.last().test_link
        else:
            return "#"
        
    def __str__(self):
        return f"Student: {self.student}"

class InstituteAccountDeletion(BaseModel):
    institute=models.ForeignKey(Institute,null=True,on_delete=models.SET_NULL,related_name="account_deletion")
    reason=models.CharField(max_length=500,null=True,blank=True)

class InstituteLog(BaseModel):
    institute=models.ForeignKey(Institute,on_delete=models.SET_NULL,null=True,related_name="institute_log")
    email=models.CharField(max_length=500,null=True,blank=True)
    students_counts=models.PositiveIntegerField(default=0)

    def get_created_students(self):
        stu_counts=self.students_counts-len(eval(self.email))
        if stu_counts<0:
            return 0
        else:
            return stu_counts